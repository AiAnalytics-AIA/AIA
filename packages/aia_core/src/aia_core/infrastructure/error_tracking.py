"""The error reporter: what broke, grouped and scrubbed, sent to GlitchTip.

GlitchTip speaks Sentry's protocol, so this module drives ``sentry_sdk`` -- the only
place in the codebase that imports it (``tools/layer_check.sh``), lazily, from the
optional ``errors`` extra. Moving to Sentry, or to GlitchTip's hosted plan, is a DSN
change (``.planning/plans/error-tracking.md``).

Off unless ``AIA_ERROR_TRACKING_DSN`` is set: without it :func:`init` installs nothing,
and every function here does nothing. The DSN is the kill switch.

What may leave, decided once for every process:

* the whole event passes AIA's redaction (:mod:`aia_core.infrastructure.redaction`), by
  key and by value shape, in ``before_send`` and ``before_breadcrumb``;
* a request keeps its method, path and two headers (``user-agent``, ``x-request-id``);
  its body, cookies, query string and every other header are dropped;
* an outgoing HTTP breadcrumb keeps scheme, host and path: a query string can carry a
  search a study wrote;
* local variables are never collected (they hold respondent answers and prompts),
  no user, cookie, body, query or model input is collected (``data_collection``), and
  there is no performance tracing.

What is worth an event is the caller's decision (the API: a 500; the worker: a step
left FAILED, an unclassified exception); this module only reports what it is given.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal, cast
from urllib.parse import urlsplit, urlunsplit

from .redaction import redact

__all__ = [
    "DSN_ENV",
    "ErrorTrackingSettings",
    "close",
    "enabled",
    "init",
    "report_exception",
    "report_failure",
    "scrub_breadcrumb",
    "scrub_event",
    "set_tags",
    "tagged",
]

Service = Literal["api", "worker"]

DSN_ENV: Final = "AIA_ERROR_TRACKING_DSN"
_KEPT_HEADERS: Final = frozenset({"user-agent", "x-request-id"})
_DSN_SHAPE: Final = re.compile(r"^https?://[A-Za-z0-9]+@[A-Za-z0-9.\-]+(:\d+)?/\d+$")

_enabled = False


@dataclass(frozen=True)
class ErrorTrackingSettings:
    """Where events go and how they are labelled. ``None`` from :meth:`from_env` is off."""

    dsn: str
    service: Service
    environment: str
    release: str | None

    @classmethod
    def from_env(
        cls, service: Service, environ: Mapping[str, str] | None = None
    ) -> ErrorTrackingSettings | None:
        """Read the reporter's settings; ``None`` when no DSN is set.

        A DSN that is set but malformed is refused (``ValueError``), never ignored: a
        typo would otherwise switch error tracking off without anyone noticing.
        """
        env = os.environ if environ is None else environ
        dsn = env.get(DSN_ENV, "").strip()
        if not dsn:
            return None
        if not _DSN_SHAPE.match(dsn):
            raise ValueError(
                f"{DSN_ENV} is not a DSN of the form http(s)://<key>@<host>[:port]/<project id>"
            )
        return cls(
            dsn=dsn,
            service=service,
            environment=env.get("AIA_ENV", "").strip() or "local",
            release=env.get("AIA_BUILD_SHA", "").strip() or None,
        )


def enabled() -> bool:
    """True once :func:`init` has installed a client."""
    return _enabled


def init(settings: ErrorTrackingSettings | None, *, transport: Any = None) -> bool:
    """Install the reporter for this process. Returns whether it is on.

    ``transport`` replaces the network for tests (a ``sentry_sdk.transport.Transport``).
    """
    global _enabled
    if settings is None:
        return False

    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration

    integrations: list[Any] = [
        # INFO lines become breadcrumbs (what happened just before), ERROR lines events:
        # a `log.exception` anywhere is a failure someone wrote down as one.
        LoggingIntegration(level=logging.INFO, event_level=logging.ERROR, sentry_logs_level=None),
    ]
    if settings.service == "api":
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        # 5xx only: a 4xx is AIA refusing something, which is AIA working.
        integrations += [
            StarletteIntegration(failed_request_status_codes={*range(500, 600)}),
            FastApiIntegration(failed_request_status_codes={*range(500, 600)}),
        ]

    sentry_sdk.init(
        dsn=settings.dsn,
        environment=settings.environment,
        release=settings.release,
        # What integrations collect at all; before_send then redacts what is left.
        data_collection={
            "user_info": False,
            "cookies": {"mode": "off"},
            "http_headers": {"request": {"mode": "allowlist", "terms": sorted(_KEPT_HEADERS)}},
            "http_bodies": [],
            "url_query_params": {"mode": "off"},
            "gen_ai": {"inputs": False, "outputs": False},
            "database_query_data": False,
            "stack_frame_variables": False,
        },
        max_request_body_size="never",
        traces_sample_rate=None,
        auto_enabling_integrations=False,
        integrations=integrations,
        # The SDK types an event as its own TypedDict; the scrubber treats it as the plain
        # JSON object it is.
        before_send=cast(Any, scrub_event),
        before_breadcrumb=scrub_breadcrumb,
        transport=transport,
    )
    sentry_sdk.get_global_scope().set_tag("service", settings.service)
    _enabled = True
    return True


def close() -> None:
    """Flush and uninstall the reporter (tests, and a process on its way out)."""
    global _enabled
    if not _enabled:
        return
    import sentry_sdk

    sentry_sdk.get_client().close(timeout=2)
    sentry_sdk.init()  # no DSN: a client that sends nothing
    _enabled = False


def set_tags(**tags: str | None) -> None:
    """Tag every event the current request or attempt raises from here on."""
    if not _enabled:
        return
    import sentry_sdk

    scope = sentry_sdk.get_isolation_scope()
    for key, value in tags.items():
        if value is not None:
            scope.set_tag(key, value)


@contextlib.contextmanager
def tagged(**tags: str | None) -> Iterator[None]:
    """A scope of its own whose events carry ``tags``; nothing when off."""
    if not _enabled:
        yield
        return
    import sentry_sdk

    with sentry_sdk.isolation_scope() as scope:
        for key, value in tags.items():
            if value is not None:
                scope.set_tag(key, value)
        yield


def report_exception(
    error: BaseException,
    *,
    tags: Mapping[str, str | None] | None = None,
    fingerprint: list[str] | None = None,
) -> None:
    """Report ``error`` with its stack, on top of the current scope's tags."""
    if not _enabled:
        return
    import sentry_sdk

    with sentry_sdk.new_scope() as scope:
        _label(scope, tags, fingerprint)
        sentry_sdk.capture_exception(error)


