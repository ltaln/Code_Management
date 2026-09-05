"""Persistent command gateway with an external ChatGPT analysis handoff."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import threading
import time
import uuid
from wsgiref.simple_server import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_assets import verify, digest
from data_engine.gpt_input import compact_match, compact_match_batch


class RequestError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


def parse_command(command):
    if not isinstance(command, str) or len(command) > 200:
        raise RequestError(400, 'INVALID_COMMAND')
    command = ' '.join(command.strip().split()).rstrip('。；;')
    if command == '检查连接':
        return {'mode': 'connection_check', 'date': None, 'scope': 'NONE'}
    match = re.fullmatch(r'(预测|回测|采集)\s+(\d{4}-\d{2}-\d{2})\s+(全部比赛|所有比赛)', command)
    if not match:
        raise RequestError(400, 'SUPPORTED: 预测 YYYY-MM-DD 所有比赛 / 回测 YYYY-MM-DD 所有比赛 / 检查连接')
    try:
        date.fromisoformat(match[2])
    except ValueError:
        raise RequestError(400, 'INVALID_DATE')
    return {'mode': {'预测':'prediction','回测':'backtest','采集':'collection'}[match[1]], 'date': match[2], 'scope': 'ALL'}


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
                    payload TEXT NOT NULL, status TEXT NOT NULL,
                    created REAL NOT NULL, updated REAL NOT NULL,
                    lease_until REAL, lease_token TEXT, attempts INTEGER NOT NULL DEFAULT 0,
                    asset_hash TEXT NOT NULL, report TEXT, blockers TEXT NOT NULL DEFAULT '[]',
                    input_ref TEXT, prediction_commit TEXT);
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                    at REAL NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS predictions (
                    task_id TEXT NOT NULL, match_no INTEGER NOT NULL, code TEXT NOT NULL,
                    payload TEXT NOT NULL, content_sha256 TEXT NOT NULL, created REAL NOT NULL,
                    PRIMARY KEY(task_id, match_no));
            ''')
            columns={row['name'] for row in db.execute('PRAGMA table_info(tasks)')}
            if 'input_ref' not in columns:
                db.execute('ALTER TABLE tasks ADD COLUMN input_ref TEXT')
            if 'prediction_commit' not in columns:
                db.execute('ALTER TABLE tasks ADD COLUMN prediction_commit TEXT')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def event(db, task_id, status, detail):
        db.execute('INSERT INTO events(task_id,at,status,detail) VALUES(?,?,?,?)',
                   (task_id, time.time(), status, detail))

    def create(self, request_id, payload, asset_hash):
        if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', request_id):
            raise RequestError(400, 'INVALID_REQUEST_ID')
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT * FROM tasks WHERE request_id=?', (request_id,)).fetchone()
            if existing:
                if existing['payload'] != encoded:
                    raise RequestError(409, 'REQUEST_ID_REUSED_WITH_DIFFERENT_COMMAND')
                return existing['id'], False
            task_id, now = uuid.uuid4().hex, time.time()
            db.execute('INSERT INTO tasks(id,request_id,payload,status,created,updated,asset_hash) VALUES(?,?,?,?,?,?,?)',
                       (task_id, request_id, encoded, 'CREATED', now, now, asset_hash))
            self.event(db, task_id, 'CREATED', '任务已持久保存')
        return task_id, True

    def get(self, task_id):
        with self.db() as db:
            row = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
            if not row:
                raise RequestError(404, 'TASK_NOT_FOUND')
            task = dict(row)
            task['payload'] = json.loads(task['payload'])
            task['blockers'] = json.loads(task['blockers'])
            task['input_ref'] = json.loads(task['input_ref']) if task.get('input_ref') else None
            task['prediction_commit'] = json.loads(task['prediction_commit']) if task.get('prediction_commit') else None
            task['events'] = [dict(x) for x in db.execute('SELECT at,status,detail FROM events WHERE task_id=? ORDER BY seq', (task_id,))]
            for key in ('lease_token', 'lease_until'):
                task.pop(key)
            return task

    def claim(self):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            now = time.time()
            expired = db.execute("SELECT id,attempts FROM tasks WHERE status IN ('STARTUP_CHECK','COLLECTING') AND lease_until<?", (now,)).fetchall()
            for row in expired:
                state = 'FAILED' if row['attempts'] >= 3 else 'CREATED'
                db.execute('UPDATE tasks SET status=?,lease_token=NULL,lease_until=NULL,updated=? WHERE id=?', (state,now,row['id']))
                self.event(db,row['id'],state,'任务中断后恢复，新尝试保留原采集记录' if state=='CREATED' else '任务重试耗尽')
            row = db.execute("SELECT * FROM tasks WHERE status='CREATED' ORDER BY created LIMIT 1").fetchone()
            if not row:
                return None
            token = uuid.uuid4().hex
            db.execute("UPDATE tasks SET status='STARTUP_CHECK',lease_token=?,lease_until=?,attempts=attempts+1,updated=? WHERE id=?", (token,now+60,now,row['id']))
            self.event(db,row['id'],'STARTUP_CHECK','校验冻结资产与运行条件')
            return dict(row), token

    def renew(self, task_id, token, stage=None):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            now=time.time()
            updated=db.execute("UPDATE tasks SET lease_until=?,updated=?,status=COALESCE(?,status) WHERE id=? AND lease_token=? AND status IN ('STARTUP_CHECK','COLLECTING') AND lease_until>=?",
                (now+60,now,stage,task_id,token,now)).rowcount
            if updated and stage:
                self.event(db,task_id,stage,'后台采集正在运行，关闭手机不影响任务')
            return bool(updated)

    def finish(self, task_id, token, status, report, blockers):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            updated = db.execute("UPDATE tasks SET status=?,report=?,blockers=?,updated=?,lease_token=NULL,lease_until=NULL WHERE id=? AND lease_token=? AND status IN ('STARTUP_CHECK','COLLECTING') AND lease_until>=?",
                (status,report,json.dumps(blockers),time.time(),task_id,token,time.time())).rowcount
            if updated:
                self.event(db,task_id,status,'报告已保存；是否为预测以报告类型为准')
            return bool(updated)

    def handoff(self, task_id, token, input_ref, report):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            now=time.time()
            updated=db.execute("UPDATE tasks SET status='AWAITING_GPT',input_ref=?,report=?,blockers='[]',updated=?,lease_token=NULL,lease_until=NULL WHERE id=? AND lease_token=? AND status='COLLECTING' AND lease_until>=?",
                (json.dumps(input_ref,ensure_ascii=False,sort_keys=True),report,now,task_id,token,now)).rowcount
            if updated:
                self.event(db,task_id,'AWAITING_GPT','采集与审计输入已保存，等待 GPT 按冻结流程逐场分析')
            return bool(updated)

    def save_match_prediction(self, task_id, match_no, code, payload):
        encoded=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'))
        content_hash=hashlib.sha256(encoded.encode('utf-8')).hexdigest()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT content_sha256 FROM predictions WHERE task_id=? AND match_no=?',(task_id,match_no)).fetchone()
            if existing:
                if existing['content_sha256'] != content_hash:
                    raise RequestError(409,'MATCH_RESULT_ALREADY_COMMITTED')
                return content_hash,False
            task=db.execute('SELECT status FROM tasks WHERE id=?',(task_id,)).fetchone()
            if not task:
                raise RequestError(404,'TASK_NOT_FOUND')
            if task['status']!='AWAITING_GPT':
                raise RequestError(409,'TASK_NOT_AWAITING_GPT')
            db.execute('INSERT INTO predictions(task_id,match_no,code,payload,content_sha256,created) VALUES(?,?,?,?,?,?)',
                       (task_id,match_no,code,encoded,content_hash,time.time()))
            self.event(db,task_id,'AWAITING_GPT',f'第 {match_no} 场分析已不可变保存')
        return content_hash,True

    def predictions(self, task_id):
        with self.db() as db:
            return [{**dict(row),'payload':json.loads(row['payload'])} for row in db.execute(
                'SELECT match_no,code,payload,content_sha256,created FROM predictions WHERE task_id=? ORDER BY match_no',(task_id,))]

    def complete_prediction(self, task_id, commit, report):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            updated=db.execute("UPDATE tasks SET status='COMPLETED',prediction_commit=?,report=?,blockers='[]',updated=? WHERE id=? AND status='AWAITING_GPT'",
                (json.dumps(commit,ensure_ascii=False,sort_keys=True),report,time.time(),task_id)).rowcount
            if not updated:
                row=db.execute('SELECT status,prediction_commit FROM tasks WHERE id=?',(task_id,)).fetchone()
                if not row:
                    raise RequestError(404,'TASK_NOT_FOUND')
                if row['status']=='COMPLETED' and row['prediction_commit']:
                    return json.loads(row['prediction_commit']),False
                raise RequestError(409,'TASK_NOT_AWAITING_GPT')
            self.event(db,task_id,'COMPLETED','全部逐场分析已提交，Prediction Commit 与报告已保存')
        return commit,True

    def cancel(self, task_id):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT status FROM tasks WHERE id=?',(task_id,)).fetchone()
            if not row:
                raise RequestError(404,'TASK_NOT_FOUND')
            if row['status'] in ('CREATED','STARTUP_CHECK','COLLECTING','AWAITING_GPT'):
                db.execute("UPDATE tasks SET status='CANCELLED',updated=?,lease_token=NULL,lease_until=NULL WHERE id=?",(time.time(),task_id))
                self.event(db,task_id,'CANCELLED','用户取消；不会删除已保存记录')


class Worker:
    def __init__(self, store, root=ROOT, collector=None):
        self.store, self.root = store, root
        self.collector=collector
        self.stop = threading.Event()

    def once(self):
        claimed = self.store.claim()
        if not claimed:
            return False
        row, token = claimed
        payload = json.loads(row['payload'])
        try:
            check = verify(self.root)
            blockers = list(check['errors'])
            if digest(self.root/'versions/asset_lock.json') != row['asset_hash']:
                blockers.append('ASSETS_CHANGED_SINCE_TASK_CREATED')
            today=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
            if payload['mode']=='prediction' and payload['date'] <= today:
                blockers.append('PREDICTION_REQUIRES_FUTURE_FIXTURE_DATE_FOR_T_MINUS_30_SAFETY')
            if payload['mode'] in ('collection','prediction') and not blockers:
                from data_engine.collector import FirecrawlCollector, CollectionError, collection_report
                collector=self.collector or FirecrawlCollector(self.store.path.parent/'collections')
                if not self.store.renew(row['id'],token,'COLLECTING'):
                    return True
                try:
                    result=collector.collect(row['id'],payload['date'],
                        lambda: not self.stop.is_set() and self.store.renew(row['id'],token),token)
                    report=collection_report(result)
                    if payload['mode']=='prediction' and result['collection_complete'] and result['prediction_eligible']:
                        if not self.store.handoff(row['id'],token,result,report):
                            return True
                        return True
                    status='COMPLETED' if result['collection_complete'] else 'PARTIAL'
                    blockers=[] if result['collection_complete'] else ['COLLECTION_INCOMPLETE']
                except CollectionError as exc:
                    status='FAILED'
                    blockers=[str(exc)]
                    report='# 采集未完成\n\n'+str(exc)+'\n\n未生成预测；已保存的原始资料保留在本次任务目录。'
            elif payload['mode'] == 'connection_check' and not blockers:
                status = 'COMPLETED'
                report = '# 连接检查完成\n\n命令已接收、任务已持久保存、后台检查已执行、报告已保存。\n\n这不是比赛预测。真实预测仍受模型资料与服务接入缺口阻塞。'
            else:
                if payload['mode']!='prediction':
                    blockers += check['readiness_blockers']
                status = 'BLOCKED'
                report = '# 任务未进入预测\n\n' + '\n'.join('- '+x for x in sorted(set(blockers)))
                report += '\n\n已读取重要注意事项对应资产并校验冻结文件；未采集新数据，未调用模型，未生成比分。'
                if payload.get('date') and payload['date'] < datetime.now(timezone.utc).date().isoformat():
                    report += '\n\n请求涉及过去日期：必须使用当时可用的赛前资料；历史重建遵守 T-30，禁止使用赛后数据。'
            self.store.finish(row['id'],token,status,report,sorted(set(blockers)))
        except Exception:
            # Avoid leaking provider credentials or local paths in future adapter errors.
            if os.environ.get('HH520_DEBUG_RAISE')=='1':
                raise
            self.store.finish(row['id'],token,'FAILED','# 启动检查失败\n\n请检查服务器日志与资产完整性。',['STARTUP_CHECK_FAILED'])
        return True

    def run(self):
        while not self.stop.is_set():
            try:
                worked = self.once()
            except sqlite3.Error:
                worked = False
            if not worked:
                self.stop.wait(1)


class Application:
    MODULE_IDS=['data_consistency_audit','data_confidence_score','water_market','team_analysis',
                'league_analysis','company_source_analysis','correct_score','soccerstats_htft',
                'odds_abnormal_detection','match_risk_engine','conflict_detection',
                'cross_model_interaction','calibration']

    def __init__(self, store, token, root=ROOT):
        if not isinstance(token,str) or len(token)<32:
            raise ValueError('HH520_GATEWAY_TOKEN must have at least 32 characters')
        self.store, self.token, self.root = store, token, root

    def __call__(self, env, start):
        try:
            method, path = env['REQUEST_METHOD'], env.get('PATH_INFO','')
            if method=='GET' and path=='/openapi.json':
                status,value=200,json.loads((self.root/'integrations/gpt-actions.openapi.json').read_text(encoding='utf-8'))
            else:
                supplied = env.get('HTTP_AUTHORIZATION','')
                if not hmac.compare_digest(supplied.encode(),('Bearer '+self.token).encode()):
                    raise RequestError(401,'UNAUTHORIZED')
                status, value = self.route(method,path,env)
        except RequestError as exc:
            task_match=re.match(r'/v1/tasks/([a-f0-9]{32})',env.get('PATH_INFO',''))
            if task_match:
                try:
                    with self.store.db() as db:
                        self.store.event(db,task_match.group(1),'REJECTED',exc.message)
                except sqlite3.Error:
                    pass
            status,value=exc.code,{'error':exc.message}
        except Exception:
            status,value=500,{'error':'INTERNAL_ERROR'}
        body=json.dumps(value,ensure_ascii=False).encode('utf-8')
        reason={200:'OK',202:'Accepted',400:'Bad Request',401:'Unauthorized',404:'Not Found',409:'Conflict',413:'Payload Too Large',415:'Unsupported Media Type',500:'Internal Server Error'}[status]
        start(f'{status} {reason}',[('Content-Type','application/json; charset=utf-8'),('Content-Length',str(len(body))),('Cache-Control','no-store')])
        return [body]

    @staticmethod
    def body(env, max_bytes=4096):
        if env.get('CONTENT_TYPE','').split(';')[0] != 'application/json':
            raise RequestError(415,'JSON_REQUIRED')
        try:
            n=int(env.get('CONTENT_LENGTH','0'))
        except ValueError:
            raise RequestError(400,'INVALID_CONTENT_LENGTH')
        if not 0<n<=max_bytes:
            raise RequestError(413,f'BODY_LIMIT_{max_bytes}_BYTES')
        stream=env['wsgi.input']
        chunks=[]
        remaining=n
        while remaining:
            chunk=stream.read(remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining-=len(chunk)
        raw=b''.join(chunks)
        if len(raw)!=n:
            raise RequestError(400,'INCOMPLETE_REQUEST_BODY')
        try:
            value=json.loads(raw)
        except json.JSONDecodeError as strict_error:
            try:
                value=json.loads(raw,strict=False)
            except (ValueError,UnicodeError) as relaxed_error:
                print('INVALID_JSON_DIAGNOSTIC '
                      f'declared={n} read={len(raw)} strict_pos={strict_error.pos} '
                      f'relaxed={type(relaxed_error).__name__} tail={raw[-24:].hex()}',
                      file=sys.stderr,flush=True)
                raise RequestError(400,'INVALID_JSON')
        except UnicodeError:
            raise RequestError(400,'INVALID_JSON')
        if not isinstance(value,dict):
            raise RequestError(400,'JSON_OBJECT_REQUIRED')
        return value

    def task_progress(self, task_id, wait_seconds=8):
        """Short-poll transient states within the ChatGPT Actions request timeout."""
        deadline=time.monotonic()+wait_seconds
        task=self.store.get(task_id)
        while task['status'] in ('CREATED','STARTUP_CHECK','COLLECTING') and time.monotonic()<deadline:
            time.sleep(1)
            task=self.store.get(task_id)
        transient=task['status'] in ('CREATED','STARTUP_CHECK','COLLECTING')
        task['must_continue']=transient
        task['next_operation']='getHH520Task' if transient else (
            'listHH520Matches' if task['status']=='AWAITING_GPT' else 'getHH520Report')
        task['instruction']=('Do not reply to the user yet. Call getHH520Task again with this task_id.'
                             if transient else 'Continue with next_operation in this same turn.')
        return task

    def input_index(self, task_id):
        task=self.store.get(task_id)
        ref=task.get('input_ref')
        if not ref:
            raise RequestError(409,'COLLECTION_INPUT_NOT_READY')
        attempt=ref.get('attempt_id','')
        if not re.fullmatch(r'[a-f0-9]{32}',attempt):
            raise RequestError(500,'INVALID_STORED_INPUT_REFERENCE')
        base=(self.store.path.parent/'collections'/task_id/attempt).resolve()
        path=(base/ref.get('package_index','')).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            raise RequestError(500,'COLLECTION_INDEX_MISSING')
        return task,base,json.loads(path.read_text(encoding='utf-8'))

    @staticmethod
    def validate_match_result(body, expected):
        required={'match_no','code','report_markdown','modules','results','warnings'}
        if set(body)!=required:
            raise RequestError(400,'MATCH_RESULT_FIELDS_INVALID')
        if body['match_no']!=expected['match_no'] or body['code']!=expected['code']:
            raise RequestError(409,'MATCH_IDENTITY_MISMATCH')
        if not isinstance(body['report_markdown'],str) or not 80<=len(body['report_markdown'])<=120000:
            raise RequestError(400,'REPORT_MARKDOWN_LENGTH_INVALID')
        module_ids=['data_consistency_audit','data_confidence_score','water_market','team_analysis',
                    'league_analysis','company_source_analysis','correct_score','soccerstats_htft',
                    'odds_abnormal_detection','match_risk_engine','conflict_detection',
                    'cross_model_interaction','calibration']
        modules=body['modules']
        if not isinstance(modules,list) or [x.get('module_id') if isinstance(x,dict) else None for x in modules]!=module_ids:
            raise RequestError(400,'FULL_FROZEN_MODULE_ORDER_REQUIRED')
        for module in modules:
            if module.get('status') not in ('COMPLETED','DEGRADED') or not isinstance(module.get('summary'),str) or not module['summary'].strip():
                raise RequestError(400,'MODULE_EVIDENCE_INVALID')
            if not isinstance(module.get('evidence_refs'),list) or not all(isinstance(x,str) and x for x in module['evidence_refs']):
                raise RequestError(400,'MODULE_EVIDENCE_INVALID')
        if not isinstance(body['results'],dict) or not isinstance(body['warnings'],list):
            raise RequestError(400,'RESULTS_OR_WARNINGS_INVALID')
        for key in ('correct_score_top3','htft_top3','asian_handicap','over_under','one_x_two','total_goals','confidence'):
            if key not in body['results']:
                raise RequestError(400,'RESULTS_MISSING_'+key.upper())

    @classmethod
    def expand_compact_result(cls, body, expected):
        required={'match_no','code','module_trace','evidence_refs','results','warnings','prediction_reason'}
        if set(body)!=required or body.get('match_no')!=expected['match_no'] or body.get('code')!=expected['code']:
            raise RequestError(400,'COMPACT_RESULT_FIELDS_INVALID')
        if not isinstance(body['module_trace'],str):
            raise RequestError(400,'COMPACT_MODULE_TRACE_INVALID')
        trace=[x.strip() for x in body['module_trace'].split('|')]
        parsed=[re.fullmatch(r'(COMPLETED|DEGRADED):(.{1,300})',x) for x in trace]
        if len(trace)!=len(cls.MODULE_IDS) or not all(parsed):
            raise RequestError(400,'COMPACT_MODULE_TRACE_MUST_HAVE_13_ORDERED_SEGMENTS')
        statuses=[x.group(1) for x in parsed]
        summaries=[x.group(2).strip() for x in parsed]
        refs=body['evidence_refs']
        if not isinstance(refs,list) or not refs or not all(isinstance(x,str) and x for x in refs):
            raise RequestError(400,'COMPACT_EVIDENCE_REFS_INVALID')
        if not isinstance(body['warnings'],list) or not all(isinstance(x,str) for x in body['warnings']):
            raise RequestError(400,'COMPACT_WARNINGS_INVALID')
        if not isinstance(body['prediction_reason'],str) or not body['prediction_reason'].strip():
            raise RequestError(400,'COMPACT_REASON_INVALID')
        results=body['results']
        if not isinstance(results,dict):
            raise RequestError(400,'COMPACT_RESULTS_INVALID')
        for key in ('correct_score_top3','htft_top3','asian_handicap','over_under','one_x_two','total_goals','confidence'):
            if not isinstance(results.get(key),str) or not results[key].strip():
                raise RequestError(400,'RESULTS_MISSING_'+key.upper())
        modules=[{'module_id':module_id,'status':statuses[i],'summary':summaries[i],
                  'evidence_refs':refs} for i,module_id in enumerate(cls.MODULE_IDS)]
        lines=[f"## 第 {body['match_no']} 场 · {body['code']}","","### 完整冻结流程"]
        lines += [f"- {m['module_id']} [{m['status']}]：{m['summary']}（证据：{', '.join(m['evidence_refs'])}）"
                  for m in modules]
        lines += ['', '### 预测结果',
                  '- 精准比分 Top3：'+results['correct_score_top3'],
                  '- 半全场 Top3：'+results['htft_top3'],
                  f"- 亚洲盘：{results['asian_handicap']}",f"- 大小球：{results['over_under']}",
                  f"- 胜平负：{results['one_x_two']}",f"- 总进球：{results['total_goals']}",
                  f"- 置信度：{results['confidence']}",f"- Prediction Reason：{body['prediction_reason']}"]
        if body['warnings']:
            lines += ['- 异常与降级：'+'；'.join(body['warnings'])]
        return {'match_no':body['match_no'],'code':body['code'],'report_markdown':'\n'.join(lines),
                'modules':modules,'results':results,'warnings':body['warnings']}

    def finalize_prediction(self, task_id):
        task,_,index=self.input_index(task_id)
        expected=index.get('matches',[])
        records=self.store.predictions(task_id)
        if len(records)!=len(expected):
            missing=sorted({x['match_no'] for x in expected}-{x['match_no'] for x in records})
            raise RequestError(409,'MISSING_MATCH_RESULTS:'+','.join(map(str,missing)))
        content={'task_id':task_id,'date':task['payload']['date'],'model_version':'HH520 V2.1-Test',
                 'prompt_version':'HH520-PROMPT-V2.1','asset_lock_hash':task['asset_hash'],
                 'snapshot_id':task['input_ref']['snapshot_id'],'matches':[x['payload'] for x in records]}
        encoded=json.dumps(content,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
        content_hash=hashlib.sha256(encoded).hexdigest()
        commit_id=f"HH520-{task['payload']['date'].replace('-','')}-{content_hash[:16]}"
        archive=(self.store.path.parent/'predictions'/task['payload']['date']).resolve()
        archive.mkdir(parents=True,exist_ok=True)
        path=archive/(commit_id+'.json')
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest()!=content_hash:
                raise RequestError(409,'PREDICTION_COMMIT_COLLISION')
        else:
            with path.open('xb') as output:
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
        commit={'prediction_commit_id':commit_id,'content_sha256':content_hash,
                'storage':'server-immutable-v1','created_at':datetime.now(timezone.utc).isoformat(),
                'match_count':len(records)}
        header=(f"# HH520 V2.1-Test 完整预测报告\n\n日期：{task['payload']['date']}\n\n"
                f"数据快照：{task['input_ref']['snapshot_id']}\n\nPrediction Commit：{commit_id}\n\n"
                "模型核心保持冻结；Upgrade Package 1：PARKED。\n\n")
        report=header+'\n\n'.join(x['payload']['report_markdown'] for x in records)
        return self.store.complete_prediction(task_id,commit,report)[0],report

    def route(self,method,path,env):
        if method=='GET' and path=='/health':
            readiness=verify(self.root)
            return 200,{'gateway':'ready','prediction':'external_gpt_handoff' if readiness['runtime_ready'] else 'blocked','release':'0.4.16',
                       'collection':'configured' if os.environ.get('FIRECRAWL_ENDPOINT') and os.environ.get('FIRECRAWL_API_KEY') else 'not_configured',
                       'delivery':'polling_only_no_chat_push'}
        if method=='POST' and path=='/v1/tasks':
            body=self.body(env)
            if set(body)!={'request_id','command'}:
                raise RequestError(400,'REQUIRED: request_id, command')
            payload=parse_command(body['command'])
            task_id,created=self.store.create(body['request_id'],payload,digest(self.root/'versions/asset_lock.json'))
            return (202 if created else 200),{'task_id':task_id,'status_url':f'/v1/tasks/{task_id}',
                    'report_url':f'/v1/tasks/{task_id}/report','created':created,
                    'must_continue':True,'next_operation':'getHH520Task',
                    'instruction':'Do not reply to the user yet. Immediately call getHH520Task with this task_id.'}
        match_input=re.fullmatch(r'/v1/tasks/([a-f0-9]{32})/matches(?:/(\d{1,3}))?',path)
        if match_input and method=='GET':
            task_id,number=match_input.groups()
            task,base,index=self.input_index(task_id)
            if number is None:
                saved={x['match_no'] for x in self.store.predictions(task_id)}
                matches=[{**x,'analysis_saved':x['match_no'] in saved} for x in index.get('matches',[])]
                return 200,{'task_id':task_id,'status':task['status'],'snapshot_id':task['input_ref']['snapshot_id'],
                            'match_count':len(matches),'matches':matches,'required_module_order':[
                            'data_consistency_audit','data_confidence_score','water_market','team_analysis','league_analysis',
                            'company_source_analysis','correct_score','soccerstats_htft','odds_abnormal_detection',
                            'match_risk_engine','conflict_detection','cross_model_interaction','calibration']}
            match_no=int(number)
            item=next((x for x in index.get('matches',[]) if x['match_no']==match_no),None)
            if not item:
                raise RequestError(404,'MATCH_NOT_FOUND')
            package=(base/task['input_ref']['package_dir']/item['file']).resolve()
            if not package.is_relative_to(base) or not package.is_file():
                raise RequestError(500,'MATCH_PACKAGE_MISSING')
            return 200,compact_match(package)
        batch_input=re.fullmatch(r'/v1/tasks/([a-f0-9]{32})/analysis-batch',path)
        if batch_input and method=='GET':
            task_id=batch_input.group(1)
            task,base,index=self.input_index(task_id)
            paths=[]
            for item in index.get('matches',[]):
                package=(base/task['input_ref']['package_dir']/item['file']).resolve()
                if not package.is_relative_to(base) or not package.is_file():
                    raise RequestError(500,'MATCH_PACKAGE_MISSING')
                paths.append(package)
            batch=compact_match_batch(paths)
            batch.update(task_id=task_id,status=task['status'],snapshot_id=task['input_ref']['snapshot_id'],
                         required_module_order=['data_consistency_audit','data_confidence_score','water_market',
                         'team_analysis','league_analysis','company_source_analysis','correct_score',
                         'soccerstats_htft','odds_abnormal_detection','match_risk_engine','conflict_detection',
                         'cross_model_interaction','calibration'])
            return 200,batch
        match_submit=re.fullmatch(r'/v1/tasks/([a-f0-9]{32})/matches/(\d{1,3})/prediction',path)
        if match_submit and method=='POST':
            task_id,number=match_submit.groups()
            _,_,index=self.input_index(task_id)
            expected=next((x for x in index.get('matches',[]) if x['match_no']==int(number)),None)
            if not expected:
                raise RequestError(404,'MATCH_NOT_FOUND')
            body=self.body(env,262144)
            if 'match_no' in body and body['match_no']!=int(number):
                raise RequestError(409,'MATCH_IDENTITY_MISMATCH')
            body['match_no']=int(number)
            self.validate_match_result(body,expected)
            content_hash,created=self.store.save_match_prediction(task_id,int(number),expected['code'],body)
            return (202 if created else 200),{'task_id':task_id,'match_no':int(number),'saved':True,
                                               'created':created,'content_sha256':content_hash}
        compact_match_submit=re.fullmatch(r'/v1/tasks/([a-f0-9]{32})/matches/(\d{1,3})/prediction-compact',path)
        if compact_match_submit and method=='POST':
            task_id,number=compact_match_submit.groups()
            _,_,index=self.input_index(task_id)
            expected=next((x for x in index.get('matches',[]) if x['match_no']==int(number)),None)
            if not expected:
                raise RequestError(404,'MATCH_NOT_FOUND')
            body=self.body(env,65536)
            if 'match_no' in body and body['match_no']!=int(number):
                raise RequestError(409,'MATCH_IDENTITY_MISMATCH')
            body['match_no']=int(number)
            result=self.expand_compact_result(body,expected)
            self.validate_match_result(result,expected)
            content_hash,created=self.store.save_match_prediction(
                task_id,int(number),expected['code'],result)
            return (202 if created else 200),{'task_id':task_id,'match_no':int(number),'saved':True,
                                               'created':created,'content_sha256':content_hash}
        batch_submit=re.fullmatch(r'/v1/tasks/([a-f0-9]{32})/analysis-batch',path)
        if batch_submit and method=='POST':
            task_id=batch_submit.group(1)
            _,_,index=self.input_index(task_id)
            body=self.body(env,524288)
            if set(body)!={'predictions'} or not isinstance(body['predictions'],list):
                raise RequestError(400,'REQUIRED: predictions')
            expected=index.get('matches',[])
            supplied={x.get('match_no'):x for x in body['predictions'] if isinstance(x,dict)}
            if len(supplied)!=len(body['predictions']) or set(supplied)!={x['match_no'] for x in expected}:
                raise RequestError(400,'BATCH_MUST_CONTAIN_EVERY_MATCH_ONCE')
            for item in expected:
                self.validate_match_result(supplied[item['match_no']],item)
            hashes=[]
            for item in expected:
                content_hash,created=self.store.save_match_prediction(
                    task_id,item['match_no'],item['code'],supplied[item['match_no']])
                hashes.append({'match_no':item['match_no'],'content_sha256':content_hash,'created':created})
            commit,report=self.finalize_prediction(task_id)
            return 200,{'task_id':task_id,'status':'COMPLETED','is_prediction':True,
                        'saved_matches':hashes,'prediction_commit':commit,'report':report}
        compact_submit=re.fullmatch(r'/v1/tasks/([a-f0-9]{32})/analysis-compact',path)
        if compact_submit and method=='POST':
            task_id=compact_submit.group(1)
            task,_,index=self.input_index(task_id)
            body=self.body(env,524288)
            if (set(body)!={'predictions'} or not isinstance(body['predictions'],list)
                    or not 1<=len(body['predictions'])<=999):
                raise RequestError(400,'REQUIRED: predictions for every remaining match')
            expected=index.get('matches',[])
            expected_by_number={x['match_no']:x for x in expected}
            supplied={x.get('match_no'):x for x in body['predictions'] if isinstance(x,dict)}
            saved={x['match_no'] for x in self.store.predictions(task_id)}
            required=set(expected_by_number) if task['status']=='COMPLETED' else set(expected_by_number)-saved
            if len(supplied)!=len(body['predictions']) or set(supplied)!=required:
                raise RequestError(400,'COMPACT_BATCH_MUST_CONTAIN_EVERY_REMAINING_MATCH_ONCE')
            expanded=[]
            chunk=[expected_by_number[number] for number in sorted(supplied)]
            for item in chunk:
                result=self.expand_compact_result(supplied[item['match_no']],item)
                self.validate_match_result(result,item)
                expanded.append(result)
            hashes=[]
            for item,result in zip(chunk,expanded):
                content_hash,created=self.store.save_match_prediction(
                    task_id,item['match_no'],item['code'],result)
                hashes.append({'match_no':item['match_no'],'content_sha256':content_hash,'created':created})
            commit,_=self.finalize_prediction(task_id)
            return 200,{'task_id':task_id,'status':'COMPLETED','is_prediction':True,
                        'saved_matches':hashes,'prediction_commit':commit,
                        'report_url':f'/v1/tasks/{task_id}/report'}
        finalize=re.fullmatch(r'/v1/tasks/([a-f0-9]{32})/finalize',path)
        if finalize and method=='POST':
            commit,report=self.finalize_prediction(finalize.group(1))
            return 200,{'task_id':finalize.group(1),'status':'COMPLETED','is_prediction':True,
                        'prediction_commit':commit,'report':report}
        compact_finalize=re.fullmatch(r'/v1/tasks/([a-f0-9]{32})/finalize-compact',path)
        if compact_finalize and method=='POST':
            task_id=compact_finalize.group(1)
            commit,_=self.finalize_prediction(task_id)
            return 200,{'task_id':task_id,'status':'COMPLETED','is_prediction':True,
                        'prediction_commit':commit,'report_url':f'/v1/tasks/{task_id}/report'}
        match=re.fullmatch(r'/v1/tasks/([a-f0-9]{32})(/report|/cancel)?',path)
        if match:
            task_id,action=match.groups()
            if method=='POST' and action=='/cancel':
                self.store.cancel(task_id)
                return 200,self.store.get(task_id)
            if method=='GET':
                task=self.store.get(task_id)
                if action=='/report':
                    is_prediction=task['status']=='COMPLETED' and task.get('prediction_commit') is not None
                    return 200,{'task_id':task_id,'status':task['status'],'report':task['report'],
                                'ready':task['report'] is not None,'is_prediction':is_prediction,
                                'prediction_commit':task.get('prediction_commit')}
                if not action:
                    return 200,self.task_progress(task_id)
        raise RequestError(404,'NOT_FOUND')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--db',type=Path,default=ROOT/'runtime/tasks.sqlite3')
    args=parser.parse_args()
    store=Store(args.db)
    app=Application(store,os.environ.get('HH520_GATEWAY_TOKEN',''))
    worker=Worker(store)
    thread=threading.Thread(target=worker.run,daemon=True)
    thread.start()
    # Loopback smoke-test server only. Production WSGI deployment is documented.
    with make_server('127.0.0.1',args.port,app) as server:
        print(f'HH520 command gateway: 127.0.0.1:{args.port}; predictions disabled',flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            worker.stop.set()
            thread.join(timeout=5)


if __name__=='__main__':
    main()
