"""A question's display condition in the design (working-copy-edit-ops WCE13 (a)).

A condition names an earlier choice question and the answers that lead to the question. The
compiler reads it into the specification or names why it refuses it, at the question, and readiness
fails that by name while every other check is still read; it never guesses a condition from text it
cannot read. Until fieldwork routes by it (run-qc-and-checkpoint RQC11), readiness still refuses a
valid one too (conditional_questions).
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from aia_core.domain import research_design
from aia_core.domain.evidence.support import SupportStatus
from aia_core.domain.fieldwork import PersonaSource
from aia_core.domain.question_outlook import OutlookReason, Verdict, question_outlook
from aia_core.domain.research_design import (
    CheckStatus,
    SpecCondition,
    assess_readiness,
    compile_design,
    condition_refusal,
)
from aia_core.domain.sociomap.relations import AUDIT_PROVISIONAL_N_MIN
from aia_core.domain.support_forecast import SupportForecast


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
    """The conditions refused, by code: the design still compiles, so every other check is read,
    and readiness fails each refusal by name at its question."""
    spec, problems = compile_design(content)
    assert problems == () and spec is not None
    refused = [q for q in spec.questions if q.condition_problem is not None]
    checks = {c.id: c for c in assess_readiness(spec, pair_n_min=AUDIT_PROVISIONAL_N_MIN).checks}
    assert checks["questionnaire"].status is CheckStatus.PASS, "the rest of Kontrola is still read"
    for q in refused:
        assert q.has_filter and q.condition is None
        failed = checks[f"condition:{q.id}"]
        assert failed.status is CheckStatus.FAIL and failed.message.startswith(f"{q.id}: ")
    # A refused condition is no valid one: it is not counted under conditional_questions.
    assert "conditional_questions" not in checks or all(
        q.id not in checks["conditional_questions"].message for q in refused
    )
    return [q.condition_problem.code for q in refused if q.condition_problem is not None]


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
        # The unit named a question as its compiler did: case-insensitively (filter_syntax.py).
        ("q1 == 'Nikdy'", ("Nikdy",)),
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
        "Q1 == 'Ni' 'kdy'",  # two literals joined: not one answer as written
        "Q1 == " + " + ".join(["'a'"] * 5000),  # too long to be a choice; never parsed
        "(" * 400 + "Q1" + ")" * 400 + " == 'Nikdy'",  # nests past the parser
        "\uff31" + "1 == 'Nikdy'",  # a full-width name the parser would fold to Q1 (NFKC)
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


def test_a_condition_on_a_question_compile_refused_says_nothing_more() -> None:
    """The earlier question's own problem stands; its dependant is not a forward reference."""
    content = _design(_q3({"question_id": "Q1", "options": ["Nikdy"]}))
    content["sections"][0]["questions"][0]["kategorie"] = ["Denně"]
    spec, problems = compile_design(content)
    assert spec is None and [p.code for p in problems] == ["too_few_categories"]


def test_a_condition_naming_two_questions_is_refused_never_bound_to_the_first() -> None:
    twin = {"id": "Q1", "text": "Pijete čaj?", "typ": "vyber", "kategorie": ["Nikdy", "Denně"]}
    content = _design(twin, _q3({"question_id": "Q1", "options": ["Nikdy"]}))
    assert _codes(content) == ["condition_ambiguous_question"]


def test_a_condition_on_a_name_the_question_itself_carries_is_refused_as_ambiguous() -> None:
    """A second Q1 conditioned on Q1: the earlier Q1 is not the only question so named."""
    twin = {
        "id": "Q1",
        "text": "Proč?",
        "typ": "otevrena",
        "filtr": {"question_id": "Q1", "options": ["Nikdy"]},
    }
    assert _codes(_design(twin)) == ["condition_ambiguous_question"]


@pytest.mark.parametrize(
    "condition", [{"question_id": "Q1", "options": ["Nikdy"]}, "q1 == 'Nikdy'"]
)
def test_a_condition_on_a_name_a_later_question_carries_is_refused_as_ambiguous(
    condition: Any,
) -> None:
    later = {"id": "Q1", "text": "Pijete čaj?", "typ": "vyber", "kategorie": ["Nikdy", "Denně"]}
    assert _codes(_design(_q3(condition), later)) == ["condition_ambiguous_question"]


def test_a_specification_cannot_say_a_question_is_conditional_without_its_condition() -> None:
    spec, _ = compile_design(_design(_q3({"question_id": "Q1", "options": ["Nikdy"]})))
    assert spec is not None
    q3 = spec.questions[-1]
    with pytest.raises(ValueError, match="has_filter"):
        type(q3).model_validate({**q3.model_dump(), "condition": None})
    with pytest.raises(ValueError, match="has_filter"):
        type(q3).model_validate({**q3.model_dump(), "has_filter": False})
    # Read and refused at once is no state compile produces.
    problem = {"code": "condition_unknown_option", "where": "q3", "message": "q3: …"}
    with pytest.raises(ValueError, match="has_filter"):
        type(q3).model_validate({**q3.model_dump(), "condition_problem": problem})


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
    assert all(
        "condition" not in q and "condition_problem" not in q for q in hashed[-1]["questions"]
    )
    never, _ = compile_design(_design(_q3({"question_id": "Q1", "options": ["Nikdy"]})))
    weekly, _ = compile_design(_design(_q3({"question_id": "Q1", "options": ["Týdně"]})))
    unconditional, _ = compile_design(_design(_q3(None)))
    assert never is not None and weekly is not None and unconditional is not None
    unread, _ = compile_design(_design(_q3("Q1 != 'Nikdy'")))
    assert unread is not None
    prints = {p.fingerprint() for p in (never, weekly, unconditional, unread)}
    assert len(prints) == 4


