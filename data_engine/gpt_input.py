"""Create a bounded, auditable view of one collected match for ChatGPT Actions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


MAX_SECTION_CHARS = {
    'mixed_data': 1_200,
    'asian_handicap_changes': 1_800,
    'score_odds_changes': 1_000,
    'predicted_lineup': 1_600,
    'historical_lineup_ratings': 900,
    'match_list': 900,
    'internal_model_analysis': 1_400,
}
OMIT_SHARED = {'daily_asian_handicap_summary'}


def _clean(text: str) -> str:
    text = re.sub(r'!\[[^\]]*\]\(<Base64-Image-Removed>\)', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _bounded(text: str, limit: int) -> tuple[str, bool]:
    text = _clean(text)
    if len(text) <= limit:
        return text, False
    half = (limit - 80) // 2
    return text[:half] + '\n\n[中间重复内容已压缩；完整原文保存在服务器并由 Hash 校验]\n\n' + text[-half:], True


def _market_snapshots(text: str, limit: int) -> tuple[str, bool]:
    """Expose only the most recent market snapshot to prediction analysis."""
    text = _clean(text)
    markers = list(re.finditer(r'(?m)^📸 快照 #\d+更新时间:', text))
    if not markers:
        return _bounded(text, limit)
    header = text[:markers[0].start()]
    latest=text[markers[-1].start():]
    compact=header+'\n\n[盘口时间序列共 %d 份；预测仅使用最近一次快照]\n\n' % len(markers)
    compact+=latest
    bounded,truncated=_bounded(compact,limit)
    return bounded,truncated or len(markers)>1


def compact_match(path: Path) -> dict:
    raw = path.read_bytes()
    package = json.loads(raw)
    output = {
        'date': package['date'],
        'match_no': package['match_no'],
        'code': package['code'],
        'xi': package.get('xi'),
        'kickoff_at_raw': package.get('kickoff_at_raw'),
        'identity_check': package['identity_check'],
        'snapshot_id': package['snapshot_id'],
        'package_version': package['package_version'],
        'complete': package['complete'],
        'package_sha256': hashlib.sha256(raw).hexdigest(),
        'compression_policy': 'latest_market_snapshot_only_v2',
        'sections': [],
    }
    entries = list(package.get('sections', [])) + list(package.get('shared_context', []))
    for entry in entries:
        category = entry.get('category')
        if category in OMIT_SHARED or category not in MAX_SECTION_CHARS:
            continue
        text = entry.get('markdown', '')
        if category == 'asian_handicap_changes':
            content, truncated = _market_snapshots(text, MAX_SECTION_CHARS[category])
        else:
            content, truncated = _bounded(text, MAX_SECTION_CHARS[category])
        output['sections'].append({
            'category': category,
            'source_url': entry.get('url'),
            'source_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'content': content,
            'compressed': truncated,
        })
    return output


def compact_match_batch(paths: list[Path]) -> dict:
    """Return all match-specific evidence once and de-duplicate shared context."""
    matches=[]
    shared=[]
    shared_seen=set()
    for position,path in enumerate(paths):
        raw=path.read_bytes()
        package=json.loads(raw)
        item={
            'date':package['date'],'match_no':package['match_no'],'code':package['code'],
            'xi':package.get('xi'),'kickoff_at_raw':package.get('kickoff_at_raw'),
            'identity_check':package['identity_check'],'snapshot_id':package['snapshot_id'],
            'package_version':package['package_version'],'complete':package['complete'],
            'package_sha256':hashlib.sha256(raw).hexdigest(),'sections':[],
        }
        for entry in package.get('sections',[]):
            category=entry.get('category')
            if category not in MAX_SECTION_CHARS:
                continue
            if category=='asian_handicap_changes':
                content,truncated=_market_snapshots(entry.get('markdown',''),min(MAX_SECTION_CHARS[category],6000))
            else:
                content,truncated=_bounded(entry.get('markdown',''),min(MAX_SECTION_CHARS[category],6000))
            item['sections'].append({'category':category,'source_url':entry.get('url'),
                                     'content':content,'compressed':truncated})
        matches.append(item)
        if position==0:
            for entry in package.get('shared_context',[]):
                category=entry.get('category')
                if category in OMIT_SHARED or category not in MAX_SECTION_CHARS or category in shared_seen:
                    continue
                shared_seen.add(category)
                content,truncated=_bounded(entry.get('markdown',''),MAX_SECTION_CHARS[category])
                shared.append({'category':category,'source_url':entry.get('url'),
                               'content':content,'compressed':truncated})
    return {'compression_policy':'latest_market_snapshot_per_match_6000_shared_once_v2','matches':matches,
            'shared_context':shared}


def compact_match_page(paths: list[Path], cursor: int, page_size: int = 2) -> dict:
    """Return at most two bounded matches so large fixture dates stay under Actions limits."""
    total=len(paths)
    if cursor < 0 or cursor >= total:
        raise ValueError('INVALID_ANALYSIS_CURSOR')
    end=min(cursor+page_size,total)
    return {'compression_policy':'two_match_pages_latest_snapshot_v1',
            'cursor':cursor,'next_cursor':end if end<total else None,
            'has_more':end<total,'total_matches':total,
            'matches':[compact_match(path) for path in paths[cursor:end]]}
