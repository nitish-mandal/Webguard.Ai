"""Authenticated storage API. Handlers never execute repository jobs."""

import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, Path, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.exceptions import HTTPException

from backend.app.api_models import (
    CancelJob,
    CancelResult,
    CreateJob,
    ErrorResponse,
    EventPage,
    EventQuery,
    EventView,
    JobPage,
    JobQuery,
    JobReport,
    JobView,
    Limits,
    Readiness,
    Status,
    decode_cursor,
    encode_cursor,
)
from backend.app.database import MIGRATIONS
from backend.app.domain import Conflict, NotFound
from backend.app.http_security import (
    ORIGINS,
    APIError,
    RequestBoundary,
    check_operator,
    error_response,
    protect_access_logs,
)
from backend.app.jobs import JobService
from backend.app.reports import job_report
from backend.app.settings import Settings, load_settings

JobID = Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]
bearer = HTTPBearer(auto_error=False, scheme_name="OperatorBearer",
                    description="Local AUTH_TOKEN; never a Gemini or GitHub credential.")


def status() -> Status:
    """Conservative capability defaults for non-HTTP callers."""
    return Status()


def database_ready(service: JobService | None) -> bool:
    if service is None:
        return False
    try:
        with service.db.transaction() as connection:
            connection.execute("UPDATE schema_migrations SET applied_at=applied_at WHERE 0")
            versions = [row[0] for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version")]
            connection.execute("SELECT id FROM jobs LIMIT 0")
            connection.execute("SELECT sequence FROM events LIMIT 0")
            connection.execute("SELECT repair_attempt FROM evidence LIMIT 0")
            connection.execute("SELECT patch_digest FROM publications LIMIT 0")
            connection.execute("SELECT workspace_id FROM source_snapshots LIMIT 0")
            connection.execute("SELECT verification_id FROM publication_intents LIMIT 0")
            connection.execute("SELECT next_run_at FROM job_dispatch LIMIT 0")
            connection.execute("SELECT expires_at FROM worker_sessions LIMIT 0")
            return versions == list(range(1, len(MIGRATIONS) + 1))
    except (sqlite3.Error, OSError):
        return False


def job_view(service: JobService, row: dict) -> JobView:
    public = {key: row[key] for key in set(JobView.model_fields) - {"limits"}}
    public["limits"] = {key: row["max_" + key] for key in Limits.model_fields}
    return JobView.model_validate(service.redactor.clean(public))


EVENT_FIELDS = {
    "created": {"state"}, "state_changed": {"from", "to", "reason"},
    "lease_claimed": {"reclaimed"}, "lease_released": set(), "revision_pinned": {"sha"},
    "usage_reserved": {"model_calls", "model_tokens", "cost_micros", "execution_seconds"},
    "evidence_added": {"evidence_id", "kind", "exit_code"},
    "publication_recorded": {"branch", "pr_number", "draft"},
    "source_acquired": {"sha", "workspace_id", "manifest_digest", "profile_digest"},
    "publication_prepared": {"branch", "simulated", "verification_id"},
    "draft_observed": {"pr_number", "url", "simulated"},
    "draft_pr_recorded": {"pr_number", "commit_sha", "simulated", "draft"},
    "publication_blocked": {"reason", "branch", "simulated"},
    "publication_retryable": {"reason", "branch", "simulated"},
    "worker_stage": {"stage"}, "worker_cleanup": {"attempts_removed"}, "worker_resumed": set(),
    "worker_deferred": {"reason", "paused", "next_run_at"},
    "terminal_publication_reconciled": {"pr_number", "url", "simulated", "observation"},
}


def create_app(settings: Settings | None = None) -> FastAPI:
    protect_access_logs()
    @asynccontextmanager
    async def lifespan(application):
        protect_access_logs()
        configured = settings if settings is not None else load_settings()
        application.state.settings = configured
        try:
            application.state.jobs = JobService(configured)
        except (sqlite3.Error, OSError, RuntimeError):
            # Alive but unready; fix storage and restart. No in-memory acceptance.
            application.state.jobs = None
        yield
        application.state.jobs = None
        application.state.settings = None

    application = FastAPI(title="WebGuard-AI job API", version="0.1.0", lifespan=lifespan,
                          redirect_slashes=False, swagger_ui_parameters={"persistAuthorization": False})
    application.state.settings = None
    application.state.jobs = None
    application.add_middleware(CORSMiddleware, allow_origins=list(ORIGINS),
                               allow_methods=["GET", "POST"], allow_credentials=False,
                               allow_headers=["Content-Type", "Authorization", "Idempotency-Key"],
                               expose_headers=["Location"])
    application.add_middleware(RequestBoundary)

    @application.exception_handler(APIError)
    async def api_error(request, error):
        return error_response(error.status, error.code, error.message)

    @application.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        return error_response(422, "invalid_input", "Request fields are invalid.")

    @application.exception_handler(NotFound)
    async def unknown_job(request, error):
        return error_response(404, "unknown_job", "Job not found.")

    @application.exception_handler(sqlite3.Error)
    @application.exception_handler(OSError)
    async def storage_error(request, error):
        return error_response(503, "storage_unavailable", "Job storage is unavailable.")

    @application.exception_handler(HTTPException)
    async def http_error(request, error):
        code = {404: "not_found", 405: "method_not_allowed"}.get(error.status_code, "http_error")
        return error_response(error.status_code, code, "HTTP request could not be completed.")

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/ready", response_model=Readiness)
    def ready(request: Request, response: Response):
        available = database_ready(request.app.state.jobs)
        response.status_code = 200 if available else 503
        return Readiness(status="ready" if available else "not_ready", database_ready=available)

    @application.get("/api/status", response_model=Status)
    def api_status(request: Request):
        configured = request.app.state.settings
        available = database_ready(request.app.state.jobs)
        if configured is None:
            return status()
        live = configured.enable_live_gemini or configured.enable_github_draft_pr
        worker_available = available and request.app.state.jobs.worker_available()
        return Status(mode="live_configured" if live else "offline", database_ready=available,
                      approved_repository=configured.allowed_repository,
                      worker_available=worker_available, processing_enabled=worker_available,
                      repair_enabled=worker_available,
                      operator_auth_configured=bool(configured.auth_token),
                      job_api_enabled=bool(configured.auth_token) and available,
                      live_gemini_configured=configured.enable_live_gemini,
                      live_github_configured=configured.enable_github_draft_pr)

    def operator(request: Request,
                 credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        check_operator(request.scope)
        if request.app.state.jobs is None:
            raise APIError(503, "storage_unavailable", "Job storage is unavailable.")
        return request.app.state.jobs

    Service = Annotated[JobService, Depends(operator)]
    router = APIRouter(prefix="/api/jobs", responses={
        code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 413, 415, 422, 503)
    })

    @router.post("", status_code=202, response_model=JobView)
    def create_job(payload: CreateJob, service: Service, response: Response,
                   idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1,
                                                          max_length=200, pattern=r"^[!-~]+$")]):
        try:
            row = service.create(idempotency_key, **payload.model_dump())
        except Conflict:
            raise APIError(409, "idempotency_conflict", "Key already used for different input.") from None
        except ValueError:
            raise APIError(422, "invalid_input", "Repository, ref or SHA is not approved or valid.") from None
        response.headers["Location"] = f"/api/jobs/{row['id']}"
        return job_view(service, row)

    @router.get("", response_model=JobPage)
    def list_jobs(service: Service, query: Annotated[JobQuery, Query()]):
        try:
            after = decode_cursor(query.cursor)
        except ValueError:
            raise APIError(422, "invalid_input", "Invalid pagination cursor.") from None
        rows = service.list_jobs(limit=query.limit, after=after, descending=query.order == 'desc')
        return JobPage(items=[job_view(service, row) for row in rows],
                       next_cursor=encode_cursor(rows[-1]) if len(rows) == query.limit else None)

    @router.get("/{job_id}", response_model=JobView)
    def get_job(job_id: JobID, service: Service):
        return job_view(service, service.get(job_id))

    @router.get("/{job_id}/events", response_model=EventPage)
    def job_events(job_id: JobID, service: Service, query: Annotated[EventQuery, Query()]):
        rows = service.events(job_id, after=query.after, limit=query.limit)
        items = []
        for row in rows:
            public = {key: row[key] for key in ("sequence", "created_at", "kind")}
            public["data"] = {key: value for key, value in row["data"].items()
                              if key in EVENT_FIELDS.get(row["kind"], set())}
            items.append(EventView.model_validate(service.redactor.clean(public)))
        return EventPage(items=items,
                         next_cursor=rows[-1]["sequence"] if len(rows) == query.limit else None)

    @router.get('/{job_id}/report', response_model=JobReport)
    def report(job_id: JobID, service: Service):
        return job_report(service, job_id)

    @router.post("/{job_id}/cancel", response_model=CancelResult)
    def cancel_job(job_id: JobID, service: Service, payload: CancelJob | None = None):
        try:
            row = service.cancel(job_id)
        except Conflict:
            raise APIError(409, "terminal_state_conflict", "This terminal outcome cannot be cancelled.") from None
        return CancelResult(job=job_view(service, row))

    application.include_router(router)
    return application


app = create_app()
