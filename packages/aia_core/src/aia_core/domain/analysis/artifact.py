"""What an analysis module's outcome is when stored, and how its identity is computed.

Two artifact kinds, both JSON on the Study's owned design project, both versioned:

* ``research_analysis_module`` (:class:`ModuleArtifact`) -- one module's outcome over
  one run: ``COMPLETED`` with the draft the evidence gate accepted, or ``BLOCKED``
  with every violation that stopped it. It records where the evidence came from
  (the run's specification, dataset and aggregate artifacts, by id and SHA-256), the
  authority it was judged under, the harness, and every model turn.
* ``research_analysis_turn`` (:class:`TurnArtifact`) -- one model turn's answer,
  written as soon as the call returns. A retried attempt replays a turn it finds
  instead of paying for it again.

**No claim is stored.** An :class:`~aia_core.domain.evidence.AdmittedClaim` can be
minted only by the evidence gate, and a stored one would be a number asserted by a
file. The artifact stores the accepted *draft*; whoever reads it rebuilds the
evidence from the run's own artifacts, checks every fingerprint, and puts the draft
through the gate again (``aia_core.application.analysis_results``). If anything moved,
the reconstruction is refused, not trusted.

Parsing is strict and closed: an unknown key, another contract version, a
``COMPLETED`` outcome without a draft or a ``BLOCKED`` one without a reason are all
refused. Pure: no I/O.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Final, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from ..ai_contracts import canonical_json
from ..evidence import ClaimSurface, Violation, ViolationCode
from ..fieldwork import DataOrigin
from ..pipeline import fingerprint
from .draft import AnalysisDraft
from .modules import AnalysisModuleId, module_spec

__all__ = [
    "ANALYSIS_ARTIFACT_CONTRACT",
    "ANALYSIS_MODULE_ARTIFACT",
    "ANALYSIS_TURN_ARTIFACT",
    "TURN_ARTIFACT_CONTRACT",
    "AuthoritySummary",
    "CallRecord",
    "EvidenceSummary",
    "HarnessSummary",
    "ModuleArtifact",
    "ModuleLabels",
    "ModuleSources",
    "ProducedBy",
    "SourceRef",
    "TurnArtifact",
    "ViolationRecord",
    "module_reuse_fingerprint",
    "parse_module_artifact",
    "parse_turn_artifact",
    "turn_fingerprint",
]

ANALYSIS_MODULE_ARTIFACT: Final = "research_analysis_module"
ANALYSIS_TURN_ARTIFACT: Final = "research_analysis_turn"
ANALYSIS_ARTIFACT_CONTRACT: Final = "aia-analysis-module-artifact-1"
TURN_ARTIFACT_CONTRACT: Final = "aia-analysis-turn-1"

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
Outcome = Literal["COMPLETED", "BLOCKED"]


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _sha(value: str) -> str:
    if not _SHA256.fullmatch(value):
        raise ValueError("not a SHA-256")
    return value


Sha256 = Annotated[str, AfterValidator(_sha)]


class SourceRef(_Closed):
    """One upstream artifact of the run, by id and by content."""

    artifact_id: str = Field(min_length=1)
    sha256: Sha256


class ModuleSources(_Closed):
    """The run's artifacts the evidence was built from. Nothing else was read."""

    design_revision_id: str = Field(min_length=1)
    specification: SourceRef
    specification_fingerprint: Sha256
    dataset: SourceRef
    aggregate: SourceRef


class EvidenceSummary(_Closed):
    adapter_version: str = Field(min_length=1)
    table_fingerprint: Sha256
    rows: int = Field(ge=0)
    suppressed: tuple[str, ...]
    data_origin: DataOrigin


class AuthoritySummary(_Closed):
    """What the claims were judged under: the policy book, the certificate, the method."""

    field_policy_version: str = Field(min_length=1)
    field_policy_sha256: Sha256
    joint_status_fingerprint: Sha256
    joint_degradation: str | None
    #: The validation state the method status was computed from: none, today.
    validation: None = None
    system_fingerprint: Sha256


class HarnessSummary(_Closed):
    harness_version: str = Field(min_length=1)
    harness_sha256: Sha256
    prompt_template_version: str = Field(min_length=1)
    prompt_template_sha256: Sha256
    agent_id: str = Field(min_length=1)
    agent_version: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    schema_fingerprint: str = Field(min_length=1)
    language: str = Field(min_length=1)
    max_repairs: int = Field(ge=0)
    #: The most model calls this module may make over every attempt: one per turn.
    max_calls: int = Field(ge=1)


class CallRecord(_Closed):
    """One model turn: the call that answered it, or the checkpoint it was replayed from."""

    turn: int = Field(ge=1)
    request_sha256: Sha256
    answer: Literal["DRAFT", "SCHEMA_INVALID"]
    turn_artifact_id: str = Field(min_length=1)
    #: True when this attempt read the answer from a checkpoint and sent nothing.
    replayed: bool
    call_id: str | None
    provider_request_id: str | None
    model: str | None
    route_id: str | None
    policy_version: str | None
    cost_usd: float = Field(ge=0, allow_inf_nan=False)
    cost_basis: str | None


class ViolationRecord(_Closed):
    code: ViolationCode
    subject: str
    detail: str

    @classmethod
    def of(cls, violation: Violation) -> ViolationRecord:
        return cls(code=violation.code, subject=violation.subject, detail=violation.detail)

    def violation(self) -> Violation:
        return Violation(self.code, self.subject, self.detail)


