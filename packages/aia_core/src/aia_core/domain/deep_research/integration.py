"""Why a Deep Research run runs, what it researches, and what it is anchored to (ADR 0021).

The engine -- retrieval, acquisition, investigation, the lead, fan-out, verification,
grounding, confidence and the sealed :class:`~.bundle.EvidenceBundle` -- is frozen after
PR #166. AIA's methodology uses it at two checkpoints, and this module is the envelope
that says which, *around* the engine rather than inside it::

    DeepResearchRunSpec
    ├── contract_version   RUN_SPEC_CONTRACT
    ├── purpose            DeepResearchPurpose          why
    ├── target             ResearchTargetRef            what
    ├── lineage            FrozenLineage                which immutable AIA state
    ├── title              presentation only, never identity
    └── engine_request     DeepResearchRequest          unchanged, its fingerprint unchanged

**Purpose, target and lineage are three different things.** The purpose is why the run
exists. The target is the research object a person asked about: a Design Revision, one
question's result, a battery object's result, an analysis module, a battery's Sociomap,
one of its objects, or a pair of them. The lineage is the exact immutable state
underneath it: the Design Revision's content hash, and for interpretation every
artifact of the producing research run the target rests on, pinned by id and SHA256.
A newer result is another run and so another lineage; nothing here is ever "the latest".

**Two identities, kept apart.** :meth:`DeepResearchRunSpec.fingerprint` is the
orchestration identity -- purpose, target, lineage and the engine request's own
fingerprint -- and keys the run. The engine's fingerprints (the request's, every
track's) are not touched, so two runs that differ only in purpose are two runs that
share the engine's reusable work.

**No authority to write.** Neither purpose may change an approved design or anything
of the deterministic research chain (:data:`DETERMINISTIC_ARTIFACT_TYPES`). Design
Research may only propose, and a person turns a proposal into a new Design Revision;
Interpretation Research may only produce evidence about a result. The engine's own
artifact types are checked disjoint from the deterministic ones when this module is
imported, so an engine change that wrote one would not load.

**The Sociomap's direction.** Interpretation Research may read the frozen canonical Sociomap.
Deep Research and external evidence are never inputs to the canonical Sociomap calculation. A
Sociomap target is a read-only reference into the frozen map, pinned by id and SHA256; and
``research_sociomap*`` is in :data:`DETERMINISTIC_ARTIFACT_TYPES`, which no purpose may write.

Only identifiers that exist are targets. There is no segment target (no segment
identifier exists: ``research_aggregate.py`` has no segment tables), no Sociomap region
(none exist), and no analysis finding id (findings carry none). Each is added when the
domain gains the identifier, as a new variant of the closed union.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..analysis.modules import AnalysisModuleId
from .contracts import DeepResearchRequest, digest
from .workflow import ARTIFACT_TYPES

__all__ = [
    "AGGREGATE_ARTIFACT",
    "ANALYSIS_MODULE_ARTIFACT",
    "DETERMINISTIC_ARTIFACT_TYPES",
    "LEGACY_UNVERSIONED",
    "RUN_SPEC_CONTRACT",
    "SOCIOMAP_ARTIFACT",
    "AnalysisModuleTarget",
    "ArtifactPin",
    "DeepResearchProvenance",
    "DeepResearchPurpose",
    "DeepResearchRunSpec",
    "DesignLineage",
    "DesignRevisionTarget",
    "FrozenLineage",
    "InterpretationLineage",
    "MethodologyBoundaryViolation",
    "PurposeAuthority",
    "PurposeSource",
    "ResearchTargetRef",
    "ResultBatteryObjectTarget",
    "ResultQuestionTarget",
    "SociomapObjectTarget",
    "SociomapRelationshipTarget",
    "SociomapTarget",
    "TargetKind",
    "authority_of",
    "require_engine_writes_are_sidecars",
    "require_may_write",
    "run_spec_identity",
    "target_node",
]

#: The orchestration envelope's version. A change to what it identifies is a new value;
#: it is not the engine's ``HARNESS_VERSION``, which moves only when the method does.
RUN_SPEC_CONTRACT: Final = "aia-deep-research-run-spec-1"
#: How a run stored before this contract reads: no purpose, no target, no lineage, said so.
LEGACY_UNVERSIONED: Final = "legacy-unversioned"

#: The deterministic research chain's artifact types (ADR 0016, ``aia_executors.research``,
#: ``domain/analysis/artifact.py``): respondent data, aggregates, analysis, Sociomaps.
SPECIFICATION_ARTIFACT: Final = "research_specification"
READINESS_ARTIFACT: Final = "research_readiness"
DATASET_ARTIFACT: Final = "research_fieldwork_dataset"
AGGREGATE_ARTIFACT: Final = "research_aggregate"
SOCIOMAP_ARTIFACT: Final = "research_sociomap"
SOCIOMAPPING_ARTIFACT: Final = "research_sociomapping"
ANALYSIS_MODULE_ARTIFACT: Final = "research_analysis_module"
ANALYSIS_TURN_ARTIFACT: Final = "research_analysis_turn"
DETERMINISTIC_ARTIFACT_TYPES: Final[frozenset[str]] = frozenset(
    {
        SPECIFICATION_ARTIFACT,
        READINESS_ARTIFACT,
        DATASET_ARTIFACT,
        AGGREGATE_ARTIFACT,
        SOCIOMAP_ARTIFACT,
        SOCIOMAPPING_ARTIFACT,
        ANALYSIS_MODULE_ARTIFACT,
        ANALYSIS_TURN_ARTIFACT,
    }
)
#: What an approved design is, as something Deep Research must never write.
DESIGN_REVISION: Final = "design_revision"

_REV = r"^REV-[0-9a-f]{1,32}$"
_RUN = r"^RUN-[0-9a-f]{1,32}$"
_ART = r"^ART-[0-9a-f]{16}$"
_SHA = r"^[0-9a-f]{64}$"


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _entity() -> Any:
    return Field(min_length=1, max_length=200)


# --------------------------------------------------------------------------- #
# Purpose
# --------------------------------------------------------------------------- #


class DeepResearchPurpose(StrEnum):
    """Why a Deep Research run exists: one of AIA's two methodological checkpoints."""

    #: Before the methodology freeze: context, terms, constructs, benchmarks and gaps that
    #: may become *proposals*; a person turns a proposal into a new Design Revision.
    DESIGN_RESEARCH = "DESIGN_RESEARCH"
    #: After deterministic results exist: corroborate, challenge, benchmark or explain a
    #: result. It never changes the result it reads.
    INTERPRETATION_RESEARCH = "INTERPRETATION_RESEARCH"


