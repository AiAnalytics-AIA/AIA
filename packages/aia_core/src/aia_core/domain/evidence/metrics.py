"""The metrics a client analysis may cite. A typed set, not a sentence in a prompt.

In the reference the allowed-metric set -- ``mean | top2box_pct | n |
effective_n | pct:<exact answer>`` -- exists only inside the analysis system
prompt and its repair prompt (methodology-ledger M17). Rewriting the prompt would
silently widen what a model may claim. Here the set is :class:`MetricKind`, the
prompt is rendered *from* it (:func:`allowed_metric_spellings`), and anything
outside it is refused by :func:`parse_metric` -- including the reference's
habit of letting an unrecognised metric id fall through to a T-score.

Each metric has exactly one unit (:func:`unit_for`), so a claim cannot cite a
share as a count.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

__all__ = [
    "AnalysisMetric",
    "MetricKind",
    "MetricUnit",
    "UnknownMetric",
    "allowed_metric_spellings",
    "parse_metric",
    "unit_for",
]


class MetricKind(StrEnum):
    MEAN = "mean"
    TOP2BOX_PCT = "top2box_pct"
    N = "n"
    EFFECTIVE_N = "effective_n"
    PCT = "pct"


class MetricUnit(StrEnum):
    PERCENT = "%"
    RESPONDENTS = "respondents"
    SCALE_MEAN = "scale_mean"


_UNITS: Final[dict[MetricKind, MetricUnit]] = {
    MetricKind.MEAN: MetricUnit.SCALE_MEAN,
    MetricKind.TOP2BOX_PCT: MetricUnit.PERCENT,
    MetricKind.N: MetricUnit.RESPONDENTS,
    MetricKind.EFFECTIVE_N: MetricUnit.RESPONDENTS,
    MetricKind.PCT: MetricUnit.PERCENT,
}

_PCT_PREFIX: Final = "pct:"


class UnknownMetric(ValueError):
    """A metric id outside the allowed set. Never mapped onto a nearby metric."""


@dataclass(frozen=True, slots=True)
class AnalysisMetric:
    """One allowed metric. ``answer`` is the exact answer label, and only for ``pct``."""

    kind: MetricKind
    answer: str | None = None

    def __post_init__(self) -> None:
        if (self.kind is MetricKind.PCT) != (self.answer is not None):
            raise UnknownMetric("pct needs an exact answer label; no other metric takes one")
        if self.answer is not None and not self.answer:
            raise UnknownMetric("pct needs a non-empty answer label")

    @property
    def unit(self) -> MetricUnit:
        return unit_for(self.kind)

    def __str__(self) -> str:
        return f"{_PCT_PREFIX}{self.answer}" if self.kind is MetricKind.PCT else self.kind.value


def parse_metric(raw: str) -> AnalysisMetric:
    """Parse a metric id exactly as written. No trimming, no case folding, no aliases.

    ``pct:<answer>`` keeps the answer verbatim because it must match an answer
    label in the evidence exactly ("copy values exactly from the evidence").
    """
    if raw.startswith(_PCT_PREFIX):
        return AnalysisMetric(MetricKind.PCT, raw[len(_PCT_PREFIX) :])
    try:
        kind = MetricKind(raw)
    except ValueError:
        raise UnknownMetric(
            f"{raw!r} is not an allowed metric ({', '.join(allowed_metric_spellings())})"
        ) from None
    if kind is MetricKind.PCT:
        raise UnknownMetric("pct needs an exact answer label: pct:<answer>")
    return AnalysisMetric(kind)


def unit_for(kind: MetricKind) -> MetricUnit:
    return _UNITS[kind]


def allowed_metric_spellings() -> tuple[str, ...]:
    """The allowed set as a model should be told it, generated from the enum."""
    return tuple(
        f"{_PCT_PREFIX}<exact answer>" if kind is MetricKind.PCT else kind.value
        for kind in MetricKind
    )
