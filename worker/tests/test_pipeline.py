"""Pipeline lifecycle with data fakes; target code is never run on the host."""

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app.domain import FailureReason, JobState, LeaseLost, NotFound
from backend.app.jobs import JobService
from worker.docker_client import DockerFault
from worker.github_publishers import FakeGitHubPublisher, PublicationError
from worker.pipeline import LeaseKeeper, Runtime, Worker, run_job
from worker.source_common import Budget
from worker.source_service import RepositoryAccess
from worker.tests.test_detection import FakeExecution, result
from worker.tests.test_repositories import access, fixture_git
from worker.tests.test_verification import FakeVerificationExecution

__all__ = ['access', 'fixture_git']


class Execution(FakeVerificationExecution):
    def __init__(self, access):
        super().__init__(access)
        self.baseline = FakeExecution(access, [result(), result()])
        self.runner.recover = lambda **kwargs: {}

    def execute(self, lease, request, *, record_evidence):
        if request.kind == 'baseline':
            return self.baseline.execute(lease, request, record_evidence=record_evidence)
        return super().execute(lease, request, record_evidence=record_evidence)


@pytest.fixture
def runtime(access):
    value = Runtime(access, Execution(access))
    yield value
    value.close()


def test_worker_runs_entire_pipeline_with_evidence_and_cleans_attempts(runtime):
    job = runtime.jobs.create('automatic', 'demo-repository')
    found = Worker(runtime).run_once()
    assert found.outcome == 'draft_pr_created', found
    assert runtime.jobs.publication(job['id'])['simulated']
    assert runtime.publication.remote.draft_count() == 1
    assert runtime.jobs.get(job['id'])['lease_owner'] is None
    assert runtime.jobs.get(job['id'])['model_calls'] == 1
    workspace = runtime.manager.reopen(job['id'], runtime.jobs.source_snapshot(job['id']), Budget(5))
    assert list((runtime.manager.path(workspace) / 'attempts').iterdir()) == []
    assert list((runtime.manager.path(workspace) / 'verification-receipts').glob('*.json'))
    stages = [item['data']['stage'] for item in runtime.jobs.events(job['id'], limit=100) if item['kind'] == 'worker_stage']
    assert stages == ['source', 'reproduction', 'repair', 'verification', 'publication']
    assert Worker(runtime).run_once() is None


def test_run_job_requires_a_claim_and_matching_identity(runtime):
    job = runtime.jobs.create('identity', 'demo-repository')
    lease = runtime.jobs.claim('test')
    with pytest.raises(ValueError):
        run_job('f' * 32, runtime=runtime, lease=lease)
    runtime.jobs.release(lease)
    with pytest.raises(LeaseLost):
        run_job(job['id'], runtime=runtime, lease=lease)


def test_competing_workers_use_separate_connections_and_one_claim(runtime, fixture_git):
    job = runtime.jobs.create('compete', 'demo-repository')
    jobs2 = JobService(runtime.jobs.settings)
    other = Runtime(RepositoryAccess.fixture(jobs2, fixture_git))
    barrier = threading.Barrier(2)
    def claim(service):
        barrier.wait()
        return service.claim(uuid.uuid4().hex)
    try:
        with ThreadPoolExecutor(2) as pool:
            claims = list(pool.map(claim, [runtime.jobs, jobs2]))
        assert sum(item is not None for item in claims) == 1
        lease = next(item for item in claims if item)
        assert run_job(job['id'], runtime=runtime, lease=lease).outcome == 'draft_pr_created'
        assert runtime.publication.remote.draft_count() == 1
    finally:
        other.close()


def test_expired_lease_recovers_without_resetting_usage(runtime):
    job = runtime.jobs.create('expired', 'demo-repository')
    first = runtime.jobs.claim('dead-worker')
    runtime.jobs.advance(first, JobState.BASELINING)
    runtime.access.prepare(first)
    runtime.jobs.reserve_usage(first, execution_seconds=1)
    with runtime.jobs.db.transaction() as connection:
        connection.execute('UPDATE jobs SET lease_expires_at=? WHERE id=?', (time.time() - 1, job['id']))
    with pytest.raises(LeaseLost): runtime.jobs.advance(first, JobState.REPRODUCED)
    assert Worker(runtime).run_once().outcome == 'draft_pr_created'
    row = runtime.jobs.get(job['id'])
    assert row['claims'] == 2 and row['execution_seconds'] == 7 and row['model_calls'] == 1


