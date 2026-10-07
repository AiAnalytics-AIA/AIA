"""The research workflow's steps (ADR 0016): compile, preflight, fieldwork, and after.

Each executor is a thin shell around a pure function in ``aia_core``: it reads its
inputs under the lease-issued scope, calls the function, stores the result as an
artifact of the Study's research (``research_artifacts``), and returns the
artifact's identity. The function is the method; the executor only moves data.

Upstream results are found through the run itself -- the output a finished step
recorded -- never through an id in the step's payload, so a step cannot be
pointed at another run's, or another Study's, artifact.

**Fieldwork is a boundary.** :class:`FieldworkExecutor` produces a dataset from the
source the run recorded at creation, and only from a source its composition was
given. ``ai_runtime`` is produced by the AI respondent engine
(:class:`~aia_executors.ai_fieldwork.AIFieldwork`) when the composition built one
-- only when the AI runtime is configured (``AIA_AI_RUNTIME_ENABLED``) -- and parks
the run (``RUNTIME_UNAVAILABLE``) otherwise, or when the gateway refuses its
material; nothing downstream runs while it waits. The fictional synthetic source
exists only in ``aia_executors.workbench``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Final, Protocol

from aia_core.application.research import research_artifacts
from aia_core.domain.fieldwork import (
    FieldworkDataset,
    FieldworkSource,
    InvalidDataset,
    validate_dataset,
)
from aia_core.domain.pipeline import fingerprint
from aia_core.domain.research_aggregate import AGGREGATE_VERSION, aggregate_dataset
from aia_core.domain.research_design import (
    ResearchSpecification,
    assess_readiness,
    compile_design,
)
from aia_core.domain.research_sociomap import SOCIOMAP_VERSION, research_sociomaps
from aia_core.domain.research_sociomapping import SOCIOMAPPING_VERSION, research_sociomappings
from aia_core.domain.sociomap import AIA_SOCIOMAP_V1, ENGINE_IMPLEMENTATION_VERSION
from aia_core.domain.sociomap.hmodel_candidate import CANDIDATE_METHOD, CandidateParameters
from aia_core.domain.workflow import FailureClass
from aia_core.domain.workflow_templates import RESEARCH_KINDS, SOCIOMAPPING_STEP_KIND
from aia_core.infrastructure.artifact_repository import ArtifactRepository
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import ArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome, Succeeded
from sqlalchemy.orm import Session

from .ai_fieldwork import ProducedDataset

__all__ = [
    "FIELDWORK_DATASET",
    "READINESS",
    "SOCIOMAP",
    "SPECIFICATION",
    "AIDatasetProducer",
    "AggregateExecutor",
    "CompileExecutor",
    "DatasetProducer",
    "FieldworkExecutor",
    "PreflightExecutor",
    "SociomapExecutor",
    "SociomappingExecutor",
    "research_registry",
    "upstream_artifact",
]

AGGREGATE: Final = "research_aggregate"
SOCIOMAP: Final = "research_sociomap"
SOCIOMAPPING: Final = "research_sociomapping"
SPECIFICATION: Final = "research_specification"
READINESS: Final = "research_readiness"
FIELDWORK_DATASET: Final = "research_fieldwork_dataset"

#: What a fieldwork source is, to the executor: the specification in, a dataset out.
DatasetProducer = Callable[[ResearchSpecification], FieldworkDataset]


class AIDatasetProducer(Protocol):
    """The ``ai_runtime`` source: it needs the attempt's context, to meter and ledger calls."""

    def produce(
        self, spec: ResearchSpecification, step: StepInput, context: StepContext
    ) -> ProducedDataset | Failed: ...


_RUNTIME_UNAVAILABLE_MESSAGE: Final = (
    "AI respondenti zatím nejsou nasazeni. Běh čeká u sběru dat; nic nebylo vymyšleno "
    "ani nahrazeno a další kroky se nespustí, dokud sběr neproběhne."
)


# --------------------------------------------------------------------------- #
# shared
# --------------------------------------------------------------------------- #


def upstream_artifact(workflow: WorkflowRepository, step: StepInput, node_key: str) -> str | None:
    """The artifact the run's ``node_key`` step recorded, or ``None`` if it has none."""
    output = workflow.step_output(step.run_id, node_key)
    artifact_id = (output or {}).get("artifact_id")
    return str(artifact_id) if artifact_id else None


