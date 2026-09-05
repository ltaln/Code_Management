import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'data_engine'/'vendor'))
from match_identity import assemble


def record(url,category,html):
    return {'url':url,'category':category,'fetched_at':'2026-09-05T00:00:00Z',
            'response':{'success':True,'data':{'rawHtml':html,'markdown':'赛前资料'}}}


class IdentityTests(unittest.TestCase):
    def test_authoritative_roster_and_mixed_page_allow_degraded_package(self):
        roster='''<div class="element match finished visible">
          <a href="https://www.hh520.com/xi.php?id=6183" class="match-link"></a>
          <div class="info"><span class="time">周一 : 1 </span></div>
          <div class="team-name">卡利亚里</div><div class="team-name">莱切</div>
        </div>'''
        mixed='<h1>卡利亚里 vs 莱切。</h1><p>2026-09-08 00:30</p>'
        rows=[record('https://www.hh520.com/?date=20260907','match_list',roster),
              record('https://www.hh520.com/xi.php?id=6183','mixed_data',mixed)]
        joined,unassigned=assemble(rows,'2026-09-07')
        self.assertEqual(unassigned,[])
        self.assertEqual(joined[0]['code'],'20260907001')
        self.assertEqual(joined[0]['identity_check']['result'],'PASS')
        self.assertIn('score_odds_changes: missing or ambiguous explicit link',
                      joined[0]['identity_check']['warnings'])

    def test_roster_team_conflict_blocks_identity(self):
        roster='''<div class="element match visible"><a href="/xi.php?id=1"></a>
          <span class="time">周一 : 1</span><div class="team-name">甲</div>
          <div class="team-name">乙</div></div>'''
        rows=[record('https://www.hh520.com/?date=20260907','match_list',roster),
              record('https://www.hh520.com/xi.php?id=1','mixed_data','<h1>甲 vs 丙。</h1>')]
        joined,_=assemble(rows,'2026-09-07')
        self.assertEqual(joined[0]['identity_check']['result'],'FAIL')


if __name__=='__main__':
    unittest.main()
