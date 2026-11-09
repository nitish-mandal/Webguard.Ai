"""Owned workspace trees, sealed baselines and independent attempt copies."""

import hashlib
import json
import os
import re
import stat
import uuid
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from worker.source_common import Budget, SourceError, SourceLimits, identifier, no_links, safe_path


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


@dataclass(frozen=True)
class TargetProfile:
    name: str = "approved-demo-python-pytest-v4"
    verification_revision: str = 'pagination-regression-v1'
    python_version: str = "3.12"
    test_command: tuple[str, ...] = (
        "python", "-I", "-B", "-m", "pytest", "-q", "--capture=no", "-c", "/opt/webguard/pytest.ini",
        "-p", "no:cacheprovider", "-p", "webguard_report", "tests",
    )
    source_edit_allowlist: tuple[str, ...] = ("pagination.py",)
    dependency_recipe: tuple[str, ...] = (
        "python", "-m", "pip", "install", "--no-index", "--find-links=/wheels",
        "--no-deps", "--only-binary=:all:", "pytest==9.2.0", "iniconfig==2.3.1",
        "packaging==26.3", "pluggy==1.7.0", "pygments==2.21.0", "colorama==0.4.6",
    )

    def __post_init__(self):
        if (self.python_version != "3.12" or not re.fullmatch(r"[a-z0-9-]{1,80}", self.name)
                or not all(type(value) is tuple for value in
                           (self.test_command, self.source_edit_allowlist, self.dependency_recipe))):
            raise SourceError("profile")
        for path in self.source_edit_allowlist:
            safe_path(path)
            if not path.endswith(".py") or any(
                part.casefold() in ("test", "tests", "conftest.py")
                or part.casefold().startswith("test_") or part.casefold().endswith("_test.py")
                for part in path.split("/")
            ):
                raise SourceError("profile")

    @property
    def digest(self):
        return hashlib.sha256(canonical(asdict(self))).hexdigest()


DEMO_PROFILE = TargetProfile()


@dataclass(frozen=True)
class Workspace:
    job_id: str
    workspace_id: str
    sha: str | None = None
    manifest_digest: str | None = None
    profile_digest: str | None = None


