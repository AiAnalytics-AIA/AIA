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

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..domain.ai_contracts import canonical_json
from ..domain.analysis.steps import analysis_step_inputs
from ..domain.design import DESIGN_PROJECT_OWNER, DesignRejected, DesignRevision
from ..domain.evidence import ClaimSurface
from ..domain.fieldwork import FieldworkSource
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
from ..domain.run_cost import CeilingUnknown, RunCostCeiling, run_cost_ceiling
from ..domain.scope import OrganizationRole, Permission, StudyContext
from ..domain.workflow import StepRunStatus, WorkflowRunStatus
from ..domain.workflow_templates import RESEARCH, RESEARCH_AGENT
from ..infrastructure.artifact_repository import ArtifactRepository
from ..infrastructure.client_knowledge_repository import ClientKnowledgeRepository
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
from .workflows import StartedRun, start_workflow

__all__ = [
    "BudgetNotRaised",
    "CostCeilingUnknown",
    "CostConfirmationRequired",
    "DesignNotReady",
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
class RunReservations:
    """What the worker reserves per model request, as the API reads it from the same settings.

    ``None`` is not zero: the ceiling that needs a missing one is unknown.
    """

    fieldwork_usd: float | None
    analysis_usd: float | None


@dataclass(frozen=True, slots=True)
class ResearchRuns:
    """The research runs of the Study in scope. The caller owns the transaction."""

    session: Session
    scope: StudyContext

    def _designs(self) -> StudyDesignRepository:
        return StudyDesignRepository(self.session, self.scope)

    def _workflows(self) -> WorkflowRepository:
        return WorkflowRepository(self.session, self.scope)

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
    ) -> StartedRun:
        """Run the research workflow over one Design Revision of the Study.

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
        _spec, readiness = prepare(designs.content(revision.revision_id))
        if not readiness.ready:
            raise DesignNotReady(readiness)
        project_id = designs.project_id()
        assert project_id is not None  # a revision exists, so its design project does
        key = f"{RESEARCH}:{revision.revision_id}"
        if analysis_enabled:
            key += ":analysis"
        if sociomapping_enabled:
            key += ":sociomapping"
        if retry_of:
            key += f":retry:{retry_of}"
        confirmation: tuple[float, float] | None = None
        limit = self.spend_limit()
        if limit is not None and self._workflows().find_run_by_idempotency_key(key) is None:
            assert _spec is not None  # a ready design compiles
            ceiling = self.cost_ceiling(
                _spec,
                fieldwork_source=fieldwork_source,
                analysis_enabled=analysis_enabled,
                reservations=reservations,
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
                **({"retry_of": retry_of} if retry_of else {}),
            },
            step_inputs={
                "compile": {"design_revision_id": revision.revision_id},
                "run": {"fieldwork_source": fieldwork_source.value},
                **(analysis_step_inputs(ClaimSurface.INTERNAL) if analysis_enabled else {}),
            },
            owner=DESIGN_PROJECT_OWNER,
            analysis_enabled=analysis_enabled,
            sociomapping_enabled=sociomapping_enabled,
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
        for :meth:`start`.
        """
        run = self.get(run_id)
        if not retryable(run["status"]):
            raise ResearchRunNotRetryable(run["status"])
        return self.start(
            design_revision_id=str(run["metadata"]["design_revision_id"]),
            fieldwork_source=fieldwork_source,
            retry_of=run_id,
            analysis_enabled=bool(run["metadata"].get("analysis_enabled", False)),
            sociomapping_enabled=bool(run["metadata"].get("sociomapping_enabled", False)),
            reservations=reservations,
            confirm_cost_usd=confirm_cost_usd,
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

    def readiness(self, design_revision_id: str) -> tuple[ResearchSpecification | None, Readiness]:
        """Compile a revision of this Study and assess it, without starting anything."""
        designs = self._designs()
        revision = designs.get(design_revision_id)
        return prepare(designs.content(revision.revision_id))

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
