"""Research execution under the Study: Design Revisions, and the runs that execute them.

ADR 0016. Every route resolves the Study through ``ScopeResolver`` first
(``StudyScopeDep``): a Study outside the caller's scope is a 404, and so is a
revision or run that is not the Study's own. Inside a Study the caller can see,
a missing permission is a 403. No route takes a client, organization or unit
project id: the browser supplies content, never authority.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import date, datetime
from typing import Annotated, Any, Final, Literal

from aia_core.application.analysis_results import (
    AnalysisNotRetryable,
    ReconstructionRefused,
    reconstruct_run,
    retry_failed_modules,
    stored_analysis,
)
from aia_core.application.audience_preview import PanelDraw, PanelSampler
from aia_core.application.client_report import (
    CLIENT_REPORT_DOCUMENT_ARTIFACT_TYPE,
    ClientGateRefused,
    ClientReportRefused,
    client_report_document,
    prepare_client_report,
    stored_client_report,
)
from aia_core.application.contextual_report import (
    contextual_report_document,
    stored_contextual_report,
)
from aia_core.application.deep_research import (
    BundleNotReady,
    DeepResearchRunNotFound,
    LineageChanged,
    RunNotGoverned,
    RunSpecCorrupt,
)
from aia_core.application.errors import WorkspaceConflict
from aia_core.application.lead_chat_start import RunStartSettings
from aia_core.application.proposal_accept import StaleProposal
from aia_core.application.report import (
    INTERNAL_REPORT_ARTIFACT_TYPE,
    INTERNAL_REPORT_DOCUMENT_ARTIFACT_TYPE,
    INTERNAL_REPORT_MEDIA_TYPE,
    ReportCompositionRefused,
)
from aia_core.application.report_approval import (
    CLIENT_REPORT_KINDS,
    REPORT_KINDS,
    ReportNotApprovable,
    approve_report,
)
from aia_core.application.report_export import (
    Export,
    ReviewUnrecorded,
    export_docx,
    exports_stamped,
    review_mark,
    stampable,
)
from aia_core.application.report_method import research_question_gap, research_question_gaps
from aia_core.application.report_variants import (
    PdfState,
    VariantState,
    VariantStatus,
    approval_renders_pdf,
    prepared_context_report,
    request_pdf,
    step_pdf,
    variant_pdf,
    variant_status,
)
from aia_core.application.research import (
    BudgetNotRaised,
    CostCeilingUnknown,
    CostConfirmationRequired,
    DesignNotReady,
    PanelPopulationMissing,
    ResearchAgentJobs,
    ResearchQuestionsUnanswerable,
    ResearchRunNotFound,
    ResearchRunNotRetryable,
    ResearchRunOnRetiredMethod,
    ResearchRuns,
    ResearchStepNotFound,
    RunOutlook,
    RunReservations,
    WorkingRevisionNotFound,
    readiness_in_force,
    research_artifacts,
)
from aia_core.application.sociomapping_report import SOCIOMAPPING_REPORT_ARTIFACT_TYPE
from aia_core.application.workflows import StartedRun
from aia_core.domain.analysis.steps import ANALYSIS_STEP_KIND
from aia_core.domain.answerability import (
    ANSWERABILITY_RULES,
    MAX_ACKNOWLEDGEMENT_CHARS,
    MIN_ACKNOWLEDGEMENT_CHARS,
    Acknowledgement,
    AcknowledgementRefused,
    Answerability,
    read_answerability_note,
)
from aia_core.domain.design import DesignRejected, DesignRevision
from aia_core.domain.design_reuse import DesignSource
from aia_core.domain.fieldwork import (
    DataOrigin,
    FieldworkSource,
    OriginKind,
    PersonaSource,
    origin_kind,
    persona_source_of,
)
from aia_core.domain.methodology.pins import response_deviates, run_methods
from aia_core.domain.persona_topics import dimension_topic
from aia_core.domain.population import PopulationError, UnknownDatasetVersion
from aia_core.domain.population.sampling import quota_keys
from aia_core.domain.report.document_model import (
    DOCUMENT_MODEL_MEDIA_TYPE,
    DocumentModelInvalid,
    read_document_payload,
)
from aia_core.domain.report.review import ReviewMark, ReviewState
from aia_core.domain.report.validation import ReportInvalid
from aia_core.domain.research_agents import ResearchAction
from aia_core.domain.research_design import settle_selection
from aia_core.domain.research_trace import ResearchTrace
from aia_core.domain.scope import (
    Permission,
    ScopeDenied,
    SeparationOfDutiesViolation,
    StudyContext,
)
from aia_core.domain.sociomap_register import SOCIOMAP_REGISTER
from aia_core.domain.workflow import StepRunStatus
from aia_core.infrastructure.artifact_repository import (
    Artifact,
    ArtifactNotFound,
    ArtifactRepository,
    ArtifactStatus,
)
from aia_core.infrastructure.report_pdf import PDF_MEDIA_TYPE
from aia_core.infrastructure.storage import ArtifactStore, IntegrityError, ObjectNotFound
from aia_core.infrastructure.study_design_repository import (
    DesignRevisionNotFound,
    StudyDesignRepository,
)
from aia_core.infrastructure.workflow_repository import (
    BudgetWaitNotLiftable,
    RuntimeParkNotResumable,
)
from fastapi import APIRouter, HTTPException, Path, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from ..dependencies import (
    ArtifactStoreDep,
    AudiencePopulation,
    PanelSamplerDep,
    RunPopulationDep,
    SessionDep,
    SettingsDep,
    StudyScopeDep,
)
from ..schemas.projects import ErrorResponse
from ..schemas.runs import ArtifactResponse, RunEventResponse
from .runs import artifact_corrupt, artifact_response

router = APIRouter(
    prefix="/studies/{study_id}",
    tags=["research"],
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Insufficient role, or the study is closed"},
        404: {"model": ErrorResponse, "description": "Not found, or not accessible"},
    },
)

#: The run's selected child population (P4d), as its start would name it: readiness then draws no
#: panel sample, since the sampler reads only the population a new run records (RQC6b).
PopulationChoiceQuery = Annotated[str | None, Query(min_length=1, max_length=255)]
RevisionIdPath = Annotated[str, Path(max_length=64, pattern=r"^REV-[0-9a-f]{1,32}$")]
RunIdPath = Annotated[str, Path(max_length=64, pattern=r"^RUN-[0-9a-f]{1,32}$")]
ArtifactIdPath = Annotated[str, Path(max_length=64, pattern=r"^ART-[0-9a-f]{1,32}$")]

# JSON payloads above this size are not inlined (as for project artifacts).
_INLINE_PAYLOAD_LIMIT = 1024 * 1024

# Respondent-level data is never inlined to the browser, whatever its size: the
# results screens read what was computed from it, not the rows (ADR 0016).
_NEVER_INLINED = frozenset({"research_fieldwork_dataset"})

# INTERNAL_ONLY while PROGRESS D6 is open (ADR 0016 decision 6): whoever may edit
# the Study may inspect it. Since ADR 0019 that is every member who has the Study;
# the marker, not the role, is what keeps it out of a client-facing report.
# The experimental Sociomapping and its draft (plan sociomapping-engine I1-I3) likewise:
# EXPERIMENTAL_AIA and never client-facing.
_RESEARCHERS_ONLY = frozenset(
    {
        "research_sociomap",
        "research_analysis_module",
        INTERNAL_REPORT_ARTIFACT_TYPE,
        INTERNAL_REPORT_DOCUMENT_ARTIFACT_TYPE,
        "research_sociomapping",
        SOCIOMAPPING_REPORT_ARTIFACT_TYPE,
    }
)


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class DesignSubmission(BaseModel):
    """The design the browser holds. Content only: identity comes from the Study."""

    model_config = ConfigDict(extra="forbid")

    content: dict[str, Any]
    source_stage: str = Field(max_length=32)
    #: The working revision this design is (ADR 0026 decision 5): the server checks the content
    #: is exactly that revision's and records it with the Design Revision. Required.
    workspace_revision: int = Field(ge=1)


class DesignRevisionResponse(BaseModel):
    """One immutable Design Revision of the Study."""

    model_config = ConfigDict(extra="forbid")

    revision_id: str
    study_id: str
    revision: int
    content_sha256: str
    parent_revision: int | None
    source_stage: str
    created_by: str | None
    created_at: datetime
    created: bool | None = None
    content: dict[str, Any] | None = None
    #: The working revision the design came from; null for a revision written before every
    #: writer named one (ADR 0026 decision 5).
    workspace_revision: int | None = None


class DesignSourceLabels(BaseModel):
    """What a reused design carries from its source, and what that was derived from."""

    model_config = ConfigDict(extra="forbid")

    synthetic: bool
    draft: bool
    never_run: bool
    unlabelled_data: bool
    run_ids: list[str]
    report_artifact_ids: list[str]
    #: Some run answered AI respondents built from its population (ADR 0024).
    modelled: bool = False


class DesignSourceResponse(BaseModel):
    """Where the Study's design came from: a past study's Design Revision (project memory M3)."""

    model_config = ConfigDict(extra="forbid")

    study_id: str
    revision_id: str
    source_study_id: str
    source_revision_id: str
    source_revision: int
    source_content_sha256: str
    labels: DesignSourceLabels
    created_by: str
    created_at: datetime


class DesignRevisionList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DesignRevisionResponse]


class AnswerabilityAcknowledgementBody(BaseModel):
    """A person's decision to run a design whose research questions the run cannot all answer.

    ``digest`` is readiness's ``answerability.digest``: it names the exact gaps the person
    saw, so an acknowledgement never covers a design that changed after it was read.
    """

    model_config = ConfigDict(extra="forbid")

    digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=MIN_ACKNOWLEDGEMENT_CHARS, max_length=MAX_ACKNOWLEDGEMENT_CHARS)

    def domain(self) -> Acknowledgement:
        return Acknowledgement(digest=self.digest, reason=self.reason)


class RunStart(BaseModel):
    """Start the research workflow over one Design Revision of this Study."""

    model_config = ConfigDict(extra="forbid")

    design_revision_id: str = Field(max_length=64, pattern=r"^REV-[0-9a-f]{1,32}$")
    #: What the person confirms a run can cost at most. Only read when the study has a limit
    #: the run's ceiling reaches; the server works the ceiling out and holds this to it.
    confirm_cost_usd: float | None = Field(default=None, ge=0, le=1_000_000)
    #: A materialized child of this study's client to run over instead of LIVE (P4e2).
    population_version_id: str | None = Field(default=None, min_length=1, max_length=255)
    #: Who answers the run, as the person chose it (plan run-recovery-and-truth 5a): one the
    #: deployment offers (``persona_sources`` on readiness), else 409. ``None``: the
    #: deployment's default.
    persona_source: PersonaSource | None = None
    #: Only read when the run cannot answer every research question it states (readiness's
    #: ``answerability``); a start without it is 409 ``research_questions_unanswerable``.
    acknowledge_research_questions: AnswerabilityAcknowledgementBody | None = None


class RunRetry(BaseModel):
    """A retry's confirmation, when the study's limit asks for one."""

    model_config = ConfigDict(extra="forbid")

    confirm_cost_usd: float | None = Field(default=None, ge=0, le=1_000_000)
    #: A retry inherits the original's acknowledgement while the gaps are the same.
    acknowledge_research_questions: AnswerabilityAcknowledgementBody | None = None


class ResearchStepResponse(BaseModel):
    """One step of a research run: its state, its checkpoint, what it produced."""

    model_config = ConfigDict(extra="forbid")

    #: The id the run's events name (``RunEventResponse.step_id``): which step reported what.
    step_id: str
    node_key: str
    kind: str
    stage_type: str
    status: str
    waiting_reason: str | None
    attempts_recorded: int
    max_attempts: int
    started_at: datetime | None
    finished_at: datetime | None
    failure_class: str | None
    error_message: str | None
    #: The code the last attempt's error recorded beside its message (a gate's refusal, such as
    #: ``egress_route_not_approved_for_class``); ``None`` when it recorded none, or anything that
    #: is not a code.
    error_reason: str | None = None
    artifact_id: str | None
    #: ``SYNTHETIC_FIXTURE`` when the step's output came from fictional fieldwork.
    data_origin: str | None = None
    #: An analysis step's stored outcome, ``COMPLETED`` or ``BLOCKED``; ``None`` for any
    #: other step. A BLOCKED module's step SUCCEEDED (the outcome is stored), and this is
    #: what tells it apart from a finished one.
    analysis_outcome: str | None = None
    #: How a label reads ``data_origin``: ``SIMULATED``, ``MODELLED`` or ``UNKNOWN``; ``None``
    #: when the step stamped no origin.
    data_origin_kind: OriginKind | None = None
    #: Why a step stopped for recovery (``RECOVERY_REQUIRED``, which keeps no waiting reason):
    #: ``paid_call_uncertain`` (an attempt sent a paid call whose outcome is unknown, so nothing
    #: repeats it) or ``attempts_exhausted``; ``None`` for any other step, or when its attempts
    #: were not read (a listing) -- unknown, never guessed.
    recovery_reason: Literal["paid_call_uncertain", "attempts_exhausted"] | None = None


class ResearchRunSpend(BaseModel):
    """What one run has cost, by the rules Settings reads a person's spend (Q40), whoever each
    charge is booked to (``artifact-fieldwork`` FLD4)."""

    #: Settled: the usage ledger's rows and the holds no ledger row names.
    spent_usd: float
    #: Holds open now: not spent yet, and not in the study's remainder.
    reserved_usd: float
    #: Calls whose cost is not known: with any, ``spent_usd`` is not known to the cent.
    uncertain_calls: int


class ResearchRunPopulation(BaseModel):
    """The population a run recorded (population-operations P3), and whether anything read it.

    ``read_by_fieldwork`` is whether the run pinned the panel persona source: only then is the
    recorded population where its respondents come from; otherwise it is a record.
    """

    model_config = ConfigDict(extra="forbid")

    population_id: str | None
    version_id: str
    version_label: str
    read_by_fieldwork: bool


class ResearchRunSelection(BaseModel):
    """What a run's design selected for its respondents and what reached them (5b).

    An applied flag is true only where the code that applies it ran; every false one carries
    its reason (``research_design.selection_receipt``).
    """

    model_config = ConfigDict(extra="forbid")

    dimensions: list[str]
    #: Selected ids that are no persona topic, so they reached no respondent; a run recorded
    #: before this field reads as none named.
    dimensions_unmatched: list[str] = []
    dimensions_applied: bool
    dimensions_reason: str | None
    audience_filters: dict[str, Any]
    filters_applied: bool
    filters_reason: str | None


class ResearchRunMethod(BaseModel):
    """One method a run pinned when it started (plan ``methodology-tab`` Z1)."""

    model_config = ConfigDict(extra="forbid")

    #: ``None``: the run recorded a pin that cannot be read as a name; never a guess.
    name: str | None
    #: ``True``: a version stored on the Metodika tab; ``False``: the code's preset.
    stored: bool


class ResearchRunMethodology(BaseModel):
    """The methods a run computed under, by name: what Results says the numbers came from."""

    model_config = ConfigDict(extra="forbid")

    sociomap: ResearchRunMethod
    support: ResearchRunMethod
    aggregation: ResearchRunMethod
    #: How AI respondents' answers were drawn (plan ``methodology-tab`` R1d).
    response: ResearchRunMethod
    #: ``True``: the response process is not 18.6.6's; ``None``: its pin cannot be read.
    response_deviates: bool | None


class AnswerabilityGapResponse(BaseModel):
    """One research question the run cannot answer, or a design that states none."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    research_question: str | None
    verdict: str | None
    reasons: list[str]
    measures: list[str]


