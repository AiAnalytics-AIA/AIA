"""The audience step's feasibility preview: how many rows a filter selects, and whether a run
could sample them (panel-grounded-respondents 6c).

18.6.6 previewed an audience with its own preflight beside the sampler (``/api/audience``).
AIA asks the functions a run asks: :func:`~.audience.select_audience` for what the filters
select, and :func:`~.sampling.draw_panel_sample` for whether ``n`` respondents can be drawn
from it -- so the preview and the run cannot disagree about the filters, and a design the
sampler would refuse (OI-99 included) is said to be refused before anyone starts a run.

The draw uses :data:`PREVIEW_SEED`, not the run's seed (which is derived from the design the
run compiles): where the verdict depends on the draw, the run's own may differ, and the
answer says which seed it asked with. It holds counts and the sampler's verdict, never a row
or a respondent's value.

Beside the combined count, ``per_filter`` is each filter alone over the same population
(artifact-audience AUD3): what each one admits, so a person sees which filter narrows the
audience. Each is :func:`~.audience.select_audience` over that one filter, the function a
run asks, so the count is the one a run with that filter alone would select.

Pure: stdlib only.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from .audience import AudienceRefused, select_audience
from .errors import PopulationError
from .runtime import RuntimePopulation
from .sampling import DONOR_FIELD, SamplingRefused, draw_panel_sample, quota_keys

__all__ = ["PREVIEW_SEED", "audience_preview"]

#: The seed the preview's draw uses; stated in every answer.
PREVIEW_SEED: Final = 20261012


def _refusal(exc: PopulationError) -> dict[str, Any]:
    return {
        "reason": exc.reason,
        "message": str(exc),
        "reasons": list(getattr(exc, "reasons", ())),
    }


def audience_preview(
    population: RuntimePopulation, filters: Mapping[str, Any] | None, n: int | None
) -> dict[str, Any]:
    """What ``filters`` select in ``population`` and, given ``n``, whether a run could draw it."""
    out: dict[str, Any] = {
        "population_rows": population.row_count,
        "selected_rows": None,
        "selected_donors": None,
        "filters_applied": None,
        "per_filter": None,
        "audience": None,
        "n": n,
        "sample": None,
        "seed": PREVIEW_SEED,
    }
    try:
        selection = select_audience(population, filters)
    except AudienceRefused as exc:
        out["audience"] = {"ok": False, **_refusal(exc)}
        return out
    out["selected_rows"] = len(selection.rows)
    out["filters_applied"] = selection.filters_json()
    # Every filter passed the combined selection, so alone each selects at least as many rows:
    # none can be refused or empty here.
    out["per_filter"] = {
        key: len(select_audience(population, {key: (filters or {})[key]}).rows)
        for key in out["filters_applied"]
    }
    if DONOR_FIELD in population.fields:
        donors = population.column(DONOR_FIELD)
        out["selected_donors"] = len({donors[r] for r in selection.rows if donors[r] is not None})
    out["audience"] = {"ok": True}
    if n is None:
        return out
    try:
        sample = draw_panel_sample(population, filters, n, PREVIEW_SEED)
    except SamplingRefused as exc:
        out["sample"] = {"ok": False, **_refusal(exc)}
        return out
    out["sample"] = {
        "ok": True,
        "status": sample.audit.status,
        "sample_donors": sample.audit.sample_donors,
        "effective_n": sample.audit.effective_n,
        # How the sampler spreads n at this seed (RQC6b); a run's own may differ only at ties.
        "quota_fields": list(sample.audit.quota_fields),
        "cells": [
            {"key": key, "values": list(c.values), "n": c.n}
            for c, key in zip(sample.quota_cells, quota_keys(sample.quota_cells), strict=True)
        ],
    }
    return out
