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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..domain.ai_contracts import canonical_json
from ..domain.analysis.steps import analysis_step_inputs
from ..domain.design import DESIGN_PROJECT_OWNER, DesignRejected, DesignRevision
from ..domain.evidence import ClaimSurface
from ..domain.evidence.support import AIA_SUPPORT_V1, SupportSpec
from ..domain.fieldwork import FieldworkSource, PersonaSource, persona_source_of
from ..domain.methodology.pins import (
    UNIT_AGGREGATION_PIN,
    aggregation_pin_for,
    read_aggregation_pin,
    read_response_pin,
    read_support_pin,
    response_spec_for,
    sociomap_methods_for,
    support_spec_for,
)
from ..domain.pipeline import fingerprint
from ..domain.population import (
    CZ_LIVE,
    CZ_SYNTHETIC_V17,
    PopulationBinding,
    PopulationBindingMissing,
    PopulationImportContract,
    VersionOwner,
)
from ..domain.prompts import PromptPin
from ..domain.research import phase_of, retryable
from ..domain.research_agents import (
    HARNESS_VERSION,
    ResearchAction,
    context_snapshot,
    prompt_for,
    snapshot_hash,
)
from ..domain.research_design import Readiness, ResearchSpecification, prepare
from ..domain.research_sociomap import (
    SociomapMethod,
    default_methods,
    methods_fingerprint,
    read_methods,
    side_tables_of,
)
from ..domain.respondent_behavior import AIA_RESPONSE_V1, ResponseProcessSpec
from ..domain.run_cost import CeilingUnknown, RunCostCeiling, run_cost_ceiling
from ..domain.scope import OrganizationRole, Permission, StudyContext
from ..domain.support_forecast import forecast_support, with_support_forecast
from ..domain.workflow import StepRunStatus, WorkflowRunStatus
from ..domain.workflow_templates import RESEARCH, RESEARCH_AGENT
from ..infrastructure.artifact_repository import ArtifactRepository
from ..infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from ..infrastructure.methodology_repository import methodology_in_force_for_study
from ..infrastructure.prompt_repository import PromptRefused, PromptResolver
from ..infrastructure.scope_repository import ScopeRepository
from ..infrastructure.storage import ArtifactStore
from ..infrastructure.study_design_repository import StudyDesignRepository
from ..infrastructure.workflow_repository import (
    BudgetWaitNotLiftable,
    WorkflowNotFound,
    WorkflowRepository,
)
from .analysis import MAX_REPAIRS
from .population import child_binding, live_binding
from .workflows import StartedRun, start_workflow

