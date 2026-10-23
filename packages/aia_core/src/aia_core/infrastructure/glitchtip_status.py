"""GlitchTip read for Settings → Stav systému (settings-backends SB4): the backend project's
open issues of the last seven days, its alert rules and the organization's uptime monitors.

Read with a read-only API token (organization, project and event read) over GlitchTip's
Sentry-compatible API, on the internal network (``http://glitchtip:8000`` on develop). The token
is sent as a bearer header and nowhere else: never logged, never in an error, never returned.
A refusal, a timeout or an answer of an unexpected shape is said as an error code with what was
read before it; it never raises to the caller. No proxy is used: GlitchTip is internal.

The project is the one AIA reports to: the DSN's project id when it names one GlitchTip lists,
else the first project listed. Nothing here writes.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Final
from urllib.parse import quote, urlsplit

__all__ = [
    "AlertRule",
    "ErrorTrackingStatus",
    "Issue",
    "Monitor",
    "dsn_project_id",
    "read_glitchtip",
]

ISSUE_DAYS: Final = 7
_TIMEOUT_S: Final = 5.0
_MAX_ISSUES: Final = 25


@dataclass(frozen=True, slots=True)
class Issue:
    title: str
    culprit: str | None
    #: As GlitchTip counts events; ``None`` when it did not say.
    count: int | None
    last_seen: datetime | None
    url: str | None


@dataclass(frozen=True, slots=True)
class AlertRule:
    name: str
    #: "N events in M minutes", as the rule is set; ``None`` parts not said.
    quantity: int | None
    timespan_minutes: int | None
    recipients: int


@dataclass(frozen=True, slots=True)
class Monitor:
    name: str
    #: ``None``: GlitchTip did not say (never read as up).
    is_up: bool | None
    last_change: datetime | None


@dataclass(slots=True)
class ErrorTrackingStatus:
    project: str | None = None
    project_url: str | None = None
    issues_7d: list[Issue] = field(default_factory=list)
    alerts: list[AlertRule] = field(default_factory=list)
    uptime: list[Monitor] = field(default_factory=list)
    #: False: GlitchTip's uptime monitoring is off (its monitors route answers 404, as with
    #: GLITCHTIP_ENABLE_UPTIME false on develop); ``None``: not read.
    uptime_enabled: bool | None = None
    #: The first thing that could not be read, by code; ``None`` when all of it was read.
    error: str | None = None


def dsn_project_id(dsn: str) -> str | None:
    """The project id a DSN names (its path's last segment), or ``None``."""
    path = urlsplit(dsn.strip()).path.strip("/") if dsn.strip() else ""
    last = path.rsplit("/", 1)[-1] if path else ""
    return last or None


def _when(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


class _Refused(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


Fetch = Callable[[str], Any]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is refused, never followed: urllib would carry the bearer header to
    whatever host the Location names."""

    def redirect_request(self, *_: Any, **__: Any) -> None:
        raise _Refused("glitchtip_redirect")


def _fetcher(api_url: str, token: str) -> Fetch:
    if urlsplit(api_url).scheme not in ("http", "https"):
        raise _Refused("glitchtip_url_invalid")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    base = api_url.rstrip("/")

    def fetch(path: str) -> Any:
        request = urllib.request.Request(
            f"{base}{path}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        try:
            with opener.open(request, timeout=_TIMEOUT_S) as response:
                body = response.read(2_000_000)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise _Refused("glitchtip_refused_token") from None
            raise _Refused(f"glitchtip_http_{exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise _Refused("glitchtip_unreachable") from None
        try:
            return json.loads(body)
        except ValueError:
            raise _Refused("glitchtip_unexpected_answer") from None

    return fetch


def read_glitchtip(
    *,
    token: str,
    api_url: str,
    dashboard_url: str | None,
    project_id: str | None,
    now: datetime,
    fetch: Fetch | None = None,
) -> ErrorTrackingStatus:
    """Read the project's last seven days of open issues, its alert rules and the
    organization's uptime monitors. Each part read before a failure is kept; the failure is
    ``error``."""
    status = ErrorTrackingStatus()
    dashboard = (dashboard_url or "").rstrip("/") or None
    try:
        get = fetch or _fetcher(api_url, token)
        projects = get("/api/0/projects/")
        if not isinstance(projects, list) or not projects:
            raise _Refused("glitchtip_no_project")
        chosen = next(
            (p for p in projects if isinstance(p, dict) and str(p.get("id")) == project_id),
            projects[0],
        )
        organization = (chosen.get("organization") or {}).get("slug")
        slug = chosen.get("slug")
        if not isinstance(organization, str) or not isinstance(slug, str):
            raise _Refused("glitchtip_unexpected_answer")
        status.project = str(chosen.get("name") or slug)
        org_q, slug_q = quote(organization, safe=""), quote(slug, safe="")
        if dashboard:
            status.project_url = f"{dashboard}/{org_q}/issues?project={chosen.get('id')}"

        since = now - timedelta(days=ISSUE_DAYS)
        issues = get(f"/api/0/projects/{org_q}/{slug_q}/issues/?query=is%3Aunresolved")
        if not isinstance(issues, list):
            raise _Refused("glitchtip_unexpected_answer")
        for item in issues:
            if not isinstance(item, dict):
                continue
            seen = _when(item.get("lastSeen"))
            if seen is None or seen < since:
                continue
            issue_id = item.get("id")
            status.issues_7d.append(
                Issue(
                    title=str(item.get("title") or "")[:300],
                    culprit=(str(item["culprit"])[:300] if item.get("culprit") else None),
                    count=_int(item.get("count")),
                    last_seen=seen,
                    url=f"{dashboard}/{org_q}/issues/{quote(str(issue_id), safe='')}"
                    if dashboard and issue_id
                    else None,
                )
            )
        status.issues_7d.sort(key=lambda i: i.last_seen or since, reverse=True)
        del status.issues_7d[_MAX_ISSUES:]

        alerts = get(f"/api/0/projects/{org_q}/{slug_q}/alerts/")
        if not isinstance(alerts, list):
            raise _Refused("glitchtip_unexpected_answer")
        status.alerts = [
            AlertRule(
                name=str(a.get("name") or "")[:200],
                quantity=_int(a.get("quantity")),
                timespan_minutes=_int(a.get("timespanMinutes")),
                recipients=len(a.get("alertRecipients") or []),
            )
            for a in alerts
            if isinstance(a, dict)
        ]

        try:
            monitors = get(f"/api/0/organizations/{org_q}/monitors/")
        except _Refused as refused:
            if refused.code != "glitchtip_http_404":
                raise
            status.uptime_enabled = False  # uptime off in GlitchTip: no failure, nothing to list
            return status
        status.uptime_enabled = True
        if not isinstance(monitors, list):
            raise _Refused("glitchtip_unexpected_answer")
        status.uptime = [
            Monitor(
                name=str(m.get("name") or "")[:200],
                is_up=m.get("isUp") if isinstance(m.get("isUp"), bool) else None,
                last_change=_when(m.get("lastChange")),
            )
            for m in monitors
            if isinstance(m, dict)
        ]
    except _Refused as refused:
        status.error = refused.code
    except (AttributeError, TypeError, KeyError, ValueError):
        status.error = "glitchtip_unexpected_answer"
    return status
