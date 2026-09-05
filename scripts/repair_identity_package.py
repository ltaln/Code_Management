"""Rebuild packages from one saved Firecrawl snapshot after an identity adapter fix."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from data_engine.collector import collection_report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,required=True)
    parser.add_argument('--task-id',required=True)
    args=parser.parse_args()
    if len(args.task_id)!=32 or any(c not in '0123456789abcdef' for c in args.task_id):
        raise SystemExit('INVALID_TASK_ID')

    db=sqlite3.connect(args.db)
    db.row_factory=sqlite3.Row
    task=db.execute('SELECT * FROM tasks WHERE id=?',(args.task_id,)).fetchone()
    if not task or task['status']!='PARTIAL':
        raise SystemExit('TASK_MUST_BE_PARTIAL')
    payload=json.loads(task['payload'])
    if payload.get('mode')!='prediction':
        raise SystemExit('TASK_MUST_BE_PREDICTION')

    task_root=args.db.parent/'collections'/args.task_id
    attempts=[p for p in task_root.iterdir() if p.is_dir() and (p/'receipt.json').is_file()]
    if len(attempts)!=1:
        raise SystemExit('EXACTLY_ONE_SAVED_ATTEMPT_REQUIRED')
    attempt=attempts[0]
    original=json.loads((attempt/'receipt.json').read_text(encoding='utf-8'))
    if original.get('task_id')!=args.task_id or original.get('date')!=payload.get('date'):
        raise SystemExit('RECEIPT_IDENTITY_MISMATCH')
    latest=json.loads((attempt/'data/raw'/payload['date']/'latest.json').read_text(encoding='utf-8'))
    snapshot=(attempt/latest['snapshot_dir']).resolve()
    if not snapshot.is_relative_to(attempt.resolve()) or not snapshot.is_dir():
        raise SystemExit('INVALID_SNAPSHOT_PATH')

    subprocess.run([sys.executable,str(ROOT/'data_engine/vendor/build_match_packages.py'),
                    '--date',payload['date'],'--snapshot-dir',str(snapshot),
                    '--output-root',str(attempt/'data/matches')],check=True)
    package_ref=json.loads((attempt/'data/matches'/payload['date']/'latest.json').read_text(encoding='utf-8'))
    index=json.loads((attempt/package_ref['index']).read_text(encoding='utf-8'))
    discovery=json.loads((snapshot/'url_discovery.json').read_text(encoding='utf-8'))
    if (index['match_count']<1 or index['complete_matches']!=index['match_count']
            or discovery['truncated'] or discovery['failed_pages']):
        raise SystemExit('REPAIRED_PACKAGE_NOT_COMPLETE')

    result=dict(original)
    result.update(package_version='identity-v2',package_index=package_ref['index'],
                  package_dir=package_ref['package_dir'],match_count=index['match_count'],
                  complete_matches=index['complete_matches'],collection_complete=True,
                  prediction_eligible=bool(original.get('t_minus_30_verified')),
                  identity_repaired_at=datetime.now(timezone.utc).isoformat(),
                  identity_repair='identity-v2-missing-data-degrades')
    result['files']={p.relative_to(attempt).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in attempt.rglob('*.json') if p.name!='receipt.identity-v2.json'}
    encoded=json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2).encode('utf-8')
    repaired=attempt/'receipt.identity-v2.json'
    with repaired.open('xb') as output:
        output.write(encoded)
        output.flush()
    result['receipt_sha256']=hashlib.sha256(encoded).hexdigest()
    report=collection_report(result)+'\n\n身份包由同一 Firecrawl 快照重新构建；原始页面未重新采集或改写。'

    with db:
        updated=db.execute("UPDATE tasks SET status='AWAITING_GPT',input_ref=?,report=?,blockers='[]',updated=? WHERE id=? AND status='PARTIAL'",
                           (json.dumps(result,ensure_ascii=False,sort_keys=True),report,time.time(),args.task_id)).rowcount
        if not updated:
            raise SystemExit('TASK_STATE_CHANGED')
        db.execute('INSERT INTO events(task_id,at,status,detail) VALUES(?,?,?,?)',
                   (args.task_id,time.time(),'AWAITING_GPT','同一快照已按 identity-v2 重建；缺失资料降级处理，等待 GPT 分析'))
    print(json.dumps({'task_id':args.task_id,'status':'AWAITING_GPT',
                      'snapshot_id':result['snapshot_id'],'match_count':result['match_count'],
                      'receipt_sha256':result['receipt_sha256']},ensure_ascii=False))


if __name__=='__main__':
    main()