def _artifacts(session: Session, context: StepContext, store: ArtifactStore) -> ArtifactRepository:
    return research_artifacts(session, context.scope, store)


def _read_spec(repo: ArtifactRepository, artifact_id: str) -> ResearchSpecification:
    payload = repo.read_json(artifact_id)
    return ResearchSpecification.model_validate(payload["specification"])


def _missing_upstream(node_key: str) -> Failed:
    return Failed(
        FailureClass.MISSING_CONFIGURATION,
        error={"message": f"the run's {node_key!r} step recorded no artifact"},
    )


def _produced(
    step: StepInput, artifact: Any, created: bool, artifact_type: str, **extra: Any
) -> Succeeded:
    return Succeeded(
        output={
            "artifact_id": artifact.artifact_id,
            "artifact_type": artifact_type,
            "sha256": artifact.sha256,
            "size_bytes": artifact.size_bytes,
            "reused": not created,
            **extra,
        }
    )


class _Step:
    def __init__(self, *, store: ArtifactStore, build: BuildIdentity) -> None:
        self._store = store
        self._build = build

    def _put(
        self,
        repo: ArtifactRepository,
        step: StepInput,
        *,
        payload: dict[str, Any],
        artifact_type: str,
        input_fingerprint: str,
        depends_on: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[Any, bool]:
        return repo.put_json(
            payload={
                **payload,
                "produced_by": {"run_id": step.run_id, "step_id": step.step_id, "kind": step.kind},
                "runtime_version": self._build.sha,
            },
            project_id=step.project_id,
            revision=step.project_revision,
            stage_type=step.stage_type,
            artifact_type=artifact_type,
            input_fingerprint=input_fingerprint,
            runtime_version=self._build.sha or "",
            produced_by_job_id=step.attempt_id,
            metadata={"run_id": step.run_id, "step_id": step.step_id, **(metadata or {})},
            depends_on=depends_on,
        )


# --------------------------------------------------------------------------- #
# compile, preflight
# --------------------------------------------------------------------------- #


class CompileExecutor(_Step):
    """The Design Revision the run is pinned to -> a research specification artifact."""

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        revision_id = str(step.payload.get("design_revision_id") or "")
        with context.transaction() as (session, _workflow):
            designs = StudyDesignRepository(session, context.scope)
            content = designs.content(revision_id)
            spec, problems = compile_design(content)
            if spec is None:
                return Failed(
                    FailureClass.SCHEMA_VIOLATION,
                    error={
                        "message": "Návrh nelze sestavit do dotazníku.",
                        "problems": [p.model_dump() for p in problems],
                    },
                )
            artifact, created = self._put(
                _artifacts(session, context, self._store),
                step,
                payload={
                    "kind": SPECIFICATION,
                    "design_revision_id": revision_id,
                    "specification": spec.model_dump(mode="json"),
                    "specification_fingerprint": spec.fingerprint(),
                },
                artifact_type=SPECIFICATION,
                input_fingerprint=fingerprint(
                    {"design": content, "compiler": spec.compiler_version}
                ),
            )
        context.progress("specifikace sestavena", artifact_id=artifact.artifact_id)
        return _produced(
            step, artifact, created, SPECIFICATION, specification_fingerprint=spec.fingerprint()
        )


class PreflightExecutor(_Step):
    """AIA's structural readiness checks over the specification, stored as evidence."""

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        with context.transaction() as (session, workflow):
            spec_id = upstream_artifact(workflow, step, "compile")
            if spec_id is None:
                return _missing_upstream("compile")
            repo = _artifacts(session, context, self._store)
            spec = _read_spec(repo, spec_id)
            readiness = assess_readiness(spec)
            artifact, created = self._put(
                repo,
                step,
                payload={"kind": READINESS, "readiness": readiness.model_dump(mode="json")},
                artifact_type=READINESS,
                input_fingerprint=fingerprint(
                    {"spec": spec.fingerprint(), "rules": readiness.rules}
                ),
                depends_on=[spec_id],
            )
        if not readiness.ready:
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={
                    "message": "Návrh neprošel kontrolou připravenosti.",
                    "readiness_artifact_id": artifact.artifact_id,
                    "failed": [
                        c.model_dump(mode="json") for c in readiness.checks if c.status == "FAIL"
                    ],
                },
            )
        context.progress("návrh je připraven", artifact_id=artifact.artifact_id)
        return _produced(step, artifact, created, READINESS)


