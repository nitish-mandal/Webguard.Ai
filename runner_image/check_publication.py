"""Phase 9 gate: real Docker verification and one durable simulated draft, no skips."""

import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='webguard-publication-gate-') as directory:
        receipt = Path(directory) / 'results.xml'
        process = subprocess.run([sys.executable, '-m', 'pytest', 'worker/tests/test_publication_docker.py',
                                  '-q', '-r', 's', f'--junitxml={receipt}'], cwd=ROOT, shell=False, check=False)
        cases = list(ET.parse(receipt).iter('testcase')) if receipt.is_file() and receipt.stat().st_size <= 2097152 else []
        skipped = sum(item.find('skipped') is not None for item in cases)
        failures = sum(item.find('failure') is not None or item.find('error') is not None for item in cases)
        status = 'failed' if process.returncode or failures else ('blocked' if skipped or len(cases) != 1 else 'passed')
        print(json.dumps({'publication_acceptance': status, 'tests': len(cases), 'skipped': skipped,
                          'failures': failures, 'provider': 'offline', 'live_publication_tested': False}, sort_keys=True))
        return {'passed': 0, 'blocked': 2, 'failed': 1}[status]


if __name__ == '__main__':
    raise SystemExit(main())
