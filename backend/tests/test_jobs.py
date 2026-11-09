import json
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from backend.app.database import MIGRATIONS, Database
from backend.app.domain import (
    TERMINAL,
    TRANSITIONS,
    BudgetExceeded,
    Conflict,
    FailureReason,
    JobState,
    LeaseLost,
    NotFound,
    check_transition,
)
from backend.app.jobs import JobService, Lease
from backend.app.settings import Settings

SHA = "a" * 40
PATCH = "b" * 64
ARTIFACT = "c" * 64


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f"sqlite:///{tmp_path / 'jobs.sqlite'}",
                    allowed_repository="owner/repo", max_model_calls_per_job=2,
                    max_repair_attempts=2, max_publication_attempts=2)


@pytest.fixture
def service(settings, clock):
    return JobService(settings, clock)


def create(service, key="request-1"):
    return service.create(key, service.settings.allowed_repository, sha=SHA)


def baseline(service, exit_code=1):
    job = create(service)
    lease = service.claim("worker")
    service.advance(lease, JobState.BASELINING)
    service.record_source(lease, job['id'], 'b' * 64, 'c' * 64)
    service.add_evidence(lease, kind="baseline", artifact_digest=ARTIFACT,
                         exit_code=exit_code, summary={"result": "baseline"})
    return job, lease


def repairing(service):
    job, lease = baseline(service)
    prove_detection(service, lease)
    service.advance(lease, JobState.REPRODUCED)
    service.advance(lease, JobState.REPAIRING)
    proposed(service, lease)
    return job, lease


def prove_detection(service, lease, green=False):
    proofs = []
    for number in range(1 if green else 2):
        summary = {'run_id': str(number + 1) * 32, 'attempt_id': f'attempt-{number}',
                   'image_id': 'sha256:' + 'a' * 64, 'input_digest': 'b' * 64,
                   'profile_digest': 'c' * 64, 'report_valid': True, 'cleanup_complete': True,
                   'classification': 'no_reproducible_bug' if green else 'assertion_failure',
                   'assertions': [{'node_id': 'tests/test_x.py::test_x', 'signature': 'd' * 64}]}
        summary['test_nodes'] = ['tests/test_x.py::test_x']
        proofs.append(service.add_evidence(lease, kind='baseline', artifact_digest=ARTIFACT,
                                           exit_code=0 if green else 1, summary=summary))
    service.record_detection(lease, verdict='no_reproducible_bug' if green else 'reproduced',
                             artifact_digest=ARTIFACT, runs=proofs,
                             node_id=None if green else 'tests/test_x.py::test_x',
                             signature=None if green else 'd' * 64)


def verified(service):
    job, lease = repairing(service)
    service.advance(lease, JobState.VERIFYING)
    verified_round(service, lease)
    return job, lease


def proposed(service, lease):
    proof = service.reproduction(lease)
    number = service.get(lease.job_id)['repair_attempts']
    return service.record_candidate(lease, detection_id=proof['id'], attempt_id=f'{number:02d}-' + uuid.uuid4().hex,
        manifest_digest='b' * 64, profile_digest='c' * 64, patch_digest=PATCH, artifact_digest=ARTIFACT,
        provider='offline', diagnosis='fixture proposal', changed_files=['source.py'])


def verified_round(service, lease):
    from worker.check_policy import DISCRIMINATING_IDS, REGRESSION_IDS

    row = service.get(lease.job_id)
    candidate = next(item for item in service.candidates(lease.job_id) if item['repair_attempt'] == row['repair_attempts'])
    image = 'sha256:' + 'a' * 64
    identity = service.begin_verification(lease, candidate['id'], image)
    checks = {}
    for name in ('baseline_regression', 'original', 'suite', 'patched_regression'):
        control = name == 'baseline_regression'
        nodes = REGRESSION_IDS if 'regression' in name else ['tests/test_x.py::test_x']
        checks[name] = {'run_id': uuid.uuid4().hex, 'container_id': uuid.uuid4().hex * 2,
            'complete': True, 'cleanup_complete': True, 'skipped': 0, 'source_sha': SHA,
            'image_id': image, 'patch_digest': None if control else PATCH, 'command': ['python', '-m', 'pytest'],
            'exit_code': 1 if control else 0,
            'passed_nodes': sorted(set(nodes) - set(DISCRIMINATING_IDS)) if control else list(nodes),
            'failed_nodes': list(DISCRIMINATING_IDS) if control else []}
    service.finish_verification(lease, identity, verdict='verified', artifact_digest=ARTIFACT, checks=checks)


