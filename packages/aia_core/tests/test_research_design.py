"""Compiling a design and deciding whether it can run (ADR 0016, PR C chunk 4).

The compile rules follow the unit where cited; what the unit does and AIA does
not yet (conditional routing, familiarity questions) is refused by readiness,
never skipped. The fictional dataset is deterministic and answers only what the
specification asks.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from aia_core.domain.fieldwork import DataOrigin, InvalidDataset, validate_dataset
from aia_core.domain.research_design import (
    DONT_KNOW,
    CheckStatus,
    assess_readiness,
    compile_design,
    prepare,
)
from aia_core.domain.synthetic_fieldwork import synthetic_dataset

DESIGN: dict[str, Any] = {
    "title": "Ranní nápoj",
    "n": 120,
    "audience": {"source_mode": "population", "strategy": "population", "filters": {}},
    "sections": [
        {
            "type": "questions",
            "id": "Úvod",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                {
                    "id": "q2",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic", "Kávu"],
                    "povolit_nevim": True,
                },
                {
                    "text": "Co ještě?",
                    "typ": "multi",
                    "kategorie": ["Pečivo", "Ovoce"],
                },
                {"id": "q1", "text": "Proč?", "typ": "otevrena"},
            ],
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_type": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda", "Káva"],
            "object_question": "Jak hodnotíte",
        },
        {"type": "notes", "text": "not part of the study"},
    ],
}


def _check(readiness: Any, check_id: str) -> Any:
    return next(c for c in readiness.checks if c.id == check_id)


def test_a_design_compiles_to_what_fieldwork_asks() -> None:
    spec, problems = compile_design(DESIGN)
    assert problems == () and spec is not None
    q = {x.id: x for x in spec.questions}
    assert list(q) == ["q1", "q2", "uvod_3", "q1_2"], "ids stay unique; a missing id is made"
    assert q["q1"].scale == (1, 5) and q["q1"].section_id == "uvod"
    # Duplicate categories collapse, and "don't know" is an option only where allowed.
    assert q["q2"].options == ("Kávu", "Čaj", "Nic", DONT_KNOW)
    assert q["uvod_3"].options == ("Pečivo", "Ovoce")
    (battery,) = spec.batteries
    assert battery.family == "nápoje" and battery.scale == (1, 10)
    assert [o.label for o in battery.objects] == ["Káva", "Čaj", "Kakao", "Džus", "Voda"]
    assert battery.question_template == "Jak hodnotíte {object}?"
    assert battery.question_id(battery.objects[0]) == "napoje_obj_kava"
    assert spec.n == 120 and spec.audience["has_filters"] is False
    assert spec.fingerprint() == compile_design(copy.deepcopy(DESIGN))[0].fingerprint()  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("section", "code"),
    [
        (
            {"type": "questions", "questions": [{"text": "x", "typ": "skala?"}]},
            "unknown_question_type",
        ),
        ({"type": "questions", "questions": [{"typ": "skala"}]}, "question_without_text"),
        (
            {"type": "questions", "questions": [{"text": "x", "typ": "vyber", "kategorie": ["a"]}]},
            "too_few_categories",
        ),
        (
            {"type": "questions", "questions": [{"text": "x", "typ": "skala", "skala": [5, 1]}]},
            "invalid_scale",
        ),
        ({"type": "object_battery", "objects": ["a", "b", "c"]}, "battery_without_family"),
        ({"type": "object_battery", "object_family": "f", "objects": ["a", "b"]}, "battery_size"),
    ],
)
def test_what_cannot_be_compiled_is_named_and_nothing_is_guessed(section: Any, code: str) -> None:
    spec, problems = compile_design({"n": 100, "sections": [section]})
    assert spec is None
    assert [p.code for p in problems] == [code]


def test_an_empty_questionnaire_does_not_compile() -> None:
    spec, problems = compile_design({"n": 100, "sections": []})
    assert spec is None and problems[0].code == "empty_questionnaire"


def test_readiness_is_named_checks_and_a_fail_blocks() -> None:
    spec, _ = compile_design(DESIGN)
    assert spec is not None
    ready = assess_readiness(spec)
    assert ready.ready and ready.rules == "aia-structural-readiness-1"
    assert _check(ready, "sample_size").status is CheckStatus.PASS
    assert _check(ready, "sociomap_input").status is CheckStatus.PASS

    for n, status in (
        (None, CheckStatus.FAIL),
        (19, CheckStatus.FAIL),
        (10001, CheckStatus.FAIL),
        (20, CheckStatus.PASS),
    ):
        _, r = prepare({**DESIGN, "n": n})
        assert _check(r, "sample_size").status is status and r.ready is (status is CheckStatus.PASS)


def test_what_the_unit_does_and_aia_does_not_yet_is_refused_not_skipped() -> None:
    """Skipping a filter would put answers in the data nobody would have been asked for."""
    filtered = copy.deepcopy(DESIGN)
    filtered["sections"][0]["questions"][2]["filtr"] = "q2 == 'Kávu'"
    _, r = prepare(filtered)
    assert not r.ready and _check(r, "conditional_questions").status is CheckStatus.FAIL
    familiar = copy.deepcopy(DESIGN)
    familiar["sections"][1]["familiarity_required"] = True
    _, r = prepare(familiar)
    assert not r.ready and _check(r, "battery_familiarity").status is CheckStatus.FAIL
    audience = {**DESIGN, "audience": {"source_mode": "customer", "filters": {"age": [18, 35]}}}
    _, r = prepare(audience)
    assert r.ready and _check(r, "audience").status is CheckStatus.WARN


def test_a_design_that_does_not_compile_is_not_ready() -> None:
    spec, r = prepare(
        {"n": 100, "sections": [{"type": "questions", "questions": [{"typ": "vyber"}]}]}
    )
    assert spec is None and not r.ready
    assert [c.status for c in r.checks] == [CheckStatus.FAIL]


def test_the_fictional_dataset_is_deterministic_labelled_and_answers_only_the_spec() -> None:
    spec, _ = compile_design(DESIGN)
    assert spec is not None
    first = synthetic_dataset(spec, seed=7)
    assert first == synthetic_dataset(spec, seed=7)
    assert first != synthetic_dataset(spec, seed=8)
    assert first.origin is DataOrigin.SYNTHETIC_FIXTURE and first.is_synthetic
    assert len(first.respondents) == 120
    assert len({r.donor_id for r in first.respondents}) <= 40
    validate_dataset(spec, first)
    answered = set(first.respondents[0].answers)
    assert answered == {q.id for q in spec.questions} | set(spec.battery_questions())


def test_a_dataset_is_checked_against_its_specification() -> None:
    spec, _ = compile_design(DESIGN)
    assert spec is not None
    good = synthetic_dataset(spec, seed=1)
    other, _ = compile_design({**DESIGN, "n": 121})
    assert other is not None
    with pytest.raises(InvalidDataset, match="different specification"):
        validate_dataset(other, good)

    def with_answer(qid: str, value: Any) -> Any:
        first = good.respondents[0].model_copy(
            update={"answers": {**good.respondents[0].answers, qid: value}}
        )
        return good.model_copy(update={"respondents": (first, *good.respondents[1:])})

    for qid, value, match in (
        ("q1", 9, "off the scale"),
        ("q2", "Pivo", "not an option"),
        ("napoje_obj_kava", 11, "off the 1-10 scale"),
        ("unasked", "x", "unknown items"),
        ("uvod_3", [DONT_KNOW], "are not options"),
    ):
        with pytest.raises(InvalidDataset, match=match):
            validate_dataset(spec, with_answer(qid, value))


def test_a_fictional_dataset_needs_n() -> None:
    spec, _ = compile_design({**DESIGN, "n": None})
    assert spec is not None
    with pytest.raises(ValueError, match="needs the specification's n"):
        synthetic_dataset(spec, seed=1)
