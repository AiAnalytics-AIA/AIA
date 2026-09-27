"""A native research run's analysis in the application layer: its inputs, its outcomes read back.

Three use cases over the Study in scope, sharing one path so that what a module was
judged on and what a reader re-checks cannot differ:

* :func:`native_sources` -- the run's own upstream artifacts (specification, fieldwork
  dataset, aggregate), found through the run's recorded step outputs, read through the
  Study's research artifacts, and checked against each other: the specification is the
  run's Design Revision compiled, the aggregate was computed from that specification
  and that dataset (its recorded dependencies), the types are what they must be.
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
    native_evidence,
    native_preflight,
    research_questions_of,
)
from ..domain.analysis.steps import analysis_node_key, module_of_node
from ..domain.evidence import INSTRUMENT_POLICY_VERSION, ClaimSurface, Violation, method_status
from ..domain.fieldwork import DataOrigin, FieldworkSource
from ..domain.licence import DataLineage
from ..domain.licence_determinations import SYNTHETIC_FIXTURE_DATASET
from ..domain.research_design import ResearchSpecification
from ..domain.scope import Permission, StudyContext
from ..domain.workflow import StepRunStatus
from ..infrastructure.artifact_repository import Artifact, ArtifactNotFound, ArtifactStatus
from ..infrastructure.storage import ArtifactStore, IntegrityError, ObjectNotFound
from ..infrastructure.study_design_repository import StudyDesignRepository
from .analysis import MAX_REPAIRS, AnalysisInputs, ModuleOutcomeKind, input_fingerprint
from .research import ResearchRunNotFound, ResearchRuns, research_artifacts

__all__ = [
    "AGGREGATE_ARTIFACT",
    "DATASET_ARTIFACT",
    "SPECIFICATION_ARTIFACT",
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
]

#: The research steps' artifact types (``aia_executors.research``: SPECIFICATION,
#: FIELDWORK_DATASET, AGGREGATE). Named here because the application layer never
#: imports an app; ``apps/executors/tests`` asserts the two stay equal.
SPECIFICATION_ARTIFACT: Final = "research_specification"
DATASET_ARTIFACT: Final = "research_fieldwork_dataset"
AGGREGATE_ARTIFACT: Final = "research_aggregate"


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
        depends = {a.artifact_id for a in repo.dependencies(aggregate_row.artifact_id)}
    except ArtifactNotFound as exc:
        raise SourcesRefused(
            "source_not_found", f"an upstream artifact is not in scope: {exc}"
        ) from exc
    except (IntegrityError, ObjectNotFound) as exc:
        raise SourcesRefused("source_corrupt", f"an upstream artifact is corrupt: {exc}") from exc

    spec = ResearchSpecification.model_validate(spec_payload.get("specification"))
    if spec_payload.get("specification_fingerprint") != spec.fingerprint():
        raise SourcesRefused(
            "specification_moved", "the specification does not match its fingerprint"
        )
    revision_id = str(spec_payload.get("design_revision_id") or "")
    if revision_id != str((run.get("metadata") or {}).get("design_revision_id") or ""):
        raise SourcesRefused(
            "design_revision", "the specification is not the run's Design Revision"
        )
    if not {spec_row.artifact_id, dataset_row.artifact_id} <= depends:
        raise SourcesRefused(
            "aggregate_lineage", "the aggregate does not record this specification and dataset"
        )
    aggregate = aggregate_payload.get("aggregate")
    if not isinstance(aggregate, Mapping):
        raise SourcesRefused("aggregate_shape", "the aggregate artifact holds no aggregate")

    raw_origin = dataset_row.metadata.get("data_origin")
    try:
        origin = DataOrigin(raw_origin) if raw_origin is not None else None
    except ValueError:
        raise SourcesRefused("dataset_origin", f"unknown data origin {raw_origin!r}") from None

    content = StudyDesignRepository(session, scope).content(revision_id)
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
    """
    if sources.fieldwork_source == FieldworkSource.SYNTHETIC_FIXTURE.value:
        fixture = sources.dataset_origin is DataOrigin.SYNTHETIC_FIXTURE
        return DatasetMaterial(
            lineage=DataLineage.of(SYNTHETIC_FIXTURE_DATASET) if fixture else None,
            respondents_fictional=fixture,
        )
    if sources.fieldwork_source != FieldworkSource.AI_RUNTIME.value:
        return DatasetMaterial(lineage=None, respondents_fictional=False)
    payload = research_artifacts(session, scope, store).read_json(sources.refs.dataset.artifact_id)
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
    if record.sources != sources.refs:
        raise ReconstructionRefused(
            "sources_moved", "the run's sources are not the ones this outcome was judged on"
        )
    prepared = prepare_module(
        sources,
        module_id=module_id,
        surface=record.surface,
        language=record.harness.language,
        max_repairs=record.harness.max_repairs,
    )
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
