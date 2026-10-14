"""A native research run's analysis in the application layer: its inputs, its outcomes read back.

Three use cases over the Study in scope, sharing one path so that what a module was
judged on and what a reader re-checks cannot differ:

* :func:`native_sources` -- the run's own upstream artifacts (specification, fieldwork
  dataset, aggregate), found through the run's recorded step outputs, read through the
  Study's research artifacts, and checked against each other: the specification is the
  run's Design Revision compiled (or an identical earlier revision's, which the compile
  step reuses) -- the revision it records, and, when this system's compiler produced
  it, the revision compiled again -- the aggregate was computed from that dataset and a
  specification of that fingerprint (its recorded dependencies), and the types and
  shapes are what they must be.
* :func:`prepare_module` -- those sources as the :class:`AnalysisInputs` one module is
  judged on, with the domain's module fingerprint, the artifact's reuse key and the
  deterministic preflight. The executor calls this before any reservation.
* :func:`reconstruct_module` / :func:`reconstruct_run` -- a stored outcome read back.
  The stored artifact is parsed against its contract; the sources are loaded again
  and must be the ones it records, by content; the inputs are rebuilt and every
  fingerprint must match; and a completed module's stored draft goes through the
  evidence gate again, which mints the claims the result holds. Stored JSON never
  becomes an :class:`~aia_core.domain.evidence.AdmittedClaim` by saying so. Anything
  that moved refuses the reconstruction (:class:`ReconstructionRefused`, with a reason
  code) rather than returning something stale.

Reading needs ``VIEW_RESULTS``; an ``INTERNAL`` outcome -- today, every outcome, since
every native run is fictional -- needs ``EDIT_STUDY`` too: the Study's researchers see
internal interpretation, as they see the internal Sociomap (ADR 0016 decision 6).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from sqlalchemy.orm import Session

from ..domain.ai_contracts import schema_fingerprint
from ..domain.analysis import (
    PROMPT_TEMPLATE_VERSION,
    AnalysisDraft,
    AnalysisModuleId,
    AnalysisModuleResult,
    check_analysis_draft,
    module_spec,
    prompt_template_sha256,
    result_from_check,
)
from ..domain.analysis.artifact import (
    ANALYSIS_ARTIFACT_CONTRACT,
    ANALYSIS_MODULE_ARTIFACT,
    AuthoritySummary,
    CallRecord,
    EvidenceSummary,
    HarnessSummary,
    ModuleArtifact,
    ModuleLabels,
    ModuleSources,
    ProducedBy,
    SourceRef,
    ViolationRecord,
    module_reuse_fingerprint,
    parse_module_artifact,
)
from ..domain.analysis.harness import (
    AGENT_ID,
    AGENT_VERSION,
    ANALYSIS_CAPABILITY,
    ANALYSIS_HARNESS_VERSION,
    analysis_agent,
    harness_labels,
    harness_sha256,
)
from ..domain.analysis.native import (
    NATIVE_EVIDENCE_VERSION,
    NativeEvidence,
    NativeEvidenceRefused,
    native_evidence,
    native_preflight,
    research_questions_of,
)
from ..domain.analysis.steps import analysis_node_key, module_of_node
from ..domain.evidence import (
    INSTRUMENT_POLICY_VERSION,
    ClaimSurface,
    InstrumentPolicyRefused,
    Violation,
    method_status,
)
from ..domain.fieldwork import DataOrigin, FieldworkSource
from ..domain.licence import DataLineage
from ..domain.licence_determinations import SYNTHETIC_FIXTURE_DATASET
from ..domain.pipeline import fingerprint
from ..domain.research_design import COMPILER_VERSION, ResearchSpecification, compile_design
from ..domain.research_sociomap import read_methods
from ..domain.scope import Permission, StudyContext
from ..domain.workflow import StepRunStatus, WorkflowRunStatus
from ..infrastructure.artifact_repository import (
    Artifact,
    ArtifactNotFound,
    ArtifactRepository,
    ArtifactStatus,
)
from ..infrastructure.storage import ArtifactStore, IntegrityError, ObjectNotFound
from ..infrastructure.study_design_repository import (
    DesignRevisionNotFound,
    StudyDesignRepository,
)
from .analysis import MAX_REPAIRS, AnalysisInputs, ModuleOutcomeKind, input_fingerprint
from .research import (
    FrozenDataset,
    ResearchRunNotFound,
    ResearchRuns,
    RunReservations,
    research_artifacts,
)
from .workflows import StartedRun

__all__ = [
    "AGGREGATE_ARTIFACT",
    "DATASET_ARTIFACT",
    "SPECIFICATION_ARTIFACT",
    "AnalysisNotRetryable",
    "DatasetMaterial",
    "NativeSources",
    "PreparedModule",
    "ReconstructedModule",
    "ReconstructionRefused",
    "RunAnalysis",
    "SourcesRefused",
    "dataset_material",
    "harness_summary",
    "module_artifact",
    "native_sources",
    "prepare_module",
    "reconstruct_module",
    "reconstruct_run",
    "retry_failed_modules",
]

#: The research steps' artifact types (``aia_executors.research``: SPECIFICATION,
#: FIELDWORK_DATASET, AGGREGATE). Named here because the application layer never
#: imports an app; ``apps/executors/tests`` asserts the two stay equal.
SPECIFICATION_ARTIFACT: Final = "research_specification"
DATASET_ARTIFACT: Final = "research_fieldwork_dataset"
AGGREGATE_ARTIFACT: Final = "research_aggregate"


#: A step that ended without an outcome a person can ask for again.
_RETRYABLE_STEP_STATES: Final = frozenset({"FAILED", "CANCELLED"})


class SourcesRefused(Exception):
    """The run's upstream artifacts are missing, or do not describe one computation."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class ReconstructionRefused(Exception):
    """A stored outcome cannot be trusted as it stands. ``reason`` is a stable code."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


# --------------------------------------------------------------------------- #
# sources
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class NativeSources:
    """A run's upstream artifacts, read in scope and checked against each other."""

    run_id: str
    refs: ModuleSources
    specification: ResearchSpecification
    aggregate: Mapping[str, Any]
    dataset_origin: DataOrigin | None
    fieldwork_source: str | None
    research_questions: tuple[str, ...]


