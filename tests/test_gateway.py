import io
import json
from pathlib import Path
import sqlite3
import sys
import threading
import unittest
import urllib.request
import uuid
from wsgiref.simple_server import make_server

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'task_manager'))
from service import Store, Worker, Application, RequestError, parse_command, digest


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.path=ROOT/'runtime'/'gateway_tests'/uuid.uuid4().hex/'tasks.sqlite3'
        self.store=Store(self.path)
        self.worker=Worker(self.store)
        self.app=Application(self.store,'test-token-'+'x'*40)
        self.hash=digest(ROOT/'versions/asset_lock.json')

    def create(self,command='检查连接',request_id='request-001'):
        return self.store.create(request_id,parse_command(command),self.hash)[0]

    def test_command_dates(self):
        self.assertEqual(parse_command('预测 2026-08-11 所有比赛')['mode'],'prediction')
        for command in ['预测 2026-99-99 所有比赛','预测 今天 全部比赛','rm -rf /']:
            with self.assertRaises(RequestError): parse_command(command)

    def test_duplicate_and_conflict(self):
        one=self.create()
        self.assertEqual(one,self.create())
        with self.assertRaises(RequestError) as err:
            self.create('预测 2026-08-11 所有比赛')
        self.assertEqual(err.exception.code,409)

    def test_persistence_and_blocked_prediction(self):
        task=self.create('预测 2026-08-11 所有比赛')
        reopened=Store(self.path)
        Worker(reopened).once()
        row=reopened.get(task)
        self.assertEqual(row['status'],'BLOCKED')
        self.assertIn('未生成比分',row['report'])
        self.assertIn('FLOW_ORDER_CONFLICT',row['blockers'])

    def test_probe_is_not_prediction(self):
        task=self.create()
        self.worker.once()
        row=self.store.get(task)
        self.assertEqual(row['status'],'COMPLETED')
        self.assertIn('这不是比赛预测',row['report'])

    def test_expired_lease_fences_stale_worker(self):
        task=self.create()
        old,old_token=self.store.claim()
        with self.store.db() as db:
            db.execute('UPDATE tasks SET lease_until=0 WHERE id=?',(task,))
        new,new_token=self.store.claim()
        self.assertNotEqual(old_token,new_token)
        self.assertFalse(self.store.finish(task,old_token,'COMPLETED','stale',[]))
        self.assertTrue(self.store.finish(task,new_token,'COMPLETED','current',[]))

    def test_cancel_cannot_be_overwritten(self):
        task=self.create()
        _,token=self.store.claim()
        self.store.cancel(task)
        self.assertFalse(self.store.finish(task,token,'COMPLETED','wrong',[]))
        self.assertEqual(self.store.get(task)['status'],'CANCELLED')

    def test_auth_and_input(self):
        statuses=[]
        env={'REQUEST_METHOD':'GET','PATH_INFO':'/health'}
        self.app(env,lambda status,headers:statuses.append(status))
        self.assertTrue(statuses[0].startswith('401'))
        env.update({'REQUEST_METHOD':'POST','PATH_INFO':'/v1/tasks','HTTP_AUTHORIZATION':'Bearer '+self.app.token,'CONTENT_TYPE':'application/json','CONTENT_LENGTH':'5','wsgi.input':io.BytesIO(b'hello')})
        self.app(env,lambda status,headers:statuses.append(status))
        self.assertTrue(statuses[-1].startswith('400'))

    def test_real_http_roundtrip(self):
        with make_server('127.0.0.1',0,self.app) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            base=f'http://127.0.0.1:{server.server_port}'
            headers={'Authorization':'Bearer '+self.app.token,'Content-Type':'application/json'}
            try:
                request=urllib.request.Request(base+'/v1/tasks',data=json.dumps({'request_id':'http-request','command':'检查连接'}).encode(),headers=headers)
                with urllib.request.urlopen(request,timeout=5) as response:
                    self.assertEqual(response.status,202)
                    result=json.load(response)
                self.worker.once()
                with urllib.request.urlopen(urllib.request.Request(base+result['report_url'],headers=headers),timeout=5) as response:
                    report=json.load(response)
                self.assertTrue(report['ready'])
                self.assertFalse(report['is_prediction'])
            finally:
                server.shutdown()
                thread.join(timeout=5)


if __name__=='__main__': unittest.main()
