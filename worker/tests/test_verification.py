"""Verification policy/controller tests with data fakes. No target code runs on the host."""

import hashlib
import json
import uuid

import pytest

from backend.app.domain import Conflict, JobState
from backend.app.jobs import JobService
from backend.app.settings import Redactor
from worker.check_policy import DISCRIMINATING_IDS, REGRESSION_IDS, check_command
from worker.docker_client import DockerFault
from worker.docker_runner import DockerRunner
from worker.repair import RepairService
from worker.runner_models import Outcome, RunResult
from worker.source_common import Budget
from worker.test_reports import PREFIX, decode_report
from worker.tests.test_detection import IMAGE, FakeExecution, result
from worker.tests.test_repositories import access, fixture_git, job_lease
from worker.verification import VerificationService

__all__ = ['access', 'fixture_git']


@pytest.fixture
def candidate(access):
    from worker.detection import DetectionService

    _, lease = job_lease(access)
    DetectionService(access, FakeExecution(access, [result(), result()])).detect(lease)
    proposal = RepairService(access).propose(lease)
    return access, lease, proposal


class FakeVerificationExecution:
    def __init__(self, access, fault=None):
        self.jobs = access.jobs
        self.runner = DockerRunner(access.manager, IMAGE)
        self.runner.preflight = lambda: IMAGE
        self.requests, self.fault = [], fault

    def execute(self, lease, request, *, record_evidence):
        assert record_evidence is False
        self.jobs.reserve_usage(lease, execution_seconds=1)
        self.requests.append(request)
        payload, patch = self.runner._package(request)
        nodes = (REGRESSION_IDS if request.check == 'regression' else [request.test_id] if request.check == 'original'
                 else ['tests/test_pagination.py::test_first_page_contains_requested_count',
                       'tests/test_pagination.py::test_invalid_page_rejected'])
        control = request.kind == 'control'
        records = []
        for node in nodes:
            for phase in ('setup', 'call', 'teardown'):
                failed = control and node in DISCRIMINATING_IDS and phase == 'call'
                records.append({'node_id': node, 'phase': phase, 'outcome': 'failed' if failed else 'passed',
                                'assertion': failed, 'message': 'assert [] == [1]' if failed else '',
                                'traceback': 'E assert [] == [1]' if failed else ''})
        report = {'schema': 1, 'complete': True, 'exit_code': 1 if control else 0,
                  'tests': records, 'collection_errors': []}
        stdout = PREFIX + json.dumps(report) + '\n'
        run = RunResult(uuid.uuid4().hex, lease.job_id, request.workspace.sha,
                        request.workspace.manifest_digest, request.workspace.profile_digest,
                        input_digest=hashlib.sha256(payload).hexdigest(), patch_digest=patch,
                        outcome=Outcome.TEST_FAILURE if control else Outcome.PASSED,
                        exit_code=report['exit_code'], stdout=stdout, image_id=IMAGE,
                        container_id=uuid.uuid4().hex * 2, test_report=decode_report(stdout, report['exit_code'], Redactor()),
                        command=check_command(self.runner.profile.test_command, request.check, request.test_id),
                        check=request.check)
        if self.fault:
            self.fault(self, request, run)
        return run


def test_exact_candidate_is_verified_only_after_four_complete_fresh_checks(candidate):
    access, lease, proposal = candidate
    executor = FakeVerificationExecution(access)
    verified = VerificationService(access, executor).verify(lease)
    assert verified.outcome == 'verified' and len(verified.runs) == 4
    assert len({request.attempt for request in executor.requests}) == 4
    assert access.jobs.get(lease.job_id)['state'] == JobState.VERIFIED
    reopened = JobService(access.jobs.settings)
    persisted = reopened.candidates(lease.job_id)[0]
    assert persisted['status'] == 'verified' and persisted['patch_digest'] == proposal['patch_digest']
    assert persisted['verification_id'] == verified.round_id
    assert reopened.verification_rounds(lease.job_id)[0]['artifact_digest'] == verified.artifact_digest
    before = reopened.get(lease.job_id)['execution_seconds']
    assert VerificationService(access, executor).verify(lease).reason == 'already_verified'
    assert reopened.get(lease.job_id)['execution_seconds'] == before