def test_heartbeat_renews_during_blocking_stage_and_stops_on_cancel(runtime):
    short = runtime.jobs.settings.model_copy(update={'lease_seconds': 1})
    jobs = JobService(short)
    job = jobs.create('heartbeat', 'demo-repository')
    lease = jobs.claim('slow')
    with LeaseKeeper(jobs, lease) as keeper:
        time.sleep(1.4)
        jobs.check_lease(lease)
        assert not keeper.lost.is_set() and jobs.claim('competitor') is None
        jobs.cancel(job['id'])
        assert keeper.lost.wait(1)
    assert not keeper.thread.is_alive()


def test_missing_docker_pauses_without_execution_and_can_resume_without_budget_reset(runtime):
    job = runtime.jobs.create('docker', 'demo-repository')
    original = runtime.runner.preflight
    def unavailable(): raise DockerFault('docker_missing')
    runtime.runner.preflight = unavailable
    found = Worker(runtime).run_once()
    assert found.outcome == 'blocked'
    row = runtime.jobs.get(job['id'])
    assert row['state'] == 'queued' and row['execution_seconds'] == row['model_calls'] == 0
    assert runtime.jobs.dispatch(job['id'])['paused']
    assert Worker(runtime).run_once() is None
    runtime.jobs.resume_dispatch(job['id'])
    runtime.runner.preflight = original
    assert Worker(runtime).run_once().outcome == 'draft_pr_created'
    assert runtime.jobs.get(job['id'])['claims'] == 2


def test_restart_after_accepted_pr_never_repeats_repair_or_verification(runtime, fixture_git):
    job = runtime.jobs.create('publication-crash', 'demo-repository')
    original = runtime.publication.remote.create_draft
    def accepted(*args):
        original(*args)
        raise SystemExit('injected worker death')
    runtime.publication.remote.create_draft = accepted
    lease = runtime.jobs.claim('old-process')
    with pytest.raises(SystemExit): run_job(job['id'], runtime=runtime, lease=lease)
    before = runtime.jobs.get(job['id'])
    assert before['state'] == 'publishing' and runtime.publication.remote.draft_count() == 1
    with runtime.jobs.db.transaction() as connection:
        connection.execute('UPDATE jobs SET lease_expires_at=? WHERE id=?', (time.time() - 1, job['id']))
    jobs = JobService(runtime.jobs.settings)
    reopened_access = RepositoryAccess.fixture(jobs, fixture_git)
    restarted = Runtime(reopened_access, Execution(reopened_access),
                        remote=FakeGitHubPublisher(runtime.publication.remote.path, 'demo-repository'))
    def unavailable(**kwargs): raise DockerFault('docker_missing')
    restarted.runner.recover = unavailable
    try:
        assert Worker(restarted).run_once().outcome == 'draft_pr_created'
        after = jobs.get(job['id'])
        assert after['execution_seconds'] == before['execution_seconds'] and after['model_calls'] == before['model_calls']
        assert after['publication_attempts'] == 1 and restarted.publication.remote.draft_count() == 1
    finally:
        restarted.close()


def test_publication_timeout_schedules_a_persistent_retry(runtime):
    job = runtime.jobs.create('retry', 'demo-repository')
    original = runtime.publication.remote.create_draft
    def timeout(*args):
        original(*args)
        raise PublicationError('remote_timeout')
    runtime.publication.remote.create_draft = timeout
    assert Worker(runtime).run_once().outcome == 'retryable'
    assert Worker(runtime).run_once() is None
    assert not runtime.jobs.dispatch(job['id'])['paused']
    with runtime.jobs.db.transaction() as connection:
        connection.execute('UPDATE job_dispatch SET next_run_at=0 WHERE job_id=?', (job['id'],))
    assert Worker(runtime).run_once().outcome == 'draft_pr_created'
    assert runtime.publication.remote.draft_count() == 1


def test_cancel_after_remote_acceptance_reports_actual_draft_without_reviving_job(runtime):
    job = runtime.jobs.create('cancel-publish', 'demo-repository')
    original = runtime.publication.remote.create_draft
    def accepted(*args):
        original(*args)
        runtime.jobs.cancel(job['id'])
        raise PublicationError('remote_timeout')
    runtime.publication.remote.create_draft = accepted
    assert Worker(runtime).run_once().outcome == 'cancelled'
    intent = runtime.jobs.publication_intent(job['id'])
    assert intent['pr_number'] == 1 and intent['pr_url'].startswith('simulated://')
    assert runtime.jobs.get(job['id'])['state'] == 'cancelled'
    assert runtime.jobs.publication(job['id']) is None
    assert runtime.publication.remote.draft_count() == 1


def test_worker_drain_session_prevents_further_claims(runtime):
    worker = Worker(runtime)
    runtime.jobs.worker_session(worker.owner, start=True)
    assert runtime.jobs.worker_available()
    runtime.jobs.stop_worker(worker.owner)
    runtime.jobs.create('no-claim-after-drain', 'demo-repository')
    assert worker.run_once() is None and not runtime.jobs.worker_available()
    with pytest.raises(NotFound): runtime.jobs.resume_dispatch('f' * 32)