class ModuleLabels(_Closed):
    surface: ClaimSurface
    data_origin: DataOrigin
    simulated_respondents: bool
    internal_only: bool


class ProducedBy(_Closed):
    run_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)


class ModuleArtifact(_Closed):
    """One analysis module's stored outcome (contract ``aia-analysis-module-artifact-1``)."""

    kind: Literal["research_analysis_module"]
    contract_version: Literal["aia-analysis-module-artifact-1"]
    module_id: AnalysisModuleId
    ordinal: int
    artifact_name: str
    outcome: Outcome
    surface: ClaimSurface
    method_status: str = Field(min_length=1)
    #: The domain's module fingerprint (``module_input_fingerprint``).
    input_fingerprint: Sha256
    #: The artifact's reuse key: the module fingerprint, the sources and the harness.
    reuse_fingerprint: Sha256
    research_questions: tuple[str, ...]
    #: The draft the evidence gate accepted. Never a claim: claims are re-admitted.
    draft: AnalysisDraft | None
    violations: tuple[ViolationRecord, ...]
    #: Model turns taken; 0 when the preflight blocked before any.
    attempts: int = Field(ge=0)
    sources: ModuleSources
    evidence: EvidenceSummary
    authority: AuthoritySummary
    harness: HarnessSummary
    calls: tuple[CallRecord, ...]
    labels: ModuleLabels
    produced_by: ProducedBy
    runtime_version: str | None

    @model_validator(mode="after")
    def _consistent(self) -> ModuleArtifact:
        spec = module_spec(self.module_id)
        if (self.ordinal, self.artifact_name) != (spec.ordinal, spec.artifact_name):
            raise ValueError(f"{self.module_id} is module {spec.ordinal} ({spec.artifact_name})")
        if self.outcome == "COMPLETED":
            if self.draft is None or self.violations:
                raise ValueError("a completed module has its accepted draft and no violation")
            if self.draft.module != self.module_id.value:
                raise ValueError("the draft is for another module")
        elif self.draft is not None or not self.violations:
            raise ValueError("a blocked module has no draft and says why")
        if [c.turn for c in self.calls] != list(range(1, self.attempts + 1)):
            raise ValueError("every model turn has exactly one call record, in order")
        if self.attempts > self.harness.max_calls:
            raise ValueError("more turns than the harness allows")
        if self.labels.surface is not self.surface or self.evidence.data_origin is not (
            self.labels.data_origin
        ):
            raise ValueError("the labels disagree with the outcome")
        return self


class TurnArtifact(_Closed):
    """One model turn's answer, checkpointed the moment the call returned."""

    kind: Literal["research_analysis_turn"]
    contract_version: Literal["aia-analysis-turn-1"]
    module_id: AnalysisModuleId
    turn: int = Field(ge=1)
    reuse_fingerprint: Sha256
    request_sha256: Sha256
    answer: Literal["DRAFT", "SCHEMA_INVALID"]
    #: The answer as the output contract validated it (``DRAFT``); none otherwise.
    draft: AnalysisDraft | None
    schema_violations: tuple[str, ...]
    call_id: str | None
    provider_request_id: str | None
    model: str | None
    route_id: str | None
    policy_version: str | None
    cost_usd: float = Field(ge=0, allow_inf_nan=False)
    cost_basis: str | None
    produced_by: ProducedBy
    runtime_version: str | None

    @model_validator(mode="after")
    def _consistent(self) -> TurnArtifact:
        if (self.answer == "DRAFT") != (self.draft is not None):
            raise ValueError("a DRAFT turn carries its draft and a SCHEMA_INVALID one does not")
        if self.answer == "SCHEMA_INVALID" and not self.schema_violations:
            raise ValueError("a schema failure says what failed")
        return self


def parse_module_artifact(payload: Any) -> ModuleArtifact:
    """Parse a stored module artifact: strict JSON semantics, closed, this contract only."""
    return ModuleArtifact.model_validate_json(canonical_json(payload), strict=True)


def parse_turn_artifact(payload: Any) -> TurnArtifact:
    """Parse a stored turn checkpoint: strict JSON semantics, closed, this contract only."""
    return TurnArtifact.model_validate_json(canonical_json(payload), strict=True)


def module_reuse_fingerprint(
    *, module_fingerprint: str, sources: ModuleSources, harness: HarnessSummary
) -> str:
    """The reuse key of a module outcome: everything its validity depends on.

    The domain's module fingerprint covers the evidence, the research questions, the
    policy book, the certificate, the prompt, the surface, the language, the method
    status and the system; this adds the run's source artifacts by content and the
    harness that asked. The model and the route are deliberately absent: they are
    provenance, not validity (``modules.module_input_fingerprint``).
    """
    return fingerprint(
        {
            "contract": ANALYSIS_ARTIFACT_CONTRACT,
            "module": module_fingerprint,
            "sources": {
                "specification": sources.specification.sha256,
                "specification_fingerprint": sources.specification_fingerprint,
                "dataset": sources.dataset.sha256,
                "aggregate": sources.aggregate.sha256,
            },
            "harness": harness.model_dump(mode="json"),
        }
    )


def turn_fingerprint(*, reuse_fingerprint: str, turn: int, request_sha256: str) -> str:
    """The checkpoint key of one turn: which module, which turn, exactly what was sent."""
    return fingerprint(
        {
            "contract": TURN_ARTIFACT_CONTRACT,
            "module": reuse_fingerprint,
            "turn": turn,
            "request": request_sha256,
        }
    )