def _upstream_ids(run: Mapping[str, Any]) -> dict[str, str]:
    found: dict[str, str] = {}
    for step in run.get("steps") or []:
        artifact_id = (step.get("output") or {}).get("artifact_id")
        if step.get("node_key") in ("compile", "run", "aggregate") and artifact_id:
            found[str(step["node_key"])] = str(artifact_id)
    return found


def _typed(artifact: Artifact, artifact_type: str) -> Artifact:
    if artifact.artifact_type != artifact_type:
        raise SourcesRefused(
            "source_type",
            f"{artifact.artifact_id} is a {artifact.artifact_type}, not a {artifact_type}",
        )
    if artifact.status is not ArtifactStatus.VALID:
        raise SourcesRefused("source_invalid", f"{artifact.artifact_id} is {artifact.status}")
    return artifact


def _computed_from(
    repo: ArtifactRepository,
    depends: Sequence[Artifact],
    *,
    spec: ResearchSpecification,
    spec_id: str,
    dataset_id: str,
) -> bool:
    """Whether an aggregate records the run's dataset and the run's specification.

    The specification by fingerprint, as the fieldwork and aggregate steps key on it: a
    design edited outside its questionnaire (its research questions, say) compiles to a
    new artifact of the same specification, and the steps after it reuse the earlier
    run's dataset and aggregate, which record the earlier artifact.
    """
    ids = {d.artifact_id for d in depends}
    if dataset_id not in ids:
        return False
    if spec_id in ids:
        return True
    for dependency in depends:
        if dependency.artifact_type != SPECIFICATION_ARTIFACT:
            continue
        recorded = repo.read_json(dependency.artifact_id)
        if not isinstance(recorded, Mapping):
            continue
        try:
            other = ResearchSpecification.model_validate(recorded.get("specification"))
        except ValueError:
            continue
        if other.fingerprint() == recorded.get("specification_fingerprint") == spec.fingerprint():
            return True
    return False


