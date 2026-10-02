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
from ..domain.scope import OrganizationRole, Permission, StudyContext
from ..domain.workflow import WorkflowRunStatus
from ..domain.workflow_templates import RESEARCH, RESEARCH_AGENT
from ..infrastructure.artifact_repository import ArtifactRepository
from ..infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from ..infrastructure.prompt_repository import PromptRefused, PromptResolver
from ..infrastructure.storage import ArtifactStore
from ..infrastructure.study_design_repository import StudyDesignRepository
from ..infrastructure.workflow_repository import WorkflowNotFound, WorkflowRepository
from .workflows import StartedRun, start_workflow

__all__ = [
    "DesignNotReady",
    "ResearchAgentJobs",
    "ResearchRunNotFound",
    "ResearchRunNotRetryable",
    "ResearchRuns",
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

    def start(
        self,
        *,
        design_revision_id: str,
        fieldwork_source: FieldworkSource,
        retry_of: str | None = None,
        analysis_enabled: bool = False,
    ) -> StartedRun:
        """Run the research workflow over one Design Revision of the Study.

        Idempotent: the same revision starts one run, and so does retrying the
        same run -- a double submission gets the run that already exists. Needs
        ``RUN_WORKFLOW`` on an open Study. Raises
        :class:`~aia_core.infrastructure.study_design_repository.DesignRevisionNotFound`
        for a revision that is not this Study's.
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
        if retry_of:
            key += f":retry:{retry_of}"
        return start_workflow(
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
                **({"retry_of": retry_of} if retry_of else {}),
            },
            step_inputs={
                "compile": {"design_revision_id": revision.revision_id},
                "run": {"fieldwork_source": fieldwork_source.value},
                **(analysis_step_inputs(ClaimSurface.INTERNAL) if analysis_enabled else {}),
            },
            owner=DESIGN_PROJECT_OWNER,
            analysis_enabled=analysis_enabled,
        )

    def retry(self, run_id: str, *, fieldwork_source: FieldworkSource) -> StartedRun:
        """Start a failed or cancelled run again, as a new run linked to it."""
        run = self.get(run_id)
        if not retryable(run["status"]):
            raise ResearchRunNotRetryable(run["status"])
        return self.start(
            design_revision_id=str(run["metadata"]["design_revision_id"]),
            fieldwork_source=fieldwork_source,
            retry_of=run_id,
            analysis_enabled=bool(run["metadata"].get("analysis_enabled", False)),
        )

    def cancel(self, run_id: str, *, reason: str = "researcher") -> WorkflowRunStatus:
        """Cancel a run of this Study. Needs ``CANCEL_WORKFLOW``."""
        self.scope.require(Permission.CANCEL_WORKFLOW)
        self.get(run_id)
        return self._workflows().request_cancel(run_id, reason=reason)

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
        self.scope.require(Permission.EDIT_STUDY)
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
        return StudyDesignRepository(self.session, self.scope).submit_if_current(
            content=result["result"]["project"],
            source_stage=stages[action],
            expected_revision_id=expected_revision_id,
        )
