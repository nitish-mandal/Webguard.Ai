"""Real Phase 6 acceptance: committed temporary demo, two fresh Docker executions."""

import hashlib
import json
import os
from pathlib import Path

import pytest

from backend.app.domain import JobState
from backend.app.jobs import JobService
from backend.app.settings import Settings
from worker.detection import DetectionService
from worker.docker_runner import DockerRunner
from worker.execution import ExecutionService
from worker.source_common import Budget
from worker.source_service import RepositoryAccess
from worker.tests.test_docker_isolation import real
from worker.tests.test_repositories import fixture_git, git

pytestmark = pytest.mark.isolation
__all__ = ['fixture_git', 'real']


def test_real_demo_reproduces_same_assertion_and_invalid_input_stays_passing(real, fixture_git, tmp_path):
    original_runner, _ = real
    demo = Path(__file__).resolve().parents[2] / 'demo-repository'
    before = [(demo / name).read_bytes() for name in ('pagination.py', 'tests/test_pagination.py')]
    jobs = JobService(Settings(database_url=f"sqlite:///{tmp_path / 'real-detection.sqlite'}",
                               workspace_root=str(tmp_path / 'real-detection-owned'), lease_seconds=120))
    access = RepositoryAccess.fixture(jobs, fixture_git)
    runner = DockerRunner(access.manager, original_runner.image_id, original_runner.limits,
                          client=original_runner.client)
    job = jobs.create('real-demo-detection', 'demo-repository')
    lease = jobs.claim('real-detector')
    jobs.advance(lease, JobState.BASELINING)
    found = DetectionService(access, ExecutionService(jobs, runner)).detect(lease)
    if os.environ.get('WEBGUARD_RECORD_ACCEPTANCE') == '1':
        evidence_root = demo.parent / 'docs/baseline'
        record = jobs.source_snapshot(job['id'])
        workspace = access.manager.reopen(job['id'], record, Budget(5))
        for path in (access.manager.path(workspace) / 'detection-receipts').glob('*.json'):
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest() == found.artifact_digest:
                (evidence_root / 'docker-demo-evidence.json').write_bytes(payload)
        summary = {'verdict': found.verdict, 'job_id': job['id'], 'state': jobs.get(job['id'])['state'],
                   'sha': found.sha, 'failing_test_id': found.failing_test_id,
                   'failure_signature': found.failure_signature, 'artifact_digest': found.artifact_digest,
                   'runs': [{key: run[key] for key in ('run_id', 'container_id', 'source_sha', 'input_digest',
                                                       'exit_code', 'duration_seconds', 'image_id',
                                                       'cleanup_complete', 'test_report')}
                            for run in found.runs]}
        (evidence_root / 'docker-demo-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf8')
    assert found.verdict == 'reproduced'
    assert found.sha == git(fixture_git, 'rev-parse', 'HEAD') == jobs.get(job['id'])['sha']
    assert found.failing_test_id == 'tests/test_pagination.py::test_first_page_contains_requested_count'
    assert len(found.runs) == 2 and found.failure_signature
    assert found.runs[0]['run_id'] != found.runs[1]['run_id']
    for run in found.runs:
        assert run['exit_code'] == 1 and run['cleanup_complete']
        assert run['image_id'] == runner.image_id
        assert any(test['node_id'] == 'tests/test_pagination.py::test_invalid_page_rejected'
                   and test['phase'] == 'call' and test['outcome'] == 'passed'
                   for test in run['test_report']['tests'])
    assert before == [(demo / name).read_bytes() for name in ('pagination.py', 'tests/test_pagination.py')]
    assert all(runner.recover(min_age_seconds=0).values())
