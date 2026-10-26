"""The Lead's per-artifact contract: one row per workbench stage (research-lead-workbench 14-16).

Each of the eleven artifacts plugs into the Research Lead the same way, and this row says how:

* ``artifact``: what the stage shows -- the study's working copy, a frozen run's artifact, or
  the report's unapproved draft;
* ``edits``: whether the Lead's proposed edits (``research_lead.EditOp``) land on this stage;
* ``view_ops``: the closed set of display operations the Lead may run on it (chunk 14). Only
  ``open_stage``, ``focus`` and ``inspect`` are in
  :class:`~aia_core.domain.research_lead.LeadOutput` today; the others are the contract a screen
  builds to, and join the Lead's output with it;
* ``targets``: the kinds of element the Lead can name there (chunk 16), each a ``data-aia``
  id ``<kind>:<id>`` the screen puts on the element;
* ``starts``: the workers and requests its cards start (an ``agent_job:<action>`` or a
  :data:`~aia_core.domain.research_lead.JobRequest` kind);
* ``inputs`` and ``hands_off``: the stages it is made from, and what it passes on, in what form
  (``artifact-chain-to-draft-report``);
* ``report_sections``: the internal report's sections it feeds (:data:`REPORT_SECTIONS`).

The fixture the rows are held to is ``tests/fixtures/lead_artifacts/contract.json``; the web's
``lib/workbench-artifacts.ts`` is held to the same file. Pure.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .research_agents import ResearchAction
from .research_lead import STAGES, Stage

__all__ = [
    "ARTIFACTS",
    "FIELDS",
    "FILTER_VALUES",
    "LIVE_TARGETS",
    "LIVE_VIEW_OPS",
    "REPORT_SECTIONS",
    "ArtifactContract",
    "ArtifactKind",
    "HandOff",
    "ReportSection",
    "SectionState",
    "TargetKind",
    "ViewOpKind",
    "allows_view",
    "contract_for",
    "stage_of",
]

FIELDS: Final = (
    "stage",
    "artifact",
    "edits",
    "view_ops",
    "targets",
    "starts",
    "inputs",
    "hands_off",
    "report_sections",
    "refusals",
)


class ArtifactKind(StrEnum):
    WORKING = "working"
    RUN = "run"
    DRAFT = "draft"


class ViewOpKind(StrEnum):
    OPEN_STAGE = "open_stage"
    FOCUS = "focus"
    INSPECT = "inspect"
    SELECT = "select"
    FILTER = "filter"
    SHOW_DIFF = "show_diff"


#: The view operations the Lead's output carries today (``research_lead.ViewOp``).
LIVE_VIEW_OPS: Final = frozenset(
    {
        ViewOpKind.OPEN_STAGE,
        ViewOpKind.FOCUS,
        ViewOpKind.INSPECT,
        ViewOpKind.SHOW_DIFF,
        ViewOpKind.SELECT,
        ViewOpKind.FILTER,
    }
)

#: The display filters a stage's ``filter`` names, and each one's values: a filter changes the
#: picture, never a computation (artifact-sociomap SOC1, the web's ``FILTER_VALUES``). ``None``:
#: the run's own values (a battery id), which only the run's map knows.
FILTER_VALUES: Final[Mapping[str, Mapping[str, tuple[str, ...] | None]]] = {
    "sociomap": {
        "view": ("top", "relief"),
        "labels": ("on", "off"),
        "hide_weak": ("on", "off"),
        "mode": ("objects", "respondents"),
        "battery": None,
    },
}


class TargetKind(StrEnum):
    BRIEF = "brief"
    OBJECTIVE = "objective"
    MATERIAL = "material"
    PLAN = "plan"
    RQ = "rq"
    HYPOTHESIS = "hypothesis"
    SET = "set"
    ASSUMPTION = "assumption"
    SECTION = "section"
    QUESTION = "question"
    AUDIENCE = "audience"
    DIMENSION = "dimension"
    OWN_DIMENSION = "own_dimension"
    SAMPLE = "sample"
    STEP = "step"
    RECEIPT = "receipt"
    MEASURE = "measure"
    OBJECT = "object"
    PAIR = "pair"
    MODULE = "module"
    FINDING = "finding"
    CLAIM = "claim"
    REPORT = "report"


#: The target kinds a person's message may name and the Lead may focus: every kind, since the
#: server's FOCUS_ID takes each (research-lead-workbench 16).
LIVE_TARGETS: Final = frozenset(TargetKind)

#: What a card may start: a design worker, one of the Lead's prepared requests, or a finished
#: run's failed analysis modules asked again (``POST …/analysis/retry``).
_REQUESTS: Final = frozenset(
    {"research_run", "design_research", "interpretation_research", "analysis_retry"}
)
_STARTS: Final = frozenset({f"agent_job:{a.value}" for a in ResearchAction}) | _REQUESTS


class ReportSection(StrEnum):
    """The internal report's sections, by the id the composer gives each ``Section`` (``intro``,
    ``ch-1`` … ``ch-8`` by the analysis module's ordinal, ``ch-native-map-<n>`` per battery)."""

    INTRODUCTION = "intro"
    DESIGN = "ch-design"
    EXECUTIVE = "ch-1"
    RESEARCH_QUESTIONS = "ch-2"
    LITERATURE = "literature"
    METHODOLOGY = "methodology"
    RESPONDENTS = "ch-method"
    QUESTION_TABLES = "ch-questions"
    AUDIENCE = "ch-4"
    OBJECTS = "ch-3"
    MAPS = "ch-native-map"
    SEGMENTS = "ch-5"
    HYPOTHESES = "ch-6"
    IMPLICATIONS = "ch-7"
    LIMITATIONS = "ch-8"
    QUESTIONNAIRE_APPENDIX = "app-questionnaire"
    EVIDENCE_APPENDIX = "app-evidence"
    AUDIT = "app-audit"