@pytest.mark.parametrize("old_version", [1, 2, 5, 6])
def test_migrations_upgrade_reopen_and_reject_future_schema(tmp_path, old_version):
    path = tmp_path / "upgrade.sqlite"
    db = Database.__new__(Database)
    db.path = path
    db.migrate(target=old_version)
    with db.transaction() as connection:
        columns = {r[1] for r in connection.execute("PRAGMA table_info(evidence)")}
        assert ("repair_attempt" in columns) == (old_version >= 2)
    upgraded = Database(path)
    with upgraded.transaction() as connection:
        assert [r[0] for r in connection.execute("SELECT version FROM schema_migrations")] == list(range(1, len(MIGRATIONS) + 1))
        assert "repair_attempt" in {r[1] for r in connection.execute("PRAGMA table_info(evidence)")}
        connection.execute("INSERT INTO schema_migrations VALUES (99, 0)")
    with pytest.raises(RuntimeError, match="Unsupported"):
        Database(path)


def test_migration_failure_rolls_back(tmp_path, monkeypatch):
    import backend.app.database as module

    db = Database.__new__(Database)
    db.path = tmp_path / "rollback.sqlite"
    db.migrate(target=1)
    monkeypatch.setattr(module, "MIGRATIONS", (MIGRATIONS[0], (
        "CREATE TABLE should_rollback (id INTEGER)", "INVALID SQL",
    )))
    with pytest.raises(sqlite3.OperationalError):
        db.migrate(target=2)
    with db.transaction() as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
        assert not connection.execute("SELECT name FROM sqlite_master WHERE name='should_rollback'").fetchall()


def test_reopen_preserves_job_events_and_limits(service, settings, clock):
    job, lease = repairing(service)
    service.reserve_usage(lease, model_calls=1, model_tokens=200, cost_micros=100)
    reopened = JobService(settings.model_copy(update={"max_model_calls_per_job": 100}), clock)
    row = reopened.get(job["id"])
    assert row["model_calls"] == 1
    assert row["max_model_calls"] == 2
    assert row["repair_attempts"] == 1
    assert row["deadline"] == job["deadline"]
    assert len(reopened.events(job["id"])) >= 6
    assert reopened.events(job["id"])[-1]["data"]["model_tokens"] == 200
    reopened.reserve_usage(lease, model_calls=1)
    before = reopened.get(job["id"])
    events = reopened.events(job["id"])
    with pytest.raises(BudgetExceeded):
        reopened.reserve_usage(lease, model_calls=1, model_tokens=100)
    assert reopened.get(job["id"]) == before
    assert reopened.events(job["id"]) == events


@pytest.mark.parametrize("current", list(JobState))
@pytest.mark.parametrize("target", list(JobState))
def test_entire_transition_graph(current, target):
    allowed = current not in TERMINAL and (
        target in TRANSITIONS.get(current, set()) or target in {JobState.FAILED, JobState.CANCELLED})
    if allowed:
        check_transition(current, target)
    else:
        with pytest.raises(Conflict):
            check_transition(current, target)


def test_state_evidence_requirements_and_pinning(service):
    job = service.create("unbound", "owner/repo")
    lease = service.claim("worker")
    with pytest.raises(Conflict):
        service.advance(lease, JobState.VERIFIED)
    service.advance(lease, JobState.BASELINING)
    with pytest.raises(Conflict):
        service.advance(lease, JobState.REPRODUCED)
    with pytest.raises(Conflict):
        service.add_evidence(lease, kind="baseline", artifact_digest=ARTIFACT, exit_code=1, summary={})
    service.pin_revision(lease, SHA)
    with pytest.raises(Conflict):
        service.pin_revision(lease, "d" * 40)
    service.add_evidence(lease, kind="baseline", artifact_digest=ARTIFACT, exit_code=2, summary={})
    with pytest.raises(Conflict):
        service.advance(lease, JobState.REPRODUCED)
    assert service.get(job["id"])["sha"] == SHA


