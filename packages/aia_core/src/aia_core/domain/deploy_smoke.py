"""A deploy's smoke run read from its own lines (settings-backends SB4), pure.

``deploy/develop/bin/smoke.sh`` and ``aia_executors.smoke`` print one line per check, in one
shape: ``ok    <label>``, ``FAIL  <label>`` or ``NOT_RUNNABLE  <label>``, a failure's detail on
the indented lines after it. :func:`parse_smoke_lines` keeps each check's label and result and
nothing else: no detail line (a response body, a header, a path), no ``info`` line. A label
longer than :data:`MAX_LABEL` is cut, never dropped, so the count of checks stays true.

:func:`order_checks` is how Settings lists them: what is not ready first (FAIL, then
NOT_RUNNABLE), then the passes, each group in the order the smoke ran them.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

__all__ = [
    "MAX_LABEL",
    "SmokeCheck",
    "SmokeStatus",
    "order_checks",
    "parse_smoke_lines",
]

MAX_LABEL: Final = 300


class SmokeStatus(StrEnum):
    OK = "ok"
    FAIL = "FAIL"
    NOT_RUNNABLE = "NOT_RUNNABLE"


@dataclass(frozen=True, slots=True)
class SmokeCheck:
    label: str
    status: SmokeStatus


# The longest token first: "NOT_RUNNABLE" is never read as anything shorter.
_PREFIXES: Final = (
    (SmokeStatus.NOT_RUNNABLE, "NOT_RUNNABLE "),
    (SmokeStatus.FAIL, "FAIL "),
    (SmokeStatus.OK, "ok "),
)


def parse_smoke_lines(lines: Iterable[str]) -> list[SmokeCheck]:
    """Every check line in ``lines``, in order; any other line (a detail, ``info``, the
    banner, the closing verdict) is not a check and is left out."""
    checks: list[SmokeCheck] = []
    for raw in lines:
        line = raw.rstrip("\r\n")
        for status, prefix in _PREFIXES:
            if line.startswith(prefix):
                label = line[len(prefix) :].strip()
                if label:
                    checks.append(SmokeCheck(label[:MAX_LABEL], status))
                break
    return checks


_ORDER: Final = {SmokeStatus.FAIL: 0, SmokeStatus.NOT_RUNNABLE: 1, SmokeStatus.OK: 2}


def order_checks(checks: Iterable[tuple[int, SmokeCheck]]) -> list[SmokeCheck]:
    """``(position, check)`` pairs as Settings lists them: not ready first, then by position."""
    return [c for _, c in sorted(checks, key=lambda pc: (_ORDER[pc[1].status], pc[0]))]
