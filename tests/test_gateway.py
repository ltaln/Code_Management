import io
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
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
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'tasks.sqlite3'
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
        self.assertIn('PREDICTION_REQUIRES_FUTURE_FIXTURE_DATE_FOR_T_MINUS_30_SAFETY',row['blockers'])

    def test_external_gpt_handoff_and_immutable_commit(self):
        task=self.create('预测 2099-08-11 所有比赛','future-prediction')
        class FakeCollector:
            def collect(inner,task_id,target_date,pulse,attempt_id):
                base=self.path.parent/'collections'/task_id/attempt_id
                package_dir=Path('data/matches')/target_date/'snapshot_identity_v1'
                (base/package_dir).mkdir(parents=True)
                package={'date':target_date,'match_no':1,'code':'20990811001','xi':'1',
                         'kickoff_at_raw':'2099-08-12 00:30','identity_check':{'result':'PASS'},
                         'package_version':'identity-v1','snapshot_id':'snapshot','complete':True,
                         'sections':[{'category':'mixed_data','url':'https://example.test/1','markdown':'比赛资料 '*100}],
                         'shared_context':[]}
                (base/package_dir/'match_001_20990811001.json').write_text(json.dumps(package,ensure_ascii=False),encoding='utf-8')
                index={'matches':[{'match_no':1,'code':'20990811001','xi':'1','file':'match_001_20990811001.json','complete':True}],
                       'match_count':1,'complete_matches':1}
                index_path=package_dir/'index.json'
                (base/index_path).write_text(json.dumps(index),encoding='utf-8')
                return {'task_id':task_id,'attempt_id':attempt_id,'date':target_date,'snapshot_id':'snapshot',
                        'package_index':index_path.as_posix(),'package_dir':package_dir.as_posix(),
                        'collection_complete':True,'prediction_eligible':True,'scraped_pages':6,'failed_pages':0,
                        'match_count':1,'complete_matches':1,'truncated':False,'unassigned_count':0,
                        'receipt_sha256':'a'*64}
        Worker(self.store,collector=FakeCollector()).once()
        self.assertEqual(self.store.get(task)['status'],'AWAITING_GPT')
        status,index=self.app.route('GET',f'/v1/tasks/{task}/matches',{})
        self.assertEqual(status,200)
        status,match=self.app.route('GET',f'/v1/tasks/{task}/matches/1',{})
        self.assertEqual(match['package_sha256'],hashlib.sha256((self.path.parent/'collections'/task/self.store.get(task)['input_ref']['attempt_id']/'data/matches/2099-08-11/snapshot_identity_v1/match_001_20990811001.json').read_bytes()).hexdigest())
        status,batch=self.app.route('GET',f'/v1/tasks/{task}/analysis-batch',{})
        self.assertEqual(status,200)
        self.assertEqual(len(batch['matches']),1)
        modules=[{'module_id':name,'status':'COMPLETED','summary':'已按冻结流程执行','evidence_refs':['mixed_data']}
                 for name in index['required_module_order']]
        payload={'match_no':1,'code':'20990811001','report_markdown':'## 第1场\n\n'+'完整流程分析。'*20,
                 'modules':modules,'results':{'correct_score_top3':[],'htft_top3':[],
                 'asian_handicap':'PASS','over_under':'PASS','one_x_two':'PASS','total_goals':'PASS','confidence':'低'},
                 'warnings':[]}
        encoded=json.dumps({'predictions':[payload]},ensure_ascii=False).encode('utf-8')
        env={'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(encoded)),'wsgi.input':io.BytesIO(encoded)}
        status,final=self.app.route('POST',f'/v1/tasks/{task}/analysis-batch',env)
        self.assertEqual(status,200)
        self.assertTrue(final['is_prediction'])
        self.assertEqual(self.store.get(task)['status'],'COMPLETED')
        env={'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(encoded)),'wsgi.input':io.BytesIO(encoded)}
        status,retry=self.app.route('POST',f'/v1/tasks/{task}/analysis-batch',env)
        self.assertEqual(retry['prediction_commit'],final['prediction_commit'])

    def test_probe_is_not_prediction(self):
        task=self.create()
        self.worker.once()
        row=self.store.get(task)
        self.assertEqual(row['status'],'COMPLETED')
        self.assertIn('这不是比赛预测',row['report'])

    def test_transient_task_tells_gpt_to_continue(self):
        task=self.create()
        progress=self.app.task_progress(task,wait_seconds=0)
        self.assertTrue(progress['must_continue'])
        self.assertEqual(progress['next_operation'],'getHH520Task')

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

    def test_openapi_schema_is_public_but_tasks_are_private(self):
        statuses=[]
        bodies=self.app({'REQUEST_METHOD':'GET','PATH_INFO':'/openapi.json'},
                        lambda status,headers:statuses.append(status))
        self.assertTrue(statuses[-1].startswith('200'))
        self.assertEqual(json.loads(b''.join(bodies))['info']['version'],'0.4.4')
        self.app({'REQUEST_METHOD':'GET','PATH_INFO':'/v1/tasks/'+'a'*32},
                 lambda status,headers:statuses.append(status))
        self.assertTrue(statuses[-1].startswith('401'))

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