def _corrupt(what: str) -> SourcesRefused:
    """A source whose bytes failed verification, or whose object is gone.

    The read has marked the artifact CORRUPT in the caller's transaction. A caller keeps
    that mark only by ending the transaction without raising: the worker's rolls back
    on any exception (OI-77). The storage error's text is not repeated, because it holds
    the object's key, and this message reaches a step's error and a reader.
    """
    return SourcesRefused("source_corrupt", f"{what} failed verification and is marked corrupt")


def _specification(payload: Any) -> ResearchSpecification:
    """The specification a compile artifact holds: bytes that pass their hash but are of
    another shape (an older producer's, say) hold none, and are refused as such."""
    if not isinstance(payload, Mapping):
        raise SourcesRefused("specification_shape", "the specification artifact holds no object")
    try:
        return ResearchSpecification.model_validate(payload.get("specification"))
    except ValueError as exc:
        raise SourcesRefused(
            "specification_shape",
            f"the specification artifact holds no specification this system reads: {exc}",
        ) from exc


def native_sources(
    session: Session, scope: StudyContext, store: ArtifactStore, run: Mapping[str, Any]
) -> NativeSources:
    """The run's specification, dataset and aggregate, each verified, and its questions.

    ``run`` is the run as :class:`~aia_core.application.research.ResearchRuns` or the
    workflow repository returns it under ``scope``; its recorded step outputs are the
    only way an artifact is found, so nothing here can be pointed at another run's.
    """
    ids = _upstream_ids(run)
    missing = [n for n in ("compile", "run", "aggregate") if n not in ids]
    if missing:
        raise SourcesRefused("missing_upstream", f"the run recorded no artifact for {missing}")
    repo = research_artifacts(session, scope, store)
    try:
        spec_row = _typed(repo.get(ids["compile"]), SPECIFICATION_ARTIFACT)
        dataset_row = _typed(repo.get(ids["run"]), DATASET_ARTIFACT)
        aggregate_row = _typed(repo.get(ids["aggregate"]), AGGREGATE_ARTIFACT)
        spec_payload = repo.read_json(spec_row.artifact_id)
        aggregate_payload = repo.read_json(aggregate_row.artifact_id)
        spec = _specification(spec_payload)
        computed_from = _computed_from(
            repo,
            repo.dependencies(aggregate_row.artifact_id),
            spec=spec,
            spec_id=spec_row.artifact_id,
            dataset_id=dataset_row.artifact_id,
        )
    except ArtifactNotFound as exc:
        raise SourcesRefused(
            "source_not_found", f"an upstream artifact is not in scope: {exc}"
        ) from exc
    except (IntegrityError, ObjectNotFound) as exc:
        raise _corrupt("an upstream artifact") from exc

    if spec_payload.get("specification_fingerprint") != spec.fingerprint():
        raise SourcesRefused(
            "specification_moved", "the specification does not match its fingerprint"
        )
    revision_id = str((run.get("metadata") or {}).get("design_revision_id") or "")
    compiled_from = str(spec_payload.get("design_revision_id") or "")
    designs = StudyDesignRepository(session, scope)
    try:
        content = designs.content(revision_id)
        # The compile step keys its artifact on the design's content, so a revision
        # identical to an earlier one runs on that revision's specification.
        compiled = compiled_from == revision_id or fingerprint(
            designs.content(compiled_from)
        ) == fingerprint(content)
    except DesignRevisionNotFound as exc:
        raise SourcesRefused("design_revision", f"no such Design Revision here: {exc}") from exc
    if not compiled:
        raise SourcesRefused(
            "design_revision", "the specification is not the run's Design Revision"
        )
    # What the compile step recorded is checked against what it compiles: the revision is
    # immutable and the compiler deterministic, so a specification of this compiler is
    # exactly the revision compiled. Another compiler's cannot be compiled again here,
    # and a run parked across a deploy must still be read, so it is held to the revision
    # it records, above.
    if spec.compiler_version == COMPILER_VERSION:
        recompiled, _ = compile_design(content)
        if recompiled is None or recompiled.fingerprint() != spec.fingerprint():
            raise SourcesRefused(
                "design_revision", "the specification is not the run's Design Revision compiled"
            )
    if not computed_from:
        raise SourcesRefused(
            "aggregate_lineage", "the aggregate does not record this specification and dataset"
        )
    aggregate = (
        aggregate_payload.get("aggregate") if isinstance(aggregate_payload, Mapping) else None
    )
    if not isinstance(aggregate, Mapping):
        raise SourcesRefused("aggregate_shape", "the aggregate artifact holds no aggregate")

    raw_origin = dataset_row.metadata.get("data_origin")
    try:
        origin = DataOrigin(raw_origin) if raw_origin is not None else None
    except ValueError:
        raise SourcesRefused("dataset_origin", f"unknown data origin {raw_origin!r}") from None

    return NativeSources(
        run_id=str(run["run_id"]),
        refs=ModuleSources(
            design_revision_id=revision_id,
            specification=SourceRef(artifact_id=spec_row.artifact_id, sha256=spec_row.sha256),
            specification_fingerprint=spec.fingerprint(),
            dataset=SourceRef(artifact_id=dataset_row.artifact_id, sha256=dataset_row.sha256),
            aggregate=SourceRef(artifact_id=aggregate_row.artifact_id, sha256=aggregate_row.sha256),
        ),
        specification=spec,
        aggregate=aggregate,
        dataset_origin=origin,
        fieldwork_source=dataset_row.metadata.get("fieldwork_source"),
        research_questions=research_questions_of(content),
    )


