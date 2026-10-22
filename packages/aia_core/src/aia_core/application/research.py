"""Research execution: start, retry, cancel and read the runs of a research Study.

ADR 0016. ``execute(study_context, stage, input_revision)`` is
:func:`start_research_run`: a run of the ``research`` workflow pinned to one
Design Revision of the Study in scope. A run is found only through the Study's
own design project; a run id of another Study -- or another client -- is
:class:`ResearchRunNotFound`, whatever its id says.

The fieldwork source is chosen by the composition (the API's settings), never
by the request, and recorded on the run so the worker executes only a source it
provides.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..domain.ai_contracts import canonical_json
from ..domain.ai_respondent import fieldwork_seed
from ..domain.analysis.native import research_questions_of
from ..domain.analysis.steps import analysis_step_inputs
from ..domain.answerability import (
    ANSWERABILITY_RULES,
    Acknowledgement,
    AcknowledgementRefused,
    Answerability,
    answerability,
    answerability_note,
    decided_trace,
    read_answerability_note,
    with_answerability,
)
from ..domain.deep_research.workflow import DEEP_RESEARCH
from ..domain.design import DESIGN_PROJECT_OWNER, DesignRejected
from ..domain.design_items import ItemKey
from ..domain.evidence import ClaimSurface
from ..domain.evidence.support import AIA_SUPPORT_V1, SupportSpec
from ..domain.fieldwork import FieldworkSource, PersonaSource, persona_source_of
from ..domain.methodology.pins import (
    UNIT_AGGREGATION_PIN,
    aggregation_pin_for,
    read_aggregation_pin,
    read_readiness_pin,
    read_response_pin,
    read_support_pin,
    readiness_spec_for,
    response_spec_for,
    sociomap_methods_for,
    support_spec_for,
)
from ..domain.money import ThresholdVerdict, threshold_verdict
from ..domain.panel_persona import persona_allowlist
from ..domain.panel_source import panel_filters, with_panel_refusal
from ..domain.pipeline import StageImpact, changed_fields, fingerprint, stage_impacts
from ..domain.population import (
    CZ_LIVE,
    CZ_SYNTHETIC_V17,
    PopulationBinding,
    PopulationBindingMissing,
    PopulationImportContract,
    VersionOwner,
)
from ..domain.prompts import PromptPin
from ..domain.question_outlook import QuestionOutlook, question_outlook
from ..domain.report.review import ReviewMark
from ..domain.research import phase_of, retryable
from ..domain.research_agents import (
    DESIGN_ACTIONS,
    HARNESS_VERSION,
    ProposalState,
    ResearchAction,
    context_snapshot,
    prompt_for,
    proposal_documents,
    proposal_state,
    snapshot_hash,
)
from ..domain.research_design import (
    Readiness,
    ReadinessSpec,
    ResearchSpecification,
    prepare,
    routed_questions,
    selection_receipt,
)
from ..domain.research_sociomap import (
    SociomapMethod,
    default_methods,
    is_retired,
    methods_fingerprint,
    read_methods,
    side_tables_of,
    without_reference,
)
from ..domain.research_trace import (
    ResearchTrace,
    comparisons_of,
    trace_research,
    with_research_trace,
)
from ..domain.respondent_behavior import AIA_RESPONSE_V1, ResponseProcessSpec
from ..domain.run_cost import CeilingUnknown, RunCostCeiling, run_cost_ceiling
from ..domain.scope import OrganizationRole, Permission, StudyContext
from ..domain.spend_attribution import ActivitySpend, run_spend
from ..domain.support_forecast import SupportForecast, forecast_support, with_support_forecast
from ..domain.workflow import RUNTIME_UNAVAILABLE_REASON, StepRunStatus, WorkflowRunStatus
from ..domain.workflow_templates import REPORT_PDF, RESEARCH, RESEARCH_AGENT
from ..infrastructure.artifact_repository import Artifact, ArtifactRepository
from ..infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from ..infrastructure.methodology_repository import methodology_in_force_for_study
from ..infrastructure.prompt_repository import PromptRefused, PromptResolver
from ..infrastructure.researcher_spend_repository import run_spend_facts
from ..infrastructure.scope_repository import ScopeRepository
from ..infrastructure.storage import ArtifactStore
from ..infrastructure.study_design_repository import DesignRevisionNotFound, StudyDesignRepository
from ..infrastructure.study_workspace_repository import StudyWorkspaceRepository
from ..infrastructure.workflow_repository import (
    BudgetWaitNotLiftable,
    RuntimeParkNotResumable,
    WorkflowNotFound,
    WorkflowRepository,
)
from .analysis import MAX_REPAIRS
from .audience_preview import PanelDraw, PanelSampler
from .population import child_binding, live_binding
from .proposal_accept import (
    AcceptedProposal,
    StaleProposal,
    accept_into_working_copy,
    proposal_baseline,
)
from .report_export import exports_stamped
from .workflows import StartedRun, start_workflow

__all__ = [
    "BudgetNotRaised",
    "CostCeilingUnknown",
    "CostConfirmationRequired",
    "DesignNotReady",
    "FrozenDataset",
    "PanelPopulationMissing",
    "ResearchAgentJobs",
    "ResearchQuestionsUnanswerable",
    "ResearchRunNotFound",
    "ResearchRunNotRetryable",
    "ResearchRunOnRetiredMethod",
    "ResearchRuns",
    "ResearchStepNotFound",
    "RunOutlook",
    "RunReservations",
    "WorkingImpact",
    "WorkingRevisionNotFound",
    "readiness_in_force",
    "report_pdf_key",
    "research_artifacts",
]


def research_artifacts(
    session: Session, scope: StudyContext, store: ArtifactStore
) -> ArtifactRepository:
    """The artifacts of the Study's research: those of its owned design project.

    The one way to reach them. An ordinary :class:`ArtifactRepository` cannot see
    an owned project's artifacts, so a research artifact is never served by the
    generic project routes, only by the run that produced it (ADR 0016).
    """
    return ArtifactRepository(session, scope, store, owner=DESIGN_PROJECT_OWNER)


def report_pdf_key(
    run_id: str,
    deep_research_run_id: str | None,
    docx_artifact_id: str,
    *,
    approved: bool = False,
) -> str:
    """The idempotency key of the first PDF job for one stored report DOCX of one run and
    review (plan research-integrity-report chunk 3); a later job for the same DOCX, asked after
    one failed, adds ``:again-<n>``, so every job of the DOCX shares this prefix.

    The approved version's PDF renders its stamped export (D2) under a key of its own:
    ``report_pdf:approved:…``, which no draft key's prefix matches (a lookup is a literal
    ``startswith``, ``WorkflowRepository.list_runs``), so a draft PDF is never found as the
    approved one. Draft keys are as they always were, so every stored draft PDF stays found."""
    kind = f"{REPORT_PDF}:approved" if approved else REPORT_PDF
    return f"{kind}:{run_id}:{deep_research_run_id or 'base'}:{docx_artifact_id}"


class DesignNotReady(Exception):
    """The Design Revision does not compile, or fails a readiness check."""

    def __init__(self, readiness: Readiness) -> None:
        super().__init__("the design is not ready to run")
        self.readiness = readiness


class ResearchQuestionsUnanswerable(Exception):
    """The design is technically runnable, but the run cannot answer every research question
    it states, and no person has acknowledged these exact gaps (``domain.answerability``)."""

    def __init__(self, answer: Answerability) -> None:
        super().__init__(
            f"{len(answer.gaps)} research question gap(s) need a person's acknowledgement"
        )
        self.answerability = answer


class PanelPopulationMissing(Exception):
    """A panel run asked for, and no population established to draw its respondents from."""


class ResearchRunNotFound(LookupError):
    """No research run with this id in the Study in scope."""


class ResearchRunNotRetryable(Exception):
    """Only a failed or cancelled run may be retried."""

    def __init__(self, status: WorkflowRunStatus) -> None:
        super().__init__(f"a {status.value} run cannot be retried")
        self.status = status


class ResearchRunOnRetiredMethod(Exception):
    """The run's object map is the earlier default's ``aia-sociomap-3`` (or it pinned the
    reference map alone): it is never computed again. A new run over the same Design Revision
    pins ``aia-sociomap-5``."""

    def __init__(self, run: Mapping[str, Any], methods: list[str]) -> None:
        run_id = str(run["run_id"])
        design_revision_id = str(run["metadata"]["design_revision_id"])
        super().__init__(
            f"run {run_id} pinned {', '.join(methods)}, which no new run computes; start a new "
            f"run over {design_revision_id} instead"
        )
        self.run_id = run_id
        self.design_revision_id = design_revision_id
        self.methods = methods
        #: The start a new run takes to begin as this one did: the same revision, respondents,
        #: population and research-question decision (a start's own fields, as the API reads them).
        self.new_run = _new_run_start(run)


class ResearchStepNotFound(LookupError):
    """The run has no step with this node key."""


class BudgetNotRaised(ValueError):
    """The budget offered is below the study's current one: that would lower the cap."""

    def __init__(self, *, offered: float, current: float) -> None:
        super().__init__(f"budget {offered:.2f} is below the current {current:.2f}")
        self.offered = offered
        self.current = current


class CostConfirmationRequired(Exception):
    """The run's cost ceiling reaches the study's limit and the person has not confirmed it."""

    def __init__(self, *, ceiling_usd: float, limit_usd: float) -> None:
        super().__init__(
            f"a run that can cost up to {ceiling_usd:.2f} needs confirming "
            f"(the study's limit is {limit_usd:.2f})"
        )
        self.ceiling_usd = ceiling_usd
        self.limit_usd = limit_usd


class CostCeilingUnknown(Exception):
    """The study has a limit and the run's ceiling cannot be worked out: it is not let by."""

    def __init__(
        self, reason: CeilingUnknown, *, limit_usd: float, kinds: tuple[str, ...] = ()
    ) -> None:
        detail = f": {', '.join(kinds)}" if kinds else ""
        super().__init__(f"the run's cost ceiling is unknown ({reason.value}{detail})")
        self.reason = reason
        self.limit_usd = limit_usd
        #: The kinds of call whose price is missing, when the ceiling names them.
        self.kinds = kinds


