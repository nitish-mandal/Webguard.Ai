"""Phase 7 real reproduction -> fake proposal acceptance, without Phase 8 verification."""

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
from worker.repair import RepairService
from worker.runner_models import RunInput
from worker.source_common import Budget
from worker.source_service import RepositoryAccess
from worker.tests.test_docker_isolation import real
from worker.tests.test_repositories import fixture_git

__all__ = ['fixture_git', 'real']
pytestmark = pytest.mark.isolation


def test_real_reproduction_then_offline_proposal_awaits_phase8(real, fixture_git, tmp_path):
    original, _ = real
    demo = Path(__file__).resolve().parents[2] / 'demo-repository'
    before = [(demo / name).read_bytes() for name in ('pagination.py', 'tests/test_pagination.py')]
    jobs = JobService(Settings(database_url=f"sqlite:///{tmp_path / 'proposal.sqlite'}",
                               workspace_root=str(tmp_path / 'owned-proposal'), lease_seconds=120))
    access = RepositoryAccess.fixture(jobs, fixture_git)
    runner = DockerRunner(access.manager, original.image_id, original.limits, client=original.client)
    job = jobs.create('real-offline-proposal', 'demo-repository')
    lease = jobs.claim('proposer')
    jobs.advance(lease, JobState.BASELINING)
    detected = DetectionService(access, ExecutionService(jobs, runner)).detect(lease)
    assert detected.verdict == 'reproduced'  # Actual Docker executions, never a mock proof.
    candidate = RepairService(access).propose(lease)
    assert candidate['status'] == 'proposed' and candidate['provider'] == 'offline'
    assert candidate['sha'] == detected.sha
    assert jobs.get(job['id'])['state'] == JobState.REPAIRING
    workspace = access.manager.reopen(job['id'], jobs.source_snapshot(job['id']), Budget(5))
    attempt = access.manager.path(workspace) / 'attempts' / candidate['attempt_id']
    _, digest = runner._package(RunInput(workspace, attempt, 'verification'))
    assert digest == candidate['patch_digest']
    assert b'page_size - 1' not in (attempt / 'pagination.py').read_bytes()
    assert before == [(demo / name).read_bytes() for name in ('pagination.py', 'tests/test_pagination.py')]
    assert all(runner.recover(min_age_seconds=0).values())
    if os.environ.get('WEBGUARD_RECORD_ACCEPTANCE') == '1':
        for receipt in (access.manager.path(workspace) / 'candidate-receipts').glob('*.json'):
            payload = receipt.read_bytes()
            if hashlib.sha256(payload).hexdigest() == candidate['artifact_digest']:
                (demo.parent / 'docs/baseline/phase7-proposal-receipt.json').write_bytes(payload)
        (demo.parent / 'docs/baseline/phase7-real-proposal.json').write_text(json.dumps({
            'candidate': candidate, 'reproduction_sha': detected.sha,
            'failure_signature': detected.failure_signature, 'state': jobs.get(job['id'])['state'],
            'reproduction_containers': [run['container_id'] for run in detected.runs],
            'image_id': runner.image_id, 'verified': False, 'phase8_verification': 'not_run',
            'fixture_unchanged': True}, indent=2), encoding='utf8')