@dataclass(frozen=True, slots=True)
class DatasetMaterial:
    """What a model request built from this dataset derives from, as the dataset recorded it."""

    lineage: DataLineage | None
    respondents_fictional: bool


def dataset_material(
    session: Session, scope: StudyContext, store: ArtifactStore, sources: NativeSources
) -> DatasetMaterial:
    """The dataset's lineage and whether its respondents are fictional. Unknown is ``None``.

    The AI respondent source records both on its artifact (``provenance``); the
    fictional fixture is, by definition, invented from no source dataset (ADR 0016
    D1), which is exactly its licence determination's dataset. Anything else, or a
    record without them, declares nothing -- and the gateway refuses an undeclared
    lineage before any adapter.

    A dataset whose bytes fail verification is refused (``source_corrupt``), as in
    :func:`native_sources`.
    """
    if sources.fieldwork_source == FieldworkSource.SYNTHETIC_FIXTURE.value:
        fixture = sources.dataset_origin is DataOrigin.SYNTHETIC_FIXTURE
        return DatasetMaterial(
            lineage=DataLineage.of(SYNTHETIC_FIXTURE_DATASET) if fixture else None,
            respondents_fictional=fixture,
        )
    if sources.fieldwork_source != FieldworkSource.AI_RUNTIME.value:
        return DatasetMaterial(lineage=None, respondents_fictional=False)
    try:
        payload = research_artifacts(session, scope, store).read_json(
            sources.refs.dataset.artifact_id
        )
    except (IntegrityError, ObjectNotFound) as exc:
        raise _corrupt("the fieldwork dataset") from exc
    provenance = payload.get("provenance") if isinstance(payload, Mapping) else None
    provenance = provenance if isinstance(provenance, Mapping) else {}
    recorded = provenance.get("lineage")
    lineage = (
        DataLineage.of(*recorded)
        if isinstance(recorded, list)
        and recorded
        and all(isinstance(d, str) and d for d in recorded)
        else None
    )
    persona = provenance.get("persona_source")
    fictional = isinstance(persona, Mapping) and persona.get("fictional") is True
    return DatasetMaterial(lineage=lineage, respondents_fictional=fictional)


# --------------------------------------------------------------------------- #
# one module, prepared
# --------------------------------------------------------------------------- #


def harness_summary(*, language: str, max_repairs: int = MAX_REPAIRS) -> HarnessSummary:
    """The harness a module runs under, as its artifact records it."""
    agent = analysis_agent(max_output_tokens=1)
    return HarnessSummary(
        harness_version=ANALYSIS_HARNESS_VERSION,
        harness_sha256=harness_sha256(),
        prompt_template_version=PROMPT_TEMPLATE_VERSION,
        prompt_template_sha256=prompt_template_sha256(),
        agent_id=AGENT_ID,
        agent_version=AGENT_VERSION,
        capability=ANALYSIS_CAPABILITY.value,
        schema_fingerprint=schema_fingerprint(agent.schema or {}),
        language=language,
        max_repairs=max_repairs,
        max_calls=1 + max_repairs,
    )


