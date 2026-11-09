"""Offline publication/reconciliation tests; no target execution or GitHub traffic."""

import json

import pytest

from backend.app.domain import JobState
from backend.app.jobs import JobService
from worker.github_publishers import FakeGitHubPublisher, PublicationError
from worker.publication import PublicationService
from worker.tests.test_repositories import access, fixture_git, job_lease
from worker.tests.test_verification import FakeVerificationExecution, candidate
from worker.verification import VerificationService

__all__ = ['access', 'candidate', 'fixture_git']


@pytest.fixture
def verified(candidate):
    access, lease, proposal = candidate
    assert VerificationService(access, FakeVerificationExecution(access)).verify(lease).outcome == 'verified'
    remote = FakeGitHubPublisher(access.manager.root / 'remote.sqlite', access.jobs.settings.allowed_repository)
    return access, lease, proposal, remote


def test_simulated_draft_is_unique_durable_and_contains_actual_checks(verified):
    access, lease, proposal, remote = verified
    before = access.jobs.get(lease.job_id)
    result = PublicationService(access, remote).publish(lease)
    assert result.outcome == 'draft_pr_created' and result.simulated
    record = result.publication
    assert record['draft'] == 1 and record['simulated'] and record['mode'] == 'offline'
    assert record['url'].startswith('simulated://') and record['patch_digest'] == proposal['patch_digest']
    assert record['sha'] == before['sha'] and record['commit_sha'] != record['sha']
    assert record['branch'] == 'webguard/jobs/' + lease.job_id
    reopened = JobService(access.jobs.settings)
    assert reopened.get(lease.job_id)['state'] == JobState.DRAFT_PR_CREATED
    assert reopened.publication(lease.job_id) == record
    fresh_remote = FakeGitHubPublisher(remote.path, remote.repository)
    again = PublicationService(access, fresh_remote).publish(lease)
    assert again.publication == record and fresh_remote.draft_count() == 1
    with remote.connect() as connection:
        draft = json.loads(connection.execute('SELECT payload FROM drafts').fetchone()[0])
    assert draft['simulated'] and draft['draft'] and 'SIMULATED' in draft['title']
    assert 'Baseline commit: ' + record['sha'] in draft['body']
    assert r'test\_first\_page\_contains\_requested\_count' in draft['body']
    assert 'unpatched' in draft['body'] and 'operator' in draft['body']
    assert access.jobs.get(lease.job_id)['model_calls'] == before['model_calls']
    assert access.jobs.get(lease.job_id)['execution_seconds'] == before['execution_seconds']


def test_unverified_job_cannot_publish(access):
    _, lease = job_lease(access)
    remote = FakeGitHubPublisher(access.manager.root / 'remote.sqlite', 'demo-repository')
    result = PublicationService(access, remote).publish(lease)
    assert result.outcome == 'blocked' and remote.draft_count() == 0
    assert access.jobs.publication_intent(lease.job_id) is None


def test_cancelled_verified_job_has_no_remote_side_effects(verified):
    access, lease, _, remote = verified
    access.jobs.cancel(lease.job_id)
    result = PublicationService(access, remote).publish(lease)
    assert result.outcome == 'cancelled' and remote.draft_count() == 0
    assert access.jobs.publication_intent(lease.job_id) is None


def test_stale_base_is_latched_and_requires_reverification(verified):
    access, lease, _, remote = verified
    original = access.jobs.get(lease.job_id)['sha']
    remote.seed_base('main', original)
    remote.move_base('main', '0' * 40)
    publisher = PublicationService(access, remote)
    blocked = publisher.publish(lease)
    assert blocked.outcome == 'blocked' and blocked.reason == 'base_moved'
    assert remote.draft_count() == 0 and access.jobs.get(lease.job_id)['state'] == JobState.VERIFIED
    remote.move_base('main', original)
    assert publisher.publish(lease).reason == 'base_moved'  # A move back does not waive re-verification.
    assert access.jobs.publication_intent(lease.job_id)['stale'] == 1


def test_wrong_remote_repository_is_rejected(verified):
    access, lease, _, remote = verified
    remote.repository = 'unapproved/repository'
    rejected = PublicationService(access, remote).publish(lease)
    assert rejected.reason == 'remote_identity' and remote.draft_count() == 0


@pytest.mark.parametrize('stage', ['branch', 'pr'])
def test_timeout_after_remote_acceptance_reconciles_without_duplicate(verified, stage):
    access, lease, _, remote = verified
    method = 'create_branch' if stage == 'branch' else 'create_draft'
    original = getattr(remote, method)
    calls = []
    def accepted_then_timeout(*args, **kwargs):
        calls.append(1)
        original(*args, **kwargs)
        raise PublicationError('remote_timeout')
    setattr(remote, method, accepted_then_timeout)
    publisher = PublicationService(access, remote)
    before = access.jobs.get(lease.job_id)
    uncertain = publisher.publish(lease)
    assert uncertain.outcome == 'retryable' and uncertain.reason == 'remote_timeout'
    assert access.jobs.get(lease.job_id)['state'] == JobState.VERIFIED
    recovered = PublicationService(access, FakeGitHubPublisher(remote.path, remote.repository)).publish(lease)
    assert recovered.outcome == 'draft_pr_created' and remote.draft_count() == 1
    assert len(calls) == 1
    assert access.jobs.get(lease.job_id)['model_calls'] == before['model_calls']
    assert access.jobs.get(lease.job_id)['execution_seconds'] == before['execution_seconds']


