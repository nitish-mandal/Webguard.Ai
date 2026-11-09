"""Lease-fenced background orchestration. Target execution stays in Docker."""

import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from backend.app.domain import (
    TERMINAL,
    BudgetExceeded,
    Conflict,
    FailureReason,
    JobState,
    LeaseLost,
)
from backend.app.jobs import JobService
from worker.demo_fixture import DemoFixture
from worker.detection import DetectionService
from worker.docker_client import DockerFault
from worker.docker_runner import DockerRunner
from worker.execution import ExecutionService
from worker.publication import PublicationService
from worker.repair import RepairService
from worker.repair_models import RepairError
from worker.source_common import Budget, SourceError, no_links
from worker.source_service import RepositoryAccess, limits_from_settings
from worker.verification import VerificationError, VerificationService
from worker.workspaces import Workspace, WorkspaceManager


@dataclass
class PipelineResult:
    job_id: str
    outcome: str
    reason: str | None = None


class Runtime:
    def __init__(self, access, execution=None, provider=None, remote=None):
        self.access, self.jobs, self.manager = access, access.jobs, access.manager
        self.runner = execution.runner if execution else DockerRunner.configured(self.manager, self.jobs.settings)
        self.execution = execution if execution else ExecutionService(self.jobs, self.runner)
        self.detection = DetectionService(access, self.execution)
        self.repair = RepairService(access, provider)
        self.verification = VerificationService(access, self.execution)
        self.publication = PublicationService(access, remote)
        self.fixture = None
        self.owner = uuid.uuid4().hex

    @classmethod
    def configured(cls, settings):
        jobs = JobService(settings)
        if settings.allowed_repository == 'demo-repository':
            manager = WorkspaceManager(Path(settings.workspace_root), limits_from_settings(settings))
            owner = uuid.uuid4().hex
            fixture = DemoFixture(manager, owner)
            try:
                runtime = cls(RepositoryAccess.fixture(jobs, fixture.path))
                runtime.fixture = fixture
                runtime.owner = owner
                return runtime
            except BaseException:
                fixture.close()
                raise
        return cls(RepositoryAccess.github(jobs))

    def recover_job(self, lease):
        self.jobs.check_lease(lease)
        result = self.runner.recover(active_jobs=lambda job: job != lease.job_id, min_age_seconds=0)
        self.jobs.check_lease(lease)
        if not all(result.values()):
            raise DockerFault('cleanup_failed')

    def cleanup(self, job_id, lease=None):
        """Serialize ownership validation + filesystem cleanup against new claims."""
        with self.jobs.db.transaction() as connection:
            row = self.jobs._row(connection, job_id)
            terminal = row['state'] in TERMINAL
            if not terminal and row['lease_owner'] is not None:
                if lease is None:
                    return False
                self.jobs._owned(connection, lease, self.jobs.clock())
            snapshot = self.jobs.source_snapshot(job_id)
            if snapshot:
                workspace = self.manager.reopen(job_id, snapshot, Budget(self.manager.limits.seconds))
                root = self.manager.path(workspace) / 'attempts'
                keep = set() if terminal else {item['attempt_id'] for item in self.jobs.candidates(job_id)}
                for path in root.iterdir():
                    if path.is_dir() and re.fullmatch(r'\d{2}-[0-9a-f]{32}', path.name) and path.name not in keep:
                        no_links(path)
                        sidecar = root / (path.name + '.json')
                        if sidecar.exists():
                            self.manager.cleanup_attempt(workspace, path)
                        else:
                            self.manager._delete(path, self.manager.path(workspace))
            for path in self.manager.root.glob(job_id + '-*'):
                if (re.fullmatch(job_id + '-[0-9a-f]{32}', path.name)
                        and (not snapshot or path.name != job_id + '-' + snapshot['workspace_id'])):
                    self.manager.cleanup(Workspace(job_id, path.name[len(job_id) + 1:]))
            if terminal:
                connection.execute('INSERT INTO job_dispatch(job_id,terminal_cleaned) VALUES (?,1) '
                    'ON CONFLICT(job_id) DO UPDATE SET terminal_cleaned=1', (job_id,))
            self.jobs._event(connection, job_id, 'worker_cleanup', {'attempts_removed': True}, self.jobs.clock())
            return True

    def maintenance(self):
        self.jobs.expire()
        def active(job):
            row = self.jobs.get(job)
            return row['state'] not in TERMINAL and bool(row['lease_expires_at'] and row['lease_expires_at'] > self.jobs.clock())
        try:
            self.runner.recover(active_jobs=active, min_age_seconds=self.jobs.settings.runner_control_seconds + 2)
        except DockerFault:
            pass  # Claim records an explicit isolation blocker; no host fallback.
        job_id = self.jobs.terminal_reconciliation()
        if job_id:
            self.publication.reconcile_terminal(job_id)
        with self.jobs.db.transaction() as connection:
            rows = connection.execute("SELECT j.id FROM jobs j LEFT JOIN job_dispatch d ON d.job_id=j.id "
                "WHERE j.state IN ('cancelled','failed','no_reproducible_bug','draft_pr_created') "
                'AND j.repository=? AND COALESCE(d.terminal_cleaned,0)=0 LIMIT 10',
                (self.jobs.settings.allowed_repository,)).fetchall()
        for row in rows:
            self.cleanup(row['id'])
        self.cleanup_fixtures()

    def cleanup_fixtures(self):
        for marker in self.manager.root.glob('*-*/.fixture-owner.json'):
            with self.jobs.db.transaction() as connection:
                metadata = self.manager._json(marker)
                if metadata.get('owner') == self.owner:
                    continue
                owner = metadata.get('owner', '')
                if not re.fullmatch(r'[0-9a-f]{32}', owner) or metadata.get('version') != 1:
                    continue
                session = connection.execute('SELECT * FROM worker_sessions WHERE owner=?', (owner,)).fetchone()
                now = self.jobs.clock()
                if session and not session['stopped'] and session['expires_at'] > now:
                    continue
                if not session and now - metadata.get('created_at', now) < 60:
                    continue
                if connection.execute('SELECT 1 FROM jobs WHERE lease_owner=? AND lease_expires_at>? LIMIT 1',
                                      (owner, now)).fetchone():
                    continue
                workspace = Workspace(metadata['job_id'], metadata['workspace_id'])
                if self.manager.path(workspace) != marker.parent:
                    raise SourceError('workspace_identity')
                self.manager.cleanup(workspace)

    def close(self):
        self.publication.close()
        self.runner.client.close()
        if self.fixture:
            with self.jobs.db.transaction():
                self.fixture.close()