class WorkspaceManager:
    def __init__(self, root: Path, limits: SourceLimits | None = None):
        root = root.absolute()
        no_links(root)
        if root == Path(root.anchor) or ".." in root.parts:
            raise SourceError("workspace_root")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root = root.resolve()
        self.limits = limits if limits is not None else SourceLimits()
        marker = self.root / ".webguard-owner.json"
        if not marker.exists():
            if any(self.root.iterdir()):
                raise SourceError("unowned_root")
            # Exclusive create: concurrent initializers cannot overwrite ownership.
            try:
                with marker.open("xb") as output:
                    output.write(canonical({"version": 1, "owner": uuid.uuid4().hex}))
            except FileExistsError:
                raise SourceError("root_busy") from None
        no_links(marker)
        self.owner = self._json(marker).get("owner")
        identifier(self.owner)

    @staticmethod
    def _json(path: Path):
        no_links(path)
        try:
            if path.stat().st_size > 2097152:
                raise SourceError("manifest_limit")
            with path.open("rb") as source:
                data = source.read(2097153)
            if len(data) > 2097152:
                raise SourceError("manifest_limit")
            result = json.loads(data)
            if not isinstance(result, dict):
                raise SourceError("workspace_identity")
            return result
        except (ValueError, OSError, UnicodeError, RecursionError):
            raise SourceError("workspace_identity") from None

    def path(self, workspace: Workspace) -> Path:
        if not isinstance(workspace, Workspace):
            raise SourceError("workspace_identity")
        name = f"{identifier(workspace.job_id)}-{identifier(workspace.workspace_id)}"
        no_links(self.root)
        if self._json(self.root / ".webguard-owner.json") != {"owner": self.owner, "version": 1}:
            raise SourceError("workspace_identity")
        target = self.root / name
        no_links(target)
        if target.resolve().parent != self.root:
            raise SourceError("workspace_escape")
        expected = {"owner": self.owner, "job_id": workspace.job_id,
                    "workspace_id": workspace.workspace_id, "version": 1}
        if self._json(target / ".owned.json") != expected:
            raise SourceError("workspace_identity")
        return target

    def create(self, job_id: str) -> Workspace:
        workspace = Workspace(identifier(job_id), uuid.uuid4().hex)
        # Revalidate root before creating anything, including partial acquisitions.
        no_links(self.root)
        if self._json(self.root / ".webguard-owner.json") != {"owner": self.owner, "version": 1}:
            raise SourceError("workspace_identity")
        target = self.root / f"{workspace.job_id}-{workspace.workspace_id}"
        target.mkdir(mode=0o700)
        try:
            with (target / ".owned.json").open("xb") as output:
                output.write(canonical({"owner": self.owner, "job_id": job_id,
                                        "workspace_id": workspace.workspace_id, "version": 1}))
            (target / "baseline").mkdir(mode=0o700)
            (target / "attempts").mkdir(mode=0o700)
        except OSError:
            # No source content exists yet; leave an incomplete directory for review
            # if ownership could not be written rather than deleting an unowned path.
            raise SourceError("workspace_create") from None
        return workspace

    def _inventory(self, path: Path, budget: Budget) -> dict:
        result = {}
        folders = set()
        total = 0
        for folder, directories, files in os.walk(path, followlinks=False):
            no_links(Path(folder))
            for directory in directories:
                no_links(Path(folder) / directory)
                folders.add(safe_path((Path(folder) / directory).relative_to(path).as_posix()))
            if len(folders) > self.limits.files * 16:
                raise SourceError("size_limit")
            for name in files:
                budget.remaining()
                file = Path(folder) / name
                no_links(file)
                info = file.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise SourceError("filesystem_link")
                relative = safe_path(file.relative_to(path).as_posix())
                if info.st_size > self.limits.file_bytes:
                    raise SourceError("size_limit")
                total += info.st_size
                if total > self.limits.total_bytes or len(result) >= self.limits.files:
                    raise SourceError("size_limit")
                with file.open("rb") as source:
                    data = source.read(self.limits.file_bytes + 1)
                if len(data) != info.st_size:
                    raise SourceError("integrity")
                result[relative] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        expected_folders = {parent.as_posix() for name in result for parent in Path(name).parents
                            if str(parent) != "."}
        if folders != expected_folders:
            raise SourceError("baseline_integrity")
        return result

    def seal(self, workspace: Workspace, sha: str, profile: TargetProfile, budget: Budget) -> Workspace:
        target = self.path(workspace)
        files = self._inventory(target / "baseline", budget)
        if not files or any(safe_path(path) not in files for path in profile.source_edit_allowlist):
            raise SourceError("profile")
        manifest = canonical({"version": 1, "sha": sha, "profile": asdict(profile), "files": files})
        if len(manifest) > 2097152:
            raise SourceError("manifest_limit")
        with (target / "baseline.json").open("xb") as output:
            output.write(manifest)
        for file in (target / "baseline").rglob("*"):
            if file.is_file():
                file.chmod(stat.S_IREAD)
        (target / "baseline.json").chmod(stat.S_IREAD)
        return replace(workspace, sha=sha, manifest_digest=hashlib.sha256(manifest).hexdigest(),
                       profile_digest=profile.digest)

    def verify(self, workspace: Workspace, budget: Budget) -> dict:
        target = self.path(workspace)
        manifest = self._json(target / "baseline.json")
        if (hashlib.sha256(canonical(manifest)).hexdigest() != workspace.manifest_digest
                or manifest.get("sha") != workspace.sha
                or hashlib.sha256(canonical(manifest.get("profile"))).hexdigest() != workspace.profile_digest):
            raise SourceError("baseline_integrity")
        if self._inventory(target / "baseline", budget) != manifest.get("files"):
            raise SourceError("baseline_integrity")
        return manifest

    def reopen(self, job_id: str, record: dict, budget: Budget) -> Workspace:
        workspace = Workspace(job_id, record["workspace_id"], record["sha"],
                              record["manifest_digest"], record["profile_digest"])
        self.verify(workspace, budget)
        return workspace

    def create_attempt(self, workspace: Workspace, attempt: int, budget: Budget) -> Path:
        if type(attempt) is not int or not 1 <= attempt <= 10:
            raise SourceError("attempt")
        manifest = self.verify(workspace, budget)
        # Generations never reuse paths: an expired owner cannot overwrite/delete
        # a newer owner's copy, even when both refer to the same logical attempt.
        generation = f"{attempt:02d}-{uuid.uuid4().hex}"
        target = self.path(workspace) / "attempts" / generation
        no_links(target)
        target.mkdir()
        try:
            for name, expected in manifest["files"].items():
                budget.remaining()
                source = self.path(workspace) / "baseline" / name
                no_links(source)
                with source.open("rb") as input_file:
                    data = input_file.read(self.limits.file_bytes + 1)
                if hashlib.sha256(data).hexdigest() != expected["sha256"]:
                    raise SourceError("baseline_integrity")
                destination = target.joinpath(*safe_path(name).split("/"))
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("xb") as output:
                    output.write(data)
            self.verify(workspace, budget)
            with (target.parent / f"{generation}.json").open("xb") as metadata:
                metadata.write(canonical({"sha": workspace.sha,
                                          "manifest_digest": workspace.manifest_digest,
                                          "profile_digest": workspace.profile_digest}))
            return target
        except (SourceError, OSError):
            self._delete(target, self.path(workspace))
            raise

    def _scan_cleanup(self, path: Path, base: Path):
        no_links(path)
        resolved = path.resolve()
        if not resolved.is_relative_to(base) or resolved == base:
            raise SourceError("cleanup_escape")
        for file in path.iterdir():
            no_links(file)
            if file.is_dir():
                self._scan_cleanup(file, base)
            elif not stat.S_ISREG(file.lstat().st_mode) or file.lstat().st_nlink != 1:
                raise SourceError("filesystem_link")

    def cleanup_attempt(self, workspace: Workspace, attempt: Path):
        root = self.path(workspace) / 'attempts'
        no_links(attempt)
        if attempt.parent != root or not re.fullmatch(r'\d{2}-[0-9a-f]{32}', attempt.name):
            raise SourceError('unowned_attempt')
        sidecar = root / (attempt.name + '.json')
        if self._json(sidecar) != {'sha': workspace.sha, 'manifest_digest': workspace.manifest_digest,
                                  'profile_digest': workspace.profile_digest}:
            raise SourceError('attempt_identity')
        self._delete(attempt, self.path(workspace))
        sidecar.unlink()

    def _delete(self, path: Path, base: Path):
        # Verify the complete absolute target tree BEFORE recursive deletion.
        self._scan_cleanup(path, base)

        def remove(folder):
            no_links(folder)
            if folder.resolve() == base or not folder.resolve().is_relative_to(base):
                raise SourceError("cleanup_escape")
            for file in folder.iterdir():
                no_links(file)
                if file.is_dir():
                    remove(file)
                else:
                    file.chmod(stat.S_IREAD | stat.S_IWRITE)
                    file.unlink()
            folder.rmdir()

        remove(path)

    def cleanup(self, workspace: Workspace) -> None:
        target = self.path(workspace)
        self._delete(target, self.root)
