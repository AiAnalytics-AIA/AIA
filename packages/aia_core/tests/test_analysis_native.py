"""Native evidence: a run's specification and aggregate -> what an analysis module may cite."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from aia_core.domain.analysis import AnalysisModuleId, check_analysis_draft, module_spec
from aia_core.domain.analysis.native import (
    INTERVAL_LEVEL,
    MAX_RESEARCH_QUESTIONS,
    NativeEvidence,
    NativeEvidenceRefused,
    native_evidence,
    native_items,
    native_preflight,
    research_questions_of,
)
from aia_core.domain.evidence import (
    ClaimBasis,
    ClaimLevel,
    ClaimSurface,
    Disclosure,
    InstrumentPolicyRefused,
    JointDegradation,
    MetricKind,
    SupportStatus,
    ViolationCode,
)
from aia_core.domain.fieldwork import DataOrigin, FieldworkDataset
from aia_core.domain.research_aggregate import aggregate_dataset
from aia_core.domain.research_design import ResearchSpecification, compile_design
from aia_core.domain.synthetic_fieldwork import synthetic_dataset

DATASET_SHA = "d" * 64

DESIGN: dict[str, Any] = {
    "title": "Ranní nápoj",
    "n": 200,
    "research_plan": {"research_questions": ["Co lidé ráno pijí?", "Jak hodnotí kávu?"]},
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                {
                    "id": "q2",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic"],
                    "povolit_nevim": True,
                },
                {
                    "id": "q3",
                    "text": "Co ještě snídáte?",
                    "typ": "multi",
                    "kategorie": ["Pečivo", "Ovoce", "Nic"],
                },
                {"id": "q4", "text": "Proč?", "typ": "otevrena"},
                {
                    "id": "q5",
                    "text": "Kolik byste zaplatil za šálek kávy?",
                    "typ": "vyber",
                    "kategorie": ["Málo", "Středně", "Hodně"],
                },
            ],
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
        },
    ],
}


def run(design: dict[str, Any] = DESIGN) -> tuple[ResearchSpecification, FieldworkDataset, Any]:
    spec, problems = compile_design(design)
    assert spec is not None, problems
    dataset = synthetic_dataset(spec, seed=20260816)
    return spec, dataset, aggregate_dataset(spec, dataset)


@pytest.fixture(scope="module")
def built() -> tuple[ResearchSpecification, Any, NativeEvidence]:
    spec, dataset, aggregate = run()
    evidence = native_evidence(spec, aggregate, dataset_sha256=DATASET_SHA, origin=dataset.origin)
    return spec, aggregate, evidence


def question(spec: ResearchSpecification, qid: str) -> Any:
    return next(q for q in spec.questions if q.id == qid)


# --- research questions -----------------------------------------------------------------


def test_research_questions_come_from_the_plan_then_objectives_then_the_goal() -> None:
    plan = {"research_questions": [" A? ", "B?"], "objectives": ["O"]}
    assert research_questions_of({"research_plan": plan, "goal": "G"}) == ("A?", "B?")
    assert research_questions_of({"research_plan": {"objectives": ["O"]}, "goal": "G"}) == ("O",)
    assert research_questions_of({"goal": " G "}) == ("G",)
    assert research_questions_of({}) == ()


def test_research_questions_are_capped_deduplicated_and_never_a_string_split_up() -> None:
    many = [f"Q{i}?" for i in range(12)]
    assert len(research_questions_of({"research_plan": {"research_questions": many}})) == (
        MAX_RESEARCH_QUESTIONS
    )
    assert research_questions_of({"research_plan": {"research_questions": ["A?", "A?"]}}) == ("A?",)
    assert research_questions_of({"research_plan": {"research_questions": "Why?"}}) == ()
    assert research_questions_of({"research_plan": {"research_questions": [1, None, {}]}}) == ()
    assert research_questions_of({"research_plan": "not a plan", "goal": "G"}) == ("G",)


# --- the rows ------------------------------------------------------------------------------


def test_every_item_is_declared_and_every_number_is_a_row_or_a_removed_ref(
    built: tuple[ResearchSpecification, Any, NativeEvidence],
) -> None:
    spec, _, evidence = built
    items = native_items(spec)
    assert [i.question_id for i in items][:5] == ["q1", "q2", "q3", "q4", "q5"]
    assert len(items) == 5 + 4
    assert set(evidence.book.fields) == {f"instrument:{i.question_id}" for i in items}
    refs = set(evidence.table.rows) | set(evidence.table.suppressed)
    assert {"q1.n", "q1.effective_n", "q1.mean", "q1.top2box"} <= refs
    assert {"q2.pct.1", "q2.pct.2", "q2.pct.3", "q2.pct.4"} <= refs  # + "Nevím / neodpovím"
    assert {"q3.pct.1", "q3.pct.2", "q3.pct.3"} <= refs
    assert {"q4.n", "q4.effective_n"} <= refs and not any(
        r.startswith("q4.pct") or r.startswith("q4.mean") for r in refs
    )
    battery = spec.batteries[0]
    first = battery.question_id(battery.objects[0])
    assert {f"{first}.mean", f"{first}.top2box"} <= refs
    assert evidence.rows_considered == len(refs)


def test_a_row_copies_the_aggregate_exactly_with_its_interval_and_origin(
    built: tuple[ResearchSpecification, Any, NativeEvidence],
) -> None:
    _, aggregate, evidence = built
    result = aggregate["questions"]["q2"]
    row = evidence.table.rows["q2.pct.1"]
    assert row.value == result["celkem_pct"]["Kávu"] and row.decimals == 1
    assert str(row.metric) == "pct:Kávu" and row.unit.value == "%"
    assert row.interval is not None and row.interval.level == INTERVAL_LEVEL
    assert (row.interval.lower, row.interval.upper) == (
        result["intervaly_95"]["Kávu"]["low"],
        result["intervaly_95"]["Kávu"]["high"],
    )
    assert row.basis is ClaimBasis.MODELED and row.level is ClaimLevel.AGGREGATE
    assert row.fields == ("instrument:q2",) and row.question_id == "q2"
    assert row.data_origin is DataOrigin.SYNTHETIC_FIXTURE
    assert row.disclosures == frozenset({Disclosure.MODELED_VALUE})
    assert row.cell == "Co si ráno koupíte? | odpověď: Kávu"

    mean = evidence.table.rows["q1.mean"]
    assert mean.value == aggregate["questions"]["q1"]["prumer"] and mean.decimals == 2
    assert mean.metric.kind is MetricKind.MEAN and mean.cell.endswith("průměr, škála 1-5")
    n = evidence.table.rows["q1.n"]
    assert n.value == aggregate["questions"]["q1"]["n_platnych"] and n.interval is None


def test_support_is_the_units_reassessed_by_aias_stricter_thresholds(
    built: tuple[ResearchSpecification, Any, NativeEvidence],
) -> None:
    _, aggregate, evidence = built
    row = evidence.table.rows["q1.mean"]
    unit = aggregate["questions"]["q1"]
    assert unit["support_status"] in {"INDICATIVE", "REPORTABLE"}
    assert row.support.status in {SupportStatus.INDICATIVE, SupportStatus.REPORTABLE}
    assert row.support.effective_n == unit["effective_n"]


def test_a_thin_run_has_no_citable_evidence_and_says_why() -> None:
    spec, dataset, aggregate = run({**DESIGN, "n": 60})  # 20 fictional donors < 25
    evidence = native_evidence(spec, aggregate, dataset_sha256=DATASET_SHA, origin=dataset.origin)
    assert evidence.table.rows == {}
    reasons = evidence.table.suppressed["q1.mean"].reasons
    assert any("unique layer donors" in r for r in reasons)
    blocked = native_preflight(
        module_spec(AnalysisModuleId.EXECUTIVE),
        evidence,
        surface=ClaimSurface.INTERNAL,
        research_questions=("Q?",),
    )
    assert [v.code for v in blocked] == [ViolationCode.SUPPORT_SUPPRESSED]


def test_a_question_the_fidelity_rule_refuses_backs_nothing(
    built: tuple[ResearchSpecification, Any, NativeEvidence],
) -> None:
    _, aggregate, evidence = built
    assert aggregate["questions"]["q5"]["evidence"]["mode"] == "REFUSE"
    q5 = [ref for ref in evidence.table.suppressed if ref.startswith("q5.")]
    assert q5 and not any(ref.startswith("q5.") for ref in evidence.table.rows)
    assert all(evidence.table.suppressed[ref].reasons[0].startswith("fidelity RED") for ref in q5)


@pytest.mark.parametrize(
    ("mutate", "why"),
    [
        (lambda r: r["intervaly_95"]["Kávu"].update(low=0.0, high=0.1), "outside its interval"),
        (lambda r: r["intervaly_95"].pop("Kávu"), "no interval"),
        (lambda r: r["intervaly_95"]["Kávu"].update(low=90.0, high=10.0), "malformed"),
        (lambda r: r["celkem_pct"].update({"Kávu": 41.25}), "not rounded"),
        (lambda r: r["celkem_pct"].pop("Kávu"), "no estimate"),
        (lambda r: r.update(support_status="SUPPRESS"), "the unit suppressed"),
        (lambda r: r.update(support_status="GREEN"), "unknown support status"),
        (lambda r: r.pop("evidence"), "no fidelity rating"),
    ],
)
def test_a_number_without_what_it_needs_is_removed_keeping_why(mutate: Any, why: str) -> None:
    spec, dataset, aggregate = run()
    changed = copy.deepcopy(aggregate)
    mutate(changed["questions"]["q2"])
    evidence = native_evidence(spec, changed, dataset_sha256=DATASET_SHA, origin=dataset.origin)
    assert "q2.pct.1" not in evidence.table.rows
    assert any(why in r for r in evidence.table.suppressed["q2.pct.1"].reasons)


# --- refusals ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda a: a.update(aggregate_version="other"), "computed by"),
        (lambda a: a.update(data_origin="SYNTHETIC_AI_FICTIONAL"), "data origin"),
        (lambda a: a["questions"].pop("q1"), "differently"),
        (lambda a: a["questions"].update(q9=a["questions"]["q1"]), "differently"),
        (lambda a: a["questions"]["q1"].update(typ="vyber"), "another type"),
        (lambda a: a["batteries"].clear(), "tracked sets"),
        (lambda a: next(iter(a["batteries"].values()))["objects"].clear(), "no result"),
        (lambda a: a.pop("questions"), "no questions"),
    ],
)
def test_artifacts_that_do_not_describe_one_computation_are_refused(
    mutate: Any, match: str
) -> None:
    spec, dataset, aggregate = run()
    changed = copy.deepcopy(aggregate)
    mutate(changed)
    with pytest.raises(NativeEvidenceRefused, match=match):
        native_evidence(spec, changed, dataset_sha256=DATASET_SHA, origin=dataset.origin)


def test_answers_of_no_known_origin_have_no_policy() -> None:
    spec, _, aggregate = run()
    with pytest.raises(InstrumentPolicyRefused):
        native_evidence(
            spec, {**aggregate, "data_origin": None}, dataset_sha256=DATASET_SHA, origin=None
        )
    with pytest.raises(NativeEvidenceRefused, match="SHA-256"):
        native_evidence(
            spec, aggregate, dataset_sha256="short", origin=DataOrigin.SYNTHETIC_FIXTURE
        )


def test_a_native_run_has_no_certificate_and_its_system_is_its_own(
    built: tuple[ResearchSpecification, Any, NativeEvidence],
) -> None:
    spec, aggregate, evidence = built
    assert not evidence.joint_status.certified
    assert evidence.joint_status.degradation is JointDegradation.MISSING
    other = native_evidence(
        spec, aggregate, dataset_sha256="e" * 64, origin=DataOrigin.SYNTHETIC_FIXTURE
    )
    assert other.system_fingerprint != evidence.system_fingerprint
    assert other.book.source_sha256 != evidence.book.source_sha256
    assert other.table.fingerprint() == evidence.table.fingerprint()


# --- preflight and the gate ---------------------------------------------------------------


def test_client_facing_is_refused_before_anything_is_sent(
    built: tuple[ResearchSpecification, Any, NativeEvidence],
) -> None:
    _, _, evidence = built
    blocked = native_preflight(
        module_spec(AnalysisModuleId.EXECUTIVE),
        evidence,
        surface=ClaimSurface.CLIENT_FACING,
        research_questions=("Q?",),
    )
    assert [v.code for v in blocked] == [
        ViolationCode.SYNTHETIC_DATA_ORIGIN,
        ViolationCode.FIELD_INTERNAL_ONLY,
        ViolationCode.JOINT_CERTIFICATE_DEGRADED,
    ]
    assert all(v.subject == "preflight" for v in blocked)


def test_internal_modules_may_run_but_research_questions_needs_a_question(
    built: tuple[ResearchSpecification, Any, NativeEvidence],
) -> None:
    _, _, evidence = built
    for module in AnalysisModuleId:
        found = native_preflight(
            module_spec(module), evidence, surface=ClaimSurface.INTERNAL, research_questions=()
        )
        expected = (
            [ViolationCode.RESEARCH_QUESTION_UNANSWERED]
            if module is AnalysisModuleId.RESEARCH_QUESTIONS
            else []
        )
        assert [v.code for v in found] == expected, module


def draft(row: Any, text: str) -> dict[str, Any]:
    return {
        "module": "executive",
        "summary": text,
        "key_findings": [{"text": text, "claim_ids": ["c1"]}],
        "numeric_claims": [
            {
                "claim_id": "c1",
                "evidence_ref": row.evidence_ref,
                "metric": str(row.metric),
                "value": row.value,
                "unit": row.unit.value,
            }
        ],
    }


def test_a_draft_citing_native_evidence_passes_internally_and_never_client_facing(
    built: tuple[ResearchSpecification, Any, NativeEvidence],
) -> None:
    _, _, evidence = built
    row = evidence.table.rows["q2.pct.1"]
    text = f"Kávu si ráno koupí {row.value:.1f} % fiktivních respondentů.".replace(".", ",", 1)
    raw = draft(row, text)

    def check(surface: ClaimSurface) -> Any:
        return check_analysis_draft(
            raw,
            module_spec(AnalysisModuleId.EXECUTIVE),
            evidence.table,
            book=evidence.book,
            joint_status=evidence.joint_status,
            surface=surface,
            research_questions=(),
        )

    assert check(ClaimSurface.INTERNAL).decision.allowed
    refused = check(ClaimSurface.CLIENT_FACING).decision.codes
    assert {
        ViolationCode.FIELD_INTERNAL_ONLY,
        ViolationCode.SYNTHETIC_DATA_ORIGIN,
        ViolationCode.JOINT_CERTIFICATE_DEGRADED,
    } <= refused
