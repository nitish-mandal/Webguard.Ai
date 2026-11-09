"""Fenced Docker controller integration for the worker. No HTTP handler calls it."""

import hashlib
import time
import uuid
from dataclasses import replace

from backend.app.domain import BudgetExceeded, JobState, LeaseLost
from backend.app.settings import Redactor
from worker.docker_client import DockerFault
from worker.docker_runner import DockerRunner
from worker.runner_models import Outcome, RunResult
from worker.source_common import no_links
from worker.workspaces import canonical


class ExecutionService:
    def __init__(self, jobs, runner: DockerRunner):
        self.jobs, self.runner = jobs, runner

    def execute(self, lease, request, *, record_evidence=True):
        row = self.jobs.check_lease(lease)
        expected = JobState.BASELINING if request.kind == "baseline" else JobState.VERIFYING
        blocked = RunResult(uuid.uuid4().hex, lease.job_id, row["sha"],
                            request.workspace.manifest_digest, request.workspace.profile_digest,
                            outcome=Outcome.BLOCKED)
        snapshot = self.jobs.source_snapshot(lease.job_id)
        if (request.kind not in ("baseline", "verification", 'control') or request.workspace.job_id != lease.job_id
                or row["state"] != expected or snapshot is None
                or any(snapshot[key] != getattr(request.workspace, key) for key in
                       ("workspace_id", "sha", "manifest_digest", "profile_digest"))):
            blocked.reason = "job_state_or_identity"
            return blocked
        try:
            self.runner.preflight()
        except DockerFault as error:
            blocked.reason = error.code
            return blocked
        seconds = min(self.runner.limits.wall_seconds,
                      row["max_execution_seconds"] - row["execution_seconds"],
                      int(row["deadline"] - self.jobs.clock()))
        if seconds < 1:
            blocked.reason = "execution_budget"
            return blocked
        try:
            self.jobs.reserve_usage(lease, execution_seconds=seconds)
        except BudgetExceeded:
            blocked.reason = "execution_budget"
            return blocked
        runner = DockerRunner(
            self.runner.manager, self.runner.image_id,
            replace(self.runner.limits, wall_seconds=seconds,
                    output_bytes=min(row["max_output_bytes"], self.runner.limits.output_bytes)),
            self.runner.profile,
            Redactor(tuple(set(self.runner.redactor._secrets + self.jobs.redactor._secrets))),
            self.runner.client,
        )
        runner.active, runner.lock = self.runner.active, self.runner.lock
        last_checked = 0
        was_cancelled = False

        def cancelled():
            nonlocal last_checked, was_cancelled
            if time.monotonic() - last_checked < 0.1:
                return was_cancelled
            last_checked = time.monotonic()
            current = self.jobs.get(lease.job_id)
            was_cancelled = bool(current["cancellation_requested"])
            if was_cancelled:
                return True
            try:
                self.jobs.check_lease(lease)
                if current["lease_expires_at"] - self.jobs.clock() < self.jobs.settings.lease_seconds / 2:
                    self.jobs.renew(lease)
            except LeaseLost:
                raise DockerFault("lease_lost") from None
            return False

        result = runner.run(request, cancelled)
        if result.outcome in (Outcome.PASSED, Outcome.TEST_FAILURE):
            try:
                self.jobs.check_lease(lease)
            except LeaseLost:
                result.outcome, result.reason = Outcome.INFRASTRUCTURE, "lease_lost"
        # Append a unique redacted receipt outside the source/attempt transfer tree.
        directory = runner.manager.path(request.workspace) / "runner-receipts"
        no_links(directory)
        directory.mkdir(exist_ok=True)
        receipt = canonical(result.document())
        with (directory / f"{result.run_id}.json").open("xb") as output:
            output.write(receipt)
        if record_evidence and request.kind != 'control' and result.outcome in (Outcome.PASSED, Outcome.TEST_FAILURE) and result.cleanup_complete:
            try:
                self.jobs.add_evidence(
                    lease, kind=request.kind, artifact_digest=hashlib.sha256(receipt).hexdigest(),
                    exit_code=result.exit_code, patch_digest=result.patch_digest,
                    summary={"runner": "docker", "outcome": result.outcome,
                             "image_id": result.image_id, "input_digest": result.input_digest,
                             "duration_seconds": result.duration_seconds, "cleanup_complete": True},
                )
            except LeaseLost:
                result.outcome, result.reason = Outcome.INFRASTRUCTURE, "lease_lost"
        return result

    def recover(self, min_age_seconds=300):
        def active(job_id):
            row = self.jobs.get(job_id)
            return bool(row["lease_owner"] and row["lease_expires_at"] > self.jobs.clock())
        return self.runner.recover(active_jobs=active, min_age_seconds=min_age_seconds)
