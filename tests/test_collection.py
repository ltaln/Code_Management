import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from task_manager.service import Store, Worker, parse_command, digest
from data_engine.collector import CollectionError, FirecrawlCollector, supervise, check_vendor


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)
        self.store=Store(self.path/'tasks.sqlite3')
        self.task=self.store.create('collection-test',parse_command('采集 2026-09-04 所有比赛'),digest(ROOT/'versions/asset_lock.json'))[0]

    def test_long_task_lease_and_cancel(self):
        _,token=self.store.claim()
        self.assertTrue(self.store.renew(self.task,token,'COLLECTING'))
        self.assertEqual(self.store.get(self.task)['status'],'COLLECTING')
        self.store.cancel(self.task)
        self.assertFalse(self.store.renew(self.task,token))
        self.assertFalse(self.store.finish(self.task,token,'COMPLETED','late',[]))

    def test_restart_preserves_attempt_and_fences_old_collector(self):
        _,old=self.store.claim()
        self.store.renew(self.task,old,'COLLECTING')
        with self.store.db() as db:
            db.execute('UPDATE tasks SET lease_until=0 WHERE id=?',(self.task,))
        _,new=Store(self.path/'tasks.sqlite3').claim()
        self.assertNotEqual(old,new)
        self.assertFalse(self.store.renew(self.task,old))
        self.assertTrue(self.store.renew(self.task,new))

    def test_missing_secret_never_starts_network(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(CollectionError,'FIRECRAWL_NOT_CONFIGURED'):
                FirecrawlCollector(self.path).collect(self.task,'2026-09-04',lambda:True,'f'*32)

    def test_cancel_stops_real_child(self):
        with self.assertRaisesRegex(CollectionError,'TASK_CANCELLED_OR_LEASE_LOST'):
            supervise([sys.executable,'-c','import time; time.sleep(20)'],self.path,dict(os.environ),lambda:False,30)

    def test_partial_collection_not_reported_as_prediction(self):
        class FakeCollector:
            def collect(inner,*args):
                return {'collection_complete':False,'date':'2026-09-04','scraped_pages':2,
                        'failed_pages':1,'match_count':3,'complete_matches':1,'truncated':True,
                        'unassigned_count':1,'snapshot_id':'fixture','receipt_sha256':'a'*64}
        Worker(self.store,collector=FakeCollector()).once()
        row=self.store.get(self.task)
        self.assertEqual(row['status'],'PARTIAL')
        self.assertIn('COLLECTION_INCOMPLETE',row['blockers'])
        self.assertIn('这不是比赛预测',row['report'])

    def test_vendor_integrity(self):
        check_vendor()


if __name__=='__main__': unittest.main()
