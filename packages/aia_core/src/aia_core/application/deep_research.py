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

**Purpose, target and frozen lineage** (ADR 0021). A governed run is started from a
:class:`~aia_core.domain.deep_research.integration.DeepResearchRunSpec`: *why*
(``DESIGN_RESEARCH`` before the methodology freeze, ``INTERPRETATION_RESEARCH`` over
results that exist), *what* (a typed target) and *which immutable state* (the Design
Revision's hash; for interpretation every artifact of the producing research run the
target rests on, pinned by id and SHA256). The spec is the run's identity and is stored
with the run; the engine request inside it, and so every engine fingerprint, is the one
this module froze before ADR 0021. :meth:`freeze_design` is the design-side freeze;
:meth:`freeze_interpretation` the result-side one. Interpretation Research is frozen, never
enqueued, until chunk 30: :meth:`_enqueue`, where every run is created, refuses its spec
(:class:`InterpretationNotReady`, OI-88). A run stored before the contract reads as
``legacy-unversioned``: nothing is back-filled.

**Registered and parked by default.** The API route (``routers/deep_research.py``) calls
this service, and the worker's default registry holds the six executors; the worker
composes a runtime only with ``AIA_DEEP_RESEARCH_ENABLED`` (off on develop), and a run
parks without one. ``deep_research`` is not a ``WORKFLOW_TYPES`` template: the run is
created from the domain's own step graph.

**A study's spend limit asks first** (ADR 0019 gate 2, plan
``deep-research-web-search.md`` chunk 22), as a research run's start does: when the
Study has a limit and a start would create a run, the run's cost ceiling is worked out
here from the frozen request, its preset and the prices the caller states
(:func:`~aia_core.domain.run_cost.deep_research_cost_ceiling`), never taken from the
request. A ceiling at or above the limit needs ``confirm_cost_usd`` to cover it, and
the yes is recorded once, in the approval ledger, with the run; a ceiling that cannot
be worked out is not let by.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..domain.deep_research.budgets import ResearchMode, track_counts
from ..domain.deep_research.bundle import EvidenceBundle
from ..domain.deep_research.contracts import (
    HARNESS_VERSION,
    Channel,
    DeepResearchRequest,
    SourceSnapshot,
    digest,
)
from ..domain.deep_research.integration import (
    AGGREGATE_ARTIFACT,
    DATASET_ARTIFACT,
    LEGACY_UNVERSIONED,
    RUN_SPEC_CONTRACT,
    SPECIFICATION_ARTIFACT,
    AnalysisModuleTarget,
    ArtifactPin,
    DeepResearchProvenance,
    DeepResearchPurpose,
    DeepResearchRunSpec,
    DesignLineage,
    DesignRevisionTarget,
    FrozenLineage,
    InterpretationLineage,
    PurposeSource,
    ResearchTargetRef,
    ResultBatteryObjectTarget,
    ResultQuestionTarget,
    SociomapObjectTarget,
    SociomapRelationshipTarget,
    SociomapTarget,
    run_spec_identity,
    target_node,
)
from ..domain.deep_research.knowledge_access import client_terms, freeze_knowledge
from ..domain.deep_research.planning import (
    PRESET_TABLE_VERSION,
    brief_digest,
    extract_subjects,
    preset,
    screen_questions,
)
from ..domain.deep_research.workflow import DEEP_RESEARCH, deep_research_steps
from ..domain.research import phase_of, retryable
from ..domain.run_cost import (
    CeilingUnknown,
    DeepResearchCeiling,
    DeepResearchPrices,
    deep_research_cost_ceiling,
)
from ..domain.scope import Permission, StudyContext
from ..domain.workflow import StepRunStatus, WorkflowRunStatus
from ..infrastructure.artifact_repository import ArtifactNotFound, ArtifactStatus
from ..infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from ..infrastructure.scope_repository import ScopeRepository
from ..infrastructure.storage import ArtifactStore
from ..infrastructure.study_design_repository import StudyDesignRepository
from ..infrastructure.workflow_repository import WorkflowNotFound, WorkflowRepository
from .research import (
    CostCeilingUnknown,
    CostConfirmationRequired,
    ResearchRunNotFound,
    ResearchRuns,
    research_artifacts,
)
from .workflows import StartedRun