class AnswerabilityResponse(BaseModel):
    """Whether the run can answer every research question it states (``domain.answerability``).

    ``ready`` on readiness says whether the design can run at all; this says whether it can
    answer what it asks. A start over a design that cannot needs a person's acknowledgement of
    exactly these gaps (``digest``).
    """

    model_config = ConfigDict(extra="forbid")

    rules: str
    capable: bool
    digest: str
    gaps: list[AnswerabilityGapResponse]
    #: Research questions whose support only fieldwork decides: not gaps, never answerable.
    pending: list[str] = []
    #: On readiness: whether a start needs the person's acknowledgement of these gaps -- the
    #: deployment's switch is on and the run cannot answer every research question. The page
    #: asks exactly when the server would refuse; off, it only shows the gaps.
    acknowledgement_required: bool = False
    #: On a run: the acknowledgement that let it start with gaps; ``None`` when it had none.
    acknowledgement: dict[str, Any] | None = None
    #: On a run with gaps and no acknowledgement: ``False`` when the switch was off.
    enforced: bool | None = None
    #: On an analysis retry: never refused, recorded as exempt (``analysis_retry``).
    exempt: str | None = None


class ResearchRunResponse(BaseModel):
    """A research run of this Study, as a person needs to read it (ADR 0016)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    study_id: str
    design_revision_id: str
    design_revision: int
    status: str
    phase: str
    needs_attention: bool
    is_terminal: bool
    retryable: bool
    cancel_requested: bool
    fieldwork_source: str
    retry_of: str | None
    created: bool | None = None
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    steps: list[ResearchStepResponse] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    #: Only with ``VIEW_COSTS``; ``None`` otherwise, never zero.
    actual_cost_usd: float | None = None
    #: Only on ``GET …/research/runs/{run_id}``, with ``VIEW_COSTS``; ``None`` on a listed run
    #: and on an action's answer (start, cancel, retry, budget), which is not a cost read.
    spend: ResearchRunSpend | None = None
    #: The population the run recorded; ``None``: it recorded none (no LIVE when it started).
    population: ResearchRunPopulation | None = None
    #: The Sociomap, support and aggregation methods the run pinned when it started.
    methodology: ResearchRunMethodology
    #: Who its AI respondents are, as the run pinned it: ``fictional_roster`` or ``panel``.
    persona_source: str = PersonaSource.FICTIONAL_ROSTER.value
    #: What the design selected and what was applied; ``None``: a run started before 5b,
    #: which recorded nothing -- never read as "nothing selected".
    selection: ResearchRunSelection | None = None
    #: Whether the run could answer its research questions when it started; ``None``: a run
    #: started before it was recorded -- never read as capable.
    answerability: AnswerabilityResponse | None = None


class ResearchRunList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ResearchRunResponse]


class ReadinessCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    message: str


class QuestionOutlookResponse(BaseModel):
    """One item a respondent will answer, and whether the run will answer it."""

    model_config = ConfigDict(extra="forbid")

    question_id: str
    text: str
    section_id: str
    #: The tracked set an object's rating belongs to; ``None`` for a question.
    battery_id: str | None
    #: ANSWERABLE, AT_RISK, UNANSWERABLE or UNKNOWN (``domain.question_outlook``).
    verdict: str
    reasons: list[str]


class ResearchQuestionTraceResponse(BaseModel):
    """One stated research question and the items that measure it."""

    model_config = ConfigDict(extra="forbid")

    text: str
    #: Item ids (``question_outlook[].question_id``) that declare they measure it.
    measures: list[str]
    #: The verdict the start would decide (``answerability.decided_trace``): a gap's, else the
    #: best among the measures the run answers and the analysis cites; never "at risk" beside
    #: a gap that says the run will not answer it.
    verdict: str
    reasons: list[str]
    #: The comparison the plan declares for it (describe, rank_objects, compare_segments,
    #: ab_test); ``None`` when none is declared or the declared one is unknown.
    comparison: str | None = None


class DanglingLinkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    research_question: str


class ResearchTraceResponse(BaseModel):
    """Each stated research question traced to its measures (``domain.research_trace``)."""

    model_config = ConfigDict(extra="forbid")

    questions: list[ResearchQuestionTraceResponse]
    #: Items naming a research question the plan does not state.
    dangling: list[DanglingLinkResponse]
    #: Whether any item declares a link; without one, coverage is unknown.
    linked: bool


class SampleSizeRange(BaseModel):
    """A valid n: a whole number from ``min`` to ``max``, both included."""

    model_config = ConfigDict(extra="forbid")

    min: int
    max: int


class TrackedSetRange(BaseModel):
    """How many objects one tracked set may hold: outside ``min``-``max`` the design does not
    compile (battery_size); outside the recommended range readiness warns."""

    model_config = ConfigDict(extra="forbid")

    min: int
    max: int
    recommended_min: int
    recommended_max: int


class ResearchLimitsResponse(BaseModel):
    """The readiness limits in force for the Study (plan ``run-qc-and-checkpoint`` RQC9).

    The one authority for a valid n: what a run start checks and pins and what a Research Lead
    edit is held to. The web reads it instead of a range of its own, and refuses a value
    outside it -- never clamps it. ``version`` is the stored methodology version in force;
    ``None``: nothing stored, the code's preset (``methodology_version``)."""

    model_config = ConfigDict(extra="forbid")

    methodology_version: str
    version: int | None
    sample_size: SampleSizeRange
    tracked_set: TrackedSetRange


class QuotaCellResponse(BaseModel):
    """One cell of the sample's quota (``domain.population.sampling.QuotaCell``)."""

    model_config = ConfigDict(extra="forbid")

    #: The cell as an identifier: its values folded to ASCII, joined by ``/``.
    key: str
    #: Its value in each of the composition's ``quota_fields``.
    values: list[str]
    #: The respondents the sampler's largest-remainder allotment gave it.
    n: int


class SampleCompositionResponse(BaseModel):
    """The sample a panel run of this design would draw: ``draw_panel_sample`` over the
    population a new run records, at the design's filters, its n and the run's own seed. How n
    is spread over the quota cells, never support for anything measured in a cell."""

    model_config = ConfigDict(extra="forbid")

    #: Why the sampler refused (its reason code); ``None`` when it drew.
    refused: str | None
    #: What the refusal names, the audience preview's ``reasons``; empty when it names nothing.
    refused_reasons: list[str] = []
    version_id: str | None
    seed: int | None
    quota_fields: list[str]
    cells: list[QuotaCellResponse]
    #: Distinct donors behind the sample; ``None`` when refused or without a donor column.
    sample_donors: int | None
    #: Whether the support forecast was counted from this sample (a respondent without a donor
    #: leaves it unknown, as fieldwork refuses such a sample).
    support_counted: bool = False


class _ReadinessBody(BaseModel):
    """What readiness says of a design, whichever revision it was read on."""

    model_config = ConfigDict(extra="forbid")

    rules: str
    ready: bool
    checks: list[ReadinessCheckResponse]
    questions: int
    batteries: int
    objects: int
    n: int | None
    #: The deployment's fieldwork source: ``ai_runtime`` parks until it exists.
    fieldwork_source: str
    #: The most the run can cost: model requests times what the worker reserves for one. An
    #: upper bound, not a forecast. ``None`` with a reason when it cannot be worked out: unknown
    #: is never shown as zero.
    cost_ceiling_usd: float | None = None
    cost_ceiling_unknown: str | None = None
    fieldwork_requests: int = 0
    analysis_calls: int = 0
    #: The study's limit, and whether this run's start will ask for confirmation against it.
    spend_confirm_usd: float | None = None
    confirmation_required: bool = False
    #: Every item, in questionnaire order, with its verdict; empty when the design does not
    #: compile.
    question_outlook: list[QuestionOutlookResponse] = []
    #: ``None`` when the design does not compile.
    research_trace: ResearchTraceResponse | None = None
    #: The source of AI respondents these checks assumed (5a): the one asked for, else the
    #: deployment's default.
    persona_source: str = PersonaSource.FICTIONAL_ROSTER.value
    #: Every source, offered or not, and why not.
    persona_sources: list[PersonaSourceOption] = []
    #: ``None`` when the design does not compile.
    answerability: AnswerabilityResponse | None = None
    #: The sample a panel run would draw (RQC6b); ``None`` when none was drawn (another persona
    #: source, no population to draw from, a fieldwork source that is not ``ai_runtime``).
    sample_composition: SampleCompositionResponse | None = None


class ReadinessResponse(_ReadinessBody):
    """Whether a Design Revision can run in AIA: AIA's structural checks, by name."""

    design_revision_id: str


class WorkingReadinessResponse(_ReadinessBody):
    """The same readiness on a revision of the Study's working content, before any Design
    Revision is submitted (working-copy-edit-ops WCE7). Its answerability's digest names no
    Design Revision, so it never stands for a start's acknowledgement."""

    working_revision: int


class StageImpactResponse(BaseModel):
    """One pipeline stage and what the working copy means for it."""

    model_config = ConfigDict(extra="forbid")

    stage: str
    #: CURRENT, CHANGED (its own inputs differ) or RECHECK (an earlier change reaches it).
    impact: Literal["CURRENT", "CHANGED", "RECHECK"]


class WorkingImpactResponse(BaseModel):
    """A working revision beside a Design Revision (working-copy-edit-ops WCE7)."""

    model_config = ConfigDict(extra="forbid")

    working_revision: int
    design_revision_id: str
    design_revision: int
    #: The top-level fields of the design that differ.
    changed: list[str]
    #: Every pipeline stage, in pipeline order.
    stages: list[StageImpactResponse]


class PersonaSourceOption(BaseModel):
    """One source of a run's AI respondents, and whether this deployment offers it (5a)."""

    model_config = ConfigDict(extra="forbid")

    source: str
    offered: bool
    #: Why it is not offered (``fieldwork_not_ai_runtime``, ``panel_personas_disabled``);
    #: ``None`` when it is.
    reason: str | None
    #: The source a start that names none pins.
    default: bool


def _reservations(request: Request) -> RunReservations:
    """What the worker reserves per request, as the deployment's settings carry it."""
    settings = request.app.state.settings
    return RunReservations(
        fieldwork_usd=settings.ai_fieldwork_reservation_usd,
        analysis_usd=settings.ai_analysis_reservation_usd,
    )


def _cost_refused(exc: CostConfirmationRequired | CostCeilingUnknown) -> HTTPException:
    """409: the study's limit asks first (with the ceiling), or the ceiling cannot be worked out."""
    if isinstance(exc, CostConfirmationRequired):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "cost_confirmation_required",
                "message": "This run can cost up to the ceiling shown; confirm it to start.",
                "details": {"ceiling_usd": exc.ceiling_usd, "limit_usd": exc.limit_usd},
            },
        )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "cost_ceiling_unknown",
            "message": "The study has a spend limit and this run's cost ceiling cannot be worked "
            "out, so it is not started.",
            "details": {
                "reason": exc.reason.value,
                "limit_usd": exc.limit_usd,
                **({"kinds": list(exc.kinds)} if exc.kinds else {}),
            },
        },
    )


def _answerability(answer: Answerability, *, required: bool) -> AnswerabilityResponse:
    return AnswerabilityResponse(
        rules=ANSWERABILITY_RULES,
        capable=answer.capable,
        digest=answer.digest,
        gaps=[AnswerabilityGapResponse.model_validate(g.to_json()) for g in answer.gaps],
        pending=list(answer.pending),
        acknowledgement_required=required and not answer.capable,
    )


def _recorded_answerability(meta: Mapping[str, Any]) -> AnswerabilityResponse | None:
    note = read_answerability_note(meta)
    if note is None:
        return None
    return AnswerabilityResponse(
        rules=str(note["rules"]),
        capable=bool(note["capable"]),
        digest=str(note.get("digest") or ""),
        gaps=[AnswerabilityGapResponse.model_validate(g) for g in note["gaps"]],
        pending=[str(p) for p in note.get("pending") or []],
        acknowledgement=note.get("acknowledgement"),
        enforced=note.get("enforced") if isinstance(note.get("enforced"), bool) else None,
        exempt=str(note["exempt"]) if note.get("exempt") else None,
    )


def _unanswerable(exc: ResearchQuestionsUnanswerable) -> HTTPException:
    """409: the design can run, but not answer every research question it states."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "research_questions_unanswerable",
            "message": "The run cannot answer every research question the design states; "
            "acknowledge these gaps with a reason to start it anyway.",
            "details": _answerability(exc.answerability, required=True).model_dump(mode="json"),
        },
    )


def _acknowledgement(
    body: AnswerabilityAcknowledgementBody | None,
) -> Acknowledgement | None:
    try:
        return body.domain() if body is not None else None
    except AcknowledgementRefused as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "acknowledgement_invalid", "message": str(exc)},
        ) from exc


def _not_ready(readiness: Any) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "design_not_ready",
            "message": "The design does not pass the readiness checks.",
            "details": {
                "failed": [
                    c.model_dump(mode="json") for c in readiness.checks if c.status == "FAIL"
                ]
            },
        },
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _not_found(what: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": f"{what}_not_found", "message": "No such resource."},
    )


def _population_refused(exc: PopulationError) -> HTTPException:
    """409: the selected child exists but its population cannot be resolved now."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "population_unavailable",
            "message": "The selected population cannot be used for a run now.",
            "details": {"reason": exc.reason},
        },
    )


def _refused(exc: ScopeDenied) -> HTTPException:
    """A permission or lifecycle refusal inside a Study the caller can see: 403."""
    code = "study_closed" if exc.reason == "study_closed" else "insufficient_role"
    message = (
        "The study no longer accepts changes."
        if code == "study_closed"
        else "Your role on this study does not permit that."
    )
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": code, "message": message, "details": {"reason": exc.reason}},
    )


def _artifact_origin_kind(metadata: Mapping[str, Any]) -> OriginKind:
    """A report artifact's origin kind; one written before it recorded ``data_origin`` was
    labelled only ``synthetic``, so anything else it says is unknown."""
    if metadata.get("data_origin"):
        return origin_kind(str(metadata["data_origin"]))
    return OriginKind.SIMULATED if metadata.get("synthetic") else OriginKind.UNKNOWN


def _origin_flags(kinds: set[OriginKind]) -> dict[str, Any]:
    """``modelled`` and the one ``data_origin_kind`` of what was read (``None``: nothing; mixed
    kinds read as ``UNKNOWN``)."""
    kind = next(iter(kinds)) if len(kinds) == 1 else (OriginKind.UNKNOWN if kinds else None)
    return {
        "modelled": OriginKind.MODELLED in kinds,
        "data_origin_kind": kind.value if kind is not None else None,
    }


def design_source_response(source: DesignSource) -> DesignSourceResponse:
    """The citation as the API returns it."""
    labels = source.labels
    return DesignSourceResponse(
        study_id=source.study_id,
        revision_id=source.revision_id,
        source_study_id=source.source_study_id,
        source_revision_id=source.source_revision_id,
        source_revision=source.source_revision,
        source_content_sha256=source.source_content_sha256,
        labels=DesignSourceLabels(
            synthetic=labels.synthetic,
            draft=labels.draft,
            never_run=labels.never_run,
            unlabelled_data=labels.unlabelled_data,
            run_ids=list(labels.run_ids),
            report_artifact_ids=list(labels.report_artifact_ids),
            modelled=labels.modelled,
        ),
        created_by=source.created_by,
        created_at=source.created_at,
    )


def design_revision_response(r: DesignRevision) -> DesignRevisionResponse:
    """A Design Revision as the API returns it, without its content."""
    return _revision(r)


