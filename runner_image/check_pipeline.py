"""Strict Phase 10 real API/worker Docker acceptance; skipped tests block acceptance."""

import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='webguard-pipeline-gate-') as directory:
        receipt = Path(directory) / 'results.xml'
        result = subprocess.run([sys.executable, '-m', 'pytest', 'worker/tests/test_pipeline_docker.py',
            '-q', '-r', 's', f'--junitxml={receipt}'], cwd=ROOT, shell=False, check=False)
        cases = list(ET.parse(receipt).iter('testcase')) if receipt.is_file() and receipt.stat().st_size <= 2097152 else []
        skipped = sum(item.find('skipped') is not None for item in cases)
        failures = sum(item.find('failure') is not None or item.find('error') is not None for item in cases)
        status = 'failed' if result.returncode or failures else ('blocked' if skipped or len(cases) != 2 else 'passed')
        print(json.dumps({'pipeline_acceptance': status, 'tests': len(cases), 'skipped': skipped, 'failures': failures,
                          'gemini': 'offline_fake', 'github': 'simulated', 'live_tested': False}, sort_keys=True))
        return {'passed': 0, 'blocked': 2, 'failed': 1}[status]


if __name__ == '__main__':
    raise SystemExit(main())
