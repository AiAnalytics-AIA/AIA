"""The Lead's Deep Research requests and what grounds them (lead-orchestration LO5a.1): the
request's preset, focus, target and retry; the ``targets`` and ``deep_research`` layers; their
bounds and class."""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.ai_contracts import canonical_json, validate_structured_output
from aia_core.domain.analysis.modules import AnalysisModuleId
from aia_core.domain.item_ids import list_ids, with_item_ids
from aia_core.domain.lead_research_targets import (
    DEEP_RESEARCH_MAX_BYTES,
    TARGETS_MAX,
    TARGETS_MAX_BYTES,
    FinishedRun,
    ModuleOutcome,
    deep_research_layer,
    interpretation_candidates,
    targets_layer,
)
from aia_core.domain.prompt_slots import get_slot
from aia_core.domain.prompts import PromptPin
from aia_core.domain.research_lead import (
    CONTEXT_MAX_BYTES,
    DEFAULT_LEAD_NAME,
    DEFAULT_SOUL,
    LEAD_PROMPT_ID,
    RequestIds,
    context_bytes,
    context_classification,
    freeze_context,
    layer,
    lead_contract,
    lead_prompt,
    request_ids,
)
from aia_core.domain.residency import DataClass

WHY = "Protože výsledek potřebuje kontext."
RQ1 = "Proč lidé kupují rostlinné nápoje?"
RQ2 = "Kdo je nekupuje?"
DESIGN = {
    "title": "Rostlinné nápoje",
    "goal": "Test",
    "research_plan": {"research_questions": [RQ1, RQ2]},
}
RQ_IDS = list_ids(
    with_item_ids(DESIGN)[0]["research_plan"], "research_questions", "research_question_ids"
)

#: The workbench fixture run's shape: one question, one set of three objects, every module.
SPEC = {
    "questions": [
        {"id": "q1", "text": "Jak často pijete rostlinné nápoje?", "research_questions": [RQ1]}
    ],
    "batteries": [
        {
            "id": "s1",
            "title": "Značky",
            "research_questions": [RQ2],
            "objects": [
                {"id": "o1", "label": "Alfa"},
                {"id": "o2", "label": "Beta"},
                {"id": "o3", "label": "Gama"},
            ],
        }
    ],
}


def _bytes(value: Any) -> int:
    return len(canonical_json(value).encode("utf-8"))


def _run(run_id: str = "RUN-aaaa0001", **kw: Any) -> FinishedRun:
    modules = kw.pop(
        "modules",
        [
            ModuleOutcome(AnalysisModuleId.EXECUTIVE, "ART-0000000000000001", "COMPLETED"),
            ModuleOutcome(AnalysisModuleId.RESEARCH_QUESTIONS, "ART-0000000000000002", "COMPLETED"),
            ModuleOutcome(AnalysisModuleId.SEGMENTS, "ART-0000000000000003", "BLOCKED"),
        ],
    )
    return FinishedRun(
        run_id=run_id,
        specification=kw.pop("specification", SPEC),
        aggregate_artifact_id=kw.pop("aggregate_artifact_id", "ART-0000000000000010"),
        sociomap_artifact_id=kw.pop("sociomap_artifact_id", "ART-0000000000000011"),
        modules=modules,
    )


# --------------------------------------------------------------------------- candidates