class PurposeSource(StrEnum):
    """How a run's purpose was stated (recorded, never part of its identity)."""

    #: The caller named the purpose.
    EXPLICIT = "EXPLICIT"
    #: The deployed start API's shape, which names none: a new request through it is
    #: Design Research, by this compatibility rule and only for new requests (ADR 0021).
    LEGACY_DEFAULT = "LEGACY_DEFAULT"


# --------------------------------------------------------------------------- #
# Target
# --------------------------------------------------------------------------- #


class TargetKind(StrEnum):
    DESIGN_REVISION = "DESIGN_REVISION"
    RESULT_QUESTION = "RESULT_QUESTION"
    RESULT_BATTERY_OBJECT = "RESULT_BATTERY_OBJECT"
    ANALYSIS_MODULE = "ANALYSIS_MODULE"
    SOCIOMAP = "SOCIOMAP"
    SOCIOMAP_OBJECT = "SOCIOMAP_OBJECT"
    SOCIOMAP_RELATIONSHIP = "SOCIOMAP_RELATIONSHIP"


class DesignRevisionTarget(_Closed):
    """A Study's Design Revision: what Design Research informs."""

    kind: Literal["DESIGN_REVISION"]
    design_revision_id: str = Field(pattern=_REV)


class ResultQuestionTarget(_Closed):
    """One question's deterministic result in a research run's ``research_aggregate``."""

    kind: Literal["RESULT_QUESTION"]
    research_run_id: str = Field(pattern=_RUN)
    aggregate_artifact_id: str = Field(pattern=_ART)
    question_id: str = _entity()


