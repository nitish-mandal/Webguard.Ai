"""Phase 6 real demo gate: skipped execution must never be reported as acceptance."""

import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='webguard-reproduction-gate-') as directory:
        report = Path(directory) / 'result.xml'
        completed = subprocess.run([sys.executable, '-m', 'pytest',
                                    'worker/tests/test_detection_docker.py', '-q', '-r', 's',
                                    f'--junitxml={report}'], cwd=ROOT, shell=False, check=False)
        cases = list(ET.parse(report).iter('testcase')) if report.is_file() else []
        failures = sum(test.find('failure') is not None or test.find('error') is not None for test in cases)
        skipped = sum(test.find('skipped') is not None for test in cases)
        status = 'failed' if completed.returncode or failures else ('blocked' if skipped or len(cases) != 1 else 'passed')
        print(json.dumps({'reproduction_acceptance': status, 'tests': len(cases),
                          'skipped': skipped, 'failures': failures, 'pytest_exit': completed.returncode}, sort_keys=True))
        return {'passed': 0, 'blocked': 2, 'failed': 1}[status]


if __name__ == '__main__':
    raise SystemExit(main())
