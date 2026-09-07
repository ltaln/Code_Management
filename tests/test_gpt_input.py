import json
from pathlib import Path
import tempfile
import unittest

from data_engine.gpt_input import compact_match


class GPTInputTests(unittest.TestCase):
    def test_prediction_uses_only_latest_market_snapshot(self):
        snapshots='\n\n'.join(f'📸 快照 #{i}更新时间: 2099-01-01 00:{i:02d}\n'+('盘口资料 '*800)
                              for i in range(1,10))
        package={'date':'2099-01-01','match_no':1,'code':'20990101001','xi':'1',
                 'kickoff_at_raw':'2099-01-02 00:00','identity_check':{'result':'PASS'},
                 'package_version':'identity-v1','snapshot_id':'snapshot','complete':True,
                 'sections':[{'category':'asian_handicap_changes','url':'https://example.test','markdown':snapshots}],
                 'shared_context':[]}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'match.json'
            path.write_text(json.dumps(package,ensure_ascii=False),encoding='utf-8')
            result=compact_match(path)
        content=result['sections'][0]['content']
        self.assertLessEqual(len(content),18000)
        self.assertIn('快照 #9',content)
        self.assertNotIn('快照 #1更新时间',content)
        self.assertNotIn('快照 #5更新时间',content)
        self.assertRegex(result['package_sha256'],r'^[a-f0-9]{64}$')

    def test_replay_omits_explicitly_future_dated_evidence_lines(self):
        lineup = '\n'.join([
            '| 日期 | 比赛 | 评分 |',
            '| 2026-07-01 | 历史比赛 | 7.1 |',
            '| 2026年07月16日 | 当日赛前资料 | 7.0 |',
            '| 2026-08-02 | 未来比赛一 | 8.0 |',
            '| 2026年08月20日 | 未来比赛二 | 8.2 |',
        ])
        package={'date':'2026-07-16','match_no':208,'code':'20260716208','xi':'1',
                 'kickoff_at_raw':'2026-07-17 01:00','identity_check':{'result':'PASS'},
                 'package_version':'identity-v2','snapshot_id':'snapshot','complete':True,
                 'sections':[{'category':'predicted_lineup','url':'https://example.test','markdown':lineup}],
                 'shared_context':[]}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'match.json'
            path.write_text(json.dumps(package,ensure_ascii=False),encoding='utf-8')
            result=compact_match(path,replay=True)
        content=result['sections'][0]['content']
        self.assertIn('2026-07-01',content)
        self.assertIn('2026年07月16日',content)
        self.assertNotIn('2026-08-02',content)
        self.assertNotIn('2026年08月20日',content)
        self.assertEqual(result['result_mask']['future_lines_omitted'],2)


if __name__=='__main__': unittest.main()