class ResultBatteryObjectTarget(_Closed):
    """One tracked object's result in a battery of a run's ``research_aggregate``."""

    kind: Literal["RESULT_BATTERY_OBJECT"]
    research_run_id: str = Field(pattern=_RUN)
    aggregate_artifact_id: str = Field(pattern=_ART)
    battery_id: str = _entity()
    object_id: str = _entity()


class AnalysisModuleTarget(_Closed):
    """One analysis module's stored outcome (``research_analysis_module``) of a run."""

    kind: Literal["ANALYSIS_MODULE"]
    research_run_id: str = Field(pattern=_RUN)
    analysis_artifact_id: str = Field(pattern=_ART)
    module_id: AnalysisModuleId


class SociomapTarget(_Closed):
    """One battery's canonical Sociomap in a run's ``research_sociomap``."""

    kind: Literal["SOCIOMAP"]
    research_run_id: str = Field(pattern=_RUN)
    sociomap_artifact_id: str = Field(pattern=_ART)
    battery_id: str = _entity()


class SociomapObjectTarget(_Closed):
    """One object of a battery's canonical Sociomap."""

    kind: Literal["SOCIOMAP_OBJECT"]
    research_run_id: str = Field(pattern=_RUN)
    sociomap_artifact_id: str = Field(pattern=_ART)
    battery_id: str = _entity()
    object_id: str = _entity()


class SociomapRelationshipTarget(_Closed):
    """The relation between two objects of a battery's canonical Sociomap.

    The relation matrix is symmetric (``research_sociomap.derive_relation_matrix``), so a
    pair is one relationship whichever way it is named: the two ids are kept in sorted
    order, and the same pair always has the same identity.
    """

    kind: Literal["SOCIOMAP_RELATIONSHIP"]
    research_run_id: str = Field(pattern=_RUN)
    sociomap_artifact_id: str = Field(pattern=_ART)
    battery_id: str = _entity()
    source_object_id: str = _entity()
    target_object_id: str = _entity()

    @model_validator(mode="before")
    @classmethod
    def _ordered(cls, data: Any) -> Any:
        if isinstance(data, dict):
            a, b = data.get("source_object_id"), data.get("target_object_id")
            if isinstance(a, str) and isinstance(b, str):
                if a == b:
                    raise ValueError("a relationship is between two different objects")
                if b < a:
                    data = {**data, "source_object_id": b, "target_object_id": a}
        return data


ResearchTargetRef = Annotated[
    DesignRevisionTarget
    | ResultQuestionTarget
    | ResultBatteryObjectTarget
    | AnalysisModuleTarget
    | SociomapTarget
    | SociomapObjectTarget
    | SociomapRelationshipTarget,
    Field(discriminator="kind"),
]

_INTERPRETATION_TARGETS: Final = (
    ResultQuestionTarget,
    ResultBatteryObjectTarget,
    AnalysisModuleTarget,
    SociomapTarget,
    SociomapObjectTarget,
    SociomapRelationshipTarget,
)


def target_node(target: ResearchTargetRef) -> tuple[str, str, str] | None:
    """For a result-side target: (the research run's node key, the artifact id the target
    names, the artifact type that node stores). None for a Design Revision."""
    if isinstance(target, ResultQuestionTarget | ResultBatteryObjectTarget):
        return "aggregate", target.aggregate_artifact_id, AGGREGATE_ARTIFACT
    if isinstance(target, AnalysisModuleTarget):
        return (
            f"analysis_{target.module_id.value}",
            target.analysis_artifact_id,
            ANALYSIS_MODULE_ARTIFACT,
        )
    if isinstance(target, SociomapTarget | SociomapObjectTarget | SociomapRelationshipTarget):
        return "sociomap", target.sociomap_artifact_id, SOCIOMAP_ARTIFACT
    return None


# --------------------------------------------------------------------------- #
# Lineage
# --------------------------------------------------------------------------- #


class ArtifactPin(_Closed):
    """One immutable artifact a run is anchored to: the producing step, its id and hash."""

    node_key: str = Field(min_length=1, max_length=64)
    artifact_id: str = Field(pattern=_ART)
    artifact_type: str = Field(min_length=1, max_length=64)
    sha256: str = Field(pattern=_SHA)