@pytest.mark.parametrize('bad', ['original', 'suite', 'regression', 'skip', 'missing', 'extra', 'incomplete', 'wrong_patch', 'image', 'command', 'container_reuse'])
def test_failed_missing_skipped_or_mismatched_checks_never_verify(candidate, bad):
    access, lease, _ = candidate
    def corrupt(executor, request, run):
        if request.kind == 'control':
            return
        if bad in ('original', 'suite', 'regression') and request.check != bad:
            return
        if bad in ('original', 'suite', 'regression'):
            run.outcome, run.exit_code = Outcome.TEST_FAILURE, 1
            run.test_report['exit_code'] = 1
            test = next(item for item in run.test_report['tests'] if item['phase'] == 'call')
            test.update(outcome='failed', assertion=True)
        elif bad == 'skip': run.test_report['tests'][1]['outcome'] = 'skipped'
        elif bad == 'missing': run.test_report['tests'].pop()
        elif bad == 'extra':
            run.test_report['tests'].append({**run.test_report['tests'][0], 'node_id': 'tests/test_extra.py::test_extra'})
        elif bad == 'incomplete': run.test_report['complete'] = False
        elif bad == 'wrong_patch': run.patch_digest = '0' * 64
        elif bad == 'image': run.image_id = 'sha256:' + '0' * 64
        elif bad == 'command': run.command = ['untrusted-command']
        elif bad == 'container_reuse': run.container_id = '0' * 64
    rejected = VerificationService(access, FakeVerificationExecution(access, corrupt)).verify(lease)
    assert rejected.outcome == 'failed'
    assert access.jobs.get(lease.job_id)['state'] == JobState.FAILED
    assert access.jobs.candidates(lease.job_id)[0]['status'] == 'proposed'
    assert not any(row['status'] == 'verified' for row in access.jobs.verification_rounds(lease.job_id))


def test_new_regressions_must_detect_the_unpatched_bug(candidate):
    access, lease, _ = candidate
    def green_control(executor, request, run):
        if request.kind == 'control':
            run.outcome, run.exit_code = Outcome.PASSED, 0
            run.test_report['exit_code'] = 0
            for test in run.test_report['tests']:
                test.update(outcome='passed', assertion=False)
    rejected = VerificationService(access, FakeVerificationExecution(access, green_control)).verify(lease)
    assert rejected.reason == 'regression_not_discriminating'


def test_timeout_retries_from_clean_copies_and_preserves_usage(candidate):
    access, lease, _ = candidate
    def once(executor, request, run):
        if len(executor.requests) == 2:
            run.outcome, run.exit_code = Outcome.TIMEOUT, 124
    executor = FakeVerificationExecution(access, once)
    verified = VerificationService(access, executor).verify(lease)
    assert verified.outcome == 'verified' and len(executor.requests) == 6
    assert len({request.attempt for request in executor.requests}) == 6
    rounds = JobService(access.jobs.settings).verification_rounds(lease.job_id)
    assert [row['status'] for row in rounds] == ['failed', 'verified']
    assert access.jobs.get(lease.job_id)['execution_seconds'] == 8  # Two fake baselines + six runs.


def test_unavailable_docker_blocks_without_budget_or_round_reset(candidate):
    access, lease, _ = candidate
    executor = FakeVerificationExecution(access)
    def absent(): raise DockerFault('docker_missing')
    executor.runner.preflight = absent
    before = access.jobs.get(lease.job_id)['execution_seconds']
    rejected = VerificationService(access, executor).verify(lease)
    assert rejected.outcome == 'blocked' and rejected.reason == 'docker_missing'
    assert access.jobs.get(lease.job_id)['execution_seconds'] == before
    assert access.jobs.verification_rounds(lease.job_id) == []


def test_changed_candidate_or_original_tests_are_rejected_before_execution(candidate):
    access, lease, proposal = candidate
    workspace = access.manager.reopen(lease.job_id, access.jobs.source_snapshot(lease.job_id), Budget(5))
    attempt = access.manager.path(workspace) / 'attempts' / proposal['attempt_id']
    (attempt / 'tests/test_pagination.py').write_text('def test_fake(): pass\n')
    executor = FakeVerificationExecution(access)
    rejected = VerificationService(access, executor).verify(lease)
    assert rejected.outcome == 'blocked' and not executor.requests


