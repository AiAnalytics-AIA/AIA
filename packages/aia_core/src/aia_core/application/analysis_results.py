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

import hashlib
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
    finding_expected,
    module_reuse_fingerprint,
    no_supported_finding,
    parse_module_artifact,
)
from ..domain.analysis.external import (
    ShownContext,
    external_context_lines,
    public_context,
    shown_context,
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
    hypotheses_of,
    native_evidence,
    native_preflight,
    research_questions_of,
)
from ..domain.analysis.steps import analysis_node_key, module_of_node
from ..domain.answerability import Acknowledgement, read_answerability_note
from ..domain.deep_research.quarantine import AnalysisContext
from ..domain.evidence import (
    ClaimLevel,
    ClaimSurface,
    InstrumentPolicyRefused,
    Violation,
    instrument_policy_version,
    method_status,
    respondent_system_fingerprint,
)
from ..domain.evidence.support import SupportSpec
from ..domain.fieldwork import (
    JOINT_CERTIFICATE_METADATA,
    RESPONDENT_SYSTEM_METADATA,
    DataOrigin,
    FieldworkSource,
    OriginKind,
    origin_kind,
)
from ..domain.licence import DataLineage
from ..domain.licence_determinations import SYNTHETIC_FIXTURE_DATASET
from ..domain.methodology.pins import read_readiness_pin, read_support_pin
from ..domain.pipeline import fingerprint
from ..domain.research_design import COMPILER_VERSION, ResearchSpecification, compile_design
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
from .deep_research import BundleNotReady, DeepResearchRunNotFound, DeepResearchRuns
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
    "StoredAnalysis",
    "dataset_material",
    "harness_summary",
    "module_artifact",
    "native_sources",
    "prepare_module",
    "reconstruct_module",
    "reconstruct_run",
    "retry_failed_modules",
    "stored_analysis",
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
    #: The hypotheses the design states, which the hypotheses module is given (Q72).
    hypotheses: tuple[str, ...]
    #: Research questions the run recorded as gaps at start, whitespace folded: none of them is
    #: expected to be answered with a number (evidence-integrity 9a).
    gap_questions: frozenset[str]
    #: The support rules the run pinned (plan ``methodology-tab`` G1c); its ``analysis`` rule
    #: gates every number this run's analysis admits.
    support: SupportSpec
    #: A modelled dataset's respondent system (ADR 0024 §4), fingerprinted from what the dataset
    #: recorded; ``None`` for every other origin, or when it recorded none.
    respondent_system: str | None = None
    #: A modelled dataset's population certificate and the panel SHA-256 it was verified
    #: against (complete-study-report B5a); ``None`` for every other origin or when none.
    joint_certificate: tuple[bytes, str] | None = None
    #: The accepted findings of the Design Research bundle the run pinned, as each module is
    #: shown them: external context, never evidence (evidence-integrity 7). None without a pin.
    external: ShownContext | None = None


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
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    run: Mapping[str, Any],
    *,
    with_context: bool = True,
) -> NativeSources:
    """The run's specification, dataset and aggregate, each verified, and its questions.

    With ``with_context`` (the analysis, and every reader that re-judges it), also the external
    context the run pinned, verified; a reader of the data alone passes ``False``, so a pin
    that no longer reads refuses only what the context is part of.

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
        # Under the limits the run compiled with (plan methodology-tab V1a): a set the run's
        # version let by would not compile under the preset.
        try:
            limits = read_readiness_pin((run.get("metadata") or {}).get("readiness"))
        except ValueError as exc:
            raise SourcesRefused(
                "readiness_pin", f"the run's readiness pin does not read: {exc}"
            ) from None
        recompiled, _ = compile_design(content, limits=limits)
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

    try:
        support = read_support_pin((run.get("metadata") or {}).get("support"))
    except ValueError as exc:
        raise SourcesRefused("support_pin", f"the run's support pin does not read: {exc}") from None

    raw_origin = dataset_row.metadata.get("data_origin")
    try:
        origin = DataOrigin(raw_origin) if raw_origin is not None else None
    except ValueError:
        raise SourcesRefused("dataset_origin", f"unknown data origin {raw_origin!r}") from None

    respondent_system = _respondent_system(origin, dataset_row.metadata)
    joint_certificate = _joint_certificate(origin, dataset_row.metadata)
    pin = (run.get("metadata") or {}).get("analysis_context")
    context = pinned_context(session, scope, store, pin) if with_context else None
    # pinned_context answers a context only for a Mapping pin it read, never None for one: the
    # isinstance narrows the type and is never false here.
    external = (
        shown_context(str(pin["deep_research_run_id"]), context)
        if context is not None and isinstance(pin, Mapping)
        else None
    )

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
        hypotheses=hypotheses_of(content),
        gap_questions=_gap_questions(run.get("metadata") or {}),
        support=support,
        respondent_system=respondent_system,
        joint_certificate=joint_certificate,
        external=external,
    )


def _gap_questions(metadata: Mapping[str, Any]) -> frozenset[str]:
    """The research questions the run recorded as gaps at start, whitespace folded; none when it
    recorded none or its record does not read (then every question is expected, never fewer)."""
    note = read_answerability_note(metadata)
    if note is None:
        return frozenset()
    return frozenset(
        " ".join(str(g["research_question"]).split())
        for g in note["gaps"]
        if isinstance(g, Mapping) and g.get("research_question")
    )


_CONTEXT_PIN: Final = ("deep_research_run_id", "artifact_id", "sha256")


def _external_context(
    session: Session, scope: StudyContext, store: ArtifactStore, pin: object
) -> tuple[str, ...]:
    """The external context the run pinned (``metadata.analysis_context``) as each module is
    shown it: :func:`pinned_context`'s findings as lines, none without a pin."""
    context = pinned_context(session, scope, store, pin)
    return external_context_lines(context) if context is not None else ()