class SectionState(StrEnum):
    """Where a section's content comes from today: its named source, fixed text, or nowhere."""

    FILLED = "filled"
    FIXED_TEXT = "fixed_text"
    MISSING = "missing"


#: Each section's state today (``artifact-chain-to-draft-report`` closes the rest).
REPORT_SECTIONS: Final[dict[ReportSection, SectionState]] = {
    **dict.fromkeys(ReportSection, SectionState.FILLED),
    ReportSection.LITERATURE: SectionState.MISSING,
    ReportSection.METHODOLOGY: SectionState.FIXED_TEXT,
}


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class HandOff(_Closed):
    to: Stage | None
    form: str = Field(min_length=1)


class ArtifactContract(_Closed):
    stage: Stage
    artifact: ArtifactKind
    edits: bool
    view_ops: tuple[ViewOpKind, ...] = Field(min_length=1)
    targets: tuple[TargetKind, ...]
    starts: tuple[str, ...]
    inputs: tuple[Stage, ...]
    hands_off: tuple[HandOff, ...] = Field(min_length=1)
    report_sections: tuple[ReportSection, ...]
    refusals: tuple[str, ...]

    @model_validator(mode="after")
    def _consistent(self) -> ArtifactContract:
        if self.view_ops[:2] != (ViewOpKind.OPEN_STAGE, ViewOpKind.FOCUS):
            raise ValueError(f"{self.stage}: every artifact opens and focuses first")
        if len(set(self.view_ops)) != len(self.view_ops):
            raise ValueError(f"{self.stage}: a view operation listed twice")
        if not self.targets:
            raise ValueError(f"{self.stage}: focus needs a target kind")
        if unknown := sorted(set(self.starts) - _STARTS):
            raise ValueError(f"{self.stage}: unknown starts {unknown}")
        if self.edits and self.artifact is not ArtifactKind.WORKING:
            raise ValueError(f"{self.stage}: edits land only on the working copy")
        if self.stage in self.inputs:
            raise ValueError(f"{self.stage}: an artifact is not its own input")
        return self

    def fixture_row(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _row(
    stage: Stage,
    artifact: Literal["working", "run", "draft"],
    *,
    edits: bool,
    view_ops: tuple[str, ...],
    targets: tuple[str, ...],
    starts: tuple[str, ...],
    inputs: tuple[Stage, ...],
    hands_off: tuple[tuple[Stage | None, str], ...],
    report_sections: tuple[str, ...],
    refusals: tuple[str, ...],
) -> ArtifactContract:
    return ArtifactContract.model_validate(
        {
            "stage": stage,
            "artifact": artifact,
            "edits": edits,
            "view_ops": ("open_stage", "focus", *view_ops),
            "targets": targets,
            "starts": starts,
            "inputs": inputs,
            "hands_off": [{"to": to, "form": form} for to, form in hands_off],
            "report_sections": report_sections,
            "refusals": refusals,
        }
    )


_MEMORY: Final = "agent_job:answer_memory"

ARTIFACTS: Final[dict[str, ArtifactContract]] = {
    c.stage: c
    for c in (
        _row(
            "brief",
            "working",
            edits=True,
            view_ops=(),
            targets=("brief", "objective", "material"),
            starts=("agent_job:analyze_brief", _MEMORY),
            inputs=(),
            hands_off=(("design", "working content `briefing`, read by analyze_brief"),),
            report_sections=("intro",),
            refusals=("důvěrný podklad nelze poslat do veřejného vyhledávání",),
        ),
        _row(
            "design",
            "working",
            edits=True,
            view_ops=("inspect", "show_diff"),
            targets=("plan", "rq", "hypothesis", "set", "assumption"),
            starts=(
                "agent_job:analyze_brief",
                "agent_job:critique_design",
                "agent_job:design_copilot",
                _MEMORY,
                "design_research",
            ),
            inputs=("brief",),
            hands_off=(
                (
                    "questionnaire",
                    "research_plan.research_questions, linked by items' research_questions",
                ),
                ("analysis", "ResearchSpecification research questions (compile_design)"),
            ),
            report_sections=("intro", "ch-design", "ch-6"),
            refusals=("metodickou volbu neuzavírá AI",),
        ),
        _row(
            "questionnaire",
            "working",
            edits=True,
            view_ops=("show_diff",),
            targets=("section", "question"),
            starts=(
                "agent_job:build_questionnaire",
                "agent_job:optimize_questionnaire",
                _MEMORY,
                "design_research",
            ),
            inputs=("design",),
            hands_off=(
                (
                    "fieldwork",
                    "ResearchSpecification questions and batteries (compile_design)",
                ),
            ),
            report_sections=("ch-design", "ch-questions", "app-questionnaire"),
            refusals=("přijetí návrhu jen člověk (APPROVE_GATE)",),
        ),
        _row(
            "audience",
            "working",
            edits=False,
            view_ops=(),
            targets=("audience",),
            starts=("agent_job:propose_audience", _MEMORY),
            inputs=("design",),
            hands_off=(("sample", "ResearchSpecification audience and SpecSelection filters"),),
            report_sections=("ch-design", "ch-4"),
            refusals=("náhled vrací jen počty, žádné řádky",),
        ),
        _row(
            "dimensions",
            "working",
            edits=True,
            view_ops=("show_diff",),
            targets=("dimension", "own_dimension"),
            starts=("agent_job:suggest_dimensions", _MEMORY),
            inputs=("design", "audience"),
            hands_off=(("fieldwork", "SpecSelection dimensions (persona_dimensions.approved)"),),
            report_sections=("ch-design", "ch-5"),
            refusals=("pole použije jen to, co dovolí politika pole (decide)",),
        ),
        _row(
            "sample",
            "working",
            edits=True,
            view_ops=("show_diff", "inspect"),
            targets=("sample",),
            starts=(_MEMORY,),
            inputs=("audience", "dimensions"),
            hands_off=(("fieldwork", "ResearchSpecification n"),),
            report_sections=("ch-design", "ch-method"),
            refusals=("kvóta nezaručuje podporu dvojic",),
        ),
        _row(
            "fieldwork",
            "run",
            edits=False,
            view_ops=("inspect",),
            targets=("step", "receipt"),
            starts=("research_run",),
            inputs=("questionnaire", "audience", "dimensions", "sample"),
            hands_off=(
                ("results", "research_fieldwork_dataset -> research_aggregate"),
                ("sociomap", "research_fieldwork_dataset -> research_sociomap"),
                ("analysis", "research_fieldwork_dataset as admitted evidence"),
            ),
            report_sections=("ch-method", "app-audit"),
            refusals=("nad limit potvrzení jen člověk",),
        ),
        _row(
            "results",
            "run",
            edits=False,
            view_ops=("inspect",),
            targets=("measure",),
            starts=(_MEMORY,),
            inputs=("fieldwork",),
            hands_off=(("analysis", "research_aggregate"),),
            report_sections=("ch-questions",),
            refusals=("potlačené číslo se neukáže ani AI",),
        ),
        _row(
            "sociomap",
            "run",
            edits=False,
            view_ops=("select", "filter", "inspect"),
            targets=("object", "pair"),
            starts=("interpretation_research",),
            inputs=("fieldwork",),
            hands_off=(("report", "research_sociomap contract-3 maps (verified_map)"),),
            report_sections=("ch-native-map",),
            refusals=("filtr zobrazení nemění výpočet", "externí kontext do výpočtu nevstupuje"),
        ),
        _row(
            "analysis",
            "run",
            edits=False,
            view_ops=("inspect",),
            targets=("module", "finding", "claim"),
            starts=("analysis_retry", "interpretation_research"),
            inputs=("fieldwork", "results", "sociomap"),
            hands_off=(("report", "eight research_analysis modules (RunAnalysis)"),),
            report_sections=(
                "ch-1",
                "ch-2",
                "ch-4",
                "ch-3",
                "ch-5",
                "ch-6",
                "ch-7",
                "ch-8",
                "app-evidence",
            ),
            refusals=("číslo jen jako AdmittedClaim", "AI neschvaluje vlastní tvrzení"),
        ),
        _row(
            "report",
            "draft",
            edits=False,
            view_ops=("show_diff",),
            targets=("report",),
            starts=("interpretation_research",),
            inputs=("design", "questionnaire", "sociomap", "analysis"),
            hands_off=(
                (None, "research_internal_docx, DRAFT_UNAPPROVED; approved only by a person"),
            ),
            report_sections=("literature",),
            refusals=("schválení jen člověk",),
        ),
    )
}

if tuple(ARTIFACTS) != STAGES:  # pragma: no cover - a registration error, caught at import
    raise RuntimeError("ARTIFACTS must hold one row per stage, in STAGES order")


def contract_for(stage: str) -> ArtifactContract:
    """The stage's row; an unknown stage is a KeyError, never a default row."""
    return ARTIFACTS[stage]


def allows_view(stage: str, op: str) -> bool:
    """Whether the Lead may run the display operation ``op`` on ``stage``'s artifact."""
    row = ARTIFACTS.get(stage)
    return row is not None and op in {v.value for v in row.view_ops}


def stage_of(kind: str) -> str | None:
    """The stage whose screen shows elements of ``kind`` (the row naming it in ``targets``), or
    None for a kind no row names."""
    for stage, row in ARTIFACTS.items():
        if kind in {t.value for t in row.targets}:
            return stage
    return None