def test_healthy_terminal_and_cancel_protection(service):
    job, lease = baseline(service, exit_code=0)
    prove_detection(service, lease, green=True)
    service.advance(lease, JobState.NO_REPRODUCIBLE_BUG)
    with pytest.raises(LeaseLost):
        service.advance(lease, JobState.REPAIRING)
    with pytest.raises(Conflict):
        service.cancel(job["id"])


@pytest.mark.parametrize("claimed", [False, True])
def test_cancellation_is_atomic_idempotent_and_fences_worker(service, claimed):
    job = create(service)
    lease = service.claim("worker") if claimed else None
    row = service.cancel(job["id"])
    assert row["state"] == JobState.CANCELLED
    assert row["cancellation_requested"] == 1
    assert row["cancelled_at"] is not None
    assert service.cancel(job["id"]) == row
    assert service.claim("other") is None
    if lease:
        with pytest.raises(LeaseLost):
            service.advance(lease, JobState.BASELINING)
        with pytest.raises(LeaseLost):
            service.renew(lease)


def test_idempotency_payload_conflict_and_pagination(service):
    first = create(service)
    assert create(service) == first
    with pytest.raises(Conflict):
        service.create("request-1", "owner/repo", ref="different", sha=SHA)
    second = create(service, "request-2")
    page = service.list_jobs(limit=1)
    cursor = (page[0]["created_at"], page[0]["id"])
    rest = service.list_jobs(limit=1, after=cursor)
    assert {page[0]["id"], rest[0]["id"]} == {first["id"], second["id"]}
    assert not service.list_jobs(after=(rest[0]["created_at"], rest[0]["id"]))
    lease = service.claim("worker")
    all_events = service.events(lease.job_id)
    one = service.events(lease.job_id, limit=1)
    two = service.events(lease.job_id, after=one[0]["sequence"])
    assert one + two == all_events
    assert [e["sequence"] for e in all_events] == list(range(1, len(all_events) + 1))


def test_concurrent_duplicate_creates_use_distinct_connections(settings, clock):
    services = [JobService(settings, clock) for _ in range(6)]
    barrier = Barrier(len(services))

    def submit(service):
        barrier.wait()
        return create(service)["id"]

    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(submit, services))
    assert len(set(ids)) == 1
    assert len(services[0].list_jobs()) == 1
    assert len(services[0].events(ids[0])) == 1


def test_concurrent_conflicting_payloads(settings, clock):
    services = [JobService(settings, clock) for _ in range(2)]
    barrier = Barrier(2)

    def submit(index):
        barrier.wait()
        try:
            return services[index].create("same-key", "owner/repo", ref=f"branch-{index}")["id"]
        except Conflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert results.count("conflict") == 1
    assert len(services[0].list_jobs()) == 1


