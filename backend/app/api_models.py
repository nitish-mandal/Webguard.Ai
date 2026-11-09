"""Public API shapes; database rows and settings are never responses."""

import base64
import json
import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain import FailureReason, JobState


class CreateJob(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    repository: str = Field(min_length=1, max_length=140,
                            pattern=r"^(demo-repository|[a-z0-9][a-z0-9-]{0,38}/[a-z0-9][a-z0-9_.-]{0,99})$")
    ref: str = Field(default="main", min_length=1, max_length=200,
                     pattern=r"^[A-Za-z0-9][A-Za-z0-9_./-]*$")
    sha: str | None = Field(default=None, pattern=r"^([0-9a-f]{40}|[0-9a-f]{64})$")


class CancelJob(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class JobQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=256, pattern=r"^[A-Za-z0-9_-]+$")
    order: Literal['asc', 'desc'] = 'asc'


class EventQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=50, ge=1, le=100)
    after: int = Field(default=0, ge=0, le=9223372036854775807)


class Limits(BaseModel):
    repair_attempts: int
    publication_attempts: int
    model_calls: int
    model_tokens: int
    cost_micros: int
    execution_seconds: int
    output_bytes: int
    patch_files: int
    patch_lines: int


class JobView(BaseModel):
    id: str
    repository: str
    ref: str
    sha: str | None
    state: JobState
    created_at: float
    updated_at: float
    deadline: float
    failure_reason: FailureReason | None
    cancellation_requested: bool
    cancelled_at: float | None
    repair_attempts: int
    publication_attempts: int
    model_calls: int
    model_tokens: int
    cost_micros: int
    execution_seconds: int
    version: int
    limits: Limits


class JobPage(BaseModel):
    items: list[JobView]
    next_cursor: str | None


class EventView(BaseModel):
    sequence: int
    created_at: float
    kind: str
    data: dict


class EventPage(BaseModel):
    items: list[EventView]
    next_cursor: int | None


class CancelResult(BaseModel):
    job: JobView
    execution_stop_confirmed: Literal[False] = False
    message: str = "Cancellation persisted. No executor stop has been confirmed."


class Status(BaseModel):
    api_version: Literal["v1"] = "v1"
    mode: Literal["offline", "live_configured"] = "offline"
    repair_enabled: bool = False
    processing_enabled: bool = False
    worker_available: bool = False
    approved_repository: str | None = None
    job_api_enabled: bool = False
    database_ready: bool = False
    operator_auth_configured: bool = False
    live_gemini_configured: bool = False
    live_github_configured: bool = False
    message: str = "HTTP stores jobs; a separately started worker processes them. Availability uses worker heartbeats, not Docker readiness."


class Readiness(BaseModel):
    status: Literal["ready", "not_ready"]
    database_ready: bool


class ObservationView(BaseModel):
    exit_code: int | None = None
    duration_seconds: float | None = None
    image_id: str | None = None


class DetectionView(BaseModel):
    verdict: str | None = None
    evidence_available: bool = False
    node_id: str | None = None
    expected: str | None = None
    actual: str | None = None
    message: str | None = None
    traceback: str | None = None
    observations: list[ObservationView] = Field(default_factory=list, max_length=2)


class CheckView(BaseModel):
    name: str
    exit_code: int | None = None
    passed: int
    failed: int
    command: list[str] = Field(default_factory=list, max_length=32)


class VerificationView(BaseModel):
    round: int
    status: str
    reason: str | None = None
    image_id: str
    patch_digest: str
    evidence_available: bool
    checks: list[CheckView] = Field(default_factory=list, max_length=4)


class PublicationView(BaseModel):
    simulated: bool
    confirmed: bool
    draft: bool = True
    branch: str
    commit_sha: str | None = None
    pr_number: int | None = None
    live_url: str | None = None
    reason: str | None = None


class JobReport(BaseModel):
    version: int
    stage: str | None = None
    paused: bool = False
    reason: str | None = None
    next_run_at: float | None = None
    cleanup_completed: bool = False
    detection: DetectionView = Field(default_factory=DetectionView)
    verifications: list[VerificationView] = Field(default_factory=list, max_length=10)
    publication: PublicationView | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def encode_cursor(row: dict) -> str:
    value = json.dumps([row["created_at"], row["id"]], separators=(",", ":"))
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def decode_cursor(value: str | None) -> tuple[float, str] | None:
    if value is None:
        return None
    try:
        decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        items = json.loads(decoded)
        if (not isinstance(items, list) or len(items) != 2
                or type(items[0]) not in (int, float) or not math.isfinite(items[0])
                or not 0 <= items[0] <= 253402300799
                or not isinstance(items[1], str) or not re.fullmatch(r"[0-9a-f]{32}", items[1])):
            raise ValueError
        return float(items[0]), items[1]
    except (ValueError, TypeError, OverflowError):
        raise ValueError("Invalid pagination cursor") from None
