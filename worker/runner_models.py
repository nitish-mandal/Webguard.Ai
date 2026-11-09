"""Structured runner contracts. A runner/infrastructure failure is not a code bug."""

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path

from worker.workspaces import Workspace


class Outcome(StrEnum):
    PASSED = "passed"
    TEST_FAILURE = "test_failure"
    TEST_ENVIRONMENT_ERROR = "test_environment_error"
    TIMEOUT = "timeout"
    OOM = "oom"
    OUTPUT_LIMIT = "output_limit"
    CANCELLED = "cancelled"
    INFRASTRUCTURE = "infrastructure_error"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class RunnerLimits:
    cpu_millis: int = 1000
    memory_mib: int = 256
    pids: int = 64
    scratch_mib: int = 128
    tmp_mib: int = 16
    wall_seconds: int = 30
    output_bytes: int = 65536
    control_seconds: int = 10

    def __post_init__(self):
        ranges = {"cpu_millis": (100, 4000), "memory_mib": (64, 4096), "pids": (16, 512),
                  "scratch_mib": (16, 1024), "tmp_mib": (1, 256), "wall_seconds": (1, 300),
                  "output_bytes": (1024, 1048576), "control_seconds": (1, 60)}
        if any(type(getattr(self, key)) is not int or not low <= getattr(self, key) <= high
               for key, (low, high) in ranges.items()) or self.scratch_mib + self.tmp_mib + 1 >= self.memory_mib:
            raise ValueError("Invalid runner resource policy")


@dataclass(frozen=True)
class RunInput:
    workspace: Workspace
    attempt: Path
    kind: str = "baseline"
    check: str = 'suite'
    test_id: str | None = None


@dataclass
class RunResult:
    run_id: str
    job_id: str
    source_sha: str | None
    source_manifest_digest: str | None
    profile_digest: str | None
    input_digest: str | None = None
    patch_digest: str | None = None
    outcome: Outcome = Outcome.INFRASTRUCTURE
    reason: str = "not_started"
    exit_code: int | None = None
    duration_seconds: float = 0
    test_duration_seconds: float | None = None
    stdout: str = ""
    stderr: str = ""
    output_truncated: bool = False
    image_id: str | None = None
    container_id: str | None = None
    effective_settings: dict = field(default_factory=dict)
    cleanup_complete: bool = True
    test_report: dict | None = None
    command: list[str] = field(default_factory=list)
    check: str = 'suite'

    def document(self):
        return asdict(self)