@dataclass(frozen=True, slots=True)
class PreparedModule:
    """Everything one module is judged on, and every reason it cannot run."""

    module_id: AnalysisModuleId
    sources: NativeSources
    evidence: NativeEvidence
    inputs: AnalysisInputs
    module_fingerprint: str
    reuse_fingerprint: str
    harness: HarnessSummary
    preflight: tuple[Violation, ...]

    @property
    def method_status(self) -> str:
        return method_status(self.inputs.validation, self.inputs.system_fingerprint)


def prepare_module(
    sources: NativeSources,
    *,
    module_id: AnalysisModuleId,
    surface: ClaimSurface,
    language: str,
    max_repairs: int = MAX_REPAIRS,
) -> PreparedModule:
    """Build one module's inputs from verified sources. Pure given the sources."""
    evidence = native_evidence(
        sources.specification,
        sources.aggregate,
        dataset_sha256=sources.refs.dataset.sha256,
        origin=sources.dataset_origin,
    )
    inputs = AnalysisInputs(
        table=evidence.table,
        book=evidence.book,
        joint_status=evidence.joint_status,
        surface=surface,
        research_questions=sources.research_questions,
        language=language,
        system_fingerprint=evidence.system_fingerprint,
    )
    fingerprint = input_fingerprint(module_id, inputs)
    harness = harness_summary(language=language, max_repairs=max_repairs)
    return PreparedModule(
        module_id=module_id,
        sources=sources,
        evidence=evidence,
        inputs=inputs,
        module_fingerprint=fingerprint,
        reuse_fingerprint=module_reuse_fingerprint(
            module_fingerprint=fingerprint, sources=sources.refs, harness=harness
        ),
        harness=harness,
        preflight=native_preflight(
            module_spec(module_id),
            evidence,
            surface=surface,
            research_questions=sources.research_questions,
        ),
    )


def module_artifact(
    prepared: PreparedModule,
    *,
    outcome: ModuleOutcomeKind,
    draft: Mapping[str, Any] | None,
    violations: Sequence[Violation],
    calls: Sequence[CallRecord],
    produced_by: ProducedBy,
    runtime_version: str | None,
) -> ModuleArtifact:
    """The stored form of one module's outcome. The one builder the executor uses."""
    spec = module_spec(prepared.module_id)
    evidence = prepared.evidence
    joint = evidence.joint_status
    surface = prepared.inputs.surface
    return ModuleArtifact(
        kind=ANALYSIS_MODULE_ARTIFACT,
        contract_version=ANALYSIS_ARTIFACT_CONTRACT,
        module_id=prepared.module_id,
        ordinal=spec.ordinal,
        artifact_name=spec.artifact_name,
        outcome="COMPLETED" if outcome is ModuleOutcomeKind.COMPLETED else "BLOCKED",
        surface=surface,
        method_status=prepared.method_status,
        input_fingerprint=prepared.module_fingerprint,
        reuse_fingerprint=prepared.reuse_fingerprint,
        research_questions=prepared.inputs.research_questions,
        draft=AnalysisDraft.model_validate(dict(draft)) if draft is not None else None,
        violations=tuple(ViolationRecord.of(v) for v in violations),
        attempts=len(calls),
        sources=prepared.sources.refs,
        evidence=EvidenceSummary(
            adapter_version=NATIVE_EVIDENCE_VERSION,
            table_fingerprint=evidence.table.fingerprint(),
            rows=len(evidence.table.rows),
            suppressed=tuple(sorted(evidence.table.suppressed)),
            data_origin=evidence.origin,
        ),
        authority=AuthoritySummary(
            field_policy_version=INSTRUMENT_POLICY_VERSION,
            field_policy_sha256=evidence.book.source_sha256,
            joint_status_fingerprint=joint.fingerprint(),
            joint_degradation=joint.degradation.value if joint.degradation else None,
            system_fingerprint=evidence.system_fingerprint,
        ),
        harness=prepared.harness,
        calls=tuple(calls),
        labels=ModuleLabels.model_validate(harness_labels(origin=evidence.origin, surface=surface)),
        produced_by=produced_by,
        runtime_version=runtime_version,
    )