@pytest.mark.parametrize(
    ("condition", "code"),
    [
        ({"question_id": "Q1", "options": ["Nikdy"]}, None),
        ({"question_id": "Q9", "options": ["Nikdy"]}, "condition_unknown_question"),
        ({"question_id": "Q3", "options": ["Nikdy"]}, "condition_forward_reference"),
        ({"question_id": "Q2", "options": ["5"]}, "condition_not_choice"),
        ({"question_id": "Q1", "options": ["Někdy"]}, "condition_unknown_option"),
        ({"q": "Q1"}, "condition_unstructured"),
    ],
)
def test_an_edit_is_held_to_the_compilers_own_rule(
    condition: dict[str, Any], code: str | None
) -> None:
    """``condition_refusal`` (what ``route_set`` asks before writing) says what compile says."""
    content = _design(_q3(None))
    assert condition_refusal(content, "Q3", condition) == code
    compiled = _codes(_design(_q3(condition)))
    assert compiled == ([] if code is None else [code])


def test_an_edit_on_no_stored_question_is_refused() -> None:
    assert condition_refusal(_design(), "Q9", None) == "unknown_question"


def _routing_checks(content: dict[str, Any], *, routing: bool) -> dict[str, Any]:
    spec, problems = compile_design(content)
    assert problems == () and spec is not None
    readiness = assess_readiness(spec, pair_n_min=AUDIT_PROVISIONAL_N_MIN, routing=routing)
    return {c.id: c for c in readiness.checks}


def test_the_routing_switch_passes_a_valid_condition_and_off_fails_it_as_before() -> None:
    """WCE13 (d): ``AIA_ROUTING_ENABLED`` as a run pins it. Off (the default, and develop's until
    RQC11 routes fieldwork), a valid condition fails readiness exactly as before; on, it passes."""
    content = _design(_q3({"question_id": "Q1", "options": ["Nikdy"]}))
    off = _routing_checks(content, routing=False)["conditional_questions"]
    assert off.status is CheckStatus.FAIL and "q3" in off.message
    spec, _ = compile_design(content)
    assert spec is not None
    default = assess_readiness(spec, pair_n_min=AUDIT_PROVISIONAL_N_MIN)
    assert next(c for c in default.checks if c.id == "conditional_questions") == off
    on = _routing_checks(content, routing=True)["conditional_questions"]
    assert on.status is CheckStatus.PASS and "q3" in on.message


def test_routing_never_passes_a_condition_compile_refused() -> None:
    checks = _routing_checks(
        _design(_q3({"question_id": "Q1", "options": ["Někdy"]})), routing=True
    )
    assert checks["condition:q3"].status is CheckStatus.FAIL
    assert "conditional_questions" not in checks


def test_routing_asks_a_valid_condition_of_part_of_the_sample_whose_support_is_unknown() -> None:
    """The outlook: off, a conditional question is unanswerable (everyone is asked it); on, it is
    asked of those it names, a part the forecast does not model, so its support is unknown."""
    spec, _ = compile_design(
        _design(
            _q3({"question_id": "Q1", "options": ["Nikdy"]}),
            {"id": "Q4", "text": "Kolik?", "typ": "skala", "skala": [1, 5],
             "filtr": {"question_id": "Q1", "options": ["Někdy"]}},
        )
    )  # fmt: skip
    assert spec is not None
    # The whole sample's support is reportable: what a question everyone answers would have.
    whole = SupportForecast(
        persona_source=PersonaSource.FICTIONAL_ROSTER,
        respondents=300,
        donors=300,
        results=SupportStatus.REPORTABLE,
        analysis=SupportStatus.REPORTABLE,
    )
    off = {o.question_id: o for o in question_outlook(spec, whole)}
    assert OutlookReason.CONDITIONAL in off["q3"].reasons
    assert off["q3"].verdict is Verdict.UNANSWERABLE
    assert off["q2"].verdict is Verdict.ANSWERABLE
    on = {o.question_id: o for o in question_outlook(spec, whole, routing=True)}
    assert on["q2"] == off["q2"], "a question everyone answers is read as before"
    assert OutlookReason.CONDITIONAL not in on["q3"].reasons
    assert OutlookReason.SUPPORT_UNKNOWN in on["q3"].reasons
    assert on["q3"].verdict is not Verdict.ANSWERABLE, "never good on a part not forecast"
    # A refused condition is never routed.
    assert OutlookReason.CONDITIONAL in on["q4"].reasons
    assert on["q4"].verdict is Verdict.UNANSWERABLE