# --------------------------------------------------------------------------- #
# fieldwork
# --------------------------------------------------------------------------- #


class FieldworkExecutor(_Step):
    """Produce the run's fieldwork dataset from its recorded source, or park.

    ``producers`` are the deterministic sources this composition provides (only the
    workbench gives one, the fictional fixture); ``ai_runtime`` is the AI respondent
    engine, when the composition built one. A run whose recorded source is
    ``ai_runtime`` is **never** given another source's data: with no engine it parks,
    and the synthetic fixture cannot be registered for it. A run recorded with a
    source the composition does not provide fails permanently.
    """

    def __init__(
        self,
        *,
        store: ArtifactStore,
        build: BuildIdentity,
        producers: Mapping[FieldworkSource, DatasetProducer] | None = None,
        ai_runtime: AIDatasetProducer | None = None,
    ) -> None:
        super().__init__(store=store, build=build)
        self._producers = dict(producers or {})
        if FieldworkSource.AI_RUNTIME in self._producers:
            raise ValueError("the AI runtime is not a dataset producer; pass it as ai_runtime")
        self._ai = ai_runtime

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        try:
            source = FieldworkSource(str(step.payload.get("fieldwork_source")))
        except ValueError:
            return Failed(
                FailureClass.MISSING_CONFIGURATION,
                error={
                    "message": f"unknown fieldwork source {step.payload.get('fieldwork_source')!r}"
                },
            )
        if source is FieldworkSource.AI_RUNTIME and self._ai is None:
            return Failed(
                FailureClass.RUNTIME_UNAVAILABLE,
                error={"message": _RUNTIME_UNAVAILABLE_MESSAGE, "source": source.value},
            )
        producer = self._producers.get(source)
        if source is not FieldworkSource.AI_RUNTIME and producer is None:
            return Failed(
                FailureClass.MISSING_CONFIGURATION,
                error={
                    "message": (
                        f"this worker does not provide the {source.value!r} fieldwork source"
                    ),
                    "source": source.value,
                },
            )
        with context.transaction() as (session, workflow):
            spec_id = upstream_artifact(workflow, step, "compile")
            if spec_id is None:
                return _missing_upstream("compile")
            repo = _artifacts(session, context, self._store)
            spec = _read_spec(repo, spec_id)

        provenance: dict[str, Any] | None = None
        if source is FieldworkSource.AI_RUNTIME:
            assert self._ai is not None
            produced = self._ai.produce(spec, step, context)
            if isinstance(produced, Failed):
                return produced
            dataset, provenance = produced.dataset, produced.provenance
        else:
            assert producer is not None
            dataset = producer(spec)
        try:
            validate_dataset(spec, dataset)
        except InvalidDataset as exc:
            return Failed(FailureClass.SCHEMA_VIOLATION, error={"message": str(exc)})
        origin = dataset.origin.value if dataset.origin else None
        fingerprint_inputs: dict[str, Any] = {
            "spec": spec.fingerprint(),
            "source": source.value,
            "generator": dataset.generator,
            "seed": dataset.seed,
        }
        if provenance is not None:
            # A model's answers are not a function of the inputs: every attempt's
            # dataset is its own artifact, never "reused" over another attempt's.
            fingerprint_inputs["attempt"] = step.attempt_id
        payload: dict[str, Any] = {
            "kind": FIELDWORK_DATASET,
            "dataset": dataset.model_dump(mode="json"),
        }
        if provenance is not None:
            payload["provenance"] = provenance
        context.checkpoint()
        with context.transaction() as (session, _workflow):
            artifact, created = self._put(
                _artifacts(session, context, self._store),
                step,
                payload=payload,
                artifact_type=FIELDWORK_DATASET,
                input_fingerprint=fingerprint(fingerprint_inputs),
                depends_on=[spec_id],
                metadata={"data_origin": origin, "fieldwork_source": source.value},
            )
        context.progress(
            "fiktivní data připravena" if dataset.is_synthetic else "sběr dat dokončen",
            artifact_id=artifact.artifact_id,
            respondents=len(dataset.respondents),
        )
        return _produced(
            step,
            artifact,
            created,
            FIELDWORK_DATASET,
            data_origin=origin,
            respondents=len(dataset.respondents),
        )