def test_the_fixture_runs_candidates_cover_every_result_kind_in_reading_order() -> None:
    candidates, omitted = interpretation_candidates([_run()])
    assert omitted == 0
    assert [(c["id"], c["kind"], c["words"]) for c in candidates] == [
        ("t1", "ANALYSIS_MODULE", "Analýza: Odpovědi na výzkumné otázky"),
        ("t2", "ANALYSIS_MODULE", "Analýza: Shrnutí pro vedení"),
        ("t3", "RESULT_QUESTION", "Výsledek otázky: Jak často pijete rostlinné nápoje?"),
        ("t4", "SOCIOMAP", "Sociomapa sady: Značky"),
        ("t5", "RESULT_BATTERY_OBJECT", "Hodnocení: Alfa (Značky)"),
        ("t6", "RESULT_BATTERY_OBJECT", "Hodnocení: Beta (Značky)"),
        ("t7", "RESULT_BATTERY_OBJECT", "Hodnocení: Gama (Značky)"),
        ("t8", "SOCIOMAP_OBJECT", "Na mapě: Alfa (Značky)"),
        ("t9", "SOCIOMAP_OBJECT", "Na mapě: Beta (Značky)"),
        ("t10", "SOCIOMAP_OBJECT", "Na mapě: Gama (Značky)"),
        ("t11", "SOCIOMAP_RELATIONSHIP", "Vztah na mapě: Alfa a Beta"),
        ("t12", "SOCIOMAP_RELATIONSHIP", "Vztah na mapě: Alfa a Gama"),
        ("t13", "SOCIOMAP_RELATIONSHIP", "Vztah na mapě: Beta a Gama"),
    ]
    # The ref is the ADR 0021 target the start freezes and verifies again.
    assert candidates[0]["ref"] == {
        "kind": "ANALYSIS_MODULE",
        "research_run_id": "RUN-aaaa0001",
        "analysis_artifact_id": "ART-0000000000000002",
        "module_id": "research_questions",
    }


def test_a_blocked_module_is_left_out() -> None:
    candidates, _ = interpretation_candidates([_run()])
    modules = [c["ref"].get("module_id") for c in candidates if c["kind"] == "ANALYSIS_MODULE"]
    assert "segments" not in modules


def test_a_candidates_connections_name_its_research_questions() -> None:
    by_words = {c["words"]: c for c in interpretation_candidates([_run()])[0]}
    rqs = lambda w: by_words[w]["connections"]["research_questions"]  # noqa: E731
    # The research-questions module answers every one the run's items declare.
    assert rqs("Analýza: Odpovědi na výzkumné otázky") == [RQ1, RQ2]
    assert rqs("Výsledek otázky: Jak často pijete rostlinné nápoje?") == [RQ1]
    assert rqs("Na mapě: Alfa (Značky)") == [RQ2]
    assert rqs("Analýza: Shrnutí pro vedení") == []


def test_a_step_that_did_not_succeed_offers_nothing_of_its_kind() -> None:
    kinds = {
        c["kind"]
        for c in interpretation_candidates(
            [_run(sociomap_artifact_id=None, aggregate_artifact_id=None, modules=[])]
        )[0]
    }
    assert kinds == set()


def test_the_newest_runs_come_first_and_the_list_is_bounded_and_counted() -> None:
    objects = [{"id": f"o{i}", "label": f"Objekt {i}"} for i in range(12)]
    big = {"questions": [], "batteries": [{"id": "s1", "title": "Velká", "objects": objects}]}
    candidates, omitted = interpretation_candidates(
        [_run("RUN-bbbb0002", specification=big), _run()], max_bytes=10**6
    )
    assert len(candidates) == TARGETS_MAX and omitted > 0
    assert candidates[0]["run_id"] == "RUN-bbbb0002"
    assert [c["id"] for c in candidates] == [f"t{i}" for i in range(1, TARGETS_MAX + 1)]


def test_the_targets_layer_keeps_its_own_byte_budget() -> None:
    long = "Velmi dlouhá otázka " * 20
    spec = {"questions": [{"id": f"q{i}", "text": long} for i in range(40)], "batteries": []}
    candidates, omitted = interpretation_candidates([_run(specification=spec)], max_bytes=4000)
    assert omitted > 0
    assert _bytes(candidates) <= 4000
    # A candidate's words are bounded too.
    assert all(len(c["words"]) <= 160 for c in candidates)


def test_the_default_is_the_newest_research_questions_module_or_none() -> None:
    assert targets_layer([_run()])["default"] == "t1"
    without = _run(
        modules=[ModuleOutcome(AnalysisModuleId.EXECUTIVE, "ART-0000000000000001", "COMPLETED")]
    )
    assert targets_layer([without])["default"] is None
    assert targets_layer([]) == {"candidates": [], "default": None, "omitted": 0}


# ------------------------------------------------------------------------- the deep_research layer

