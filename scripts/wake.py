"""Verify the project and display a takeover summary. Never runs predictions."""
import json
import sys
from verify_assets import ROOT, verify


def main():
    report = verify()
    if report['errors']:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    print('HH520-FOOTBALL-AI-V2026')
    print('模型：HH520 V2.1-Test；核心冻结；Upgrade Package 1 = PARKED')
    print('资产校验：PASS；自动预测：未启用')
    print('读取顺序：README.md → PROJECT_MEMORY.md → docs/STATUS.md → docs/GAPS.md → docs/DECISIONS.md')
    print('阻塞：' + ', '.join(report['readiness_blockers']))
    print('完整接管文本见：' + str(ROOT / 'WAKE_CODE.md'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
