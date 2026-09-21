"""Structured logging, request correlation and error translation.

Every log line is JSON with a ``request_id`` so that a support question -- "why did
project X stop during stage Y?" -- can be answered from the log stream alone. The
same id is returned to the client in the ``X-Request-ID`` header and in every error
body.

Secret redaction happens here rather than at each call site, because the one thing
worse than no logs is logs containing an API key.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# Values that must never reach a log sink. Matched on the *key*, so a nested
# payload carrying `{"api_key": "sk-ant-..."}` is redacted regardless of depth.
_SECRET_KEY_PATTERN = re.compile(
    r"(api[_-]?key|secret|token|password|passwd|credential|authorization|cookie|"
    r"anthropic_api_key|openai_api_key)",
    re.IGNORECASE,
)

# Provider key shapes, redacted even when they appear inside a free-text message.
# The `sk-` pattern must allow interior hyphens: current Anthropic and OpenAI keys
# are `sk-ant-api03-...` and `sk-proj-...`, so a character class without `-` stops
# matching at the first separator and leaks the remainder of the key.
_SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9][A-Za-z0-9_\-]{15,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{10,}", re.IGNORECASE),
    # Generic long opaque tokens in an explicit assignment, e.g. `token=...`.
    re.compile(
        r"((?:api[_-]?key|token|secret|password)\s*[=:]\s*)[A-Za-z0-9._\-]{12,}",
        re.IGNORECASE,
    ),
)

REDACTED = "[redacted]"


def redact(value: Any, *, _depth: int = 0) -> Any:
    """Return ``value`` with anything secret-looking replaced.

    Recursion is depth-limited so a cyclic or pathologically nested payload cannot
    hang the logger.
    """
    if _depth > 8:
        return "[truncated]"

    if isinstance(value, dict):
        return {
            key: (
                REDACTED if _SECRET_KEY_PATTERN.search(str(key)) else redact(val, _depth=_depth + 1)
            )
            for key, val in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item, _depth=_depth + 1) for item in value]
    if isinstance(value, str):
        out = value
        for pattern in _SECRET_VALUE_PATTERNS:
            # A pattern with a capture group keeps its prefix (e.g. "token=") so the
            # log line stays readable; the secret itself is replaced.
            replacement = r"\1" + REDACTED if pattern.groups else REDACTED
            out = pattern.sub(replacement, out)
        return out
    return value


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid

        # Structured extras attached via logger.info(..., extra={"context": {...}}).
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload.update(redact(context))

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(redact(payload), ensure_ascii=False, default=str)


def configure_logging(*, level: str = "INFO", fmt: str = "json") -> None:
    """Install the root log handler.

    Existing handlers are replaced so that a re-import during tests or an
    autoreload does not produce duplicated lines.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if fmt == "json"
        else logging.Formatter("%(levelname)s %(name)s %(message)s")
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, level, logging.INFO))

    # Access logs are emitted by our own middleware with richer context.
    logging.getLogger("uvicorn.access").disabled = True


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request id, log the request, and time it.

    An inbound ``X-Request-ID`` is honoured so a trace survives across services,
    but it is length-capped and stripped of anything unexpected so a client cannot
    inject content into the log stream.
    """

    _SAFE_ID = re.compile(r"[^A-Za-z0-9._\-]")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        inbound = request.headers.get("X-Request-ID", "")
        rid = self._SAFE_ID.sub("", inbound)[:64] or uuid.uuid4().hex
        token = request_id_var.set(rid)
        logger = logging.getLogger("aia.request")
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request failed",
                extra={
                    "context": {
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    }
                },
            )
            raise
        finally:
            request_id_var.reset(token)

        duration = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = rid
        logger.info(
            "request",
            extra={
                "context": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration,
                }
            },
        )
        return response


class ProductionAuthGateMiddleware(BaseHTTPMiddleware):
    """Refuse authenticated routes in production until a real verifier is wired up.

    This lives in middleware rather than in a dependency because dependency
    resolution order is an implementation detail of the framework: FastAPI may
    enter a generator dependency (which opens a database session) before it runs
    the plain dependency that checks identity. A security gate must not depend on
    that ordering, so it runs here, before routing and before any dependency is
    resolved.

    Health and readiness probes stay open: an orchestrator has no credentials.
    """

    OPEN_PATHS = ("/api/v1/health", "/api/v1/ready")

    def __init__(self, app: Any, *, enabled: bool) -> None:
        super().__init__(app)
        self._enabled = enabled

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not self._enabled or request.url.path in self.OPEN_PATHS:
            return await call_next(request)

        return _error(
            501,
            "auth_not_configured",
            "No identity provider is configured. Production refuses header-based "
            "identity; wire get_principal to the real verifier.",
        )


def _error(status_code: int, code: str, message: str, details: dict[str, Any] | None = None):
    """Build the standard error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "details": redact(details or {}),
            "request_id": request_id_var.get() or None,
        },
    )


def install_exception_handlers(app: FastAPI) -> None:
    """Register handlers so every error shares one response shape.

    Unhandled exceptions never return their text to the client: a stack trace or a
    database error string can disclose schema, file paths or credentials. The
    detail goes to the logs, keyed by request id.
    """

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        return _error(
            422,
            "validation_error",
            "The request body or parameters are invalid.",
            {"errors": json.loads(json.dumps(exc.errors(), default=str))},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            return _error(
                exc.status_code,
                str(detail.get("code")),
                str(detail.get("message", "")),
                detail.get("details") if isinstance(detail.get("details"), dict) else {},
            )
        return _error(exc.status_code, f"http_{exc.status_code}", str(detail))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logging.getLogger("aia.error").exception(
            "unhandled exception",
            extra={"context": {"path": request.url.path, "type": type(exc).__name__}},
        )
        return _error(
            500,
            "internal_error",
            "An unexpected error occurred. Quote the request id when reporting it.",
        )