def lift_study_budget_waits(
    session: Session,
    scope: StudyContext,
    run_id: str,
    steps: Sequence[Mapping[str, Any]],
    *,
    budget_usd: float,
    note: str = "",
) -> None:
    """Raise the study's budget to ``budget_usd`` and let each of ``steps`` waiting for it go on.

    The one lift every kind of a Study's work shares: a research run's step, an agent job, a
    Deep Research run. A step whose reservation would pass the study's budget stops in
    ``AWAITING_BUDGET`` without spending an attempt, and only a person lifts it (plan 5b.1).
    Needs ``APPROVE_BUDGET`` and ``MANAGE_STUDY_BUDGET`` on an open Study, which a worker's
    scope does not hold. ``budget_usd`` equal to the current budget lifts the wait without
    changing it (it was raised by hand); below it is refused: this lifts a cap, it does not
    lower one. One lift is one decision: every waiting step of ``steps`` goes on under one
    lock and one approval row in the ledger (CR-3), so a run whose eight analysis modules
    stopped at the cap needs one lift, not eight. ``steps`` are the steps of run ``run_id``,
    whose lock is taken before the study's (the order a completing step takes them in); the
    study's budget is then read locked, so two lifts at once never compare against the same
    old budget and a raise is never overwritten by a smaller one decided earlier.

    Checked before anything is written, so a refused lift changes nothing, not even the
    budget; the budget change and the resumes share the caller's transaction. The callers
    find ``steps`` through their own run, so a step of another Study never reaches here.
    """
    scope.require(Permission.APPROVE_BUDGET)
    scope.require(Permission.MANAGE_STUDY_BUDGET)
    scope.require_open_study()
    waiting = [s for s in steps if s["status"] is StepRunStatus.AWAITING_BUDGET]
    if not waiting:
        raise BudgetWaitNotLiftable("only a step waiting for budget can be lifted")
    scopes = ScopeRepository(session)
    workflows = WorkflowRepository(session, scope)
    # The run, then the study: the order a completing step takes them in (run, then the payer
    # it charges), so the two never wait on each other.
    workflows.lock_run(run_id)
    # Locked before it is compared: two lifts at once must not compare against the same old
    # budget, the later one writing a lower cap over the earlier one's raise.
    current = float(scopes.get_study(scope, for_update=True).budget_usd)
    if budget_usd < current:
        raise BudgetNotRaised(offered=budget_usd, current=current)
    if budget_usd > current:
        scopes.set_study_budget(scope, budget_usd)
    workflows.resume_budget_waits(
        [str(step["step_id"]) for step in waiting],
        note=note,
        budget_before=current,
        budget_after=budget_usd,
    )


def resume_runtime_parks(
    session: Session, scope: StudyContext, steps: Sequence[Mapping[str, Any]]
) -> int:
    """Offer every step of ``steps`` parked for the AI runtime to a worker again; how many.

    A step whose runtime is not deployed, or whose gateway refused it before any call, parks
    ``WAITING_PROVIDER`` / ``ai_runtime_unavailable``, and no timer resumes it
    (``domain.workflow.resume_due``): only a person's action does, after the runtime is on.
    Each step goes through ``WorkflowRepository.resume_runtime_park``, which refuses a step
    that dispatched a paid call, was asked to cancel or has no attempt left, so this can never
    repeat a call that may have been billed. A step resumed while the runtime is still off
    parks again at its next attempt, without spending one. Needs ``RUN_WORKFLOW`` on an open
    Study. Refused (``RuntimeParkNotResumable``) when nothing in ``steps`` waits for the
    runtime; one step refused refuses the whole action, in the caller's transaction.
    """
    scope.require(Permission.RUN_WORKFLOW)
    scope.require_open_study()
    parked = [
        s
        for s in steps
        if s["status"] is StepRunStatus.WAITING_PROVIDER
        and s["waiting_reason"] == RUNTIME_UNAVAILABLE_REASON
    ]
    if not parked:
        raise RuntimeParkNotResumable("nothing here waits for the AI runtime")
    workflows = WorkflowRepository(session, scope)
    return sum(workflows.resume_runtime_park(str(step["step_id"])) for step in parked)


@dataclass(frozen=True, slots=True)
class FrozenDataset:
    """What an analysis retry runs over: another run's dataset, and what it asks again."""

    run_id: str
    artifact_id: str
    sha256: str
    analysis_round: int
    #: The modules the retry asks again: the most its analysis can cost.
    retried: tuple[str, ...]
    #: Modules whose step will ask a model: the retried ones, and any completed one whose
    #: stored harness or prompt is not today's (its reuse key moved).
    modules_asked: int
    #: The original's specification, by artifact id and SHA-256: the retry's compile step
    #: takes it as stored, never compiling the revision again under a later compiler (whose
    #: specification would move every completed module's reuse key, unpaid in the ceiling).
    #: ``None`` only for a caller that names none; :func:`retry_failed_modules` always does.
    specification_artifact_id: str | None = None
    specification_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.analysis_round < 1:
            raise ValueError("an analysis retry is round 1 or later")

    def step_input(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "artifact_id": self.artifact_id, "sha256": self.sha256}

    def note(self) -> dict[str, Any]:
        return {**self.step_input(), "round": self.analysis_round, "modules": list(self.retried)}

    def specification_input(self) -> dict[str, Any] | None:
        """The compile step's ``frozen_specification``; ``None`` when none is named."""
        if self.specification_artifact_id is None or self.specification_sha256 is None:
            return None
        return {
            "run_id": self.run_id,
            "artifact_id": self.specification_artifact_id,
            "sha256": self.specification_sha256,
        }


class WorkingRevisionNotFound(LookupError):
    """The Study's working project never wrote this revision, or it holds no content."""


@dataclass(frozen=True, slots=True)
class WorkingImpact:
    """A working revision beside a Design Revision: the top-level fields that differ and every
    pipeline stage's impact, in pipeline order (``domain.pipeline.stage_impacts``)."""

    working_revision: int
    design_revision_id: str
    design_revision: int
    changed: tuple[str, ...]
    stages: dict[str, StageImpact]


@dataclass(frozen=True, slots=True)
class RunOutlook:
    """What a run of a revision would be, before it starts: its specification (``None``: it
    does not compile), its readiness, every item's verdict (empty when it does not
    compile) and each stated research question traced to its measures."""

    spec: ResearchSpecification | None
    readiness: Readiness
    questions: tuple[QuestionOutlook, ...]
    #: Each stated research question traced to its measures; ``None`` when it does not compile.
    trace: ResearchTrace | None
    #: Whether the run can answer every stated research question, and the gaps a start must
    #: have acknowledged when it cannot; ``None`` when it does not compile.
    answerability: Answerability | None = None
    #: The sample a panel run would draw (or the sampler's refusal); ``None`` when none was drawn.
    panel: PanelDraw | None = None
    #: The support forecast readiness carries; ``None`` when this fieldwork forecasts none.
    forecast: SupportForecast | None = None


@dataclass(frozen=True, slots=True)
class RunReservations:
    """What the worker reserves per model request, as the API reads it from the same settings.

    ``None`` is not zero: the ceiling that needs a missing one is unknown.
    """

    fieldwork_usd: float | None
    analysis_usd: float | None


def _population_note(binding: PopulationBinding, *, read_by_fieldwork: bool) -> dict[str, Any]:
    """What the run says about its population: the version it names, and whether fieldwork
    draws its respondents from it.

    The binding row is the record (``WorkflowRepository.population_binding``); this is how
    a run reads without a second query. ``read_by_fieldwork`` is whether the run pinned the
    panel persona source; a fictional-roster run records its population and reads nothing.
    """
    return {
        "population_id": binding.population_id,
        "version_id": binding.version_id,
        "version_label": binding.version_label,
        "read_by_fieldwork": read_by_fieldwork,
    }


def readiness_in_force(
    session: Session, scope: StudyContext
) -> tuple[ReadinessSpec, dict[str, Any] | None]:
    """The readiness limits in force for the Study, and the stored version they come from
    (``None``: nothing stored, so the code's preset ``aia-readiness-1``).

    The one authority for a valid n (plan ``run-qc-and-checkpoint`` RQC9): what a run start
    checks and pins, what the API's ``GET …/research/limits`` answers the web, and what a
    Research Lead turn is frozen with and its ``set_n`` accepted under. Read through the
    Study's resolved scope; only its organization's methodology rows are read."""
    in_force = methodology_in_force_for_study(session, scope, "readiness")
    if in_force.version is None:
        return readiness_spec_for(None), None
    return readiness_spec_for(in_force.version.payload), {
        "module": "readiness",
        "version": in_force.version.version_number,
        "name": in_force.version.name,
        "payload_sha256": in_force.version.payload_sha256,
    }


