"""Deep Research runs of a research Study: freeze, start, read, cancel, and the bundle.

ADR 0017 as amended (plan decisions I-8 and I-9). :meth:`DeepResearchRuns.start`
freezes everything a run depends on -- the Design Revision, the subjects, the brief,
the questionnaire the leakage screen reads, the approved Client Knowledge the Study
may see and the client terms -- into one
:class:`~aia_core.domain.deep_research.contracts.DeepResearchRequest`, and enqueues
the ``deep_research`` graph on the Study's owned design project. From then on a
knowledge approval or a design edit changes nothing about the job. A later pass is a
new run over a new request, and reuses what did not change through its track
fingerprints.

A run is found only through the Study's design project and its type, as research
runs are (ADR 0016): a run of another Study, or of another type, is
:class:`DeepResearchRunNotFound`, whatever its id says. Its bundle and snapshots are
read only through the run.

**Not registered.** ``deep_research`` is not in ``WORKFLOW_TYPES`` and no API route
calls this service; the run is created from the domain's own step graph, which a
worker claims only if its registry has the kinds (``WorkQueue.claim(kinds=...)``).
Registering the type, the executors and a route is the integrator's (Job 6).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..domain.deep_research.bundle import EvidenceBundle
from ..domain.deep_research.contracts import (
    HARNESS_VERSION,
    Channel,
    DeepResearchRequest,
    SourceSnapshot,
)
from ..domain.deep_research.knowledge_access import client_terms, freeze_knowledge
from ..domain.deep_research.planning import (
    brief_digest,
    extract_subjects,
    preset,
    screen_questions,
)
from ..domain.deep_research.workflow import DEEP_RESEARCH, deep_research_steps
from ..domain.research import phase_of, retryable
from ..domain.scope import Permission, StudyContext
from ..domain.workflow import WorkflowRunStatus
from ..infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from ..infrastructure.scope_repository import ScopeRepository
from ..infrastructure.storage import ArtifactStore
from ..infrastructure.study_design_repository import StudyDesignRepository
from ..infrastructure.workflow_repository import WorkflowNotFound, WorkflowRepository
from .research import research_artifacts
from .workflows import StartedRun

__all__ = [
    "BundleNotReady",
    "DeepResearchRunNotFound",
    "DeepResearchRunNotRetryable",
    "DeepResearchRuns",
    "NothingToResearch",
]


class DeepResearchRunNotFound(LookupError):
    """No Deep Research run with this id in the Study in scope."""


class DeepResearchRunNotRetryable(Exception):
    """Only a failed or cancelled run may be started again."""

    def __init__(self, status: WorkflowRunStatus) -> None:
        super().__init__(f"a {status.value} run cannot be retried")
        self.status = status


class NothingToResearch(Exception):
    """The Design Revision holds no research question, goal or tracked object."""


class BundleNotReady(Exception):
    """The run has not published a bundle (yet), or what it stored is not one."""

    def __init__(self, message: str, *, status: WorkflowRunStatus | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True, slots=True)
class DeepResearchRuns:
    """The Deep Research runs of the Study in scope. The caller owns the transaction."""

    session: Session
    scope: StudyContext

    def _designs(self) -> StudyDesignRepository:
        return StudyDesignRepository(self.session, self.scope)

    def _workflows(self) -> WorkflowRepository:
        return WorkflowRepository(self.session, self.scope)

    # -- freeze and start -------------------------------------------------------

    def freeze(
        self,
        *,
        design_revision_id: str,
        preset_name: str,
        channels: Sequence[Channel] = (Channel.INTERNAL, Channel.WEB),
    ) -> DeepResearchRequest:
        """The request a run over this revision would be frozen to. Writes nothing.

        Raises ``DesignRevisionNotFound`` for a revision that is not this Study's,
        :class:`~aia_core.domain.deep_research.planning.UnknownPreset` for a depth
        that does not exist (there is no default depth, DR-5), and
        :class:`NothingToResearch` for a design with no subject yet.
        """
        depth = preset(preset_name)
        designs = self._designs()
        revision = designs.get(design_revision_id)
        content = designs.content(revision.revision_id)
        # The study's own client's approved knowledge, never another's (ADR 0015):
        # the client comes from the issued scope, not from any argument.
        knowledge = freeze_knowledge(ClientKnowledgeRepository(self.session).for_study(self.scope))
        subjects = extract_subjects(content, knowledge)
        if not subjects:
            raise NothingToResearch("the design has no research question, goal or tracked object")
        scopes = ScopeRepository(self.session)
        client = scopes.client_of_study(self.scope)
        study = scopes.get_study(self.scope)
        return DeepResearchRequest(
            harness_version=HARNESS_VERSION,
            design_revision_id=revision.revision_id,
            design_revision=revision.revision,
            preset=depth.name,
            channels=tuple(channels),
            brief=brief_digest(content),
            subjects=subjects,
            questionnaire=screen_questions(content),
            knowledge=knowledge,
            client_terms=client_terms(
                identity=[
                    ("client.name", client.name),
                    ("client.slug", client.slug),
                    ("study.name", study.name),
                    ("study.slug", study.slug),
                ],
                knowledge=knowledge,
            ),
        )

    def start(
        self,
        *,
        design_revision_id: str,
        preset_name: str,
        channels: Sequence[Channel] = (Channel.INTERNAL, Channel.WEB),
        retry_of: str | None = None,
    ) -> StartedRun:
        """Freeze a request over one Design Revision and enqueue a run of it.

        Idempotent per request: the same revision, depth, channels, knowledge and
        terms start one run, so a double submission gets the run that exists; an
        approval in between is a different request and a new run. Needs
        ``RUN_WORKFLOW`` on an open Study, checked before anything is read.
        """
        self.scope.require(Permission.RUN_WORKFLOW)
        self.scope.require_open_study()
        request = self.freeze(
            design_revision_id=design_revision_id, preset_name=preset_name, channels=channels
        )
        project_id = self._designs().project_id()
        assert project_id is not None  # a revision exists, so its design project does
        request_fingerprint = request.fingerprint()
        steps = deep_research_steps()
        key = f"{DEEP_RESEARCH}:{request.design_revision_id}:{request_fingerprint}"
        if retry_of:
            key += f":retry:{retry_of}"
        workflows = self._workflows()
        existing = workflows.find_run_by_idempotency_key(key)
        run_id = workflows.create_run(
            project_id=project_id,
            project_revision=request.design_revision,
            workflow_type=DEEP_RESEARCH,
            steps=steps,
            idempotency_key=key,
            metadata={
                "design_revision_id": request.design_revision_id,
                "design_revision": request.design_revision,
                "request_fingerprint": request_fingerprint,
                "harness_version": HARNESS_VERSION,
                "preset": request.preset,
                "channels": [c.value for c in request.channels],
                "subjects": len(request.subjects),
                "knowledge_items": len(request.knowledge.items),
                "omitted_knowledge_ids": list(request.knowledge.omitted_ids),
                **({"retry_of": retry_of} if retry_of else {}),
            },
            # Each step's fingerprint is the request's: a re-run after a crash is
            # the same work, and the artifacts it stored are found by their own.
            fingerprints={s.node_key: request_fingerprint for s in steps},
            step_inputs={"plan": {"request": request.model_dump(mode="json")}},
        )
        return StartedRun(
            run_id=run_id,
            project_id=project_id,
            project_revision=request.design_revision,
            workflow_type=DEEP_RESEARCH,
            created=existing is None,
            run=workflows.get_run(run_id),
        )

    def retry(self, run_id: str) -> StartedRun:
        """Start a failed or cancelled run again, as a new run linked to it.

        Frozen afresh: what changed since -- an approval, a revoked item -- is in the
        new request. What the earlier run stored is found by fingerprint, so a track,
        a snapshot or a verification it completed is not bought again.
        """
        run = self.get(run_id)
        if not retryable(run["status"]):
            raise DeepResearchRunNotRetryable(run["status"])
        metadata = run["metadata"]
        return self.start(
            design_revision_id=str(metadata["design_revision_id"]),
            preset_name=str(metadata["preset"]),
            channels=[Channel(c) for c in metadata["channels"]],
            retry_of=run_id,
        )

    def cancel(self, run_id: str, *, reason: str = "researcher") -> WorkflowRunStatus:
        """Cancel a run of this Study. Needs ``CANCEL_WORKFLOW``."""
        self.scope.require(Permission.CANCEL_WORKFLOW)
        self.get(run_id)
        return self._workflows().request_cancel(run_id, reason=reason)

    # -- read -------------------------------------------------------------------

    def get(self, run_id: str) -> dict[str, Any]:
        """One Deep Research run of this Study, in full, with its phase."""
        project_id = self._designs().project_id()
        try:
            run = self._workflows().get_run(run_id)
        except WorkflowNotFound as exc:
            raise DeepResearchRunNotFound(run_id) from exc
        # Scope already confined the run to this Study; the design project and the
        # type confine it to this Study's Deep Research.
        if project_id is None or run["project_id"] != project_id:
            raise DeepResearchRunNotFound(run_id)
        if run["workflow_type"] != DEEP_RESEARCH:
            raise DeepResearchRunNotFound(run_id)
        run["attempted"] = any(s["attempts"] for s in run["steps"])
        run["phase"] = phase_of(run["status"], attempted=run["attempted"])
        run["retryable"] = retryable(run["status"])
        return run

    def runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        """This Study's Deep Research runs, newest first, with their phases."""
        project_id = self._designs().project_id()
        if project_id is None:
            return []
        runs = self._workflows().list_runs(
            project_id=project_id, limit=limit, workflow_type=DEEP_RESEARCH
        )
        for r in runs:
            r["phase"] = phase_of(r["status"], attempted=r["attempted"])
            r["retryable"] = retryable(r["status"])
        return runs

    def events(self, run_id: str, *, since: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        """The run's append-only events after ``since``: tool calls and counts included."""
        self.get(run_id)
        return self._workflows().events(run_id, since=since, limit=limit)

    def bundle(self, run_id: str, *, store: ArtifactStore) -> EvidenceBundle:
        """The sealed evidence bundle this run published, verified against its seal.

        Raises :class:`BundleNotReady` while the run has not published one, and when
        what it stored no longer hashes to its seal.
        """
        self.scope.require(Permission.VIEW_RESULTS)
        run = self.get(run_id)
        publish = next(s for s in run["steps"] if s["node_key"] == "publish")
        artifact_id = (publish.get("output") or {}).get("artifact_id")
        if not artifact_id:
            raise BundleNotReady("the run has published no bundle", status=run["status"])
        payload = research_artifacts(self.session, self.scope, store).read_json(str(artifact_id))
        bundle = EvidenceBundle.model_validate(payload["bundle"])
        if not bundle.verify():
            raise BundleNotReady("the stored bundle does not hash to its seal")
        if bundle.request_fingerprint != run["metadata"].get("request_fingerprint"):
            raise BundleNotReady("the stored bundle is not this run's request")
        return bundle

    def snapshot(self, run_id: str, snapshot_id: str, *, store: ArtifactStore) -> SourceSnapshot:
        """One source a finding of this run rests on, as it was captured.

        Only a snapshot the run's own bundle lists: a snapshot id from anywhere
        else reads nothing, whatever it names.
        """
        bundle = self.bundle(run_id, store=store)
        ref = next((s for s in bundle.snapshots if s.snapshot_id == snapshot_id), None)
        if ref is None:
            raise DeepResearchRunNotFound(snapshot_id)
        payload = research_artifacts(self.session, self.scope, store).read_json(ref.artifact_id)
        snapshot = SourceSnapshot.model_validate(payload["snapshot"])
        if snapshot.snapshot_id != ref.snapshot_id or snapshot.text_sha256 != ref.text_sha256:
            raise BundleNotReady("the stored snapshot is not the one the bundle cites")
        return snapshot
