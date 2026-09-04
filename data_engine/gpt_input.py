"""Create a bounded, auditable view of one collected match for ChatGPT Actions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


MAX_SECTION_CHARS = {
    'mixed_data': 8_000,
    'asian_handicap_changes': 18_000,
    'score_odds_changes': 8_000,
    'predicted_lineup': 14_000,
    'historical_lineup_ratings': 8_000,
    'match_list': 7_000,
    'internal_model_analysis': 10_000,
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
    """Keep latest, middle and earliest market snapshots instead of every duplicate."""
    text = _clean(text)
    markers = list(re.finditer(r'(?m)^📸 快照 #\d+更新时间:', text))
    if len(markers) <= 3:
        return _bounded(text, limit)
    header = text[:markers[0].start()]
    chunks = []
    for i, marker in enumerate(markers):
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        chunks.append(text[marker.start():end])
    selected = [chunks[0], chunks[len(chunks) // 2], chunks[-1]]
    per = max((limit - len(header) - 160) // 3, 1_000)
    selected = [_bounded(chunk, per)[0] for chunk in selected]
    compact = header + '\n\n[盘口时间序列共 %d 份；保留最新、中间、最早快照]\n\n' % len(chunks)
    compact += '\n\n'.join(selected)
    return compact[:limit], True


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
        'compression_policy': 'latest_middle_earliest_market_snapshots_v1',
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