def test_invisible_uncertain_request_never_blindly_reposts(verified):
    access, lease, _, remote = verified
    calls = []
    def timeout(*args):
        calls.append(1)
        raise PublicationError('remote_timeout')
    remote.create_draft = timeout
    publisher = PublicationService(access, remote)
    assert publisher.publish(lease).outcome == 'retryable'
    assert publisher.publish(lease).reason == 'outcome_unknown'
    assert publisher.publish(lease).reason == 'outcome_unknown'
    assert len(calls) == 1 and remote.draft_count() == 0
    assert access.jobs.publication_intent(lease.job_id)['phase'] == 'pr_inflight'


def test_stale_base_after_remote_draft_acceptance_is_recorded_but_not_completed(verified):
    access, lease, _, remote = verified
    create = remote.create_draft
    def moved(*args):
        number = create(*args)
        remote.move_base('main', '0' * 40)
        return number
    remote.create_draft = moved
    blocked = PublicationService(access, remote).publish(lease)
    assert blocked.reason == 'base_moved' and remote.draft_count() == 1
    intent = access.jobs.publication_intent(lease.job_id)
    assert intent['stale'] and intent['pr_number'] == 1
    assert access.jobs.get(lease.job_id)['state'] == JobState.VERIFIED


def test_publication_failure_does_not_erase_verification(verified):
    access, lease, _, remote = verified
    def unavailable(*args): raise PublicationError('remote_unavailable')
    remote.create_branch = unavailable
    before = access.jobs.evidence(lease.job_id)
    result = PublicationService(access, remote).publish(lease)
    assert result.outcome == 'retryable' and access.jobs.evidence(lease.job_id) == before
    assert access.jobs.get(lease.job_id)['state'] == JobState.VERIFIED


def test_candidate_tampering_blocks_before_remote_calls(verified):
    from worker.source_common import Budget

    access, lease, proposal, remote = verified
    workspace = access.manager.reopen(lease.job_id, access.jobs.source_snapshot(lease.job_id), Budget(5))
    path = access.manager.path(workspace) / 'attempts' / proposal['attempt_id'] / 'pagination.py'
    path.write_text('unverified content')
    assert PublicationService(access, remote).publish(lease).outcome == 'blocked'
    assert access.jobs.publication_intent(lease.job_id) is None and remote.draft_count() == 0


def test_read_only_reconciliation_works_after_mutation_budget_exhausted(verified):
    access, lease, _, remote = verified
    with access.jobs.db.transaction() as connection:
        connection.execute('UPDATE jobs SET max_publication_attempts=1 WHERE id=?', (lease.job_id,))
    create = remote.create_draft
    def accepted(*args):
        create(*args)
        raise PublicationError('remote_timeout')
    remote.create_draft = accepted
    assert PublicationService(access, remote).publish(lease).outcome == 'retryable'
    assert PublicationService(access, remote).publish(lease).outcome == 'draft_pr_created'
    assert access.jobs.get(lease.job_id)['publication_attempts'] == 1 and remote.draft_count() == 1


def test_transaction_failure_after_remote_acceptance_is_reconciled(verified, monkeypatch):
    access, lease, _, remote = verified
    original = access.jobs._event
    def broken(connection, job, kind, data, now):
        if kind == 'draft_pr_recorded': raise RuntimeError('injected commit failure')
        return original(connection, job, kind, data, now)
    monkeypatch.setattr(access.jobs, '_event', broken)
    with pytest.raises(RuntimeError): PublicationService(access, remote).publish(lease)
    assert remote.draft_count() == 1 and access.jobs.get(lease.job_id)['state'] == JobState.PUBLISHING
    monkeypatch.setattr(access.jobs, '_event', original)
    assert PublicationService(access, remote).publish(lease).outcome == 'draft_pr_created'
    assert remote.draft_count() == 1


@pytest.mark.parametrize('accepted', [False, True])
def test_cancellation_during_publication_fences_completion(verified, accepted):
    access, lease, _, remote = verified
    original = remote.create_draft
    def cancel(*args):
        if accepted:
            original(*args)
        access.jobs.cancel(lease.job_id)
        remote.heartbeat()
    remote.create_draft = cancel
    outcome = PublicationService(access, remote).publish(lease)
    assert outcome.outcome == 'cancelled' and remote.draft_count() == int(accepted)
    assert access.jobs.get(lease.job_id)['state'] == JobState.CANCELLED
    assert access.jobs.publication(lease.job_id) is None
    assert any(item['kind'] == 'verification' for item in access.jobs.evidence(lease.job_id))


def test_pr_text_is_redacted_and_repository_mentions_are_escaped(verified):
    access, _, _, remote = verified
    service = PublicationService(access, remote)
    proof = {'summary': {'checks': {}}}
    body = service.body({'mode': 'offline', 'marker': '<!-- trusted -->', 'base_sha': 'a' * 40,
                         'patch_digest': 'b' * 64, 'evidence_digest': 'c' * 64}, proof,
                        {'diagnosis': 'secret=private @everyone <script>'},
                        {'node_id': 'test_fake', 'message': 'Bearer private @owner'})
    assert 'private' not in body and '@everyone' not in body and '@owner' not in body
    assert '<script>' not in body and '[REDACTED]' not in body  # Markdown escaped too.
    assert 'REDACTED' in body


def test_cancellation_during_remote_timeout_cannot_write_retry_metadata(verified):
    access, lease, _, remote = verified
    create = remote.create_draft
    def accepted(*args):
        create(*args)
        access.jobs.cancel(lease.job_id)
        raise PublicationError('remote_timeout')
    remote.create_draft = accepted
    result = PublicationService(access, remote).publish(lease)
    assert result.outcome == 'cancelled' and remote.draft_count() == 1
    assert access.jobs.get(lease.job_id)['state'] == JobState.CANCELLED
    assert access.jobs.publication_intent(lease.job_id)['last_error'] is None
