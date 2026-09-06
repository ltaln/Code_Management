"""Create a bounded, auditable view of one collected match for ChatGPT Actions."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
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
REPLAY_OMIT = {'internal_model_analysis'}


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


def _parse_time(value: str) -> datetime | None:
    found = re.search(r'(20\d{2}-\d{2}-\d{2})\s+(\d{2}:\d{2})(?::(\d{2}))?', value or '')
    if not found:
        return None
    return datetime.fromisoformat(f"{found.group(1)} {found.group(2)}:{found.group(3) or '00'}")


def _replay_market_snapshot(text: str, limit: int, kickoff: str) -> tuple[str, bool]:
    """Use the newest snapshot strictly before kickoff, never a post-match snapshot."""
    text = _clean(text)
    cutoff = _parse_time(kickoff)
    markers = list(re.finditer(r'(?m)^📸 快照 #\d+更新时间:\s*([^\n]+)', text))
    if not cutoff or not markers:
        return '[历史重放：未找到可验证的赛前盘口快照；该模块降级，不得用赛后数据补齐]', True
    candidates = []
    for index, marker in enumerate(markers):
        observed = _parse_time(marker.group(1))
        if observed and observed < cutoff:
            end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
            candidates.append((observed, text[marker.start():end]))
    if not candidates:
        return '[历史重放：开赛前没有可验证盘口快照；该模块降级]', True
    observed, block = max(candidates, key=lambda item: item[0])
    content = f'[历史重放仅使用开赛前最后快照：{observed.isoformat(sep=" ")}；其余快照已屏蔽]\n\n{block}'
    bounded, truncated = _bounded(content, limit)
    return bounded, truncated or len(candidates) != len(markers)


def _replay_score_odds(text: str, kickoff: str, limit: int) -> tuple[str, bool]:
    """Remove score-odds columns timestamped at or after kickoff."""
    cutoff = _parse_time(kickoff)
    lines = _clean(text).splitlines()
    if not cutoff:
        return '[历史重放：无法验证比分赔率时间，模块降级]', True
    header_index = next((i for i, line in enumerate(lines) if re.match(r'^\|\s*比分\s*\|', line)), None)
    if header_index is None:
        return '[历史重放：未找到可验证的赛前比分赔率版本，模块降级]', True
    cells = [cell.strip() for cell in lines[header_index].strip().strip('|').split('|')]
    keep = [0]
    for index, cell in enumerate(cells[1:], 1):
        observed = _parse_time(cell)
        if observed and observed < cutoff:
            keep.append(index)
    if len(keep) == 1:
        return '[历史重放：开赛前没有可验证的比分赔率版本，模块降级]', True
    output = lines[:header_index]
    for line in lines[header_index:]:
        if not line.lstrip().startswith('|'):
            output.append(line)
            continue
        row = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if len(row) >= len(cells):
            output.append('| ' + ' | '.join(row[index] for index in keep) + ' |')
        else:
            output.append(line)
    output.insert(header_index, '[历史重放：已删除开赛时及赛后的赔率版本列]')
    content = '\n'.join(output)
    if len(content) > limit:
        content = content[:limit - 55].rsplit('\n', 1)[0] + '\n[其余赛前比分赔率行已压缩]'
        return content, True
    return content, len(keep) != len(cells)


def _mask_replay_result(text: str, category: str, target_date: str, kickoff: str = '') -> tuple[str, int]:
    """Mask only target-date outcomes; earlier form/history remains valid evidence."""
    masked = 0
    output = []
    target_dates = {target_date}
    parsed_kickoff = _parse_time(kickoff)
    if parsed_kickoff:
        target_dates.add(parsed_kickoff.date().isoformat())
    date_values = target_dates | {value.replace('-', '年', 1).replace('-', '月', 1) + '日' for value in target_dates}
    score = re.compile(r'(?<![\d-])\d{1,2}\s*[:：-]\s*\d{1,2}(?![-\d])')
    result_words = re.compile(r'完场|比赛结果|比赛以\s*\d{1,2}\s*[:：-]\s*\d{1,2}\s*的比分结束|最终比分|赛果')
    for line in text.splitlines():
        target_line = any(value in line for value in date_values)
        has_result_word = bool(result_words.search(line))
        score_only = bool(re.fullmatch(r'\s*\d{1,2}\s*[:：-]\s*\d{1,2}\s*', line))
        if has_result_word or (target_line and ('比分' in line or '结果' in line)) or score_only:
            line, count1 = result_words.subn('[目标比赛赛果已屏蔽]', line)
            count2 = 0
            if score_only or '比分' in line or '结果' in line or (category == 'match_list' and has_result_word):
                line, count2 = score.subn('[目标比赛比分已屏蔽]', line)
            masked += count1 + count2
        output.append(line)
    return _clean('\n'.join(output)), masked


def compact_match(path: Path, replay: bool = False) -> dict:
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
        'replay_mode': replay,
        'result_mask': {'applied': replay, 'masked_values': 0, 'future_sections_omitted': []},
        'sections': [],
    }
    entries = list(package.get('sections', [])) + list(package.get('shared_context', []))
    for entry in entries:
        category = entry.get('category')
        if category in OMIT_SHARED or category not in MAX_SECTION_CHARS:
            continue
        if replay and category in REPLAY_OMIT:
            output['result_mask']['future_sections_omitted'].append(category)
            continue
        text = entry.get('markdown', '')
        if replay and category == 'asian_handicap_changes':
            content, truncated = _replay_market_snapshot(text, MAX_SECTION_CHARS[category], package.get('kickoff_at_raw', ''))
        elif replay and category == 'score_odds_changes':
            content, truncated = _replay_score_odds(text, package.get('kickoff_at_raw', ''), MAX_SECTION_CHARS[category])
        elif category == 'asian_handicap_changes':
            content, truncated = _market_snapshots(text, MAX_SECTION_CHARS[category])
        else:
            content, truncated = _bounded(text, MAX_SECTION_CHARS[category])
        if replay and category != 'score_odds_changes':
            content, masked = _mask_replay_result(content, category, package['date'], package.get('kickoff_at_raw', ''))
            output['result_mask']['masked_values'] += masked
        output['sections'].append({
            'category': category,
            'source_url': entry.get('url'),
            'source_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'content': content,
            'compressed': truncated,
        })
    return output


def compact_match_batch(paths: list[Path], replay: bool = False) -> dict:
    """Return all match-specific evidence once and de-duplicate shared context."""
    matches=[]
    shared=[]
    shared_seen=set()
    for position,path in enumerate(paths):
        package=json.loads(path.read_bytes())
        item=compact_match(path,replay=replay)
        matches.append(item)
        if position==0:
            for entry in package.get('shared_context',[]):
                category=entry.get('category')
                if category in OMIT_SHARED or category not in MAX_SECTION_CHARS or category in shared_seen or (replay and category in REPLAY_OMIT):
                    continue
                shared_seen.add(category)
                content,truncated=_bounded(entry.get('markdown',''),MAX_SECTION_CHARS[category])
                if replay:
                    content,_=_mask_replay_result(content,category,package['date'],package.get('kickoff_at_raw',''))
                shared.append({'category':category,'source_url':entry.get('url'),
                               'content':content,'compressed':truncated})
    return {'compression_policy':'replay_prematch_only_v1' if replay else 'latest_market_snapshot_per_match_6000_shared_once_v2','replay_mode':replay,'matches':matches,
            'shared_context':shared}


def compact_match_page(paths: list[Path], cursor: int, page_size: int = 2, replay: bool = False) -> dict:
    """Return at most two bounded matches so large fixture dates stay under Actions limits."""
    total=len(paths)
    if cursor < 0 or cursor >= total:
        raise ValueError('INVALID_ANALYSIS_CURSOR')
    end=min(cursor+page_size,total)
    return {'compression_policy':'two_match_pages_latest_snapshot_v1',
            'cursor':cursor,'next_cursor':end if end<total else None,
            'has_more':end<total,'total_matches':total,
            'replay_mode':replay,
            'matches':[compact_match(path,replay=replay) for path in paths[cursor:end]]}
