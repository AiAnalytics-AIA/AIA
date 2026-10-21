"""The audience step's feasibility preview (panel-grounded-respondents 6c).

Over the sampler's 3,000 fictional rows, loaded as a run loads its population
(``conftest.sampled_population``). The preview asks the run's own functions, so each
answer here is checked against what ``select_audience`` and ``draw_panel_sample`` say.
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.population.audience import select_audience
from aia_core.domain.population.audience_preview import PREVIEW_SEED, audience_preview
from aia_core.domain.population.sampling import draw_panel_sample


@pytest.fixture
def population(sampled_population: Any) -> Any:
    return sampled_population().population


def test_a_filter_and_an_n_the_sampler_can_draw(population: Any) -> None:
    filters = {"vek": {"min": 30, "max": 59}}
    answer = audience_preview(population, filters, 200)
    selected = select_audience(population, filters)
    assert answer["selected_rows"] == len(selected.rows) < population.row_count
    assert answer["population_rows"] == population.row_count
    donors = population.column("core_donor_id")
    assert answer["selected_donors"] == len({donors[r] for r in selected.rows})
    assert answer["filters_applied"] == selected.filters_json()
    assert answer["audience"] == {"ok": True}
    sample = draw_panel_sample(population, filters, 200, PREVIEW_SEED)
    assert answer["sample"] == {
        "ok": True,
        "status": sample.audit.status,
        "sample_donors": sample.audit.sample_donors,
        "effective_n": sample.audit.effective_n,
    }
    assert answer["seed"] == PREVIEW_SEED


def test_each_filter_is_counted_alone_over_the_same_population(population: Any) -> None:
    """AUD3: per_filter is select_audience over each filter alone; the combined is their AND."""
    filters = {"vek": {"min": 30, "max": 59}, "kraj": ["Zlínský kraj", "Hlavní město Praha"]}
    answer = audience_preview(population, filters, None)
    alone = {k: len(select_audience(population, {k: v}).rows) for k, v in filters.items()}
    assert answer["per_filter"] == alone
    assert set(answer["per_filter"]) == set(answer["filters_applied"])
    assert all(answer["selected_rows"] <= count < population.row_count for count in alone.values())
    assert answer["selected_rows"] < min(alone.values())


def test_no_filter_counts_nothing_alone_and_a_refusal_counts_none(population: Any) -> None:
    assert audience_preview(population, {}, None)["per_filter"] == {}
    assert audience_preview(population, {"vek": "abc"}, None)["per_filter"] is None
    empty = audience_preview(population, {"vek": {"min": 101, "max": 120}}, None)
    assert empty["per_filter"] is None


def test_without_an_n_only_the_audience_is_counted(population: Any) -> None:
    answer = audience_preview(population, {}, None)
    assert answer["selected_rows"] == population.row_count and answer["sample"] is None


def test_a_filter_the_run_would_refuse_is_said_with_every_reason(population: Any) -> None:
    answer = audience_preview(population, {"vek": "abc", "neexistuje": 1}, 100)
    assert answer["audience"]["ok"] is False
    assert answer["audience"]["reason"] == "sampling_filter_invalid"
    assert len(answer["audience"]["reasons"]) == 2
    assert answer["selected_rows"] is None and answer["sample"] is None
    empty = audience_preview(population, {"vek": {"min": 101, "max": 120}}, 100)
    assert empty["audience"]["reason"] == "sampling_empty"


def test_an_n_the_sampler_refuses_is_said_before_a_run_is_started(population: Any) -> None:
    """OI-99 is the owner's: a small study is refused, and the preview says so first."""
    small = audience_preview(population, {}, 8)
    assert small["audience"] == {"ok": True}
    assert small["sample"]["ok"] is False
    assert small["sample"]["reason"] == "sampling_unrepresentative"
    over = audience_preview(population, {"vek": {"min": 80, "max": 89}}, 3000)
    assert over["sample"]["reason"] == "sampling_n_exceeds_support"