def _revision(
    r: DesignRevision, *, created: bool | None = None, content: dict[str, Any] | None = None
) -> DesignRevisionResponse:
    return DesignRevisionResponse(
        revision_id=r.revision_id,
        study_id=r.study_id,
        revision=r.revision,
        content_sha256=r.content_sha256,
        parent_revision=r.parent_revision,
        source_stage=r.source_stage,
        created_by=r.created_by,
        created_at=r.created_at,
        created=created,
        content=content,
        workspace_revision=r.workspace_revision,
    )


# --------------------------------------------------------------------------- #
# Design Revisions
# --------------------------------------------------------------------------- #


@router.post(
    "/design/revisions",
    response_model=DesignRevisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit the research design as a new Design Revision",
    responses={200: {"description": "Identical to the newest revision: nothing new"}},
)
def submit_design(
    body: DesignSubmission, scope: StudyScopeDep, session: SessionDep, response: Response
) -> DesignRevisionResponse:
    """Store the design as an immutable, Study-scoped revision (ADR 0016 decision 1).

    Needs ``EDIT_STUDY`` on an open research Study. Content identical to the
    newest revision answers 200 with that revision; anything else is a new one. The content
    must be exactly the working revision ``workspace_revision`` names, else 422
    ``design_not_from_workspace`` (ADR 0026 decision 5).
    """
    try:
        revision, created = StudyDesignRepository(session, scope).submit(
            content=body.content,
            source_stage=body.source_stage,
            workspace_revision=body.workspace_revision,
        )
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except DesignRejected as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.reason, "message": str(exc)},
        ) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return _revision(revision, created=created)


@router.get(
    "/design/revisions",
    response_model=DesignRevisionList,
    summary="The Study's Design Revisions, newest first",
)
def list_designs(
    scope: StudyScopeDep, session: SessionDep, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> DesignRevisionList:
    items = StudyDesignRepository(session, scope).revisions(limit=limit)
    return DesignRevisionList(items=[_revision(r) for r in items])


@router.get(
    "/design/revisions/{revision_id}",
    response_model=DesignRevisionResponse,
    summary="One Design Revision, with its content",
)
def get_design(
    revision_id: RevisionIdPath, scope: StudyScopeDep, session: SessionDep
) -> DesignRevisionResponse:
    """A revision of this Study only; another Study's revision id is a 404."""
    repo = StudyDesignRepository(session, scope)
    try:
        return _revision(repo.get(revision_id), content=repo.content(revision_id))
    except DesignRevisionNotFound as exc:
        raise _not_found("design_revision") from exc


@router.get(
    "/design/source",
    response_model=DesignSourceResponse,
    summary="Where the Study's design came from, when it was reused",
    responses={404: {"model": ErrorResponse, "description": "The design was not reused"}},
)
def design_source(scope: StudyScopeDep, session: SessionDep) -> DesignSourceResponse:
    """The past study and Design Revision this Study's design was reused from, with its labels."""
    source = StudyDesignRepository(session, scope).source()
    if source is None:
        raise _not_found("design_source")
    return design_source_response(source)


# --------------------------------------------------------------------------- #
# Research runs
# --------------------------------------------------------------------------- #


def _fieldwork_source(request: Request) -> Any:
    """The composition's fieldwork source: settings decide, never the request."""
    return request.app.state.settings.research_fieldwork_source


def _recovery_reason(
    s: Mapping[str, Any],
) -> Literal["paid_call_uncertain", "attempts_exhausted"] | None:
    """Why a step stopped for recovery, from its attempts (PC14); ``None`` when it did not, or when
    its attempts were not read."""
    if s["status"] is not StepRunStatus.RECOVERY_REQUIRED or "attempts" not in s:
        return None
    if any(a["paid_call_dispatched"] and not a["paid_call_outcome_known"] for a in s["attempts"]):
        return "paid_call_uncertain"
    if s["attempts_recorded"] >= s["max_attempts"]:
        return "attempts_exhausted"
    return None


_CODE = re.compile(r"[a-z][a-z0-9_:.-]{0,79}")


def _code(value: object) -> str | None:
    """A stored reason when it is a code; free text is never passed on as one."""
    return value if isinstance(value, str) and _CODE.fullmatch(value) else None


def _step(s: dict[str, Any]) -> ResearchStepResponse:
    attempts = s.get("attempts") or []
    last = attempts[-1] if attempts else None
    error = (last or {}).get("error") or {}
    output = s.get("output") or {}
    return ResearchStepResponse(
        step_id=s["step_id"],
        node_key=s["node_key"],
        kind=s["kind"],
        stage_type=s["stage_type"],
        status=s["status"].value,
        waiting_reason=s.get("waiting_reason"),
        attempts_recorded=s["attempts_recorded"],
        max_attempts=s["max_attempts"],
        started_at=attempts[0]["started_at"] if attempts else None,
        finished_at=s.get("finished_at"),
        failure_class=last["failure_class"].value if last and last["failure_class"] else None,
        error_message=str(error.get("message")) if error.get("message") else None,
        error_reason=_code(error.get("reason")),
        artifact_id=str(output["artifact_id"]) if output.get("artifact_id") else None,
        data_origin=str(output["data_origin"]) if output.get("data_origin") else None,
        data_origin_kind=origin_kind(output["data_origin"]) if output.get("data_origin") else None,
        analysis_outcome=str(output["outcome"])
        if s.get("kind") == ANALYSIS_STEP_KIND and output.get("outcome") in _ANALYSIS_OUTCOMES
        else None,
        recovery_reason=_recovery_reason(s),
    )


def _methodology(meta: Mapping[str, Any]) -> ResearchRunMethodology:
    methods = run_methods(meta)
    return ResearchRunMethodology(
        **{
            module: ResearchRunMethod(name=m.name, stored=m.stored) for module, m in methods.items()
        },
        response_deviates=response_deviates(meta),
    )


_ANALYSIS_OUTCOMES: Final = frozenset({"COMPLETED", "BLOCKED"})


def _run(
    run: dict[str, Any], scope: StudyContext, *, created: bool | None = None
) -> ResearchRunResponse:
    meta = run.get("metadata") or {}
    steps = [_step(s) for s in run.get("steps", [])]
    cost: float | None = None
    # A listed run's steps carry no attempts, so no cost: unknown, never zero.
    listed = "steps" in run and any("attempts" not in s for s in run["steps"])
    if scope.has(Permission.VIEW_COSTS) and "steps" in run and not listed:
        cost = sum(
            float(a.get("actual_cost_usd") or 0.0)
            for s in run["steps"]
            for a in s.get("attempts", [])
        )
    return ResearchRunResponse(
        run_id=run["run_id"],
        study_id=scope.study_id,
        design_revision_id=str(meta.get("design_revision_id", "")),
        design_revision=int(meta.get("design_revision", run.get("project_revision", 0))),
        status=run["status"].value,
        phase=run["phase"].value,
        needs_attention=run["status"].needs_attention,
        is_terminal=run["status"].is_terminal,
        retryable=bool(run["retryable"]),
        cancel_requested=bool(run["cancel_requested"]),
        fieldwork_source=str(meta.get("fieldwork_source", "")),
        retry_of=meta.get("retry_of"),
        created=created,
        created_at=run.get("created_at"),
        started_at=run.get("started_at"),
        finished_at=run.get("finished_at"),
        steps=steps,
        artifact_ids=[s.artifact_id for s in steps if s.artifact_id],
        actual_cost_usd=cost,
        population=(
            ResearchRunPopulation.model_validate(meta["population"])
            if isinstance(meta.get("population"), dict)
            else None
        ),
        methodology=_methodology(meta),
        persona_source=persona_source_of(meta).value,
        selection=_selection(meta, steps, terminal=run["status"].is_terminal),
        answerability=_recorded_answerability(meta),
    )


def _selection(
    meta: dict[str, Any], steps: list[ResearchStepResponse], *, terminal: bool
) -> ResearchRunSelection | None:
    """The run's recorded selection, settled by its fieldwork (``settle_selection``; 5b, 5c;
    review, Codex on #439). ``None``: a run that recorded none, never read as nothing selected."""
    if not isinstance(meta.get("selection"), dict):
        return None
    fieldwork = next((s for s in steps if s.node_key == "run"), None)
    drawn = (
        fieldwork is not None
        and fieldwork.status == "SUCCEEDED"
        and fieldwork.data_origin == DataOrigin.MODELLED_AI_PANEL.value
    )
    return ResearchRunSelection.model_validate(
        settle_selection(meta["selection"], drawn=drawn, ended=terminal)
    )


def _persona_source(request: Request) -> PersonaSource:
    """The deployment's default for a new run that names no source (5a): the panel with the
    switch on and the AI runtime as the source, else the roster. The run pins what it starts
    with, and a retry keeps the original's instead."""
    settings = request.app.state.settings
    if (
        settings.ai_population_personas_enabled
        and _fieldwork_source(request) is FieldworkSource.AI_RUNTIME
    ):
        return PersonaSource.PANEL
    return PersonaSource.FICTIONAL_ROSTER


def _unoffered(request: Request, source: PersonaSource) -> str | None:
    """Why this deployment does not offer ``source``; ``None`` when it does. The roster is
    always offered; the panel only under the AI runtime with the panel switch on."""
    if source is PersonaSource.FICTIONAL_ROSTER:
        return None
    if _fieldwork_source(request) is not FieldworkSource.AI_RUNTIME:
        return "fieldwork_not_ai_runtime"
    if not request.app.state.settings.ai_population_personas_enabled:
        return "panel_personas_disabled"
    return None


def _persona_sources(request: Request) -> list[PersonaSourceOption]:
    default = _persona_source(request)
    return [
        PersonaSourceOption(
            source=source.value,
            offered=_unoffered(request, source) is None,
            reason=_unoffered(request, source),
            default=source is default,
        )
        for source in PersonaSource
    ]


def _chosen_persona_source(request: Request, asked: PersonaSource | None) -> PersonaSource:
    """The source a person asked for, when the deployment offers it; the default when none
    was asked. One it does not offer is refused by name, never swapped for another."""
    if asked is None:
        return _persona_source(request)
    reason = _unoffered(request, asked)
    if reason is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "persona_source_unavailable",
                "message": "This deployment does not offer that source of respondents.",
                "details": {"persona_source": asked.value, "reason": reason},
            },
        )
    return asked


def _no_population(exc: PanelPopulationMissing) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "population_not_established",
            "message": (
                "Respondenti se berou z populace, ale žádná populace není založená. "
                "Nic nebylo spuštěno."
            ),
            "details": {"reason": str(exc)},
        },
    )


