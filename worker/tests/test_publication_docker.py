"""Real Docker detection/verification, followed by exactly one simulated draft PR."""

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
from worker.github_publishers import FakeGitHubPublisher
from worker.publication import PublicationService
from worker.repair import RepairService
from worker.source_service import RepositoryAccess
from worker.tests.test_docker_isolation import real
from worker.tests.test_repositories import fixture_git
from worker.verification import VerificationService

__all__ = ['fixture_git', 'real']
pytestmark = pytest.mark.isolation


def test_real_verified_demo_publishes_exactly_one_simulated_draft(real, fixture_git, tmp_path, request):
    original, _ = real
    demo = Path(__file__).resolve().parents[2] / 'demo-repository'
    names = ('pagination.py', 'tests/test_pagination.py')
    before = [(demo / name).read_bytes() for name in names]
    jobs = JobService(Settings(database_url=f"sqlite:///{tmp_path / 'publication.sqlite'}",
                               workspace_root=str(tmp_path / 'publication-owned'), lease_seconds=120,
                               max_repair_attempts=1))
    access = RepositoryAccess.fixture(jobs, fixture_git)
    runner = DockerRunner(access.manager, original.image_id, original.limits, client=original.client)
    def recover_owned():
        assert all(runner.recover(min_age_seconds=0).values())
    request.addfinalizer(recover_owned)
    execution = ExecutionService(jobs, runner)
    job = jobs.create('simulated-draft-demo', 'demo-repository')
    lease = jobs.claim('publisher')
    jobs.advance(lease, JobState.BASELINING)
    detected = DetectionService(access, execution).detect(lease)
    assert detected.verdict == 'reproduced' and len(detected.runs) == 2, asdict(detected)
    candidate = RepairService(access).propose(lease)
    verified = VerificationService(access, execution).verify(lease, candidate['id'])
    assert verified.outcome == 'verified' and len(verified.runs) == 4
    assert [run['exit_code'] for run in verified.runs.values()] == [1, 0, 0, 0]
    budget = jobs.get(job['id'])
    result = PublicationService(access).publish(lease)
    assert result.outcome == 'draft_pr_created' and result.simulated
    assert jobs.get(job['id'])['state'] == JobState.DRAFT_PR_CREATED
    remote = FakeGitHubPublisher(access.manager.root / 'fake-github.sqlite', 'demo-repository')
    assert remote.draft_count() == 1
    reopened = JobService(jobs.settings)
    again = PublicationService(RepositoryAccess.fixture(reopened, fixture_git), remote).publish(lease)
    assert again.publication == result.publication and remote.draft_count() == 1
    assert reopened.publication(job['id'])['simulated']
    assert jobs.get(job['id'])['model_calls'] == budget['model_calls']
    assert jobs.get(job['id'])['execution_seconds'] == budget['execution_seconds']
    assert before == [(demo / name).read_bytes() for name in names]
    assert all(runner.recover(min_age_seconds=0).values())
    if os.environ.get('WEBGUARD_RECORD_ACCEPTANCE') == '1':
        with remote.connect() as connection:
            draft = json.loads(connection.execute('SELECT payload FROM drafts').fetchone()[0])
        report = {'provider': 'offline', 'live_publication_tested': False, 'simulated_drafts': 1,
                  'sha': detected.sha, 'original_failure': detected.runs[0],
                  'verification': asdict(verified), 'publication': asdict(result), 'draft': draft,
                  'intent': jobs.publication_intent(job['id']), 'fixture_unchanged': True,
                  'counters': {key: jobs.get(job['id'])[key] for key in
                               ('repair_attempts', 'publication_attempts', 'model_calls', 'execution_seconds')}}
        (demo.parent / 'docs/baseline/phase9-offline-demo.json').write_text(
            json.dumps(report, indent=2), encoding='utf8')
