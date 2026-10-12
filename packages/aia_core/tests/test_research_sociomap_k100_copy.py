"""The body's K100 is copied from an object map only when the map's bootstrap is the body's.

Plan ``methodology-tab.md`` finding H5. The body (the reference map's set) computes K100
over the respondent count; ``aia-sociomap-3`` computes it over Kish's effective n (Q6). Under
unequal weights the two decide different pair statuses, so a map with the same B, seed,
n_min and confidence is still not the same bootstrap, and its K100 is not the body's. Copied,
it gave the body the map's numbers -- on a heavily weighted panel, no K100 at all where the
body's own were known.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aia_core.domain.fieldwork import FieldworkDataset
from aia_core.domain.research_design import ResearchSpecification
from aia_core.domain.research_sociomap import battery_sociomap
from aia_core.domain.sociomap import (
    AIA_SOCIOMAP_V1,
    AIA_SOCIOMAP_V2,
    AIA_SOCIOMAP_V3,
    SociomapSpecV3,
)

CASES = Path(__file__).parent / "fixtures" / "research_aggregate" / "cases"


def _weighted(case_id: str) -> tuple[ResearchSpecification, FieldworkDataset]:
    case = json.loads((CASES / f"{case_id}.json").read_text(encoding="utf-8"))
    spec = ResearchSpecification.model_validate(case["spec"])
    dataset = FieldworkDataset.model_validate(case["dataset"])
    # 45 people, one in three weighted 20 times the others: 45 raters reach n_min 30, their
    # Kish n does not.
    unequal = tuple(
        r.model_copy(update={"weight": (0.2, 0.3, 4.0)[k % 3]})
        for k, r in enumerate(dataset.respondents[:45])
    )
    return spec, dataset.model_copy(update={"respondents": unequal})


def _body(
    spec: ResearchSpecification, dataset: FieldworkDataset, maps: tuple[SociomapSpecV3, ...]
) -> dict[str, Any]:
    battery = spec.batteries[0]
    return battery_sociomap(
        battery,
        dataset,
        rated_with=spec.batteries,
        map_spec=AIA_SOCIOMAP_V1,
        object_maps=maps,
        rating_questions=spec.rating_questions(),
        connectedness_interval=True,
    )


def test_under_unequal_weights_the_body_keeps_its_own_k100_beside_aia_sociomap_3() -> None:
    spec, dataset = _weighted("A01_full_questionnaire")
    alone = _body(spec, dataset, ())["connectedness_100"]
    beside = _body(spec, dataset, (AIA_SOCIOMAP_V3,))
    assert beside["connectedness_100"] == alone
    # The panel is one where the two bootstraps differ, or this proves nothing.
    copied = beside["maps"]["aia-sociomap-3"]["artifact"]["connectedness_100"]
    assert [o["k100"] for o in copied["objects"]] != [o["k100"] for o in alone["objects"]]


def test_a_map_with_other_quantiles_does_not_lend_the_body_its_k100() -> None:
    # Everything the body's bootstrap is, but its interval's quantiles: the map's K100 has the
    # body's points and other intervals, so copying it would give the body the wrong interval.
    # The body reads the last pinned map (S2b), aia-sociomap-2 here; the edit pinned before it
    # matches it in all but the quantiles, and is the first a copy would find.
    spec, dataset = _weighted("A01_full_questionnaire")
    dataset = dataset.model_copy(
        update={
            "respondents": tuple(r.model_copy(update={"weight": 1.0}) for r in dataset.respondents)
        }
    )
    narrow = AIA_SOCIOMAP_V2.model_copy(
        update={
            "methodology_version": "aia-sociomap-4+e1",
            "connectedness": AIA_SOCIOMAP_V2.connectedness.model_copy(
                update={"quantiles": (0.25, 0.75)}
            ),
        }
    )
    own = _body(spec, dataset, (AIA_SOCIOMAP_V2,))["connectedness_100"]
    beside = _body(spec, dataset, (narrow, AIA_SOCIOMAP_V2))
    assert beside["side_tables"]["method"] == "aia-sociomap-2"
    assert beside["connectedness_100"] == own
    assert own["quantiles"] == [0.025, 0.975]
    mapped = beside["maps"]["aia-sociomap-4+e1"]["artifact"]["connectedness_100"]
    assert mapped["quantiles"] == [0.25, 0.75]
    assert [o["k100"] for o in mapped["objects"]] == [o["k100"] for o in own["objects"]]