def pinned_context(
    session: Session, scope: StudyContext, store: ArtifactStore, pin: object
) -> AnalysisContext | None:
    """The external context the run pinned (``metadata.analysis_context``), read again through
    the Deep Research run that published it and held to the pin: the same artifact, the same
    bytes, its seal verified. ``None`` without a pin; anything else is refused, never read as no
    context, since the modules' fingerprints and payloads carry it. Its public findings only
    (:func:`~aia_core.domain.analysis.external.public_context`)."""
    if pin is None:
        return None
    if not isinstance(pin, Mapping) or not all(isinstance(pin.get(k), str) for k in _CONTEXT_PIN):
        raise SourcesRefused("context_pin", "the run's external-context pin does not read")
    runs = DeepResearchRuns(session, scope)
    try:
        steps = runs.get(pin["deep_research_run_id"])["steps"]
        published = next((s for s in steps if s["node_key"] == "publish"), None)
        output = (published or {}).get("output") or {}
        if (output.get("artifact_id"), output.get("sha256")) != (pin["artifact_id"], pin["sha256"]):
            raise SourcesRefused("context_moved", "the pinned bundle is not the one the run pinned")
        bundle = runs.bundle(pin["deep_research_run_id"], store=store)
    except DeepResearchRunNotFound as exc:
        raise SourcesRefused(
            "context_not_found", "the pinned Deep Research run is not in scope"
        ) from exc
    except (BundleNotReady, KeyError, ValueError) as exc:
        raise SourcesRefused(
            "context_unverified", f"the pinned bundle does not read: {exc}"
        ) from exc
    except (IntegrityError, ObjectNotFound) as exc:
        raise _corrupt("the pinned Deep Research bundle") from exc
    return public_context(bundle)


def _joint_certificate(
    origin: DataOrigin | None, metadata: Mapping[str, Any]
) -> tuple[bytes, str] | None:
    """The population certificate a modelled dataset recorded, re-hashed; else ``None``.

    Read for a modelled origin only. A record that does not hash to its recorded SHA-256 is
    refused, never read as no certificate: the gate must not be judged on altered bytes.
    """
    if origin_kind(origin) is not OriginKind.MODELLED:
        return None
    raw = metadata.get(JOINT_CERTIFICATE_METADATA)
    if raw is None:
        return None
    if not isinstance(raw, Mapping) or not all(
        isinstance(raw.get(k), str) for k in ("certificate", "sha256", "panel_sha256")
    ):
        raise SourcesRefused("joint_certificate", "the dataset's certificate is not a record")
    data = str(raw["certificate"]).encode("utf-8")
    if hashlib.sha256(data).hexdigest() != raw["sha256"]:
        raise SourcesRefused(
            "joint_certificate", "the dataset's certificate does not hash to its recorded SHA-256"
        )
    return data, str(raw["panel_sha256"])


