"""Run the existing, pinned Firecrawl collector in a private per-task directory."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

VENDOR = Path(__file__).with_name('vendor')


class CollectionError(Exception):
    pass


def check_vendor():
    lock = json.loads((VENDOR / 'source.json').read_text(encoding='utf-8'))
    for name, expected in lock['files'].items():
        if hashlib.sha256((VENDOR/name).read_bytes()).hexdigest() != expected:
            raise CollectionError('COLLECTOR_HASH_MISMATCH')


def supervise(args, cwd, env, pulse, timeout):
    # Logs stay on the server. Provider errors may contain private information.
    with (cwd/'collector.log').open('ab') as log:
        process = subprocess.Popen(args, cwd=cwd, env=env, stdout=log, stderr=log)
        started = time.monotonic()
        try:
            while process.poll() is None:
                if not pulse():
                    raise CollectionError('TASK_CANCELLED_OR_LEASE_LOST')
                if time.monotonic()-started > timeout:
                    raise CollectionError('COLLECTION_TIMEOUT')
                time.sleep(2)
            if process.returncode:
                raise CollectionError('COLLECTOR_PROCESS_FAILED')
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


class FirecrawlCollector:
    def __init__(self, storage):
        self.storage = Path(storage)

    def collect(self, task_id, target_date, pulse, attempt_id):
        check_vendor()
        endpoint = os.environ.get('FIRECRAWL_ENDPOINT', '')
        key = os.environ.get('FIRECRAWL_API_KEY', '')
        if not endpoint.startswith('https://') or not key:
            raise CollectionError('FIRECRAWL_NOT_CONFIGURED')
        # Task IDs and attempt IDs originate in Store, never in paths from clients.
        for identifier in (task_id, attempt_id):
            if len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier):
                raise CollectionError('INVALID_COLLECTION_ID')
        work = self.storage/task_id/attempt_id
        work.mkdir(parents=True, exist_ok=False)
        env = {k:v for k,v in os.environ.items() if k in ('PATH','SYSTEMROOT','HOME','LANG','TZ')}
        env.update(FIRECRAWL_ENDPOINT=endpoint, FIRECRAWL_API_KEY=key,
                   PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
        max_pages = min(max(int(os.environ.get('HH520_MAX_PAGES','150')),1),500)
        timeout = min(max(int(os.environ.get('HH520_COLLECTION_TIMEOUT','1800')),30),3600)
        supervise([sys.executable,str(VENDOR/'run_pipeline.py'),'--date',target_date,
                   '--skip-source-validation','--max-pages',str(max_pages)],work,env,pulse,timeout)
        latest = json.loads((work/'data/raw'/target_date/'latest.json').read_text(encoding='utf-8'))
        raw = work/latest['snapshot_dir']
        supervise([sys.executable,str(VENDOR/'build_match_packages.py'),'--date',target_date,
                   '--snapshot-dir',str(raw)],work,env,pulse,60)
        package_ref = json.loads((work/'data/matches'/target_date/'latest.json').read_text(encoding='utf-8'))
        index = json.loads((work/package_ref['index']).read_text(encoding='utf-8'))
        discovery = json.loads((raw/'url_discovery.json').read_text(encoding='utf-8'))
        manifest = json.loads((raw/'manifest.json').read_text(encoding='utf-8'))
        hashes = {p.relative_to(work).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in work.rglob('*.json')}
        complete = (index['match_count'] > 0 and index['complete_matches'] == index['match_count']
                    and not discovery['truncated'] and not discovery['failed_pages']
                    and not index.get('unassigned_discoveries'))
        result = {'task_id':task_id,'attempt_id':attempt_id,'date':target_date,
                  'collected_at':datetime.now(timezone.utc).isoformat(),
                  'snapshot_id':manifest['snapshot_id'],'collector':'Firecrawl',
                  'package_version':'identity-v1','match_count':index['match_count'],
                  'complete_matches':index['complete_matches'],
                  'scraped_pages':manifest['scraped_pages'],
                  'failed_pages':discovery['failed_pages'],'truncated':discovery['truncated'],
                  'unassigned_count':len(index.get('unassigned_discoveries',[])),
                  'collection_complete':complete,'is_prediction':False,
                  'prediction_eligible':False,'historical_cutoff_verified':False,
                  'source_validation':'FIRECRAWL_ONLY_NO_DIRECT_FETCH_COMPARISON',
                  'files':hashes}
        content=json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2).encode('utf-8')
        with (work/'receipt.json').open('xb') as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        result['receipt_sha256']=hashlib.sha256(content).hexdigest()
        return result


def collection_report(result):
    state='采集完成' if result['collection_complete'] else '采集完成，但数据存在缺项'
    return (f"# {state}\n\n日期：{result['date']}\n\n"
            f"成功采集 {result['scraped_pages']} 页；失败 {result['failed_pages']} 页。\n\n"
            f"识别 {result['match_count']} 场；资料齐全且身份核对通过 {result['complete_matches']} 场。\n\n"
            f"达到页数上限：{'是' if result['truncated'] else '否'}；未归属资料：{result['unassigned_count']}。\n\n"
            f"快照：{result['snapshot_id']}\n\n归档校验：{result['receipt_sha256']}\n\n"
            "这不是比赛预测。原始页面和逐场数据包已保存；历史 T-30 与赛后字段隔离尚未验证，不能直接交给预测模型。")
