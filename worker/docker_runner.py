"""Explicit Docker-only test execution; there is deliberately no host fallback."""

import hashlib
import io
import re
import tarfile
import threading
import time
import uuid
from datetime import UTC, datetime

from backend.app.settings import Redactor
from worker.check_policy import check_command
from worker.docker_client import DockerCLI, DockerFault
from worker.docker_policy import (
    MANAGED,
    check_container,
    check_daemon,
    check_image,
    check_volume,
    create_arguments,
    labels,
    resource_name,
)
from worker.runner_models import Outcome, RunInput, RunnerLimits, RunResult
from worker.source_common import Budget, SourceError, identifier, no_links, safe_path
from worker.workspaces import DEMO_PROFILE, canonical


def output_text(data, redactor, truncated):
    text = data.decode("utf8", errors="replace")
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    text = "".join(char for char in text if char in "\n\t" or ord(char) >= 32)
    text = redactor.text(text)
    if truncated:
        # A capture boundary must not reveal a configured secret's partial prefix.
        for secret in redactor._secrets:
            for length in range(min(len(secret) - 1, len(text)), 0, -1):
                if text.endswith(secret[:length]):
                    text = text[:-length] + "[REDACTED]"
                    break
    return text


class DockerRunner:
    def __init__(self, manager, image_id=None, limits=None, profile=DEMO_PROFILE,
                 redactor=None, client=None):
        self.manager, self.image_id, self.profile = manager, image_id, profile
        self.limits = limits if limits is not None else RunnerLimits()
        self.redactor = redactor if redactor is not None else Redactor()
        self.client = client if client is not None else DockerCLI(self.limits.control_seconds)
        self.active = set()
        self.lock = threading.Lock()

    @classmethod
    def configured(cls, manager, settings, **kwargs):
        limits = RunnerLimits(
            cpu_millis=settings.runner_cpu_millis, memory_mib=settings.runner_memory_mib,
            pids=settings.runner_pids, scratch_mib=settings.runner_scratch_mib,
            tmp_mib=settings.runner_tmp_mib, wall_seconds=settings.runner_wall_seconds,
            output_bytes=settings.max_output_bytes, control_seconds=settings.runner_control_seconds,
        )
        return cls(manager, settings.runner_image_id, limits, redactor=settings.redactor(), **kwargs)

    def preflight(self):
        info = self.client.document(["info", "--format", "{{json .}}"])
        check_daemon(info)
        if not self.image_id or not re.fullmatch(r"sha256:[0-9a-f]{64}", self.image_id):
            raise DockerFault("image_not_configured")
        image = self.client.inspect("image", self.image_id)
        check_image(image, self.image_id, self.profile, info, self.redactor)
        return self.image_id

    def _package(self, request):
        if request.kind not in ("baseline", "verification", 'control') or (request.kind == 'control' and request.check != 'regression'):
            raise DockerFault("invalid_input")
        identifier(request.workspace.job_id)
        if request.workspace.profile_digest != self.profile.digest:
            raise DockerFault("profile_mismatch")
        budget = Budget(self.manager.limits.seconds)
        manifest = self.manager.verify(request.workspace, budget)
        root = self.manager.path(request.workspace) / "attempts"
        attempt = request.attempt.absolute()
        no_links(attempt)
        if (attempt.parent != root or not re.fullmatch(r"\d{2}-[0-9a-f]{32}", attempt.name)
                or attempt.resolve().parent != root.resolve()):
            raise DockerFault("unowned_attempt")
        record = self.manager._json(root / f"{attempt.name}.json")
        if record != {"sha": request.workspace.sha, "manifest_digest": request.workspace.manifest_digest,
                      "profile_digest": request.workspace.profile_digest}:
            raise DockerFault("attempt_identity")
        actual = self.manager._inventory(attempt, budget)
        check_command(self.profile.test_command, request.check, request.test_id, actual)
        if actual.keys() != manifest["files"].keys():
            raise DockerFault("source_changes")
        changed = {name for name in actual if actual[name] != manifest["files"][name]}
        if changed and (request.kind != "verification" or changed - set(self.profile.source_edit_allowlist)):
            raise DockerFault("source_changes")
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
            folders = {"source"}
            for name in actual:
                parts = name.split("/")
                folders.update("source/" + "/".join(parts[:i]) for i in range(1, len(parts)))
            for name in sorted(folders):
                item = tarfile.TarInfo(name)
                item.type, item.mode, item.uid, item.gid = tarfile.DIRTYPE, 0o555, 10001, 10001
                archive.addfile(item)
            for name, expected in sorted(actual.items()):
                budget.remaining()
                source = attempt.joinpath(*safe_path(name).split("/"))
                no_links(source)
                with source.open("rb") as stream:
                    data = stream.read(self.manager.limits.file_bytes + 1)
                if len(data) != expected["size"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
                    raise DockerFault("source_changed_during_transfer")
                item = tarfile.TarInfo("source/" + name)
                item.mode, item.uid, item.gid, item.size = 0o444, 10001, 10001, len(data)
                archive.addfile(item, io.BytesIO(data))
            data = canonical({"schema": 1, "sha": request.workspace.sha,
                              "manifest_digest": request.workspace.manifest_digest,
                              "profile_digest": self.profile.digest, "files": actual,
                              'check': {'name': request.check, 'test_id': request.test_id}})
            item = tarfile.TarInfo("manifest.json")
            item.mode, item.uid, item.gid, item.size = 0o444, 10001, 10001, len(data)
            archive.addfile(item, io.BytesIO(data))
        if buffer.tell() > self.manager.limits.total_bytes + self.manager.limits.files * 4096 + 2097152:
            raise DockerFault("input_limit")
        patch_digest = hashlib.sha256(canonical({"baseline_manifest": request.workspace.manifest_digest,
                                                 "files": actual})).hexdigest()
        return buffer.getvalue(), patch_digest if request.kind == "verification" else None

    def _remove_container(self, name, job, run, role):
        document = self.client.inspect("container", name, optional=True)
        if document is None:
            return
        expected = labels(self.manager.owner, job, run, role)
        if (document.get("Name") != "/" + name
                or any((document.get("Config", {}).get("Labels") or {}).get(key) != value
                       for key, value in expected.items())
                or not re.fullmatch(r"[0-9a-f]{64}", document.get("Id", ""))):
            raise DockerFault("cleanup_identity")
        self.client.command(["container", "rm", "--force", document["Id"]])
        if self.client.inspect("container", name, optional=True) is not None:
            raise DockerFault("cleanup_failed")

    def _cleanup(self, job, run, retain_source=False):
        okay = True
        for role in ("test", "stage"):
            try:
                self._remove_container(resource_name(self.manager.owner, run, role), job, run, role)
            except DockerFault:
                okay = False
        try:
            name = resource_name(self.manager.owner, run, "source")
            if retain_source:
                # A timed-out create/copy may still be in flight at the daemon.
                # Keep the labelled source volume until explicit recovery, so a
                # late create cannot silently recreate it without ownership labels.
                return False
            volume = self.client.inspect("volume", name, optional=True)
            if volume is not None:
                check_volume(volume, self.manager.owner, job, run)
                self.client.command(["volume", "rm", name])
                if self.client.inspect("volume", name, optional=True) is not None:
                    okay = False
        except DockerFault:
            okay = False
        return okay

    def run(self, request: RunInput, cancelled=None) -> RunResult:
        started = time.monotonic()
        run = uuid.uuid4().hex
        workspace = request.workspace
        result = RunResult(run, workspace.job_id, workspace.sha, workspace.manifest_digest,
                           workspace.profile_digest)
        result.check = request.check
        resources = False
        uncertain = False
        capture = None
        owner, job = self.manager.owner, workspace.job_id
        volume = resource_name(owner, run, "source")
        stage, target = (resource_name(owner, run, role) for role in ("stage", "test"))
        with self.lock:
            self.active.add(run)
        try:
            if cancelled and cancelled():
                result.outcome, result.reason = Outcome.CANCELLED, "cancelled_before_start"
                return result
            result.image_id = self.preflight()
            payload, result.patch_digest = self._package(request)
            result.command = check_command(self.profile.test_command, request.check, request.test_id)
            result.input_digest = hashlib.sha256(payload).hexdigest()
            if cancelled and cancelled():
                result.outcome, result.reason = Outcome.CANCELLED, "cancelled_before_start"
                return result
            arguments = ["volume", "create", "--driver=local"]
            for key, value in labels(owner, job, run, "source").items():
                arguments += ["--label", f"{key}={value}"]
            resources = True  # Create can succeed at the daemon even if the CLI times out.
            self.client.command([*arguments, volume])
            check_volume(self.client.inspect("volume", volume), owner, job, run)
            self.client.command(create_arguments(self.image_id, owner, job, run, "stage", volume, self.limits))
            check_container(self.client.inspect("container", stage), self.image_id, owner, job, run,
                            "stage", volume, self.limits)
            self.client.command(["container", "start", stage])
            if self.client.inspect("container", stage).get("State", {}).get("Running") is not True:
                raise DockerFault("stage_failed")
            self.client.command(["container", "cp", "--quiet", "--archive", "-", f"{stage}:/input"], payload)
            self._remove_container(stage, job, run, "stage")
            if cancelled and cancelled():
                result.outcome, result.reason = Outcome.CANCELLED, "cancelled_during_staging"
                return result
            self.client.command(create_arguments(self.image_id, owner, job, run, "test", volume, self.limits))
            document = self.client.inspect("container", target)
            result.effective_settings = check_container(document, self.image_id, owner, job, run,
                                                         "test", volume, self.limits)
            result.container_id = document["Id"]
            if cancelled and cancelled():
                result.outcome, result.reason = Outcome.CANCELLED, "cancelled_before_start"
                return result
            capture = self.client.attach(target, self.limits.output_bytes)
            deadline = time.monotonic() + self.limits.wall_seconds
            forced = None
            while capture.poll() is None:
                if cancelled and cancelled():
                    forced = Outcome.CANCELLED
                elif capture.overflow.is_set():
                    forced = Outcome.OUTPUT_LIMIT
                elif time.monotonic() >= deadline:
                    forced = Outcome.TIMEOUT
                if forced:
                    try:
                        self.client.command(["container", "kill", target])
                    except DockerFault:
                        pass  # Forced removal in finally is still mandatory.
                    break
                time.sleep(0.02)
            attach_exit = capture.finish(self.limits.control_seconds)
            document = self.client.inspect("container", target)
            check_container(document, self.image_id, owner, job, run, "test", volume, self.limits)
            state = document.get("State") or {}
            if state.get("Running") or not state.get("StartedAt", "").startswith("20"):
                raise DockerFault("execution_not_confirmed")
            result.exit_code = state.get("ExitCode")
            if type(result.exit_code) is not int:
                raise DockerFault("execution_not_confirmed")
            try:
                execution_start = datetime.fromisoformat(state["StartedAt"])
                execution_end = datetime.fromisoformat(state["FinishedAt"])
                result.test_duration_seconds = (execution_end - execution_start).total_seconds()
                if result.test_duration_seconds < 0:
                    raise ValueError
            except (ValueError, KeyError):
                raise DockerFault("execution_not_confirmed") from None
            if attach_exit not in (0, result.exit_code) and not forced:
                raise DockerFault("attach_failed")
            if capture.overflow.is_set():
                forced = forced or Outcome.OUTPUT_LIMIT
            if forced == Outcome.CANCELLED:
                result.outcome, result.reason = forced, forced.value
            elif state.get("OOMKilled") is True:
                result.outcome, result.reason = Outcome.OOM, "kernel_oom"
            elif forced:
                result.outcome, result.reason = forced, forced.value
            elif result.exit_code == 124 and result.test_duration_seconds >= self.limits.wall_seconds:
                result.outcome, result.reason = Outcome.TIMEOUT, "image_watchdog_timeout"
            elif state.get("Error"):
                result.outcome, result.reason = Outcome.INFRASTRUCTURE, "container_error"
            elif result.exit_code == 0:
                result.outcome, result.reason = Outcome.PASSED, "pytest_exit_0"
            elif result.exit_code == 1:
                result.outcome, result.reason = Outcome.TEST_FAILURE, "pytest_exit_1"
            elif result.exit_code in (2, 3, 4, 5):
                result.outcome, result.reason = Outcome.TEST_ENVIRONMENT_ERROR, "pytest_environment"
            else:
                result.outcome, result.reason = Outcome.INFRASTRUCTURE, "unexpected_exit"
        except DockerFault as error:
            result.outcome = Outcome.INFRASTRUCTURE if resources else Outcome.BLOCKED
            result.reason = error.code
            uncertain = resources and error.code in (
                "cli_timeout", "cli_io", "cli_failed", "cli_output_limit", "docker_unavailable",
            )
        except (SourceError, OSError, ValueError):
            result.outcome, result.reason = Outcome.INFRASTRUCTURE, "invalid_source_or_storage"
        except Exception:  # noqa: BLE001 - controller callback/raw Docker errors must stay private.
            result.outcome, result.reason = Outcome.INFRASTRUCTURE, "controller_error"
        finally:
            if capture is not None:
                capture.stop()
                try:
                    capture.finish(2)
                except DockerFault:
                    result.outcome, result.reason = Outcome.INFRASTRUCTURE, "attach_cleanup_failed"
                truncated = capture.overflow.is_set()
                # Local import avoids a module cycle with the shared sanitization helper.
                from worker.test_reports import decode_report

                if not truncated:
                    result.test_report = decode_report(bytes(capture.stdout).decode('utf8', errors='replace'),
                                                       result.exit_code, self.redactor)
                stdout = output_text(bytes(capture.stdout), self.redactor, truncated).encode()
                stderr = output_text(bytes(capture.stderr), self.redactor, truncated).encode()
                cap = self.limits.output_bytes
                result.output_truncated = truncated or len(stdout) + len(stderr) > cap
                result.stdout = stdout[:cap].decode("utf8", errors="ignore")
                result.stderr = stderr[:max(0, cap - len(stdout))].decode("utf8", errors="ignore")
            if resources:
                result.cleanup_complete = self._cleanup(job, run, retain_source=uncertain)
                if not result.cleanup_complete:
                    result.outcome, result.reason = Outcome.INFRASTRUCTURE, "cleanup_failed"
            with self.lock:
                self.active.discard(run)
            result.duration_seconds = round(time.monotonic() - started, 6)
        return result

    def recover(self, active_jobs=None, min_age_seconds=300, now=None):
        """Explicit recovery only: caller must quiesce workers or provide active job leases."""
        if not 0 <= min_age_seconds <= 86400:
            raise ValueError("Invalid recovery age")
        now = datetime.now(UTC).timestamp() if now is None else now
        found = {}
        for kind in ("container", "volume"):
            args = [kind, "ls", *( ["--all"] if kind == "container" else []),
                    "--filter", f"label=io.webguard.managed={MANAGED}",
                    "--filter", f"label=io.webguard.owner={self.manager.owner}",
                    "--format", "{{.ID}}" if kind == "container" else "{{.Name}}"]
            for name in self.client.command(args).decode("ascii").splitlines():
                document = self.client.inspect(kind, name)
                metadata = document.get("Config", {}).get("Labels") if kind == "container" else document.get("Labels")
                metadata = metadata or {}
                try:
                    run, job = identifier(metadata.get("io.webguard.run")), identifier(metadata.get("io.webguard.job"))
                    role = metadata.get("io.webguard.role")
                    if (metadata.get("io.webguard.owner") != self.manager.owner
                            or metadata.get("io.webguard.managed") != MANAGED
                            or role not in (("stage", "test") if kind == "container" else ("source",))):
                        continue
                    created = datetime.fromisoformat(document["Created"]).timestamp()
                    expected = resource_name(self.manager.owner, run, role)
                    actual_name = document.get("Name", "").lstrip("/")
                    if actual_name != expected or now - created < min_age_seconds:
                        continue
                except (SourceError, ValueError, KeyError, TypeError):
                    continue
                with self.lock:
                    active = run in self.active
                if active or (active_jobs is not None and active_jobs(job)):
                    continue
                found[run] = job
        return {run: self._cleanup(job, run) for run, job in found.items()}
