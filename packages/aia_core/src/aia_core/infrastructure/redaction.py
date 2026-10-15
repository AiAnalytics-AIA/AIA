"""What must never reach a log sink, an attempt's ``error_json`` or an error report.

One definition for every process (OI-23): the API's log lines and error bodies, the
worker's log lines and the exception text it records, and the error reporter's events
(:mod:`aia_core.infrastructure.error_tracking`) all redact with these patterns. A new key
shape added here is redacted everywhere at once.

Pure: the standard library only.
"""

from __future__ import annotations

import re
from typing import Any, Final

__all__ = ["REDACTED", "redact", "redact_text"]

REDACTED: Final = "[redacted]"
_MAX_RECORDED_MESSAGE: Final = 500

# Values that must never reach a sink. Matched on the *key*, so a nested payload
# carrying `{"api_key": "sk-ant-..."}` is redacted regardless of depth.
_SECRET_KEY_PATTERN: Final = re.compile(
    r"(api[_-]?key|secret|token|password|passwd|credential|authorization|cookie|"
    r"anthropic_api_key|openai_api_key)",
    re.IGNORECASE,
)

# Provider key shapes, redacted even when they appear inside a free-text message.
# The `sk-` pattern must allow interior hyphens: current Anthropic and OpenAI keys
# are `sk-ant-api03-...` and `sk-proj-...`, so a character class without `-` stops
# matching at the first separator and leaks the remainder of the key.
_SECRET_VALUE_PATTERNS: Final = (
    re.compile(r"sk-[A-Za-z0-9][A-Za-z0-9_\-]{15,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{10,}", re.IGNORECASE),
    # A JWT on its own (a Cognito id or refresh token pasted into a message): three
    # base64url segments, the first a JSON header (`{"` is `eyJ`).
    re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),
    # Generic long opaque tokens in an explicit assignment, e.g. `token=...`.
    re.compile(
        r"((?:api[_-]?key|token|secret|password)\s*[=:]\s*)[A-Za-z0-9._\-]{12,}",
        re.IGNORECASE,
    ),
)


def _redact_string(value: str) -> str:
    out = value
    for pattern in _SECRET_VALUE_PATTERNS:
        # A pattern with a capture group keeps its prefix (e.g. "token=") so the
        # line stays readable; the secret itself is replaced.
        replacement = r"\1" + REDACTED if pattern.groups else REDACTED
        out = pattern.sub(replacement, out)
    return out


def redact(value: Any, *, _depth: int = 0) -> Any:
    """Return ``value`` with anything secret-looking replaced.

    Recursion is depth-limited so a cyclic or pathologically nested payload cannot
    hang the caller.
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
        return _redact_string(value)
    return value


def redact_text(value: str, *, limit: int = _MAX_RECORDED_MESSAGE) -> str:
    """Return ``value`` with secret-looking substrings replaced, truncated to ``limit``."""
    text = _redact_string(str(value))
    return text if len(text) <= limit else text[: limit - 1] + "…"
