"""Strict final offline Docker gate. Never count skipped or mock execution as isolation."""

import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='webguard-release-gate-') as directory:
        receipt = Path(directory) / 'results.xml'
        result = subprocess.run([sys.executable, '-m', 'pytest', '-m', 'isolation', '-q', '-r', 's',
                                 f'--junitxml={receipt}'], cwd=ROOT, shell=False, check=False)
        cases = list(ET.parse(receipt).iter('testcase')) if receipt.is_file() and receipt.stat().st_size <= 2097152 else []
        skipped = sum(item.find('skipped') is not None for item in cases)
        failures = sum(item.find('failure') is not None or item.find('error') is not None for item in cases)
        status = 'failed' if result.returncode or failures else ('blocked' if skipped or len(cases) != 24 else 'passed')
        summary = {'offline_docker_acceptance': status, 'tests': len(cases), 'skipped': skipped,
                   'failures': failures, 'gemini': 'offline_fake', 'github': 'simulated', 'live_tested': False}
        (ROOT / 'docs/baseline/phase12-docker-gate.json').write_text(json.dumps(summary, indent=2), encoding='utf8')
        print(json.dumps(summary, sort_keys=True))
        return {'passed': 0, 'blocked': 2, 'failed': 1}[status]


if __name__ == '__main__':
    raise SystemExit(main())