def _retired_method(exc: ResearchRunOnRetiredMethod, study_id: str) -> HTTPException:
    """409: the run's Sociomap method is one no new run computes, so it is not started again.
    ``new_run`` is the request that starts a new run over the same Design Revision, which pins
    ``aia-sociomap-5``, with the refused run's respondents, population and research-question
    decision; nothing was started."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "run_on_retired_method",
            "message": (
                "Běh byl spočten starší metodou Sociomapy a znovu se nespouští. Spusťte nový "
                "běh ze stejné revize návrhu; spočte se metodou aia-sociomap-5. Nic nebylo "
                "spuštěno."
            ),
            "details": {
                "methods": exc.methods,
                "design_revision_id": exc.design_revision_id,
                "new_run": {
                    "method": "POST",
                    "href": f"/api/v1/studies/{study_id}/research/runs",
                    "body": exc.new_run,
                },
            },
        },
    )


def _started(runs: ResearchRuns, started: StartedRun, response: Response) -> ResearchRunResponse:
    if started.created:
        response.headers["Location"] = (
            f"/api/v1/studies/{runs.scope.study_id}/research/runs/{started.run_id}"
        )
    else:
        response.status_code = status.HTTP_200_OK
    return _run(runs.get(started.run_id), runs.scope, created=started.created)


@router.get(
    "/research/limits",
    response_model=ResearchLimitsResponse,
    summary="The readiness limits in force: the valid sample size and a tracked set's size",
)
def research_limits(scope: StudyScopeDep, session: SessionDep) -> ResearchLimitsResponse:
    """The limits a run start of this Study checks today, read from the organization's
    readiness methodology in force (the preset when nothing is stored). Starts nothing."""
    limits, stored = readiness_in_force(session, scope)
    return ResearchLimitsResponse(
        methodology_version=limits.methodology_version,
        version=None if stored is None else int(stored["version"]),
        sample_size=SampleSizeRange(min=limits.sample_size.min, max=limits.sample_size.max),
        tracked_set=TrackedSetRange(**limits.tracked_set.model_dump()),
    )


@router.get(
    "/research/readiness",
    response_model=ReadinessResponse,
    summary="Can this Design Revision run in AIA?",
)
def readiness(
    request: Request,
    scope: StudyScopeDep,
    session: SessionDep,
    sampler: PanelSamplerDep,
    design_revision_id: Annotated[str, Query(max_length=64, pattern=r"^REV-[0-9a-f]{1,32}$")],
    persona_source: Annotated[PersonaSource | None, Query()] = None,
    population_version_id: PopulationChoiceQuery = None,
) -> ReadinessResponse:
    """Compile the revision and run AIA's structural checks, without starting anything.

    ``persona_source`` assesses the design under that source of respondents (the support
    forecast and the audience check differ); one the deployment does not offer is 409.
    The 18.6.6 technical preflight is not these checks and is not claimed.
    """
    chosen = _chosen_persona_source(request, persona_source)
    runs = ResearchRuns(session, scope, panel_sampler=sampler)
    try:
        outlook = runs.outlook(
            design_revision_id,
            persona_source=chosen,
            fieldwork_source=_fieldwork_source(request),
            population_version_id=population_version_id,
        )
    except DesignRevisionNotFound as exc:
        raise _not_found("design_revision") from exc
    return ReadinessResponse(
        design_revision_id=design_revision_id,
        **_readiness_body(request, runs, outlook, chosen),
    )


@router.get(
    "/research/readiness/working",
    response_model=WorkingReadinessResponse,
    summary="Could this working revision run in AIA?",
)
def working_readiness(
    request: Request,
    scope: StudyScopeDep,
    session: SessionDep,
    sampler: PanelSamplerDep,
    working_revision: Annotated[int, Query(ge=1)],
    persona_source: Annotated[PersonaSource | None, Query()] = None,
    population_version_id: PopulationChoiceQuery = None,
) -> WorkingReadinessResponse:
    """The readiness of a revision of the Study's working content, read as a submit of it
    would read it, with no Design Revision written (working-copy-edit-ops WCE7). A stage
    reads it on the revision it shows; a start still runs a submitted Design Revision.
    A revision the Study never saved is 404 ``working_revision``."""
    chosen = _chosen_persona_source(request, persona_source)
    runs = ResearchRuns(session, scope, panel_sampler=sampler)
    try:
        outlook = runs.outlook_working(
            working_revision,
            persona_source=chosen,
            fieldwork_source=_fieldwork_source(request),
            population_version_id=population_version_id,
        )
    except WorkingRevisionNotFound as exc:
        raise _not_found("working_revision") from exc
    return WorkingReadinessResponse(
        working_revision=working_revision,
        **_readiness_body(request, runs, outlook, chosen),
    )


@router.get(
    "/research/impact",
    response_model=WorkingImpactResponse,
    summary="What a working revision changes against a Design Revision, stage by stage",
)
def working_impact(
    scope: StudyScopeDep,
    session: SessionDep,
    working_revision: Annotated[int, Query(ge=1)],
    design_revision_id: Annotated[
        str | None, Query(max_length=64, pattern=r"^REV-[0-9a-f]{1,32}$")
    ] = None,
) -> WorkingImpactResponse:
    """Each pipeline stage CURRENT, CHANGED or RECHECK going from the Design Revision (the newest
    when none is named; a run's own to ask about that run) to the working revision, and the
    top-level fields that differ (working-copy-edit-ops WCE7). Reads both; writes nothing. A
    working revision the Study never saved is 404 ``working_revision``; a Design Revision not of
    this Study, or a Study with none, 404 ``design_revision``."""
    runs = ResearchRuns(session, scope)
    try:
        found = runs.impact(working_revision, design_revision_id)
    except WorkingRevisionNotFound as exc:
        raise _not_found("working_revision") from exc
    except DesignRevisionNotFound as exc:
        raise _not_found("design_revision") from exc
    return WorkingImpactResponse(
        working_revision=found.working_revision,
        design_revision_id=found.design_revision_id,
        design_revision=found.design_revision,
        changed=list(found.changed),
        stages=[StageImpactResponse(stage=k, impact=v.value) for k, v in found.stages.items()],
    )


def _readiness_body(
    request: Request, runs: ResearchRuns, outlook: RunOutlook, chosen: PersonaSource
) -> dict[str, Any]:
    """The readiness fields both routes answer, from one outlook."""
    spec, result = outlook.spec, outlook.readiness
    settings = request.app.state.settings
    ceiling = (
        runs.cost_ceiling(
            spec,
            fieldwork_source=_fieldwork_source(request),
            analysis_enabled=settings.ai_analysis_enabled,
            reservations=_reservations(request),
        )
        if spec
        else None
    )
    limit = runs.spend_limit()
    return {
        "rules": result.rules,
        "ready": result.ready,
        "checks": [
            ReadinessCheckResponse(id=c.id, status=c.status.value, message=c.message)
            for c in result.checks
        ],
        "questions": len(spec.questions) if spec else 0,
        "batteries": len(spec.batteries) if spec else 0,
        "objects": sum(len(b.objects) for b in spec.batteries) if spec else 0,
        "n": spec.n if spec else None,
        "fieldwork_source": str(_fieldwork_source(request).value),
        "cost_ceiling_usd": ceiling.total_usd if ceiling else None,
        "cost_ceiling_unknown": ceiling.unknown.value if ceiling and ceiling.unknown else None,
        "fieldwork_requests": ceiling.fieldwork_requests if ceiling else 0,
        "analysis_calls": ceiling.analysis_calls if ceiling else 0,
        "spend_confirm_usd": limit,
        # Unknown does not ask: it refuses at the start, so the page shows it differently.
        "confirmation_required": bool(
            limit is not None
            and ceiling
            and ceiling.total_usd is not None
            and ceiling.total_usd >= limit
        ),
        "question_outlook": [
            QuestionOutlookResponse(
                question_id=q.question_id,
                text=q.text,
                section_id=q.section_id,
                battery_id=q.battery_id,
                verdict=q.verdict.value,
                reasons=[r.value for r in q.reasons],
            )
            for q in outlook.questions
        ],
        "research_trace": _trace(outlook.trace) if outlook.trace is not None else None,
        "persona_source": chosen.value,
        "persona_sources": _persona_sources(request),
        "answerability": _answerability(
            outlook.answerability,
            required=request.app.state.settings.research_answerability_gate,
        )
        if outlook.answerability is not None
        else None,
        "sample_composition": _composition(
            outlook.panel, counted=outlook.forecast is not None and outlook.forecast.known
        )
        if outlook.panel is not None
        else None,
    }


def _composition(panel: PanelDraw, *, counted: bool) -> SampleCompositionResponse:
    sample = panel.sample
    if sample is None:
        return SampleCompositionResponse(
            refused=panel.refused,
            refused_reasons=list(panel.reasons),
            version_id=panel.version_id,
            seed=panel.seed,
            quota_fields=[],
            cells=[],
            sample_donors=None,
        )
    return SampleCompositionResponse(
        refused=None,
        version_id=sample.version_id,
        seed=sample.seed,
        quota_fields=list(sample.audit.quota_fields),
        cells=[
            QuotaCellResponse(key=key, values=list(c.values), n=c.n)
            for c, key in zip(sample.quota_cells, quota_keys(sample.quota_cells), strict=True)
        ],
        sample_donors=sample.audit.sample_donors,
        support_counted=counted,
    )


def _trace(trace: ResearchTrace) -> ResearchTraceResponse:
    return ResearchTraceResponse(
        questions=[
            ResearchQuestionTraceResponse(
                text=q.text,
                measures=list(q.measures),
                verdict=q.verdict.value,
                reasons=[r.value for r in q.reasons],
                comparison=q.comparison.value if q.comparison else None,
            )
            for q in trace.questions
        ],
        dangling=[
            DanglingLinkResponse(question_id=d.question_id, research_question=d.research_question)
            for d in trace.dangling
        ],
        linked=trace.linked,
    )


@router.post(
    "/research/runs",
    response_model=ResearchRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run the research workflow over a Design Revision",
    responses={200: {"description": "This revision already has a run: that run"}},
)
def start_run(
    body: RunStart,
    request: Request,
    scope: StudyScopeDep,
    session: SessionDep,
    response: Response,
    population: RunPopulationDep,
    sampler: PanelSamplerDep,
) -> ResearchRunResponse:
    """Idempotent per Design Revision: a double submission gets the existing run.

    Needs ``RUN_WORKFLOW`` on an open Study. The fieldwork source is the
    deployment's, never the request's; who answers is the person's, among the sources the
    deployment offers (409 ``persona_source_unavailable`` otherwise). The population a new run
    records is the deployment's (the Czech LIVE; the population double only in local and test).
    """
    persona_source = _chosen_persona_source(request, body.persona_source)
    runs = ResearchRuns(
        session,
        scope,
        population_contract=population.contract,
        population_id=population.population_id,
        panel_sampler=sampler,
    )
    with run_start_errors():
        started = runs.start(
            design_revision_id=body.design_revision_id,
            fieldwork_source=_fieldwork_source(request),
            analysis_enabled=request.app.state.settings.ai_analysis_enabled,
            external_context=request.app.state.settings.ai_analysis_external_context,
            sociomapping_enabled=request.app.state.settings.sociomapping_experimental_enabled,
            reservations=_reservations(request),
            confirm_cost_usd=body.confirm_cost_usd,
            population_version_id=body.population_version_id,
            persona_source=persona_source,
            acknowledge=_acknowledgement(body.acknowledge_research_questions),
            require_answerability=request.app.state.settings.research_answerability_gate,
        )
    return _started(runs, started, response)


@contextmanager
def run_start_errors() -> Iterator[None]:
    """A research run start's refusals as HTTP, one mapping for every way a run is started:
    this router's ``POST …/research/runs`` and the Lead's typed start (``routers/lead.py``)."""
    try:
        yield
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except DesignRevisionNotFound as exc:
        raise _not_found("design_revision") from exc
    except DesignNotReady as exc:
        raise _not_ready(exc.readiness) from exc
    except ResearchQuestionsUnanswerable as exc:
        raise _unanswerable(exc) from exc
    except (CostConfirmationRequired, CostCeilingUnknown) as exc:
        raise _cost_refused(exc) from exc
    except PanelPopulationMissing as exc:
        raise _no_population(exc) from exc
    except UnknownDatasetVersion as exc:
        # Another client's or organization's child reads as not there, like any scope miss.
        raise _not_found("population_version") from exc
    except PopulationError as exc:
        raise _population_refused(exc) from exc
    except AnalysisNotRetryable as exc:
        # The Lead's typed analysis retry ("Zopakuj analýzu"), refused as the stage's retry is.
        raise _not_retryable(exc) from exc
    except ReconstructionRefused as exc:
        if exc.reason == "run_not_found":
            raise _not_found("run") from exc
        raise HTTPException(
            status_code=409, detail={"code": exc.reason, "message": str(exc)}
        ) from exc


def run_start_settings(
    request: Request,
    population: AudiencePopulation,
    sampler: PanelSampler | None,
    store: ArtifactStore | None = None,
) -> RunStartSettings:
    """What a research run's start takes from the deployment, as ``start_run`` passes it: the
    fieldwork source, analysis and Sociomapping switches, reservations, the default persona
    source, the answerability gate and the population a new run records. A typed start (LO5)
    names no persona source, population child or acknowledgement, so it starts on the
    deployment's defaults, as a start naming none does here. ``store``: what a typed analysis
    retry reads the run's stored outcomes from."""
    settings = request.app.state.settings
    return RunStartSettings(
        fieldwork_source=_fieldwork_source(request),
        analysis_enabled=settings.ai_analysis_enabled,
        external_context=settings.ai_analysis_external_context,
        sociomapping_enabled=settings.sociomapping_experimental_enabled,
        reservations=_reservations(request),
        persona_source=_persona_source(request),
        require_answerability=settings.research_answerability_gate,
        population_contract=population.contract,
        population_id=population.population_id,
        panel_sampler=sampler,
        store=store,
    )


@router.get(
    "/research/sociomap-register",
    response_model=dict[str, Any],
    summary="Which Sociomap methods are approved, at which exact specification",
)
def sociomap_register(scope: StudyScopeDep) -> dict[str, Any]:
    """The register a map's status is read from (complete-study-report B4): a map is approved
    only when its run recorded exactly an entry's method id and spec fingerprint."""
    try:
        scope.require(Permission.VIEW_RESULTS)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    return {"entries": [entry.model_dump(mode="json") for entry in SOCIOMAP_REGISTER]}


class DimensionTopic(BaseModel):
    """A selected dimension and the persona topic it lets through (``dimension_topic``)."""

    model_config = ConfigDict(extra="forbid")

    dimension: str
    #: ``None``: it names no persona topic, so a run lists it in ``dimensions_unmatched`` and
    #: no respondent's profile carries it.
    topic: str | None


class DimensionTopicList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DimensionTopic]


@router.get(
    "/research/persona-topics",
    response_model=DimensionTopicList,
    summary="The persona topic each dimension lets through",
)
def persona_topics(
    scope: StudyScopeDep,
    dimension: Annotated[
        list[Annotated[str, StringConstraints(max_length=80)]], Query(max_length=64)
    ] = [],  # noqa: B006
) -> DimensionTopicList:
    """Dimenze's chip before any run (artifact-dimensions DIM2): the same mapping a run's
    ``selection_receipt`` reads, asked of the working copy's dimensions, in the order given.
    It reads no design, so a dimension chosen a moment ago is answered without a revision."""
    try:
        scope.require(Permission.VIEW_STUDY)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    return DimensionTopicList(
        items=[DimensionTopic(dimension=d, topic=dimension_topic(d)) for d in dimension]
    )


@router.get("/research/runs", response_model=ResearchRunList, summary="The Study's research runs")
def list_runs(
    scope: StudyScopeDep, session: SessionDep, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> ResearchRunList:
    runs = ResearchRuns(session, scope)
    return ResearchRunList(items=[_run(r, scope) for r in runs.runs(limit=limit, steps=True)])


@router.get(
    "/research/runs/{run_id}", response_model=ResearchRunResponse, summary="One research run"
)
def get_run(run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep) -> ResearchRunResponse:
    runs = ResearchRuns(session, scope)
    try:
        run = runs.get(run_id)
        response = _run(run, scope)
        if scope.has(Permission.VIEW_COSTS):
            spent = runs.spend(run)
            response.spend = ResearchRunSpend(
                spent_usd=spent.total_usd,
                reserved_usd=spent.reserved_usd,
                uncertain_calls=spent.uncertain_calls,
            )
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc
    return response


@router.get(
    "/research/runs/{run_id}/events",
    response_model=list[RunEventResponse],
    summary="The run's events after a cursor",
)
def run_events(
    run_id: RunIdPath,
    scope: StudyScopeDep,
    session: SessionDep,
    since: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> list[RunEventResponse]:
    try:
        events = ResearchRuns(session, scope).events(run_id, since=since, limit=limit)
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc
    return [_event(e) for e in events]


def _event(e: dict[str, Any]) -> RunEventResponse:
    return RunEventResponse(
        event_id=e["event_id"],
        step_id=e["step_id"],
        attempt_id=e["attempt_id"],
        event_type=e["event_type"],
        level=e["level"],
        message=e["message"],
        payload=e["payload"],
        created_at=e["created_at"],
    )


@router.post(
    "/research/runs/{run_id}/cancel",
    response_model=ResearchRunResponse,
    summary="Cancel a research run",
)
def cancel_run(run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep) -> ResearchRunResponse:
    """Needs ``CANCEL_WORKFLOW``. A running step stops at its next checkpoint."""
    runs = ResearchRuns(session, scope)
    try:
        runs.cancel(run_id)
        return _run(runs.get(run_id), scope)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc


NodeKeyPath = Annotated[str, Path(max_length=64, pattern=r"^[a-z][a-z0-9_]*$")]


class BudgetLiftRequest(BaseModel):
    """The budget the study is raised to, and why. Never a lower one."""

    model_config = ConfigDict(extra="forbid")

    budget_usd: float = Field(ge=0, le=1_000_000)
    note: str = Field(default="", max_length=500)


@router.post(
    "/research/runs/{run_id}/budget",
    response_model=ResearchRunResponse,
    summary="Raise the study's budget and let every step of the run stopped at the cap go on",
    responses={
        409: {"model": ErrorResponse, "description": "Nothing in the run waits for budget"},
        422: {"model": ErrorResponse, "description": "The budget offered is below the current one"},
    },
)
def lift_run_budget_wait(
    run_id: RunIdPath,
    body: BudgetLiftRequest,
    scope: StudyScopeDep,
    session: SessionDep,
) -> ResearchRunResponse:
    """Needs ``APPROVE_BUDGET`` and ``MANAGE_STUDY_BUDGET`` on an open Study.

    The run's lift (CR-3): a run's analysis modules each reserve their own call, so several
    steps can stop at the study's budget at once. One lift raises the budget (equal to the
    current one lifts the waits without changing it; lower is refused) and offers every
    waiting step to a worker again, under one lock, as one decision in the approval ledger.
    The cap stays hard: a step whose next reservation still passes the budget stops again.
    """
    runs = ResearchRuns(session, scope)
    try:
        return _run(
            runs.lift_budget_wait(run_id, budget_usd=body.budget_usd, note=body.note), scope
        )
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc
    except (BudgetWaitNotLiftable, BudgetNotRaised) as exc:
        raise _budget_lift_refused(exc) from exc


@router.post(
    "/research/runs/{run_id}/steps/{node_key}/budget",
    response_model=ResearchRunResponse,
    summary="Raise the study's budget and let the run's steps that stopped at the cap go on",
    responses={
        409: {"model": ErrorResponse, "description": "The step is not waiting for budget"},
        422: {"model": ErrorResponse, "description": "The budget offered is below the current one"},
    },
)
def lift_budget_wait(
    run_id: RunIdPath,
    node_key: NodeKeyPath,
    body: BudgetLiftRequest,
    scope: StudyScopeDep,
    session: SessionDep,
) -> ResearchRunResponse:
    """Needs ``APPROVE_BUDGET`` and ``MANAGE_STUDY_BUDGET`` on an open Study.

    A step whose next paid call would pass the study's budget stops waiting for budget,
    and nothing else can resume it. The person names the budget the study is raised to
    (equal to the current one lifts the wait without changing it; lower is refused) and
    the step, with every other step of the run waiting for budget, is offered to a worker
    again (the run's lift, ``POST …/runs/{run_id}/budget``). The decision is written once to
    the approval ledger and the change to the access audit. The cap stays hard: if the new budget is
    still too small the step stops again at its next reservation.
    """
    runs = ResearchRuns(session, scope)
    try:
        return _run(
            runs.lift_budget_wait(run_id, node_key, budget_usd=body.budget_usd, note=body.note),
            scope,
        )
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc
    except ResearchStepNotFound as exc:
        raise _not_found("step") from exc
    except (BudgetWaitNotLiftable, BudgetNotRaised) as exc:
        raise _budget_lift_refused(exc) from exc


def _budget_lift_refused(exc: BudgetWaitNotLiftable | BudgetNotRaised) -> HTTPException:
    """A refused lift, the same on every kind of a Study's work: nothing waits for budget
    (409), or the budget offered would lower the cap (422)."""
    if isinstance(exc, BudgetNotRaised):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "budget_not_raised",
                "message": f"The study's budget is already {exc.current:.2f}; offer at least that.",
            },
        )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "not_waiting_for_budget", "message": str(exc)},
    )


