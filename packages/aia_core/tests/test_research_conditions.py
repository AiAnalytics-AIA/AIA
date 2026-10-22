"""A question's display condition in the design (working-copy-edit-ops WCE13 (a)).

A condition names an earlier choice question and the answers that lead to the question. The
compiler reads it into the specification or refuses it by name; it never guesses one from text it
cannot read. Until fieldwork routes by it (run-qc-and-checkpoint RQC11), readiness still refuses a
conditional question, valid or not.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from aia_core.domain import research_design
from aia_core.domain.research_design import (
    CheckStatus,
    SpecCondition,
    assess_readiness,
    compile_design,
)
from aia_core.domain.sociomap.relations import AUDIT_PROVISIONAL_N_MIN


def _design(*questions: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": "Fiktivní nápoje",
        "n": 300,
        "sections": [
            {
                "id": "uvod",
                "type": "questions",
                "questions": [
                    {"id": "Q1", "text": "Jak často pijete kávu?", "typ": "vyber",
                     "kategorie": ["Denně", "Týdně", "Nikdy"]},
                    {"id": "Q2", "text": "Jak vám chutná?", "typ": "skala", "skala": [1, 5]},
                    *questions,
                ],
            }
        ],
    }  # fmt: skip


def _q3(filtr: Any) -> dict[str, Any]:
    return {"id": "Q3", "text": "Proč ne?", "typ": "otevrena", "filtr": filtr}


def _codes(content: dict[str, Any]) -> list[str]:
    spec, problems = compile_design(content)
    assert spec is None
    return [p.code for p in problems]


def test_a_condition_on_an_earlier_choice_compiles_and_still_waits_for_routing() -> None:
    spec, problems = compile_design(_design(_q3({"question_id": "Q1", "options": ["Nikdy"]})))
    assert problems == () and spec is not None
    q3 = next(q for q in spec.questions if q.id == "q3")
    # The compiled id of the question it names, the answers as written.
    assert q3.condition == SpecCondition(question_id="q1", options=("Nikdy",))
    assert q3.has_filter
    # Fieldwork does not route yet (RQC11): readiness refuses it exactly as before.
    check = next(
        c
        for c in assess_readiness(spec, pair_n_min=AUDIT_PROVISIONAL_N_MIN).checks
        if c.id == "conditional_questions"
    )
    assert check.status is CheckStatus.FAIL and "q3" in check.message


@pytest.mark.parametrize(
    ("written", "options"),
    [
        ("Q1 == 'Nikdy'", ("Nikdy",)),
        ("Q1 in ['Týdně', 'Nikdy']", ("Týdně", "Nikdy")),
        ("Q1 in ('Týdně',)", ("Týdně",)),
    ],
)
def test_a_condition_written_as_the_classic_did_reads_when_it_is_exactly_a_choice(
    written: str, options: tuple[str, ...]
) -> None:
    spec, problems = compile_design(_design(_q3(written)))
    assert problems == () and spec is not None
    assert spec.questions[-1].condition == SpecCondition(question_id="q1", options=options)


@pytest.mark.parametrize(
    "written",
    [
        "Q1 != 'Nikdy'",  # another operator
        "Q1 == Nikdy",  # an unquoted answer: the classic quoted it by a guess
        "Q1 == 'Nikdy' and Q2 > 3",  # a compound
        "Q1 in []",  # no answer at all
        "Q1 ==",  # not an expression
        {"q": "Q1"},  # another shape
        {"question_id": "Q1", "options": []},
        {"question_id": "Q1", "options": "Nikdy"},
        {"question_id": "Q1", "options": ["Nikdy"], "negate": True},
        ["Q1", "Nikdy"],
    ],
)
def test_a_condition_the_domain_cannot_read_stays_as_written_and_is_refused_by_name(
    written: Any,
) -> None:
    content = _design(_q3(written))
    stored = copy.deepcopy(content)
    assert _codes(content) == ["condition_unstructured"]
    assert content == stored, "nothing is rewritten or dropped"


@pytest.mark.parametrize(
    ("condition", "code"),
    [
        ({"question_id": "Q9", "options": ["Nikdy"]}, "condition_unknown_question"),
        ({"question_id": "Q3", "options": ["Nikdy"]}, "condition_forward_reference"),
        ({"question_id": "Q2", "options": ["5"]}, "condition_not_choice"),
        ({"question_id": "Q1", "options": ["Někdy"]}, "condition_unknown_option"),
    ],
)
def test_a_condition_names_an_earlier_choice_question_and_one_of_its_answers(
    condition: dict[str, Any], code: str
) -> None:
    assert _codes(_design(_q3(condition))) == [code]


def test_a_condition_on_a_later_question_is_refused_as_a_forward_reference() -> None:
    later = {"id": "Q4", "text": "Pijete čaj?", "typ": "vyber", "kategorie": ["Ano", "Ne"]}
    content = _design(_q3({"question_id": "Q4", "options": ["Ano"]}), later)
    assert _codes(content) == ["condition_forward_reference"]


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_no_condition_is_no_condition(empty: Any) -> None:
    spec, problems = compile_design(_design(_q3(empty)))
    assert problems == () and spec is not None
    assert spec.questions[-1].condition is None and not spec.questions[-1].has_filter


def test_a_condition_is_in_the_fingerprint_only_when_declared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Absent, the condition is out of the fingerprint, so a design compiled before conditions
    existed keeps the identity it had; declared, a changed condition is a changed design."""
    hashed: list[dict[str, Any]] = []
    real = research_design.fingerprint
    monkeypatch.setattr(
        research_design, "fingerprint", lambda body: hashed.append(body) or real(body)
    )
    plain, _ = compile_design(_design())
    assert plain is not None
    plain.fingerprint()
    assert all("condition" not in q for q in hashed[-1]["questions"])
    never, _ = compile_design(_design(_q3({"question_id": "Q1", "options": ["Nikdy"]})))
    weekly, _ = compile_design(_design(_q3({"question_id": "Q1", "options": ["Týdně"]})))
    unconditional, _ = compile_design(_design(_q3(None)))
    assert never is not None and weekly is not None and unconditional is not None
    assert len({never.fingerprint(), weekly.fingerprint(), unconditional.fingerprint()}) == 3
