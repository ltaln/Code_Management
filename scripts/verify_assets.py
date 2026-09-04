"""Read-only asset verification. Does not execute HH520 or rewrite its lock."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PROTECTED = ('models', 'prompts', 'rules', 'calibration', 'workflows', 'docs/sources')
MODEL = 'HH520 V2.1-Test'
MANIFEST = 'models/HH520_V2.1-Test/manifest.json'
REQUIRED = ['README.md', 'PROJECT_MEMORY.md', 'WAKE_CODE.md', 'docs/STATUS.md',
            'docs/GAPS.md', 'docs/DECISIONS.md', 'config/system.json', 'config/model.json',
            'config/task.json', 'versions/asset_lock.json', MANIFEST,
            'task_manager/task.schema.json', 'data_engine/package.schema.json',
            'prediction/record.schema.json', 'prediction/receipt.schema.json',
            'backtest/README.md', 'evaluation/README.md', 'logs/README.md']
PHASES = ['phase_1_assets', 'phase_2_management', 'phase_3_tasks', 'phase_4_data',
          'phase_5_prediction', 'phase_6_backtest']


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root: Path):
    return sorted(p for p in root.rglob('*') if p.is_file() and
                  not any(part in {'.git', '__pycache__', 'runtime'} for part in p.relative_to(root).parts))


def verify(root: Path = ROOT) -> dict:
    root = root.resolve()
    errors = []
    documents = {}
    inventory = files(root)
    for rel in REQUIRED + [f'docs/phases/{p}.md' for p in PHASES]:
        if not (root / rel).is_file():
            errors.append(f'MISSING: {rel}')
    for p in inventory:
        if not p.resolve().is_relative_to(root):
            errors.append(f'OUTSIDE_ROOT: {p}')
            continue
        if p.suffix == '.json':
            try:
                documents[p.relative_to(root).as_posix()] = json.loads(p.read_text(encoding='utf-8'))
            except (ValueError, OSError) as exc:
                errors.append(f'INVALID_JSON: {p.relative_to(root)}: {exc}')

    lock = documents.get('versions/asset_lock.json', {})
    entries = lock.get('files', {}) if isinstance(lock, dict) else {}
    if not isinstance(entries, dict) or not entries:
        errors.append('INVALID_LOCK: no protected files')
        entries = {}
    actual = {p.relative_to(root).as_posix() for p in inventory
              if any(p.relative_to(root).as_posix().startswith(prefix + '/') for prefix in PROTECTED)}
    for rel in sorted(actual - entries.keys()):
        errors.append(f'UNLOCKED_ASSET: {rel}')
    for rel, expected in entries.items():
        p = (root / rel).resolve()
        if not p.is_relative_to(root):
            errors.append(f'UNSAFE_LOCK_PATH: {rel}')
        elif not p.is_file():
            errors.append(f'MISSING_ASSET: {rel}')
        elif digest(p) != expected:
            errors.append(f'ASSET_HASH_MISMATCH: {rel}')

    index = documents.get('docs/sources/index.json', [])
    if not isinstance(index, list):
        errors.append('INVALID_SOURCE_INDEX')
        index = []
    for source in index:
        if not isinstance(source, dict) or not isinstance(source.get('path'), str):
            errors.append('INVALID_SOURCE_ENTRY')
            continue
        p = (root / source['path']).resolve()
        if not p.is_relative_to(root) or not p.is_file() or digest(p) != source.get('sha256'):
            errors.append(f'SOURCE_HASH_MISMATCH: {source.get("id")}')

    # Compare the recovered prompt to the original source, without normalizing text.
    source_path = root / 'docs/sources/model_sop_original.md'
    prompt_path = root / 'prompts/HH520-PROMPT-V2.1.txt'
    try:
        original = source_path.read_text(encoding='utf-8')
        section = original.split('# 十二、Prompt 固定模板', 1)[1].split('# 十三、重要注意事项', 1)[0]
        original_prompt = re.search(r'```\n(.*?)\n```', section, re.S).group(1).encode('utf-8')
        if prompt_path.read_bytes() != original_prompt:
            errors.append('PROMPT_NOT_VERBATIM')
    except (OSError, IndexError, AttributeError):
        errors.append('PROMPT_SOURCE_UNREADABLE')

    manifest = documents.get(MANIFEST, {})
    config = documents.get('config/system.json', {})
    if not isinstance(manifest, dict):
        manifest = {}
    if not isinstance(config, dict):
        config = {}
    if manifest.get('model_id') != MODEL or config.get('model') != MODEL:
        errors.append('MODEL_MISMATCH')
    if manifest.get('core_frozen') is not True:
        errors.append('CORE_NOT_FROZEN')
    if any(x.get('upgrade_package_1') != 'PARKED' for x in (manifest, config)):
        errors.append('UPGRADE_NOT_PARKED')
    if config.get('auto_upgrade') is not False:
        errors.append('AUTO_UPGRADE_ENABLED')
    if config.get('prompt') != manifest.get('prompt_version') or config.get('prompt') != 'HH520-PROMPT-V2.1':
        errors.append('PROMPT_VERSION_MISMATCH')
    blockers = manifest.get('blockers', [])
    if not isinstance(blockers, list):
        errors.append('INVALID_BLOCKER_LIST')
        blockers = ['INVALID_MANIFEST']
    # This release contains no executor. A config toggle cannot turn it into one.
    ready_reasons = sorted(set(blockers + ['RUNTIME_NOT_IMPLEMENTED_IN_ASSET_RELEASE']))
    if manifest.get('runtime_enabled') is not False or config.get('prediction_enabled') is not False or config.get('backtest_enabled') is not False:
        errors.append('RUNTIME_SWITCH_INVALID_FOR_ASSET_RELEASE')

    links_checked = 0
    for p in inventory:
        if p.suffix != '.md' or p.relative_to(root).as_posix().startswith('docs/sources/'):
            continue  # Preserve historical source links as evidence, not live links.
        text = re.sub(r'```.*?```', '', p.read_text(encoding='utf-8'), flags=re.S)
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', text):
            target = target.strip().strip('<>')
            if not target or target.startswith('#') or urlsplit(target).scheme:
                continue
            path = unquote(target.split('#', 1)[0])
            if not (p.parent / path).exists():
                errors.append(f'BROKEN_LINK: {p.relative_to(root)} -> {target}')
            links_checked += 1
    return {'asset_integrity': 'PASS' if not errors else 'FAIL', 'files': len(inventory),
            'locked_files': len(entries), 'sources': len(index), 'local_links_checked': links_checked,
            'model': MODEL, 'core_frozen': manifest.get('core_frozen') is True,
            'runtime_ready': False, 'readiness_blockers': ready_reasons, 'errors': errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--require-ready', action='store_true')
    args = parser.parse_args()
    report = verify(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report['errors']:
        return 1
    return 2 if args.require_ready and not report['runtime_ready'] else 0


if __name__ == '__main__':
    sys.exit(main())