__all__ = [
    "BudgetNotRaised",
    "CostCeilingUnknown",
    "CostConfirmationRequired",
    "DesignNotReady",
    "FrozenDataset",
    "PanelPopulationMissing",
    "ResearchAgentJobs",
    "ResearchRunNotFound",
    "ResearchRunNotRetryable",
    "ResearchRuns",
    "ResearchStepNotFound",
    "RunReservations",
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


class DesignNotReady(Exception):
    """The Design Revision does not compile, or fails a readiness check."""

    def __init__(self, readiness: Readiness) -> None:
        super().__init__("the design is not ready to run")
        self.readiness = readiness


class PanelPopulationMissing(Exception):
    """A panel run asked for, and no population established to draw its respondents from."""


class ResearchRunNotFound(LookupError):
    """No research run with this id in the Study in scope."""


class ResearchRunNotRetryable(Exception):
    """Only a failed or cancelled run may be retried."""

    def __init__(self, status: WorkflowRunStatus) -> None:
        super().__init__(f"a {status.value} run cannot be retried")
        self.status = status


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

    def __post_init__(self) -> None:
        if self.analysis_round < 1:
            raise ValueError("an analysis retry is round 1 or later")

    def step_input(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "artifact_id": self.artifact_id, "sha256": self.sha256}

    def note(self) -> dict[str, Any]:
        return {**self.step_input(), "round": self.analysis_round, "modules": list(self.retried)}


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


@dataclass(frozen=True, slots=True)
class ResearchRuns:
    """The research runs of the Study in scope. The caller owns the transaction."""

    session: Session
    scope: StudyContext
    #: The population a new run records (``_population_for``); the Czech LIVE in every
    #: composition, another only in tests over a fictional contract.
    population_contract: PopulationImportContract = CZ_SYNTHETIC_V17
    population_id: str = CZ_LIVE

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
        sociomapping_enabled: bool = False,
        reservations: RunReservations | None = None,
        confirm_cost_usd: float | None = None,
        sociomap_methods: Sequence[SociomapMethod] | None = None,
        support: SupportSpec | None = None,
        aggregation: Mapping[str, Any] | None = None,
        response: ResponseProcessSpec | None = None,
        kept: Mapping[str, Any] | None = None,
        persona_source: PersonaSource = PersonaSource.FICTIONAL_ROSTER,
        population_version_id: str | None = None,
        frozen_dataset: FrozenDataset | None = None,
    ) -> StartedRun:
        """Run the research workflow over one Design Revision of the Study.

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
        ``support_methodology``, ``aggregation_methodology``, ``response_methodology``) of the
        run it retries. A retry passes that run's pins explicitly, so they are not resolved
        from what is in force here; without these records the new run would say its stored
        versions were the code's (plan ``methodology-tab`` Z1a). They are metadata only, never
        part of the run's key.

        The run records the population it names (``population_version_id``: a materialized
        child of the study's client, P4e2; LIVE when not given). A selected child is part of
        the run's identity, so the same revision over LIVE and over a child is two runs; a
        child that is not this client's raises
        :class:`~aia_core.domain.population.UnknownDatasetVersion`, as a scope miss does.

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
        module's preset becomes before it runs or is retried. A set the caller chooses over
        the default is part of the run's identity, so the same revision under two chosen
        sets is two runs; taking the default is not, so a start over a revision that has a
        run (made under an earlier default) returns that run and pays for nothing again.

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
        _spec, readiness = prepare(
            designs.content(revision.revision_id),
            pair_n_min=side_tables_of(methods).n_min,
        )
        if not readiness.ready:
            raise DesignNotReady(readiness)
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
        elif sociomap_methods is not None and methods != default_methods():
            # Only a set the caller chose over the default is new identity. A start that
            # takes the default keeps the key every earlier run of the revision has, so a
            # re-start after the default changes returns the run that exists -- with the
            # methods it pinned -- instead of paying for its fieldwork again.
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
        panel = persona_source is PersonaSource.PANEL
        if panel and fieldwork_source is not FieldworkSource.AI_RUNTIME:
            raise ValueError("panel personas answer only through the ai_runtime source")
        if panel:
            key += ":personas:panel"
        if frozen_dataset is not None:
            if not retry_of or not analysis_enabled:
                raise ValueError("an analysis retry names the run it retries, with analysis on")
            key += f":analysis-retry:{retry_of}"
        elif retry_of:
            key += f":retry:{retry_of}"
        # A retry's pins came from stored versions resolved when its original started.
        held = dict(kept or {})
        methodology = methodology or held.get("methodology")
        support_version = support_version or held.get("support_methodology")
        aggregation_version = aggregation_version or held.get("aggregation_methodology")
        response_version = response_version or held.get("response_methodology")
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
            if ceiling.total_usd is None:
                assert ceiling.unknown is not None
                raise CostCeilingUnknown(ceiling.unknown, limit_usd=limit)
            if ceiling.total_usd >= limit:
                if confirm_cost_usd is None or confirm_cost_usd < ceiling.total_usd:
                    raise CostConfirmationRequired(ceiling_usd=ceiling.total_usd, limit_usd=limit)
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
                **({"sociomapping_enabled": True} if sociomapping_enabled else {}),
                "sociomap_methods": pinned,
                **({"methodology": methodology} if methodology else {}),
                "support": support_pin,
                **({"support_methodology": support_version} if support_version else {}),
                "aggregation": aggregation_pin,
                **({"aggregation_methodology": aggregation_version} if aggregation_version else {}),
                "response": response_pin,
                **({"response_methodology": response_version} if response_version else {}),
                **({"retry_of": retry_of} if retry_of else {}),
                **({"analysis_retry": frozen_dataset.note()} if frozen_dataset else {}),
                "persona_source": persona_source.value,
                **(
                    {"population": _population_note(population, read_by_fieldwork=panel)}
                    if population
                    else {}
                ),
            },
            step_inputs={
                "compile": {"design_revision_id": revision.revision_id},
                "preflight": {"methods": pinned, "persona_source": persona_source.value},
                "run": {
                    "fieldwork_source": fieldwork_source.value,
                    "persona_source": persona_source.value,
                    "response": response_pin,
                    **({"frozen_dataset": frozen_dataset.step_input()} if frozen_dataset else {}),
                },
                "aggregate": {"support": support_pin, "aggregation": aggregation_pin},
                "sociomap": {"methods": pinned},
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
    ) -> StartedRun:
        """Start a failed or cancelled run again, as a new run linked to it.

        A retry spends again, so it asks again: the limit and the confirmation work as they do
        for :meth:`start`. It pins the Sociomap methods the run it retries pinned, never the
        current default; a run stored before methods were pinned retries as
        ``aia-sociomap-1``, the method that computed it. It keeps the original's persona
        source whatever the deployment's switch now says; a run stored before the source was
        pinned retries on the fictional roster, which answered it.
        """
        run = self.get(run_id)
        if not retryable(run["status"]):
            raise ResearchRunNotRetryable(run["status"])
        return self._restart(
            run,
            fieldwork_source=fieldwork_source,
            reservations=reservations,
            confirm_cost_usd=confirm_cost_usd,
        )

    def retry_analysis(
        self,
        run_id: str,
        *,
        frozen_dataset: FrozenDataset,
        reservations: RunReservations | None = None,
        confirm_cost_usd: float | None = None,
    ) -> StartedRun:
        """Start ``run_id`` again over its own collected data: an analysis retry.

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
    ) -> StartedRun:
        """A new run linked to ``run``, under every pin it recorded."""
        run_id = str(run["run_id"])
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
            sociomap_methods=read_methods(run["metadata"].get("sociomap_methods")),
            support=read_support_pin(run["metadata"].get("support")),
            aggregation=_aggregation_of(run["metadata"]),
            response=read_response_pin(run["metadata"].get("response")),
            kept={
                k: run["metadata"][k]
                for k in (
                    "methodology",
                    "support_methodology",
                    "aggregation_methodology",
                    "response_methodology",
                )
                if run["metadata"].get(k)
            },
            persona_source=persona_source_of(run["metadata"]),
        )

    def cancel(self, run_id: str, *, reason: str = "researcher") -> WorkflowRunStatus:
        """Cancel a run of this Study. Needs ``CANCEL_WORKFLOW``."""
        self.scope.require(Permission.CANCEL_WORKFLOW)
        self.get(run_id)
        return self._workflows().request_cancel(run_id, reason=reason)

    def lift_budget_wait(
        self, run_id: str, node_key: str, *, budget_usd: float, note: str = ""
    ) -> dict[str, Any]:
        """Raise the study's budget to ``budget_usd`` and let the waiting step go on.

        A step whose reservation would pass the budget stops in ``AWAITING_BUDGET``
        without spending an attempt; until a person lifts the wait it stays there
        (plan 5b.1). Needs ``APPROVE_BUDGET`` and ``MANAGE_STUDY_BUDGET`` on an open
        Study, which a worker's scope does not hold. ``budget_usd`` equal to the current
        budget lifts the wait without changing it (it was raised by hand), and below it
        is refused: this lifts a cap, it does not lower one.

        Checked before anything is written, so a refused lift changes nothing, not even
        the budget; the budget change and the resume share the caller's transaction.
        """
        self.scope.require(Permission.APPROVE_BUDGET)
        self.scope.require(Permission.MANAGE_STUDY_BUDGET)
        self.scope.require_open_study()
        run = self.get(run_id)
        step = next((s for s in run["steps"] if s["node_key"] == node_key), None)
        if step is None:
            raise ResearchStepNotFound(node_key)
        if step["status"] is not StepRunStatus.AWAITING_BUDGET:
            raise BudgetWaitNotLiftable("only a step waiting for budget can be lifted")
        scopes = ScopeRepository(self.session)
        current = float(scopes.get_study(self.scope).budget_usd)
        if budget_usd < current:
            raise BudgetNotRaised(offered=budget_usd, current=current)
        if budget_usd > current:
            scopes.set_study_budget(self.scope, budget_usd)
        self._workflows().resume_budget_wait(
            step["step_id"], note=note, budget_before=current, budget_after=budget_usd
        )
        return self.get(run_id)

    def readiness(
        self,
        design_revision_id: str,
        *,
        persona_source: PersonaSource = PersonaSource.FICTIONAL_ROSTER,
        fieldwork_source: FieldworkSource | None = None,
    ) -> tuple[ResearchSpecification | None, Readiness]:
        """Compile a revision of this Study and assess it, without starting anything, under
        the methodology a start would pin now (the one in force) and the persona source it
        would pin (a panel run applies the design's audience filters).

        With ``fieldwork_source`` ``ai_runtime`` the readiness also forecasts the run's
        evidence support (``domain.support_forecast``) under the support rules a start would
        pin: the donors fieldwork will draw and whether any number will be shown. Other
        sources answer by code (the workbench's fixture) and get no forecast."""
        designs = self._designs()
        revision = designs.get(design_revision_id)
        methods, _ = self._methods(None)
        spec, readiness = prepare(
            designs.content(revision.revision_id),
            pair_n_min=side_tables_of(methods).n_min,
            filters_applied=persona_source is PersonaSource.PANEL,
        )
        if spec is not None and fieldwork_source is FieldworkSource.AI_RUNTIME:
            support, _ = self._support(None)
            # The aggregation a start would pin, compiled as the aggregate reads it: a version
            # that replaces Kish's formula changes every cell's effective n.
            pin, _ = self._aggregation(None)
            _, slots = read_aggregation_pin(pin)
            readiness = with_support_forecast(
                readiness,
                forecast_support(spec, support=support, persona_source=persona_source, slots=slots),
                support=support,
            )
        return spec, readiness

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

    def runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        """This Study's research runs, newest first, with their phases."""
        project_id = self._designs().project_id()
        if project_id is None:
            return []
        runs = [
            r
            for r in self._workflows().list_runs(
                project_id=project_id, limit=limit, workflow_type=RESEARCH
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


@dataclass(frozen=True, slots=True)
class ResearchAgentJobs:
    """Design assistance is a durable job, never a request-time model call.

    Approved client memory is frozen at enqueue. Jobs only produce proposals;
    applying one requires EDIT_STUDY and its unchanged Design Revision.
    """

    session: Session
    scope: StudyContext
    #: The clients a draft prompt may be tested on (``AIA_AI_FICTIONAL_CLIENT_IDS``). Empty
    #: by default, so a caller that does not pass it can run no draft at all.
    draft_client_ids: frozenset[str] = frozenset()

    def start(
        self,
        *,
        design_revision_id: str,
        action: ResearchAction,
        instruction: str = "",
        prompt_version: int | None = None,
    ) -> StartedRun:
        """Queue one proposal. The prompt it runs is chosen here and frozen into the job.

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
            "action": action.value,
            "instruction": instruction,
            "snapshot": snapshot,
            "job_fingerprint": digest,
            "harness_version": HARNESS_VERSION,
            "prompt": prompt.model_dump(mode="json"),
        }
        project_id = designs.project_id()
        assert project_id is not None
        return start_workflow(
            self.session,
            self.scope,
            project_id=project_id,
            revision=revision.revision,
            workflow_type=RESEARCH_AGENT,
            idempotency_key=f"{RESEARCH_AGENT}:{design_revision_id}:{digest}",
            metadata={
                "design_revision_id": design_revision_id,
                "action": action.value,
                "context_sha256": snapshot_hash(snapshot),
                "harness_version": HARNESS_VERSION,
                "prompt_version": prompt.version,
                "prompt_origin": prompt.origin,
            },
            step_inputs={"agent": payload},
            owner=DESIGN_PROJECT_OWNER,
        )

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
        self, run_id: str, *, store: ArtifactStore, expected_revision_id: str
    ) -> tuple[DesignRevision, bool]:
        """A person applies what the agent job proposed: a new Design Revision, and its record.

        ADR 0019 gate 1. Needs ``APPROVE_GATE`` beside ``EDIT_STUDY``: the worker's scope holds
        the second and not the first (decision 6), so only a person accepts. The accept is
        written to the approval ledger in the same transaction as the revision (plan 5b.3).
        """
        self.scope.require(Permission.EDIT_STUDY)
        self.scope.require(Permission.APPROVE_GATE)
        self.scope.require_open_study()
        run = self.get(run_id)
        if expected_revision_id != run["metadata"]["design_revision_id"]:
            raise DesignRejected("proposal baseline does not match", reason="stale_proposal")
        result = self.result(run_id, store=store)
        action = ResearchAction(run["metadata"]["action"])
        stages = {
            ResearchAction.ANALYZE: "plan",
            ResearchAction.BUILD: "questionnaire",
            ResearchAction.OPTIMIZE: "questionnaire",
            ResearchAction.AUDIENCE: "audience",
            ResearchAction.DIMENSIONS: "persona",
        }
        if action not in stages:
            raise DesignRejected("an advice answer is not a design mutation", reason="advice_only")
        designs = StudyDesignRepository(self.session, self.scope)
        revision, created = designs.submit_if_current(
            content=result["result"]["project"],
            source_stage=stages[action],
            expected_revision_id=expected_revision_id,
        )
        project_id = designs.project_id()
        assert project_id is not None  # submit_if_current has just written to it
        WorkflowRepository(self.session, self.scope).record_ai_proposal_acceptance(
            run_id,
            action=action.value,
            revision_id=revision.revision_id,
            project_id=project_id,
            project_revision=revision.revision,
            created=created,
            artifact_id=str(run["steps"][0]["output"]["artifact_id"]),
        )
        return revision, created


def _aggregation_of(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """The aggregation a run pinned, as a retry pins it again. A run started before
    aggregation was pinned was computed as 18.6.6's port, so its retry is too."""
    stored = metadata.get("aggregation")
    if stored is None:
        return {"spec": dict(UNIT_AGGREGATION_PIN["spec"]), "formulas": {}}
    return {"spec": dict(stored["spec"]), "formulas": dict(stored.get("formulas") or {})}