def _runtime_park_refused(exc: RuntimeParkNotResumable) -> HTTPException:
    """Nothing here waits for the AI runtime, or a step that does may not be offered again
    (it sent a paid call, is being cancelled or has no attempt left): 409."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "runtime_park_not_resumable", "message": str(exc)},
    )


@router.post(
    "/research/runs/{run_id}/resume",
    response_model=ResearchRunResponse,
    summary="Let a run parked for the AI runtime go on, once the runtime is on",
    responses={
        409: {
            "model": ErrorResponse,
            "description": "Nothing in the run waits for the AI runtime, or it may not go on",
        },
    },
)
def resume_run(run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep) -> ResearchRunResponse:
    """Needs ``RUN_WORKFLOW`` on an open Study.

    A step whose AI runtime is not deployed (fieldwork's AI respondents, an analysis module)
    or whose gateway refused it before any call parks ``WAITING_PROVIDER`` /
    ``ai_runtime_unavailable``, and no timer resumes it. Once the runtime is on, a person
    offers the same run's parked steps to a worker again: same revision, pins and confirmed
    ceiling, nothing re-chosen. A step that sent a paid call is never offered again here. If
    the runtime is still off the step parks again, without spending an attempt.
    """
    runs = ResearchRuns(session, scope)
    try:
        return _run(runs.resume(run_id), scope)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc
    except RuntimeParkNotResumable as exc:
        raise _runtime_park_refused(exc) from exc


@router.post(
    "/research/runs/{run_id}/retry",
    response_model=ResearchRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a failed or cancelled run again",
    responses={
        200: {"description": "This run was already retried: that retry"},
        409: {
            "model": ErrorResponse,
            "description": "The run is not failed or cancelled, the study's limit asks first, "
            "or it pinned a Sociomap method no new run computes (run_on_retired_method)",
        },
    },
)
def retry_run(
    run_id: RunIdPath,
    request: Request,
    scope: StudyScopeDep,
    session: SessionDep,
    response: Response,
    body: RunRetry | None = None,
) -> ResearchRunResponse:
    """A new run over the same Design Revision, linked to the one it retries."""
    runs = ResearchRuns(session, scope)
    try:
        started = runs.retry(
            run_id,
            fieldwork_source=_fieldwork_source(request),
            reservations=_reservations(request),
            confirm_cost_usd=body.confirm_cost_usd if body else None,
            acknowledge=_acknowledgement(body.acknowledge_research_questions if body else None),
            require_answerability=request.app.state.settings.research_answerability_gate,
        )
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc
    except DesignNotReady as exc:
        raise _not_ready(exc.readiness) from exc
    except ResearchQuestionsUnanswerable as exc:
        raise _unanswerable(exc) from exc
    except (CostConfirmationRequired, CostCeilingUnknown) as exc:
        raise _cost_refused(exc) from exc
    except PanelPopulationMissing as exc:
        raise _no_population(exc) from exc
    except ResearchRunOnRetiredMethod as exc:
        raise _retired_method(exc, scope.study_id) from exc
    except ResearchRunNotRetryable as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "run_not_retryable",
                "message": "Only a failed or cancelled run can be started again.",
                "details": {"status": exc.status.value},
            },
        ) from exc
    return _started(runs, started, response)


@router.get(
    "/research/runs/{run_id}/analysis/retryable",
    response_model=dict[str, Any],
    summary="The analysis modules of a run a person may ask again over its collected data",
)
def run_analysis_retryable(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> dict[str, Any]:
    """Read from the stored outcomes as they are, under whichever harness stored them, so a
    run made before a harness change can still be repaired (``…/analysis`` re-judges and
    refuses those). ``stale``: the modules among them a model completed under an earlier
    harness, which today's refuses to re-admit -- the reason, not a model's failure."""
    try:
        scope.require(Permission.EDIT_STUDY)
        analysis = stored_analysis(session, scope, store, run_id=run_id)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ReconstructionRefused as exc:
        if exc.reason == "run_not_found":
            raise _not_found("run") from exc
        raise HTTPException(
            status_code=409, detail={"code": exc.reason, "message": str(exc)}
        ) from exc
    return {
        "run_id": run_id,
        "modules": [module.value for module in analysis.retryable],
        "stale": [module.value for module in analysis.stale],
    }


_NOT_RETRYABLE_MESSAGES: Final = {
    "run_not_finished": "Běh ještě neskončil; neúspěšné moduly lze zopakovat až po jeho konci.",
    "analysis_not_in_run": "Tento běh neobsahoval AI analýzu.",
    "dataset_missing": "Běh nemá sebraná data, nad kterými by šlo analýzu zopakovat.",
    "nothing_to_retry": "Žádný modul analýzy v tomto běhu neselhal.",
    # The Lead's typed retry, which names no run: the study has none that ran analysis.
    "no_analysed_run": "Studie zatím nemá žádný běh s AI analýzou, který by šlo zopakovat.",
}


@router.post(
    "/research/runs/{run_id}/analysis/retry",
    response_model=ResearchRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ask a finished run's failed analysis modules again, over its collected data",
    responses={
        200: {"description": "This run's analysis was already retried: that retry"},
        409: {
            "model": ErrorResponse,
            "description": "Nothing to retry, the run has not finished, or the limit asks first",
        },
    },
)
def retry_analysis(
    run_id: RunIdPath,
    request: Request,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
    response: Response,
    body: RunRetry | None = None,
) -> ResearchRunResponse:
    """A new run linked to this one: the same respondents' answers, no new fieldwork; only
    the modules a model failed (or whose step failed) are asked again."""
    try:
        started = retry_failed_modules(
            session,
            scope,
            store,
            run_id=run_id,
            reservations=_reservations(request),
            confirm_cost_usd=body.confirm_cost_usd if body else None,
            acknowledge=_acknowledgement(body.acknowledge_research_questions if body else None),
        )
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc
    except ReconstructionRefused as exc:
        if exc.reason == "run_not_found":
            raise _not_found("run") from exc
        raise HTTPException(
            status_code=409, detail={"code": exc.reason, "message": str(exc)}
        ) from exc
    except DesignNotReady as exc:
        raise _not_ready(exc.readiness) from exc
    except ResearchQuestionsUnanswerable as exc:
        raise _unanswerable(exc) from exc
    except (CostConfirmationRequired, CostCeilingUnknown) as exc:
        raise _cost_refused(exc) from exc
    except ResearchRunOnRetiredMethod as exc:
        raise _retired_method(exc, scope.study_id) from exc
    except AnalysisNotRetryable as exc:
        raise _not_retryable(exc) from exc
    return _started(ResearchRuns(session, scope), started, response)


def _not_retryable(exc: AnalysisNotRetryable) -> HTTPException:
    """An analysis retry refused, by its reason: this route's and the Lead's typed retry's."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "analysis_not_retryable",
            "message": _NOT_RETRYABLE_MESSAGES.get(exc.reason, str(exc)),
            "details": {"reason": exc.reason},
        },
    )