DR_RUN = {
    "run_id": "RUN-dddd0001",
    "status": "AWAITING_BUDGET",
    "phase": "WAITING",
    "retryable": False,
    "metadata": {
        "purpose": "INTERPRETATION_RESEARCH",
        "target": {
            "kind": "ANALYSIS_MODULE",
            "research_run_id": "RUN-aaaa0001",
            "analysis_artifact_id": "ART-0000000000000002",
            "module_id": "research_questions",
        },
        "preset": "STANDARD",
        "subjects": 2,
        "cost_ceiling_usd": 1.25,
    },
    "steps": [
        {
            "status": "SUCCEEDED",
            "attempts": [{"actual_cost_usd": 0.1}],
        },
        {
            "status": "WAITING",
            "waiting_reason": "budget_exhausted",
            "attempts": [{"actual_cost_usd": None}],
        },
    ],
}


def test_a_deep_research_run_is_read_into_its_layer_in_words() -> None:
    candidates = targets_layer([_run()])["candidates"]
    out = deep_research_layer([DR_RUN], candidates)
    assert out == {
        "runs": [
            {
                "run_id": "RUN-dddd0001",
                "purpose": "INTERPRETATION_RESEARCH",
                "target": "Analýza: Odpovědi na výzkumné otázky",
                "preset": "STANDARD",
                "status": "AWAITING_BUDGET",
                "phase": "WAITING",
                "park": "budget_exhausted",
                "retryable": False,
                "subjects": 2,
                "steps_done": 1,
                "steps": 2,
                "actual_cost_usd": 0.1,
                "cost_ceiling_usd": 1.25,
            }
        ],
        "omitted": 0,
    }


def test_an_unknown_cost_is_none_never_zero() -> None:
    run = {**DR_RUN, "metadata": {"purpose": "DESIGN_RESEARCH"}, "steps": [{"attempts": []}]}
    entry = deep_research_layer([run])["runs"][0]
    assert entry["actual_cost_usd"] is None and entry["cost_ceiling_usd"] is None
    assert entry["target"] == "neuvedeno"


def test_the_deep_research_layer_keeps_its_own_byte_budget() -> None:
    runs = [{**DR_RUN, "run_id": f"RUN-dddd{i:04d}"} for i in range(5)]
    out = deep_research_layer(runs)
    assert _bytes(out["runs"]) <= DEEP_RESEARCH_MAX_BYTES
    assert len(out["runs"]) + out["omitted"] == 5


# --------------------------------------------------------------------------- the context


def _context(**overrides: Any) -> dict[str, Any]:
    slot = get_slot(LEAD_PROMPT_ID)
    assert slot is not None
    fields: dict[str, Any] = {
        "prompt": slot.baseline_pin(),
        "lead": {"name": DEFAULT_LEAD_NAME, "soul": DEFAULT_SOUL, "user": "", "notes": []},
        "knowledge": [],
        "omitted_knowledge_ids": [],
        "study": {"name": "S", "client_name": "C", "budget_usd": 25.0, "spent_usd": 0.0},
        "design": {"design_revision_id": "REV-1", "content": DESIGN, "analysis": None},
        "runs": [],
        "view": {"kind": "message", "stage": "results", "focus": None, "message": "Ahoj"},
        "conversation": [],
        "deep_research": deep_research_layer([DR_RUN], targets_layer([_run()])["candidates"]),
        "targets": targets_layer([_run()]),
    }
    fields.update(overrides)
    return freeze_context(**fields)


def test_the_layers_sit_after_the_runs_and_a_deep_research_run_is_in_the_context() -> None:
    context = _context()
    names = [entry["layer"] for entry in context["layers"]]
    assert names[names.index("runs") + 1 : names.index("runs") + 3] == ["deep_research", "targets"]
    assert layer(context, "deep_research")["runs"][0]["run_id"] == "RUN-dddd0001"
    # Absent, the context is what it was.
    assert "targets" not in [
        e["layer"] for e in _context(deep_research=None, targets=None)["layers"]
    ]


