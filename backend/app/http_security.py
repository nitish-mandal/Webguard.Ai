"""ASGI boundary: authenticate before parsing, cap bodies, never log inputs."""

import json
import logging
from urllib.parse import parse_qsl

from starlette.responses import JSONResponse

ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173",
           "http://localhost:8000", "http://127.0.0.1:8000")
MAX_BODY_BYTES = 16384


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message


def error_response(status: int, code: str, message: str) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status,
                        headers=headers)


def check_operator(scope) -> None:
    settings = getattr(scope["app"].state, "settings", None)
    if settings is None:
        raise APIError(503, "service_not_ready", "Service startup is not complete.")
    if not settings.auth_token:
        raise APIError(503, "auth_not_configured", "Operator authentication is not configured.")
    values = [value for key, value in scope["headers"] if key.lower() == b"authorization"]
    token = None
    if len(values) == 1 and len(values[0]) <= 263:
        parts = values[0].split(b" ")
        if len(parts) == 2 and parts[0].lower() == b"bearer":
            try:
                token = parts[1].decode("ascii")
            except UnicodeDecodeError:
                pass
    if not settings.authenticate(token):
        raise APIError(401, "unauthorized", "A valid operator bearer token is required.")


class PrivateAccessLogFilter(logging.Filter):
    """Uvicorn access arguments contain the untrusted path and query string."""

    def filter(self, record):
        status = record.args[-1] if isinstance(record.args, tuple) and len(record.args) == 5 else 0
        status = status if type(status) is int and 100 <= status <= 599 else 0
        record.msg = '%s - "%s %s HTTP/%s" %d'
        record.args = ("local-client", "HTTP", "[request-target-omitted]", "1.1", status)
        record.exc_info = record.exc_text = record.stack_info = None
        return True


def protect_access_logs():
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, PrivateAccessLogFilter) for item in logger.filters):
        logger.addFilter(PrivateAccessLogFilter())


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Nonfinite JSON number")


class RequestBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def safe_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                message["headers"] = [(key, value) for key, value in message.get("headers", [])
                                      if key.lower() not in (b"cache-control", b"x-content-type-options")] + [
                    (b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff"),
                ]
                origins = [value for key, value in scope["headers"] if key.lower() == b"origin"]
                if (len(origins) == 1 and origins[0].decode("latin1") in ORIGINS
                        and not any(key.lower() == b"access-control-allow-origin"
                                    for key, _ in message["headers"])):
                    # Boundary errors must remain readable by the approved future UI.
                    message["headers"] += [(b"access-control-allow-origin", origins[0]),
                                           (b"vary", b"Origin")]
            await send(message)

        try:
            path = scope["path"]
            headers = scope["headers"]
            if sum(len(key) + len(value) for key, value in headers) > 16384:
                raise APIError(431, "headers_too_large", "Request headers exceed the limit.")
            hosts = [value.decode("latin1") for key, value in headers if key.lower() == b"host"]
            if len(hosts) != 1 or hosts[0].split(":")[0] not in ("127.0.0.1", "localhost"):
                raise APIError(400, "invalid_host", "A loopback host is required.")
            if len(scope.get("raw_path", b"")) + len(scope.get("query_string", b"")) > 2048:
                raise APIError(414, "request_target_too_large", "Request target exceeds the limit.")
            protected = path == "/api/jobs" or path.startswith("/api/jobs/")
            preflight = scope["method"] == "OPTIONS" and any(
                key.lower() == b"origin" for key, _ in headers
            ) and any(key.lower() == b"access-control-request-method" for key, _ in headers)
            if protected and not preflight:
                origins = [value.decode("latin1") for key, value in headers if key.lower() == b"origin"]
                if origins and (len(origins) != 1 or origins[0] not in ORIGINS):
                    raise APIError(403, "forbidden_origin", "Browser origin is not allowed.")
                check_operator(scope)
                query = parse_qsl(scope.get("query_string", b"").decode("latin1"), keep_blank_values=True)
                keys = [key for key, _ in query]
                if len(keys) != len(set(keys)):
                    raise APIError(422, "invalid_input", "Duplicate query parameters are not allowed.")
                allowed = {"limit", "cursor", "order"} if path == "/api/jobs" else (
                    {"limit", "after"} if path.endswith("/events") else set())
                if set(keys) - allowed:
                    raise APIError(422, "invalid_input", "Unknown query parameter.")
                if scope["method"] == "POST" and query:
                    raise APIError(422, "invalid_input", "Mutation query parameters are not allowed.")
            lengths = [value for key, value in headers if key.lower() == b"content-length"]
            encoding = [value.lower() for key, value in headers if key.lower() == b"content-encoding"]
            if len(lengths) > 1 or (lengths and any(key.lower() == b"transfer-encoding" for key, _ in headers)):
                raise APIError(400, "invalid_request", "Ambiguous request framing.")
            if encoding and encoding != [b"identity"]:
                raise APIError(415, "unsupported_media_type", "Encoded request bodies are not supported.")
            declared = None
            if lengths:
                if not lengths[0].isdigit():
                    raise APIError(400, "invalid_request", "Invalid request length.")
                if len(lengths[0]) > 6:
                    raise APIError(413, "request_too_large", "Request body exceeds 16384 bytes.")
                declared = int(lengths[0])
                if declared > MAX_BODY_BYTES:
                    raise APIError(413, "request_too_large", "Request body exceeds 16384 bytes.")
            chunks = []
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > MAX_BODY_BYTES:
                    raise APIError(413, "request_too_large", "Request body exceeds 16384 bytes.")
                if chunk:
                    chunks.append(chunk)
                if not message.get("more_body", False):
                    break
            if declared is not None and declared != size:
                raise APIError(400, "invalid_request", "Request length does not match body.")
            body = b"".join(chunks)
            if protected and scope["method"] == "POST":
                if path == "/api/jobs":
                    keys = [value for key, value in headers if key.lower() == b"idempotency-key"]
                    if len(keys) != 1:
                        raise APIError(422, "invalid_input", "One Idempotency-Key header is required.")
                if body:
                    types = [value.split(b";", 1)[0].lower() for key, value in headers
                             if key.lower() == b"content-type"]
                    if types != [b"application/json"]:
                        raise APIError(415, "unsupported_media_type", "Use application/json.")
                    try:
                        json.loads(body.decode("utf8"), object_pairs_hook=_object, parse_constant=_constant)
                    except (ValueError, UnicodeError, RecursionError):
                        raise APIError(422, "invalid_input", "Invalid JSON request.") from None

            async def replay():
                return {"type": "http.request", "body": body, "more_body": False}

            await self.app(scope, replay, safe_send)
        except APIError as error:
            if not started:
                await error_response(error.status, error.code, error.message)(scope, receive, safe_send)
        except Exception:  # noqa: BLE001 - public boundary must not leak raw exception text.
            # Never let raw inputs, SQL messages or provider exceptions reach logs.
            if not started:
                await error_response(500, "internal_error", "Request could not be completed.")(
                    scope, receive, safe_send)
