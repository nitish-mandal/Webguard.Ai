"""Controller configuration. Never serialize configuration or validation inputs."""

import hmac
import re
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator


class SettingsError(ValueError):
    """Safe configuration failure without rejected values or chained exceptions."""


class Redactor:
    def __init__(self, secrets: tuple[str, ...] = ()):
        self._secrets = tuple(sorted(filter(None, secrets), key=len, reverse=True))

    def __repr__(self) -> str:
        return "Redactor(<configured secrets hidden>)"

    def text(self, value: str) -> str:
        for secret in self._secrets:
            value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"(?i)\bBearer\s+[^\s\"']+", "Bearer [REDACTED]", value)
        value = re.sub(r"(?i)([a-z][a-z0-9+.-]*://)[^/\s@]+@", r"\1[REDACTED]@", value)
        value = re.sub(
            r"(?i)((?:api[_-]?key|token|password|secret|authorization)"
            r"\s*[\"']?\s*[:=]\s*[\"']?)[^\s,;\"'}&]+",
            r"\1[REDACTED]", value,
        )
        return re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9_.-]+|github_pat_[A-Za-z0-9_]+|"
                      r"AIza[A-Za-z0-9_-]{20,})\b", "[REDACTED]", value)

    def clean(self, value):
        if isinstance(value, dict):
            return {
                self.text(str(key)): (
                    "[REDACTED]" if re.search(
                        r"(?i)secret|password|token|credential|authorization|api.?key", str(key)
                    ) and not (str(key) in {"model_tokens", "max_model_tokens"}
                               and type(item) is int) else self.clean(item)
                ) for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self.clean(item) for item in value]
        if isinstance(value, str):
            return self.text(value)
        if value is None or type(value) in (int, float, bool):
            return value
        raise ValueError("Unsupported metadata type")


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    app_env: str = Field(default="development", pattern=r"^(development|test|production)$")
    database_url: str = "sqlite:///./data/webguard.db"
    allowed_repository: str = "demo-repository"
    auth_token: SecretStr | None = Field(default=None, repr=False, exclude=True)
    gemini_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    github_token: SecretStr | None = Field(default=None, repr=False, exclude=True)
    gemini_model: str = Field(default="", max_length=100, pattern=r"^[A-Za-z0-9._/-]*$")
    enable_live_gemini: bool = False
    enable_github_draft_pr: bool = False
    max_repair_attempts: int = Field(default=3, ge=1, le=10)
    max_publication_attempts: int = Field(default=3, ge=1, le=10)
    max_lease_claims: int = Field(default=5, ge=1, le=100)
    job_timeout_seconds: int = Field(default=600, ge=1, le=86400)
    lease_seconds: int = Field(default=30, ge=1, le=300)
    worker_poll_seconds: float = Field(default=1, ge=0.1, le=30)
    worker_retry_seconds: int = Field(default=10, ge=1, le=300)
    max_model_calls_per_job: int = Field(default=3, ge=1, le=100)
    max_model_tokens_per_job: int = Field(default=100000, ge=1, le=10000000)
    max_cost_micros_per_job: int = Field(default=1000000, ge=1, le=1000000000)
    max_execution_seconds: int = Field(default=120, ge=1, le=3600)
    max_output_bytes: int = Field(default=65536, ge=1024, le=1048576)
    max_patch_files: int = Field(default=5, ge=1, le=20)
    max_patch_lines: int = Field(default=200, ge=1, le=2000)
    repair_input_bytes: int = Field(default=16384, ge=1024, le=65536)
    repair_output_bytes: int = Field(default=16384, ge=1024, le=65536)
    repair_output_tokens: int = Field(default=2048, ge=128, le=8192)
    repair_call_seconds: int = Field(default=20, ge=1, le=120)
    # SDK HTTP timeout cap; runtime also clamps it below the remaining process deadline.
    repair_http_timeout_seconds: int = Field(default=15, ge=1, le=110)
    repair_max_retries: int = Field(default=1, ge=0, le=2)
    repair_cost_micros_per_call: int = Field(default=100000, ge=1, le=1000000000)
    publication_seconds: int = Field(default=30, ge=5, le=120)
    publication_request_seconds: int = Field(default=5, ge=1, le=20)
    publication_max_requests: int = Field(default=40, ge=10, le=100)
    publication_response_bytes: int = Field(default=1048576, ge=1024, le=8388608)
    publication_request_bytes: int = Field(default=2097152, ge=1024, le=16777216)
    workspace_root: str = Field(default="workspaces", min_length=1, max_length=500)
    source_timeout_seconds: int = Field(default=20, ge=1, le=300)
    source_max_file_bytes: int = Field(default=1048576, ge=1, le=10485760)
    source_max_total_bytes: int = Field(default=10485760, ge=1, le=104857600)
    source_max_files: int = Field(default=1000, ge=1, le=10000)
    source_max_archive_bytes: int = Field(default=10485760, ge=1, le=104857600)
    source_max_metadata_bytes: int = Field(default=1048576, ge=128, le=10485760)
    runner_image_id: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    runner_cpu_millis: int = Field(default=1000, ge=100, le=4000)
    runner_memory_mib: int = Field(default=256, ge=64, le=4096)
    runner_pids: int = Field(default=64, ge=16, le=512)
    runner_scratch_mib: int = Field(default=128, ge=16, le=1024)
    runner_tmp_mib: int = Field(default=16, ge=1, le=256)
    runner_wall_seconds: int = Field(default=30, ge=1, le=300)
    runner_control_seconds: int = Field(default=10, ge=1, le=60)

    @model_validator(mode="after")
    def validate_controller(self):
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,37}[a-z0-9])?/"
                            r"[a-z0-9][a-z0-9_.-]{0,99}",
                            self.allowed_repository) and self.allowed_repository != "demo-repository":
            raise ValueError("Repository must be canonical lowercase owner/name or demo-repository")
        if any(part in (".", "..") for part in self.allowed_repository.split("/")):
            raise ValueError("Invalid repository")
        if self.allowed_repository.endswith((".git", ".")):
            raise ValueError("Repository must not include a Git suffix or trailing dot")
        if ("\x00" in self.workspace_root or self.workspace_root.startswith(("//", "\\\\"))
                or ".." in Path(self.workspace_root).parts
                or Path(self.workspace_root) == Path(Path(self.workspace_root).anchor)):
            raise ValueError("Invalid workspace root")
        if (not self.database_url.startswith("sqlite:///")
                or not self.database_url[10:] or "?" in self.database_url
                or "\x00" in self.database_url or ":memory:" in self.database_url
                or "@" in self.database_url or self.database_url[10:].startswith(("//", "\\\\"))):
            raise ValueError("A file-backed SQLite URL is required")
        if self.auth_token and not re.fullmatch(r"[!-~]{32,256}", self.auth_token.get_secret_value()):
            raise ValueError("Auth token requires 32-256 visible ASCII characters")
        if self.runner_scratch_mib + self.runner_tmp_mib + 1 >= self.runner_memory_mib:
            raise ValueError("Runner scratch must fit within the memory policy")
        if self.app_env == "production" and not self.auth_token:
            raise ValueError("Production requires operator authentication")
        if self.enable_live_gemini and not (self.gemini_api_key and self.gemini_model):
            raise ValueError("Live Gemini requires credentials and a selected model")
        if self.enable_github_draft_pr and not (
            self.github_token and self.allowed_repository != "demo-repository"
        ):
            raise ValueError("Live publication requires credentials and an approved owner/name")
        if (self.enable_live_gemini or self.enable_github_draft_pr) and not self.auth_token:
            raise ValueError("Live operations require operator authentication")
        redactor = self.redactor()
        if any(redactor.text(value) != value for value in
               (self.database_url, self.allowed_repository, self.gemini_model, self.workspace_root)):
            raise ValueError("Sensitive configuration identifier rejected")
        return self

    @property
    def database_path(self) -> Path:
        return Path(self.database_url[10:])

    def redactor(self) -> Redactor:
        return Redactor(tuple(value.get_secret_value() for value in
                              (self.auth_token, self.gemini_api_key, self.github_token) if value))

    def authenticate(self, supplied: str | None) -> bool:
        return bool(self.auth_token and supplied and hmac.compare_digest(
            self.auth_token.get_secret_value().encode(), supplied.encode()
        ))


def load_settings(env_file: Path | str = ".env", environ: Mapping[str, str] | None = None
                  ) -> Settings:
    """Explicit allowlist; environment overrides dotenv. No interpolation of secrets."""
    import os

    try:
        source = dotenv_values(env_file, interpolate=False)
        source.update(os.environ if environ is None else environ)
        values = {}
        for field in Settings.model_fields:
            value = source.get(field.upper())
            if value is not None:
                optional = field.endswith(("token", "api_key")) or field == "runner_image_id"
                values[field] = None if optional and not value else value
        return Settings.model_validate(values)
    except (ValidationError, ValueError, OSError):
        raise SettingsError("Invalid server settings; check configuration fields and limits") from None