def test_both_layers_at_their_bounds_fit_inside_the_context() -> None:
    assert TARGETS_MAX_BYTES + DEEP_RESEARCH_MAX_BYTES < CONTEXT_MAX_BYTES // 4
    objects = [{"id": f"o{i}", "label": "Objekt " * 10} for i in range(30)]
    big = {"questions": [], "batteries": [{"id": "s1", "title": "Velká", "objects": objects}]}
    targets = targets_layer([_run(specification=big), _run()])
    dr = deep_research_layer([{**DR_RUN, "run_id": f"RUN-dddd{i:04d}"} for i in range(5)])
    context = _context(targets=targets, deep_research=dr)
    assert context_bytes(context) <= CONTEXT_MAX_BYTES


def test_both_layers_take_the_designs_class_by_rule() -> None:
    context = _context()
    prompt = PromptPin(**layer(context, "prompt")["pin"])
    parts = {p["part"]: p for p in context_classification(context, (), prompt)}
    for name in ("deep_research", "targets"):
        assert parts[name]["data_class"] == DataClass.CLASS_B_DERIVED_CLIENT.value
        assert parts[name]["source"] == "rule:design"


# --------------------------------------------------------------------------- the request


def _valid(request: dict[str, Any], context: dict[str, Any] | None = None) -> Any:
    ids = request_ids(context if context is not None else _context())
    contract = lead_contract("", ids=ids)
    return validate_structured_output(
        contract, structured={"reply": "Dobře.", "request": request}, text=""
    )


def test_request_ids_read_the_design_targets_and_runs() -> None:
    assert RQ_IDS is not None
    assert request_ids(_context()) == RequestIds(
        research_questions=frozenset(RQ_IDS),
        targets=frozenset(f"t{i}" for i in range(1, 14)),
        default_target="t1",
        deep_research_runs=frozenset({"RUN-dddd0001"}),
    )


def test_standard_is_the_default_preset_and_deep_is_refused() -> None:
    ok = _valid({"kind": "design_research", "why": WHY})
    assert ok.ok and ok.value.request.preset == "STANDARD"
    assert _valid({"kind": "design_research", "why": WHY, "preset": "QUICK"}).ok
    for preset in ("DEEP", "EXHAUSTIVE"):
        assert not _valid({"kind": "design_research", "why": WHY, "preset": preset}).ok
        assert not _valid({"kind": "interpretation_research", "why": WHY, "preset": preset}).ok


def test_a_focus_names_only_the_designs_research_questions() -> None:
    assert RQ_IDS is not None
    assert _valid({"kind": "design_research", "why": WHY, "focus": [RQ_IDS[1]]}).ok
    refused = _valid({"kind": "design_research", "why": WHY, "focus": ["rq_nope"]})
    assert not refused.ok


def test_a_target_names_only_a_candidate_and_none_takes_the_default() -> None:
    assert _valid({"kind": "interpretation_research", "why": WHY, "target": "t4"}).ok
    assert _valid({"kind": "interpretation_research", "why": WHY}).ok
    assert not _valid({"kind": "interpretation_research", "why": WHY, "target": "t99"}).ok
    # No research-questions module: a target must be named; no candidates: nothing is.
    no_default = _context(
        targets=targets_layer(
            [
                _run(
                    modules=[
                        ModuleOutcome(
                            AnalysisModuleId.EXECUTIVE, "ART-0000000000000001", "COMPLETED"
                        )
                    ]
                )
            ]
        )
    )
    assert not _valid({"kind": "interpretation_research", "why": WHY}, no_default).ok
    assert _valid({"kind": "interpretation_research", "why": WHY, "target": "t1"}, no_default).ok
    nothing = _context(targets=None)
    assert not _valid({"kind": "interpretation_research", "why": WHY, "target": "t1"}, nothing).ok


@pytest.mark.parametrize("run_id", ["RUN-dddd0001"])
def test_a_retry_names_only_a_run_of_the_layer(run_id: str) -> None:
    assert _valid({"kind": "deep_research_retry", "why": WHY, "run_id": run_id}).ok
    assert not _valid({"kind": "deep_research_retry", "why": WHY, "run_id": "RUN-eeee0001"}).ok
    assert not _valid({"kind": "deep_research_retry", "why": WHY}).ok


def test_the_prompt_says_a_reserse_is_external_context_never_respondent_evidence() -> None:
    prompt = lead_prompt()
    assert "vnější kontext, nikdy důkaz od respondentů" in prompt
    assert "targets" in prompt and "deep_research_retry" in prompt