class LeaseKeeper:
    def __init__(self, jobs, lease):
        self.jobs, self.lease = jobs, lease
        self.done, self.lost = threading.Event(), threading.Event()
        self.thread = threading.Thread(target=self._run, name='webguard-lease', daemon=True)

    def _run(self):
        while not self.done.wait(max(0.1, self.jobs.settings.lease_seconds / 3)):
            try:
                self.jobs.renew(self.lease)
            except (Conflict, sqlite3.Error, OSError):
                self.lost.set()
                return

    def __enter__(self):
        self.jobs.check_lease(self.lease)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.done.set()
        self.thread.join(timeout=12)


def run_job(job_id, *, runtime, lease):
    if lease.job_id != job_id:
        raise ValueError('Claimed job identity required')
    jobs = runtime.jobs
    with LeaseKeeper(jobs, lease):
        try:
            initial = jobs.check_lease(lease)
            if initial['state'] in (JobState.VERIFIED, JobState.PUBLISHING):
                try:
                    runtime.recover_job(lease)
                except DockerFault:
                    pass  # Reconcile accepted publication even if Docker is now unavailable.
            else:
                runtime.recover_job(lease)
            runtime.cleanup(job_id, lease)
            for _ in range(10):
                row = jobs.check_lease(lease)
                state = JobState(row['state'])
                if state == JobState.QUEUED:
                    runtime.runner.preflight()
                    jobs.advance(lease, JobState.BASELINING)
                elif state == JobState.BASELINING:
                    runtime.runner.preflight()
                    jobs.worker_stage(lease, 'source')
                    runtime.access.prepare(lease)
                    jobs.worker_stage(lease, 'reproduction')
                    result = runtime.detection.detect(lease)
                    if result.verdict == 'blocked':
                        jobs.defer(lease, 'docker_unavailable', paused=True)
                        return PipelineResult(job_id, 'blocked', 'docker_unavailable')
                    if jobs.get(job_id)['state'] in TERMINAL:
                        return PipelineResult(job_id, jobs.get(job_id)['state'], result.verdict)
                elif state in (JobState.REPRODUCED, JobState.REPAIRING, JobState.VERIFYING):
                    if state != JobState.VERIFYING:
                        jobs.worker_stage(lease, 'repair')
                        candidate = runtime.repair.propose(lease)
                        candidate_id = candidate['id']
                    else:
                        candidate_id = None
                    jobs.worker_stage(lease, 'verification')
                    result = runtime.verification.verify(lease, candidate_id)
                    if result.outcome == 'blocked':
                        jobs.defer(lease, 'verification_blocked', paused=True)
                        return PipelineResult(job_id, 'blocked', result.reason)
                    if result.outcome != 'verified':
                        return PipelineResult(job_id, result.outcome, result.reason)
                elif state in (JobState.VERIFIED, JobState.PUBLISHING):
                    jobs.worker_stage(lease, 'publication')
                    result = runtime.publication.publish(lease)
                    if result.outcome in ('stale_owner', 'cancelled'):
                        jobs.expire()
                        current = jobs.get(job_id)
                        if current['state'] in TERMINAL:
                            return PipelineResult(job_id, current['state'], result.reason)
                    if result.outcome in ('blocked', 'retryable'):
                        jobs.defer(lease, 'publication_retry' if result.outcome == 'retryable' else 'publication_blocked',
                                   paused=result.outcome == 'blocked')
                    return PipelineResult(job_id, result.outcome, result.reason)
            raise Conflict('Pipeline step bound exceeded')
        except LeaseLost:
            jobs.expire()
            row = jobs.get(job_id)
            return PipelineResult(job_id, row['state'] if row['state'] in TERMINAL else 'stale_owner')
        except DockerFault:
            jobs.defer(lease, 'docker_unavailable', paused=True)
            return PipelineResult(job_id, 'blocked', 'docker_unavailable')
        except (BudgetExceeded, RepairError) as error:
            reason = FailureReason.BUDGET if isinstance(error, BudgetExceeded) or error.code == 'budget_exhausted' else FailureReason.MODEL
            if isinstance(error, RepairError) and error.code in ('invalid_edit', 'patch_limit', 'invalid_proposal'):
                reason = FailureReason.PATCH
            jobs.advance(lease, JobState.FAILED, failure_reason=reason)
            return PipelineResult(job_id, 'failed', str(reason))
        except (SourceError, VerificationError, Conflict, ValueError, OSError):
            if jobs.get(job_id)['state'] not in TERMINAL:
                jobs.defer(lease, 'controller_error', paused=True)
            return PipelineResult(job_id, 'blocked', 'controller_error')
        finally:
            jobs.expire()
            row = jobs.get(job_id)
            owned = row['lease_owner'] == lease.owner and row['fence'] == lease.fence
            if row['state'] in (JobState.CANCELLED, JobState.FAILED) and jobs.terminal_reconciliation(job_id):
                runtime.publication.reconcile_terminal(job_id)
            if owned or row['lease_owner'] is None or row['state'] in TERMINAL:
                try:
                    runtime.cleanup(job_id, lease)
                except (Conflict, SourceError, OSError):
                    pass