# --------------------------------------------------------------------------- #
# reading an outcome back
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ReconstructedModule:
    """A stored outcome, re-checked. ``result`` holds claims the gate minted just now."""

    module_id: AnalysisModuleId
    outcome: ModuleOutcomeKind
    result: AnalysisModuleResult | None
    violations: tuple[Violation, ...]
    #: What the result was judged on, rebuilt: its table carries the suppressed refs a
    #: report must say it removed (``EvidenceLedger.from_claims(table=...)``).
    inputs: AnalysisInputs
    artifact_id: str
    artifact_sha256: str
    record: ModuleArtifact


@dataclass(frozen=True, slots=True)
class RunAnalysis:
    """Every analysis module of a run: its outcome, or why there is none yet."""

    run_id: str
    modules: Mapping[AnalysisModuleId, ReconstructedModule]
    #: Modules with no stored outcome, and the status of their step.
    pending: Mapping[AnalysisModuleId, str] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        """True when all eight modules completed. Only then can a report be composed."""
        return (
            not self.pending
            and len(self.modules) == len(AnalysisModuleId)
            and all(m.outcome is ModuleOutcomeKind.COMPLETED for m in self.modules.values())
        )

    @property
    def retryable(self) -> tuple[AnalysisModuleId, ...]:
        """The modules a person may ask again over this run's frozen data, in module order.

        A module a model's drafts left ``BLOCKED`` (it took turns), and a module whose
        step ended ``FAILED`` or ``CANCELLED`` without an outcome. Never a module the
        preflight blocked before any turn: code refused it, and the same data would
        refuse it again.
        """
        return tuple(
            m
            for m in AnalysisModuleId
            if (
                m in self.modules
                and self.modules[m].outcome is ModuleOutcomeKind.BLOCKED
                and self.modules[m].record.attempts > 0
            )
            or self.pending.get(m) in _RETRYABLE_STEP_STATES
        )


def _run(session: Session, scope: StudyContext, run_id: str) -> dict[str, Any]:
    scope.require(Permission.VIEW_RESULTS)
    try:
        return ResearchRuns(session, scope).get(run_id)
    except ResearchRunNotFound as exc:
        raise ReconstructionRefused("run_not_found", f"no research run {run_id} here") from exc


def _step(run: Mapping[str, Any], module_id: AnalysisModuleId) -> Mapping[str, Any] | None:
    key = analysis_node_key(module_id)
    return next((s for s in run.get("steps") or [] if s.get("node_key") == key), None)


def _reconstruct(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    sources: NativeSources,
    module_id: AnalysisModuleId,
    artifact_id: str,
) -> ReconstructedModule:
    repo = research_artifacts(session, scope, store)
    try:
        artifact = repo.get(artifact_id)
    except ArtifactNotFound as exc:
        raise ReconstructionRefused("outcome_not_found", str(exc)) from exc
    if artifact.artifact_type != ANALYSIS_MODULE_ARTIFACT or not artifact.is_reusable:
        raise ReconstructionRefused(
            "outcome_invalid", f"{artifact_id} is a {artifact.status} {artifact.artifact_type}"
        )
    try:
        stored = repo.read_json(artifact_id)
    except (IntegrityError, ObjectNotFound) as exc:
        raise ReconstructionRefused("outcome_corrupt", f"{artifact_id}: {exc}") from exc
    try:
        record = parse_module_artifact(stored)
    except ValueError as exc:
        raise ReconstructionRefused(
            "contract", f"{artifact_id} breaks its contract: {exc}"
        ) from exc
    if record.module_id is not module_id:
        raise ReconstructionRefused("module", f"{artifact_id} is the {record.module_id} module")
    if record.surface is ClaimSurface.INTERNAL:
        scope.require(Permission.EDIT_STUDY)
    if record.sources.content() != sources.refs.content():
        raise ReconstructionRefused(
            "sources_moved", "the run's sources are not the ones this outcome was judged on"
        )
    try:
        prepared = prepare_module(
            sources,
            module_id=module_id,
            surface=record.surface,
            language=record.harness.language,
            max_repairs=record.harness.max_repairs,
        )
    except (NativeEvidenceRefused, InstrumentPolicyRefused) as exc:
        raise ReconstructionRefused(
            "evidence_refused", f"the recorded sources no longer make evidence: {exc}"
        ) from exc
    if (
        record.input_fingerprint != prepared.module_fingerprint
        or record.reuse_fingerprint != prepared.reuse_fingerprint
        or record.harness != prepared.harness
        or record.method_status != prepared.method_status
    ):
        raise ReconstructionRefused(
            "fingerprint_mismatch",
            "the evidence, policy, method status or harness no longer match this outcome",
        )
    if record.outcome == "BLOCKED":
        return ReconstructedModule(
            module_id=module_id,
            outcome=ModuleOutcomeKind.BLOCKED,
            result=None,
            violations=tuple(v.violation() for v in record.violations),
            inputs=prepared.inputs,
            artifact_id=artifact_id,
            artifact_sha256=artifact.sha256,
            record=record,
        )
    assert record.draft is not None  # the contract holds a completed module's draft
    inputs = prepared.inputs
    check = check_analysis_draft(
        record.draft.model_dump(mode="json"),
        module_spec(module_id),
        inputs.table,
        book=inputs.book,
        joint_status=inputs.joint_status,
        surface=inputs.surface,
        research_questions=inputs.research_questions,
    )
    if not check.decision.allowed:
        raise ReconstructionRefused(
            "readmission_refused",
            "; ".join(str(v) for v in check.decision.violations[:5]),
        )
    return ReconstructedModule(
        module_id=module_id,
        outcome=ModuleOutcomeKind.COMPLETED,
        result=result_from_check(
            check,
            module_id=module_id,
            surface=inputs.surface,
            method_status=prepared.method_status,
            input_fingerprint=prepared.module_fingerprint,
            research_questions=inputs.research_questions,
        ),
        violations=(),
        inputs=inputs,
        artifact_id=artifact_id,
        artifact_sha256=artifact.sha256,
        record=record,
    )