__all__ = [
    "BundleNotReady",
    "DeepResearchRunNotFound",
    "DeepResearchRunNotRetryable",
    "DeepResearchRuns",
    "GovernedRecord",
    "InterpretationNotReady",
    "LineageChanged",
    "NothingToResearch",
    "ResearchTargetInvalid",
    "ResearchTargetNotFound",
    "RunNotGoverned",
    "RunSpecCorrupt",
    "governed_record",
    "run_spec_metadata",
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


class ResearchTargetNotFound(LookupError):
    """The target, or an artifact it rests on, is not this Study's (or does not exist)."""


class ResearchTargetInvalid(ValueError):
    """The target does not fit its purpose, or names something its artifact does not hold."""


class LineageChanged(Exception):
    """A retry would no longer rest on the exact artifacts its run was anchored to."""


class InterpretationNotReady(Exception):
    """Interpretation Research may be frozen, never enqueued, until chunk 30 (ADR 0021).

    Its engine request would still be the one frozen from the producing run's Design
    Revision, so a run would be labelled as interpreting a result while researching the
    design's subjects. Chunk 30 derives the mission from the exact target, builds the
    engine request from it, and enables enqueueing together with the result-side route.
    """

    code = "interpretation_not_ready"

    def __init__(self) -> None:
        super().__init__(
            "Interpretation Research cannot run yet: its research mission is not derived "
            "from the target until chunk 30 (OI-88); the target and lineage freeze is available"
        )


class RunSpecCorrupt(ValueError):
    """A stored run spec no longer hashes to the fingerprint stored with it."""


class RunNotGoverned(Exception):
    """A run stored before ADR 0021: it has no purpose, target or lineage to cite."""


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

    def spend_limit(self) -> float | None:
        """The study's limit above which starting a run asks for confirmation; ``None``: never."""
        return ScopeRepository(self.session).get_study(self.scope).spend_confirm_usd

    @staticmethod
    def cost_ceiling(
        request: DeepResearchRequest,
        *,
        prices: DeepResearchPrices,
        modes: Collection[ResearchMode] = tuple(ResearchMode),
    ) -> DeepResearchCeiling:
        """The most a run of ``request`` can cost: its preset's bounds, priced.

        ``modes`` are the modes the deployment may research in; every mode, the highest
        ceiling, when the caller does not know the composition's switches.
        """
        depth = preset(request.preset)
        return deep_research_cost_ceiling(depth, track_counts(request, depth), prices, modes=modes)

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

    def freeze_design(
        self,
        *,
        design_revision_id: str,
        preset_name: str,
        channels: Sequence[Channel] = (Channel.INTERNAL, Channel.WEB),
        title: str | None = None,
    ) -> DeepResearchRunSpec:
        """The ``DESIGN_RESEARCH`` spec over one Design Revision. Writes nothing.

        The engine request is exactly :meth:`freeze`'s; the target is the revision and the
        lineage its id, number and content hash. Running it changes no design: what it
        finds can only become a proposal a person accepts into a new revision.
        """
        request = self.freeze(
            design_revision_id=design_revision_id, preset_name=preset_name, channels=channels
        )
        revision = self._designs().get(request.design_revision_id)
        return DeepResearchRunSpec(
            contract_version=RUN_SPEC_CONTRACT,
            purpose=DeepResearchPurpose.DESIGN_RESEARCH,
            target=DesignRevisionTarget(
                kind="DESIGN_REVISION", design_revision_id=revision.revision_id
            ),
            lineage=DesignLineage(
                kind="DESIGN",
                design_revision_id=revision.revision_id,
                design_revision=revision.revision,
                design_content_sha256=revision.content_sha256,
            ),
            engine_request=request,
            title=title,
        )

    def freeze_interpretation(
        self,
        *,
        target: ResearchTargetRef,
        preset_name: str,
        store: ArtifactStore,
        channels: Sequence[Channel] = (Channel.INTERNAL, Channel.WEB),
        title: str | None = None,
    ) -> DeepResearchRunSpec:
        """The ``INTERPRETATION_RESEARCH`` spec over one result of this Study. Writes nothing.

        The target's research run is found only through this Study
        (:class:`~aia_core.application.research.ResearchRuns`); its ``compile``, ``run`` and
        ``aggregate`` outputs and the target's own artifact are pinned by id and SHA256,
        each read and verified now, and the target's entity must be in the artifact it
        names. The engine request is frozen from the Design Revision that run executed.

        Raises :class:`ResearchTargetInvalid` for a design target or an entity its
        artifact does not hold, :class:`ResearchTargetNotFound` for a run or an artifact
        that is not this Study's, or not the one the run produced, and lets the store's
        ``IntegrityError`` / ``ObjectNotFound`` through for corrupt bytes (the caller
        commits the ``CORRUPT`` mark, ``artifacts.md`` § Read protocol). Never the latest
        result: exactly the artifact named, or nothing.
        """
        lineage = self._interpretation_lineage(target, store=store)
        request = self.freeze(
            design_revision_id=lineage.design.design_revision_id,
            preset_name=preset_name,
            channels=channels,
        )
        return DeepResearchRunSpec(
            contract_version=RUN_SPEC_CONTRACT,
            purpose=DeepResearchPurpose.INTERPRETATION_RESEARCH,
            target=target,
            lineage=lineage,
            engine_request=request,
            title=title,
        )

    def _interpretation_lineage(
        self, target: ResearchTargetRef, *, store: ArtifactStore
    ) -> InterpretationLineage:
        node = target_node(target)
        if node is None:
            raise ResearchTargetInvalid("Interpretation Research targets a result, not a design")
        target_key, target_artifact_id, target_type = node
        assert not isinstance(target, DesignRevisionTarget)
        try:
            run = ResearchRuns(self.session, self.scope).get(target.research_run_id)
        except ResearchRunNotFound as exc:
            raise ResearchTargetNotFound(target.research_run_id) from exc
        steps = {s["node_key"]: s for s in run["steps"]}
        expected = {
            "compile": SPECIFICATION_ARTIFACT,
            "run": DATASET_ARTIFACT,
            "aggregate": AGGREGATE_ARTIFACT,
            target_key: target_type,
        }
        repo = research_artifacts(self.session, self.scope, store)
        pins: list[ArtifactPin] = []
        payloads: dict[str, Any] = {}
        for node_key in sorted(expected):
            step = steps.get(node_key)
            output = (step or {}).get("output") or {}
            artifact_id = output.get("artifact_id")
            if step is None or step["status"] is not StepRunStatus.SUCCEEDED or not artifact_id:
                raise ResearchTargetNotFound(f"the run produced no {node_key} result")
            if node_key == target_key and artifact_id != target_artifact_id:
                # The target names an artifact this run's step did not produce: never
                # reinterpreted as the one it did, whatever is newer.
                raise ResearchTargetNotFound(target_artifact_id)
            try:
                artifact = repo.get(str(artifact_id))
            except ArtifactNotFound as exc:
                raise ResearchTargetNotFound(str(artifact_id)) from exc
            if artifact.artifact_type != expected[node_key]:
                raise ResearchTargetInvalid(f"{artifact_id} is not a {expected[node_key]}")
            if artifact.status is not ArtifactStatus.VALID:
                raise ResearchTargetInvalid(f"{artifact_id} is {artifact.status.value}")
            payloads[node_key] = repo.read_json(artifact.artifact_id)  # verified: SHA256
            pins.append(
                ArtifactPin(
                    node_key=node_key,
                    artifact_id=artifact.artifact_id,
                    artifact_type=artifact.artifact_type,
                    sha256=artifact.sha256,
                )
            )
        _require_entity(target, payloads[target_key])
        revision = self._designs().get(str(run["metadata"]["design_revision_id"]))
        return InterpretationLineage(
            kind="INTERPRETATION",
            research_run_id=run["run_id"],
            design=DesignLineage(
                kind="DESIGN",
                design_revision_id=revision.revision_id,
                design_revision=revision.revision,
                design_content_sha256=revision.content_sha256,
            ),
            artifacts=tuple(pins),
        )

    def start(
        self,
        *,
        design_revision_id: str,
        preset_name: str,
        channels: Sequence[Channel] = (Channel.INTERNAL, Channel.WEB),
        retry_of: str | None = None,
        prices: DeepResearchPrices | None = None,
        modes: Collection[ResearchMode] = tuple(ResearchMode),
        confirm_cost_usd: float | None = None,
        purpose_source: PurposeSource = PurposeSource.EXPLICIT,
        title: str | None = None,
    ) -> StartedRun:
        """Start ``DESIGN_RESEARCH`` over one Design Revision (:meth:`freeze_design`).

        ``purpose_source`` records how the purpose was stated: the deployed start API
        names none, and a new request through it is Design Research by ADR 0021's
        compatibility rule (``LEGACY_DEFAULT``). It is recorded, never identity.
        """
        self.scope.require(Permission.RUN_WORKFLOW)
        self.scope.require_open_study()
        spec = self.freeze_design(
            design_revision_id=design_revision_id,
            preset_name=preset_name,
            channels=channels,
            title=title,
        )
        return self._enqueue(
            spec,
            purpose_source=purpose_source,
            retry_of=retry_of,
            prices=prices,
            modes=modes,
            confirm_cost_usd=confirm_cost_usd,
        )

    def start_interpretation(
        self,
        *,
        target: ResearchTargetRef,
        preset_name: str,
        store: ArtifactStore,
        channels: Sequence[Channel] = (Channel.INTERNAL, Channel.WEB),
        retry_of: str | None = None,
        prices: DeepResearchPrices | None = None,
        modes: Collection[ResearchMode] = tuple(ResearchMode),
        confirm_cost_usd: float | None = None,
        title: str | None = None,
    ) -> StartedRun:
        """Start ``INTERPRETATION_RESEARCH`` over one result: refused until chunk 30.

        The target, its scope and its lineage are resolved first (:meth:`freeze_interpretation`),
        so a target of another Study, a missing entity or a corrupt artifact fails as it
        would; then the enqueue boundary refuses the spec (:class:`InterpretationNotReady`).
        Chunk 30 derives the research mission from the target and enables this with its
        route.
        """
        self.scope.require(Permission.RUN_WORKFLOW)
        self.scope.require_open_study()
        spec = self.freeze_interpretation(
            target=target, preset_name=preset_name, store=store, channels=channels, title=title
        )
        return self._enqueue(
            spec,
            purpose_source=PurposeSource.EXPLICIT,
            retry_of=retry_of,
            prices=prices,
            modes=modes,
            confirm_cost_usd=confirm_cost_usd,
        )

    def _enqueue(
        self,
        spec: DeepResearchRunSpec,
        *,
        purpose_source: PurposeSource,
        retry_of: str | None,
        prices: DeepResearchPrices | None,
        modes: Collection[ResearchMode],
        confirm_cost_usd: float | None,
    ) -> StartedRun:
        """Enqueue a run of ``spec``, idempotently.

        Idempotent per spec: the same purpose, target, lineage and engine request start
        one run, so a double submission gets the run that exists; an approval in between
        is a different engine request and a new run, and so is a different purpose or
        target over the same request. Each step's fingerprint stays the engine request's,
        so the engine's reuse across runs is unchanged.

        When the Study has a spend limit and this would create a run, the run's cost
        ceiling is worked out from ``prices`` (the deployment's, never the request's)
        over ``modes``. A ceiling at or above the limit needs ``confirm_cost_usd`` to
        cover it (:class:`~aia_core.application.research.CostConfirmationRequired`
        otherwise) and the yes is recorded in the approval ledger with the run. No
        prices, or a price the run needs missing, is
        :class:`~aia_core.application.research.CostCeilingUnknown`: not let by. A start
        that finds its run already there spends nothing and asks nothing.

        **The one enqueue boundary.** Every run is created here, and an
        ``INTERPRETATION_RESEARCH`` spec is refused before anything is read, priced or
        written (:class:`InterpretationNotReady`): until chunk 30 its engine request would
        research the design's subjects under an interpretation label.
        """
        if spec.purpose is DeepResearchPurpose.INTERPRETATION_RESEARCH:
            raise InterpretationNotReady()
        request = spec.engine_request
        project_id = self._designs().project_id()
        assert project_id is not None  # a revision exists, so its design project does
        request_fingerprint = request.fingerprint()
        spec_fingerprint = spec.fingerprint()
        steps = deep_research_steps()
        key = f"{DEEP_RESEARCH}:spec:{spec_fingerprint}"
        if retry_of:
            key += f":retry:{retry_of}"
        workflows = self._workflows()
        existing = workflows.find_run_by_idempotency_key(key)
        confirmation: tuple[float, float] | None = None
        ceiling: DeepResearchCeiling | None = None
        limit = self.spend_limit()
        if limit is not None and existing is None:
            if prices is None:
                raise CostCeilingUnknown(
                    CeilingUnknown.DEEP_RESEARCH_PRICE_MISSING, limit_usd=limit
                )
            ceiling = self.cost_ceiling(request, prices=prices, modes=modes)
            if ceiling.total_usd is None:
                assert ceiling.unknown is not None
                raise CostCeilingUnknown(
                    ceiling.unknown,
                    limit_usd=limit,
                    kinds=tuple(k.value for k in ceiling.unknown_kinds),
                )
            if ceiling.total_usd >= limit:
                if confirm_cost_usd is None or confirm_cost_usd < ceiling.total_usd:
                    raise CostConfirmationRequired(ceiling_usd=ceiling.total_usd, limit_usd=limit)
                confirmation = (ceiling.total_usd, limit)
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
                "preset_table": PRESET_TABLE_VERSION,
                # ADR 0021: why, what and on which immutable state. The engine request
                # itself is the plan step's input, below.
                **run_spec_metadata(spec, purpose_source=purpose_source),
                **(
                    {"cost_ceiling_usd": ceiling.total_usd, "cost_ceiling_mode": ceiling.mode.value}
                    if ceiling is not None
                    else {}
                ),
                **({"retry_of": retry_of} if retry_of else {}),
            },
            # Each step's fingerprint is the engine request's: a re-run after a crash is
            # the same work, and the artifacts it stored are found by their own.
            fingerprints={s.node_key: request_fingerprint for s in steps},
            step_inputs={"plan": {"request": request.model_dump(mode="json")}},
        )
        if confirmation is not None and existing is None:
            assert confirm_cost_usd is not None
            workflows.record_spend_confirmation(
                run_id,
                ceiling_usd=confirmation[0],
                limit_usd=confirmation[1],
                confirmed_usd=confirm_cost_usd,
            )
        return StartedRun(
            run_id=run_id,
            project_id=project_id,
            project_revision=request.design_revision,
            workflow_type=DEEP_RESEARCH,
            created=existing is None,
            run=workflows.get_run(run_id),
        )

    def retry(
        self,
        run_id: str,
        *,
        prices: DeepResearchPrices | None = None,
        modes: Collection[ResearchMode] = tuple(ResearchMode),
        confirm_cost_usd: float | None = None,
        store: ArtifactStore | None = None,
    ) -> StartedRun:
        """Start a failed or cancelled run again, as a new run linked to it.

        Frozen afresh, as before ADR 0021: what changed since -- an approval, a revoked
        item -- is in the new engine request, and what the earlier run stored is found
        by fingerprint, so a track, a snapshot or a verification it completed is not
        bought again. The *target* is never re-chosen: a design run retries over its
        revision. A run stored before ADR 0021 retries as a new Design Research run through
        the legacy rule. A stored ``INTERPRETATION_RESEARCH`` row -- which no code path can
        create until chunk 30 -- is :class:`InterpretationNotReady` before anything is
        frozen or read. A retry can spend again, so it asks again, as :meth:`start` does.
        ``store`` is accepted for the result-side retry chunk 30 enables.
        """
        run = self.get(run_id)
        if not retryable(run["status"]):
            raise DeepResearchRunNotRetryable(run["status"])
        metadata = run["metadata"]
        record = governed_record(metadata)
        if record is not None and record.purpose is DeepResearchPurpose.INTERPRETATION_RESEARCH:
            raise InterpretationNotReady()
        del store  # read by the result-side retry, from chunk 30
        return self.start(
            design_revision_id=str(metadata["design_revision_id"]),
            preset_name=str(metadata["preset"]),
            channels=[Channel(c) for c in metadata["channels"]],
            retry_of=run_id,
            prices=prices,
            modes=modes,
            confirm_cost_usd=confirm_cost_usd,
            purpose_source=(
                PurposeSource.LEGACY_DEFAULT
                if record is None
                else PurposeSource(str(metadata.get("purpose_source", "EXPLICIT")))
            ),
            title=record.title if record is not None else None,
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

    # -- purpose, target and lineage (ADR 0021) ----------------------------------

    def provenance(self, run_id: str, *, store: ArtifactStore) -> DeepResearchProvenance:
        """What a governed run's evidence cites: purpose, target, lineage and the bundle.

        The bundle is read and verified against its seal (:meth:`bundle`); the envelope
        names it by its artifact id and the row's SHA256 beside the seal, and changes
        nothing in it. The stored spec's fingerprint is recomputed from what is stored
        and must match. A run stored before ADR 0021 is :class:`RunNotGoverned`.
        """
        run = self.get(run_id)
        record = governed_record(run["metadata"])
        if record is None:
            raise RunNotGoverned(f"{run_id} was started before ADR 0021 ({LEGACY_UNVERSIONED})")
        bundle = self.bundle(run_id, store=store)
        publish = next(s for s in run["steps"] if s["node_key"] == "publish")
        artifact_id = str((publish.get("output") or {})["artifact_id"])
        artifact = research_artifacts(self.session, self.scope, store).get(artifact_id)
        return DeepResearchProvenance(
            contract_version=RUN_SPEC_CONTRACT,
            run_id=run["run_id"],
            purpose=record.purpose,
            target=record.target,
            lineage=record.lineage,
            run_spec_fingerprint=record.run_spec_fingerprint,
            engine_request_fingerprint=record.engine_request_fingerprint,
            evidence_bundle_artifact_id=artifact.artifact_id,
            evidence_bundle_artifact_sha256=artifact.sha256,
            evidence_bundle_seal=bundle.sha256,
        )

    def resolve_lineage(
        self, run_id: str, *, store: ArtifactStore
    ) -> InterpretationLineage | DesignLineage:
        """A governed run's lineage, re-resolved now: every pin read, verified and compared.

        Design lineage: the revision still has the stored number and content hash.
        Interpretation lineage: each pinned artifact is this Study's, ``VALID``, of the
        pinned type, and its bytes still hash to the pinned SHA256. Any difference is
        :class:`LineageChanged`; corrupt bytes raise from the store.
        """
        run = self.get(run_id)
        record = governed_record(run["metadata"])
        if record is None:
            raise RunNotGoverned(f"{run_id} was started before ADR 0021 ({LEGACY_UNVERSIONED})")
        lineage = record.lineage
        design = lineage if isinstance(lineage, DesignLineage) else lineage.design
        revision = self._designs().get(design.design_revision_id)
        if (revision.revision, revision.content_sha256) != (
            design.design_revision,
            design.design_content_sha256,
        ):
            raise LineageChanged(f"{design.design_revision_id} no longer reads as pinned")
        if isinstance(lineage, InterpretationLineage):
            repo = research_artifacts(self.session, self.scope, store)
            for pin in lineage.artifacts:
                try:
                    artifact = repo.get(pin.artifact_id)
                except ArtifactNotFound as exc:
                    raise LineageChanged(f"{pin.artifact_id} is gone") from exc
                if (artifact.artifact_type, artifact.sha256, artifact.status) != (
                    pin.artifact_type,
                    pin.sha256,
                    ArtifactStatus.VALID,
                ):
                    raise LineageChanged(f"{pin.artifact_id} is not the artifact pinned")
                repo.read(pin.artifact_id)  # its bytes still hash to the pin
        return lineage


def run_spec_metadata(
    spec: DeepResearchRunSpec, *, purpose_source: PurposeSource
) -> dict[str, Any]:
    """What a run's metadata holds of its spec (ADR 0021): read back by :func:`governed_record`.

    The engine request is not here: it is the plan step's input, and its fingerprint is
    the metadata's ``request_fingerprint``.
    """
    return {
        "integration_contract": spec.contract_version,
        "purpose": spec.purpose.value,
        "purpose_source": purpose_source.value,
        "target": spec.target.model_dump(mode="json"),
        "lineage": spec.lineage.model_dump(mode="json"),
        "run_spec_fingerprint": spec.fingerprint(),
        **({"title": spec.title} if spec.title is not None else {}),
    }


@dataclass(frozen=True, slots=True)
class GovernedRecord:
    """A governed run's purpose, target and lineage, as stored with the run."""

    purpose: DeepResearchPurpose
    purpose_source: PurposeSource
    target: ResearchTargetRef
    lineage: InterpretationLineage | DesignLineage
    run_spec_fingerprint: str
    engine_request_fingerprint: str
    title: str | None


def governed_record(metadata: dict[str, Any]) -> GovernedRecord | None:
    """The stored purpose, target and lineage of a run; None for a run stored before them.

    The stored run-spec fingerprint is recomputed from the stored parts and the engine
    request's fingerprint; a mismatch is not quietly accepted (:class:`RunSpecCorrupt`).
    """
    if metadata.get("integration_contract") != RUN_SPEC_CONTRACT:
        return None
    spec = _StoredSpec.model_validate(
        {
            "purpose": metadata["purpose"],
            "target": metadata["target"],
            "lineage": metadata["lineage"],
        }
    )
    engine = str(metadata["request_fingerprint"])
    stored = str(metadata["run_spec_fingerprint"])
    recomputed = digest(run_spec_identity(spec.purpose, spec.target, spec.lineage, engine))
    if recomputed != stored:
        raise RunSpecCorrupt("the stored run spec does not hash to its fingerprint")
    title = metadata.get("title")
    return GovernedRecord(
        purpose=spec.purpose,
        purpose_source=PurposeSource(str(metadata.get("purpose_source", "EXPLICIT"))),
        target=spec.target,
        lineage=spec.lineage,
        run_spec_fingerprint=stored,
        engine_request_fingerprint=engine,
        title=str(title) if title is not None else None,
    )


class _StoredSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    purpose: DeepResearchPurpose
    target: ResearchTargetRef
    lineage: FrozenLineage


def _require_entity(target: ResearchTargetRef, payload: Any) -> None:
    """The target's entity is in the artifact it names, or the target is refused."""
    try:
        if isinstance(target, ResultQuestionTarget):
            found = target.question_id in payload["aggregate"]["questions"]
        elif isinstance(target, ResultBatteryObjectTarget):
            battery = payload["aggregate"]["batteries"].get(target.battery_id)
            found = battery is not None and target.object_id in battery["objects"]
        elif isinstance(target, AnalysisModuleTarget):
            found = payload["module_id"] == target.module_id.value
        elif isinstance(target, SociomapTarget | SociomapObjectTarget | SociomapRelationshipTarget):
            battery = next(
                (
                    b
                    for b in payload["sociomap"]["batteries"]
                    if b["battery_id"] == target.battery_id
                ),
                None,
            )
            objects = {o["id"] for o in battery["objects"]} if battery is not None else set()
            if isinstance(target, SociomapObjectTarget):
                found = target.object_id in objects
            elif isinstance(target, SociomapRelationshipTarget):
                found = {target.source_object_id, target.target_object_id} <= objects
            else:
                found = battery is not None
        else:
            found = False
    except (KeyError, TypeError, AttributeError) as exc:
        raise ResearchTargetInvalid("the artifact does not have the shape of its type") from exc
    if not found:
        raise ResearchTargetInvalid(f"{target.kind}: the artifact holds no such entity")
