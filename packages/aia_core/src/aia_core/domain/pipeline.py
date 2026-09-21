"""Stage pipeline, fingerprinting and impact analysis.

This is a typed port of the legacy prototype's ``project_pipeline.py``. It is the
durable contract that decides, after a project edit, which completed work may be
reused and which stages must be recomputed. Parity with the legacy implementation
is enforced by ``tests/test_pipeline_parity.py``.

Two invariants here are load-bearing and must not be "simplified":

1. Provider transport is deliberately excluded from the stage fingerprint. A user
   switching provider (Claude Code -> Claude API) must not invalidate completed
   artifacts, because mixed-provider continuation is an explicit product feature.
   Model choice is included only for the stages where it changes generated content.

2. The first changed stage invalidates itself and everything downstream. Stages
   upstream of the change are preserved so their artifacts can be reused.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any, Final

__all__ = [
    "IMPACT_ROOTS",
    "RESEARCH_STAGES",
    "SIMULATION_STAGES",
    "STAGE_EQUIVALENTS",
    "ImpactPreview",
    "ProjectType",
    "StageStatus",
    "changed_fields",
    "fingerprint",
    "impact_preview",
    "resolve_stage",
    "stage_fingerprint",
    "stage_ids",
    "stage_input_payload",
    "stage_labels",
    "stages_for",
]


class ProjectType(StrEnum):
    """The two project lifecycles the product supports."""

    RESEARCH = "research"
    SIMULATION = "simulation"

    @classmethod
    def coerce(cls, value: Any) -> ProjectType:
        """Map anything to a valid project type, defaulting to research.

        The legacy store treats only the exact string ``simulation`` as a
        simulation and everything else as research; that behaviour is preserved
        because existing rows depend on it.
        """
        return cls.SIMULATION if str(value).lower() == "simulation" else cls.RESEARCH


class StageStatus(StrEnum):
    """Durable stage states.

    ``WAITING_*`` states are not errors: they are parked states a stage can sit in
    indefinitely until credits, provider capacity or a user decision arrives. They
    exist so that an interrupted run is resumable rather than lost.
    """

    NOT_STARTED = "NOT_STARTED"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_USER = "WAITING_USER"
    WAITING_CREDITS = "WAITING_CREDITS"
    WAITING_CAPACITY = "WAITING_CAPACITY"
    DONE = "DONE"
    DONE_WITH_WARNINGS = "DONE_WITH_WARNINGS"
    INVALIDATED = "INVALIDATED"
    FAILED = "FAILED"

    @property
    def is_complete(self) -> bool:
        """True for the states whose artifacts may be carried into a new revision."""
        return self in _COMPLETE_STATUSES

    @property
    def is_waiting(self) -> bool:
        """True while a stage is parked awaiting an external condition."""
        return self in _WAITING_STATUSES


_COMPLETE_STATUSES: Final = frozenset({StageStatus.DONE, StageStatus.DONE_WITH_WARNINGS})
_WAITING_STATUSES: Final = frozenset(
    {StageStatus.WAITING_USER, StageStatus.WAITING_CREDITS, StageStatus.WAITING_CAPACITY}
)


# Stage id -> Czech display label. The label is product copy and stays with the
# domain because the stage list and its user-facing names must not drift apart.
RESEARCH_STAGES: Final[tuple[tuple[str, str], ...]] = (
    ("BRIEF", "Zadání"),
    ("DEEP_RESEARCH", "Deep Research"),
    ("RESEARCH_DESIGN", "Výzkumný design"),
    ("QUESTIONNAIRE", "Dotazník"),
    ("AUDIENCE", "Cílová skupina"),
    ("DIMENSIONS", "Dimenze"),
    ("SAMPLE_PLAN", "Výběrový plán"),
    ("FIELDWORK", "Respondenti"),
    ("AGGREGATION", "Agregace"),
    ("VALIDATION", "Validace"),
    ("ANALYSIS", "Analýza"),
    ("REPORT", "Report"),
    ("DELIVERY", "Předání"),
)

SIMULATION_STAGES: Final[tuple[tuple[str, str], ...]] = (
    ("BRIEF", "Kontext"),
    ("DEEP_RESEARCH", "Deep Research"),
    ("BASELINE", "Baseline"),
    ("SCENARIO_CONTRACT", "Kontrakt scénáře"),
    ("AUDIENCE", "Cílová skupina"),
    ("DIMENSIONS", "Dimenze"),
    ("VARIANTS", "Varianty"),
    ("WORLDS", "Simulované světy"),
    ("FROZEN_RESULTS", "Zmrazené výsledky"),
    ("COMPARISON", "Srovnání"),
    ("INTERPRETATION", "Interpretace"),
    ("REPORT", "Report"),
    ("DELIVERY", "Předání"),
)


# Project field -> the earliest stage that field affects. ``None`` means the field
# is explicitly impact-free: changing it invalidates nothing. Provider and model
# selection are impact-free by design (see module docstring, invariant 1).
IMPACT_ROOTS: Final[dict[str, str | None]] = {
    "brief": "BRIEF",
    "briefing": "BRIEF",
    "goal": "BRIEF",
    "decision_use": "BRIEF",
    "research_plan": "RESEARCH_DESIGN",
    "questionnaire": "QUESTIONNAIRE",
    "sections": "QUESTIONNAIRE",
    "tracked_objects": "QUESTIONNAIRE",
    "audience": "AUDIENCE",
    "persona_dimensions": "DIMENSIONS",
    "n": "SAMPLE_PLAN",
    "sample": "SAMPLE_PLAN",
    "panel_mode": "SAMPLE_PLAN",
    "provider": None,
    "preferred_provider": None,
    "provider_policy": None,
    "model": None,
    "analysis_instructions": "ANALYSIS",
    "analysis_style": "ANALYSIS",
    "report_style": "REPORT",
    "report_branding": "REPORT",
    "simulation_change": "SCENARIO_CONTRACT",
    "scenario": "SCENARIO_CONTRACT",
    "scenario_contract": "SCENARIO_CONTRACT",
    "variants": "VARIANTS",
}

# Presentation-only fields. A change confined to these invalidates REPORT onward
# but must never reopen fieldwork or analysis.
PRESENTATION_ONLY_FIELDS: Final[frozenset[str]] = frozenset({"report_style", "report_branding"})


# A research-only stage id must never be written to a simulation project or the
# reverse. Each stage maps to its nearest counterpart in the other pipeline so a
# mis-routed job degrades to the right stage instead of dying on a lookup error.
STAGE_EQUIVALENTS: Final[dict[str, str]] = {
    "RESEARCH_DESIGN": "SCENARIO_CONTRACT",
    "QUESTIONNAIRE": "SCENARIO_CONTRACT",
    "SAMPLE_PLAN": "VARIANTS",
    "FIELDWORK": "WORLDS",
    "AGGREGATION": "FROZEN_RESULTS",
    "VALIDATION": "COMPARISON",
    "ANALYSIS": "INTERPRETATION",
    "SCENARIO_CONTRACT": "RESEARCH_DESIGN",
    "BASELINE": "RESEARCH_DESIGN",
    "VARIANTS": "SAMPLE_PLAN",
    "WORLDS": "FIELDWORK",
    "FROZEN_RESULTS": "AGGREGATION",
    "COMPARISON": "VALIDATION",
    "INTERPRETATION": "ANALYSIS",
}


def stages_for(project_type: Any) -> tuple[tuple[str, str], ...]:
    """Return the ordered ``(stage_id, label)`` pipeline for a project type."""
    return (
        SIMULATION_STAGES
        if ProjectType.coerce(project_type) is ProjectType.SIMULATION
        else RESEARCH_STAGES
    )


def stage_ids(project_type: Any) -> list[str]:
    """Return the ordered stage ids for a project type."""
    return [sid for sid, _ in stages_for(project_type)]


def stage_labels(project_type: Any) -> dict[str, str]:
    """Return ``{stage_id: display_label}`` for a project type."""
    return dict(stages_for(project_type))


def resolve_stage(project_type: Any, stage_id: str | None, *, default: str | None = None) -> str:
    """Return a stage id that provably exists in this project type's pipeline.

    Resolution order: the requested stage, its cross-pipeline equivalent, the
    caller's default, that default's equivalent, then the first stage. It never
    raises, because a mis-mapped stage is a routing detail and must not destroy a
    queued job.
    """
    ids = stage_ids(project_type)

    for candidate in (stage_id, default):
        sid = str(candidate or "").strip().upper()
        if sid in ids:
            return sid
        alt = STAGE_EQUIVALENTS.get(sid)
        if alt in ids:
            return alt

    return ids[0]


def fingerprint(value: Any) -> str:
    """Return a stable SHA256 over any JSON-serialisable value.

    Key order is normalised so that two logically equal payloads fingerprint
    identically regardless of dict construction order. Non-serialisable values
    fall back to ``str`` rather than raising, matching the legacy contract.
    """
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _research_stage_inputs(p: dict[str, Any]) -> dict[str, dict[str, Any]]:
    plan = p.get("research_plan") or {}
    return {
        "BRIEF": {
            "title": p.get("title"),
            "goal": p.get("goal"),
            "decision_use": p.get("decision_use"),
            "briefing": p.get("briefing"),
            "study_type": p.get("study_type"),
        },
        "DEEP_RESEARCH": {
            "goal": p.get("goal"),
            "decision_use": p.get("decision_use"),
            "briefing": p.get("briefing"),
            "research_questions": plan.get("research_questions"),
            "attachment_refs": p.get("attachment_refs"),
            "data_context": p.get("data_context"),
        },
        "RESEARCH_DESIGN": {
            "goal": p.get("goal"),
            "decision_use": p.get("decision_use"),
            "study_type": p.get("study_type"),
            "research_plan": p.get("research_plan"),
            "tracked_objects": p.get("tracked_objects"),
        },
        "QUESTIONNAIRE": {
            "sections": p.get("sections"),
            "instrument_library": p.get("instrument_library"),
            "tracked_objects": p.get("tracked_objects"),
            "questionnaire_policy": p.get("questionnaire_policy"),
        },
        "AUDIENCE": {"audience": p.get("audience")},
        "DIMENSIONS": {
            "persona_mode": p.get("persona_mode"),
            "persona_dimensions": p.get("persona_dimensions"),
        },
        "SAMPLE_PLAN": {
            "n": p.get("n"),
            "panel_mode": p.get("panel_mode"),
            "audience": p.get("audience"),
            "persona_mode": p.get("persona_mode"),
            "persona_dimensions": p.get("persona_dimensions"),
        },
        "FIELDWORK": {
            "sections": p.get("sections"),
            "audience": p.get("audience"),
            "persona_mode": p.get("persona_mode"),
            "persona_dimensions": p.get("persona_dimensions"),
            "n": p.get("n"),
            "model": p.get("model"),
            "population_snapshot": p.get("population_snapshot"),
        },
        "AGGREGATION": {
            "aggregation_policy": p.get("aggregation_policy"),
            "weighting": p.get("weighting"),
        },
        "VALIDATION": {
            "validation_policy": p.get("validation_policy"),
            "benchmarks": p.get("benchmarks"),
        },
        "ANALYSIS": {
            "analysis_instructions": p.get("analysis_instructions"),
            "analysis_style": p.get("analysis_style"),
            "research_questions": plan.get("research_questions"),
            "model": p.get("model"),
        },
        "REPORT": {
            "report_style": p.get("report_style"),
            "report_branding": p.get("report_branding"),
            "language": p.get("report_language"),
        },
        "DELIVERY": {
            "delivery": p.get("delivery"),
            "report_style": p.get("report_style"),
            "report_branding": p.get("report_branding"),
        },
    }


def _simulation_stage_inputs(p: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sim = p.get("simulation") or p
    contract = p.get("scenario_contract") or sim.get("scenario_contract")
    variants = sim.get("variants") or p.get("variants")
    return {
        "BRIEF": {
            "title": p.get("title"),
            "goal": p.get("goal"),
            "context": sim.get("context") or sim.get("brief"),
        },
        "DEEP_RESEARCH": {
            "brief": sim.get("context") or sim.get("brief"),
            "attachments": p.get("attachment_refs"),
            "data_context": p.get("data_context"),
        },
        "BASELINE": {
            "baseline": sim.get("baseline"),
            "audience": sim.get("audience"),
            "dimensions": sim.get("dimensions"),
            "population": sim.get("population_snapshot"),
        },
        "SCENARIO_CONTRACT": {
            "scenario_contract": contract,
            "change": sim.get("change") or sim.get("scenario"),
        },
        "AUDIENCE": {"audience": sim.get("audience") or p.get("audience")},
        "DIMENSIONS": {"dimensions": sim.get("dimensions") or p.get("persona_dimensions")},
        "VARIANTS": {"variants": variants, "scenario_contract": contract},
        "WORLDS": {
            "variants": variants,
            "worlds": sim.get("worlds"),
            "n": sim.get("n"),
            "model": sim.get("model") or p.get("model"),
            "population": sim.get("population_snapshot"),
        },
        "FROZEN_RESULTS": {"variants": variants, "worlds": sim.get("worlds")},
        "COMPARISON": {"variants": variants, "comparison_policy": sim.get("comparison_policy")},
        "INTERPRETATION": {
            "analysis_instructions": p.get("analysis_instructions")
            or sim.get("analysis_instructions"),
            "model": sim.get("model") or p.get("model"),
        },
        "REPORT": {
            "report_style": p.get("report_style") or sim.get("report_style"),
            "report_branding": p.get("report_branding") or sim.get("report_branding"),
        },
        "DELIVERY": {
            "delivery": p.get("delivery") or sim.get("delivery"),
            "report_style": p.get("report_style") or sim.get("report_style"),
        },
    }


def stage_input_payload(
    project: dict[str, Any], stage_id: str, project_type: Any = ProjectType.RESEARCH
) -> dict[str, Any]:
    """Return only the inputs that materially affect one logical stage.

    This payload *is* the durable fingerprint contract: two projects whose stage
    payloads match may reuse each other's artifacts for that stage. Adding a field
    here invalidates every previously stored artifact for that stage, so treat
    changes as a migration, not a tweak.

    An unknown stage id falls back to the whole project (simulation: the whole
    simulation sub-object), which fingerprints as "everything matters" and is the
    safe, non-reusing default.
    """
    p = project or {}
    sid = str(stage_id or "").upper()
    ptype = ProjectType.coerce(project_type)

    if ptype is ProjectType.SIMULATION:
        mapping = _simulation_stage_inputs(p)
        default: Any = p.get("simulation") or p
    else:
        mapping = _research_stage_inputs(p)
        default = p

    return {"stage": sid, "inputs": mapping.get(sid, default)}


def stage_fingerprint(
    project: dict[str, Any], stage_id: str, project_type: Any = ProjectType.RESEARCH
) -> str:
    """Return the SHA256 fingerprint of a stage's material inputs."""
    return fingerprint(stage_input_payload(project, stage_id, project_type))