# --------------------------------------------------------------------------- #
# after fieldwork: deterministic methods over the dataset
# --------------------------------------------------------------------------- #


def _read_dataset(repo: ArtifactRepository, artifact_id: str) -> FieldworkDataset:
    return FieldworkDataset.model_validate(repo.read_json(artifact_id)["dataset"])


class AggregateExecutor(_Step):
    """The fieldwork dataset -> the unit's weighted, donor-aware aggregates (chunk 5)."""

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        with context.transaction() as (session, workflow):
            spec_id = upstream_artifact(workflow, step, "compile")
            dataset_id = upstream_artifact(workflow, step, "run")
            if spec_id is None:
                return _missing_upstream("compile")
            if dataset_id is None:
                return _missing_upstream("run")
            repo = _artifacts(session, context, self._store)
            spec = _read_spec(repo, spec_id)
            dataset = _read_dataset(repo, dataset_id)
            dataset_sha = repo.get(dataset_id).sha256
        try:
            validate_dataset(spec, dataset)
        except InvalidDataset as exc:
            return Failed(FailureClass.SCHEMA_VIOLATION, error={"message": str(exc)})
        result = aggregate_dataset(spec, dataset)
        context.checkpoint()
        origin = result["data_origin"]
        with context.transaction() as (session, _workflow):
            artifact, created = self._put(
                _artifacts(session, context, self._store),
                step,
                payload={"kind": AGGREGATE, "aggregate": result},
                artifact_type=AGGREGATE,
                input_fingerprint=fingerprint(
                    {
                        "dataset": dataset_sha,
                        "aggregate": AGGREGATE_VERSION,
                        "spec": spec.fingerprint(),
                    }
                ),
                depends_on=[spec_id, dataset_id],
                metadata={"data_origin": origin},
            )
        context.progress("agregace spočtena", artifact_id=artifact.artifact_id)
        return _produced(step, artifact, created, AGGREGATE, data_origin=origin)


def _sociomap_fingerprint(dataset_sha: str, spec: ResearchSpecification) -> str:
    """What a stored Sociomap was computed from, for reuse.

    The engine's implementation version is part of it: an engine whose output
    changed (1.2.0 stopped placing straight-liners) must not be handed a map the
    previous one drew for the same dataset and spec.
    """
    return fingerprint(
        {
            "dataset": dataset_sha,
            "sociomap": SOCIOMAP_VERSION,
            "preset": AIA_SOCIOMAP_V1.fingerprint(),
            "engine": ENGINE_IMPLEMENTATION_VERSION,
            "spec": spec.fingerprint(),
        }
    )


class SociomapExecutor(_Step):
    """Each tracked set's relation matrix and Sociomap: stored, and INTERNAL_ONLY (chunk 6)."""

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        with context.transaction() as (session, workflow):
            spec_id = upstream_artifact(workflow, step, "compile")
            dataset_id = upstream_artifact(workflow, step, "run")
            if spec_id is None:
                return _missing_upstream("compile")
            if dataset_id is None:
                return _missing_upstream("run")
            repo = _artifacts(session, context, self._store)
            spec = _read_spec(repo, spec_id)
            dataset = _read_dataset(repo, dataset_id)
            dataset_sha = repo.get(dataset_id).sha256
        try:
            validate_dataset(spec, dataset)
        except InvalidDataset as exc:
            return Failed(FailureClass.SCHEMA_VIOLATION, error={"message": str(exc)})
        result = research_sociomaps(spec, dataset)
        context.checkpoint()
        origin = result["data_origin"]
        with context.transaction() as (session, _workflow):
            artifact, created = self._put(
                _artifacts(session, context, self._store),
                step,
                payload={"kind": SOCIOMAP, "sociomap": result},
                artifact_type=SOCIOMAP,
                input_fingerprint=_sociomap_fingerprint(dataset_sha, spec),
                depends_on=[spec_id, dataset_id],
                metadata={
                    "data_origin": origin,
                    "methodology_status": result["methodology_status"],
                },
            )
        context.progress("Sociomapa spočtena (interní)", artifact_id=artifact.artifact_id)
        return _produced(
            step,
            artifact,
            created,
            SOCIOMAP,
            data_origin=origin,
            methodology_status=result["methodology_status"],
        )