def test_competing_claims_expiry_renewal_release_and_fencing(settings, clock):
    first, second = JobService(settings, clock), JobService(settings, clock)
    job = create(first)
    barrier = Barrier(2)

    def claim(index):
        barrier.wait()
        return (first, second)[index].claim(f"worker-{index}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(claim, range(2)))
    assert sum(lease is not None for lease in claims) == 1
    original = next(lease for lease in claims if lease)
    clock.now += 10
    renewal = first.renew(original)
    assert renewal["lease_expires_at"] == clock.now + settings.lease_seconds
    clock.now = renewal["lease_expires_at"]
    with pytest.raises(LeaseLost):
        first.renew(original)
    replacement = second.claim(original.owner)  # Same owner still needs a NEW fence.
    assert replacement.fence > original.fence
    assert replacement.job_id == job["id"]
    for mutate in (lambda: first.release(original),
                   lambda: first.advance(original, JobState.BASELINING),
                   lambda: first.reserve_usage(original, execution_seconds=1)):
        with pytest.raises(LeaseLost):
            mutate()
    second.release(replacement)
    with pytest.raises(LeaseLost):
        second.renew(replacement)
    newest = first.claim("worker-new")
    assert newest.fence > replacement.fence


def test_deadline_and_claim_retry_exhaustion(settings, clock):
    service = JobService(settings.model_copy(update={"max_lease_claims": 1}), clock)
    job = create(service)
    lease = service.claim("worker")
    clock.now += settings.lease_seconds
    assert service.claim("other") is None
    assert service.get(job["id"])["failure_reason"] == FailureReason.RETRIES
    with pytest.raises(LeaseLost):
        service.release(lease)
    job2 = create(service, "deadline")
    clock.now = job2["deadline"]
    assert service.expire() == 1
    assert service.get(job2["id"])["failure_reason"] == FailureReason.DEADLINE
    assert service.expire() == 0


def test_deadline_blocks_owned_mutations_before_reaper(service, clock):
    job = create(service)
    lease = service.claim("worker")
    clock.now = job["deadline"]
    with pytest.raises(LeaseLost):
        service.advance(lease, JobState.BASELINING)
    assert service.expire() == 1


def test_transaction_failure_rolls_back_job_event_and_usage(service, monkeypatch):
    original = service._event

    def fail(*args):
        raise RuntimeError("injected event storage failure")

    monkeypatch.setattr(service, "_event", fail)
    with pytest.raises(RuntimeError):
        create(service)
    assert service.list_jobs() == []
    monkeypatch.setattr(service, "_event", original)
    job, lease = repairing(service)
    before = service.get(job["id"])
    monkeypatch.setattr(service, "_event", fail)
    with pytest.raises(RuntimeError):
        service.reserve_usage(lease, model_calls=1)
    assert service.get(job["id"]) == before


def test_version_guard_and_failure_reason(service):
    job = create(service)
    lease = service.claim("worker")
    with pytest.raises(Conflict, match="version"):
        service.advance(lease, JobState.BASELINING, expected_version=job["version"])
    with pytest.raises(ValueError):
        service.advance(lease, JobState.FAILED)
    result = service.advance(lease, JobState.FAILED, failure_reason=FailureReason.ENVIRONMENT)
    assert result["failure_reason"] == "environment"
    with pytest.raises(LeaseLost):
        service.advance(lease, JobState.BASELINING)


def test_repair_retry_limit_and_old_verification_cannot_be_reused(service):
    job, lease = repairing(service)
    service.advance(lease, JobState.VERIFYING)
    service.add_evidence(lease, kind="verification", artifact_digest=ARTIFACT,
                         patch_digest=PATCH, exit_code=0, summary={})
    service.advance(lease, JobState.REPAIRING)
    proposed(service, lease)
    service.advance(lease, JobState.VERIFYING)
    with pytest.raises(Conflict, match="evidence"):
        service.advance(lease, JobState.VERIFIED)
    with pytest.raises(BudgetExceeded):
        service.advance(lease, JobState.REPAIRING)
    # Identical artifacts can legitimately recur on a new attempt, but need a NEW record.
    service.add_evidence(lease, kind="verification", artifact_digest=ARTIFACT,
                         patch_digest=PATCH, exit_code=0, summary={})
    with pytest.raises(Conflict):
        service.advance(lease, JobState.VERIFIED)
    verified_round(service, lease)
    assert service.get(job["id"])["repair_attempts"] == 2


def test_publication_metadata_bound_to_verified_patch_and_retries(service, settings, clock):
    job, lease = verified(service)
    intent = service.prepare_publication(lease, base_ref='main', mode='live')
    branch = intent['branch']
    assert service.get(job["id"])["state"] != JobState.DRAFT_PR_CREATED
    with pytest.raises(Conflict):
        service.set_publication(lease, branch)
    service.advance(lease, JobState.PUBLISHING)
    with pytest.raises(Conflict):
        service.advance(lease, JobState.DRAFT_PR_CREATED)
    service.set_publication(lease, branch)
    service.advance(lease, JobState.VERIFIED)  # Failed publication keeps verified evidence.
    service.advance(lease, JobState.PUBLISHING)
    with pytest.raises(ValueError):
        service.set_publication(lease, branch, pr_number=1, draft=False)
    record = service.set_publication(lease, branch, pr_number=17)
    assert record["url"] == "https://github.com/owner/repo/pull/17"
    assert record["patch_digest"] == PATCH
    with pytest.raises(Conflict):
        service.set_publication(lease, "webguard/other", pr_number=17)
    with pytest.raises(Conflict):
        service.advance(lease, JobState.DRAFT_PR_CREATED)  # Legacy metadata is not reconciled publication proof.
    service.note_publication(lease, phase='branch_ready', commit_sha='d' * 40)
    service.finish_publication(lease, commit_sha='d' * 40, pr_number=17)
    reopened = JobService(settings, clock)
    assert reopened.publication(job["id"])["pr_number"] == 17
    assert reopened.evidence(job["id"])[-1]["patch_digest"] == PATCH
    with pytest.raises(Conflict):
        reopened.cancel(job["id"])


def test_publication_retries_are_bounded(service):
    job, lease = verified(service)
    for _ in range(2):
        service.advance(lease, JobState.PUBLISHING)
        service.advance(lease, JobState.VERIFIED)
    with pytest.raises(BudgetExceeded):
        service.advance(lease, JobState.PUBLISHING)
    assert service.get(job["id"])["publication_attempts"] == 2


def test_all_usage_limits_are_persistent_and_no_negative_refunds(service):
    job, lease = repairing(service)
    for field in ("model_tokens", "cost_micros"):
        limit = service.get(job["id"])["max_" + field]
        service.reserve_usage(lease, **{field: limit})
        with pytest.raises(BudgetExceeded):
            service.reserve_usage(lease, **{field: 1})
    for value in (-1, True, 0.5):
        with pytest.raises(ValueError):
            service.reserve_usage(lease, model_calls=value)
    with pytest.raises(Conflict):
        service.reserve_usage(lease, execution_seconds=1)
    service.advance(lease, JobState.VERIFYING)
    service.reserve_usage(lease, execution_seconds=service.get(job["id"])["max_execution_seconds"])
    with pytest.raises(BudgetExceeded):
        service.reserve_usage(lease, execution_seconds=1)


def test_concurrent_usage_cannot_exceed_budget(settings, clock):
    service = JobService(settings, clock)
    job, lease = repairing(service)
    services = [JobService(settings, clock) for _ in range(6)]
    barrier = Barrier(6)

    def reserve(other):
        barrier.wait()
        try:
            other.reserve_usage(lease, model_calls=1)
            return True
        except BudgetExceeded:
            return False

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(reserve, services))
    assert sum(results) == 2
    assert service.get(job["id"])["model_calls"] == 2


