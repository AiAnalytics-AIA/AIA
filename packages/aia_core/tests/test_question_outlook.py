"""Which questions a run will answer, before it starts (plan run-recovery-and-truth 2b)."""

from __future__ import annotations

from typing import Any

from aia_core.domain.analysis.native import native_evidence
from aia_core.domain.evidence import SupportStatus
from aia_core.domain.evidence.support import AIA_SUPPORT_V1, SupportSpec, SupportThresholds
from aia_core.domain.fieldwork import PersonaSource
from aia_core.domain.question_outlook import OutlookReason, Verdict, question_outlook
from aia_core.domain.research_aggregate import aggregate_dataset
from aia_core.domain.research_design import compile_design
from aia_core.domain.support_forecast import forecast_support
from aia_core.domain.synthetic_fieldwork import synthetic_dataset

#: A question per rule, and a tracked set: everything the outlook decides on.
DESIGN: dict[str, Any] = {
    "title": "Fiktivní ranní nápoj",
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                {
                    "id": "q2",
                    "text": "Kolik Kč byste maximálně zaplatili za kávu?",
                    "typ": "skala",
                    "skala": [1, 5],
                },
                {"id": "q3", "text": "Co vás ráno probudí?", "typ": "otevrena"},
                {
                    "id": "q4",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic"],
                },
            ],
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
        },
    ],
}

ROSTER = PersonaSource.FICTIONAL_ROSTER


def _spec(n: int, design: dict[str, Any] = DESIGN) -> Any:
    spec, problems = compile_design({**design, "n": n})
    assert spec is not None, problems
    return spec


def _by_id(spec: Any, forecast: Any) -> dict[str, Any]:
    return {o.question_id: o for o in question_outlook(spec, forecast)}


def test_every_item_is_listed_in_questionnaire_order_with_the_wording_asked() -> None:
    spec = _spec(200)
    outlook = question_outlook(
        spec, forecast_support(spec, support=AIA_SUPPORT_V1, persona_source=ROSTER)
    )
    assert [o.question_id for o in outlook] == [
        *(q.id for q in spec.questions),
        *spec.battery_questions(),
    ]
    first_object = next(o for o in outlook if o.battery_id is not None)
    assert first_object.text == "Jak hodnotíte Káva?"
    assert first_object.section_id == first_object.battery_id


def test_with_support_each_question_gets_the_verdict_its_own_rule_gives() -> None:
    spec = _spec(200)
    forecast = forecast_support(spec, support=AIA_SUPPORT_V1, persona_source=ROSTER)
    assert forecast.analysis is not None and forecast.analysis.value == "REPORTABLE"
    items = _by_id(spec, forecast)
    q1, q2, q3, q4 = (spec.questions[i].id for i in range(4))
    assert items[q1].verdict is Verdict.ANSWERABLE and items[q1].reasons == ()
    assert items[q2].verdict is Verdict.UNANSWERABLE
    assert items[q2].reasons == (OutlookReason.FIDELITY_REFUSED,)
    assert items[q3].verdict is Verdict.AT_RISK
    assert items[q3].reasons == (OutlookReason.OPEN_ENDED,)
    assert items[q4].verdict is Verdict.ANSWERABLE
    assert all(items[qid].verdict is Verdict.ANSWERABLE for qid in spec.battery_questions())


def test_suppressed_support_makes_every_item_unanswerable_and_keeps_its_other_reasons() -> None:
    spec = _spec(50)
    forecast = forecast_support(spec, support=AIA_SUPPORT_V1, persona_source=ROSTER)
    items = question_outlook(spec, forecast)
    assert {o.verdict for o in items} == {Verdict.UNANSWERABLE}
    assert all(OutlookReason.SUPPORT_SUPPRESSED in o.reasons for o in items)
    open_ended = next(o for o in items if o.question_id == spec.questions[2].id)
    assert open_ended.reasons == (OutlookReason.OPEN_ENDED, OutlookReason.SUPPORT_SUPPRESSED)


