"""Real Docker verification and negative controls. No target code runs on the host."""

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path

import pytest

from backend.app.domain import JobState
from backend.app.jobs import JobService
from backend.app.settings import Settings
from worker.detection import DetectionService
from worker.docker_runner import DockerRunner
from worker.execution import ExecutionService
from worker.repair import RepairService
from worker.source_common import Budget
from worker.source_service import RepositoryAccess
from worker.tests.test_docker_isolation import real
from worker.tests.test_repair import Reply
from worker.tests.test_repositories import fixture_git
from worker.verification import VerificationService

__all__ = ['fixture_git', 'real']
pytestmark = pytest.mark.isolation


def bad_patch(request, scenario):
    if scenario == 'bug_remains':
        old, new = 'exclusive end is one too small.', 'unverified proposed pagination implementation.'
    else:
        old = 'if page < 0 or page_size <= 0:'
        new = ('if page >= 0 and page_size > 0:\n'
               '        return items[page * page_size:(page + 1) * page_size]\n    if False:')
    return json.dumps({'diagnosis': 'Deliberately incorrect proposal for negative acceptance coverage.',
                       'edits': [{'path': 'pagination.py', 'old_text': old, 'new_text': new}]})


@pytest.mark.parametrize('scenario', ['valid', 'bug_remains', 'previously_passing_breaks'])
def test_real_verification_of_exact_fake_proposal(real, fixture_git, tmp_path, scenario):
    original, _ = real
    demo = Path(__file__).resolve().parents[2] / 'demo-repository'
    before = [(demo / name).read_bytes() for name in ('pagination.py', 'tests/test_pagination.py')]
    jobs = JobService(Settings(database_url=f"sqlite:///{tmp_path / 'verification.sqlite'}",
                               workspace_root=str(tmp_path / 'verification-owned'), lease_seconds=120,
                               max_repair_attempts=1))
    access = RepositoryAccess.fixture(jobs, fixture_git)
    runner = DockerRunner(access.manager, original.image_id, original.limits, client=original.client)
    execution = ExecutionService(jobs, runner)
    job = jobs.create('verified-demo-' + scenario, 'demo-repository')
    lease = jobs.claim('verifier')
    jobs.advance(lease, JobState.BASELINING)
    detected = DetectionService(access, execution).detect(lease)
    assert detected.verdict == 'reproduced'
    provider = None if scenario == 'valid' else Reply(lambda request: bad_patch(request, scenario))
    candidate = RepairService(access, provider).propose(lease)
    verified = VerificationService(access, execution).verify(lease, candidate['id'])
    persisted = jobs.candidates(job['id'])[0]
    if scenario == 'valid':
        assert verified.outcome == 'verified', asdict(verified)
        assert jobs.get(job['id'])['state'] == JobState.VERIFIED and persisted['status'] == 'verified'
        assert len(verified.runs) == 4
        assert [run['exit_code'] for run in verified.runs.values()] == [1, 0, 0, 0]
        assert len({run['container_id'] for run in verified.runs.values()}) == 4
    else:
        assert verified.outcome == 'failed', asdict(verified)
        assert jobs.get(job['id'])['state'] == JobState.FAILED and persisted['status'] == 'proposed'
        failed_step = 'original' if scenario == 'bug_remains' else 'suite'
        assert verified.runs[failed_step]['exit_code'] == 1
    assert all(run['image_id'] == detected.runs[0]['image_id'] for run in verified.runs.values())
    assert all(run['source_sha'] == detected.sha and run['cleanup_complete'] for run in verified.runs.values())
    assert before == [(demo / name).read_bytes() for name in ('pagination.py', 'tests/test_pagination.py')]
    assert all(runner.recover(min_age_seconds=0).values())
    if os.environ.get('WEBGUARD_RECORD_ACCEPTANCE') == '1':
        destination = demo.parent / 'docs/baseline'
        report = {'scenario': scenario, 'candidate': persisted, 'state': jobs.get(job['id'])['state'],
                  'sha': detected.sha, 'original_failure': detected.runs[0],
                  'verification': asdict(verified), 'fixture_unchanged': True}
        (destination / f'phase8-real-{scenario}.json').write_text(json.dumps(report, indent=2), encoding='utf8')
        if scenario == 'valid':
            workspace = access.manager.reopen(job['id'], jobs.source_snapshot(job['id']), Budget(5))
            for path in (access.manager.path(workspace) / 'verification-receipts').glob('*.json'):
                payload = path.read_bytes()
                if hashlib.sha256(payload).hexdigest() == verified.artifact_digest:
                    (destination / 'phase8-verification-receipt.json').write_bytes(payload)