def test_credentials_never_persist_in_events_evidence_or_identifiers(settings, clock):
    secret = "sensitive-private-key-1234567890"
    configured = Settings(**{**settings.model_dump(), "gemini_api_key": secret})
    service = JobService(configured, clock)
    job, lease = baseline(service)
    service.add_evidence(lease, kind="baseline", artifact_digest="d" * 64, exit_code=1,
                         summary={"nested": [{"message": secret}], "token": "also-secret"})
    evidence = service.evidence(job["id"])
    assert secret not in json.dumps(evidence)
    with pytest.raises(ValueError, match="Sensitive"):
        service.create("reject", "owner/repo", ref=secret)
    with service.db.transaction() as connection:
        dump = "\n".join(connection.iterdump())
    assert secret not in dump
    assert "also-secret" not in dump
    assert secret.encode() not in settings.database_path.read_bytes()


@pytest.mark.parametrize("ref", ["../outside", "https://host/repo", "a//b", "a.lock", "a\nsecret"])
def test_untrusted_refs_are_rejected(service, ref):
    with pytest.raises(ValueError):
        service.create("key", "owner/repo", ref=ref)


def test_validation_and_not_found(service):
    with pytest.raises(ValueError):
        service.create("key", "attacker/repo")
    with pytest.raises(ValueError):
        service.create("key", "owner/repo", sha="short")
    with pytest.raises(NotFound):
        service.get("missing")
    with pytest.raises(NotFound):
        service.events("missing")
    with pytest.raises(ValueError):
        service.list_jobs(limit=101)
    with pytest.raises(ValueError):
        service.events("missing", after=-1)
    with pytest.raises(LeaseLost):
        job = create(service)
        service.renew(Lease(job["id"], "invented-owner", 1))


def test_upgrade_preserves_existing_jobs_events_and_evidence(tmp_path, settings, clock):
    source = JobService(settings, clock)
    job, lease = baseline(source)
    # Populate an actual version-1 database, then reopen with the current migrations.
    db = Database.__new__(Database)
    db.path = tmp_path / "old.sqlite"
    db.migrate(target=1)
    row = source.get(job["id"])
    with db.transaction() as connection:
        columns = ",".join(row)
        placeholders = ",".join("?" for _ in row)
        connection.execute(f"INSERT INTO jobs ({columns}) VALUES ({placeholders})", tuple(row.values()))
        connection.execute("INSERT INTO events VALUES (?, 1, 1000, 'created', '{}')", (job["id"],))
        connection.execute("INSERT INTO evidence VALUES ('old-proof', ?, 1000, 'baseline', ?, NULL, ?, 1, '{}')",
                           (job["id"], SHA, ARTIFACT))
    reopened = JobService(settings.model_copy(update={"database_url": f"sqlite:///{db.path}"}), clock)
    assert reopened.get(job["id"]) == row
    assert reopened.events(job["id"])[0]["kind"] == "created"
    assert reopened.evidence(job["id"])[0]["repair_attempt"] == 0
    with pytest.raises(Conflict, match='detection'):
        reopened.advance(lease, JobState.REPRODUCED)  # Legacy exit-only proof is insufficient.