def changed_fields(old: dict[str, Any] | None, new: dict[str, Any]) -> list[str]:
    """Return the sorted top-level project keys whose content changed.

    Comparison is by fingerprint rather than ``==`` so that nested structures
    compare by value and unorderable types never raise.
    """
    if not isinstance(old, dict):
        return []
    keys = set(old) | set(new or {})
    return [k for k in sorted(keys) if fingerprint(old.get(k)) != fingerprint((new or {}).get(k))]


class ImpactPreview:
    """Which stages a set of project edits invalidates, and which survive.

    ``preserve`` is ordered upstream-first and ``invalidate`` downstream-first,
    matching pipeline order. ``root_stage`` is the earliest affected stage, or
    ``None`` when nothing material changed.
    """

    __slots__ = ("invalidate", "presentation_only", "preserve", "root_stage")

    def __init__(
        self,
        *,
        root_stage: str | None,
        invalidate: list[str],
        preserve: list[str],
        presentation_only: bool,
    ) -> None:
        self.root_stage = root_stage
        self.invalidate = invalidate
        self.preserve = preserve
        self.presentation_only = presentation_only

    def as_dict(self) -> dict[str, Any]:
        """Return the legacy-compatible dict shape."""
        return {
            "root_stage": self.root_stage,
            "invalidate": list(self.invalidate),
            "preserve": list(self.preserve),
            "presentation_only": self.presentation_only,
        }

    def __repr__(self) -> str:
        return (
            f"ImpactPreview(root_stage={self.root_stage!r}, "
            f"invalidate={self.invalidate!r}, presentation_only={self.presentation_only!r})"
        )


