"""Persistent command gateway. Analysis stays blocked until frozen inputs are ready."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timezone
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


class RequestError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


def parse_command(command):
    if not isinstance(command, str) or len(command) > 200:
        raise RequestError(400, 'INVALID_COMMAND')
    command = ' '.join(command.strip().split())
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
                    asset_hash TEXT NOT NULL, report TEXT, blockers TEXT NOT NULL DEFAULT '[]');
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                    at REAL NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL);
            ''')

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

    def cancel(self, task_id):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT status FROM tasks WHERE id=?',(task_id,)).fetchone()
            if not row:
                raise RequestError(404,'TASK_NOT_FOUND')
            if row['status'] in ('CREATED','STARTUP_CHECK','COLLECTING'):
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
            if payload['mode'] == 'collection' and not blockers:
                from data_engine.collector import FirecrawlCollector, CollectionError, collection_report
                collector=self.collector or FirecrawlCollector(self.store.path.parent/'collections')
                if not self.store.renew(row['id'],token,'COLLECTING'):
                    return True
                try:
                    result=collector.collect(row['id'],payload['date'],
                        lambda: not self.stop.is_set() and self.store.renew(row['id'],token),token)
                    status='COMPLETED' if result['collection_complete'] else 'PARTIAL'
                    report=collection_report(result)
                    blockers=[] if result['collection_complete'] else ['COLLECTION_INCOMPLETE']
                except CollectionError as exc:
                    status='FAILED'
                    blockers=[str(exc)]
                    report='# 采集未完成\n\n'+str(exc)+'\n\n未生成预测；已保存的原始资料保留在本次任务目录。'
            elif payload['mode'] == 'connection_check' and not blockers:
                status = 'COMPLETED'
                report = '# 连接检查完成\n\n命令已接收、任务已持久保存、后台检查已执行、报告已保存。\n\n这不是比赛预测。真实预测仍受模型资料与服务接入缺口阻塞。'
            else:
                blockers += check['readiness_blockers']
                status = 'BLOCKED'
                report = '# 任务未进入预测\n\n' + '\n'.join('- '+x for x in sorted(set(blockers)))
                report += '\n\n已读取重要注意事项对应资产并校验冻结文件；未采集新数据，未调用模型，未生成比分。'
                if payload.get('date') and payload['date'] < datetime.now(timezone.utc).date().isoformat():
                    report += '\n\n请求涉及过去日期：必须使用当时可用的赛前资料；历史重建遵守 T-30，禁止使用赛后数据。'
            self.store.finish(row['id'],token,status,report,sorted(set(blockers)))
        except Exception:
            # Avoid leaking provider credentials or local paths in future adapter errors.
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
    def __init__(self, store, token, root=ROOT):
        if not isinstance(token,str) or len(token)<32:
            raise ValueError('HH520_GATEWAY_TOKEN must have at least 32 characters')
        self.store, self.token, self.root = store, token, root

    def __call__(self, env, start):
        try:
            supplied = env.get('HTTP_AUTHORIZATION','')
            if not hmac.compare_digest(supplied.encode(),('Bearer '+self.token).encode()):
                raise RequestError(401,'UNAUTHORIZED')
            method, path = env['REQUEST_METHOD'], env.get('PATH_INFO','')
            status, value = self.route(method,path,env)
        except RequestError as exc:
            status,value=exc.code,{'error':exc.message}
        except Exception:
            status,value=500,{'error':'INTERNAL_ERROR'}
        body=json.dumps(value,ensure_ascii=False).encode('utf-8')
        reason={200:'OK',202:'Accepted',400:'Bad Request',401:'Unauthorized',404:'Not Found',409:'Conflict',413:'Payload Too Large',415:'Unsupported Media Type',500:'Internal Server Error'}[status]
        start(f'{status} {reason}',[('Content-Type','application/json; charset=utf-8'),('Content-Length',str(len(body))),('Cache-Control','no-store')])
        return [body]

    @staticmethod
    def body(env):
        if env.get('CONTENT_TYPE','').split(';')[0] != 'application/json':
            raise RequestError(415,'JSON_REQUIRED')
        try:
            n=int(env.get('CONTENT_LENGTH','0'))
        except ValueError:
            raise RequestError(400,'INVALID_CONTENT_LENGTH')
        if not 0<n<=4096:
            raise RequestError(413,'BODY_LIMIT_4096_BYTES')
        try:
            value=json.loads(env['wsgi.input'].read(n))
        except (ValueError,UnicodeError):
            raise RequestError(400,'INVALID_JSON')
        if not isinstance(value,dict):
            raise RequestError(400,'JSON_OBJECT_REQUIRED')
        return value

    def route(self,method,path,env):
        if method=='GET' and path=='/health':
            return 200,{'gateway':'ready','prediction':'blocked','release':'0.3.0',
                       'collection':'configured' if os.environ.get('FIRECRAWL_ENDPOINT') and os.environ.get('FIRECRAWL_API_KEY') else 'not_configured',
                       'delivery':'polling_only_no_chat_push'}
        if method=='POST' and path=='/v1/tasks':
            body=self.body(env)
            if set(body)!={'request_id','command'}:
                raise RequestError(400,'REQUIRED: request_id, command')
            payload=parse_command(body['command'])
            task_id,created=self.store.create(body['request_id'],payload,digest(self.root/'versions/asset_lock.json'))
            return (202 if created else 200),{'task_id':task_id,'status_url':f'/v1/tasks/{task_id}','report_url':f'/v1/tasks/{task_id}/report','created':created}
        match=re.fullmatch(r'/v1/tasks/([a-f0-9]{32})(/report|/cancel)?',path)
        if match:
            task_id,action=match.groups()
            if method=='POST' and action=='/cancel':
                self.store.cancel(task_id)
                return 200,self.store.get(task_id)
            if method=='GET':
                task=self.store.get(task_id)
                if action=='/report':
                    return 200,{'task_id':task_id,'status':task['status'],'report':task['report'],'ready':task['report'] is not None,'is_prediction':False}
                if not action:
                    return 200,task
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
