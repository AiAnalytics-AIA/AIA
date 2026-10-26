"""What the Lead may name as an Interpretation Research target (lead-orchestration LO5a.1, Q44).

Pure. The study's finished research runs, newest first, each read from what it executed: its
pinned specification and its steps' outputs. Code lists the candidates; the model only names one
by its turn-local id (``t1`` … ``tn``), and the request is refused for an id the list does not
hold (``research_lead.request_refusal``). Each candidate carries:

* ``kind``: the :class:`~aia_core.domain.deep_research.integration.TargetKind`;
* ``words``: what it is in Czech, written by code from the specification's own wording;
* ``connections``: the research questions it answers to, as the design states them (the
  research-questions module answers every one; a question or a set the ones it declares);
* ``ref``: the :data:`~aia_core.domain.deep_research.integration.ResearchTargetRef` behind it,
  which the start freezes and verifies again (``DeepResearchRuns.freeze_interpretation``).

The research-questions module of the newest run is ``t1`` when it completed: the default
candidate an Interpretation request without a target takes (Q44). A module stored BLOCKED is left
out (the web's ``needsRepair`` rule): its outcome is no result to interpret. The list is bounded
(:data:`TARGETS_MAX`) and says how many it left out. No respondent number is in a candidate: the
words are the design's, never the aggregate's.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Final

from pydantic import TypeAdapter, ValidationError

from .ai_contracts import canonical_json
from .analysis.modules import AnalysisModuleId
from .deep_research.integration import ResearchTargetRef, TargetKind

__all__ = [
    "DEEP_RESEARCH_MAX_BYTES",
    "DEEP_RESEARCH_RUNS",
    "MODULE_WORDS",
    "RUNS_FOR_TARGETS",
    "TARGETS_MAX",
    "TARGETS_MAX_BYTES",
    "FinishedRun",
    "ModuleOutcome",
    "deep_research_layer",
    "interpretation_candidates",
    "targets_layer",
]

#: The finished runs whose results are offered, newest first.
RUNS_FOR_TARGETS: Final = 2
#: The most candidates a turn is shown; the rest are counted, never silently dropped.
TARGETS_MAX: Final = 40
#: A candidate's words, bounded so one long question cannot crowd the layer.
WORDS_MAX_CHARS: Final = 160
#: The ``targets`` layer's own share of the context's 96 KB, canonical JSON.
TARGETS_MAX_BYTES: Final = 12 * 1024
#: The study's Deep Research runs a turn is shown, newest first, and their layer's bytes.
DEEP_RESEARCH_RUNS: Final = 5
DEEP_RESEARCH_MAX_BYTES: Final = 4 * 1024

#: Each analysis module in the words the Výsledky screen uses for it.
MODULE_WORDS: Final[Mapping[AnalysisModuleId, str]] = {
    AnalysisModuleId.EXECUTIVE: "Shrnutí pro vedení",
    AnalysisModuleId.RESEARCH_QUESTIONS: "Odpovědi na výzkumné otázky",
    AnalysisModuleId.OBJECTS: "Hodnocené objekty",
    AnalysisModuleId.AUDIENCE: "Cílová skupina",
    AnalysisModuleId.SEGMENTS: "Segmenty",
    AnalysisModuleId.HYPOTHESES: "Hypotézy",
    AnalysisModuleId.IMPLICATIONS: "Doporučení a důsledky",
    AnalysisModuleId.LIMITATIONS: "Omezení",
}

_REF: Final[TypeAdapter[ResearchTargetRef]] = TypeAdapter(ResearchTargetRef)


@dataclass(frozen=True, slots=True)
class ModuleOutcome:
    """One analysis step of a run, as it stored its outcome (``COMPLETED`` or ``BLOCKED``)."""

    module_id: AnalysisModuleId
    artifact_id: str
    outcome: str


@dataclass(frozen=True, slots=True)
class FinishedRun:
    """A finished research run, as the candidates read it: its pinned specification (the
    ``compile`` artifact's ``specification``), the artifacts its aggregate and Sociomap steps
    produced (``None`` when one did not succeed) and its analysis steps that succeeded."""

    run_id: str
    specification: Mapping[str, Any]
    aggregate_artifact_id: str | None = None
    sociomap_artifact_id: str | None = None
    modules: Sequence[ModuleOutcome] = field(default_factory=tuple)


def _words(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= WORDS_MAX_CHARS else text[: WORDS_MAX_CHARS - 1] + "…"


def _texts(values: Any) -> list[str]:
    return [str(v) for v in values or () if isinstance(v, str) and v.strip()]


def _all_research_questions(spec: Mapping[str, Any]) -> list[str]:
    """Every research question the specification's items declare, in their order, once."""
    seen: dict[str, None] = {}
    for item in [*(spec.get("questions") or ()), *(spec.get("batteries") or ())]:
        for text in _texts(item.get("research_questions")):
            seen.setdefault(text, None)
    return list(seen)


def _of_run(run: FinishedRun) -> list[dict[str, Any]]:
    """One run's candidates, in the order a researcher reads its results: the analysis
    modules (research questions first), each question, each set's map, its objects and their
    relations."""
    spec = run.specification
    found: list[dict[str, Any]] = []

    def add(kind: TargetKind, words: str, ref: dict[str, Any], rqs: Sequence[str]) -> None:
        try:
            checked = _REF.validate_python({"kind": kind.value, **ref})
        except ValidationError:
            return  # an id the target contract cannot name: nothing to offer
        found.append(
            {
                "kind": kind.value,
                "words": _words(words),
                "run_id": run.run_id,
                "connections": {"research_questions": list(rqs)},
                "ref": _REF.dump_python(checked, mode="json"),
            }
        )

    every_rq = _all_research_questions(spec)
    order = {m: i for i, m in enumerate(MODULE_WORDS)}
    completed = sorted(
        (m for m in run.modules if m.outcome == "COMPLETED"),
        key=lambda m: (m.module_id is not AnalysisModuleId.RESEARCH_QUESTIONS, order[m.module_id]),
    )
    for module in completed:
        add(
            TargetKind.ANALYSIS_MODULE,
            f"Analýza: {MODULE_WORDS[module.module_id]}",
            {
                "research_run_id": run.run_id,
                "analysis_artifact_id": module.artifact_id,
                "module_id": module.module_id.value,
            },
            every_rq if module.module_id is AnalysisModuleId.RESEARCH_QUESTIONS else (),
        )
    if run.aggregate_artifact_id is not None:
        for question in spec.get("questions") or ():
            add(
                TargetKind.RESULT_QUESTION,
                f"Výsledek otázky: {question.get('text', '')}",
                {
                    "research_run_id": run.run_id,
                    "aggregate_artifact_id": run.aggregate_artifact_id,
                    "question_id": str(question.get("id", "")),
                },
                _texts(question.get("research_questions")),
            )
    batteries = list(spec.get("batteries") or ())
    if run.sociomap_artifact_id is not None:
        for battery in batteries:
            add(
                TargetKind.SOCIOMAP,
                f"Sociomapa sady: {battery.get('title', '')}",
                {
                    "research_run_id": run.run_id,
                    "sociomap_artifact_id": run.sociomap_artifact_id,
                    "battery_id": str(battery.get("id", "")),
                },
                _texts(battery.get("research_questions")),
            )
    for battery in batteries:
        rqs = _texts(battery.get("research_questions"))
        objects = [o for o in battery.get("objects") or () if isinstance(o, Mapping)]
        if run.aggregate_artifact_id is not None:
            for obj in objects:
                add(
                    TargetKind.RESULT_BATTERY_OBJECT,
                    f"Hodnocení: {obj.get('label', '')} ({battery.get('title', '')})",
                    {
                        "research_run_id": run.run_id,
                        "aggregate_artifact_id": run.aggregate_artifact_id,
                        "battery_id": str(battery.get("id", "")),
                        "object_id": str(obj.get("id", "")),
                    },
                    rqs,
                )
        if run.sociomap_artifact_id is not None:
            for obj in objects:
                add(
                    TargetKind.SOCIOMAP_OBJECT,
                    f"Na mapě: {obj.get('label', '')} ({battery.get('title', '')})",
                    {
                        "research_run_id": run.run_id,
                        "sociomap_artifact_id": run.sociomap_artifact_id,
                        "battery_id": str(battery.get("id", "")),
                        "object_id": str(obj.get("id", "")),
                    },
                    rqs,
                )
    if run.sociomap_artifact_id is None:
        return found
    # Relations last: a set of n objects has n(n-1)/2 of them, and the bound cuts these first.
    for battery in batteries:
        rqs = _texts(battery.get("research_questions"))
        objects = [o for o in battery.get("objects") or () if isinstance(o, Mapping)]
        for a, b in combinations(objects, 2):
            add(
                TargetKind.SOCIOMAP_RELATIONSHIP,
                f"Vztah na mapě: {a.get('label', '')} a {b.get('label', '')}",
                {
                    "research_run_id": run.run_id,
                    "sociomap_artifact_id": run.sociomap_artifact_id,
                    "battery_id": str(battery.get("id", "")),
                    "source_object_id": str(a.get("id", "")),
                    "target_object_id": str(b.get("id", "")),
                },
                rqs,
            )
    return found


def _bytes(value: Any) -> int:
    return len(canonical_json(value).encode("utf-8"))


def interpretation_candidates(
    runs: Sequence[FinishedRun], *, limit: int = TARGETS_MAX, max_bytes: int = TARGETS_MAX_BYTES
) -> tuple[list[dict[str, Any]], int]:
    """The candidates over ``runs`` (newest first, at most :data:`RUNS_FOR_TARGETS`), each
    with its turn-local id, within ``limit`` and ``max_bytes``, and how many were left out.
    The ids are given after the bound, so ``t1`` … ``tn`` are always the ones shown."""
    every = [c for run in list(runs)[:RUNS_FOR_TARGETS] for c in _of_run(run)]
    kept: list[dict[str, Any]] = []
    for candidate in every[:limit]:
        numbered = {"id": f"t{len(kept) + 1}", **candidate}
        if _bytes([*kept, numbered]) > max_bytes:
            break
        kept.append(numbered)
    return kept, len(every) - len(kept)


def targets_layer(runs: Sequence[FinishedRun], *, unreadable: Sequence[str] = ()) -> dict[str, Any]:
    """The turn's ``targets`` layer: the candidates, which is the default, and what was left
    out. ``default`` is ``t1`` only when it is a completed research-questions module.
    ``unreadable``: completed runs whose specification did not read, named, offering nothing."""
    candidates, omitted = interpretation_candidates(runs)
    first = candidates[0] if candidates else None
    default = (
        first["id"]
        if first is not None
        and first["kind"] == TargetKind.ANALYSIS_MODULE.value
        and first["ref"]["module_id"] == AnalysisModuleId.RESEARCH_QUESTIONS.value
        else None
    )
    out: dict[str, Any] = {"candidates": candidates, "default": default, "omitted": omitted}
    if unreadable:
        out["unreadable_runs"] = list(unreadable)
    return out


def _target_words(target: Any, candidates: Sequence[Mapping[str, Any]]) -> str:
    """A run's target in words: a design is the whole design; a result the words of the
    candidate with the same ref, else its kind (a result no longer offered)."""
    if not isinstance(target, Mapping):
        return "neuvedeno"
    if target.get("kind") == TargetKind.DESIGN_REVISION.value:
        return "návrh výzkumu"
    for candidate in candidates:
        if candidate.get("ref") == dict(target):
            return str(candidate["words"])
    return str(target.get("kind", "neuvedeno"))


def _park(steps: Sequence[Mapping[str, Any]]) -> str | None:
    """Why the run stands, by code: a waiting step's reason, else the last failed attempt's."""
    for step in steps:
        if step.get("waiting_reason"):
            return str(step["waiting_reason"])
    for step in reversed(steps):
        attempts = step.get("attempts") or []
        error = (attempts[-1].get("error") or {}) if attempts else {}
        if error.get("reason"):
            return str(error["reason"])
    return None


def deep_research_layer(
    runs: Sequence[Mapping[str, Any]], candidates: Sequence[Mapping[str, Any]] = ()
) -> dict[str, Any]:
    """The turn's ``deep_research`` layer: the study's newest Deep Research runs as
    ``DeepResearchRuns.get`` reads them (steps and attempts), each by its id, purpose, target
    in words, preset, phase, status and park code, its counts, what it cost and its ceiling.
    An unknown cost or ceiling is ``None``, never 0. Bounded in runs and bytes; the rest are
    counted."""
    kept: list[dict[str, Any]] = []
    for run in list(runs)[:DEEP_RESEARCH_RUNS]:
        meta = run.get("metadata") or {}
        steps = list(run.get("steps") or [])
        attempts = [a for s in steps for a in s.get("attempts") or []]
        costs = [a.get("actual_cost_usd") for a in attempts]
        status = run.get("status")
        phase = run.get("phase")
        entry = {
            "run_id": run["run_id"],
            "purpose": meta.get("purpose"),
            "target": _target_words(meta.get("target"), candidates),
            "preset": meta.get("preset"),
            "status": getattr(status, "value", status),
            "phase": getattr(phase, "value", phase),
            "park": _park(steps),
            "retryable": bool(run.get("retryable", False)),
            "subjects": meta.get("subjects"),
            "steps_done": sum(
                1
                for s in steps
                if getattr(s.get("status"), "value", s.get("status")) == "SUCCEEDED"
            ),
            "steps": len(steps),
            "actual_cost_usd": round(sum(float(c) for c in costs if c is not None), 6)
            if any(c is not None for c in costs)
            else None,
            "cost_ceiling_usd": meta.get("cost_ceiling_usd"),
        }
        if _bytes([*kept, entry]) > DEEP_RESEARCH_MAX_BYTES:
            break
        kept.append(entry)
    return {"runs": kept, "omitted": len(runs) - len(kept)}