def test_default_demo_git_sha_is_stable_across_worker_restarts(tmp_path):
    from backend.app.settings import Settings

    config = Settings(database_url=f"sqlite:///{tmp_path / 'demo.sqlite'}", workspace_root=str(tmp_path / 'owned'))
    first = Runtime.configured(config)
    revision = first.access.adapter.resolve('main', first.manager.limits, Budget(5))
    first.close()
    second = Runtime.configured(config)
    try:
        assert second.access.adapter.resolve('main', second.manager.limits, Budget(5)) == revision
        assert second.fixture.path.parent != first.fixture.path.parent
    finally:
        second.close()


def test_restart_cleans_only_an_abandoned_owned_demo_fixture(tmp_path):
    from backend.app.settings import Settings

    config = Settings(database_url=f"sqlite:///{tmp_path / 'fixtures.sqlite'}", workspace_root=str(tmp_path / 'owned'))
    first = Runtime.configured(config)
    orphan = first.fixture
    first.jobs.worker_session(first.owner, start=True)
    first.jobs.worker_session(first.owner, stopped=True)
    first.fixture = None  # Simulate process death before filesystem cleanup.
    first.close()
    second = Runtime.configured(config)
    second.runner.recover = lambda **kwargs: {}
    try:
        second.maintenance()
        assert not orphan.path.parent.exists() and second.fixture.path.is_dir()
    finally:
        second.close()


def test_restart_never_trusts_an_incomplete_candidate(runtime):
    job = runtime.jobs.create('tampered', 'demo-repository')
    verify = runtime.verification.verify
    def corrupt(lease, candidate_id):
        candidate = runtime.jobs.candidates(lease.job_id)[0]
        snapshot = runtime.jobs.source_snapshot(lease.job_id)
        workspace = runtime.manager.reopen(lease.job_id, snapshot, Budget(5))
        (runtime.manager.path(workspace) / 'attempts' / candidate['attempt_id'] / 'pagination.py').write_text('unverified')
        return verify(lease, candidate_id)
    runtime.verification.verify = corrupt
    found = Worker(runtime).run_once()
    assert found.outcome == 'blocked' and runtime.jobs.dispatch(job['id'])['paused']
    assert runtime.jobs.get(job['id'])['state'] != JobState.VERIFIED
    assert runtime.publication.remote.draft_count() == 0


def test_deadline_after_accepted_publication_is_reconciled_without_reviving_job(runtime):
    job = runtime.jobs.create('deadline-publish', 'demo-repository')
    original = runtime.publication.remote.create_draft
    def accepted(*args):
        original(*args)
        with runtime.jobs.db.transaction() as connection:
            connection.execute('UPDATE jobs SET deadline=0 WHERE id=?', (job['id'],))
        raise PublicationError('remote_timeout')
    runtime.publication.remote.create_draft = accepted
    assert Worker(runtime).run_once().outcome == 'failed'
    row = runtime.jobs.get(job['id'])
    assert row['failure_reason'] == FailureReason.DEADLINE and runtime.jobs.publication(job['id']) is None
    assert runtime.jobs.publication_intent(job['id'])['pr_number'] == 1
    assert runtime.publication.remote.draft_count() == 1


def test_terminal_reconciliation_reservations_are_bounded_and_unknown_is_recorded(runtime):
    job = runtime.jobs.create('unknown-publish', 'demo-repository')
    create = runtime.publication.remote.create_draft
    def cancelled(*args):
        create(*args)
        runtime.jobs.cancel(job['id'])
        raise PublicationError('remote_timeout')
    runtime.publication.remote.create_draft = cancelled
    draft = runtime.publication.remote.draft
    def unavailable(*args): raise PublicationError('remote_unavailable')
    # Fail lookup only after the cancellation-triggering effect.
    def conditional(*args):
        return unavailable(*args) if runtime.jobs.get(job['id'])['state'] == JobState.CANCELLED else draft(*args)
    runtime.publication.remote.draft = conditional
    assert Worker(runtime).run_once().outcome == 'cancelled'
    events = runtime.jobs.events(job['id'], limit=100)
    assert any(item['kind'] == 'terminal_publication_reconciled' and
               item['data']['observation'] == 'outcome_unknown' for item in events)
    for _ in range(2):
        with runtime.jobs.db.transaction() as connection:
            connection.execute('UPDATE job_dispatch SET reconcile_after=0 WHERE job_id=?', (job['id'],))
        assert runtime.jobs.terminal_reconciliation(job['id']) == job['id']
    assert runtime.jobs.terminal_reconciliation(job['id']) is None