def _outcome_id(step: Mapping[str, Any] | None) -> str | None:
    if step is None or step.get("status") is not StepRunStatus.SUCCEEDED:
        return None
    artifact_id = (step.get("output") or {}).get("artifact_id")
    return str(artifact_id) if artifact_id else None


def _sources(
    session: Session, scope: StudyContext, store: ArtifactStore, run: Mapping[str, Any]
) -> NativeSources:
    try:
        return native_sources(session, scope, store, run)
    except SourcesRefused as exc:
        raise ReconstructionRefused("sources_refused", f"{exc.reason}: {exc}") from exc


def reconstruct_module(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    module_id: AnalysisModuleId,
) -> ReconstructedModule:
    """One module's stored outcome for a run of the Study in scope, re-checked in full."""
    run = _run(session, scope, run_id)
    step = _step(run, module_id)
    if step is None:
        raise ReconstructionRefused("not_in_run", f"run {run_id} has no {module_id} module")
    artifact_id = _outcome_id(step)
    if artifact_id is None:
        raise ReconstructionRefused(
            "no_outcome", f"the {module_id} module of {run_id} is {step.get('status')}"
        )
    return _reconstruct(
        session, scope, store, _sources(session, scope, store, run), module_id, artifact_id
    )


def reconstruct_run(
    session: Session, scope: StudyContext, store: ArtifactStore, *, run_id: str
) -> RunAnalysis:
    """Every analysis module of one run, each re-checked; the sources are read once."""
    run = _run(session, scope, run_id)
    steps = {
        module: step
        for step in run.get("steps") or []
        if (module := module_of_node(str(step.get("node_key")))) is not None
    }
    pending: dict[AnalysisModuleId, str] = {
        m: "not_in_run" for m in AnalysisModuleId if m not in steps
    }
    outcomes: dict[AnalysisModuleId, str] = {}
    for module, step in steps.items():
        artifact_id = _outcome_id(step)
        if artifact_id is None:
            pending[module] = str(getattr(step.get("status"), "value", step.get("status")))
        else:
            outcomes[module] = artifact_id
    modules: dict[AnalysisModuleId, ReconstructedModule] = {}
    if outcomes:
        sources = _sources(session, scope, store, run)
        for module in AnalysisModuleId:
            if module in outcomes:
                modules[module] = _reconstruct(
                    session, scope, store, sources, module, outcomes[module]
                )
    return RunAnalysis(run_id=run_id, modules=modules, pending=pending)


