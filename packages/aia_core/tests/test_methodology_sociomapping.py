"""The experimental Sociomapping on the Metodika tab (plan ``methodology-tab.md`` S1c).

What every registered module must be (complete, pinned, its tests present) is held by
``test_methodology.py``; this file pins what is particular to this one: it is shown and not
edited, its values are the parameters every result records, it says it is AIA's experiment and
not SOMECS's method, and every rule it cites is in the register.
"""

from __future__ import annotations

import json
from pathlib import Path

from aia_core.domain.methodology import MODULES, ValueOrigin, describe
from aia_core.domain.methodology.catalogue import EvidenceKind
from aia_core.domain.methodology.sociomapping import SOCIOMAPPING
from aia_core.domain.sociomap.hmodel_candidate import (
    CANDIDATE_METHOD,
    CANDIDATE_STATUS,
    CandidateParameters,
)

REPO = Path(__file__).resolve().parents[3]
REGISTER = REPO / "docs/migration/sociomapping-evidence-register.json"


def _values() -> dict[str, object]:
    view = describe(SOCIOMAPPING)
    return {v.reference: v.value for s in view.steps for v in s.values}


def test_it_is_registered_after_the_two_maps() -> None:
    assert [m.id for m in MODULES][:3] == ["sociomap", "sociomap_reference", "sociomapping"]


def test_it_is_shown_and_never_offered_for_editing() -> None:
    assert SOCIOMAPPING.editable is False
    assert SOCIOMAPPING.formulas == ()
    assert SOCIOMAPPING.in_force == CANDIDATE_METHOD


def test_every_parameter_a_result_records_is_shown_once_with_its_value() -> None:
    view = describe(SOCIOMAPPING)
    shown = [
        v.reference for s in view.steps for v in s.values if v.origin is ValueOrigin.SPECIFICATION
    ]
    defaults = CandidateParameters()
    assert sorted(shown) == sorted(CandidateParameters.model_fields)
    values = _values()
    for name in CandidateParameters.model_fields:
        assert values[name] == getattr(defaults, name), name


def test_it_says_what_it_is_an_aia_experiment_not_somecs() -> None:
    values = _values()
    assert values["aia_core.domain.sociomap.hmodel_candidate:CANDIDATE_STATUS"] == (
        CANDIDATE_STATUS
    )
    assert CANDIDATE_STATUS == "EXPERIMENTAL_AIA"
    assert "EXPERIMENTAL_AIA" in SOCIOMAPPING.note_cs and "SOMECS" in SOCIOMAPPING.note_cs
    search = next(s for s in SOCIOMAPPING.steps if s.id == "search")
    cited = {e.ref for e in search.evidence if e.kind is EvidenceKind.REGISTER_RULE}
    assert {"AIA-H8", "AIA-H9"} <= cited


def test_every_register_rule_cited_is_in_the_register() -> None:
    rules = {r["id"] for r in json.loads(REGISTER.read_text(encoding="utf-8"))["rules"]}
    cited = {
        e.ref
        for s in SOCIOMAPPING.steps
        for e in s.evidence
        if e.kind is EvidenceKind.REGISTER_RULE
    }
    assert cited and cited <= rules, sorted(cited - rules)


def test_every_step_cites_a_register_rule() -> None:
    bare = [
        s.id
        for s in SOCIOMAPPING.steps
        if not any(e.kind is EvidenceKind.REGISTER_RULE for e in s.evidence)
    ]
    assert bare == []
