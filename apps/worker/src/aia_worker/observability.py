"""Structured logging for the worker, and redaction of what it records.

One JSON object per line, carrying ``worker_id`` and -- while an attempt is being
executed -- ``run_id``, ``step_id`` and ``attempt_id``, so "why did step X stop?"
is answerable from the log stream alone.

Redaction applies to log lines **and** to exception text the worker writes into
an attempt's ``error_json``: an executor's exception message is exactly where a
provider key or a bearer token ends up. The patterns are the provider-key shapes
the API redacts (``apps/api/src/aia_api/observability.py``). The worker cannot
import the API, so the shapes are restated here; moving them into ``aia_core`` so
both import one definition is ``.planning/open-items.md`` OI-23.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar
from typing import Any, Final

__all__ = ["attempt_context", "configure_logging", "redact_text"]

# Fields bound to the attempt being executed, added to every line logged meanwhile.
attempt_context: ContextVar[dict[str, str] | None] = ContextVar("attempt_context", default=None)

_SECRET_VALUE_PATTERNS: Final = (
    re.compile(r"sk-[A-Za-z0-9][A-Za-z0-9_\-]{15,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{10,}", re.IGNORECASE),
    re.compile(
        r"((?:api[_-]?key|token|secret|password)\s*[=:]\s*)[A-Za-z0-9._\-]{12,}",
        re.IGNORECASE,
    ),
)
REDACTED: Final = "[redacted]"
_MAX_RECORDED_MESSAGE: Final = 500


def redact_text(value: str, *, limit: int = _MAX_RECORDED_MESSAGE) -> str:
    """Return ``value`` with secret-looking substrings replaced, truncated to ``limit``."""
    text = str(value)
    for pattern in _SECRET_VALUE_PATTERNS:
        text = pattern.sub(
            lambda m: (m.group(1) + REDACTED) if m.groups() else REDACTED,
            text,
        )
    return text if len(text) <= limit else text[: limit - 1] + "…"


class _JsonFormatter(logging.Formatter):
    """Render a record as one JSON object."""

    def __init__(self, worker_id: str) -> None:
        super().__init__()
        self._worker_id = worker_id

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "worker_id": self._worker_id,
            "message": redact_text(record.getMessage(), limit=4000),
            **(attempt_context.get() or {}),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            entry.update({k: v for k, v in fields.items() if k not in entry})
        if record.exc_info:
            entry["exception"] = redact_text(self.formatException(record.exc_info), limit=4000)
        return json.dumps(entry, default=str)


def configure_logging(*, worker_id: str, level: str = "INFO") -> None:
    """Send JSON lines to stdout, which is what CloudWatch collects from Fargate."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter(worker_id))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
