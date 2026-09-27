"""Anthropic API compatibility helpers.

The NPC runtime supports multiple Claude generations. Some current Anthropic
models reject the legacy ``temperature`` request parameter.  Request shaping is
centralised here so UI/copilot/survey paths cannot drift apart.
"""
from __future__ import annotations

from typing import Any
import re


def _model_disallows_temperature(model: str | None) -> bool:
    """Return True for model families known to reject temperature.

    Claude 5 family models use their model-native reasoning/sampling behavior and
    reject the old temperature parameter. Keep the predicate deliberately narrow;
    unknown/older models retain their previous request semantics, with a runtime
    retry fallback in :func:`create_message`.
    """
    m = str(model or "").strip().lower()
    if not m:
        return False
    # Claude 4.6 and later use adaptive thinking and dropped sampling parameters.
    # Covers claude-sonnet-4-6, claude-opus-4-6/4-7/4-8, the 5 generation and
    # dated/suffixed variants; older models keep their previous request semantics.
    if re.match(r"^claude-(?:sonnet|opus|haiku)-5(?:-|$)", m):
        return True
    if re.match(r"^claude-fable-5(?:-|$)", m) or re.match(r"^claude-mythos-5(?:-|$)", m):
        return True
    # Minor version is one or two digits; an 8-digit snapshot date must not match.
    gen = re.match(r"^claude-(?:sonnet|opus|haiku)-4-(\d{1,2})(?:-|$)", m)
    return bool(gen and int(gen.group(1)) >= 6)


def sanitize_params(params: dict[str, Any]) -> dict[str, Any]:
    """Return a copy safe for the selected Anthropic model."""
    out = dict(params)
    if _model_disallows_temperature(out.get("model")):
        out.pop("temperature", None)
    return out


def _is_temperature_compat_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "temperature" in text and any(
        marker in text for marker in ("deprecated", "not supported", "unsupported", "invalid_request")
    )


def create_message(client: Any, **params: Any) -> Any:
    """Call ``client.messages.create`` with safe compatibility retry.

    The retry is intentionally limited to a temperature-compatibility error; all
    other API failures propagate normally and are never hidden.
    """
    original = dict(params)
    safe = sanitize_params(original)
    try:
        return client.messages.create(**safe)
    except Exception as exc:
        # Future model IDs may start rejecting temperature before the local model
        # registry is updated. Retry exactly once without it when the server says
        # temperature is the problem.
        if "temperature" in original and "temperature" in safe and _is_temperature_compat_error(exc):
            safe.pop("temperature", None)
            return client.messages.create(**safe)
        raise