@dataclass(frozen=True, slots=True)
class ResearchRuns:
    """The research runs of the Study in scope. The caller owns the transaction."""

    session: Session
    scope: StudyContext
    #: The population a new run records (``_population_for``); the Czech LIVE in every
    #: composition, another only in tests over a fictional contract.
    population_contract: PopulationImportContract = CZ_SYNTHETIC_V17
    population_id: str = CZ_LIVE
    #: Draws a panel run's sample over the population above (run-qc-and-checkpoint RQC6b);
    #: ``None``: none composed, so a panel run's support forecast reads unknown.
    panel_sampler: PanelSampler | None = None
    #: ``AIA_ROUTING_ENABLED`` (off; working-copy-edit-ops WCE13 (d)): a valid display condition
    #: passes readiness and a new run pins it (``routing``), which its preflight reads. Off until
    #: fieldwork routes by it (run-qc-and-checkpoint RQC11).
    routing_enabled: bool = False

    def _panel_draw(self, spec: ResearchSpecification) -> PanelDraw | None:
        """The sample a panel run of ``spec`` would draw: the design's filters, its n and the
        seed fieldwork draws with (``fieldwork_seed``), over the population a new run records."""
        if self.panel_sampler is None or spec.n is None or spec.n < 1:
            return None
        return self.panel_sampler(panel_filters(spec), spec.n, fieldwork_seed(spec))

    def _designs(self) -> StudyDesignRepository:
        return StudyDesignRepository(self.session, self.scope)

    def _workflows(self) -> WorkflowRepository:
        return WorkflowRepository(self.session, self.scope)

    def _recorded_binding(self, run_id: str) -> PopulationBinding | None:
        try:
            return self._workflows().population_binding(run_id)
        except PopulationBindingMissing:
            return None

    def _population_for(
        self, key: str, retry_of: str | None, selected: PopulationBinding | None = None
    ) -> PopulationBinding | None:
        """The population a run records (owner, 2026-10-10: record LIVE, read nothing).

        A start that finds its run names the binding that run recorded, so it is returned
        as before -- a run made before LIVE existed, or before LIVE moved, keeps what it
        recorded. A retry keeps the original's, as it keeps its Sociomap methods. A new run
        records the child its study selected (``selected``, resolved by :meth:`_selected`)
        or LIVE as it stands, or nothing while LIVE is not established. Fieldwork reads it
        only when the run pinned the panel persona source.
        """
        existing = self._workflows().find_run_by_idempotency_key(key)
        if existing is not None:
            return self._recorded_binding(existing)
        if retry_of is not None:
            return self._recorded_binding(retry_of)
        if selected is not None:
            return selected
        return live_binding(
            self.session, contract=self.population_contract, population_id=self.population_id
        )

    def _selected(self, version_id: str | None) -> PopulationBinding | None:
        """The child a start selected, resolved for this study's client (P4e2), or ``None``."""
        if version_id is None:
            return None
        return child_binding(
            self.session,
            contract=self.population_contract,
            version_id=version_id,
            owner=VersionOwner(
                organization_id=self.scope.organization_id, client_id=self.scope.client_id
            ),
        )

    # -- start ------------------------------------------------------------------

    def spend_limit(self) -> float | None:
        """The study's limit above which starting a run asks for confirmation; ``None``: never."""
        return ScopeRepository(self.session).get_study(self.scope).spend_confirm_usd

    def cost_ceiling(
        self,
        spec: ResearchSpecification,
        *,
        fieldwork_source: FieldworkSource,
        analysis_enabled: bool,
        reservations: RunReservations | None,
        fieldwork_frozen: bool = False,
        analysis_modules: int | None = None,
    ) -> RunCostCeiling:
        """The most a run of ``spec`` can cost, from what the worker reserves per request."""
        reserved = reservations or RunReservations(None, None)
        return run_cost_ceiling(
            spec,
            fieldwork_source=fieldwork_source,
            fieldwork_reservation_usd=reserved.fieldwork_usd,
            analysis_enabled=analysis_enabled,
            analysis_reservation_usd=reserved.analysis_usd,
            analysis_calls_per_module=1 + MAX_REPAIRS,
            fieldwork_frozen=fieldwork_frozen,
            analysis_modules=analysis_modules,
        )

    def start(
        self,
        *,
        design_revision_id: str,
        fieldwork_source: FieldworkSource,
        retry_of: str | None = None,
        analysis_enabled: bool = False,
        external_context: bool = False,
        sociomapping_enabled: bool = False,
        reservations: RunReservations | None = None,
        confirm_cost_usd: float | None = None,
        sociomap_methods: Sequence[SociomapMethod] | None = None,
        support: SupportSpec | None = None,
        aggregation: Mapping[str, Any] | None = None,
        response: ResponseProcessSpec | None = None,
        readiness: ReadinessSpec | None = None,
        kept: Mapping[str, Any] | None = None,
        persona_source: PersonaSource = PersonaSource.FICTIONAL_ROSTER,
        population_version_id: str | None = None,
        frozen_dataset: FrozenDataset | None = None,
        acknowledge: Acknowledgement | None = None,
        inherited_acknowledgement: tuple[Acknowledgement, str, str | None] | None = None,
        require_answerability: bool = False,
        routing: bool | None = None,
        _probe: bool = False,
    ) -> StartedRun:
        """Run the research workflow over one Design Revision of the Study.

        A design can be runnable and still unable to answer what it asks
        (``domain.answerability``): a research question nothing measures, or only questions the
        run will not answer. A start that would create such a run is refused
        (:class:`ResearchQuestionsUnanswerable`) unless ``acknowledge`` names those exact gaps
        with a person's reason, or a retry inherits the acknowledgement its original recorded
        for the same gaps (``inherited_acknowledgement``: the acknowledgement, the original's
        run id and who gave it). The run records its answerability either way
        (``metadata.answerability``); a new acknowledgement is also written to the approval
        ledger. Like the cost gate, a start that finds its run asks nothing. The refusal ships
        behind ``require_answerability`` (the API's ``AIA_RESEARCH_ANSWERABILITY_GATE``): off,
        a run with gaps starts and records them unacknowledged, so its report still says so.

        ``external_context`` (the API's ``AIA_AI_ANALYSIS_EXTERNAL_CONTEXT``, off by default)
        pins, for a run with analysis, the Study's newest sealed Design Research bundle
        (``metadata.analysis_context``: the run, the artifact and its SHA-256): each module is
        shown its accepted findings as external context, never evidence (evidence-integrity 7).
        A retry keeps the original's pin, or its absence. Metadata only, never the run's key.

        ``frozen_dataset`` makes the run an analysis retry (:func:`retry_failed_modules`
        in ``application.analysis_results``, through :meth:`retry_analysis`): its fieldwork
        step takes that run's dataset by id and SHA-256 and asks nobody, and its analysis
        steps run in round ``frozen_dataset.analysis_round``. It requires ``retry_of``.

        The run pins who its AI respondents are (``persona_source``, plan
        ``panel-grounded-respondents`` 5a): the fieldwork step reads the pin, never a switch,
        and a retry keeps it. A panel run is its own identity (a start over a revision whose
        run is fictional makes a new run), needs the ``ai_runtime`` source, and is refused
        (:class:`PanelPopulationMissing`) when there is no population to draw from -- never
        started fictional instead.

        ``kept`` is a retry's: the stored-version records (``methodology``,
        ``support_methodology``, ``aggregation_methodology``, ``response_methodology``,
        ``readiness_methodology``) of the run it retries. A retry passes that run's pins
        explicitly, so they are not resolved from what is in force here; without these records
        the new run would say its stored versions were the code's (plan ``methodology-tab``
        Z1a). They are metadata only, never part of the run's key.

        The run records the population it names (``population_version_id``: a materialized
        child of the study's client, P4e2; LIVE when not given). A selected child is part of
        the run's identity, so the same revision over LIVE and over a child is two runs; a
        child that is not this client's raises
        :class:`~aia_core.domain.population.UnknownDatasetVersion`, as a scope miss does.

        The run pins whether fieldwork routes its display conditions (``routing``; the
        composition's ``routing_enabled`` when not given, a retry the original's): readiness
        passes a valid condition under it, and its preflight and fieldwork steps read the pin
        (fieldwork fails a routed run by name until it routes, RQC11). With no valid condition
        the pin changes nothing and is not recorded. It is not part of the run's key: without
        it a design with a valid condition never starts, so every run of such a revision is
        routed, and a start after the switch is turned off still finds its run.

        The run also pins its readiness limits (``readiness``; the organization's readiness
        version in force when not given, plan ``methodology-tab`` V1a): the start checks the
        design under them, and the run's compile and preflight steps read the pin. They decide
        whether a run may start, never what it computes, so they are not part of the run's
        identity: a start that finds the revision's run returns it with the limits it pinned.

        The run also pins its response process (``response``; the organization's response
        version in force when not given, plan ``methodology-tab`` R1b): AI fieldwork assigns
        styles, puts them into words and turns the model's probabilities into answers under
        it. Like the support rules, a stored version or a process the caller chooses over the
        unit's is part of the run's identity.

        The run also pins its aggregation (``aggregation``: the specification and the formulas
        it replaces; the organization's aggregation version in force when not given, plan
        ``methodology-tab`` G3a): the aggregate computes under it, and says when that is no
        longer 18.6.6's port. Like the support rules, a stored version or a pin the caller
        chooses over the unit's is part of the run's identity.

        The run also pins its support rules (``support``; the organization's support version
        in force when not given, plan ``methodology-tab`` G1c): the aggregate decides every
        cell's status by their ``results`` rule and analysis gates by their ``analysis`` rule.
        A stored version, or a set the caller chooses over the code's, is part of the run's
        identity, like the Sociomap's methods.

        The run pins its Sociomap methods here, each with its whole spec
        (``sociomap_methods``; :func:`~aia_core.domain.research_sociomap.default_methods`
        when not given): the ``sociomap`` step computes exactly those, whatever the
        module's preset becomes before it runs or is retried. The set is part of the run's
        identity, the default's included, so the same revision under two sets is two runs: a
        start over a revision whose run pinned an earlier default (``aia-sociomap-1`` with
        ``-3``) starts a new run on ``aia-sociomap-5`` rather than returning the old one. A run
        stored with the old default's bare key keeps it.

        Idempotent: the same revision starts one run, and so does retrying the
        same run -- a double submission gets the run that already exists. Needs
        ``RUN_WORKFLOW`` on an open Study. Raises
        :class:`~aia_core.infrastructure.study_design_repository.DesignRevisionNotFound`
        for a revision that is not this Study's.

        When the study has a spend limit (``Study.spend_confirm_usd``) and this would create
        a run, its cost ceiling is worked out here, never taken from the request. A ceiling
        at or above the limit needs ``confirm_cost_usd`` to cover it
        (:class:`CostConfirmationRequired` otherwise) and the yes is recorded in the approval
        ledger with the run. A ceiling that cannot be worked out is not let by
        (:class:`CostCeilingUnknown`). A start that finds its run already there spends
        nothing and asks nothing.
        """
        self.scope.require(Permission.RUN_WORKFLOW)
        self.scope.require_open_study()
        designs = self._designs()
        revision = designs.get(design_revision_id)
        # What the run will pin, resolved before the readiness checks: a pin the engine
        # cannot compute is refused before any run, and the checks read its pair n_min.
        methods, methodology = self._methods(sociomap_methods)
        support_spec, support_version = self._support(support)
        aggregation_pin, aggregation_version = self._aggregation(aggregation)
        response_spec, response_version = self._response(response)
        limits, readiness_version = self._readiness(readiness)
        content = designs.content(revision.revision_id)
        routing = self.routing_enabled if routing is None else routing
        _spec, checked = prepare(
            content,
            pair_n_min=side_tables_of(methods).n_min,
            limits=limits,
            routing=routing,
        )
        # Only a design with a valid condition is routed: elsewhere the pin changes nothing.
        routed = _spec is not None and bool(routed_questions(_spec, routing=routing))
        panel = persona_source is PersonaSource.PANEL
        # As readiness drew it: a new panel run over LIVE (a run over a selected child, or a
        # retry, which keeps the original's population, draws from one the sampler does not
        # read). A sample the sampler refuses is a failed check, never a run fieldwork refuses.
        drawn = (
            self._panel_draw(_spec)
            if panel
            and _spec is not None
            and fieldwork_source is FieldworkSource.AI_RUNTIME
            and population_version_id is None
            and retry_of is None
            else None
        )
        if drawn is not None and drawn.sampler_refused is not None:
            checked = with_panel_refusal(checked, drawn.sampler_refused, drawn.reasons)
        # A retry keeps the original's population and never re-chooses it.
        selected = self._selected(population_version_id if retry_of is None else None)
        project_id = designs.project_id()
        assert project_id is not None  # a revision exists, so its design project does
        pinned = [m.model_dump(mode="json") for m in methods]
        key = f"{RESEARCH}:{revision.revision_id}"
        if analysis_enabled:
            key += ":analysis"
        if sociomapping_enabled:
            key += ":sociomapping"
        if methodology is not None:
            # An edited methodology is new identity: the same revision under it is another
            # run, and its cost goes through the spend confirmation below like any new run.
            key += f":methodology:{methodology['payload_sha256'][:16]}"
        else:
            # The methods are identity, the default's too: a revision whose run pinned the old
            # default (keyed bare, as every start that took a default was) gets a new run on
            # the signed-off methodology, never the old run handed back as if it were one.
            key += f":sociomap:{methods_fingerprint(methods)[:16]}"
        if support_version is not None:
            key += f":support:{support_version['payload_sha256'][:16]}"
        elif support is not None and support_spec != AIA_SUPPORT_V1:
            key += f":support:{fingerprint(support_spec.model_dump(mode='json'))[:16]}"
        if aggregation_version is not None:
            key += f":aggregation:{aggregation_version['payload_sha256'][:16]}"
        elif aggregation is not None and aggregation_pin != UNIT_AGGREGATION_PIN:
            key += f":aggregation:{fingerprint(aggregation_pin)[:16]}"
        if response_version is not None:
            key += f":response:{response_version['payload_sha256'][:16]}"
        elif response is not None and response_spec != AIA_RESPONSE_V1:
            key += f":response:{fingerprint(response_spec.model_dump(mode='json'))[:16]}"
        if population_version_id is not None and retry_of is None:
            # A retry keeps the original's population; its key carries the original's id.
            key += f":population:{fingerprint(population_version_id)[:16]}"
        if panel and fieldwork_source is not FieldworkSource.AI_RUNTIME:
            raise ValueError("panel personas answer only through the ai_runtime source")
        if panel:
            key += ":personas:panel"
            # A panel run's personas read the study's selected dimensions as their topic
            # allowlist (5c): with any selected, it is its own run, never one made before.
            allowlist = persona_allowlist(_spec) if _spec is not None else ()
            if allowlist:
                key += f":persona-topics:{fingerprint(list(allowlist))[:16]}"
        if frozen_dataset is not None:
            if not retry_of or not analysis_enabled:
                raise ValueError("an analysis retry names the run it retries, with analysis on")
            key += f":analysis-retry:{retry_of}"
        elif retry_of:
            key += f":retry:{retry_of}"
        if _probe:
            raise _Probed(key)
        # The limits are not part of the key (they decide whether a run may start, not what
        # it computes): a start that finds its run returns it, whatever limits are in force
        # now. Only a run that would be created is held to them.
        if not checked.ready and self._workflows().find_run_by_idempotency_key(key) is None:
            raise DesignNotReady(checked)
        # A retry's pins came from stored versions resolved when its original started.
        held = dict(kept or {})
        methodology = methodology or held.get("methodology")
        support_version = support_version or held.get("support_methodology")
        aggregation_version = aggregation_version or held.get("aggregation_methodology")
        response_version = response_version or held.get("response_methodology")
        readiness_version = readiness_version or held.get("readiness_methodology")
        readiness_pin = limits.model_dump(mode="json")
        support_pin = support_spec.model_dump(mode="json")
        # Before the cost gate: a panel run with no population to draw from can never start,
        # so it is refused as that, never put to the person as a cost to confirm.
        population = self._population_for(key, retry_of, selected)
        if panel and population is None:
            raise PanelPopulationMissing(
                "the panel persona source draws from the run's population, and none is "
                "established; nothing was started"
            )
        response_pin = response_spec.model_dump(mode="json")
        exists = self._workflows().find_run_by_idempotency_key(key) is not None
        # A run that exists keeps what it pinned; only a new one looks for a bundle.
        context_pin = (
            held.get("analysis_context")
            if retry_of
            else (
                self.design_research_pin()
                if analysis_enabled and external_context and not exists
                else None
            )
        )
        answer_note: dict[str, Any] | None = None
        fresh_acknowledgement: Answerability | None = None
        if _spec is not None and not exists:
            # Under the support and aggregation this run pins, as readiness traced it.
            forecast: SupportForecast | None = None
            if fieldwork_source is FieldworkSource.AI_RUNTIME:
                _, slots = read_aggregation_pin(aggregation_pin)
                # As readiness forecast it, from the sample drawn above, so the gaps a person
                # acknowledged there are these; none drawn reads unknown, as before.
                forecast = forecast_support(
                    _spec,
                    support=support_spec,
                    persona_source=persona_source,
                    slots=slots,
                    sample=drawn.sample if drawn is not None else None,
                )
            items = question_outlook(_spec, forecast, routing=routing)
            trace = trace_research(
                _spec, research_questions_of(content), items, comparisons_of(content)
            )
            answer = answerability(trace, items, design_revision_id=revision.revision_id)
            if answer.capable:
                answer_note = answerability_note(trace, answer)
            elif acknowledge is not None and acknowledge.covers(answer):
                answer_note = answerability_note(
                    trace,
                    answer,
                    acknowledged_by=self.scope.actor_id,
                    acknowledgement=acknowledge,
                )
                fresh_acknowledgement = answer
            elif inherited_acknowledgement is not None and inherited_acknowledgement[0].covers(
                answer
            ):
                held_ack, original, by = inherited_acknowledgement
                answer_note = answerability_note(
                    trace,
                    answer,
                    acknowledged_by=by,
                    acknowledgement=held_ack,
                    inherited_from=original,
                )
            elif frozen_dataset is not None:
                # An analysis retry collects nothing and cannot change what the design measures:
                # never refused, and recorded as exempt -- never as "not enforced".
                answer_note = {**answerability_note(trace, answer), "exempt": "analysis_retry"}
            elif require_answerability:
                raise ResearchQuestionsUnanswerable(answer)
            else:
                answer_note = {**answerability_note(trace, answer), "enforced": False}
        confirmation: tuple[float, float] | None = None
        limit = self.spend_limit()
        if limit is not None and self._workflows().find_run_by_idempotency_key(key) is None:
            assert _spec is not None  # a ready design compiles
            ceiling = self.cost_ceiling(
                _spec,
                fieldwork_source=fieldwork_source,
                analysis_enabled=analysis_enabled,
                reservations=reservations,
                fieldwork_frozen=frozen_dataset is not None,
                analysis_modules=frozen_dataset.modules_asked if frozen_dataset else None,
            )
            # The confirmation threshold's one rule (domain/money.py; ADR 0019 gate 2).
            verdict = threshold_verdict(ceiling.total_usd, limit, confirm_cost_usd)
            if verdict is ThresholdVerdict.CEILING_UNKNOWN:
                assert ceiling.unknown is not None
                raise CostCeilingUnknown(ceiling.unknown, limit_usd=limit)
            assert ceiling.total_usd is not None
            if verdict is ThresholdVerdict.ASK:
                raise CostConfirmationRequired(ceiling_usd=ceiling.total_usd, limit_usd=limit)
            if verdict is ThresholdVerdict.CONFIRMED:
                confirmation = (ceiling.total_usd, limit)
        started = start_workflow(
            self.session,
            self.scope,
            project_id=project_id,
            workflow_type=RESEARCH,
            revision=revision.revision,
            idempotency_key=key,
            metadata={
                "design_revision_id": revision.revision_id,
                "design_revision": revision.revision,
                "fieldwork_source": fieldwork_source.value,
                "analysis_enabled": analysis_enabled,
                **({"analysis_context": context_pin} if context_pin else {}),
                **({"sociomapping_enabled": True} if sociomapping_enabled else {}),
                "sociomap_methods": pinned,
                **({"methodology": methodology} if methodology else {}),
                "support": support_pin,
                **({"support_methodology": support_version} if support_version else {}),
                "aggregation": aggregation_pin,
                **({"aggregation_methodology": aggregation_version} if aggregation_version else {}),
                "response": response_pin,
                **({"response_methodology": response_version} if response_version else {}),
                "readiness": readiness_pin,
                **({"readiness_methodology": readiness_version} if readiness_version else {}),
                **({"routing": True} if routed else {}),
                **({"retry_of": retry_of} if retry_of else {}),
                **({"analysis_retry": frozen_dataset.note()} if frozen_dataset else {}),
                "persona_source": persona_source.value,
                **(
                    {"population": _population_note(population, read_by_fieldwork=panel)}
                    if population
                    else {}
                ),
                # What the design selected and what reached its respondents (5b).
                **(
                    {"selection": selection_receipt(_spec, population_draw=panel)}
                    if _spec is not None
                    else {}
                ),
                # Whether the run can answer what it asks, and who decided to run it anyway.
                **({"answerability": answer_note} if answer_note else {}),
            },
            step_inputs={
                "compile": {
                    "design_revision_id": revision.revision_id,
                    "readiness": readiness_pin,
                    **(
                        {"frozen_specification": frozen_spec}
                        if frozen_dataset is not None
                        and (frozen_spec := frozen_dataset.specification_input()) is not None
                        else {}
                    ),
                },
                "preflight": {
                    "methods": pinned,
                    "persona_source": persona_source.value,
                    "readiness": readiness_pin,
                    **({"routing": True} if routed else {}),
                },
                "run": {
                    "fieldwork_source": fieldwork_source.value,
                    "persona_source": persona_source.value,
                    **({"routing": True} if routed else {}),
                    "response": response_pin,
                    **({"frozen_dataset": frozen_dataset.step_input()} if frozen_dataset else {}),
                },
                "aggregate": {"support": support_pin, "aggregation": aggregation_pin},
                "sociomap": {
                    "methods": pinned,
                    # An analysis retry of a run on the earlier default reuses its stored map
                    # and never computes that method again.
                    **(
                        {"reuse_only": True}
                        if frozen_dataset is not None and is_retired(methods)
                        else {}
                    ),
                },
                **(
                    analysis_step_inputs(
                        ClaimSurface.INTERNAL,
                        analysis_round=frozen_dataset.analysis_round if frozen_dataset else 0,
                    )
                    if analysis_enabled
                    else {}
                ),
            },
            owner=DESIGN_PROJECT_OWNER,
            analysis_enabled=analysis_enabled,
            sociomapping_enabled=sociomapping_enabled,
            population=population,
        )
        if fresh_acknowledgement is not None and started.created:
            assert acknowledge is not None
            self._workflows().record_answerability_acknowledgement(
                started.run_id,
                digest=fresh_acknowledgement.digest,
                reason=acknowledge.reason,
                gaps=[g.to_json() for g in fresh_acknowledgement.gaps],
                rules=ANSWERABILITY_RULES,
                design_revision_id=revision.revision_id,
            )
        if confirmation is not None and started.created:
            assert confirm_cost_usd is not None
            self._workflows().record_spend_confirmation(
                started.run_id,
                ceiling_usd=confirmation[0],
                limit_usd=confirmation[1],
                confirmed_usd=confirm_cost_usd,
            )
        return started

    def retry(
        self,
        run_id: str,
        *,
        fieldwork_source: FieldworkSource,
        reservations: RunReservations | None = None,
        confirm_cost_usd: float | None = None,
        acknowledge: Acknowledgement | None = None,
        require_answerability: bool = False,
    ) -> StartedRun:
        """Start a failed or cancelled run again, as a new run linked to it.

        A retry spends again, so it asks again: the limit and the confirmation work as they do
        for :meth:`start`. It pins the Sociomap methods the run it retries pinned, never the
        current default, without the reference map; a run whose object map is ``aia-sociomap-3``
        or that pinned the reference map alone (as a run stored before pins reads) is refused,
        :class:`ResearchRunOnRetiredMethod`.
        It keeps the original's persona source whatever the deployment's switch now says; a
        run stored before the source was pinned retries on the fictional roster, which
        answered it.
        """
        run = self.get(run_id)
        if not retryable(run["status"]):
            raise ResearchRunNotRetryable(run["status"])
        return self._restart(
            run,
            fieldwork_source=fieldwork_source,
            reservations=reservations,
            confirm_cost_usd=confirm_cost_usd,
            acknowledge=acknowledge,
            require_answerability=require_answerability,
        )

    def retry_analysis(
        self,
        run_id: str,
        *,
        frozen_dataset: FrozenDataset,
        reservations: RunReservations | None = None,
        confirm_cost_usd: float | None = None,
        acknowledge: Acknowledgement | None = None,
    ) -> StartedRun:
        """Start ``run_id`` again over its own collected data: an analysis retry.

        It is never refused for its research questions: no new data is collected, and asking
        the same modules again cannot change what the design measures. It records the gaps,
        with the original's acknowledgement when it has one.

        Every pin is kept as :meth:`retry` keeps it, and so is the fieldwork source the run
        recorded (its dataset is reused, never collected again). Which runs may be retried
        this way, and which modules, is :func:`~.analysis_results.retry_failed_modules`'s
        to decide; this only starts the run.
        """
        run = self.get(run_id)
        return self._restart(
            run,
            fieldwork_source=FieldworkSource(str(run["metadata"]["fieldwork_source"])),
            reservations=reservations,
            confirm_cost_usd=confirm_cost_usd,
            analysis_enabled=True,
            frozen_dataset=frozen_dataset,
            acknowledge=acknowledge,
        )

    def _restart(
        self,
        run: Mapping[str, Any],
        *,
        fieldwork_source: FieldworkSource,
        reservations: RunReservations | None,
        confirm_cost_usd: float | None,
        analysis_enabled: bool | None = None,
        frozen_dataset: FrozenDataset | None = None,
        acknowledge: Acknowledgement | None = None,
        require_answerability: bool = False,
    ) -> StartedRun:
        """A new run linked to ``run``, under every pin it recorded, and the answerability
        acknowledgement it recorded: it covers the retry only while the gaps are the same.

        A run whose methods no new run computes (:func:`~aia_core.domain.research_sociomap.
        is_retired`) is refused (:class:`ResearchRunOnRetiredMethod`) before anything is started
        or spent: the refusal names its Design Revision, over which a new run pins
        ``aia-sociomap-5``. An analysis retry of such a run is let through when its Sociomap is
        stored: it keeps the pins, so its step finds that map under the same inputs and computes
        nothing (the step is told to reuse only, and fails rather than compute it again). A run
        of an edited version is retried with that version alone: the reference map pinned
        beside it is dropped. Retired is the code's old default only: a run whose methods came
        from a version in force (an unchanged aia-sociomap-3 pins the preset's own name) is that
        organization's choice, retried as it pinned it."""
        run_id = str(run["run_id"])
        pinned = read_methods(run["metadata"].get("sociomap_methods"))
        if is_retired(pinned) and not run["metadata"].get("methodology"):
            if frozen_dataset is None or not _sociomap_stored(run):
                raise ResearchRunOnRetiredMethod(run, [m.method_id for m in pinned])
        else:
            pinned = without_reference(pinned)
        return self.start(
            design_revision_id=str(run["metadata"]["design_revision_id"]),
            fieldwork_source=fieldwork_source,
            retry_of=run_id,
            frozen_dataset=frozen_dataset,
            analysis_enabled=bool(run["metadata"].get("analysis_enabled", False))
            if analysis_enabled is None
            else analysis_enabled,
            sociomapping_enabled=bool(run["metadata"].get("sociomapping_enabled", False)),
            reservations=reservations,
            confirm_cost_usd=confirm_cost_usd,
            sociomap_methods=pinned,
            support=read_support_pin(run["metadata"].get("support")),
            aggregation=_aggregation_of(run["metadata"]),
            response=read_response_pin(run["metadata"].get("response")),
            readiness=read_readiness_pin(run["metadata"].get("readiness")),
            kept={
                k: run["metadata"][k]
                for k in (
                    "methodology",
                    "support_methodology",
                    "aggregation_methodology",
                    "response_methodology",
                    "readiness_methodology",
                    "analysis_context",
                )
                if run["metadata"].get(k)
            },
            persona_source=persona_source_of(run["metadata"]),
            routing=run["metadata"].get("routing") is True,
            acknowledge=acknowledge,
            inherited_acknowledgement=_acknowledgement_of(run),
            require_answerability=require_answerability,
        )

    def design_research_pin(self) -> dict[str, str] | None:
        """The bundle the Study's newest finished Design Research run published, as a run's
        ``analysis_context`` pins it (the run, the artifact, its SHA-256); ``None`` when it has
        none. Only found here: a reader reads it again through the run that published it and
        verifies it (``analysis_results._external_context``). Among the newest 200 Deep
        Research runs, the most a listing returns."""
        project_id = self._designs().project_id()
        if project_id is None:
            return None
        for run in self._workflows().list_runs(
            project_id=project_id, workflow_type=DEEP_RESEARCH, steps=True, limit=200
        ):
            if (
                run["status"] is not WorkflowRunStatus.COMPLETED
                or (run.get("metadata") or {}).get("purpose") != "DESIGN_RESEARCH"
            ):
                continue
            publish = next((x for x in run.get("steps") or [] if x["node_key"] == "publish"), None)
            output = (publish or {}).get("output") or {}
            if all(isinstance(output.get(k), str) for k in ("artifact_id", "sha256")):
                return {
                    "deep_research_run_id": str(run["run_id"]),
                    "artifact_id": output["artifact_id"],
                    "sha256": output["sha256"],
                }
        return None

    def design_project_id(self) -> str | None:
        """The Study's owned design project, where its runs and reports are; ``None`` before
        its first Design Revision."""
        return self._designs().project_id()

    def request_report_pdf(
        self,
        *,
        docx: Artifact,
        run_id: str,
        deep_research_run_id: str | None,
        mark: ReviewMark,
        again: bool = False,
    ) -> StartedRun | None:
        """Ask the worker to render a stored report DOCX of ``run_id`` as PDF (``report_pdf``).

        ``mark`` is the version's review as the caller read it (``report_export.review_mark``):
        a draft's job renders the stored bytes, an approved version's its stamped export under
        the approved key; the worker reads the mark again and refuses a job whose mark moved.
        An approved version stored before the stamp layout exports its stored bytes
        (``report_export.exports_stamped``), so its job is asked under the draft's key, where
        the rendering made while it was a draft already is its PDF.

        Asking again while a job for the same DOCX is queued, running or done returns that job;
        after one failed, was cancelled or stopped for recovery (no converter, a conversion that
        failed both attempts), or with ``again`` (its rendering is missing or corrupt, which the
        caller read: ``report_variants.variant_pdf``), a person asking again starts a new job,
        so enabling the converter later is never final.

        ``None`` on a delivered or archived Study: it starts no work, so no job is asked for,
        and its stored DOCX stays the report (the caller says why the PDF is not there). Needs
        ``RUN_WORKFLOW``, as any job does; only a person's explicit request calls it, never a
        download.
        """
        self.get(run_id)
        if not self.scope.study_status.accepts_work:
            return None
        if (mark.artifact_id, mark.sha256) != (docx.artifact_id, docx.sha256):
            raise ValueError("the review mark names another version")
        base = report_pdf_key(
            run_id, deep_research_run_id, docx.artifact_id, approved=exports_stamped(docx, mark)
        )
        # The round is the newest job's, never a count of a capped listing: past 100 jobs the
        # count named an existing key, and asking again silently returned the failed job.
        newest = self._workflows().list_runs(
            project_id=docx.project_id, workflow_type=REPORT_PDF, key_prefix=base, limit=1
        )
        round_ = int(newest[0]["metadata"].get("round") or 0) if newest else 0
        if newest and (
            again
            or newest[0]["status"]
            in (
                WorkflowRunStatus.FAILED,
                WorkflowRunStatus.CANCELLED,
                WorkflowRunStatus.RECOVERY_REQUIRED,
            )
        ):
            round_ += 1
        key = base if round_ == 0 else f"{base}:again-{round_}"
        return start_workflow(
            self.session,
            self.scope,
            project_id=docx.project_id,
            workflow_type=REPORT_PDF,
            revision=docx.revision,
            idempotency_key=key,
            metadata={
                "run_id": run_id,
                "deep_research_run_id": deep_research_run_id,
                "docx_artifact_id": docx.artifact_id,
                "round": round_,
                "review_state": mark.state.value,
            },
            step_inputs={
                "pdf": {
                    "docx_artifact_id": docx.artifact_id,
                    "docx_sha256": docx.sha256,
                    "run_id": run_id,
                    "deep_research_run_id": deep_research_run_id,
                    "review_state": mark.state.value,
                    "approved_on": mark.approved_on.isoformat() if mark.approved_on else None,
                }
            },
            owner=DESIGN_PROJECT_OWNER,
        )

    def cancel(self, run_id: str, *, reason: str = "researcher") -> WorkflowRunStatus:
        """Cancel a run of this Study. Needs ``CANCEL_WORKFLOW``."""
        self.scope.require(Permission.CANCEL_WORKFLOW)
        self.get(run_id)
        return self._workflows().request_cancel(run_id, reason=reason)

    def lift_budget_wait(
        self,
        run_id: str,
        node_key: str | None = None,
        *,
        budget_usd: float,
        note: str = "",
    ) -> dict[str, Any]:
        """Raise the study's budget to ``budget_usd`` and let every step of the run stopped at
        the cap go on, in one decision (:func:`lift_study_budget_waits`, which states the rule).

        A run's analysis modules each reserve their own call, so several can wait at once; the
        lift is the run's, not one per step (CR-3). ``node_key``, when given (the older
        per-step route), must name a step of the run that is waiting for budget; the lift
        still releases every waiting step."""
        self.scope.require(Permission.APPROVE_BUDGET)
        self.scope.require(Permission.MANAGE_STUDY_BUDGET)
        self.scope.require_open_study()
        run = self.get(run_id)
        if node_key is not None:
            step = next((s for s in run["steps"] if s["node_key"] == node_key), None)
            if step is None:
                raise ResearchStepNotFound(node_key)
            if step["status"] is not StepRunStatus.AWAITING_BUDGET:
                raise BudgetWaitNotLiftable("only a step waiting for budget can be lifted")
        lift_study_budget_waits(
            self.session, self.scope, run_id, run["steps"], budget_usd=budget_usd, note=note
        )
        return self.get(run_id)

    def resume(self, run_id: str) -> dict[str, Any]:
        """Offer this run's steps parked for the AI runtime to a worker again
        (:func:`resume_runtime_parks`, which states the rule).

        A run parked at fieldwork or at its analysis modules waits for a person once the
        runtime is on; a retry would be a new run, and ``retryable`` refuses a waiting one.
        Nothing is re-chosen: the run keeps its revision, pins and confirmed ceiling."""
        run = self.get(run_id)
        resume_runtime_parks(self.session, self.scope, run["steps"])
        return self.get(run_id)

    def readiness(
        self,
        design_revision_id: str,
        *,
        persona_source: PersonaSource = PersonaSource.FICTIONAL_ROSTER,
        fieldwork_source: FieldworkSource | None = None,
    ) -> tuple[ResearchSpecification | None, Readiness]:
        """Compile a revision of this Study and assess it, without starting anything (see
        :meth:`outlook`, which this reads)."""
        prepared = self.outlook(
            design_revision_id, persona_source=persona_source, fieldwork_source=fieldwork_source
        )
        return prepared.spec, prepared.readiness

    def outlook(
        self,
        design_revision_id: str,
        *,
        persona_source: PersonaSource = PersonaSource.FICTIONAL_ROSTER,
        fieldwork_source: FieldworkSource | None = None,
        population_version_id: str | None = None,
    ) -> RunOutlook:
        """Compile a revision of this Study and assess it, without starting anything, under
        the methodology a start would pin now (the one in force) and the persona source it
        would pin (a panel run applies the design's audience filters).

        With ``fieldwork_source`` ``ai_runtime`` the readiness also forecasts the run's
        evidence support (``domain.support_forecast``) under the support rules a start would
        pin: the donors fieldwork will draw and whether any number will be shown. Other
        sources answer by code (the workbench's fixture) and get no forecast, so their
        questions' support reads unknown. ``questions`` is every item's verdict
        (``domain.question_outlook``), from that forecast."""
        designs = self._designs()
        revision = designs.get(design_revision_id)
        return self._assess(
            designs.content(revision.revision_id),
            design_revision_id=revision.revision_id,
            persona_source=persona_source,
            fieldwork_source=fieldwork_source,
            population_version_id=population_version_id,
        )

    def outlook_working(
        self,
        working_revision: int,
        *,
        persona_source: PersonaSource = PersonaSource.FICTIONAL_ROSTER,
        fieldwork_source: FieldworkSource | None = None,
        population_version_id: str | None = None,
    ) -> RunOutlook:
        """:meth:`outlook` on a revision of the Study's working content, with no Design
        Revision submitted (plan working-copy-edit-ops WCE7).

        A Design Revision is the working content it names, byte for byte (its submit is
        checked by hash), so this is the readiness a submit of that working revision would
        read; nothing is written. Its answerability names no Design Revision, so its digest
        never matches a start's: an acknowledgement is read on the revision a start runs.
        A revision the Study's working project never wrote, or one without content, is
        :class:`WorkingRevisionNotFound`."""
        working = StudyWorkspaceRepository(self.session).at_revision(self.scope, working_revision)
        if working is None or working.content is None:
            raise WorkingRevisionNotFound(working_revision)
        return self._assess(
            working.content,
            design_revision_id=None,
            persona_source=persona_source,
            fieldwork_source=fieldwork_source,
            population_version_id=population_version_id,
        )

    def impact(self, working_revision: int, design_revision_id: str | None = None) -> WorkingImpact:
        """What each stage of the design ``design_revision_id`` (the newest Design Revision when
        omitted) would need going to working revision ``working_revision`` (plan
        working-copy-edit-ops WCE7): ``domain.pipeline.stage_impacts``. Reads both, writes nothing.
        A working revision the Study never saved is :class:`WorkingRevisionNotFound`; a Design
        Revision not of this Study, or none at all, ``DesignRevisionNotFound``."""
        working = StudyWorkspaceRepository(self.session).at_revision(self.scope, working_revision)
        if working is None or working.content is None:
            raise WorkingRevisionNotFound(working_revision)
        designs = self._designs()
        if design_revision_id is None:
            latest = designs.latest()
            if latest is None:
                raise DesignRevisionNotFound("no design revision")
            design_revision_id = latest.revision_id
        revision = designs.get(design_revision_id)
        before = designs.content(revision.revision_id)
        return WorkingImpact(
            working_revision=working_revision,
            design_revision_id=revision.revision_id,
            design_revision=revision.revision,
            changed=tuple(changed_fields(before, working.content)),
            stages=stage_impacts(before, working.content),
        )

    def _assess(
        self,
        content: dict[str, Any],
        *,
        design_revision_id: str | None,
        persona_source: PersonaSource,
        fieldwork_source: FieldworkSource | None,
        population_version_id: str | None = None,
    ) -> RunOutlook:
        methods, _ = self._methods(None)
        limits, _ = self._readiness(None)
        spec, readiness = prepare(
            content,
            pair_n_min=side_tables_of(methods).n_min,
            filters_applied=persona_source is PersonaSource.PANEL,
            limits=limits,
            routing=self.routing_enabled,
        )
        if spec is None:
            return RunOutlook(spec=None, readiness=readiness, questions=(), trace=None)
        forecast: SupportForecast | None = None
        panel: PanelDraw | None = None
        if fieldwork_source is FieldworkSource.AI_RUNTIME:
            support, _ = self._support(None)
            # The aggregation a start would pin, compiled as the aggregate reads it: a version
            # that replaces Kish's formula changes every cell's effective n.
            pin, _ = self._aggregation(None)
            _, slots = read_aggregation_pin(pin)
            # A run over a selected child draws from the child, which the sampler does not
            # read: unknown, as its start reads it.
            if persona_source is PersonaSource.PANEL and population_version_id is None:
                panel = self._panel_draw(spec)
                if panel is not None and panel.sampler_refused is not None:
                    readiness = with_panel_refusal(readiness, panel.sampler_refused, panel.reasons)
            forecast = forecast_support(
                spec,
                support=support,
                persona_source=persona_source,
                slots=slots,
                sample=panel.sample if panel is not None else None,
            )
            readiness = with_support_forecast(readiness, forecast, support=support)
        questions = question_outlook(spec, forecast, routing=self.routing_enabled)
        # The research questions as the analysis will read them, each traced to its measures.
        trace = trace_research(
            spec, research_questions_of(content), questions, comparisons_of(content)
        )
        answer = answerability(trace, questions, design_revision_id=design_revision_id)
        # One verdict on screen: the trace card and the research-question check read what the
        # gate decided, never "at risk" beside a gap that says the run will not answer it.
        return RunOutlook(
            spec=spec,
            readiness=with_answerability(with_research_trace(readiness, trace), answer),
            questions=questions,
            trace=decided_trace(trace, answer),
            answerability=answer,
            panel=panel,
            forecast=forecast,
        )

    def _support(self, support: SupportSpec | None) -> tuple[SupportSpec, dict[str, Any] | None]:
        """The support rules a start pins, and the stored version they come from (``None``:
        the code's preset, ``aia-support-1``, or the caller's own set).

        ``support`` ``None`` is the organization's support version in force; with nothing
        stored, both rules are as they were before any version (owner, 2026-10-12).
        """
        if support is not None:
            return support, None
        in_force = methodology_in_force_for_study(self.session, self.scope, "support")
        if in_force.version is None:
            return support_spec_for(None), None
        return support_spec_for(in_force.version.payload), {
            "module": "support",
            "version": in_force.version.version_number,
            "name": in_force.version.name,
            "payload_sha256": in_force.version.payload_sha256,
        }

    def _readiness(
        self, readiness: ReadinessSpec | None
    ) -> tuple[ReadinessSpec, dict[str, Any] | None]:
        """The readiness limits a start checks under and pins, and the stored version they
        come from (``None``: the code's preset, ``aia-readiness-1``, or the caller's own).

        ``readiness`` ``None`` is the organization's readiness version in force (plan
        ``methodology-tab`` V1a); with nothing stored, 18.6.6's product policy."""
        if readiness is not None:
            return readiness, None
        return readiness_in_force(self.session, self.scope)

    def _response(
        self, response: ResponseProcessSpec | None
    ) -> tuple[ResponseProcessSpec, dict[str, Any] | None]:
        """The response process a start pins, and the stored version it comes from (``None``:
        the code's preset, ``aia-response-1``, or the caller's own process)."""
        if response is not None:
            return response, None
        in_force = methodology_in_force_for_study(self.session, self.scope, "response")
        if in_force.version is None:
            return response_spec_for(None), None
        return response_spec_for(in_force.version.payload), {
            "module": "response",
            "version": in_force.version.version_number,
            "name": in_force.version.name,
            "payload_sha256": in_force.version.payload_sha256,
        }

    def _aggregation(
        self, aggregation: Mapping[str, Any] | None
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """The aggregation a start pins, and the stored version it comes from (``None``: the
        code's preset, 18.6.6's port, or the caller's own pin). A pin is checked by reading
        it as the aggregate will, so one that would fail there is refused before any run."""
        if aggregation is not None:
            read_aggregation_pin(aggregation)
            return {
                "spec": dict(aggregation["spec"]),
                "formulas": dict(aggregation["formulas"]),
            }, None
        in_force = methodology_in_force_for_study(self.session, self.scope, "aggregation")
        if in_force.version is None:
            return aggregation_pin_for(None), None
        return aggregation_pin_for(in_force.version.payload), {
            "module": "aggregation",
            "version": in_force.version.version_number,
            "name": in_force.version.name,
            "payload_sha256": in_force.version.payload_sha256,
        }

    def _methods(
        self, sociomap_methods: Sequence[SociomapMethod] | None
    ) -> tuple[tuple[SociomapMethod, ...], dict[str, Any] | None]:
        """The Sociomap methods a start pins, each resolved, and the stored methodology they
        come from (``None``: the code's preset, or the caller's own set).

        ``sociomap_methods`` ``None`` is the organization's methodology in force (ADR 0023
        decision 6): the code's preset, or an edited object map put in force on the
        Metodika tab. A pin the engine cannot compute is refused here, by name.
        """
        methodology: dict[str, Any] | None = None
        if sociomap_methods is None:
            in_force = methodology_in_force_for_study(self.session, self.scope, "sociomap")
            payload = None if in_force.version is None else in_force.version.payload
            chosen = default_methods() if payload is None else sociomap_methods_for(payload)
            if in_force.version is not None:
                methodology = {
                    "module": "sociomap",
                    "version": in_force.version.version_number,
                    "name": in_force.version.name,
                    "payload_sha256": in_force.version.payload_sha256,
                }
        else:
            chosen = tuple(sociomap_methods)
        methods = read_methods([m.model_dump(mode="json") for m in chosen])
        for method in methods:
            method.resolve()
        return methods, methodology

    # -- read -------------------------------------------------------------------

    def get(self, run_id: str) -> dict[str, Any]:
        """One research run of this Study, in full, with its phase."""
        project_id = self._designs().project_id()
        try:
            run = self._workflows().get_run(run_id)
        except WorkflowNotFound as exc:
            raise ResearchRunNotFound(run_id) from exc
        # Scope already confined the run to this Study; the design project and the
        # type confine it to this Study's research.
        if (
            project_id is None
            or run["project_id"] != project_id
            or run["workflow_type"] != RESEARCH
        ):
            raise ResearchRunNotFound(run_id)
        run["attempted"] = any(s["attempts"] for s in run["steps"])
        run["phase"] = phase_of(run["status"], attempted=run["attempted"])
        run["retryable"] = retryable(run["status"])
        return run

    def spend(self, run: Mapping[str, Any]) -> ActivitySpend:
        """What one research run of this Study has spent, holds open and could not settle, by
        the rules a person's spend is read (``artifact-fieldwork`` FLD4). ``run`` is what
        :meth:`get` found through this Study; the query is in the Study and organization too."""
        self.scope.require(Permission.VIEW_COSTS)
        usage, holds = run_spend_facts(
            self.session,
            organization_id=self.scope.organization_id,
            study_id=self.scope.study_id,
            run_id=str(run["run_id"]),
        )
        return run_spend(usage, holds)

    def runs(self, *, limit: int = 20, steps: bool = False) -> list[dict[str, Any]]:
        """This Study's research runs, newest first, with their phases.

        ``steps``: each with its steps, without their attempt history (one more query).
        """
        project_id = self._designs().project_id()
        if project_id is None:
            return []
        runs = [
            r
            for r in self._workflows().list_runs(
                project_id=project_id, limit=limit, workflow_type=RESEARCH, steps=steps
            )
            if r["workflow_type"] == RESEARCH
        ]
        for r in runs:
            r["phase"] = phase_of(r["status"], attempted=r["attempted"])
            r["retryable"] = retryable(r["status"])
        return runs

    def events(self, run_id: str, *, since: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        """The run's append-only events after ``since``."""
        self.get(run_id)
        return self._workflows().events(run_id, since=since, limit=limit)

    def artifact_ids(self, run_id: str) -> list[str]:
        """The artifacts this run's steps produced, in step order."""
        run = self.get(run_id)
        return [
            str(s["output"]["artifact_id"])
            for s in run["steps"]
            if isinstance(s.get("output"), dict) and s["output"].get("artifact_id")
        ]


class _Probed(Exception):
    """Raised by a start asked only for its key (``_probe``), before any gate or write."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def existing_start(
    session: Session, scope: StudyContext, start: Callable[[], StartedRun]
) -> str | None:
    """The run ``start`` would find already there, or None when it would create one.

    ``start`` is a :meth:`ResearchRuns.start` or :meth:`ResearchAgentJobs.start` call with
    ``_probe=True``: it computes the same idempotency key a real start does, from the same
    code, and stops before any gate, charge or write. For a caller that must not hold a found
    run to the gates of a new one (a typed start approved again, lead-orchestration LO5)."""
    try:
        start()
    except _Probed as probed:
        return WorkflowRepository(session, scope).find_run_by_idempotency_key(probed.key)
    raise AssertionError("a probed start returned instead of naming its key")


@dataclass(frozen=True, slots=True)
class ResearchAgentJobs:
    """Design assistance is a durable job, never a request-time model call.

    Approved client memory is frozen at enqueue. Jobs only produce proposals;
    applying one requires EDIT_STUDY and its unchanged Design Revision.

    A job is paid work and meets the study's confirmation threshold like a run
    (``spend_confirm_usd``, ADR 0019 gate 2, ADR 0028; lead-orchestration LO15): every way a
    job is created -- a direct start, a rebuild, the Lead's approved request -- goes through
    :meth:`spend_gate` in :meth:`start`, so none of them evades it.
    """

    session: Session
    scope: StudyContext
    #: The clients a draft prompt may be tested on (``AIA_AI_FICTIONAL_CLIENT_IDS``). Empty
    #: by default, so a caller that does not pass it can run no draft at all.
    draft_client_ids: frozenset[str] = frozenset()
    #: What one job can cost at most: the design job's reservation
    #: (``AIA_AI_RESEARCH_RESERVATION_USD``, a primary and one repair). ``None`` is unknown,
    #: never zero: with a threshold set, a new job is then refused (:class:`CostCeilingUnknown`).
    reservation_usd: float | None = None

    def spend_gate(self, confirm_cost_usd: float | None) -> tuple[float, float] | None:
        """The confirmation threshold's one rule (``domain/money.py``) for one new job.

        Returns ``(ceiling, threshold)`` when the person's ``confirm_cost_usd`` covers a ceiling
        that reaches the threshold -- the caller records it once the job exists -- and ``None``
        when nothing asks. Raises :class:`CostConfirmationRequired` when the ceiling reaches the
        threshold and nothing covering it was confirmed, and :class:`CostCeilingUnknown` when a
        threshold is set and the reservation is not configured.

        A confirmation is a person's: using one needs ``APPROVE_BUDGET``, which the worker's
        scope withholds (``WORKER_PERMISSIONS``), so a step cannot confirm the spend it starts.
        """
        limit = ScopeRepository(self.session).get_study(self.scope).spend_confirm_usd
        verdict = threshold_verdict(self.reservation_usd, limit, confirm_cost_usd)
        if verdict is ThresholdVerdict.NOT_ASKED:
            return None
        assert limit is not None
        if verdict is ThresholdVerdict.CEILING_UNKNOWN:
            raise CostCeilingUnknown(CeilingUnknown.RESEARCH_RESERVATION_MISSING, limit_usd=limit)
        assert self.reservation_usd is not None
        if verdict is ThresholdVerdict.ASK:
            raise CostConfirmationRequired(ceiling_usd=self.reservation_usd, limit_usd=limit)
        self.scope.require(Permission.APPROVE_BUDGET)
        return (self.reservation_usd, limit)

    def start(
        self,
        *,
        design_revision_id: str,
        action: ResearchAction,
        instruction: str = "",
        prompt_version: int | None = None,
        rebuild_of: str | None = None,
        confirm_cost_usd: float | None = None,
        _probe: bool = False,
    ) -> StartedRun:
        """Queue one proposal. The prompt it runs is chosen here and frozen into the job.

        A start that would create a job is held to the study's confirmation threshold
        (:meth:`spend_gate`): at or above it, ``confirm_cost_usd`` must cover the job's ceiling
        (:attr:`reservation_usd`), and the yes is written to the approval ledger with the job.
        A start that finds its job already there spends nothing and asks nothing, as a run's.

        The job records the working revision its Design Revision came from as
        ``base_workspace_revision`` (ADR 0026 decision 5): never the working copy's revision now,
        which may hold edits the design does not. ``rebuild_of`` names the job this one rebuilds
        (:meth:`rebuild`), which it supersedes.

        ``prompt_version`` names a stored version to run instead of the active one --
        how a draft is tested before it is put live (ADR 0020). Only an organization
        administrator may ask for it, and only on a client the deployment lists as
        fictional: a draft is not what the organization runs, and an unreviewed prompt
        is not tried on real client work.
        """
        self.scope.require(Permission.EDIT_STUDY)
        self.scope.require(Permission.RUN_WORKFLOW)
        self.scope.require_open_study()
        if len(instruction.encode()) > 8000:
            raise ValueError("agent instruction exceeds 8 KB")
        prompt = self._pin(action, prompt_version)
        designs = StudyDesignRepository(self.session, self.scope)
        revision = designs.get(design_revision_id)
        snapshot = context_snapshot(
            designs.content(design_revision_id),
            ClientKnowledgeRepository(self.session).for_study(self.scope),
        )
        import hashlib

        digest = hashlib.sha256(
            canonical_json(
                {
                    "action": action.value,
                    "context": snapshot_hash(snapshot),
                    "instruction": instruction,
                    # The assembled prompt: for the baseline this is byte-for-byte what it
                    # always was, so a job queued before ADR 0020 keeps its fingerprint.
                    "prompt": prompt_for(action, prompt.text),
                }
            ).encode()
        ).hexdigest()
        payload = {
            "design_revision_id": design_revision_id,
            "base_workspace_revision": revision.workspace_revision,
            "action": action.value,
            "instruction": instruction,
            "snapshot": snapshot,
            "job_fingerprint": digest,
            "harness_version": HARNESS_VERSION,
            "prompt": prompt.model_dump(mode="json"),
        }
        project_id = designs.project_id()
        assert project_id is not None
        # The same ask on the same design is the same job: asked again, it is followed, never
        # paid twice. Once it ended without a proposal -- failed, cancelled, or stopped for
        # recovery with no paid call of unknown outcome -- asking again is a new round, as a
        # report's PDF is (request_report_pdf) and a source's proposals are (OI-121). Before
        # this, a cancelled job answered every later ask, and the stage could only say so.
        base = f"{RESEARCH_AGENT}:{design_revision_id}:{digest}"
        if rebuild_of is not None:
            # A rebuild is a person's explicit ask for a new proposal: its own job, always.
            base = f"{base}:rebuild-of:{rebuild_of}"
        workflows = WorkflowRepository(self.session, self.scope)
        newest = workflows.list_runs(
            project_id=project_id, workflow_type=RESEARCH_AGENT, key_prefix=base, limit=1
        )
        round_ = int(newest[0]["metadata"].get("round") or 0) if newest else 0
        if newest and _ended_without_result(workflows.get_run(newest[0]["run_id"])):
            round_ += 1
        key = base if round_ == 0 else f"{base}:again-{round_}"
        if _probe:
            raise _Probed(key)
        # Before anything is created: a job that exists already asks nothing.
        confirmation = (
            self.spend_gate(confirm_cost_usd)
            if workflows.find_run_by_idempotency_key(key) is None
            else None
        )
        started = start_workflow(
            self.session,
            self.scope,
            project_id=project_id,
            revision=revision.revision,
            workflow_type=RESEARCH_AGENT,
            idempotency_key=key,
            metadata={
                "design_revision_id": design_revision_id,
                "action": action.value,
                "context_sha256": snapshot_hash(snapshot),
                "harness_version": HARNESS_VERSION,
                "prompt_version": prompt.version,
                "prompt_origin": prompt.origin,
                "round": round_,
                "base_workspace_revision": revision.workspace_revision,
                "rebuild_of": rebuild_of,
            },
            step_inputs={"agent": payload},
            owner=DESIGN_PROJECT_OWNER,
        )
        if confirmation is not None and started.created:
            assert confirm_cost_usd is not None
            workflows.record_spend_confirmation(
                started.run_id,
                ceiling_usd=confirmation[0],
                limit_usd=confirmation[1],
                confirmed_usd=confirm_cost_usd,
            )
        return started

    def _pin(self, action: ResearchAction, prompt_version: int | None) -> PromptPin:
        """The prompt this job will run: the organization's active one, or a draft to test."""
        resolver = PromptResolver(self.session, self.scope.organization_id)
        prompt_id = f"aia.research.{action.value}"
        if prompt_version is None:
            return resolver.pin_for(prompt_id)
        if self.scope.organization_role not in (OrganizationRole.OWNER, OrganizationRole.ADMIN):
            raise DesignRejected(
                "only an organization administrator may test a prompt version",
                reason="prompt_test_requires_administrator",
            )
        if self.scope.client_id not in self.draft_client_ids:
            raise DesignRejected(
                "a draft prompt can be tried only on a client listed as fictional",
                reason="prompt_test_requires_fictional_client",
            )
        try:
            return resolver.pin_for_version(prompt_id, prompt_version)
        except PromptRefused as exc:
            raise DesignRejected(str(exc), reason=exc.reason) from exc

    def get(self, run_id: str) -> dict[str, Any]:
        try:
            run = WorkflowRepository(self.session, self.scope).get_run(run_id)
        except WorkflowNotFound as exc:
            raise ResearchRunNotFound(run_id) from exc
        project_id = StudyDesignRepository(self.session, self.scope).project_id()
        if (
            project_id is None
            or run["project_id"] != project_id
            or run["workflow_type"] != RESEARCH_AGENT
        ):
            raise ResearchRunNotFound(run_id)
        return run

    def jobs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        project_id = StudyDesignRepository(self.session, self.scope).project_id()
        if project_id is None:
            return []
        return [
            r
            for r in WorkflowRepository(self.session, self.scope).list_runs(
                project_id=project_id, limit=limit, workflow_type=RESEARCH_AGENT
            )
            if r["workflow_type"] == RESEARCH_AGENT
        ]

    def events(self, run_id: str, *, since: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        """The job's append-only events after ``since``: what its step reported while it ran."""
        self.get(run_id)
        return WorkflowRepository(self.session, self.scope).events(run_id, since=since, limit=limit)

    def proposal_states(self, runs: Sequence[Mapping[str, Any]]) -> dict[str, ProposalState | None]:
        """Each job's proposal state (ADR 0026 decision 8), read from the ledger and the rebuilds.

        A job is superseded by a rebuild among the Study's jobs that names it (``rebuild_of``),
        whether or not ``runs`` holds that rebuild.
        """
        workflows = WorkflowRepository(self.session, self.scope)
        decisions = workflows.ai_proposal_decisions([str(r["run_id"]) for r in runs])
        rebuilt = {
            str(r["metadata"].get("rebuild_of"))
            for r in self.jobs(limit=200)
            if r["metadata"].get("rebuild_of")
        }
        return {
            str(r["run_id"]): proposal_state(
                action=str(r["metadata"].get("action")),
                completed=r["status"] is WorkflowRunStatus.COMPLETED,
                decision=decisions.get(str(r["run_id"])),
                superseded=str(r["run_id"]) in rebuilt,
            )
            for r in runs
        }

    def dismiss(self, run_id: str) -> bool:
        """A person sets a proposal aside: a ``dismiss`` row in the approval ledger, nothing else.

        ADR 0026 decision 8. Needs ``APPROVE_GATE`` beside ``EDIT_STUDY``, as an accept does: a
        decision about AI output is a person's. The proposal stays readable, and may still be
        accepted later; an accepted one is in the design and is refused
        (``proposal_already_accepted``). Returns whether a row was written (a second dismissal
        writes none).
        """
        self.scope.require(Permission.EDIT_STUDY)
        self.scope.require(Permission.APPROVE_GATE)
        self.scope.require_open_study()
        # The Study row lock every accept takes: a dismissal racing an accept reads the
        # decision the other committed, never writes a row contradicting it.
        StudyDesignRepository(self.session, self.scope).lock()
        run = self.get(run_id)
        action = str(run["metadata"].get("action"))
        state = self.proposal_states([run])[run_id]
        if state is None:
            raise DesignRejected(
                "only a completed design proposal can be dismissed", reason="proposal_not_ready"
            )
        if state is ProposalState.ACCEPTED:
            raise DesignRejected(
                "an accepted proposal is in the design", reason="proposal_already_accepted"
            )
        return WorkflowRepository(self.session, self.scope).record_ai_proposal_dismissal(
            run_id, action=action, artifact_id=str(run["steps"][0]["output"]["artifact_id"])
        )

    def rebuild(
        self, run_id: str, *, design_revision_id: str, confirm_cost_usd: float | None = None
    ) -> StartedRun:
        """Ask a proposal again, on the current design: the same action and instruction, a new job.

        ADR 0026 decision 5: a stale proposal is never accepted; a rebuild starts a new job on
        ``design_revision_id`` -- which must be the Study's newest Design Revision -- naming the
        old one as ``rebuild_of``, which supersedes it. It accepts nothing, and the old job stays
        readable. The browser submits its working copy first, so the newest revision is the
        design the person has now. The new job is paid work: held to the threshold as a start
        is (``confirm_cost_usd``, :meth:`spend_gate`).
        """
        run = self.get(run_id)
        action = ResearchAction(run["metadata"]["action"])
        if action not in DESIGN_ACTIONS:
            raise DesignRejected("advice is asked again, not rebuilt", reason="advice_only")
        latest = StudyDesignRepository(self.session, self.scope).latest()
        if latest is None or latest.revision_id != design_revision_id:
            raise DesignRejected(
                "a rebuild runs on the Study's newest Design Revision", reason="stale_design"
            )
        asked = WorkflowRepository(self.session, self.scope).step_input(run_id, "agent") or {}
        return self.start(
            design_revision_id=design_revision_id,
            action=action,
            instruction=str(asked.get("instruction") or ""),
            rebuild_of=run_id,
            confirm_cost_usd=confirm_cost_usd,
        )

    def cancel(self, run_id: str) -> WorkflowRunStatus:
        self.scope.require(Permission.CANCEL_WORKFLOW)
        self.get(run_id)
        return WorkflowRepository(self.session, self.scope).request_cancel(
            run_id, reason="researcher"
        )

    def resume_runtime_park(self, run_id: str) -> bool:
        """Reoffer this job after its unavailable runtime has been installed.

        This keeps the frozen design and knowledge snapshot. The repository
        refuses any attempt that dispatched a paid call, so it cannot become an
        implicit second model request after an uncertain delivery.
        """
        self.scope.require(Permission.RUN_WORKFLOW)
        self.scope.require_open_study()
        run = self.get(run_id)
        return WorkflowRepository(self.session, self.scope).resume_runtime_park(
            str(run["steps"][0]["step_id"])
        )

    def lift_budget_wait(self, run_id: str, *, budget_usd: float, note: str = "") -> dict[str, Any]:
        """Raise the study's budget and let this job, stopped at the cap, go on
        (:func:`lift_study_budget_waits`). A job is one step; asking the same action again on
        the same revision returns this job, so without the lift it never ends but by a cancel."""
        run = self.get(run_id)
        lift_study_budget_waits(
            self.session, self.scope, run_id, run["steps"], budget_usd=budget_usd, note=note
        )
        return self.get(run_id)

    def result(self, run_id: str, *, store: ArtifactStore) -> dict[str, Any]:
        run = self.get(run_id)
        if run["status"] is not WorkflowRunStatus.COMPLETED:
            raise DesignRejected(
                "the agent job has no completed proposal", reason="proposal_not_ready"
            )
        output = run["steps"][0]["output"]
        result = research_artifacts(self.session, self.scope, store).read_json(
            output["artifact_id"]
        )
        if not isinstance(result, dict):
            raise DesignRejected("invalid proposal artifact", reason="proposal_invalid")
        return result

    def accept(
        self,
        run_id: str,
        *,
        store: ArtifactStore,
        expected_revision_id: str,
        expected_workspace_revision: int,
    ) -> AcceptedProposal:
        """A person applies what the agent job proposed: the working copy, the design, the record.

        ADR 0019 gate 1, ADR 0026 decision 6. Needs ``APPROVE_GATE`` beside ``EDIT_STUDY``: the
        worker's scope holds the second and not the first, so only a person accepts. In one
        transaction (:func:`~.proposal_accept.accept_into_working_copy`): the stale rule, the
        merge into the working copy at ``expected_workspace_revision``, the working revision, the
        Design Revision naming it, and the approval-ledger row naming both. Refused as
        :class:`~.proposal_accept.StaleProposal` when the head moved, the baseline is unknown or
        an item it changes was edited since.
        """
        self.scope.require(Permission.EDIT_STUDY)
        self.scope.require(Permission.APPROVE_GATE)
        self.scope.require_open_study()
        run = self.get(run_id)
        if expected_revision_id != run["metadata"]["design_revision_id"]:
            raise StaleProposal("proposal baseline does not match", why="design_moved")
        action = ResearchAction(run["metadata"]["action"])
        if action not in DESIGN_ACTIONS:
            raise DesignRejected("an advice answer is not a design mutation", reason="advice_only")
        design = StudyDesignRepository(self.session, self.scope).get(expected_revision_id)
        baseline = proposal_baseline(self.session, self.scope, design)
        if baseline is None or run["metadata"].get("base_workspace_revision") is None:
            raise StaleProposal(
                "the proposal's design names no working revision to check it against",
                why="unknown_baseline",
            )
        result = self.result(run_id, store=store)
        output = run["steps"][0]["output"] or {}
        recorded = output.get("touched_items")
        accepted = accept_into_working_copy(
            self.session,
            self.scope,
            design_revision_id=expected_revision_id,
            proposed=proposal_documents(action, baseline, result["result"]),
            expected_workspace_revision=expected_workspace_revision,
            source_stage=_ACCEPT_STAGES[action],
            reason="ai_proposal_accepted",
            touched=[ItemKey.parse(str(k)) for k in recorded]
            if isinstance(recorded, list)
            else None,
        )
        project_id = StudyDesignRepository(self.session, self.scope).project_id()
        assert project_id is not None  # the accept has just written to it
        WorkflowRepository(self.session, self.scope).record_ai_proposal_acceptance(
            run_id,
            action=action.value,
            revision_id=accepted.revision.revision_id,
            project_id=project_id,
            project_revision=accepted.revision.revision,
            created=accepted.created,
            artifact_id=str(output["artifact_id"]),
            workspace_revision=accepted.working.revision,
            workspace_revision_id=accepted.working.revision_id,
        )
        return accepted


#: The stage an accepted proposal's Design Revision is recorded as submitted from.
_ACCEPT_STAGES: dict[ResearchAction, str] = {
    ResearchAction.ANALYZE: "plan",
    ResearchAction.BUILD: "questionnaire",
    ResearchAction.OPTIMIZE: "questionnaire",
    ResearchAction.AUDIENCE: "audience",
    ResearchAction.DIMENSIONS: "persona",
}


def _ended_without_result(run: Mapping[str, Any]) -> bool:
    """Whether asking again may start a new round in place of ``run``: it failed or was
    cancelled, or it stopped for recovery and no attempt left a paid call of unknown outcome
    (that call may have been billed, so an operator settles it first)."""
    if run["status"] in (WorkflowRunStatus.FAILED, WorkflowRunStatus.CANCELLED):
        return True
    if run["status"] is not WorkflowRunStatus.RECOVERY_REQUIRED:
        return False
    return not any(
        a["paid_call_dispatched"] and not a["paid_call_outcome_known"]
        for step in run["steps"]
        for a in step["attempts"]
    )


def _new_run_start(run: Mapping[str, Any]) -> dict[str, Any]:
    """What a new run over ``run``'s Design Revision starts with to begin as ``run`` did: its
    persona source, the materialized child it ran over (a pinned population names none), and
    the research-question acknowledgement it recorded."""
    meta = run["metadata"]
    population = meta.get("population")
    child = (
        population.get("version_id")
        if isinstance(population, Mapping) and population.get("population_id") is None
        else None
    )
    acknowledged = _acknowledgement_of(run)
    return {
        "design_revision_id": str(meta["design_revision_id"]),
        "persona_source": persona_source_of(meta).value,
        **({"population_version_id": str(child)} if child else {}),
        **(
            {
                "acknowledge_research_questions": {
                    "digest": acknowledged[0].digest,
                    "reason": acknowledged[0].reason,
                }
            }
            if acknowledged is not None
            else {}
        ),
    }


def _sociomap_stored(run: Mapping[str, Any]) -> bool:
    """Whether ``run``'s Sociomap step succeeded with a stored map."""
    return any(
        s.get("node_key") == "sociomap"
        and s.get("status") is StepRunStatus.SUCCEEDED
        and (s.get("output") or {}).get("artifact_id")
        for s in run.get("steps") or ()
    )


def _aggregation_of(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """The aggregation a run pinned, as a retry pins it again. A run started before
    aggregation was pinned was computed as 18.6.6's port, so its retry is too."""
    stored = metadata.get("aggregation")
    if stored is None:
        return {"spec": dict(UNIT_AGGREGATION_PIN["spec"]), "formulas": {}}
    return {"spec": dict(stored["spec"]), "formulas": dict(stored.get("formulas") or {})}


def _acknowledgement_of(run: Mapping[str, Any]) -> tuple[Acknowledgement, str, str | None] | None:
    """The answerability acknowledgement ``run`` recorded, with its run id and who gave it.

    An inherited one names the run that first recorded it, so a retry of a retry still points
    at the person's own decision. A record AIA cannot read is no acknowledgement."""
    note = read_answerability_note(run["metadata"])
    held = note.get("acknowledgement") if note else None
    if note is None or not isinstance(held, Mapping):
        return None
    try:
        ack = Acknowledgement(digest=str(note["digest"]), reason=str(held.get("reason") or ""))
    except AcknowledgementRefused:
        return None
    by = held.get("by")
    return ack, str(held.get("inherited_from") or run["run_id"]), str(by) if by else None