def _respondent_system(origin: DataOrigin | None, metadata: Mapping[str, Any]) -> str | None:
    """The respondent system a modelled dataset recorded, fingerprinted; else ``None``.

    Read for a modelled origin only: a simulated one is never validated. A record that does not
    fingerprint (a missing or blank component, a name it does not bind) is refused, never read
    as no system.
    """
    if origin_kind(origin) is not OriginKind.MODELLED:
        return None
    raw = metadata.get(RESPONDENT_SYSTEM_METADATA)
    if raw is None:
        return None
    if not isinstance(raw, Mapping) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in raw.items()
    ):
        raise SourcesRefused(
            "respondent_system", "the dataset's respondent system is not a record of names"
        )
    try:
        return respondent_system_fingerprint(raw)
    except ValueError as exc:
        raise SourcesRefused("respondent_system", str(exc)) from None


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
        support=sources.support.analysis,
        respondent_system=sources.respondent_system,
        joint_certificate=sources.joint_certificate,
        # Nothing stores a validation of a respondent system yet (chunk 7 earns the first), so a
        # modelled run's evidence stays internal.
        validation=None,
    )
    inputs = AnalysisInputs(
        table=evidence.table,
        book=evidence.book,
        joint_status=evidence.joint_status,
        surface=surface,
        research_questions=sources.research_questions,
        language=language,
        system_fingerprint=evidence.system_fingerprint,
        external_context=sources.external.lines() if sources.external is not None else (),
        hypotheses=sources.hypotheses if module_id is AnalysisModuleId.HYPOTHESES else (),
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


def _finding_expected(prepared: PreparedModule) -> bool:
    """:func:`~aia_core.domain.analysis.artifact.finding_expected` from the run's own data: the
    evidence rows the module is given (a suppressed row is not there), the design's hypotheses
    and research questions, the gaps the run recorded at start."""
    sources = prepared.sources
    rows = prepared.evidence.table.rows.values()
    tracked = {b.question_id(o) for b in sources.specification.batteries for o in b.objects}
    return finding_expected(
        prepared.module_id,
        tracked_sets=any(r.question_id in tracked for r in rows),
        hypotheses=bool(sources.hypotheses),
        segment_rows=any(r.level is ClaimLevel.SEGMENT for r in rows),
        research_questions=any(
            " ".join(q.split()) not in sources.gap_questions for q in sources.research_questions
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
            field_policy_version=instrument_policy_version(evidence.origin),
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
        finding_expected=_finding_expected(prepared),
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
    #: How the aggregate every module read departs from 18.6.6's port (plan
    #: ``methodology-tab`` G3c); ``None`` when it is the port, or nothing was read yet.
    aggregation_deviation: Mapping[str, Any] | None = None
    #: This run's own sources, read from the run itself. A reused module's record keeps the
    #: names it was computed under (:class:`ModuleSources`), so what the run stands on is read
    #: here, never from a record; ``None`` when no outcome was stored yet.
    sources: ModuleSources | None = None
    #: Modules asked again over the same data anywhere in this run's retry chain: a module among
    #: them that still states nothing is not offered another round (9a).
    retried: frozenset[AnalysisModuleId] = frozenset()
    #: The external context every module was shown, from the same verified read as its sources
    #: (evidence-integrity 7); ``None`` without a pin, or when no outcome was stored yet.
    external: ShownContext | None = None

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
        """The modules a person may ask again over this run's frozen data (:func:`_retryable`)."""
        return _retryable(
            {m: o.record for m, o in self.modules.items()}, self.pending, self.retried
        )


def _retryable(
    records: Mapping[AnalysisModuleId, ModuleArtifact],
    pending: Mapping[AnalysisModuleId, str],
    retried: frozenset[AnalysisModuleId] = frozenset(),
) -> tuple[AnalysisModuleId, ...]:
    """The modules a person may ask again over a run's frozen data, in module order.

    A module a model's drafts left ``BLOCKED`` (it took turns), a module whose step ended
    ``FAILED`` or ``CANCELLED`` without an outcome, and a module completed under an earlier
    harness (:func:`_stale`): today's harness refuses to re-admit it, so the run's analysis,
    its literature report and its Interpretation Research stay dark until it is asked again.
    A module the run held the context for that states nothing (:func:`no_supported_finding`): a
    same-data round is one way out (MVPQ-04, evidence-integrity 9a), offered once: a module this
    run already asked again (``retried``) and that still states nothing is not offered it again.
    Never a module the preflight blocked before any turn: code refused it, and the same data
    would refuse it again.
    """
    return tuple(
        m
        for m in AnalysisModuleId
        if (m in records and records[m].outcome == "BLOCKED" and records[m].attempts > 0)
        or (m in records and _stale(records[m]))
        or (m in records and no_supported_finding(records[m]) and m not in retried)
        or pending.get(m) in _RETRYABLE_STEP_STATES
    )


def _stale(record: ModuleArtifact) -> bool:
    """A module a model completed under a harness that is not today's: its stored draft is
    still exactly what it was, but :func:`reconstruct_run` refuses to re-admit it
    (``fingerprint_mismatch``) and a retry would ask it again anyway (:func:`_reused`)."""
    return record.outcome == "COMPLETED" and record.attempts > 0 and not _reused(record)


def _stale_modules(
    records: Mapping[AnalysisModuleId, ModuleArtifact],
) -> tuple[AnalysisModuleId, ...]:
    return tuple(m for m in AnalysisModuleId if m in records and _stale(records[m]))


@dataclass(frozen=True, slots=True)
class StoredAnalysis:
    """A run's module outcomes as stored, read without re-judging them.

    For deciding what a retry asks again, never for showing a result: an outcome stored
    under an earlier harness is still exactly what it says (BLOCKED after N turns), even
    though :func:`reconstruct_run` refuses to re-admit it under today's.
    """

    run_id: str
    records: Mapping[AnalysisModuleId, ModuleArtifact]
    pending: Mapping[AnalysisModuleId, str] = field(default_factory=dict)
    #: Modules this run asked again over the same data (see :attr:`RunAnalysis.retried`).
    retried: frozenset[AnalysisModuleId] = frozenset()

    @property
    def retryable(self) -> tuple[AnalysisModuleId, ...]:
        return _retryable(self.records, self.pending, self.retried)

    @property
    def stale(self) -> tuple[AnalysisModuleId, ...]:
        """The retryable modules that completed under an earlier harness (:func:`_stale`)."""
        return _stale_modules(self.records)


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
    record, artifact = _stored_record(session, scope, store, module_id, artifact_id)
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


def _split(
    run: Mapping[str, Any],
) -> tuple[dict[AnalysisModuleId, str], dict[AnalysisModuleId, str]]:
    """Each module's stored outcome id, and the step status of each module without one."""
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
    return outcomes, pending


def _retried(run: Mapping[str, Any]) -> frozenset[AnalysisModuleId]:
    """The modules asked again anywhere in this run's retry chain (its ``analysis_retry.tried``,
    which carries every earlier round's forward; ``modules`` for a retry recorded before it)."""
    note = (run.get("metadata") or {}).get("analysis_retry")
    modules = (note.get("tried", note.get("modules"))) if isinstance(note, Mapping) else None
    if not isinstance(modules, list):
        return frozenset()
    return frozenset(m for m in AnalysisModuleId if m.value in modules)


def _stored_record(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    module_id: AnalysisModuleId,
    artifact_id: str,
) -> tuple[ModuleArtifact, Artifact]:
    """One stored outcome, its bytes verified and its contract parsed; nothing re-judged."""
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
        record = parse_module_artifact(repo.read_json(artifact_id))
    except (IntegrityError, ObjectNotFound) as exc:
        raise ReconstructionRefused("outcome_corrupt", f"{artifact_id}: {exc}") from exc
    except ValueError as exc:
        raise ReconstructionRefused(
            "contract", f"{artifact_id} breaks its contract: {exc}"
        ) from exc
    if record.module_id is not module_id:
        raise ReconstructionRefused("module", f"{artifact_id} is the {record.module_id} module")
    if record.surface is ClaimSurface.INTERNAL:
        scope.require(Permission.EDIT_STUDY)
    return record, artifact


def stored_analysis(
    session: Session, scope: StudyContext, store: ArtifactStore, *, run_id: str
) -> StoredAnalysis:
    """Every analysis module of one run as stored, under any harness it was stored by."""
    run = _run(session, scope, run_id)
    outcomes, pending = _split(run)
    return StoredAnalysis(
        run_id=run_id,
        records={
            m: _stored_record(session, scope, store, m, outcomes[m])[0]
            for m in AnalysisModuleId
            if m in outcomes
        },
        pending=pending,
        retried=_retried(run),
    )


def reconstruct_run(
    session: Session, scope: StudyContext, store: ArtifactStore, *, run_id: str
) -> RunAnalysis:
    """Every analysis module of one run, each re-checked; the sources are read once."""
    run = _run(session, scope, run_id)
    outcomes, pending = _split(run)
    modules: dict[AnalysisModuleId, ReconstructedModule] = {}
    deviation: Mapping[str, Any] | None = None
    refs: ModuleSources | None = None
    external: ShownContext | None = None
    if outcomes:
        sources = _sources(session, scope, store, run)
        refs = sources.refs
        external = sources.external
        raw = sources.aggregate.get("deviation")
        deviation = raw if isinstance(raw, Mapping) else None
        for module in AnalysisModuleId:
            if module in outcomes:
                modules[module] = _reconstruct(
                    session, scope, store, sources, module, outcomes[module]
                )
    return RunAnalysis(
        run_id=run_id,
        modules=modules,
        pending=pending,
        aggregation_deviation=deviation,
        sources=refs,
        retried=_retried(run),
        external=external,
    )


# --------------------------------------------------------------------------- #
# asking failed modules again, over the run's frozen data
# --------------------------------------------------------------------------- #

#: Runs whose analysis a person may ask again: the run has stopped moving.
_FINISHED: Final = frozenset(
    {WorkflowRunStatus.COMPLETED, WorkflowRunStatus.FAILED, WorkflowRunStatus.CANCELLED}
)


class AnalysisNotRetryable(Exception):
    """The run's analysis cannot be asked again; ``reason`` says why, for the API."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _reused(record: ModuleArtifact) -> bool:
    """True when a retry will reuse this outcome: a completed module under today's harness."""
    if record.outcome != "COMPLETED":
        return False
    return record.harness == harness_summary(
        language=record.harness.language, max_repairs=record.harness.max_repairs
    )


def retry_failed_modules(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    reservations: RunReservations | None = None,
    confirm_cost_usd: float | None = None,
    acknowledge: Acknowledgement | None = None,
) -> StartedRun:
    """Ask a finished run's failed analysis modules again, without collecting data again.

    A new run, linked to ``run_id`` (``retry_of``), over the same Design Revision and every
    pin the run recorded (:meth:`~.research.ResearchRuns.retry_analysis`): its fieldwork
    step takes this run's dataset by artifact id and SHA-256
    (:class:`~.research.FrozenDataset`), so the specification, the dataset and the
    aggregate are the same bytes and every completed module is reused by its reuse key at
    no cost. The modules in :attr:`RunAnalysis.retryable` are asked again in a new round;
    a module the preflight blocked is not, because code would refuse it again. The report
    then composes only if all eight complete -- its gate is unchanged.

    The spend limit works as it does for any start, over a ceiling that counts only the
    modules that will ask a model. Idempotent: asking twice returns the same retry.
    A cancelled run counts as finished: its unstarted modules were cancelled with it, and
    the data it collected stands. Raises :class:`AnalysisNotRetryable` with ``run_not_finished``,
    ``analysis_not_in_run``, ``dataset_missing``, ``specification_missing`` or
    ``nothing_to_retry``. The retry takes this run's specification as it stored it, by id and
    SHA-256, so a later compiler never moves the reuse key of a module it reuses.
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
    compiled = next((s for s in run.get("steps") or [] if s.get("node_key") == "compile"), None)
    compiled_output = (compiled or {}).get("output") or {}
    if (
        compiled is None
        or compiled.get("status") is not StepRunStatus.SUCCEEDED
        or compiled_output.get("artifact_type") != SPECIFICATION_ARTIFACT
        or not isinstance(compiled_output.get("artifact_id"), str)
        or not isinstance(compiled_output.get("sha256"), str)
    ):
        raise AnalysisNotRetryable(
            "specification_missing", f"run {run_id} has no compiled specification to reuse"
        )
    # Read as stored, not re-judged: the runs this repairs were stored under an earlier
    # harness, which reconstruct_run refuses to re-admit (and need not: none is shown here).
    analysis = stored_analysis(session, scope, store, run_id=run_id)
    retried = analysis.retryable
    if not retried:
        raise AnalysisNotRetryable(
            "nothing_to_retry",
            f"run {run_id} has no analysis module a model failed, left without a finding or an "
            "earlier harness stored",
        )
    asked = sum(
        1
        for m in AnalysisModuleId
        if m in retried
        or (
            m in analysis.records
            and not _reused(analysis.records[m])
            and analysis.records[m].attempts > 0
        )
        or (m not in analysis.records and m not in retried)
    )
    previous = metadata.get("analysis_retry") or {}
    frozen = FrozenDataset(
        run_id=run_id,
        artifact_id=output["artifact_id"],
        sha256=output["sha256"],
        analysis_round=int(previous.get("round", 0)) + 1,
        retried=tuple(m.value for m in retried),
        modules_asked=asked,
        specification_artifact_id=compiled_output["artifact_id"],
        specification_sha256=compiled_output["sha256"],
        tried=tuple(m.value for m in analysis.retried),
    )
    return runs.retry_analysis(
        run_id,
        frozen_dataset=frozen,
        reservations=reservations,
        confirm_cost_usd=confirm_cost_usd,
        acknowledge=acknowledge,
    )