@router.get(
    "/research/runs/{run_id}/artifacts/{artifact_id}",
    response_model=ArtifactResponse,
    summary="An artifact the run produced",
)
def run_artifact(
    run_id: RunIdPath,
    artifact_id: ArtifactIdPath,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> ArtifactResponse:
    """Only an artifact this run's steps produced; any other id is a 404.

    Needs ``VIEW_RESULTS``. The bytes are hash-verified on read; a mismatch or a
    missing object marks the artifact CORRUPT, durably, and answers 409 rather
    than serving content that may have been altered.
    """
    try:
        scope.require(Permission.VIEW_RESULTS)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    try:
        produced = ResearchRuns(session, scope).artifact_ids(run_id)
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc
    if artifact_id not in produced:
        raise _not_found("artifact")
    repo = research_artifacts(session, scope, store)
    try:
        artifact = repo.get(artifact_id)
    except ArtifactNotFound as exc:  # pragma: no cover - a step output names a stored artifact
        raise _not_found("artifact") from exc
    if artifact.artifact_type in _RESEARCHERS_ONLY:
        try:
            scope.require(Permission.EDIT_STUDY)
        except ScopeDenied as exc:
            raise _refused(exc) from exc
    payload: Any = None
    if (
        artifact.content_type == "application/json"
        and artifact.size_bytes <= _INLINE_PAYLOAD_LIMIT
        and artifact.artifact_type not in _NEVER_INLINED
    ):
        try:
            payload = repo.read_json(artifact_id)
        except (IntegrityError, ObjectNotFound) as exc:
            raise artifact_corrupt(session) from exc
    return artifact_response(artifact, payload)


@router.get(
    "/research/runs/{run_id}/analysis",
    response_model=dict[str, Any],
    summary="Evidence-checked internal analysis outcomes of a research run",
)
def run_analysis(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> dict[str, Any]:
    """Recheck stored outcomes against the frozen sources before showing prose.

    Each answer to a research question carries ``gap``: what the run recorded at start about that
    question when it recorded it as a gap (its verdict and why), else ``None`` -- the same words
    the internal report prints beside it, so Results never reads such an answer as measured.
    ``external_context``: the pinned Design Research findings the modules were shown as context,
    as shown, from the same verified read as the modules' sources; ``None`` without a pin or
    before any module has an outcome."""
    try:
        scope.require(Permission.EDIT_STUDY)
        analysis = reconstruct_run(session, scope, store, run_id=run_id)
        gaps = research_question_gaps(ResearchRuns(session, scope).get(run_id)["metadata"])
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ReconstructionRefused as exc:
        if exc.reason == "run_not_found":
            raise _not_found("run") from exc
        raise HTTPException(
            status_code=409, detail={"code": exc.reason, "message": str(exc)}
        ) from exc
    return {
        "run_id": run_id,
        "complete": analysis.complete,
        "internal_only": True,
        "synthetic": any(o.record.labels.simulated_respondents for o in analysis.modules.values()),
        **_origin_flags(
            {origin_kind(o.record.labels.data_origin) for o in analysis.modules.values()}
        ),
        # The aggregate every module read is no longer 18.6.6's port (methodology-tab G3c).
        "aggregation_deviation": (
            dict(analysis.aggregation_deviation)
            if analysis.aggregation_deviation is not None
            else None
        ),
        "pending": {module.value: state for module, state in analysis.pending.items()},
        # The Design Research findings every module was shown as context, never as evidence
        # (evidence-integrity 7, artifact-analysis ANL5): exactly those, or None without a pin.
        "external_context": {
            "deep_research_run_id": analysis.external.deep_research_run_id,
            "items": [
                {"evidence_id": f.evidence_id, "claim": f.claim, "source": f.source}
                for f in analysis.external.findings
            ],
        }
        if analysis.external is not None
        else None,
        "modules": {
            module.value: {
                "outcome": outcome.outcome.value,
                "artifact_id": outcome.artifact_id,
                "summary": outcome.result.summary if outcome.result else None,
                "research_question_answers": [
                    {
                        "question": answer.question,
                        "answer": answer.answer,
                        "claim_ids": answer.claim_ids,
                        "gap": research_question_gap(gaps, answer.question),
                    }
                    for answer in outcome.result.research_question_answers
                ]
                if outcome.result
                else [],
                "key_findings": [
                    {"text": finding.text, "claim_ids": finding.claim_ids}
                    for finding in outcome.result.key_findings
                ]
                if outcome.result
                else [],
                "claims": [
                    {
                        "claim_id": claim.claim_id,
                        "evidence_ref": claim.row.evidence_ref,
                        "value": claim.value,
                        # The places the number was admitted at, as the aggregate stored it.
                        "decimals": claim.row.decimals,
                        "indicative": claim.indicative,
                        "data_origin": claim.row.data_origin.value
                        if claim.row.data_origin
                        else None,
                    }
                    for claim in outcome.result.claims
                ]
                if outcome.result
                else [],
                "violations": [
                    {
                        "code": violation.code.value,
                        "subject": violation.subject,
                        "detail": violation.detail,
                    }
                    for violation in outcome.violations
                ],
            }
            for module, outcome in analysis.modules.items()
        },
    }


# The report is read only through the run that produced it.


def _report_for_run(
    run_id: str,
    scope: StudyContext,
    session: SessionDep,
    store: ArtifactStoreDep,
    *,
    node_key: str = "report",
    artifact_type: str = INTERNAL_REPORT_ARTIFACT_TYPE,
) -> tuple[dict[str, Any] | None, Artifact | None]:
    """Find only the report recorded by this Study's own research run."""
    try:
        scope.require(Permission.VIEW_RESULTS)
        scope.require(Permission.EDIT_STUDY)  # Internal draft, including its metadata.
        run = ResearchRuns(session, scope).get(run_id)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc

    step = next((s for s in run["steps"] if s["node_key"] == node_key), None)
    if step is None or step["status"] is not StepRunStatus.SUCCEEDED:
        return step, None
    artifact_id = (step.get("output") or {}).get("artifact_id")
    if not artifact_id:
        raise HTTPException(409, detail={"code": "report_artifact_missing"})
    try:
        artifact = research_artifacts(session, scope, store).get(str(artifact_id))
    except ArtifactNotFound as exc:
        raise HTTPException(409, detail={"code": "report_artifact_missing"}) from exc
    if (
        artifact.artifact_type != artifact_type
        or artifact.content_type != INTERNAL_REPORT_MEDIA_TYPE
        or artifact.stage_type != "REPORT"
        or artifact.status is not ArtifactStatus.VALID
        or artifact.metadata.get("run_id") != run_id
        or artifact.metadata.get("report_kind") != "internal"
    ):
        raise HTTPException(409, detail={"code": "report_artifact_invalid"})
    return step, artifact


def _report_pdf(
    step: dict[str, Any] | None, report: Artifact | None, run_id: str, repo: ArtifactRepository
) -> tuple[Artifact | None, dict[str, Any] | None]:
    """:func:`step_pdf` for a download: a PDF the step said it made but cannot be served is
    409, never another file."""
    pdf, said, why = step_pdf(step, report, run_id, repo)
    if why == "pdf_missing":
        raise HTTPException(409, detail={"code": "report_artifact_missing"})
    if why is not None:
        raise HTTPException(409, detail={"code": "report_artifact_invalid"})
    return pdf, said


@router.get(
    "/research/runs/{run_id}/report",
    response_model=dict[str, Any],
    summary="Status and provenance of a run's internal report",
)
def run_report(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> dict[str, Any]:
    step, artifact = _report_for_run(run_id, scope, session, store)
    if step is None:
        return {"run_id": run_id, "state": "NOT_IN_RUN", "internal_only": True}
    if artifact is None:
        attempts = step.get("attempts") or []
        error = (attempts[-1].get("error") or {}) if attempts else {}
        return {
            "run_id": run_id,
            "state": step["status"].value,
            "internal_only": True,
            "reason": error.get("reason"),
        }
    mark = _mark(artifact, scope, session, store)
    pdf = _base_pdf(step, artifact, mark, run_id, scope, session, store)[1]
    return {
        "run_id": run_id,
        "state": "READY",
        "internal_only": True,
        **_review_fields(artifact, mark),
        **_approval_fields(artifact, scope, session, store),
        "artifact_id": artifact.artifact_id,
        "sha256": artifact.sha256,
        "size_bytes": artifact.size_bytes,
        "synthetic": bool(artifact.metadata.get("synthetic")),
        **_origin_flags({_artifact_origin_kind(artifact.metadata)}),
        "pdf": pdf,
        # Whether approving this draft now gives its approved version a PDF too: the page
        # promises one exactly then (D2, review 4).
        "approval_renders_pdf": approval_renders_pdf(
            scope, artifact, mark, pdf_ready=pdf is not None and pdf.get("state") == PdfState.READY
        ),
    }


def _base_pdf(
    step: dict[str, Any] | None,
    report: Artifact,
    mark: ReviewMark,
    run_id: str,
    scope: StudyContext,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> tuple[Artifact | None, dict[str, Any] | None]:
    """The run's own report's PDF -- the one its report step rendered, else one a person asked
    for since (``report_pdf``, research-integrity-report review: a step that rendered none, or
    failed to, left no way to get one) -- and its state; the PDF only when it is ready.

    Once the version is approved (D2) its PDF is the rendering of its approved export: for a
    stamped export only the rendering asked for it, never the step's (which renders the draft).
    A version stored before the stamp layout exports its stored bytes, so the step's PDF, or one
    asked for while it was a draft, renders exactly that export and stays its PDF
    (``report_export.exports_stamped``; cross-review interactions#4)."""
    if exports_stamped(report, mark):
        approved = variant_pdf(
            session, scope, store, docx=report, run_id=run_id, deep_research_run_id=None
        )
        return approved.artifact, approved.to_json()
    own, said, why = step_pdf(step, report, run_id, research_artifacts(session, scope, store))
    if why is not None:
        # The step's PDF is gone, corrupt or not this report's: never offered, asked for anew,
        # and said as what it is (review 2: corruption read as a different report's rendering).
        said = {"state": "INVALID", "reason": why}
    if own is not None:
        return own, {
            "state": "READY",
            "artifact_id": own.artifact_id,
            "size_bytes": own.size_bytes,
            "askable": False,
        }
    asked = variant_pdf(
        session, scope, store, docx=report, run_id=run_id, deep_research_run_id=None
    )
    if asked.state is not PdfState.NOT_REQUESTED:
        # A rendering a person asked for since: its state is the PDF's now.
        return asked.artifact, asked.to_json()
    if said is None:
        # The step rendered none (the converter was off) and nobody has asked since.
        return None, {
            "state": PdfState.NOT_REQUESTED.value,
            "reason": asked.reason,
            "askable": asked.askable,
        }
    return None, {
        "state": str(said.get("state") or "FAILED"),
        "reason": said.get("reason"),
        "askable": asked.askable,
    }


def _unrecorded(exc: ReviewUnrecorded) -> HTTPException:
    return HTTPException(
        409,
        detail={
            "code": "report_review_unrecorded",
            "message": "The report is marked approved and the approval ledger has no record of it.",
        },
    )


def _mark(
    artifact: Artifact, scope: StudyContext, session: SessionDep, store: ArtifactStoreDep
) -> ReviewMark:
    """The version's review, from the ledger; an approval without its row is 409, never a
    guess (``report_export.review_mark``)."""
    try:
        return review_mark(research_artifacts(session, scope, store), artifact)
    except ReviewUnrecorded as exc:
        raise _unrecorded(exc) from exc


def _export(
    artifact: Artifact,
    scope: StudyContext,
    session: SessionDep,
    store: ArtifactStoreDep,
    *,
    data: bytes | None = None,
) -> Export:
    """The file a DOCX download of ``artifact`` is: the stored draft, or the approved version
    stamped in its footers (D2). ``data``: its bytes, when the caller has just read them."""
    try:
        return export_docx(research_artifacts(session, scope, store), artifact, data=data)
    except ReviewUnrecorded as exc:
        raise _unrecorded(exc) from exc
    except (IntegrityError, ObjectNotFound) as exc:
        raise artifact_corrupt(session) from exc


def _review_fields(artifact: Artifact, mark: ReviewMark) -> dict[str, Any]:
    """A version's review as a status says it: its state, the day it was approved, and whether
    its file states it (``stamped``: an approved export says SCHVÁLENO in its footers; false
    for a version stored before that layout, or whose bytes the stamp refused when it was
    stored, whose file keeps its draft footer). Read from the record its writer made after
    trying the stamp (``report_export.review_stamp_record``), so it is what the export does."""
    return {
        "review_state": mark.state.value,
        "approved_on": mark.approved_on.isoformat() if mark.approved_on else None,
        "stamped": stampable(artifact),
    }


def _approval_fields(
    artifact: Artifact, scope: StudyContext, session: SessionDep, store: ArtifactStoreDep
) -> dict[str, Any]:
    """Who approved a version and when, from its ledger row (report-delivery RD2): ``approval``
    is null for a draft. ``by_you``: the asker is the approver. An approval without its row is
    409, never a draft (``report_export.review_mark``)."""
    if not artifact.is_approved:
        return {"approval": None}
    record = research_artifacts(session, scope, store).approval_record(artifact.artifact_id)
    if record is None:
        raise _unrecorded(ReviewUnrecorded(artifact.artifact_id))
    return {
        "approval": {
            "approved_at": record.decided_at.isoformat(),
            "approver_name": record.approver_name,
            "by_you": record.approver_user_id == scope.actor_id,
            "self_approved": record.self_approved,
            "self_approval_allowed": record.self_approval_allowed,
            "self_approval_source": record.self_approval_source,
            "note": record.note,
        }
    }


def _report_filename(
    study_id: str, run_id: str, variant: str, mark: ReviewMark, ext: str, *, stamped: bool
) -> str:
    """``AIA-<study>-<run>-<variant>-<version>-<review>.<ext>``: the file names the version it
    is and its review as the file itself states it -- ``koncept`` for a draft, ``schvaleno``
    for an approved version whose footers say SCHVÁLENO (``stamped``: the export, or the PDF
    rendered from it, was stamped), and ``schvaleno-v-aia`` for one approved in AIA whose file
    keeps the draft footer it was stored with (cross-review interactions#9: named
    ``schvaleno`` while every footer said KONCEPT, contradicting itself outside AIA)."""
    if mark.state is not ReviewState.APPROVED:
        state = "koncept"
    else:
        state = "schvaleno" if stamped else "schvaleno-v-aia"
    return f"AIA-{study_id}-{run_id}-{variant}-{mark.artifact_id}-{state}.{ext}"


def _review_headers(mark: ReviewMark, filename: str) -> dict[str, str]:
    return {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
        # The stored version these bytes are (or render), for its review and approval (B2, D2):
        # its id and SHA-256, and its review as the file states it.
        "X-AIA-Artifact-Id": mark.artifact_id,
        "X-AIA-Artifact-Sha256": mark.sha256,
        "X-AIA-Review-State": mark.state.value,
    }


@router.get(
    "/research/runs/{run_id}/report/pdf/download",
    summary="Download the run's internal report as PDF (a rendering of the stored DOCX)",
)
def download_run_report_pdf(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> Response:
    try:
        scope.require(Permission.EXPORT_DELIVERABLE)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    step, report = _report_for_run(run_id, scope, session, store)
    if report is None:
        raise _not_found("report_pdf")
    mark = _mark(report, scope, session, store)
    pdf, state = _base_pdf(step, report, mark, run_id, scope, session, store)
    if pdf is None:
        if state is not None and state.get("state") == PdfState.INVALID.value:
            # Never another document's bytes, and never a bare "not found" for one.
            raise HTTPException(409, detail={"code": "report_artifact_invalid"})
        raise _not_found("report_pdf")
    try:
        data = research_artifacts(session, scope, store).read(pdf.artifact_id)
    except (IntegrityError, ObjectNotFound) as exc:
        raise artifact_corrupt(session) from exc
    return Response(
        content=data,
        media_type=PDF_MEDIA_TYPE,
        headers=_review_headers(
            mark,
            _report_filename(
                scope.study_id,
                run_id,
                "zakladni",
                mark,
                "pdf",
                stamped=pdf.metadata.get("stamped") is True,
            ),
        ),
    )


@router.post(
    "/research/runs/{run_id}/report/pdf",
    response_model=dict[str, Any],
    summary="Ask for the PDF of the run's own report: a rendering of its stored DOCX",
)
def ask_run_report_pdf(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> dict[str, Any]:
    """When the report step rendered no PDF, or one that failed or became invalid, a new
    rendering of exactly its stored DOCX (``report_pdf``); a ready PDF is left as it is. On a
    Study that starts no work nothing is asked, and the status says why."""
    step, report = _report_for_run(run_id, scope, session, store)
    if report is None:
        raise _not_found("report")
    mark = _mark(report, scope, session, store)
    own, _state = _base_pdf(step, report, mark, run_id, scope, session, store)
    if own is None:
        try:
            request_pdf(
                session, scope, store, docx=report, run_id=run_id, deep_research_run_id=None
            )
        except ScopeDenied as exc:
            raise _refused(exc) from exc
    return run_report(run_id, scope, session, store)


@router.get(
    "/research/runs/{run_id}/report/download",
    summary="Download the run's internal AIA DOCX draft",
)
def download_run_report(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> Response:
    try:
        scope.require(Permission.EXPORT_DELIVERABLE)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    _step, artifact = _report_for_run(run_id, scope, session, store)
    if artifact is None:
        raise _not_found("report")
    exported = _export(artifact, scope, session, store)
    return Response(
        content=exported.data,
        media_type=INTERNAL_REPORT_MEDIA_TYPE,
        # The same headers as its PDF: the page checks the draft it downloaded is the one it
        # approves (research-integrity-report 3).
        headers=_review_headers(
            exported.mark,
            _report_filename(
                scope.study_id, run_id, "zakladni", exported.mark, "docx", stamped=exported.stamped
            ),
        ),
    )


@router.get(
    "/research/runs/{run_id}/report/document",
    response_model=dict[str, Any],
    summary="The run's internal draft as its stored document model",
)
def run_report_document(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> dict[str, Any]:
    """The document the run's internal DOCX was rendered from (report-delivery RD5a): its
    sections and blocks by their stored ids, and the ledger of every ref it cites with the text
    the DOCX prints. Read only through the run, beside the DOCX it names; the review is the
    DOCX's, because the DOCX is what a person approves.

    409 ``report_document_not_stored`` for a report composed before the document was stored
    (its DOCX still downloads); 409 ``report_artifact_invalid`` for a document that is not the
    one beside this run's DOCX."""
    step, report = _report_for_run(run_id, scope, session, store)
    if step is None or report is None:
        raise _not_found("report")
    said = (step.get("output") or {}).get("document")
    if not isinstance(said, dict) or not said.get("artifact_id"):
        raise HTTPException(409, detail={"code": "report_document_not_stored"})
    repo = research_artifacts(session, scope, store)
    try:
        model = repo.get(str(said["artifact_id"]))
    except ArtifactNotFound as exc:
        raise HTTPException(409, detail={"code": "report_artifact_missing"}) from exc
    if (
        model.artifact_type != INTERNAL_REPORT_DOCUMENT_ARTIFACT_TYPE
        or model.content_type != DOCUMENT_MODEL_MEDIA_TYPE
        or model.status is not ArtifactStatus.VALID
        or model.sha256 != said.get("sha256")
        or model.metadata.get("run_id") != run_id
        or model.metadata.get("docx_artifact_id") != report.artifact_id
        or model.metadata.get("docx_sha256") != report.sha256
    ):
        raise HTTPException(409, detail={"code": "report_artifact_invalid"})
    try:
        document = read_document_payload(repo.read(model.artifact_id))
    except (IntegrityError, ObjectNotFound) as exc:
        raise artifact_corrupt(session) from exc
    except DocumentModelInvalid as exc:
        raise HTTPException(409, detail={"code": "report_artifact_invalid"}) from exc
    mark = _mark(report, scope, session, store)
    return {
        "run_id": run_id,
        "artifact_id": model.artifact_id,
        "sha256": model.sha256,
        "report_artifact_id": report.artifact_id,
        "report_sha256": report.sha256,
        **_review_fields(report, mark),
        **_approval_fields(report, scope, session, store),
        "document": document,
    }


# The experimental Sociomapping's internal draft, read only through the run that produced it.


DeepResearchRunIdQuery = Annotated[str, Query(max_length=64, pattern=r"^RUN-[0-9a-f]{1,32}$")]
_CONTEXT_REFUSALS = (
    ReportCompositionRefused,
    ReconstructionRefused,
    ReportInvalid,
    BundleNotReady,
    LineageChanged,
    RunNotGoverned,
    RunSpecCorrupt,
    ArtifactNotFound,
    ValueError,
)


class ReportVariantPdfResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: PdfState
    artifact_id: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    #: Why a FAILED or INVALID PDF is not there (``pdf_disabled``, ``pdf_conversion_failed``,
    #: ``pdf_corrupt`` …), or why none was asked for (``study_closed``).
    reason: str | None = None
    #: Whether asking now (``POST …/pdf``) starts a rendering: the page offers it exactly then.
    askable: bool = False


class ReportVariantResponse(BaseModel):
    """The report of a run with one chosen literature review (research-integrity-report 3):
    its stored draft and the PDF rendered from exactly that draft."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    deep_research_run_id: str
    state: VariantState
    artifact_id: str | None = None
    sha256: str | None = None
    review_state: Literal["DRAFT_UNAPPROVED", "APPROVED_INTERNAL"] | None = None
    #: The Prague day the draft was approved (D2); null while it is a draft.
    approved_on: date | None = None
    #: Whether its file states its review: approved, its DOCX and PDF say SCHVÁLENO in their
    #: footers; false for a draft stored before that layout (or whose bytes the stamp refused),
    #: which keeps its draft footer and downloads as "…-schvaleno-v-aia" once approved.
    stamped: bool | None = None
    internal_only: bool = True
    pdf: ReportVariantPdfResponse | None = None
    #: Whether approving the draft now gives its approved version a PDF too: approving asks for
    #: one and this draft's own PDF was rendered here. The page promises a PDF exactly then.
    approval_renders_pdf: bool = False
    #: The composition contract the draft was stored under, and whether it is today's: an
    #: earlier one stays downloadable and approvable, and preparing composes it anew.
    contract: str | None = None
    contract_current: bool | None = None


def _variant_response(
    run_id: str, deep_research_run_id: str, status_: VariantStatus
) -> ReportVariantResponse:
    docx, mark = status_.docx, status_.mark
    if docx is None or mark is None:
        return ReportVariantResponse(
            run_id=run_id, deep_research_run_id=deep_research_run_id, state=status_.state
        )
    return ReportVariantResponse(
        run_id=run_id,
        deep_research_run_id=deep_research_run_id,
        state=status_.state,
        artifact_id=docx.artifact_id,
        sha256=docx.sha256,
        review_state=mark.state.value,
        approved_on=mark.approved_on,
        stamped=stampable(docx),
        pdf=ReportVariantPdfResponse.model_validate(status_.pdf.to_json()) if status_.pdf else None,
        approval_renders_pdf=status_.approval_renders_pdf,
        contract=docx.metadata.get("report_contract"),
        contract_current=status_.contract_current,
    )


def _variant(
    run_id: str,
    deep_research_run_id: str,
    scope: StudyContext,
    session: SessionDep,
    store: ArtifactStoreDep,
    *,
    export: bool = False,
) -> VariantStatus:
    """The variant as prepared, read only: composes nothing, enqueues nothing (a download is
    not a state change, research-journey.md:317-322)."""
    try:
        scope.require(Permission.EDIT_STUDY)
        if export:
            scope.require(Permission.EXPORT_DELIVERABLE)
        return variant_status(
            session, scope, store, run_id=run_id, deep_research_run_id=deep_research_run_id
        )
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc
    except ReviewUnrecorded as exc:
        raise _unrecorded(exc) from exc


def _not_prepared() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "context_report_not_prepared",
            "message": "Prepare the report with this review first (POST …/report/context).",
        },
    )


@router.post(
    "/research/runs/{run_id}/report/context",
    response_model=ReportVariantResponse,
    summary="Prepare the report with a chosen literature review: its draft and its PDF",
    responses={409: {"model": ErrorResponse}},
)
def prepare_contextual_report(
    run_id: RunIdPath,
    deep_research_run_id: DeepResearchRunIdQuery,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
    settings: SettingsDep,
) -> ReportVariantResponse:
    """Store the variant's draft once (refused by name when the review does not interpret this
    run, or the run's analysis is incomplete) and ask the worker for its PDF. Idempotent: the
    same run and review are one draft; preparing again after the PDF failed asks again. Once a
    person approved a version it is the report (D2): preparing composes nothing over it, and
    only asks for its PDF where that is missing."""
    try:
        scope.require(Permission.EDIT_STUDY)
        prepared = prepared_context_report(
            session, scope, store, run_id=run_id, deep_research_run_id=deep_research_run_id
        )
        if prepared is not None and prepared.is_approved:
            artifact = prepared
        else:
            artifact, _data = stored_contextual_report(
                session,
                scope,
                store,
                run_id=run_id,
                deep_research_run_id=deep_research_run_id,
                build=settings.build.sha or "",
            )
        # On a Study that starts no work the draft is still stored; its PDF says why it waits.
        request_pdf(
            session,
            scope,
            store,
            docx=artifact,
            run_id=run_id,
            deep_research_run_id=deep_research_run_id,
        )
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except (ResearchRunNotFound, DeepResearchRunNotFound) as exc:
        raise _not_found("run") from exc
    except (IntegrityError, ObjectNotFound) as exc:
        raise artifact_corrupt(session) from exc
    except ReviewUnrecorded as exc:
        raise _unrecorded(exc) from exc
    except _CONTEXT_REFUSALS as exc:
        # A refusal that names why carries it, so the screen can say it in words (PC17): the
        # analysis an earlier harness built (fingerprint_mismatch) is repaired on Průběh.
        reason = getattr(exc, "reason", None)
        raise HTTPException(
            409,
            detail={
                "code": "context_report_refused",
                "message": str(exc),
                "details": {"reason": reason} if isinstance(reason, str) else {},
            },
        ) from exc
    return _variant_response(
        run_id,
        deep_research_run_id,
        _variant(run_id, deep_research_run_id, scope, session, store),
    )


@router.post(
    "/research/runs/{run_id}/report/context/pdf",
    response_model=ReportVariantResponse,
    summary="Ask again for the PDF of the prepared report with a chosen review",
    responses={409: {"model": ErrorResponse}},
)
def ask_contextual_report_pdf(
    run_id: RunIdPath,
    deep_research_run_id: DeepResearchRunIdQuery,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> ReportVariantResponse:
    """A new rendering of the draft already prepared, after its PDF failed or became invalid;
    composes nothing, so a deploy that changed what composition accepts never strands a stored
    draft without its PDF. 409 ``context_report_not_prepared`` before it is prepared."""
    found = _variant(run_id, deep_research_run_id, scope, session, store)
    if found.docx is None:
        raise _not_prepared()
    try:
        request_pdf(
            session,
            scope,
            store,
            docx=found.docx,
            run_id=run_id,
            deep_research_run_id=deep_research_run_id,
        )
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ReviewUnrecorded as exc:
        raise _unrecorded(exc) from exc
    return _variant_response(
        run_id,
        deep_research_run_id,
        _variant(run_id, deep_research_run_id, scope, session, store),
    )


@router.get(
    "/research/runs/{run_id}/report/context",
    response_model=ReportVariantResponse,
    summary="Where the report with a chosen literature review stands, composing nothing",
)
def contextual_report_status(
    run_id: RunIdPath,
    deep_research_run_id: DeepResearchRunIdQuery,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> ReportVariantResponse:
    return _variant_response(
        run_id,
        deep_research_run_id,
        _variant(run_id, deep_research_run_id, scope, session, store),
    )


@router.get(
    "/research/runs/{run_id}/report/context/document",
    response_model=dict[str, Any],
    summary="The prepared report with a chosen literature review as its stored document model",
    responses={409: {"model": ErrorResponse}},
)
def contextual_report_document_route(
    run_id: RunIdPath,
    deep_research_run_id: DeepResearchRunIdQuery,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> dict[str, Any]:
    """The document the variant's prepared DOCX was rendered from, in the shape of the internal
    draft's (``…/report/document``), so the pane reads and approves exactly that version
    (artifact-report RPT3a). Composes nothing. 409 ``context_report_not_prepared`` before it is
    prepared; 409 ``report_document_not_stored`` for a version stored before its document was
    (its DOCX still downloads)."""
    found = _variant(run_id, deep_research_run_id, scope, session, store)
    if found.docx is None:
        raise _not_prepared()
    repo = research_artifacts(session, scope, store)
    model = contextual_report_document(repo, found.docx)
    if model is None:
        raise HTTPException(409, detail={"code": "report_document_not_stored"})
    try:
        document = read_document_payload(repo.read(model.artifact_id))
    except (IntegrityError, ObjectNotFound) as exc:
        raise artifact_corrupt(session) from exc
    except DocumentModelInvalid as exc:
        raise HTTPException(409, detail={"code": "report_artifact_invalid"}) from exc
    docx = found.docx
    return {
        "run_id": run_id,
        "artifact_id": model.artifact_id,
        "sha256": model.sha256,
        "report_artifact_id": docx.artifact_id,
        "report_sha256": docx.sha256,
        **_review_fields(docx, _mark(docx, scope, session, store)),
        **_approval_fields(docx, scope, session, store),
        "document": document,
    }


@router.get(
    "/research/runs/{run_id}/report/context/download",
    response_class=Response,
    summary="The prepared report with a chosen literature review, as DOCX",
    responses={409: {"model": ErrorResponse}},
)
def download_contextual_report(
    run_id: RunIdPath,
    deep_research_run_id: DeepResearchRunIdQuery,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> Response:
    """The draft the variant was prepared as -- the one its PDF renders and its approval
    names. 409 ``context_report_not_prepared`` before it is prepared."""
    found = _variant(run_id, deep_research_run_id, scope, session, store, export=True)
    if found.docx is None:
        raise _not_prepared()
    exported = _export(found.docx, scope, session, store)
    return Response(
        content=exported.data,
        media_type=INTERNAL_REPORT_MEDIA_TYPE,
        headers=_review_headers(
            exported.mark,
            _report_filename(
                scope.study_id,
                run_id,
                deep_research_run_id,
                exported.mark,
                "docx",
                stamped=exported.stamped,
            ),
        ),
    )


@router.get(
    "/research/runs/{run_id}/report/context/pdf/download",
    response_class=Response,
    summary="The PDF of the prepared report with a chosen literature review: its draft, rendered",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def download_contextual_report_pdf(
    run_id: RunIdPath,
    deep_research_run_id: DeepResearchRunIdQuery,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> Response:
    found = _variant(run_id, deep_research_run_id, scope, session, store, export=True)
    if found.docx is None or found.mark is None:
        raise _not_prepared()
    # The variant's PDF is the one its review allows: an approved version's rendering of its
    # export (report_variants.variant_pdf), never a draft's when the two differ.
    if found.pdf is None or found.pdf.artifact is None:
        raise _not_found("report_pdf")
    try:
        data = research_artifacts(session, scope, store).read(found.pdf.artifact.artifact_id)
    except (IntegrityError, ObjectNotFound) as exc:
        raise artifact_corrupt(session) from exc
    return Response(
        content=data,
        media_type=PDF_MEDIA_TYPE,
        headers=_review_headers(
            found.mark,
            _report_filename(
                scope.study_id,
                run_id,
                deep_research_run_id,
                found.mark,
                "pdf",
                stamped=found.pdf.artifact.metadata.get("stamped") is True,
            ),
        ),
    )


def _stored_client[T](
    run_id: str,
    scope: StudyContext,
    session: SessionDep,
    store: ArtifactStoreDep,
    read: Callable[[], T],
) -> T:
    """``read`` of the run's client report as stored (composed and stored as a draft first when
    none is), its refusals in the API's words: 409 ``client_report_refused`` for a run that has
    none."""
    try:
        return read()
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc
    except (IntegrityError, ObjectNotFound) as exc:
        raise artifact_corrupt(session) from exc
    except ClientReportRefused as exc:
        raise HTTPException(
            409,
            detail={
                "code": "client_report_refused",
                "message": str(exc),
                "details": {"reason": exc.reason},
            },
        ) from exc
    except (ReportCompositionRefused, ReportInvalid, ArtifactNotFound) as exc:
        raise HTTPException(
            409,
            detail={
                "code": "client_report_refused",
                "message": str(exc),
                "details": {"reason": "composition_refused"},
            },
        ) from exc


@router.get(
    "/research/runs/{run_id}/report/client/download",
    response_class=Response,
    summary="The run's client report (modelled data, labelled): its approved version, else a draft",
    responses={409: {"model": ErrorResponse}},
)
def download_client_report(
    run_id: RunIdPath,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
    settings: SettingsDep,
) -> Response:
    """Complete-study-report B5c: only a run whose respondents were modelled from the
    population has one; any other is refused by name (409 ``client_report_refused``)."""
    artifact, data = _stored_client(
        run_id,
        scope,
        session,
        store,
        lambda: stored_client_report(
            session, scope, store, run_id=run_id, build=settings.build.sha or ""
        ),
    )
    # The bytes it just read (or stored) are the version's: never read twice per download.
    exported = _export(artifact, scope, session, store, data=data)
    return Response(
        content=exported.data,
        media_type=INTERNAL_REPORT_MEDIA_TYPE,
        headers=_review_headers(
            exported.mark,
            _report_filename(
                scope.study_id, run_id, "klient", exported.mark, "docx", stamped=exported.stamped
            ),
        ),
    )


@router.post(
    "/research/runs/{run_id}/report/client/prepare",
    response_model=dict[str, Any],
    summary="Prepare the run's client report to be read in AIA, without a download",
    responses={409: {"model": ErrorResponse}},
)
def prepare_client_report_route(
    run_id: RunIdPath,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    """The client report composed and stored as its download would store it, answered as its
    document model (report-delivery RD3): a person reads the draft in AIA before approving it,
    and no file leaves. The approved version once there is one; nothing is composed then."""
    report, model = _stored_client(
        run_id,
        scope,
        session,
        store,
        lambda: prepare_client_report(
            session, scope, store, run_id=run_id, build=settings.build.sha or ""
        ),
    )
    return _client_document_body(run_id, report, model, scope, session, store)


class ReportApprovalRequest(BaseModel):
    """Which stored report of the run a person approves, and why."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(pattern=r"^ART-[0-9a-f]{16}$")
    note: str = Field(default="", max_length=2000)


@router.get(
    "/research/runs/{run_id}/report/client/document",
    response_model=dict[str, Any],
    summary="The run's stored client report as its document model",
)
def client_report_document_route(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> dict[str, Any]:
    """The document the run's stored client report was rendered from (report-delivery RD5a):
    the approved version's when a person approved one, else the newest stored draft's. It
    composes nothing; a client report is prepared by ``…/client/prepare`` or its download. 404
    while none is stored;
    409 ``report_document_not_stored`` for a version stored before RD5a."""
    try:
        found = client_report_document(session, scope, store, run_id=run_id)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc
    if found is None:
        raise _not_found("report")
    return _client_document_body(run_id, *found, scope, session, store)


def _client_document_body(
    run_id: str,
    report: Artifact,
    model: Artifact | None,
    scope: StudyContext,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> dict[str, Any]:
    """A stored client report's document model as the document route answers it."""
    if model is None:
        raise HTTPException(409, detail={"code": "report_document_not_stored"})
    if model.content_type != DOCUMENT_MODEL_MEDIA_TYPE or (
        model.artifact_type != CLIENT_REPORT_DOCUMENT_ARTIFACT_TYPE
    ):  # pragma: no cover - client_report_document selects by type
        raise HTTPException(409, detail={"code": "report_artifact_invalid"})
    repo = research_artifacts(session, scope, store)
    try:
        document = read_document_payload(repo.read(model.artifact_id))
    except (IntegrityError, ObjectNotFound) as exc:
        raise artifact_corrupt(session) from exc
    except DocumentModelInvalid as exc:
        raise HTTPException(409, detail={"code": "report_artifact_invalid"}) from exc
    mark = _mark(report, scope, session, store)
    return {
        "run_id": run_id,
        "artifact_id": model.artifact_id,
        "sha256": model.sha256,
        "report_artifact_id": report.artifact_id,
        "report_sha256": report.sha256,
        **_review_fields(report, mark),
        **_approval_fields(report, scope, session, store),
        "document": document,
    }


@router.post(
    "/research/runs/{run_id}/report/approve",
    response_model=dict[str, Any],
    summary="Approve a stored report of the run (internal, with literature or client; recorded)",
    responses={403: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def approve_run_report(
    run_id: RunIdPath,
    body: ReportApprovalRequest,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> dict[str, Any]:
    try:
        artifact = approve_report(
            session, scope, store, run_id=run_id, artifact_id=body.artifact_id, note=body.note
        )
    except SeparationOfDutiesViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": exc.reason,
                "message": "Someone other than the report's producer must approve it.",
            },
        ) from exc
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc
    except ArtifactNotFound as exc:
        raise _not_found("report") from exc
    except ClientGateRefused as exc:
        raise HTTPException(
            409,
            detail={
                "code": "client_gate_refused",
                "message": "Klientskou zprávu nelze schválit: " + str(exc),
                "details": {"refusals": [r.to_json() for r in exc.refusals]},
            },
        ) from exc
    except (IntegrityError, ObjectNotFound) as exc:
        raise artifact_corrupt(session) from exc
    except DocumentModelInvalid as exc:
        raise HTTPException(409, detail={"code": "report_artifact_invalid"}) from exc
    except ReportNotApprovable as exc:
        raise HTTPException(
            409,
            detail={
                "code": "report_not_approvable",
                "message": "The artifact is not a valid stored report of this run.",
            },
        ) from exc
    # Which report was approved, by kind: the client report is no internal document (G66).
    kind = REPORT_KINDS[artifact.artifact_type]
    return {
        "run_id": run_id,
        "artifact_id": artifact.artifact_id,
        "artifact_type": artifact.artifact_type,
        **_review_fields(artifact, _mark(artifact, scope, session, store)),
        **_approval_fields(artifact, scope, session, store),
        "report_kind": kind,
        "internal_only": kind not in CLIENT_REPORT_KINDS,
    }


def _sociomapping_report(
    run_id: str, scope: StudyContext, session: SessionDep, store: ArtifactStoreDep
) -> tuple[dict[str, Any] | None, Artifact | None]:
    step, artifact = _report_for_run(
        run_id,
        scope,
        session,
        store,
        node_key="sociomapping_report",
        artifact_type=SOCIOMAPPING_REPORT_ARTIFACT_TYPE,
    )
    if artifact is not None and (
        artifact.metadata.get("method_status") != "EXPERIMENTAL_AIA"
        or artifact.metadata.get("client_facing") is not False
    ):
        raise HTTPException(409, detail={"code": "report_artifact_invalid"})
    return step, artifact


@router.get(
    "/research/runs/{run_id}/sociomapping/report",
    response_model=dict[str, Any],
    summary="Status and provenance of a run's experimental Sociomapping draft",
)
def run_sociomapping_report(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> dict[str, Any]:
    step, artifact = _sociomapping_report(run_id, scope, session, store)
    base = {"run_id": run_id, "internal_only": True, "method_status": "EXPERIMENTAL_AIA"}
    if step is None:
        return {**base, "state": "NOT_IN_RUN"}
    if artifact is None:
        attempts = step.get("attempts") or []
        error = (attempts[-1].get("error") or {}) if attempts else {}
        return {**base, "state": step["status"].value, "reason": error.get("reason")}
    return {
        **base,
        "state": "READY",
        "review_state": "APPROVED_INTERNAL" if artifact.is_approved else "DRAFT_UNAPPROVED",
        "artifact_id": artifact.artifact_id,
        "sha256": artifact.sha256,
        "size_bytes": artifact.size_bytes,
        "synthetic": bool(artifact.metadata.get("synthetic")),
        **_origin_flags({_artifact_origin_kind(artifact.metadata)}),
    }


@router.get(
    "/research/runs/{run_id}/sociomapping/report/download",
    summary="Download the run's experimental Sociomapping DOCX draft (internal)",
)
def download_sociomapping_report(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> Response:
    try:
        scope.require(Permission.EXPORT_DELIVERABLE)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    _step, artifact = _sociomapping_report(run_id, scope, session, store)
    if artifact is None:
        raise _not_found("report")
    try:
        data = research_artifacts(session, scope, store).read(artifact.artifact_id)
    except (IntegrityError, ObjectNotFound) as exc:
        raise artifact_corrupt(session) from exc
    filename = f"AIA-{scope.study_id}-sociomapping-experimental-draft.docx"
    return Response(
        content=data,
        media_type=INTERNAL_REPORT_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


# Native agent jobs: the API enqueues and reads; the worker owns every model call.
class AgentJobStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    design_revision_id: str = Field(max_length=64, pattern=r"^REV-[0-9a-f]{1,32}$")
    action: ResearchAction
    instruction: str = Field(default="", max_length=8000)
    #: A stored prompt version to run instead of the active one, to test a draft (ADR 0020).
    #: Organization administrators only, and only on a client the deployment lists as
    #: fictional (409 ``prompt_test_requires_fictional_client`` otherwise); the job records
    #: which prompt it ran.
    prompt_version: int | None = Field(default=None, ge=1)
    #: The ceiling a person confirmed when the study's confirmation threshold asked (409
    #: ``cost_confirmation_required``, lead-orchestration LO15). Never the ceiling itself: the
    #: server works that out from the design job's reservation.
    confirm_cost_usd: float | None = Field(default=None, ge=0, le=1_000_000, allow_inf_nan=False)


class AgentProposalAccept(BaseModel):
    """An accept names the Design Revision the proposal was made on and the working revision the
    person has (ADR 0026 decision 6); both are required, so no client is served the old way."""

    model_config = ConfigDict(extra="forbid")
    expected_revision_id: str = Field(max_length=64, pattern=r"^REV-[0-9a-f]{1,32}$")
    expected_workspace_revision: int = Field(ge=1)


class AgentProposalAccepted(BaseModel):
    """What an accept wrote in its one transaction: the Design Revision and the working copy."""

    model_config = ConfigDict(extra="forbid")
    design_revision_id: str
    design_revision: DesignRevisionResponse
    #: False when the merged design was identical to the newest revision.
    created: bool
    workspace_revision: int
    workspace_revision_id: str


class AgentJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    design_revision_id: str
    action: str
    status: str
    is_terminal: bool
    needs_attention: bool
    context_sha256: str
    harness_version: str
    #: The prompt this job was queued with (``1`` or ``e<n>``) and whether the code's
    #: wording or an administrator's edit ran. ``None`` for a job queued before ADR 0020.
    prompt_version: str | None = None
    prompt_origin: str | None = None
    created_at: datetime | None
    steps: list[ResearchStepResponse]
    actual_cost_usd: float | None
    #: Where its design proposal stands (ADR 0026 decision 8): pending, accepted, dismissed or
    #: superseded; null for advice or a job without a proposal.
    proposal_state: Literal["pending", "accepted", "dismissed", "superseded"] | None = None
    #: The job this one rebuilt, which it supersedes; null for a job a person asked first.
    rebuild_of: str | None = None


class AgentProposalRebuild(BaseModel):
    """A rebuild runs on the Study's newest Design Revision, which the browser just submitted."""

    model_config = ConfigDict(extra="forbid")
    design_revision_id: str = Field(max_length=64, pattern=r"^REV-[0-9a-f]{1,32}$")
    #: As a start's: the new job is paid work and meets the threshold (LO15).
    confirm_cost_usd: float | None = Field(default=None, ge=0, le=1_000_000, allow_inf_nan=False)


def _agent_response(
    run: dict[str, Any], scope: StudyContext, state: str | None = None
) -> AgentJobResponse:
    meta = run["metadata"]
    return AgentJobResponse(
        run_id=run["run_id"],
        design_revision_id=meta["design_revision_id"],
        action=meta["action"],
        status=run["status"].value,
        is_terminal=run["status"].is_terminal,
        needs_attention=run["status"].needs_attention,
        context_sha256=meta["context_sha256"],
        harness_version=meta["harness_version"],
        prompt_version=meta.get("prompt_version"),
        prompt_origin=meta.get("prompt_origin"),
        created_at=run.get("created_at"),
        steps=[_step(s) for s in run["steps"]],
        actual_cost_usd=sum(
            float(a.get("actual_cost_usd") or 0) for s in run["steps"] for a in s["attempts"]
        )
        if scope.has(Permission.VIEW_COSTS)
        else None,
        proposal_state=state,
        rebuild_of=meta.get("rebuild_of"),
    )


def _agent_with_state(
    jobs: ResearchAgentJobs, run_id: str, scope: StudyContext
) -> AgentJobResponse:
    run = jobs.get(run_id)
    state = jobs.proposal_states([run])[run_id]
    return _agent_response(run, scope, state.value if state else None)


def stale_proposal(exc: StaleProposal) -> HTTPException:
    """409 ``stale_proposal``: why (``design_moved``, ``unknown_baseline``, ``items_changed``,
    ``lineage_changed``) and, for an edit, each item it touched that the proposal changes."""
    return HTTPException(
        status_code=409,
        detail={"code": "stale_proposal", "message": str(exc), "details": exc.details()},
    )


def workspace_stale(exc: WorkspaceConflict) -> HTTPException:
    """409 with the working copy's reason (``stale_revision``) and its current revision."""
    return HTTPException(
        status_code=409,
        detail={
            "code": exc.reason,
            "message": str(exc),
            "details": {"current_revision": exc.current_revision},
        },
    )


@contextmanager
def _agent_errors(session: SessionDep) -> Iterator[None]:
    try:
        yield
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except (ResearchRunNotFound, DesignRevisionNotFound) as exc:
        raise _not_found("agent_job") from exc
    except StaleProposal as exc:
        raise stale_proposal(exc) from exc
    except WorkspaceConflict as exc:
        raise workspace_stale(exc) from exc
    except DesignRejected as exc:
        raise HTTPException(
            status_code=409, detail={"code": exc.reason, "message": str(exc)}
        ) from exc
    except RuntimeParkNotResumable as exc:
        raise _runtime_park_refused(exc) from exc
    except (BudgetWaitNotLiftable, BudgetNotRaised) as exc:
        raise _budget_lift_refused(exc) from exc
    except (CostConfirmationRequired, CostCeilingUnknown) as exc:
        raise _cost_refused(exc) from exc
    except (IntegrityError, ObjectNotFound) as exc:
        # The proposal's bytes failed verification on read: keep its CORRUPT mark.
        raise artifact_corrupt(session) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_agent_input", "message": str(exc)}
        ) from exc


@router.post(
    "/research/agent-jobs",
    response_model=AgentJobResponse,
    status_code=201,
    responses={
        409: {
            "model": ErrorResponse,
            "description": "The confirmation threshold asks (cost_confirmation_required), or "
            "the job's ceiling is unknown (cost_ceiling_unknown)",
        },
    },
)
def start_agent_job(
    body: AgentJobStart,
    scope: StudyScopeDep,
    session: SessionDep,
    settings: SettingsDep,
    response: Response,
) -> AgentJobResponse:
    with _agent_errors(session):
        # The deployment's fictional-client list decides where a draft prompt may be tried.
        # What one job can cost at most, for the study's confirmation threshold (LO15).
        jobs = ResearchAgentJobs(
            session,
            scope,
            draft_client_ids=settings.fictional_client_ids,
            reservation_usd=settings.ai_research_reservation_usd,
        )
        started = jobs.start(
            design_revision_id=body.design_revision_id,
            action=body.action,
            instruction=body.instruction,
            prompt_version=body.prompt_version,
            confirm_cost_usd=body.confirm_cost_usd,
        )
        if not started.created:
            response.status_code = 200
        return _agent_response(jobs.get(started.run_id), scope)


@router.get("/research/agent-jobs", response_model=list[AgentJobResponse])
def list_agent_jobs(
    scope: StudyScopeDep, session: SessionDep, pending: Annotated[bool, Query()] = False
) -> list[AgentJobResponse]:
    """The Study's agent jobs, newest first, each with its proposal's state (ADR 0026 d8).
    ``pending=true``: only the proposals a person has still to decide."""
    with _agent_errors(session):
        jobs = ResearchAgentJobs(session, scope)
        runs = [jobs.get(r["run_id"]) for r in jobs.jobs()]
        states = jobs.proposal_states(runs)
        listed = [_agent_response(r, scope, (s := states[r["run_id"]]) and s.value) for r in runs]
        return [j for j in listed if j.proposal_state == "pending"] if pending else listed


@router.get("/research/agent-jobs/{run_id}", response_model=AgentJobResponse)
def read_agent_job(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep
) -> AgentJobResponse:
    with _agent_errors(session):
        return _agent_with_state(ResearchAgentJobs(session, scope), run_id, scope)


@router.get("/research/agent-jobs/{run_id}/events", response_model=list[RunEventResponse])
def agent_job_events(
    run_id: RunIdPath,
    scope: StudyScopeDep,
    session: SessionDep,
    since: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> list[RunEventResponse]:
    """The job's events after a cursor: what its step reported while it ran."""
    with _agent_errors(session):
        events = ResearchAgentJobs(session, scope).events(run_id, since=since, limit=limit)
    return [_event(e) for e in events]


@router.post("/research/agent-jobs/{run_id}/cancel", response_model=AgentJobResponse)
def cancel_agent_job(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep
) -> AgentJobResponse:
    with _agent_errors(session):
        jobs = ResearchAgentJobs(session, scope)
        jobs.cancel(run_id)
        return _agent_response(jobs.get(run_id), scope)


@router.post("/research/agent-jobs/{run_id}/resume", response_model=AgentJobResponse)
def resume_agent_job(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep
) -> AgentJobResponse:
    """Retry only a frozen, unbilled job parked before its runtime was available."""
    with _agent_errors(session):
        jobs = ResearchAgentJobs(session, scope)
        jobs.resume_runtime_park(run_id)
        return _agent_response(jobs.get(run_id), scope)


@router.post(
    "/research/agent-jobs/{run_id}/budget",
    response_model=AgentJobResponse,
    summary="Raise the study's budget and let an agent job that stopped at the cap go on",
    responses={
        409: {"model": ErrorResponse, "description": "The job is not waiting for budget"},
        422: {"model": ErrorResponse, "description": "The budget offered is below the current one"},
    },
)
def lift_agent_job_budget(
    run_id: RunIdPath, body: BudgetLiftRequest, scope: StudyScopeDep, session: SessionDep
) -> AgentJobResponse:
    """Needs ``APPROVE_BUDGET`` and ``MANAGE_STUDY_BUDGET`` on an open Study, as a research
    run's lift: the person names the budget the study is raised to, the job is offered to a
    worker again, and the decision is written to the approval ledger. Asking the same action
    again returns this job, so without this a job stopped at the cap ends only by a cancel."""
    with _agent_errors(session):
        jobs = ResearchAgentJobs(session, scope)
        return _agent_response(
            jobs.lift_budget_wait(run_id, budget_usd=body.budget_usd, note=body.note), scope
        )


@router.get("/research/agent-jobs/{run_id}/result", response_model=dict[str, Any])
def read_agent_result(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> dict[str, Any]:
    with _agent_errors(session):
        result = ResearchAgentJobs(session, scope).result(run_id, store=store)
        if not scope.has(Permission.VIEW_COSTS):
            result["provenance"].pop("cost_usd", None)
        return result


@router.post(
    "/research/agent-jobs/{run_id}/dismiss",
    response_model=AgentJobResponse,
    responses={409: {"model": ErrorResponse, "description": "Not a proposal, or accepted"}},
)
def dismiss_agent_result(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep
) -> AgentJobResponse:
    """A person sets the proposal aside: an approval-ledger row (``decision = "dismiss"``),
    nothing written to the design (ADR 0026 decision 8). Needs ``APPROVE_GATE``."""
    with _agent_errors(session):
        jobs = ResearchAgentJobs(session, scope)
        jobs.dismiss(run_id)
        return _agent_with_state(jobs, run_id, scope)


@router.post(
    "/research/agent-jobs/{run_id}/rebuild",
    response_model=AgentJobResponse,
    status_code=201,
    responses={
        409: {
            "model": ErrorResponse,
            "description": "Advice, not the newest design, or the confirmation threshold asks",
        }
    },
)
def rebuild_agent_result(
    run_id: RunIdPath,
    body: AgentProposalRebuild,
    scope: StudyScopeDep,
    session: SessionDep,
    settings: SettingsDep,
    response: Response,
) -> AgentJobResponse:
    """Ask the same action and instruction again on the Study's newest Design Revision: a new
    job, ``rebuild_of`` the old one, which it supersedes (ADR 0026 decision 5). Accepts
    nothing; the old proposal stays readable. The new job meets the study's confirmation
    threshold as a start does (LO15)."""
    with _agent_errors(session):
        jobs = ResearchAgentJobs(
            session, scope, reservation_usd=settings.ai_research_reservation_usd
        )
        started = jobs.rebuild(
            run_id,
            design_revision_id=body.design_revision_id,
            confirm_cost_usd=body.confirm_cost_usd,
        )
        if not started.created:
            response.status_code = 200
        return _agent_with_state(jobs, started.run_id, scope)


@router.post(
    "/research/agent-jobs/{run_id}/accept",
    response_model=AgentProposalAccepted,
    responses={
        409: {"model": ErrorResponse, "description": "stale_proposal or stale_revision"},
    },
)
def accept_agent_result(
    run_id: RunIdPath,
    body: AgentProposalAccept,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> AgentProposalAccepted:
    """Accept a proposal in one transaction (ADR 0026 decision 6): merged into the working copy,
    submitted as the Design Revision, recorded in the ledger. The browser then reloads the
    working copy; it writes nothing back itself."""
    with _agent_errors(session):
        accepted = ResearchAgentJobs(session, scope).accept(
            run_id,
            store=store,
            expected_revision_id=body.expected_revision_id,
            expected_workspace_revision=body.expected_workspace_revision,
        )
        return AgentProposalAccepted(
            design_revision_id=accepted.revision.revision_id,
            design_revision=_revision(accepted.revision, created=accepted.created),
            created=accepted.created,
            workspace_revision=accepted.working.revision,
            workspace_revision_id=accepted.working.revision_id,
        )
