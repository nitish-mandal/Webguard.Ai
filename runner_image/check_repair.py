"""Real reproduction -> offline proposal gate; skipped Docker is a blocker, not a pass."""

import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='webguard-repair-gate-') as directory:
        report = Path(directory) / 'result.xml'
        process = subprocess.run([sys.executable, '-m', 'pytest', 'worker/tests/test_repair_docker.py',
                                  '-q', '-r', 's', f'--junitxml={report}'], cwd=ROOT, shell=False, check=False)
        if not report.is_file() or report.stat().st_size > 2097152:
            status, cases, skipped, failures = 'failed', [], 0, 1
        else:
            cases = list(ET.parse(report).iter('testcase'))
            skipped = sum(item.find('skipped') is not None for item in cases)
            failures = sum(item.find('failure') is not None or item.find('error') is not None for item in cases)
            status = 'failed' if process.returncode or failures else ('blocked' if skipped or len(cases) != 1 else 'passed')
        print(json.dumps({'repair_acceptance': status, 'tests': len(cases), 'skipped': skipped,
                          'failures': failures, 'provider': 'offline', 'live_verified': False,
                          'phase8_verification': 'not_run'}, sort_keys=True))
        return {'passed': 0, 'blocked': 2, 'failed': 1}[status]


if __name__ == '__main__':
    raise SystemExit(main())