def report_failure(
    message: str,
    *,
    fingerprint: list[str],
    tags: Mapping[str, str | None] | None = None,
    context: Mapping[str, Any] | None = None,
    level: Literal["error", "warning"] = "error",
) -> None:
    """Report a failure that is not an exception (a step that ended FAILED, say).

    ``fingerprint`` groups it: every event with the same one is one issue.
    """
    if not _enabled:
        return
    import sentry_sdk

    with sentry_sdk.new_scope() as scope:
        _label(scope, tags, fingerprint)
        if context:
            scope.set_context("failure", dict(context))
        sentry_sdk.capture_message(message, level=level)


def _label(
    scope: Any, tags: Mapping[str, str | None] | None, fingerprint: list[str] | None
) -> None:
    for key, value in (tags or {}).items():
        if value is not None:
            scope.set_tag(key, value)
    if fingerprint:
        scope.fingerprint = fingerprint


# ------------------------------------------------------------------ scrubbing --


def scrub_event(event: dict[str, Any], _hint: Any = None) -> dict[str, Any]:
    """The event as it may leave: the request trimmed, everything redacted."""
    request = event.get("request")
    if isinstance(request, dict):
        headers = request.get("headers") or {}
        event["request"] = {
            "method": request.get("method"),
            "url": _without_query(request.get("url")),
            "headers": {k: v for k, v in dict(headers).items() if k.lower() in _KEPT_HEADERS},
        }
    for value in (event.get("exception") or {}).get("values") or []:
        for frame in (value.get("stacktrace") or {}).get("frames") or []:
            frame.pop("vars", None)
    scrubbed: dict[str, Any] = redact(event)
    return scrubbed


def scrub_breadcrumb(crumb: dict[str, Any], _hint: Any = None) -> dict[str, Any]:
    """A breadcrumb as it may leave: an outgoing URL without its query, all redacted."""
    data = crumb.get("data")
    if isinstance(data, dict) and "url" in data:
        data["url"] = _without_query(data["url"])
        data.pop("http.query", None)
        data.pop("http.fragment", None)
    scrubbed: dict[str, Any] = redact(crumb)
    return scrubbed


def _without_query(url: Any) -> Any:
    if not isinstance(url, str):
        return url
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