# --------------------------------------------------------------------------- #
# asking failed modules again, over the run's frozen data
# --------------------------------------------------------------------------- #

#: Runs whose analysis a person may ask again: the run has stopped moving.
_FINISHED: Final = frozenset({WorkflowRunStatus.COMPLETED, WorkflowRunStatus.FAILED})


class AnalysisNotRetryable(Exception):
    """The run's analysis cannot be asked again; ``reason`` says why, for the API."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _reused(module: ReconstructedModule) -> bool:
    """True when a retry will reuse this outcome: a completed module under today's harness."""
    if module.outcome is not ModuleOutcomeKind.COMPLETED:
        return False
    return module.record.harness == harness_summary(
        language=module.record.harness.language, max_repairs=module.record.harness.max_repairs
    )


def retry_failed_modules(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    reservations: RunReservations | None = None,
    confirm_cost_usd: float | None = None,
) -> StartedRun:
    """Ask a finished run's failed analysis modules again, without collecting data again.

    A new run, linked to ``run_id`` (``retry_of``), over the same Design Revision and
    Sociomap pins: its fieldwork step takes this run's dataset by artifact id and SHA-256
    (:class:`~.research.FrozenDataset`), so the specification, the dataset and the
    aggregate are the same bytes and every completed module is reused by its reuse key at
    no cost. The modules in :attr:`RunAnalysis.retryable` are asked again in a new round;
    a module the preflight blocked is not, because code would refuse it again. The report
    then composes only if all eight complete -- its gate is unchanged.

    The spend limit works as it does for any start, over a ceiling that counts only the
    modules that will ask a model. Idempotent: asking twice returns the same retry.
    Raises :class:`AnalysisNotRetryable` with ``run_not_finished``,
    ``analysis_not_in_run``, ``dataset_missing`` or ``nothing_to_retry``.
    """
    runs = ResearchRuns(session, scope)
    run = runs.get(run_id)
    metadata = run["metadata"]
    if run["status"] not in _FINISHED:
        raise AnalysisNotRetryable(
            "run_not_finished", f"run {run_id} is {run['status']}; it has not finished"
        )
    if not metadata.get("analysis_enabled"):
        raise AnalysisNotRetryable("analysis_not_in_run", f"run {run_id} ran no analysis")
    fieldwork = next((s for s in run.get("steps") or [] if s.get("node_key") == "run"), None)
    output = (fieldwork or {}).get("output") or {}
    if (
        fieldwork is None
        or fieldwork.get("status") is not StepRunStatus.SUCCEEDED
        or output.get("artifact_type") != DATASET_ARTIFACT
        or not isinstance(output.get("artifact_id"), str)
        or not isinstance(output.get("sha256"), str)
    ):
        raise AnalysisNotRetryable(
            "dataset_missing", f"run {run_id} has no collected dataset to analyse again"
        )
    analysis = reconstruct_run(session, scope, store, run_id=run_id)
    retried = analysis.retryable
    if not retried:
        raise AnalysisNotRetryable(
            "nothing_to_retry", f"run {run_id} has no analysis module a model failed"
        )
    asked = sum(
        1
        for m in AnalysisModuleId
        if m in retried
        or (
            m in analysis.modules
            and not _reused(analysis.modules[m])
            and analysis.modules[m].record.attempts > 0
        )
        or (m not in analysis.modules and m not in retried)
    )
    previous = metadata.get("analysis_retry") or {}
    frozen = FrozenDataset(
        run_id=run_id,
        artifact_id=output["artifact_id"],
        sha256=output["sha256"],
        analysis_round=int(previous.get("round", 0)) + 1,
        retried=tuple(m.value for m in retried),
        modules_asked=asked,
    )
    return runs.start(
        design_revision_id=str(metadata["design_revision_id"]),
        fieldwork_source=FieldworkSource(str(metadata["fieldwork_source"])),
        retry_of=run_id,
        analysis_enabled=True,
        sociomapping_enabled=bool(metadata.get("sociomapping_enabled", False)),
        reservations=reservations,
        confirm_cost_usd=confirm_cost_usd,
        sociomap_methods=read_methods(metadata.get("sociomap_methods")),
        frozen_dataset=frozen,
    )
