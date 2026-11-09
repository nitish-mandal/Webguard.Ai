"""Durable controller services only. No target execution or external API calls."""

import hashlib
import json
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from backend.app.database import Database
from backend.app.domain import (
    TERMINAL,
    BudgetExceeded,
    Conflict,
    FailureReason,
    JobState,
    LeaseLost,
    NotFound,
    check_transition,
)
from backend.app.settings import Settings


@dataclass(frozen=True)
class Lease:
    job_id: str
    owner: str
    fence: int


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _hash(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Expected lowercase SHA256 digest")
    return value


def _revision(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value):
        raise ValueError("Expected full lowercase commit SHA")
    return value


def _ref(value: str) -> str:
    if (not isinstance(value, str) or len(value) > 200
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*", value)
            or any(part.startswith(".") or part.endswith((".", ".lock"))
                   for part in value.split("/"))
            or ".." in value or "//" in value or value.endswith("/")):
        raise ValueError("Invalid Git ref")
    return value


class JobService:
    def __init__(self, settings: Settings, clock: Callable[[], float] = time.time):
        self.settings = settings
        self.redactor = settings.redactor()
        self.db = Database(settings.database_path)
        self.clock = clock

    def _safe_identifier(self, value: str) -> str:
        if self.redactor.text(value) != value:
            raise ValueError("Sensitive identifier rejected")
        return value

    def _json(self, value: dict) -> str:
        if not isinstance(value, dict):
            raise TypeError("Metadata must be an object")
        try:
            result = json.dumps(self.redactor.clean(value), sort_keys=True, allow_nan=False)
        except (ValueError, TypeError, RecursionError):
            raise ValueError("Invalid metadata") from None
        if len(result.encode()) > 16384:
            raise ValueError("Metadata exceeds storage limit")
        return result

    def _event(self, connection, job_id, kind, data, now):
        sequence = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0)+1 FROM events WHERE job_id=?", (job_id,)
        ).fetchone()[0]
        connection.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?)",
                           (job_id, sequence, now, kind, self._json(data)))

    @staticmethod
    def _row(connection, job_id) -> dict:
        row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise NotFound("Job not found")
        return dict(row)

    def _owned(self, connection, lease: Lease, now: float) -> dict:
        row = self._row(connection, lease.job_id)
        if (row["repository"] != self.settings.allowed_repository
                or row["state"] in TERMINAL or row["lease_owner"] != lease.owner
                or row["fence"] != lease.fence or row["lease_expires_at"] is None
                or row["lease_expires_at"] <= now or row["deadline"] <= now):
            raise LeaseLost("Lease expired, superseded, cancelled or job deadline reached")
        return row

    def create(self, idempotency_key: str, repository: str, ref: str = "main",
               sha: str | None = None) -> dict:
        if (not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 200
                or any(ord(char) < 33 or ord(char) > 126 for char in idempotency_key)):
            raise ValueError("Invalid idempotency key")
        if repository != self.settings.allowed_repository:
            raise ValueError("Repository is not approved")
        self._safe_identifier(repository)
        self._safe_identifier(_ref(ref))
        if sha is not None:
            self._safe_identifier(_revision(sha))
        payload_hash = _digest(json.dumps([repository, ref, sha], separators=(",", ":")))
        with self.db.transaction() as connection:
            existing = connection.execute("SELECT * FROM jobs WHERE idempotency_hash=?",
                                          (_digest(idempotency_key),)).fetchone()
            if existing:
                if existing["payload_hash"] != payload_hash:
                    raise Conflict("Idempotency key already used for different input")
                return dict(existing)
            now = self.clock()
            row = {
                "id": uuid.uuid4().hex, "idempotency_hash": _digest(idempotency_key),
                "payload_hash": payload_hash, "repository": repository, "ref": ref, "sha": sha,
                "state": JobState.QUEUED, "created_at": now, "updated_at": now,
                "deadline": now + self.settings.job_timeout_seconds,
                "max_repair_attempts": self.settings.max_repair_attempts,
                "max_publication_attempts": self.settings.max_publication_attempts,
                "max_lease_claims": self.settings.max_lease_claims,
                "max_model_calls": self.settings.max_model_calls_per_job,
                "max_model_tokens": self.settings.max_model_tokens_per_job,
                "max_cost_micros": self.settings.max_cost_micros_per_job,
                "max_execution_seconds": self.settings.max_execution_seconds,
                "max_output_bytes": self.settings.max_output_bytes,
                "max_patch_files": self.settings.max_patch_files,
                "max_patch_lines": self.settings.max_patch_lines,
            }
            columns = ",".join(row)
            placeholders = ",".join("?" for _ in row)
            connection.execute(f"INSERT INTO jobs ({columns}) VALUES ({placeholders})",
                               tuple(row.values()))
            self._event(connection, row["id"], "created", {"state": JobState.QUEUED}, now)
            return self._row(connection, row["id"])

    def get(self, job_id: str) -> dict:
        connection = self.db.connect()
        try:
            return self._row(connection, job_id)
        finally:
            connection.close()

    @staticmethod
    def _page(limit: int) -> None:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Page limit must be between 1 and 100")

    def list_jobs(self, limit: int = 50, after: tuple[float, str] | None = None, *, descending=False) -> list[dict]:
        self._page(limit)
        connection = self.db.connect()
        try:
            order = 'DESC' if descending else 'ASC'
            comparison = '<' if descending else '>'
            if after is None:
                rows = connection.execute(f"SELECT * FROM jobs ORDER BY created_at {order},id {order} LIMIT ?",
                                          (limit,))
            else:
                rows = connection.execute(f"SELECT * FROM jobs WHERE (created_at,id){comparison}(?,?) "
                                          f"ORDER BY created_at {order},id {order} LIMIT ?", (*after, limit))
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def events(self, job_id: str, after: int = 0, limit: int = 50) -> list[dict]:
        self._page(limit)
        if type(after) is not int or after < 0:
            raise ValueError("Invalid event cursor")
        connection = self.db.connect()
        try:
            self._row(connection, job_id)
            rows = connection.execute("SELECT * FROM events WHERE job_id=? AND sequence>? "
                                      "ORDER BY sequence LIMIT ?", (job_id, after, limit))
            return [{**dict(row), "data": json.loads(row["data"])} for row in rows]
        finally:
            connection.close()

    def _finish(self, connection, row, target, now, reason=None):
        check_transition(JobState(row["state"]), target)
        connection.execute("UPDATE jobs SET state=?,failure_reason=?,updated_at=?,"
                           "lease_owner=NULL,lease_expires_at=NULL,fence=fence+1,"
                           "version=version+1 WHERE id=?", (target, reason, now, row["id"]))
        connection.execute("UPDATE verification_rounds SET status='failed',finished_at=?,reason=? "
                           "WHERE job_id=? AND status='running'",
                           (now, str(reason or target), row['id']))
        self._event(connection, row["id"], "state_changed",
                    {"from": row["state"], "to": target, "reason": reason}, now)

    def cancel(self, job_id: str) -> dict:
        with self.db.transaction() as connection:
            row = self._row(connection, job_id)
            if row["state"] == JobState.CANCELLED:
                return row
            now = self.clock()
            self._finish(connection, row, JobState.CANCELLED, now)
            connection.execute("UPDATE jobs SET cancellation_requested=1,cancelled_at=? WHERE id=?",
                               (now, job_id))
            return self._row(connection, job_id)

    def _expire(self, connection, now) -> int:
        rows = connection.execute("SELECT * FROM jobs ORDER BY created_at,id").fetchall()
        count = 0
        for record in rows:
            row = dict(record)
            if row["state"] in TERMINAL:
                continue
            reason = None
            if row["deadline"] <= now:
                reason = FailureReason.DEADLINE
            elif ((row["lease_expires_at"] is None or row["lease_expires_at"] <= now)
                  and row["claims"] >= row["max_lease_claims"]):
                reason = FailureReason.RETRIES
            if reason:
                self._finish(connection, row, JobState.FAILED, now, reason)
                count += 1
        return count

    def expire(self) -> int:
        with self.db.transaction() as connection:
            return self._expire(connection, self.clock())

    def claim(self, owner: str) -> Lease | None:
        if not isinstance(owner, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", owner):
            raise ValueError("Invalid worker identifier")
        self._safe_identifier(owner)
        with self.db.transaction() as connection:
            now = self.clock()
            self._expire(connection, now)
            stopped = connection.execute('SELECT stop_requested,stopped FROM worker_sessions WHERE owner=?', (owner,)).fetchone()
            if stopped and (stopped['stop_requested'] or stopped['stopped']):
                return None
            placeholders = ",".join("?" for _ in TERMINAL)
            record = connection.execute(
                f"SELECT * FROM jobs WHERE state NOT IN ({placeholders}) AND repository=? "
                "AND (lease_expires_at IS NULL OR lease_expires_at<=?) "
                "AND NOT EXISTS (SELECT 1 FROM job_dispatch d WHERE d.job_id=jobs.id "
                "AND (d.paused=1 OR d.next_run_at>?)) "
                "ORDER BY created_at,id LIMIT 1",
                (*TERMINAL, self.settings.allowed_repository, now, now),
            ).fetchone()
            if record is None:
                return None
            row = dict(record)
            fence = row["fence"] + 1
            expires = min(now + self.settings.lease_seconds, row["deadline"])
            connection.execute("UPDATE jobs SET lease_owner=?,lease_expires_at=?,fence=?,"
                               "claims=claims+1,version=version+1,updated_at=? WHERE id=?",
                               (owner, expires, fence, now, row["id"]))
            self._event(connection, row["id"], "lease_claimed",
                        {"owner": owner, "fence": fence, "reclaimed": row["claims"] > 0}, now)
            return Lease(row["id"], owner, fence)

    def dispatch(self, job_id):
        with self.db.transaction() as connection:
            self._row(connection, job_id)
            row = connection.execute('SELECT * FROM job_dispatch WHERE job_id=?', (job_id,)).fetchone()
            return dict(row) if row else None

    def worker_stage(self, lease, stage):
        if stage not in ('source', 'reproduction', 'repair', 'verification', 'publication'):
            raise ValueError('Invalid worker stage')
        with self.db.transaction() as connection:
            now = self.clock()
            self._owned(connection, lease, now)
            connection.execute('INSERT INTO job_dispatch(job_id,stage) VALUES (?,?) '
                               'ON CONFLICT(job_id) DO UPDATE SET stage=excluded.stage,reason=NULL',
                               (lease.job_id, stage))
            self._event(connection, lease.job_id, 'worker_stage', {'stage': stage}, now)

    def defer(self, lease, reason, *, paused=False):
        # Controller-owned codes, never exception strings/source/model text.
        if reason not in ('docker_unavailable', 'verification_blocked', 'publication_retry',
                           'publication_blocked', 'source_unavailable', 'controller_error', 'shutdown'):
            raise ValueError('Invalid retry reason')
        with self.db.transaction() as connection:
            now = self.clock()
            self._owned(connection, lease, now)
            due = now + self.settings.worker_retry_seconds
            connection.execute('INSERT INTO job_dispatch(job_id,next_run_at,paused,reason) VALUES (?,?,?,?) '
                'ON CONFLICT(job_id) DO UPDATE SET next_run_at=excluded.next_run_at,paused=excluded.paused,reason=excluded.reason',
                (lease.job_id, due, int(paused), reason))
            connection.execute('UPDATE jobs SET lease_owner=NULL,lease_expires_at=NULL,fence=fence+1,'
                               'version=version+1,updated_at=? WHERE id=?', (now, lease.job_id))
            self._event(connection, lease.job_id, 'worker_deferred',
                        {'reason': reason, 'paused': bool(paused), 'next_run_at': due}, now)

    def worker_session(self, owner, *, start=False, stopped=False):
        if not re.fullmatch(r'[0-9a-f]{32}', owner):
            raise ValueError('Invalid worker ID')
        with self.db.transaction() as connection:
            now = self.clock()
            if start:
                connection.execute('INSERT INTO worker_sessions VALUES (?,?,?,?,0,0,?)',
                                   (owner, now, now, now + 15, self.settings.allowed_repository))
            connection.execute('UPDATE worker_sessions SET heartbeat_at=?,expires_at=?,stopped=MAX(stopped,?) WHERE owner=?',
                               (now, now + 15, int(stopped), owner))
            row = connection.execute('SELECT * FROM worker_sessions WHERE owner=?', (owner,)).fetchone()
            return dict(row) if row else None

    def stop_worker(self, owner):
        if not re.fullmatch(r'[0-9a-f]{32}', owner):
            raise ValueError('Invalid worker ID')
        with self.db.transaction() as connection:
            row = connection.execute('SELECT * FROM worker_sessions WHERE owner=?', (owner,)).fetchone()
            if row is None:
                raise NotFound('Worker not found')
            connection.execute('UPDATE worker_sessions SET stop_requested=1 WHERE owner=?', (owner,))
            return dict(row)

    def worker_available(self):
        with self.db.transaction() as connection:
            return connection.execute('SELECT 1 FROM worker_sessions WHERE stopped=0 AND stop_requested=0 '
                                      'AND expires_at>? AND repository=? LIMIT 1',
                                      (self.clock(), self.settings.allowed_repository)).fetchone() is not None

    def resume_dispatch(self, job_id):
        with self.db.transaction() as connection:
            row = self._row(connection, job_id)
            if row['state'] in TERMINAL or (row['lease_expires_at'] and row['lease_expires_at'] > self.clock()):
                raise Conflict('Job cannot be resumed')
            connection.execute('UPDATE job_dispatch SET paused=0,next_run_at=0,reason=NULL WHERE job_id=?', (job_id,))
            self._event(connection, job_id, 'worker_resumed', {}, self.clock())

    def terminal_reconciliation(self, job_id=None):
        """Reserve bounded read-only reconciliation; never revive a terminal job."""
        with self.db.transaction() as connection:
            now = self.clock()
            row = connection.execute("SELECT j.id FROM jobs j JOIN publication_intents p ON p.job_id=j.id "
                "LEFT JOIN job_dispatch d ON d.job_id=j.id WHERE j.state IN ('cancelled','failed') AND p.phase!='completed' "
                "AND p.repository=? AND COALESCE(d.reconciliations,0)<3 AND COALESCE(d.reconcile_after,0)<=? "
                "AND (? IS NULL OR j.id=?) ORDER BY j.created_at,j.id LIMIT 1",
                (self.settings.allowed_repository, now, job_id, job_id)).fetchone()
            if row is None:
                return None
            connection.execute('INSERT INTO job_dispatch(job_id,reconciliations,reconcile_after) VALUES (?,1,?) '
                'ON CONFLICT(job_id) DO UPDATE SET reconciliations=reconciliations+1,reconcile_after=excluded.reconcile_after',
                (row['id'], now + self.settings.worker_retry_seconds))
            return row['id']

    def record_interrupted_draft(self, job_id, *, marker, commit_sha, pr_number, observation=None):
        if observation not in (None, 'outcome_unknown'):
            raise ValueError('Invalid reconciliation observation')
        with self.db.transaction() as connection:
            row = self._row(connection, job_id)
            intent = connection.execute('SELECT * FROM publication_intents WHERE job_id=?', (job_id,)).fetchone()
            if (row['state'] not in (JobState.CANCELLED, JobState.FAILED) or not intent or intent['marker'] != marker
                    or intent['commit_sha'] != commit_sha or (pr_number is not None and
                    (type(pr_number) is not int or pr_number < 1))):
                raise Conflict('Cancelled publication identity mismatch')
            if intent['pr_number'] and pr_number is not None and intent['pr_number'] != pr_number:
                raise Conflict('Observed publication changed')
            pr_number = pr_number or intent['pr_number']
            url = (f'simulated://webguard/{job_id}/pull/{pr_number}' if intent['mode'] == 'offline'
                   else f"https://github.com/{intent['repository']}/pull/{pr_number}") if pr_number else None
            connection.execute('UPDATE publication_intents SET pr_number=COALESCE(?,pr_number),'
                               'pr_url=COALESCE(?,pr_url) WHERE job_id=?', (pr_number, url, job_id))
            self._event(connection, job_id, 'terminal_publication_reconciled',
                        {'pr_number': pr_number, 'url': url, 'simulated': intent['mode'] == 'offline',
                         'observation': observation or ('draft_exists' if pr_number else 'not_observed')}, self.clock())

    def renew(self, lease: Lease) -> dict:
        with self.db.transaction() as connection:
            now = self.clock()
            row = self._owned(connection, lease, now)
            connection.execute("UPDATE jobs SET lease_expires_at=?,updated_at=?,version=version+1 "
                               "WHERE id=?", (min(now + self.settings.lease_seconds, row["deadline"]),
                                              now, lease.job_id))
            return self._row(connection, lease.job_id)

    def release(self, lease: Lease) -> None:
        with self.db.transaction() as connection:
            now = self.clock()
            self._owned(connection, lease, now)
            connection.execute("UPDATE jobs SET lease_owner=NULL,lease_expires_at=NULL,"
                               "fence=fence+1,version=version+1,updated_at=? WHERE id=?",
                               (now, lease.job_id))
            self._event(connection, lease.job_id, "lease_released", {}, now)

    def pin_revision(self, lease: Lease, sha: str) -> dict:
        self._safe_identifier(_revision(sha))
        with self.db.transaction() as connection:
            now = self.clock()
            row = self._owned(connection, lease, now)
            if row["state"] != JobState.BASELINING or row["sha"] not in (None, sha):
                raise Conflict("Baseline revision is immutable once pinned")
            connection.execute("UPDATE jobs SET sha=?,updated_at=?,version=version+1 WHERE id=?",
                               (sha, now, lease.job_id))
            self._event(connection, lease.job_id, "revision_pinned", {"sha": sha}, now)
            return self._row(connection, lease.job_id)

    def check_lease(self, lease: Lease) -> dict:
        with self.db.transaction() as connection:
            return self._owned(connection, lease, self.clock())

    def source_snapshot(self, job_id: str) -> dict | None:
        connection = self.db.connect()
        try:
            self._row(connection, job_id)
            row = connection.execute("SELECT * FROM source_snapshots WHERE job_id=?",
                                     (job_id,)).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def record_source(self, lease: Lease, workspace_id: str, manifest_digest: str,
                      profile_digest: str) -> dict:
        if not re.fullmatch(r"[0-9a-f]{32}", workspace_id):
            raise ValueError("Invalid workspace identity")
        for value in (workspace_id, _hash(manifest_digest), _hash(profile_digest)):
            self._safe_identifier(value)
        with self.db.transaction() as connection:
            now = self.clock()
            row = self._owned(connection, lease, now)
            if row["state"] != JobState.BASELINING or row["sha"] is None:
                raise Conflict("Source snapshot requires a pinned baselining job")
            if connection.execute("SELECT 1 FROM source_snapshots WHERE job_id=?",
                                  (lease.job_id,)).fetchone():
                raise Conflict("Source snapshot is immutable")
            connection.execute("INSERT INTO source_snapshots VALUES (?, ?, ?, ?, ?, ?)",
                               (lease.job_id, workspace_id, row["sha"], manifest_digest,
                                profile_digest, now))
            connection.execute("UPDATE jobs SET version=version+1,updated_at=? WHERE id=?",
                               (now, lease.job_id))
            self._event(connection, lease.job_id, "source_acquired", {
                "sha": row["sha"], "workspace_id": workspace_id,
                "manifest_digest": manifest_digest, "profile_digest": profile_digest,
            }, now)
            return dict(connection.execute("SELECT * FROM source_snapshots WHERE job_id=?",
                                           (lease.job_id,)).fetchone())

    def advance(self, lease: Lease, target: JobState, *, expected_version: int | None = None,
                failure_reason: FailureReason | None = None) -> dict:
        try:
            target = JobState(target)
            if failure_reason is not None:
                failure_reason = FailureReason(failure_reason)
        except ValueError:
            raise ValueError("Unknown job state or failure reason") from None
        if target == JobState.CANCELLED:
            raise Conflict("Use the cancellation service")
        if (target == JobState.FAILED) != (failure_reason is not None):
            raise ValueError("Only a failed transition requires a typed failure reason")
        with self.db.transaction() as connection:
            now = self.clock()
            row = self._owned(connection, lease, now)
            if expected_version is not None and row["version"] != expected_version:
                raise Conflict("Job version changed")
            check_transition(JobState(row["state"]), target)
            if target in (JobState.REPRODUCED, JobState.NO_REPRODUCIBLE_BUG):
                expected_exit = 1 if target == JobState.REPRODUCED else 0
                baseline = connection.execute("SELECT kind,exit_code FROM evidence WHERE job_id=? "
                                              "AND sha=? ORDER BY rowid DESC "
                                              "LIMIT 1", (lease.job_id, row['sha'])).fetchone()
                if baseline is None or baseline['kind'] != 'detection' or baseline['exit_code'] != expected_exit:
                    raise Conflict("Validated detection evidence required")
            if target in (JobState.VERIFIED, JobState.PUBLISHING, JobState.DRAFT_PR_CREATED):
                evidence = self._verification(connection, lease.job_id)
                if evidence is None or evidence["exit_code"] != 0:
                    raise Conflict("Passing verification evidence required")
            if target == JobState.DRAFT_PR_CREATED:
                publication = connection.execute("SELECT * FROM publications WHERE job_id=?",
                                                 (lease.job_id,)).fetchone()
                if publication is None or publication["pr_number"] is None:
                    raise Conflict("Draft publication metadata required")
                intent = connection.execute('SELECT * FROM publication_intents WHERE job_id=?', (lease.job_id,)).fetchone()
                if (intent is None or intent['phase'] != 'completed' or intent['stale'] or not intent['commit_sha']
                        or intent['pr_number'] != publication['pr_number']):
                    raise Conflict('Reconciled draft publication proof required')
            if target == JobState.REPAIRING:
                if row["repair_attempts"] >= row["max_repair_attempts"]:
                    raise BudgetExceeded("Repair attempt limit reached")
                connection.execute("UPDATE jobs SET repair_attempts=repair_attempts+1 WHERE id=?",
                                   (lease.job_id,))
            if target == JobState.PUBLISHING:
                if row["publication_attempts"] >= row["max_publication_attempts"]:
                    raise BudgetExceeded("Publication attempt limit reached")
                connection.execute("UPDATE jobs SET publication_attempts=publication_attempts+1 "
                                   "WHERE id=?", (lease.job_id,))
            if target in TERMINAL:
                self._finish(connection, row, target, now, failure_reason)
            else:
                connection.execute("UPDATE jobs SET state=?,updated_at=?,version=version+1 "
                                   "WHERE id=?", (target, now, lease.job_id))
                self._event(connection, lease.job_id, "state_changed",
                            {"from": row["state"], "to": target}, now)
            return self._row(connection, lease.job_id)

    def reserve_usage(self, lease: Lease, *, model_calls: int = 0, model_tokens: int = 0,
                      cost_micros: int = 0, execution_seconds: int = 0) -> dict:
        """Reserve worst-case usage BEFORE work. No refunds/reset on restart or failure."""
        amounts = {"model_calls": model_calls, "model_tokens": model_tokens,
                   "cost_micros": cost_micros, "execution_seconds": execution_seconds}
        if any(type(value) is not int or value < 0 for value in amounts.values()):
            raise ValueError("Usage must be nonnegative integer reservations")
        with self.db.transaction() as connection:
            now = self.clock()
            row = self._owned(connection, lease, now)
            if (any((model_calls, model_tokens, cost_micros))
                    and row["state"] != JobState.REPAIRING):
                raise Conflict("Model usage requires repairing state")
            if execution_seconds and row["state"] not in (JobState.BASELINING, JobState.VERIFYING):
                raise Conflict("Execution reservation requires test-run state")
            for field, amount in amounts.items():
                if row[field] + amount > row["max_" + field]:
                    raise BudgetExceeded("Persistent job usage limit reached")
            connection.execute("UPDATE jobs SET model_calls=model_calls+?,model_tokens=model_tokens+?,"
                               "cost_micros=cost_micros+?,execution_seconds=execution_seconds+?,"
                               "updated_at=?,version=version+1 WHERE id=?",
                               (*amounts.values(), now, lease.job_id))
            self._event(connection, lease.job_id, "usage_reserved", amounts, now)
            return self._row(connection, lease.job_id)

    def add_evidence(self, lease: Lease, *, kind: str, artifact_digest: str,
                     exit_code: int, summary: dict, patch_digest: str | None = None) -> str:
        self._safe_identifier(_hash(artifact_digest))
        if kind not in ("baseline", "verification") or type(exit_code) is not int:
            raise ValueError("Invalid evidence kind or exit code")
        if (kind == "verification") != (patch_digest is not None):
            raise ValueError("Only verification evidence requires a patch digest")
        if patch_digest is not None:
            self._safe_identifier(_hash(patch_digest))
        data = self._json(summary)
        with self.db.transaction() as connection:
            now = self.clock()
            row = self._owned(connection, lease, now)
            expected = JobState.BASELINING if kind == "baseline" else JobState.VERIFYING
            if row["state"] != expected or row["sha"] is None:
                raise Conflict("Evidence requires a pinned revision and matching state")
            evidence_id = uuid.uuid4().hex
            connection.execute("INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (evidence_id, lease.job_id, now, kind, row["sha"], patch_digest,
                                artifact_digest, exit_code, data, row["repair_attempts"]))
            connection.execute("UPDATE jobs SET updated_at=?,version=version+1 WHERE id=?",
                               (now, lease.job_id))
            self._event(connection, lease.job_id, "evidence_added",
                        {"evidence_id": evidence_id, "kind": kind, "exit_code": exit_code}, now)
            return evidence_id

    def record_detection(self, lease: Lease, *, verdict: str, artifact_digest: str,
                         runs: list[str], node_id: str | None = None,
                         signature: str | None = None) -> str:
        """Only this service can issue state-gating detection evidence; legacy exits cannot."""
        self._safe_identifier(_hash(artifact_digest))
        allowed = {'reproduced', 'no_reproducible_bug', 'flaky_inconclusive', 'inconclusive',
                   'missing_dependencies', 'collection_error', 'environment_error', 'timeout',
                   'oom', 'output_limit', 'runner_failure', 'blocked'}
        if (verdict not in allowed or not isinstance(runs, list) or len(runs) > 2
                or any(not isinstance(value, str) for value in runs) or len(set(runs)) != len(runs)):
            raise ValueError('Invalid detection verdict or runs')
        with self.db.transaction() as connection:
            now = self.clock()
            row = self._owned(connection, lease, now)
            if row['state'] != JobState.BASELINING or not row['sha']:
                raise Conflict('Detection requires a pinned baselining job')
            proofs = []
            for evidence_id in runs:
                proof = connection.execute("SELECT * FROM evidence WHERE id=? AND job_id=? "
                                           "AND kind='baseline' AND sha=?",
                                           (evidence_id, lease.job_id, row['sha'])).fetchone()
                if proof is None:
                    raise Conflict('Detection run evidence missing')
                proofs.append((dict(proof), json.loads(proof['summary'])))
            if verdict in ('reproduced', 'no_reproducible_bug'):
                count, exit_code = (2, 1) if verdict == 'reproduced' else (1, 0)
                if len(proofs) != count or any(proof['exit_code'] != exit_code for proof, _ in proofs):
                    raise Conflict('Matching isolated run evidence required')
                for _, data in proofs:
                    if (data.get('report_valid') is not True or data.get('cleanup_complete') is not True
                            or data.get('classification') != ('assertion_failure' if exit_code else 'no_reproducible_bug')
                            or not re.fullmatch(r'sha256:[0-9a-f]{64}', data.get('image_id', ''))
                            or not all(re.fullmatch(r'[0-9a-f]{64}', data.get(key, ''))
                                       for key in ('input_digest', 'profile_digest'))
                            or not re.fullmatch(r'[0-9a-f]{32}', data.get('run_id', ''))
                            or not isinstance(data.get('attempt_id'), str)):
                        raise Conflict('Incomplete isolated run proof')
                if verdict == 'reproduced':
                    _hash(signature)
                    if not node_id or any({'node_id': node_id, 'signature': signature}
                                          not in data.get('assertions', []) for _, data in proofs):
                        raise Conflict('Same assertion signature required')
                    first, second = (data for _, data in proofs)
                    if (first['run_id'] == second['run_id'] or first['attempt_id'] == second['attempt_id']
                            or first['assertions'] != second['assertions']
                            or any(first[key] != second[key] for key in
                                   ('image_id', 'input_digest', 'profile_digest'))):
                        raise Conflict('Fresh matching isolated environments required')
            exit_code = {'reproduced': 1, 'no_reproducible_bug': 0}.get(verdict, -1)
            data = self._json({'verdict': verdict, 'runs': runs, 'node_id': node_id,
                               'signature': signature, 'untrusted_repository_data': True})
            evidence_id = uuid.uuid4().hex
            connection.execute('INSERT INTO evidence VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)',
                               (evidence_id, lease.job_id, now, 'detection', row['sha'],
                                artifact_digest, exit_code, data, row['repair_attempts']))
            connection.execute('UPDATE jobs SET version=version+1,updated_at=? WHERE id=?',
                               (now, lease.job_id))
            self._event(connection, lease.job_id, 'detection_recorded',
                        {'evidence_id': evidence_id, 'verdict': verdict}, now)
            return evidence_id

    @staticmethod
    def _verification(connection, job_id):
        return connection.execute(
            "SELECT e.* FROM evidence e JOIN jobs j ON j.id=e.job_id "
            "JOIN verification_rounds v ON v.evidence_id=e.id AND v.status='verified' "
            "JOIN repair_candidates c ON c.id=v.candidate_id AND c.job_id=j.id "
            "WHERE e.job_id=? AND e.kind='verification' AND e.sha=j.sha "
            "AND e.patch_digest=c.patch_digest AND v.patch_digest=c.patch_digest AND v.sha=j.sha "
            "AND e.repair_attempt=j.repair_attempts ORDER BY e.rowid DESC LIMIT 1",
            (job_id,),
        ).fetchone()

    def reproduction(self, lease: Lease, *, allow_verification=False) -> dict:
        """Recheck the durable Phase 6 gate before any provider request."""
        with self.db.transaction() as connection:
            row = self._owned(connection, lease, self.clock())
            allowed = (JobState.REPRODUCED, JobState.REPAIRING)
            if allow_verification:
                allowed += (JobState.VERIFYING, JobState.VERIFIED, JobState.PUBLISHING)
            if row['state'] not in allowed:
                raise Conflict('Repair requires reproduced state')
            proof = connection.execute("SELECT * FROM evidence WHERE job_id=? AND sha=? "
                                       "AND kind='detection' ORDER BY rowid DESC LIMIT 1",
                                       (lease.job_id, row['sha'])).fetchone()
            if proof is None or proof['exit_code'] != 1:
                raise Conflict('Reproduced detection evidence required')
            data = json.loads(proof['summary'])
            if data.get('verdict') != 'reproduced' or len(data.get('runs', [])) != 2:
                raise Conflict('Reproduced detection evidence required')
            return {**dict(proof), 'summary': data}

    def candidates(self, job_id: str) -> list[dict]:
        connection = self.db.connect()
        try:
            self._row(connection, job_id)
            results = []
            for row in connection.execute('SELECT c.*, (SELECT v.id FROM verification_rounds v '
                    "WHERE v.candidate_id=c.id AND v.status='verified' AND v.sha=c.sha "
                    'AND v.patch_digest=c.patch_digest LIMIT 1) AS verification_id '
                    'FROM repair_candidates c WHERE c.job_id=? ORDER BY c.repair_attempt', (job_id,)):
                results.append({**dict(row), 'changed_files': json.loads(row['changed_files']),
                                'status': 'verified' if row['verification_id'] else row['status']})
            return results
        finally:
            connection.close()

    def record_candidate(self, lease: Lease, *, detection_id: str, attempt_id: str,
                         manifest_digest: str, profile_digest: str, patch_digest: str,
                         artifact_digest: str, provider: str, diagnosis: str, changed_files: list[str]) -> dict:
        for value in (manifest_digest, profile_digest, patch_digest, artifact_digest):
            self._safe_identifier(_hash(value))
        if (not re.fullmatch(r'\d{2}-[0-9a-f]{32}', attempt_id) or provider not in ('offline', 'gemini')
                or not isinstance(diagnosis, str) or not 1 <= len(diagnosis) <= 1000
                or not isinstance(changed_files, list) or not 1 <= len(changed_files) <= 20):
            raise ValueError('Invalid candidate metadata')
        data = self._json({'diagnosis': diagnosis, 'files': changed_files})
        clean = json.loads(data)
        with self.db.transaction() as connection:
            now = self.clock()
            row = self._owned(connection, lease, now)
            source = connection.execute('SELECT * FROM source_snapshots WHERE job_id=?', (lease.job_id,)).fetchone()
            proof = connection.execute("SELECT * FROM evidence WHERE id=? AND job_id=? AND kind='detection'",
                                       (detection_id, lease.job_id)).fetchone()
            if (row['state'] != JobState.REPAIRING or source is None or proof is None
                    or source['sha'] != row['sha'] or proof['sha'] != row['sha'] or proof['exit_code'] != 1
                    or json.loads(proof['summary']).get('verdict') != 'reproduced'
                    or source['manifest_digest'] != manifest_digest or source['profile_digest'] != profile_digest
                    or len(changed_files) > row['max_patch_files'] or row['repair_attempts'] < 1
                    or not attempt_id.startswith(f"{row['repair_attempts']:02d}-")):
                raise Conflict('Candidate requires matching reproduced source and repair state')
            candidate_id = uuid.uuid4().hex
            connection.execute('INSERT INTO repair_candidates VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                               (candidate_id, lease.job_id, row['repair_attempts'], now, row['sha'],
                                manifest_digest, profile_digest, detection_id, attempt_id, patch_digest,
                                artifact_digest, provider, clean['diagnosis'], json.dumps(clean['files']), 'proposed'))
            connection.execute('UPDATE jobs SET updated_at=?,version=version+1 WHERE id=?', (now, lease.job_id))
            self._event(connection, lease.job_id, 'candidate_proposed',
                        {'candidate_id': candidate_id, 'patch_digest': patch_digest,
                         'status': 'proposed', 'verification': 'awaiting_phase8'}, now)
        return next(item for item in self.candidates(lease.job_id) if item['id'] == candidate_id)

    def repair_observation(self, lease: Lease, code: str, *, observation=None):
        if code not in ('provider_timeout', 'provider_output_limit', 'provider_unavailable',
                        'invalid_proposal', 'invalid_edit', 'patch_limit', 'input_limit', 'budget_exhausted'):
            raise ValueError('Unknown repair observation')
        safe = {}
        if isinstance(observation, dict):
            for key in ('child_started', 'sdk_invoked', 'http_request_prepared', 'http_response_received',
                        'sdk_timeout', 'sdk_error', 'response_ready', 'call_deadline_expired'):
                if type(observation.get(key)) is bool:
                    safe[key] = observation[key]
            for key, lower, upper in (('http_status', 100, 599), ('elapsed_milliseconds', 0, 180000)):
                if type(observation.get(key)) is int and lower <= observation[key] <= upper:
                    safe[key] = observation[key]
            if observation.get('timeout_origin') in ('sdk', 'controller', 'remaining_deadline'):
                safe['timeout_origin'] = observation['timeout_origin']
        with self.db.transaction() as connection:
            now = self.clock()
            self._owned(connection, lease, now)
            data = {'reason': code}
            if safe:
                data['provider_observation'] = safe
            self._event(connection, lease.job_id, 'repair_rejected', data, now)

    def verification_rounds(self, job_id):
        connection = self.db.connect()
        try:
            self._row(connection, job_id)
            return [dict(row) for row in connection.execute(
                'SELECT * FROM verification_rounds WHERE job_id=? ORDER BY round', (job_id,))]
        finally:
            connection.close()

    def begin_verification(self, lease: Lease, candidate_id: str, image_id: str) -> str:
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', image_id):
            raise ValueError('Invalid verification image')
        with self.db.transaction() as connection:
            now = self.clock()
            row = self._owned(connection, lease, now)
            candidate = connection.execute('SELECT * FROM repair_candidates WHERE id=? AND job_id=?',
                                           (candidate_id, lease.job_id)).fetchone()
            if (row['state'] != JobState.VERIFYING or candidate is None or candidate['sha'] != row['sha']
                    or candidate['repair_attempt'] != row['repair_attempts']):
                raise Conflict('Verification requires current pinned candidate')
            count = connection.execute('SELECT COUNT(*) FROM verification_rounds WHERE job_id=?',
                                       (lease.job_id,)).fetchone()[0]
            if count >= row['max_repair_attempts']:
                raise BudgetExceeded('Verification attempt limit reached')
            connection.execute("UPDATE verification_rounds SET status='failed',finished_at=?,reason='interrupted' "
                               "WHERE job_id=? AND status='running'", (now, lease.job_id))
            identity = uuid.uuid4().hex
            connection.execute('INSERT INTO verification_rounds VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, NULL, NULL, NULL)',
                               (identity, lease.job_id, candidate_id, count + 1, now, row['sha'],
                                candidate['patch_digest'], image_id, 'running'))
            self._event(connection, lease.job_id, 'verification_started',
                        {'verification_id': identity, 'candidate_id': candidate_id, 'round': count + 1}, now)
            return identity

    def finish_verification(self, lease: Lease, round_id: str, *, verdict: str, artifact_digest: str,
                            checks: dict, reason: str | None = None):
        """Only a complete aggregate can verify a candidate; raw exit-zero evidence cannot."""
        self._safe_identifier(_hash(artifact_digest))
        if verdict not in ('verified', 'failed', 'blocked'):
            raise ValueError('Invalid verification outcome')
        allowed_reasons = {'tests_failed', 'missing_or_skipped', 'incomplete_evidence', 'timeout', 'oom',
                           'output_limit', 'cancelled', 'runner_failure', 'blocked', 'budget_exhausted',
                           'environment_error', 'regression_not_discriminating', 'candidate_mismatch'}
        if (verdict == 'verified' and reason is not None) or (verdict != 'verified' and reason not in allowed_reasons):
            raise ValueError('Invalid verification reason')
        with self.db.transaction() as connection:
            now = self.clock()
            row = self._owned(connection, lease, now)
            run = connection.execute('SELECT * FROM verification_rounds WHERE id=? AND job_id=?',
                                     (round_id, lease.job_id)).fetchone()
            if row['state'] != JobState.VERIFYING or run is None or run['status'] != 'running':
                raise Conflict('Verification round is not current')
            candidate = connection.execute('SELECT * FROM repair_candidates WHERE id=?', (run['candidate_id'],)).fetchone()
            if candidate['repair_attempt'] != row['repair_attempts'] or candidate['sha'] != row['sha']:
                raise Conflict('Verification candidate changed')
            evidence_id = None
            if verdict == 'verified':
                from worker.check_policy import DISCRIMINATING_IDS, REGRESSION_IDS

                detection = connection.execute('SELECT * FROM evidence WHERE id=?', (candidate['detection_id'],)).fetchone()
                detection_data = json.loads(detection['summary'])
                baseline = connection.execute('SELECT * FROM evidence WHERE id=?', (detection_data['runs'][0],)).fetchone()
                baseline_data = json.loads(baseline['summary'])
                required = {'baseline_regression', 'original', 'suite', 'patched_regression'}
                if set(checks) != required or run['image_id'] != baseline_data.get('image_id'):
                    raise Conflict('Complete same-image verification required')
                seen = set()
                containers = set()
                for name, check in checks.items():
                    expected_patch = None if name == 'baseline_regression' else candidate['patch_digest']
                    if (check.get('complete') is not True or check.get('cleanup_complete') is not True
                            or check.get('skipped') != 0 or check.get('source_sha') != row['sha']
                            or check.get('image_id') != run['image_id'] or check.get('patch_digest') != expected_patch
                            or not re.fullmatch(r'[0-9a-f]{32}', check.get('run_id', ''))
                            or not re.fullmatch(r'[0-9a-f]{64}', check.get('container_id', ''))
                            or check['run_id'] in seen or check['container_id'] in containers
                            or not check.get('command')):
                        raise Conflict('Invalid or reused verification run')
                    seen.add(check['run_id'])
                    containers.add(check['container_id'])
                    passed, failed = set(check.get('passed_nodes', [])), set(check.get('failed_nodes', []))
                    if name == 'baseline_regression':
                        if (check.get('exit_code') != 1 or failed != set(DISCRIMINATING_IDS)
                                or passed != set(REGRESSION_IDS) - set(DISCRIMINATING_IDS)):
                            raise Conflict('Baseline regression witness required')
                    else:
                        expected = ({detection_data['node_id']} if name == 'original' else
                                    set(baseline_data.get('test_nodes', [])) if name == 'suite' else set(REGRESSION_IDS))
                        if check.get('exit_code') != 0 or failed or not expected or passed != expected:
                            raise Conflict('Every required test must pass without skips')
                evidence_id = uuid.uuid4().hex
                summary = self._json({'schema': 2, 'candidate_id': candidate['id'],
                                      'verification_id': round_id, 'checks': checks})
                connection.execute('INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)',
                                   (evidence_id, lease.job_id, now, 'verification', row['sha'],
                                    candidate['patch_digest'], artifact_digest, summary, row['repair_attempts']))
                check_transition(JobState(row['state']), JobState.VERIFIED)
                connection.execute('UPDATE jobs SET state=?,updated_at=?,version=version+1 WHERE id=?',
                                   (JobState.VERIFIED, now, lease.job_id))
                self._event(connection, lease.job_id, 'state_changed', {'from': row['state'], 'to': JobState.VERIFIED}, now)
            connection.execute('UPDATE verification_rounds SET status=?,finished_at=?,artifact_digest=?,evidence_id=?,reason=? WHERE id=?',
                               (verdict, now, artifact_digest, evidence_id, reason, round_id))
            self._event(connection, lease.job_id, 'verification_completed',
                        {'verification_id': round_id, 'candidate_id': candidate['id'], 'outcome': verdict,
                         'reason': reason}, now)

    def evidence(self, job_id: str, limit: int = 50, after: int = 0) -> list[dict]:
        self._page(limit)
        if type(after) is not int or after < 0:
            raise ValueError("Invalid evidence cursor")
        connection = self.db.connect()
        try:
            self._row(connection, job_id)
            rows = connection.execute("SELECT rowid AS cursor,* FROM evidence WHERE job_id=? "
                                      "AND rowid>? ORDER BY rowid LIMIT ?", (job_id, after, limit))
            return [{**dict(row), "summary": json.loads(row["summary"])} for row in rows]
        finally:
            connection.close()

    def set_publication(self, lease: Lease, branch: str, *, pr_number: int | None = None,
                        draft: bool = True) -> dict:
        self._safe_identifier(_ref(branch))
        if draft is not True or (pr_number is not None
                                 and (type(pr_number) is not int or pr_number < 1)):
            raise ValueError("Only draft publication metadata is allowed")
        with self.db.transaction() as connection:
            now = self.clock()
            row = self._owned(connection, lease, now)
            evidence = self._verification(connection, lease.job_id)
            if row["state"] != JobState.PUBLISHING or evidence is None or evidence["exit_code"] != 0:
                raise Conflict("Publication requires verified evidence and publishing state")
            old = connection.execute("SELECT * FROM publications WHERE job_id=?",
                                     (lease.job_id,)).fetchone()
            if old and (old["branch"] != branch or old["sha"] != row["sha"]
                        or old["patch_digest"] != evidence["patch_digest"]
                        or (old["pr_number"] is not None and old["pr_number"] != pr_number)):
                raise Conflict("Publication identity is immutable")
            url = None
            if pr_number is not None:
                # Derived only from the approved repository, never a supplied credential URL.
                url = f"https://github.com/{row['repository']}/pull/{pr_number}"
            connection.execute("INSERT INTO publications VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?) "
                               "ON CONFLICT(job_id) DO UPDATE SET pr_number=excluded.pr_number,"
                               "url=excluded.url,updated_at=excluded.updated_at",
                               (lease.job_id, branch, pr_number, url, row["sha"],
                                evidence["patch_digest"], now, now))
            connection.execute("UPDATE jobs SET updated_at=?,version=version+1 WHERE id=?",
                               (now, lease.job_id))
            self._event(connection, lease.job_id, "publication_recorded",
                        {"branch": branch, "pr_number": pr_number, "draft": True}, now)
            return dict(connection.execute("SELECT * FROM publications WHERE job_id=?",
                                           (lease.job_id,)).fetchone())

    def publication(self, job_id: str) -> dict | None:
        connection = self.db.connect()
        try:
            self._row(connection, job_id)
            row = connection.execute("SELECT * FROM publications WHERE job_id=?",
                                     (job_id,)).fetchone()
            if not row:
                return None
            intent = connection.execute('SELECT * FROM publication_intents WHERE job_id=?', (job_id,)).fetchone()
            return {**dict(row), **({'commit_sha': intent['commit_sha'], 'marker': intent['marker'],
                                     'mode': intent['mode'], 'simulated': intent['mode'] == 'offline'} if intent else {})}
        finally:
            connection.close()

    def publication_proof(self, lease):
        with self.db.transaction() as connection:
            row = self._owned(connection, lease, self.clock())
            evidence = self._verification(connection, lease.job_id)
            if row['state'] not in (JobState.VERIFIED, JobState.PUBLISHING) or evidence is None or row['cancellation_requested']:
                raise Conflict('Publication requires uncancelled verified job')
            return {**dict(evidence), 'summary': json.loads(evidence['summary'])}

    def publication_intent(self, job_id):
        connection = self.db.connect()
        try:
            self._row(connection, job_id)
            record = connection.execute('SELECT * FROM publication_intents WHERE job_id=?', (job_id,)).fetchone()
            return dict(record) if record else None
        finally:
            connection.close()

    def prepare_publication(self, lease, *, base_ref, mode):
        self._safe_identifier(_ref(base_ref))
        if mode not in ('offline', 'live'):
            raise ValueError('Invalid publisher mode')
        proof = self.publication_proof(lease)
        marker = f"<!-- webguard-ai-job:{lease.job_id};verification:{proof['summary']['verification_id']};patch:{proof['patch_digest']} -->"
        branch = 'webguard/jobs/' + lease.job_id
        with self.db.transaction() as connection:
            row = self._owned(connection, lease, self.clock())
            old = connection.execute('SELECT * FROM publication_intents WHERE job_id=?', (lease.job_id,)).fetchone()
            identity = (row['repository'], base_ref, row['sha'], proof['patch_digest'],
                        proof['summary']['verification_id'], proof['artifact_digest'], marker, branch, mode)
            if old and tuple(old[key] for key in ('repository', 'base_ref', 'base_sha', 'patch_digest',
                'verification_id', 'evidence_digest', 'marker', 'branch', 'mode')) != identity:
                raise Conflict('Publication identity is immutable')
            if not old:
                connection.execute('INSERT INTO publication_intents '
                    '(job_id,repository,base_ref,base_sha,patch_digest,verification_id,evidence_digest,marker,branch,mode,created_at,phase) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (lease.job_id, *identity, self.clock(), 'prepared'))
                self._event(connection, lease.job_id, 'publication_prepared',
                            {'branch': branch, 'simulated': mode == 'offline', 'verification_id': identity[4]}, self.clock())
            return dict(connection.execute('SELECT * FROM publication_intents WHERE job_id=?', (lease.job_id,)).fetchone())

    def note_publication(self, lease, *, phase=None, commit_sha=None, pr_number=None, error=None, stale=False):
        if phase not in (None, 'branch_inflight', 'branch_ready', 'pr_inflight'):
            raise ValueError('Invalid publication phase')
        if commit_sha is not None:
            self._safe_identifier(_revision(commit_sha))
        if pr_number is not None and (type(pr_number) is not int or pr_number < 1):
            raise ValueError('Invalid draft number')
        codes = {None, 'base_moved', 'remote_unavailable', 'remote_rejected', 'remote_timeout',
                 'outcome_unknown', 'remote_identity', 'remote_limit', 'publication_budget',
                 'token_scope', 'live_not_enabled', 'unverified_evidence'}
        if error not in codes:
            raise ValueError('Invalid publication error')
        with self.db.transaction() as connection:
            row = self._owned(connection, lease, self.clock())
            if row['state'] not in (JobState.VERIFIED, JobState.PUBLISHING) or self._verification(connection, lease.job_id) is None:
                raise Conflict('Publication requires verified evidence')
            old = connection.execute('SELECT * FROM publication_intents WHERE job_id=?', (lease.job_id,)).fetchone()
            if (old is None or (old['commit_sha'] and commit_sha and old['commit_sha'] != commit_sha)
                    or (old['pr_number'] and pr_number and old['pr_number'] != pr_number)):
                raise Conflict('Publication commit identity is immutable')
            url = None if pr_number is None else (f"simulated://webguard/{lease.job_id}/pull/{pr_number}"
                if old['mode'] == 'offline' else f"https://github.com/{old['repository']}/pull/{pr_number}")
            connection.execute('UPDATE publication_intents SET phase=COALESCE(?,phase),commit_sha=COALESCE(?,commit_sha),'
                               'pr_number=COALESCE(?,pr_number),pr_url=COALESCE(?,pr_url),last_error=?,stale=MAX(stale,?) WHERE job_id=?',
                               (phase, commit_sha, pr_number, url, error, int(stale), lease.job_id))
            if pr_number is not None:
                self._event(connection, lease.job_id, 'draft_observed',
                            {'pr_number': pr_number, 'url': url, 'simulated': old['mode'] == 'offline'}, self.clock())
            if error:
                self._event(connection, lease.job_id, 'publication_blocked' if stale else 'publication_retryable',
                            {'reason': error, 'branch': old['branch'], 'simulated': old['mode'] == 'offline'}, self.clock())

    def publication_back_to_verified(self, lease):
        row = self.check_lease(lease)
        if row['state'] == JobState.PUBLISHING:
            return self.advance(lease, JobState.VERIFIED)
        return row

    def finish_publication(self, lease, *, commit_sha, pr_number):
        self._safe_identifier(_revision(commit_sha))
        if type(pr_number) is not int or pr_number < 1:
            raise ValueError('Invalid draft PR number')
        with self.db.transaction() as connection:
            now = self.clock()
            row = self._owned(connection, lease, now)
            proof = self._verification(connection, lease.job_id)
            intent = connection.execute('SELECT * FROM publication_intents WHERE job_id=?', (lease.job_id,)).fetchone()
            if (row['state'] not in (JobState.VERIFIED, JobState.PUBLISHING) or proof is None or intent is None
                    or intent['stale'] or intent['commit_sha'] != commit_sha
                    or intent['repository'] != row['repository']
                    or intent['base_sha'] != row['sha'] or intent['patch_digest'] != proof['patch_digest']
                    or intent['evidence_digest'] != proof['artifact_digest']
                    or intent['verification_id'] != json.loads(proof['summary'])['verification_id']
                    or (intent['pr_number'] and intent['pr_number'] != pr_number)
                    or intent['phase'] not in ('branch_ready', 'pr_inflight')):
                raise Conflict('Matching reconciled verified draft required')
            simulated = intent['mode'] == 'offline'
            url = (f"simulated://webguard/{lease.job_id}/pull/{pr_number}" if simulated else
                   f"https://github.com/{row['repository']}/pull/{pr_number}")
            old = connection.execute('SELECT * FROM publications WHERE job_id=?', (lease.job_id,)).fetchone()
            if old and (old['branch'] != intent['branch'] or (old['pr_number'] and old['pr_number'] != pr_number)):
                raise Conflict('Publication identity changed')
            connection.execute('INSERT INTO publications VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?) '
                'ON CONFLICT(job_id) DO UPDATE SET pr_number=excluded.pr_number,url=excluded.url,updated_at=excluded.updated_at',
                (lease.job_id, intent['branch'], pr_number, url, row['sha'], proof['patch_digest'], now, now))
            connection.execute("UPDATE publication_intents SET phase='completed',pr_number=?,pr_url=?,last_error=NULL WHERE job_id=?",
                               (pr_number, url, lease.job_id))
            if row['state'] == JobState.VERIFIED:
                self._event(connection, lease.job_id, 'state_changed', {'from': JobState.VERIFIED, 'to': JobState.PUBLISHING,
                            'reconciled': True}, now)
                row = {**row, 'state': JobState.PUBLISHING}
            self._finish(connection, row, JobState.DRAFT_PR_CREATED, now)
            self._event(connection, lease.job_id, 'draft_pr_recorded',
                        {'pr_number': pr_number, 'commit_sha': commit_sha, 'simulated': simulated, 'draft': True}, now)
        return self.publication(lease.job_id)