class SociomappingExecutor(_Step):
    """Each tracked set's experimental Sociomapping (plan sociomapping-engine I1).

    Declared relations, the experimental AIA H-Model, heights and coherences, with every
    fingerprint, version, parameter and rule id. ``EXPERIMENTAL_AIA`` and never client-facing.
    """

    def __init__(
        self,
        *,
        store: ArtifactStore,
        build: BuildIdentity,
        parameters: CandidateParameters | None = None,
    ) -> None:
        super().__init__(store=store, build=build)
        self._parameters = parameters or CandidateParameters()

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        with context.transaction() as (session, workflow):
            spec_id = upstream_artifact(workflow, step, "compile")
            dataset_id = upstream_artifact(workflow, step, "run")
            if spec_id is None:
                return _missing_upstream("compile")
            if dataset_id is None:
                return _missing_upstream("run")
            repo = _artifacts(session, context, self._store)
            spec = _read_spec(repo, spec_id)
            dataset = _read_dataset(repo, dataset_id)
            dataset_sha = repo.get(dataset_id).sha256
        try:
            validate_dataset(spec, dataset)
        except InvalidDataset as exc:
            return Failed(FailureClass.SCHEMA_VIOLATION, error={"message": str(exc)})
        context.progress("Sociomapping: vztahy a experimentální H-Model se počítají")
        result = research_sociomappings(spec, dataset, self._parameters)
        result["inputs"] = {
            "specification_artifact_id": spec_id,
            "specification_fingerprint": spec.fingerprint(),
            "dataset_artifact_id": dataset_id,
            "dataset_sha256": dataset_sha,
        }
        context.checkpoint()
        origin = result["data_origin"]
        with context.transaction() as (session, _workflow):
            artifact, created = self._put(
                _artifacts(session, context, self._store),
                step,
                payload={"kind": SOCIOMAPPING, "sociomapping": result},
                artifact_type=SOCIOMAPPING,
                input_fingerprint=fingerprint(
                    {
                        "dataset": dataset_sha,
                        "sociomapping": SOCIOMAPPING_VERSION,
                        "method": CANDIDATE_METHOD,
                        "parameters": self._parameters.model_dump(mode="json"),
                        "spec": spec.fingerprint(),
                    }
                ),
                depends_on=[spec_id, dataset_id],
                metadata={
                    "data_origin": origin,
                    "method_status": result["method_status"],
                    "client_facing": False,
                },
            )
        context.progress("Sociomapping spočten (experimentální)", artifact_id=artifact.artifact_id)
        return _produced(
            step,
            artifact,
            created,
            SOCIOMAPPING,
            data_origin=origin,
            method_status=result["method_status"],
        )


def research_registry(
    *,
    store: ArtifactStore,
    build: BuildIdentity,
    producers: Mapping[FieldworkSource, DatasetProducer] | None = None,
    ai_runtime: AIDatasetProducer | None = None,
) -> dict[str, Any]:
    """The research step kinds -> executors. ``producers`` only from the workbench;
    ``ai_runtime`` only from a composition whose AI runtime is configured."""
    return {
        RESEARCH_KINDS["compile"]: CompileExecutor(store=store, build=build),
        RESEARCH_KINDS["preflight"]: PreflightExecutor(store=store, build=build),
        RESEARCH_KINDS["run"]: FieldworkExecutor(
            store=store, build=build, producers=producers, ai_runtime=ai_runtime
        ),
        RESEARCH_KINDS["aggregate"]: AggregateExecutor(store=store, build=build),
        RESEARCH_KINDS["sociomap"]: SociomapExecutor(store=store, build=build),
        SOCIOMAPPING_STEP_KIND: SociomappingExecutor(store=store, build=build),
    }