def test_unknown_support_is_never_answerable() -> None:
    spec = _spec(200)
    for forecast in (
        None,
        forecast_support(spec, support=AIA_SUPPORT_V1, persona_source=PersonaSource.PANEL),
    ):
        items = _by_id(spec, forecast)
        plain = items[spec.questions[0].id]
        assert plain.verdict is Verdict.UNKNOWN
        assert plain.reasons == (OutlookReason.SUPPORT_UNKNOWN,)
        # A known refusal still outranks the unknown.
        assert items[spec.questions[1].id].verdict is Verdict.UNANSWERABLE


def test_a_conditional_question_and_a_familiarity_set_cannot_be_asked() -> None:
    design = {
        **DESIGN,
        "sections": [
            {
                "type": "questions",
                "questions": [
                    {
                        "id": "q1",
                        "text": "Jak často pijete kávu?",
                        "typ": "skala",
                        "skala": [1, 5],
                        "filtr": "q0 == Ano",
                    }
                ],
            },
            {**DESIGN["sections"][1], "familiarity_required": True},
        ],
    }
    spec = _spec(200, design)
    forecast = forecast_support(spec, support=AIA_SUPPORT_V1, persona_source=ROSTER)
    items = question_outlook(spec, forecast)
    assert items[0].reasons[0] is OutlookReason.CONDITIONAL
    assert all(o.verdict is Verdict.UNANSWERABLE for o in items)
    assert all(o.reasons[0] is OutlookReason.FAMILIARITY for o in items[1:])


def test_what_the_outlook_refuses_the_analysis_gate_then_removes() -> None:
    """The rules the outlook reads are the gate's: over a run's real aggregate, a refused
    question keeps no row and an open question keeps no content row."""
    spec = _spec(400)
    dataset = synthetic_dataset(spec, seed=20261014)
    aggregate = aggregate_dataset(spec, dataset, support=AIA_SUPPORT_V1)
    table = native_evidence(
        spec,
        aggregate,
        dataset_sha256="0" * 64,
        origin=dataset.origin,
        support=AIA_SUPPORT_V1.analysis,
    ).table
    kept = {ref.split(".", 1)[0] for ref in table.rows}
    content = {
        ref.split(".", 1)[0]
        for ref in table.rows
        if ref.split(".", 1)[1] not in ("n", "effective_n")
    }
    for item in question_outlook(spec, None):
        others = set(item.reasons) - {OutlookReason.SUPPORT_UNKNOWN}
        if OutlookReason.FIDELITY_REFUSED in others:
            assert item.question_id not in kept, item.question_id
        elif OutlookReason.OPEN_ENDED in others:
            assert item.question_id not in content, item.question_id
        else:
            assert item.question_id in content, item.question_id


def test_numbers_results_shows_but_the_analysis_may_not_cite_are_at_risk_not_suppressed() -> None:
    """Review (Codex on #419): a version whose results rule is looser than its analysis rule
    shows a question's numbers on Results while the analysis suppresses them; the outlook
    must not say they are hidden."""
    lenient = SupportThresholds(
        min_cell=None, n_guard=None, indicative=None, min_layer_donors=5, indicative_layer_donors=5
    )
    support = SupportSpec(
        methodology_version="test-split", results=lenient, analysis=AIA_SUPPORT_V1.analysis
    )
    spec = _spec(50)
    forecast = forecast_support(spec, support=support, persona_source=ROSTER)
    assert forecast.results is SupportStatus.REPORTABLE
    assert forecast.analysis is SupportStatus.SUPPRESS
    plain = _by_id(spec, forecast)[spec.questions[0].id]
    assert plain.verdict is Verdict.AT_RISK
    assert plain.reasons == (OutlookReason.SUPPORT_ANALYSIS_EXCLUDED,)
