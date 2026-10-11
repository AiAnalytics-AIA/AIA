"""The body's side tables and K100 read the run's pinned object map (plan ``methodology-tab``,
chunk S2b).

Before S2b the reference set's side tables -- ``relation``, ``relation_rescaled``,
``object_scores`` -- and its K100 were computed with the code's ``n_min`` 30, confidence 0.95
and bootstrap (B 500, seed, 2.5 / 97.5 %), whatever the run pinned: an edited methodology put
in force moved the object map and left the tables beside it on the old values. They now read
the run's last pinned object map, and the body says which. A run that pinned none keeps the
code's values. The statuses keep reading the respondent count, the body's documented rule.
"""

from __future__ import annotations

import json
import types
from pathlib import Path
from typing import Any

from aia_core.domain import research_sociomap
from aia_core.domain.fieldwork import FieldworkDataset
from aia_core.domain.research_design import ResearchSpecification
from aia_core.domain.research_sociomap import (
    LEGACY_SIDE_TABLES,
    SideTables,
    battery_sociomap,
    side_tables_for,
)
from aia_core.domain.sociomap import (
    AIA_SOCIOMAP_V1,
    AIA_SOCIOMAP_V2,
    AIA_SOCIOMAP_V3,
    AIA_SOCIOMAP_V4,
    SociomapSpecV3,
)

CASES = Path(__file__).parent / "fixtures" / "research_aggregate" / "cases"

#: The constants a run path must not read: the pin carries each (S2a, S2b).
CODE_CONSTANTS = frozenset(
    {
        "AUDIT_PROVISIONAL_N_MIN",
        "PAIR_CONFIDENCE",
        "CONNECTEDNESS_RESAMPLES",
        "CONNECTEDNESS_SEED",
        "CONNECTEDNESS_QUANTILES",
        "LEGACY_SIDE_TABLES",
    }
)


def _case(
    case_id: str = "A01_full_questionnaire",
) -> tuple[ResearchSpecification, FieldworkDataset]:
    case = json.loads((CASES / f"{case_id}.json").read_text(encoding="utf-8"))
    return (
        ResearchSpecification.model_validate(case["spec"]),
        FieldworkDataset.model_validate(case["dataset"]),
    )


def _body(
    maps: tuple[SociomapSpecV3, ...],
    *,
    interval: bool = False,
    respondents: int | None = None,
) -> dict[str, Any]:
    spec, dataset = _case()
    if respondents is not None:
        dataset = dataset.model_copy(update={"respondents": dataset.respondents[:respondents]})
    return battery_sociomap(
        spec.batteries[0],
        dataset,
        rated_with=spec.batteries,
        map_spec=AIA_SOCIOMAP_V1,
        object_maps=maps,
        rating_questions=spec.rating_questions(),
        connectedness_interval=interval,
    )


def _edited(**update: Any) -> SociomapSpecV3:
    relation = {k: v for k, v in update.items() if k in ("n_min", "confidence")}
    connectedness = {k: v for k, v in update.items() if k in ("resamples", "seed", "quantiles")}
    return AIA_SOCIOMAP_V4.model_copy(
        update={
            "methodology_version": "aia-sociomap-4+e1",
            "relation": AIA_SOCIOMAP_V4.relation.model_copy(update=relation),
            "connectedness": AIA_SOCIOMAP_V4.connectedness.model_copy(update=connectedness),
        }
    )


# ------------------------------------------------------------------ the policy --


def test_a_run_without_an_object_map_keeps_the_codes_values() -> None:
    assert side_tables_for(()) == LEGACY_SIDE_TABLES
    assert LEGACY_SIDE_TABLES.to_payload() == {
        "method": None,
        "n_min": 30,
        "confidence": 0.95,
        "resamples": 500,
        "seed": 20261007,
        "quantiles": [0.025, 0.975],
    }


def test_the_last_pinned_object_map_decides() -> None:
    assert side_tables_for((AIA_SOCIOMAP_V2, AIA_SOCIOMAP_V3)).method == "aia-sociomap-3"
    edited = side_tables_for((AIA_SOCIOMAP_V3, _edited(n_min=40, quantiles=(0.05, 0.95))))
    assert edited == SideTables(
        method="aia-sociomap-4+e1",
        n_min=40,
        confidence=0.95,
        resamples=500,
        seed=20261007,
        quantiles=(0.05, 0.95),
    )


def test_a_map_that_declares_no_quantiles_reads_the_codes() -> None:
    assert AIA_SOCIOMAP_V3.connectedness.quantiles is None
    assert side_tables_for((AIA_SOCIOMAP_V3,)).quantiles == LEGACY_SIDE_TABLES.quantiles


def test_no_run_path_reads_the_codes_constants() -> None:
    """Only :func:`side_tables_for` (a run with no object map) may name them."""

    def names(code: types.CodeType) -> set[str]:
        found = set(code.co_names)
        for const in code.co_consts:
            if isinstance(const, types.CodeType):
                found |= names(const)
        return found

    for function in (battery_sociomap, research_sociomap.research_sociomaps):
        assert not names(function.__code__) & CODE_CONSTANTS, function.__name__


# -------------------------------------------------------------------- the body --


def test_the_default_pin_computes_the_tables_it_always_did() -> None:
    before, after = _body(()), _body((AIA_SOCIOMAP_V3,))
    for key in ("relation", "relation_rescaled", "object_scores"):
        assert after[key] == before[key], key
    assert before["side_tables"]["method"] is None
    assert after["side_tables"] == {**before["side_tables"], "method": "aia-sociomap-3"}


def test_an_edited_n_min_moves_every_side_table() -> None:
    # 40 respondents: every pair has 40 raters, RELIABLE or WEAK at n_min 30, UNKNOWN at 41.
    before = _body((AIA_SOCIOMAP_V3,), respondents=40)
    after = _body((_edited(n_min=41),), respondents=40)
    assert after["side_tables"]["method"] == "aia-sociomap-4+e1"
    assert after["relation"]["n_min"] == after["relation_rescaled"]["n_min"] == 41
    assert before["relation"]["status_counts"]["unknown"] == 0
    for key in ("relation", "relation_rescaled"):
        counts = after[key]["status_counts"]
        assert counts["unknown"] == sum(counts.values()), key
    assert after["object_scores"] != before["object_scores"]


def test_an_edited_bootstrap_moves_the_bodys_k100() -> None:
    small = {"resamples": 40}
    wide = _body((_edited(**small),), interval=True)["connectedness_100"]
    narrow = _body((_edited(**small, quantiles=(0.25, 0.75)),), interval=True)["connectedness_100"]
    assert wide["resamples"] == narrow["resamples"] == 40
    assert wide["quantiles"] == [0.025, 0.975]
    assert narrow["quantiles"] == [0.25, 0.75]
    pairs = list(zip(wide["objects"], narrow["objects"], strict=True))
    assert all(w["k100"] == n["k100"] for w, n in pairs)
    assert any(w["low"] is not None and w["low"] < n["low"] for w, n in pairs)