def test_cancel_and_claim_race_cannot_leave_live_lease(settings, clock):
    services = [JobService(settings, clock) for _ in range(2)]
    job = create(services[0])
    barrier = Barrier(2)

    def claim():
        barrier.wait()
        return services[0].claim("worker")

    def cancel():
        barrier.wait()
        return services[1].cancel(job["id"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        claim_future = pool.submit(claim)
        cancel_future = pool.submit(cancel)
        lease = claim_future.result()
        cancel_future.result()
    assert services[0].get(job["id"])["lease_owner"] is None
    assert services[0].get(job["id"])["state"] == JobState.CANCELLED
    if lease:
        with pytest.raises(LeaseLost):
            services[0].reserve_usage(lease, model_calls=1)


def test_evidence_and_publication_transactions_rollback(service, monkeypatch):
    job, lease = repairing(service)
    service.advance(lease, JobState.VERIFYING)
    original = service._event
    before = service.get(job["id"])

    def fail(*args):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(service, "_event", fail)
    with pytest.raises(RuntimeError):
        service.add_evidence(lease, kind="verification", artifact_digest=ARTIFACT,
                             patch_digest=PATCH, exit_code=0, summary={})
    assert all(item['kind'] != 'verification' for item in service.evidence(job['id']))
    assert service.get(job["id"]) == before
    monkeypatch.setattr(service, "_event", original)
    service.add_evidence(lease, kind="verification", artifact_digest=ARTIFACT,
                         patch_digest=PATCH, exit_code=0, summary={})
    verified_round(service, lease)
    service.advance(lease, JobState.PUBLISHING)
    before = service.get(job["id"])
    monkeypatch.setattr(service, "_event", fail)
    with pytest.raises(RuntimeError):
        service.set_publication(lease, "webguard/repair", pr_number=1)
    assert service.publication(job["id"]) is None
    assert service.get(job["id"]) == before


def test_all_evidence_and_publication_writes_require_current_fence(service, clock):
    job, lease = verified(service)
    service.advance(lease, JobState.PUBLISHING)
    clock.now += service.settings.lease_seconds
    replacement = service.claim("new-owner")
    assert replacement.job_id == job["id"]
    for mutate in (
        lambda: service.set_publication(lease, "webguard/repair", pr_number=1),
        lambda: service.add_evidence(lease, kind="verification", artifact_digest=ARTIFACT,
                                    patch_digest=PATCH, exit_code=0, summary={}),
        lambda: service.pin_revision(lease, SHA),
    ):
        with pytest.raises(LeaseLost):
            mutate()


def test_sensitive_digest_and_oversized_metadata_never_written(settings, clock):
    secret = "e" * 64
    service = JobService(Settings(**{**settings.model_dump(), "gemini_api_key": secret}), clock)
    job, lease = baseline(service)
    before = service.evidence(job["id"])
    with pytest.raises(ValueError, match="Sensitive"):
        service.add_evidence(lease, kind="baseline", artifact_digest=secret, exit_code=1, summary={})
    with pytest.raises(ValueError, match="limit"):
        service.add_evidence(lease, kind="baseline", artifact_digest=ARTIFACT, exit_code=1,
                             summary={"message": "x" * 17000})
    assert service.evidence(job["id"]) == before


def test_changed_repository_approval_does_not_claim_old_jobs(service, settings, clock):
    create(service)
    lease = service.claim("original-owner")
    other = JobService(settings.model_copy(update={"allowed_repository": "other/repo"}), clock)
    assert other.claim("worker") is None
    with pytest.raises(LeaseLost):
        other.renew(lease)
    with pytest.raises(LeaseLost):
        other.advance(lease, JobState.BASELINING)
