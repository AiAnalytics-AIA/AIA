"""Structured logging, request correlation and error translation.

Every log line is JSON with a ``request_id`` so that a support question -- "why did
project X stop during stage Y?" -- can be answered from the log stream alone. The
same id is returned to the client in the ``X-Request-ID`` header and in every error
body.

Secret redaction happens here rather than at each call site, because the one thing
worse than no logs is logs containing an API key. The patterns are
``aia_core.infrastructure.redaction``'s, shared with the worker and the error reporter.
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

from aia_core.infrastructure import error_tracking
from aia_core.infrastructure.redaction import REDACTED, redact
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

__all__ = ["REDACTED", "redact", "request_id_var"]

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


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
        # Every event this request raises names it, so an issue opens its log lines.
        error_tracking.set_tags(request_id=rid)
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


def _error(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build the standard error response.

    ``headers`` is propagated because some errors carry protocol-significant
    headers -- notably ``WWW-Authenticate`` on a 401 and ``Retry-After`` on a
    429. Building a fresh response and dropping them silently breaks the
    authentication challenge.
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "details": redact(details or {}),
            "request_id": request_id_var.get() or None,
        },
        headers=headers or None,
    )


def install_exception_handlers(app: FastAPI) -> None:
    """Register handlers so every error shares one response shape.

    Unhandled exceptions never return their text to the client: a stack trace or a
    database error string can disclose schema, file paths or credentials. The
    detail goes to the logs, keyed by request id.
    """

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error(
            422,
            "validation_error",
            "The request body or parameters are invalid.",
            {"errors": json.loads(json.dumps(exc.errors(), default=str))},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Starlette types `detail` as `str`, but FastAPI passes through whatever
        # a handler raised, and ours raise structured dicts. The annotation is
        # widened here so the structured branch below is not treated as dead.
        detail: Any = exc.detail
        headers = getattr(exc, "headers", None)
        if isinstance(detail, dict) and "code" in detail:
            # A refusal raised with a code and no message keeps its code as its message: an
            # empty one reached the screen as nothing at all (PC18; the report card read a
            # missing stored report as "loading" for ever).
            return _error(
                exc.status_code,
                str(detail.get("code")),
                str(detail.get("message") or detail.get("code")),
                detail.get("details") if isinstance(detail.get("details"), dict) else {},
                headers=headers,
            )
        return _error(exc.status_code, f"http_{exc.status_code}", str(detail), headers=headers)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("aia.error").exception(
            "unhandled exception",
            extra={"context": {"path": request.url.path, "type": type(exc).__name__}},
        )
        # The 500 a person saw, with the route it came from (the template, not the ids).
        route = getattr(request.scope.get("route"), "path", None)
        error_tracking.report_exception(
            exc, tags={"request_id": request_id_var.get() or None, "route": route}
        )
        return _error(
            500,
            "internal_error",
            "An unexpected error occurred. Quote the request id when reporting it.",
        )
