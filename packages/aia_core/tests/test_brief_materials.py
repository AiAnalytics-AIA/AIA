"""The Brief's materials (plan client-data-in-analysis 8a, a proposed interface).

A Brief names a client dataset by source, reading and intended contract; it stores no
eligibility, the signature cannot carry one, and only an accepted contract for exactly that
source, reading and version makes a dataset eligible for analysis. No contract is accepted
anywhere before chunk 2, so no dataset is admitted by being attached.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.brief_materials import (
    AcceptedContract,
    BriefMaterial,
    Eligibility,
    MaterialProblem,
    eligibility_of,
    read_materials,
)
from aia_core.domain.design_items import brief_signature
from aia_core.domain.research_agents import design_material

SOURCE = "SRC-0123456789abcdef"
READING = "a" * 64
CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "design_items" / "cases.json").read_text("utf-8")
)
SIGNED = {s["name"]: s for s in CASES["brief_signatures"]}


def _material(**change: Any) -> BriefMaterial:
    return BriefMaterial.model_validate(
        {"kind": "client_dataset", "source_id": SOURCE, "reading_sha256": READING, **change}
    )


def test_an_attached_dataset_is_visible_and_never_eligible_without_an_accepted_contract() -> None:
    attached = _material()
    named = _material(contract_id="CDC-visits", contract_version=2)
    # Nothing accepts a data contract before chunk 2: every dataset a Brief names is ineligible.
    assert eligibility_of(attached, {}) is Eligibility.NO_CONTRACT
    assert eligibility_of(named, {}) is Eligibility.CONTRACT_NOT_ACCEPTED


@pytest.mark.parametrize(
    ("accepted", "expected"),
    [
        (AcceptedContract("CDC-visits", 2, SOURCE, READING), Eligibility.ELIGIBLE),
        (AcceptedContract("CDC-visits", 3, SOURCE, READING), Eligibility.CONTRACT_STALE),
        (AcceptedContract("CDC-visits", 2, SOURCE, "b" * 64), Eligibility.CONTRACT_STALE),
        (
            AcceptedContract("CDC-visits", 2, "SRC-ffffffffffffffff", READING),
            Eligibility.CONTRACT_STALE,
        ),
    ],
)
def test_only_an_acceptance_of_exactly_this_source_reading_and_version_is_eligible(
    accepted: AcceptedContract, expected: Eligibility
) -> None:
    named = _material(contract_id="CDC-visits", contract_version=2)
    assert eligibility_of(named, {"CDC-visits": accepted}) is expected


def test_a_material_claiming_its_own_eligibility_is_refused_by_name() -> None:
    briefing = {
        "materials": [
            {"kind": "client_dataset", "source_id": SOURCE, "reading_sha256": READING},
            {
                "kind": "client_dataset",
                "source_id": SOURCE,
                "reading_sha256": READING,
                "eligibility": "eligible",
            },
            {"kind": "client_dataset", "source_id": "not-a-source", "reading_sha256": READING},
            {
                "kind": "client_dataset",
                "source_id": SOURCE,
                "reading_sha256": READING,
                "contract_id": "CDC-visits",
            },  # a contract is its id and its version
        ]
    }
    kept, problems = read_materials(briefing)
    assert kept == [_material()]
    assert problems == [
        MaterialProblem(1, "unknown_field"),
        MaterialProblem(2, "invalid_material"),
        MaterialProblem(3, "invalid_material"),
    ]
    assert read_materials({}) == ([], [])
    assert read_materials({"materials": "x"}) == ([], [MaterialProblem(-1, "materials_not_a_list")])


def test_the_signature_carries_no_eligibility_and_old_briefs_keep_theirs() -> None:
    claimed = SIGNED["materials: an entry claiming eligibility signs as one that does not"]
    plain = SIGNED["materials: a dataset under a named contract"]
    assert claimed["signature"] == plain["signature"]
    assert "eligib" not in claimed["signature"] and "admitted" not in claimed["signature"]
    # A Brief without materials, or with none, signs as it did before materials existed.
    empty = SIGNED["materials: an empty list signs as a brief without materials"]["content"]
    without = copy.deepcopy(empty)
    del without["briefing"]["materials"]
    assert brief_signature(empty) == brief_signature(without)
    assert '"materials"' not in brief_signature(without)
    # A newer reading of the same file is a different material, so a different brief.
    newer = SIGNED["materials: a newer reading of the same source is another signature"]
    assert newer["signature"] != plain["signature"]


def test_the_design_a_model_is_shown_names_the_dataset_never_its_rows() -> None:
    content = SIGNED["materials: a dataset under a named contract"]["content"]
    shown = design_material(content)
    assert shown["briefing"]["materials"] == content["briefing"]["materials"]
    assert set(shown["briefing"]["materials"][0]) == {
        "kind",
        "source_id",
        "reading_sha256",
        "contract_id",
        "contract_version",
    }