def impact_preview(
    project_type: Any,
    changed: list[str] | None = None,
    explicit_stage: str | None = None,
) -> ImpactPreview:
    """Compute which stages survive an edit and which must be recomputed.

    ``explicit_stage`` forces a specific stage to be the root, for a user asking to
    rerun from there. Otherwise the root is the earliest stage reachable from any
    changed field; fields mapped to ``None`` in :data:`IMPACT_ROOTS` contribute no
    root, so a provider or model switch preserves the whole pipeline.

    With no root, every stage is preserved and nothing is invalidated.
    """
    ids = stage_ids(project_type)
    root = explicit_stage if explicit_stage in ids else None
    presentation_only = False

    if not root:
        roots: list[str] = []
        for field in changed or []:
            mapped = IMPACT_ROOTS.get(str(field))
            if mapped:
                # DEVIATION from legacy project_pipeline.impact_preview: a field whose
                # root belongs to the *other* pipeline (e.g. `scenario` ->
                # SCENARIO_CONTRACT on a research project) made the legacy
                # implementation raise ValueError from `ids.index(root)`, which
                # propagated out of the project save path. We map such a root through
                # STAGE_EQUIVALENTS -- the mechanism this codebase already uses for
                # cross-pipeline routing -- and drop it if it still does not resolve.
                # Covered by tests/test_pipeline_parity.py::test_cross_pipeline_*.
                if mapped not in ids:
                    mapped = STAGE_EQUIVALENTS.get(mapped)
                if mapped in ids:
                    roots.append(mapped)
            if field in PRESENTATION_ONLY_FIELDS:
                presentation_only = True
        if roots:
            root = min(roots, key=ids.index)

    if not root:
        return ImpactPreview(
            root_stage=None, invalidate=[], preserve=list(ids), presentation_only=False
        )

    pos = ids.index(root)
    return ImpactPreview(
        root_stage=root,
        invalidate=ids[pos:],
        preserve=ids[:pos],
        presentation_only=presentation_only,
    )
