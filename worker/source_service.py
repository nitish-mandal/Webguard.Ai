"""Approved source controller used by the worker, never by HTTP handlers."""

from pathlib import Path

from backend.app.domain import JobState
from backend.app.jobs import JobService, Lease
from worker.repositories import GitHubRepository, LocalFixtureRepository
from worker.source_common import Budget, GitReader, SourceError, SourceLimits
from worker.workspaces import DEMO_PROFILE, TargetProfile, WorkspaceManager


def limits_from_settings(settings):
    return SourceLimits(settings.source_max_file_bytes, settings.source_max_total_bytes,
                        settings.source_max_files, settings.source_max_archive_bytes,
                        settings.source_max_metadata_bytes, settings.source_timeout_seconds)


class RepositoryAccess:
    def __init__(self, jobs: JobService, manager: WorkspaceManager, adapter,
                 profile: TargetProfile = DEMO_PROFILE):
        if jobs.settings.allowed_repository != adapter.repository:
            raise SourceError("identity")
        self.jobs, self.manager, self.adapter, self.profile = jobs, manager, adapter, profile

    @classmethod
    def github(cls, jobs: JobService):
        settings = jobs.settings
        adapter = GitHubRepository(settings.allowed_repository)
        manager = WorkspaceManager(Path(settings.workspace_root), limits_from_settings(settings))
        return cls(jobs, manager, adapter)

    @classmethod
    def fixture(cls, jobs: JobService, fixture_git_directory: Path):
        settings = jobs.settings
        if settings.allowed_repository != "demo-repository":
            raise SourceError("identity")
        manager = WorkspaceManager(Path(settings.workspace_root), limits_from_settings(settings))
        reader = GitReader(manager.root)
        return cls(jobs, manager, LocalFixtureRepository(fixture_git_directory, reader))

    def prepare(self, lease: Lease):
        row = self.jobs.check_lease(lease)
        if row["state"] != JobState.BASELINING:
            raise SourceError("state")
        seconds = min(self.manager.limits.seconds, row["deadline"] - self.jobs.clock(),
                      row["lease_expires_at"] - self.jobs.clock())
        budget = Budget(seconds)
        existing = self.jobs.source_snapshot(lease.job_id)
        if existing:
            if existing["sha"] != row["sha"] or existing["profile_digest"] != self.profile.digest:
                raise SourceError("profile")
            return self.manager.reopen(lease.job_id, existing, budget)
        sha = self.adapter.resolve(row["sha"] or row["ref"], self.manager.limits, budget)
        self.jobs.pin_revision(lease, sha)
        workspace = self.manager.create(lease.job_id)
        try:
            self.adapter.acquire(sha, self.manager.path(workspace) / "baseline", self.manager.limits, budget)
            self.jobs.check_lease(lease)
            workspace = self.manager.seal(workspace, sha, self.profile, budget)
            self.manager.verify(workspace, budget)
            self.jobs.record_source(lease, workspace.workspace_id, workspace.manifest_digest,
                                    workspace.profile_digest)
            return workspace
        except BaseException:
            self.manager.cleanup(workspace)
            raise

    def attempt(self, lease: Lease, number: int):
        row = self.jobs.check_lease(lease)
        record = self.jobs.source_snapshot(lease.job_id)
        if not record or record["sha"] != row["sha"] or record["profile_digest"] != self.profile.digest:
            raise SourceError("source_missing")
        budget = Budget(min(self.manager.limits.seconds, row["lease_expires_at"] - self.jobs.clock()))
        workspace = self.manager.reopen(lease.job_id, record, budget)
        result = self.manager.create_attempt(workspace, number, budget)
        self.jobs.check_lease(lease)
        return result
