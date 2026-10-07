"""Deep Research purpose, target and frozen lineage (ADR 0021): the envelope around the engine.

What is pinned here, in the domain:

* **compatibility** -- a request and a sealed bundle captured on develop before ADR 0021
  (``fixtures/deep_research_pre_step1``, pinned by SHA256) still have the same
  fingerprint and still verify against their seal; the harness they name stays readable
  after the harness moved for per-kind request limits (chunk 23, harness 2);
* **orchestration identity** -- purpose, target and every material part of the lineage
  change the run-spec fingerprint, the title does not, and the engine request's own
  fingerprint is never touched by any of them;
* **the purpose rule** -- every invalid purpose / target / lineage combination fails to
  construct;
* **authority** -- neither purpose may write a design or any deterministic research
  artifact, and the engine's artifact types are disjoint from them.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain.analysis.modules import AnalysisModuleId
from aia_core.domain.deep_research.bundle import EvidenceBundle
from aia_core.domain.deep_research.contracts import (
    HARNESS_VERSION,
    HARNESS_VERSIONS,
    DeepResearchRequest,
)
from aia_core.domain.deep_research.integration import (
    DETERMINISTIC_ARTIFACT_TYPES,
    RUN_SPEC_CONTRACT,
    AnalysisModuleTarget,
    ArtifactPin,
    DeepResearchPurpose,
    DeepResearchRunSpec,
    DesignLineage,
    DesignRevisionTarget,
    InterpretationLineage,
    MethodologyBoundaryViolation,
    ResultQuestionTarget,
    SociomapObjectTarget,
    SociomapRelationshipTarget,
    authority_of,
    require_engine_writes_are_sidecars,
    require_may_write,
)
from aia_core.domain.deep_research.workflow import ARTIFACT_TYPES

FIXTURES = Path(__file__).parent / "fixtures" / "deep_research_pre_step1"
INDEX = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))
SHA_A, SHA_B, SHA_C, SHA_D = ("a" * 64, "b" * 64, "c" * 64, "d" * 64)
RUN = "RUN-00000000000000a1"


def _fixture(name: str) -> Any:
    raw = (FIXTURES / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == INDEX["files"][name], f"{name} was edited"
    return json.loads(raw)


@pytest.fixture
def request_() -> DeepResearchRequest:
    return DeepResearchRequest.model_validate(_fixture("request.json"))


def _design(request: DeepResearchRequest, **over: Any) -> DeepResearchRunSpec:
    fields: dict[str, Any] = {
        "contract_version": RUN_SPEC_CONTRACT,
        "purpose": DeepResearchPurpose.DESIGN_RESEARCH,
        "target": DesignRevisionTarget(
            kind="DESIGN_REVISION", design_revision_id=request.design_revision_id
        ),
        "lineage": DesignLineage(
            kind="DESIGN",
            design_revision_id=request.design_revision_id,
            design_revision=request.design_revision,
            design_content_sha256=SHA_A,
        ),
        "engine_request": request,
    }
    return DeepResearchRunSpec(**{**fields, **over})


def _pins(*, aggregate: str = SHA_C, sociomap: str = SHA_D) -> tuple[ArtifactPin, ...]:
    return (
        ArtifactPin(
            node_key="aggregate",
            artifact_id="ART-00000000000000a3",
            artifact_type="research_aggregate",
            sha256=aggregate,
        ),
        ArtifactPin(
            node_key="compile",
            artifact_id="ART-00000000000000a1",
            artifact_type="research_specification",
            sha256=SHA_A,
        ),
        ArtifactPin(
            node_key="run",
            artifact_id="ART-00000000000000a2",
            artifact_type="research_fieldwork_dataset",
            sha256=SHA_B,
        ),
        ArtifactPin(
            node_key="sociomap",
            artifact_id="ART-00000000000000a4",
            artifact_type="research_sociomap",
            sha256=sociomap,
        ),
    )


def _interpretation(request: DeepResearchRequest, **over: Any) -> DeepResearchRunSpec:
    fields: dict[str, Any] = {
        "contract_version": RUN_SPEC_CONTRACT,
        "purpose": DeepResearchPurpose.INTERPRETATION_RESEARCH,
        "target": SociomapObjectTarget(
            kind="SOCIOMAP_OBJECT",
            research_run_id=RUN,
            sociomap_artifact_id="ART-00000000000000a4",
            battery_id="napoje",
            object_id="kava",
        ),
        "lineage": InterpretationLineage(
            kind="INTERPRETATION",
            research_run_id=RUN,
            design=DesignLineage(
                kind="DESIGN",
                design_revision_id=request.design_revision_id,
                design_revision=request.design_revision,
                design_content_sha256=SHA_A,
            ),
            artifacts=_pins(),
        ),
        "engine_request": request,
    }
    return DeepResearchRunSpec(**{**fields, **over})


# --------------------------------------------------------------------------- compatibility


def test_a_request_frozen_before_adr_0021_keeps_its_fingerprint(
    request_: DeepResearchRequest,
) -> None:
    """The engine request is not reshaped by the envelope: same bytes, same identity."""
    assert request_.fingerprint() == INDEX["request_fingerprint"]
    assert request_.model_dump(mode="json") == _fixture("request.json")
    # Frozen under harness 1, still readable after the method moved to harness 2.
    assert request_.harness_version == "aia-deep-research-harness-1" != HARNESS_VERSION
    assert request_.harness_version in HARNESS_VERSIONS
    # And wrapping it changes neither.
    spec = _design(request_)
    assert spec.engine_request_fingerprint() == INDEX["request_fingerprint"]
    assert spec.engine_request.model_dump(mode="json") == _fixture("request.json")


def test_a_bundle_sealed_before_adr_0021_still_verifies_and_names_its_request() -> None:
    bundle = EvidenceBundle.model_validate(_fixture("bundle.json"))
    assert bundle.verify()
    assert bundle.sha256 == INDEX["bundle_seal"]
    assert bundle.request_fingerprint == INDEX["request_fingerprint"]
    assert bundle.model_dump(mode="json") == _fixture("bundle.json")
    tampered = bundle.model_copy(update={"preset": "DEEP"})
    assert not tampered.verify()


def test_the_pre_adr_0021_run_metadata_names_the_same_request() -> None:
    metadata = _fixture("run_metadata.json")
    assert metadata["request_fingerprint"] == INDEX["request_fingerprint"]
    assert "integration_contract" not in metadata and "purpose" not in metadata


# --------------------------------------------------------------------------- identity


def test_purpose_changes_the_run_identity_but_never_the_engine_identity(
    request_: DeepResearchRequest,
) -> None:
    design, interpretation = _design(request_), _interpretation(request_)
    assert design.fingerprint() != interpretation.fingerprint()
    assert design.engine_request_fingerprint() == interpretation.engine_request_fingerprint()
    assert design.engine_request_fingerprint() == INDEX["request_fingerprint"]


def test_the_target_changes_the_run_identity(request_: DeepResearchRequest) -> None:
    base = _interpretation(request_)
    other_object = _interpretation(
        request_,
        target=SociomapObjectTarget(
            kind="SOCIOMAP_OBJECT",
            research_run_id=RUN,
            sociomap_artifact_id="ART-00000000000000a4",
            battery_id="napoje",
            object_id="caj",
        ),
    )
    pair = _interpretation(
        request_,
        target=SociomapRelationshipTarget(
            kind="SOCIOMAP_RELATIONSHIP",
            research_run_id=RUN,
            sociomap_artifact_id="ART-00000000000000a4",
            battery_id="napoje",
            source_object_id="kava",
            target_object_id="caj",
        ),
    )
    assert len({base.fingerprint(), other_object.fingerprint(), pair.fingerprint()}) == 3


def test_every_material_part_of_the_lineage_changes_the_run_identity(
    request_: DeepResearchRequest,
) -> None:
    base = _interpretation(request_)

    def with_lineage(**over: Any) -> DeepResearchRunSpec:
        lineage = base.lineage
        assert isinstance(lineage, InterpretationLineage)
        return _interpretation(request_, lineage=lineage.model_copy(update=over))

    changed = [
        with_lineage(artifacts=_pins(aggregate=SHA_A)),  # another aggregate's bytes
        with_lineage(artifacts=_pins(sociomap=SHA_B)),  # another map's bytes
        with_lineage(
            design=DesignLineage(
                kind="DESIGN",
                design_revision_id=request_.design_revision_id,
                design_revision=request_.design_revision,
                design_content_sha256=SHA_D,  # another revision content
            )
        ),
    ]
    fingerprints = {base.fingerprint(), *(c.fingerprint() for c in changed)}
    assert len(fingerprints) == 4
    design = _design(request_)
    other = _design(
        request_,
        lineage=DesignLineage(
            kind="DESIGN",
            design_revision_id=request_.design_revision_id,
            design_revision=request_.design_revision,
            design_content_sha256=SHA_B,
        ),
    )
    assert design.fingerprint() != other.fingerprint()


def test_the_title_is_presentation_and_not_identity(request_: DeepResearchRequest) -> None:
    plain = _design(request_)
    titled = _design(request_, title="Trh rostlinných nápojů — kontext")
    assert plain.fingerprint() == titled.fingerprint()
    assert "title" not in titled.identity()


def test_a_relationship_is_one_identity_whichever_way_it_is_named() -> None:
    forward = SociomapRelationshipTarget(
        kind="SOCIOMAP_RELATIONSHIP",
        research_run_id=RUN,
        sociomap_artifact_id="ART-00000000000000a4",
        battery_id="napoje",
        source_object_id="kava",
        target_object_id="caj",
    )
    backward = forward.model_validate(
        {**forward.model_dump(), "source_object_id": "kava", "target_object_id": "caj"}
    )
    swapped = SociomapRelationshipTarget.model_validate(
        {**forward.model_dump(), "source_object_id": "caj", "target_object_id": "kava"}
    )
    assert forward == backward == swapped
    assert (forward.source_object_id, forward.target_object_id) == ("caj", "kava")
    with pytest.raises(ValidationError, match="two different objects"):
        SociomapRelationshipTarget.model_validate(
            {**forward.model_dump(), "source_object_id": "kava", "target_object_id": "kava"}
        )


def test_a_target_is_a_closed_typed_reference_never_free_form() -> None:
    with pytest.raises(ValidationError):
        ResultQuestionTarget.model_validate(
            {
                "kind": "RESULT_QUESTION",
                "research_run_id": RUN,
                "aggregate_artifact_id": "ART-00000000000000a3",
                "question_id": "q1",
                "note": "anything else",
            }
        )
    with pytest.raises(ValidationError):  # not an artifact id
        ResultQuestionTarget(
            kind="RESULT_QUESTION",
            research_run_id=RUN,
            aggregate_artifact_id="latest",
            question_id="q1",
        )


# --------------------------------------------------------------------------- the purpose rule


def test_invalid_purpose_target_and_lineage_combinations_do_not_construct(
    request_: DeepResearchRequest,
) -> None:
    interpretation = _interpretation(request_)
    design = _design(request_)
    with pytest.raises(ValidationError, match="Design Research targets a Design Revision"):
        _design(request_, target=interpretation.target)
    with pytest.raises(ValidationError, match="anchored to a design"):
        _design(request_, lineage=interpretation.lineage)
    with pytest.raises(ValidationError, match="targets a result"):
        _interpretation(request_, target=design.target)
    with pytest.raises(ValidationError, match="anchored to results"):
        _interpretation(request_, lineage=design.lineage)
    with pytest.raises(ValidationError, match="not of the lineage's research run"):
        _interpretation(
            request_,
            target=SociomapObjectTarget(
                kind="SOCIOMAP_OBJECT",
                research_run_id="RUN-00000000000000b2",
                sociomap_artifact_id="ART-00000000000000a4",
                battery_id="napoje",
                object_id="kava",
            ),
        )
    with pytest.raises(ValidationError, match="does not pin the target's artifact"):
        _interpretation(
            request_,
            target=AnalysisModuleTarget(
                kind="ANALYSIS_MODULE",
                research_run_id=RUN,
                analysis_artifact_id="ART-00000000000000a9",
                module_id=AnalysisModuleId.SEGMENTS,
            ),
        )
    with pytest.raises(ValidationError, match="not the lineage's Design Revision"):
        _design(
            request_,
            target=DesignRevisionTarget(
                kind="DESIGN_REVISION", design_revision_id="REV-00000000000000ff"
            ),
        )
    other_revision = request_.model_copy(update={"design_revision": request_.design_revision + 1})
    with pytest.raises(ValidationError, match="not frozen from the lineage's Design Revision"):
        _design(request_, engine_request=other_revision)


def test_lineage_pins_one_artifact_per_node_in_order() -> None:
    pins = _pins()
    with pytest.raises(ValidationError, match="one pin per node"):
        InterpretationLineage(
            kind="INTERPRETATION",
            research_run_id=RUN,
            design=DesignLineage(
                kind="DESIGN",
                design_revision_id="REV-00000000000000a1",
                design_revision=1,
                design_content_sha256=SHA_A,
            ),
            artifacts=(pins[1], pins[0], *pins[2:]),
        )


# --------------------------------------------------------------------------- authority


@pytest.mark.parametrize("purpose", list(DeepResearchPurpose))
def test_no_purpose_may_write_a_design_or_deterministic_research(
    purpose: DeepResearchPurpose,
) -> None:
    """Design Research proposes, and a person writes the revision; Interpretation
    Research reads results and writes none: respondent data, aggregates, analysis and
    Sociomaps are refused to both."""
    for artifact_type in sorted(DETERMINISTIC_ARTIFACT_TYPES | {"design_revision"}):
        with pytest.raises(MethodologyBoundaryViolation, match="never rewrites"):
            require_may_write(purpose, artifact_type)
    with pytest.raises(MethodologyBoundaryViolation, match="may write no"):
        require_may_write(purpose, "client_knowledge_revision")
    for artifact_type in ARTIFACT_TYPES.values():  # its own evidence, beside the research
        require_may_write(purpose, artifact_type)


def test_only_design_research_may_propose_and_only_a_design_revision() -> None:
    design = authority_of(DeepResearchPurpose.DESIGN_RESEARCH)
    interpretation = authority_of(DeepResearchPurpose.INTERPRETATION_RESEARCH)
    assert design.may_propose == frozenset({"design_revision"})
    assert interpretation.may_propose == frozenset()
    assert not (design.may_write | interpretation.may_write) & DETERMINISTIC_ARTIFACT_TYPES


def test_the_engine_cannot_be_made_to_write_research_truth() -> None:
    require_engine_writes_are_sidecars(ARTIFACT_TYPES.values())
    assert all(t.startswith("deep_research_") for t in ARTIFACT_TYPES.values())
    with pytest.raises(MethodologyBoundaryViolation, match="research_sociomap"):
        require_engine_writes_are_sidecars([*ARTIFACT_TYPES.values(), "research_sociomap"])


def test_interpretation_may_read_a_sociomap_but_never_write_it(
    request_: DeepResearchRequest,
) -> None:
    """The direction of the Sociomap invariant (ADR 0021 decision 6): Interpretation Research
    may read the frozen canonical Sociomap; Deep Research and external evidence are never
    inputs to the canonical Sociomap calculation."""
    spec = _interpretation(request_)  # a Sociomap object, pinned by id and SHA256: a read
    assert isinstance(spec.target, SociomapObjectTarget)
    pin = spec.lineage.pin("sociomap") if isinstance(spec.lineage, InterpretationLineage) else None
    assert pin is not None and pin.artifact_type == "research_sociomap"
    for artifact_type in ("research_sociomap", "research_sociomapping"):
        with pytest.raises(MethodologyBoundaryViolation, match="never rewrites"):
            require_may_write(DeepResearchPurpose.INTERPRETATION_RESEARCH, artifact_type)