class DesignLineage(_Closed):
    """The exact Design Revision: its id, its number in the Study and its content's hash."""

    kind: Literal["DESIGN"]
    design_revision_id: str = Field(pattern=_REV)
    design_revision: int = Field(ge=1)
    design_content_sha256: str = Field(pattern=_SHA)


class InterpretationLineage(_Closed):
    """The exact results under an interpretation: the run, the revision it executed, and
    every artifact the target rests on (specification, dataset, aggregate, the target's
    own), each pinned by id and SHA256, in node order."""

    kind: Literal["INTERPRETATION"]
    research_run_id: str = Field(pattern=_RUN)
    design: DesignLineage
    artifacts: tuple[ArtifactPin, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _one_per_node(self) -> InterpretationLineage:
        keys = [p.node_key for p in self.artifacts]
        if keys != sorted(set(keys)):
            raise ValueError("one pin per node, in node-key order")
        return self

    def pin(self, node_key: str) -> ArtifactPin | None:
        return next((p for p in self.artifacts if p.node_key == node_key), None)


FrozenLineage = Annotated[DesignLineage | InterpretationLineage, Field(discriminator="kind")]


# --------------------------------------------------------------------------- #
# The run spec
# --------------------------------------------------------------------------- #


class DeepResearchRunSpec(_Closed):
    """A governed Deep Research run: purpose, target and frozen lineage around the engine.

    Its validation is the purpose--target--lineage rule: Design Research targets a Design
    Revision and is anchored to that revision; Interpretation Research targets a result
    and is anchored to the research run that produced it, whose Design Revision is the one
    the engine request was frozen from. Any other combination does not construct.
    """

    contract_version: Literal["aia-deep-research-run-spec-1"]
    purpose: DeepResearchPurpose
    target: ResearchTargetRef
    lineage: FrozenLineage
    engine_request: DeepResearchRequest
    #: A person's name for the run. Presentation only: not part of :meth:`fingerprint`.
    title: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _coherent(self) -> DeepResearchRunSpec:
        design = self.lineage if isinstance(self.lineage, DesignLineage) else self.lineage.design
        if self.engine_request.design_revision_id != design.design_revision_id or (
            self.engine_request.design_revision != design.design_revision
        ):
            raise ValueError("the engine request is not frozen from the lineage's Design Revision")
        if self.purpose is DeepResearchPurpose.DESIGN_RESEARCH:
            if not isinstance(self.target, DesignRevisionTarget):
                raise ValueError("Design Research targets a Design Revision")
            if not isinstance(self.lineage, DesignLineage):
                raise ValueError("Design Research is anchored to a design, not to results")
            if self.target.design_revision_id != self.lineage.design_revision_id:
                raise ValueError("the target is not the lineage's Design Revision")
            return self
        if not isinstance(self.target, _INTERPRETATION_TARGETS):
            raise ValueError("Interpretation Research targets a result, not a design")
        if not isinstance(self.lineage, InterpretationLineage):
            raise ValueError("Interpretation Research is anchored to results")
        node = target_node(self.target)
        assert node is not None
        node_key, artifact_id, artifact_type = node
        if self.target.research_run_id != self.lineage.research_run_id:
            raise ValueError("the target is not of the lineage's research run")
        pin = self.lineage.pin(node_key)
        if pin is None or pin.artifact_id != artifact_id or pin.artifact_type != artifact_type:
            raise ValueError("the lineage does not pin the target's artifact")
        return self

    def engine_request_fingerprint(self) -> str:
        """The engine's own identity, unchanged: what its reuse is keyed by."""
        return self.engine_request.fingerprint()

    def identity(self) -> dict[str, Any]:
        """Everything the orchestration identity covers (never the title)."""
        return run_spec_identity(
            self.purpose, self.target, self.lineage, self.engine_request_fingerprint()
        )

    def fingerprint(self) -> str:
        """The orchestration identity: two runs differ when any of these differ."""
        return digest(self.identity())


def run_spec_identity(
    purpose: DeepResearchPurpose,
    target: ResearchTargetRef,
    lineage: DesignLineage | InterpretationLineage,
    engine_request_fingerprint: str,
) -> dict[str, Any]:
    """The orchestration identity's parts. The one definition: a stored run's spec is
    re-checked against it without its engine request (whose fingerprint is stored)."""
    return {
        "contract_version": RUN_SPEC_CONTRACT,
        "purpose": purpose.value,
        "target": target.model_dump(mode="json"),
        "lineage": lineage.model_dump(mode="json"),
        "engine_request_fingerprint": engine_request_fingerprint,
    }


class DeepResearchProvenance(_Closed):
    """What a later consumer (a report, a Research Lens) cites for a governed run's output.

    Assembled from durable state only: the run's stored spec, the publish step's bundle
    artifact (its id and the row's SHA256) and the sealed bundle's own seal. The bundle
    itself is unchanged; this envelope references it.
    """

    contract_version: Literal["aia-deep-research-run-spec-1"]
    run_id: str = Field(pattern=_RUN)
    purpose: DeepResearchPurpose
    target: ResearchTargetRef
    lineage: FrozenLineage
    run_spec_fingerprint: str = Field(pattern=_SHA)
    engine_request_fingerprint: str = Field(pattern=_SHA)
    evidence_bundle_artifact_id: str = Field(pattern=_ART)
    evidence_bundle_artifact_sha256: str = Field(pattern=_SHA)
    evidence_bundle_seal: str = Field(pattern=_SHA)


# --------------------------------------------------------------------------- #
# Authority
# --------------------------------------------------------------------------- #


class MethodologyBoundaryViolation(Exception):
    """Deep Research asked to change what only a person or the deterministic chain may."""


@dataclass(frozen=True, slots=True)
class PurposeAuthority:
    """What a purpose may do to AIA's state: propose, and write its own evidence; nothing else."""

    purpose: DeepResearchPurpose
    #: What it may *propose* for a person to accept (ADR 0019 gate 1).
    may_propose: frozenset[str]
    #: What it may write itself: the engine's own evidence artifacts (``deep_research_*``),
    #: sidecars beside the research state, never the research state.
    may_write: frozenset[str]


_ENGINE_ARTIFACTS: Final[frozenset[str]] = frozenset(ARTIFACT_TYPES.values())
_AUTHORITY: Final[dict[DeepResearchPurpose, PurposeAuthority]] = {
    DeepResearchPurpose.DESIGN_RESEARCH: PurposeAuthority(
        purpose=DeepResearchPurpose.DESIGN_RESEARCH,
        may_propose=frozenset({DESIGN_REVISION}),
        may_write=_ENGINE_ARTIFACTS,
    ),
    DeepResearchPurpose.INTERPRETATION_RESEARCH: PurposeAuthority(
        purpose=DeepResearchPurpose.INTERPRETATION_RESEARCH,
        may_propose=frozenset(),
        may_write=_ENGINE_ARTIFACTS,
    ),
}


def authority_of(purpose: DeepResearchPurpose) -> PurposeAuthority:
    return _AUTHORITY[purpose]


def require_may_write(purpose: DeepResearchPurpose, artifact_type: str) -> None:
    """Refuse a Deep Research write to anything but its own evidence.

    A design or a deterministic research artifact is refused for every purpose: Design
    Research proposes and a person writes the new Design Revision; Interpretation Research
    reads results and writes none of them. Anything else not the engine's own is refused
    too: authority is listed, never inferred.
    """
    if artifact_type in DETERMINISTIC_ARTIFACT_TYPES or artifact_type == DESIGN_REVISION:
        raise MethodologyBoundaryViolation(
            f"{purpose.value} may not write {artifact_type}: "
            "Deep Research never rewrites a design or deterministic research truth"
        )
    if artifact_type not in authority_of(purpose).may_write:
        raise MethodologyBoundaryViolation(f"{purpose.value} may write no {artifact_type}")


def require_engine_writes_are_sidecars(engine_types: Iterable[str]) -> None:
    """The engine's artifact types are its own: none is a design or a deterministic one."""
    clash = sorted(set(engine_types) & (DETERMINISTIC_ARTIFACT_TYPES | {DESIGN_REVISION}))
    if clash:
        raise MethodologyBoundaryViolation(
            f"the Deep Research engine would write deterministic artifacts: {clash}"
        )


# Checked once, when the envelope is imported: an engine that wrote research truth
# would not load beside it.
require_engine_writes_are_sidecars(ARTIFACT_TYPES.values())
