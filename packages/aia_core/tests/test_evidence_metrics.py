"""The allowed analysis metrics: a closed set with one unit each."""

from __future__ import annotations

import pytest

from aia_core.domain.evidence import (
    AnalysisMetric,
    MetricKind,
    MetricUnit,
    UnknownMetric,
    allowed_metric_spellings,
    parse_metric,
    unit_for,
)


@pytest.mark.parametrize(
    ("raw", "kind", "answer"),
    [
        ("mean", MetricKind.MEAN, None),
        ("top2box_pct", MetricKind.TOP2BOX_PCT, None),
        ("n", MetricKind.N, None),
        ("effective_n", MetricKind.EFFECTIVE_N, None),
        ("pct:Rozhodně ano", MetricKind.PCT, "Rozhodně ano"),
        ("pct: leading space kept", MetricKind.PCT, " leading space kept"),
        ("pct:a:b", MetricKind.PCT, "a:b"),
    ],
)
def test_allowed_metrics_parse_exactly(raw: str, kind: MetricKind, answer: str | None) -> None:
    metric = parse_metric(raw)
    assert (metric.kind, metric.answer) == (kind, answer)
    assert str(metric) == raw


@pytest.mark.parametrize(
    "raw",
    ["t_score", "Mean", "mean ", "median", "pct", "pct:", "top2box", "share", "", "PCT:x"],
)
def test_anything_else_is_refused_not_mapped(raw: str) -> None:
    with pytest.raises(UnknownMetric):
        parse_metric(raw)


def test_answer_only_on_pct() -> None:
    with pytest.raises(UnknownMetric):
        AnalysisMetric(MetricKind.MEAN, "x")
    with pytest.raises(UnknownMetric):
        AnalysisMetric(MetricKind.PCT)


def test_every_metric_has_one_unit() -> None:
    assert unit_for(MetricKind.PCT) is MetricUnit.PERCENT
    assert unit_for(MetricKind.TOP2BOX_PCT) is MetricUnit.PERCENT
    assert unit_for(MetricKind.N) is MetricUnit.RESPONDENTS
    assert unit_for(MetricKind.EFFECTIVE_N) is MetricUnit.RESPONDENTS
    assert unit_for(MetricKind.MEAN) is MetricUnit.SCALE_MEAN
    assert parse_metric("pct:x").unit is MetricUnit.PERCENT


def test_prompt_spelling_is_generated_from_the_enum() -> None:
    """M17: the reference set, which previously existed only inside a prompt string."""
    assert allowed_metric_spellings() == (
        "mean",
        "top2box_pct",
        "n",
        "effective_n",
        "pct:<exact answer>",
    )