class Worker:
    def __init__(self, runtime, owner=None):
        self.runtime, self.jobs = runtime, runtime.jobs
        self.owner = owner or runtime.owner
        self.stopping, self.session_done = threading.Event(), threading.Event()

    def run_once(self):
        lease = self.jobs.claim(self.owner)
        if lease is None:
            return None
        try:
            return run_job(lease.job_id, runtime=self.runtime, lease=lease)
        except LeaseLost:
            self.jobs.expire()
            row = self.jobs.get(lease.job_id)
            return PipelineResult(lease.job_id, row['state'] if row['state'] in TERMINAL else 'stale_owner')
        finally:
            try:
                self.jobs.release(lease)
            except LeaseLost:
                pass

    def _session(self):
        while not self.session_done.wait(1):
            try:
                row = self.jobs.worker_session(self.owner)
                if row['stop_requested']:
                    self.stopping.set()
            except (sqlite3.Error, OSError):
                self.stopping.set()

    def serve(self, on_started=None):
        self.jobs.worker_session(self.owner, start=True)
        thread = threading.Thread(target=self._session, name='webguard-session', daemon=True)
        thread.start()
        if on_started:
            on_started(self.owner)
        try:
            while not self.stopping.is_set():
                try:
                    self.runtime.maintenance()
                except (sqlite3.Error, OSError, SourceError, DockerFault):
                    pass
                try:
                    if not self.stopping.is_set():
                        self.run_once()
                except (sqlite3.Error, OSError, SourceError, DockerFault):
                    pass
                self.stopping.wait(self.jobs.settings.worker_poll_seconds)
        finally:
            self.session_done.set()
            thread.join(timeout=12)
            self.jobs.worker_session(self.owner, stopped=True)
