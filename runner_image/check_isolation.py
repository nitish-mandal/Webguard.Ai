"""A zero pytest exit with skipped Docker tests is BLOCKED, never acceptance."""

import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verdict(document, pytest_exit):
    cases = list(document.iter("testcase"))
    skipped = sum(case.find("skipped") is not None for case in cases)
    failures = sum(case.find("failure") is not None or case.find("error") is not None for case in cases)
    status = "failed" if pytest_exit or failures else (
        "blocked" if skipped or len(cases) < 16 else "passed")
    return {"isolation_acceptance": status, "tests": len(cases), "skipped": skipped,
            "failures": failures, "pytest_exit": pytest_exit}


def main():
    with tempfile.TemporaryDirectory(prefix="webguard-isolation-gate-") as directory:
        receipt = Path(directory) / "isolation.xml"
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "worker/tests/test_docker_isolation.py", "-q", "-r", "s",
             f"--junitxml={receipt}"], cwd=ROOT, shell=False, check=False,
        )
        if not receipt.exists() or receipt.stat().st_size > 2097152:
            report = {"isolation_acceptance": "failed", "reason": "missing_report"}
        else:
            report = verdict(ET.parse(receipt).getroot(), result.returncode)
        print(json.dumps(report, sort_keys=True))
        return {"passed": 0, "failed": 1, "blocked": 2}[report["isolation_acceptance"]]


if __name__ == "__main__":
    raise SystemExit(main())