def test_cancellation_fences_verification_and_never_marks_candidate_verified(candidate):
    access, lease, _ = candidate
    def cancel(executor, request, run):
        access.jobs.cancel(lease.job_id)
        run.outcome = Outcome.CANCELLED
    cancelled = VerificationService(access, FakeVerificationExecution(access, cancel)).verify(lease)
    assert cancelled.outcome == 'cancelled'
    assert access.jobs.get(lease.job_id)['state'] == JobState.CANCELLED
    assert access.jobs.candidates(lease.job_id)[0]['status'] == 'proposed'
    assert access.jobs.verification_rounds(lease.job_id)[0]['reason'] == 'cancelled'


def test_legacy_passing_evidence_cannot_bypass_aggregate_gate(candidate):
    access, lease, proposal = candidate
    access.jobs.advance(lease, JobState.VERIFYING)
    access.jobs.add_evidence(lease, kind='verification', artifact_digest='a' * 64,
                             exit_code=0, summary={}, patch_digest=proposal['patch_digest'])
    with pytest.raises(Conflict): access.jobs.advance(lease, JobState.VERIFIED)


def test_redacts_retained_verification_results(candidate):
    access, lease, _ = candidate
    secret = 'private-verification-key'
    access.jobs.redactor = Redactor((secret,))
    def output(executor, request, run): run.stdout += secret
    verified = VerificationService(access, FakeVerificationExecution(access, output)).verify(lease)
    assert verified.outcome == 'verified'
    assert secret not in str(verified.runs)


def test_blocked_mid_round_resumes_with_fresh_copies_and_persistent_round_count(candidate):
    access, lease, _ = candidate
    def once(executor, request, run):
        if len(executor.requests) == 2:
            run.outcome = Outcome.BLOCKED
    executor = FakeVerificationExecution(access, once)
    verifier = VerificationService(access, executor)
    assert verifier.verify(lease).outcome == 'blocked'
    assert JobService(access.jobs.settings).verification_rounds(lease.job_id)[0]['status'] == 'blocked'
    assert verifier.verify(lease).outcome == 'verified'
    assert len({request.attempt for request in executor.requests}) == 6
    assert [row['status'] for row in access.jobs.verification_rounds(lease.job_id)] == ['blocked', 'verified']


def test_persistent_execution_budget_exhaustion_prevents_target_calls(candidate):
    access, lease, _ = candidate
    with access.jobs.db.transaction() as connection:
        connection.execute('UPDATE jobs SET max_execution_seconds=execution_seconds WHERE id=?', (lease.job_id,))
    executor = FakeVerificationExecution(access)
    rejected = VerificationService(access, executor).verify(lease)
    assert rejected.reason == 'budget_exhausted' and not executor.requests
    assert access.jobs.get(lease.job_id)['failure_reason'] == 'budget_exhausted'


def test_deadline_during_verification_expires_job_without_verifying(candidate):
    access, lease, _ = candidate
    def expire(executor, request, run):
        deadline = access.jobs.get(lease.job_id)['deadline']
        access.jobs.clock = lambda: deadline + 1
    rejected = VerificationService(access, FakeVerificationExecution(access, expire)).verify(lease)
    assert rejected.reason == 'deadline_exceeded'
    assert access.jobs.get(lease.job_id)['failure_reason'] == 'deadline_exceeded'
    assert access.jobs.candidates(lease.job_id)[0]['status'] == 'proposed'


def test_stale_owner_cannot_finish_verification(candidate):
    access, lease, _ = candidate
    def steal(executor, request, run):
        access.jobs.release(lease)
        access.jobs.claim('replacement-verifier')
    rejected = VerificationService(access, FakeVerificationExecution(access, steal)).verify(lease)
    assert rejected.outcome == 'stale_owner'
    assert access.jobs.candidates(lease.job_id)[0]['status'] == 'proposed'


def test_aggregate_record_rollback_cannot_mark_candidate_verified(candidate, monkeypatch):
    access, lease, _ = candidate
    original = access.jobs._event
    def broken(connection, job, kind, data, now):
        if kind == 'verification_completed':
            raise RuntimeError('injected transaction failure')
        return original(connection, job, kind, data, now)
    monkeypatch.setattr(access.jobs, '_event', broken)
    with pytest.raises(RuntimeError, match='injected'):
        VerificationService(access, FakeVerificationExecution(access)).verify(lease)
    assert access.jobs.get(lease.job_id)['state'] == JobState.VERIFYING
    assert access.jobs.candidates(lease.job_id)[0]['status'] == 'proposed'
    assert not any(item['kind'] == 'verification' for item in access.jobs.evidence(lease.job_id))
