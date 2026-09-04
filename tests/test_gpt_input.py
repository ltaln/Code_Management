import json
from pathlib import Path
import tempfile
import unittest

from data_engine.gpt_input import compact_match


class GPTInputTests(unittest.TestCase):
    def test_market_history_is_bounded_and_auditable(self):
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
        self.assertIn('快照 #1',content)
        self.assertIn('快照 #5',content)
        self.assertIn('快照 #9',content)
        self.assertRegex(result['package_sha256'],r'^[a-f0-9]{64}$')


if __name__=='__main__': unittest.main()
