"""A Design Research run's proposal, and what a person's accept adds to a design (chunk 29)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from test_deep_research_bundle_and_quarantine import (
    OBJECT,
    QUESTION,
    WEB_O,
    _accepted,
    _bundle,
)

from aia_core.domain.deep_research.bundle import EvidenceBundle
from aia_core.domain.deep_research.design_proposals import (
    DESIGN_PROPOSAL_CONTRACT,
    DESIGN_RESEARCH_KEY,
    DESIGN_RESEARCH_MAX_BYTES,
    DesignProposalRefused,
    DesignResearchProposal,
    ItemKind,
    apply_to_design,
    design_research_proposal,
    selection_id,
)
from aia_core.domain.deep_research.integration import (
    RUN_SPEC_CONTRACT,
    DeepResearchProvenance,
    DeepResearchPurpose,
    DesignLineage,
    DesignRevisionTarget,
    InterpretationLineage,
    ResultQuestionTarget,
)
from aia_core.domain.deep_research.integration import (
    ArtifactPin as Pin,
)

FINDING = "Regulace obalů se mění od roku 2026."
DESIGN: dict[str, Any] = {
    "title": "Rostlinné nápoje",
    "goal": "Pochopit trh",
    "research_plan": {"research_questions": ["Proč lidé kupují rostlinné nápoje?"]},
    "sections": [{"id": "s1", "type": "questions", "questions": [{"id": "q1", "text": "?"}]}],
    "audience": {"description": "ČR 18+"},
}


def _provenance(bundle: EvidenceBundle, **fields: Any) -> DeepResearchProvenance:
    values: dict[str, Any] = {
        "contract_version": RUN_SPEC_CONTRACT,
        "run_id": "RUN-1",
        "purpose": DeepResearchPurpose.DESIGN_RESEARCH,
        "target": DesignRevisionTarget(kind="DESIGN_REVISION", design_revision_id="REV-1"),
        "lineage": DesignLineage(
            kind="DESIGN",
            design_revision_id="REV-1",
            design_revision=1,
            design_content_sha256="c" * 64,
        ),
        "run_spec_fingerprint": "f" * 64,
        "engine_request_fingerprint": bundle.request_fingerprint,
        "evidence_bundle_artifact_id": "ART-00000000000000aa",
        "evidence_bundle_artifact_sha256": "e" * 64,
        "evidence_bundle_seal": bundle.sha256,
        **fields,
    }
    return DeepResearchProvenance.model_validate(values)


def _proposal(*, fictional: bool = True) -> DesignResearchProposal:
    bundle = _bundle(_accepted(1, FINDING), fictional=fictional)
    return design_research_proposal(_provenance(bundle), bundle)


def test_every_subject_is_an_item_with_its_findings_verbatim_or_a_gap() -> None:
    proposal = _proposal()
    assert proposal.contract_version == DESIGN_PROPOSAL_CONTRACT
    assert proposal.admissible and proposal.refusal is None
    assert (proposal.design_revision_id, proposal.design_revision) == ("REV-1", 1)
    assert proposal.role == "EXTERNAL_CONTEXT"
    by_subject = {i.subject_key: i for i in proposal.items}
    assert list(by_subject) == [QUESTION.key, OBJECT.key]
    evidence, gap = by_subject[QUESTION.key], by_subject[OBJECT.key]
    assert evidence.kind is ItemKind.EVIDENCE and gap.kind is ItemKind.GAP
    assert [(f.claim, f.quote) for f in evidence.findings] == [(FINDING, FINDING)]
    assert evidence.subject_origin == QUESTION.origin and gap.findings == ()


def test_the_same_run_always_proposes_the_same_item_ids() -> None:
    assert [i.item_id for i in _proposal().items] == [i.item_id for i in _proposal().items]
    other = _bundle(_accepted(2, "Jiný nález.", track=WEB_O), fictional=True)
    others = design_research_proposal(_provenance(other), other)
    assert not {i.item_id for i in others.items} & {i.item_id for i in _proposal().items}


def test_only_design_research_anchored_to_its_own_bundle_proposes() -> None:
    bundle = _bundle(_accepted(1, FINDING), fictional=True)
    interpretation = _provenance(
        bundle,
        purpose=DeepResearchPurpose.INTERPRETATION_RESEARCH,
        target=ResultQuestionTarget(
            kind="RESULT_QUESTION",
            research_run_id="RUN-2",
            aggregate_artifact_id="ART-00000000000000bb",
            question_id="q1",
        ),
        lineage=InterpretationLineage(
            kind="INTERPRETATION",
            research_run_id="RUN-2",
            design=DesignLineage(
                kind="DESIGN",
                design_revision_id="REV-1",
                design_revision=1,
                design_content_sha256="c" * 64,
            ),
            artifacts=(
                Pin(
                    node_key="aggregate",
                    artifact_id="ART-00000000000000bb",
                    artifact_type="research_aggregate",
                    sha256="d" * 64,
                ),
            ),
        ),
    )
    with pytest.raises(DesignProposalRefused) as refused:
        design_research_proposal(interpretation, bundle)
    assert refused.value.reason == "not_design_research"

    with pytest.raises(DesignProposalRefused) as refused:
        design_research_proposal(_provenance(bundle, evidence_bundle_seal="0" * 64), bundle)
    assert refused.value.reason == "bundle_mismatch"
    tampered = bundle.model_copy(update={"preset": "DEEP"})
    with pytest.raises(DesignProposalRefused) as refused:
        design_research_proposal(_provenance(bundle), tampered)
    assert refused.value.reason == "bundle_mismatch"
    other_revision = _provenance(
        bundle,
        lineage=DesignLineage(
            kind="DESIGN",
            design_revision_id="REV-2",
            design_revision=2,
            design_content_sha256="c" * 64,
        ),
        target=DesignRevisionTarget(kind="DESIGN_REVISION", design_revision_id="REV-2"),
    )
    with pytest.raises(DesignProposalRefused) as refused:
        design_research_proposal(other_revision, bundle)
    assert refused.value.reason == "bundle_mismatch"


def test_recorded_evidence_never_enters_a_real_clients_design() -> None:
    proposal = _proposal(fictional=False)
    assert not proposal.admissible and "recorded fixtures" in (proposal.refusal or "")
    with pytest.raises(DesignProposalRefused) as refused:
        apply_to_design(DESIGN, proposal, [proposal.items[0].item_id])
    assert refused.value.reason == "inadmissible"


def test_accepting_writes_only_the_chosen_items_and_leaves_every_other_key_unchanged() -> None:
    proposal = _proposal()
    evidence = proposal.items[0]
    design = apply_to_design(DESIGN, proposal, [evidence.item_id])
    assert {k: v for k, v in design.items() if k != DESIGN_RESEARCH_KEY} == DESIGN
    assert DESIGN_RESEARCH_KEY not in DESIGN  # the baseline is not mutated
    block = design[DESIGN_RESEARCH_KEY]
    assert block["contract_version"] == DESIGN_PROPOSAL_CONTRACT
    assert list(block["items"]) == [evidence.item_id]
    entry = block["items"][evidence.item_id]
    assert entry["role"] == "EXTERNAL_CONTEXT" and entry["kind"] == "EVIDENCE"
    assert entry["findings"][0]["quote"] == FINDING
    assert entry["provenance"]["run_id"] == "RUN-1"
    assert entry["provenance"]["evidence_bundle_seal"] == proposal.evidence_bundle_seal
    assert entry["provenance"]["origins"] == ["RECORDED_FIXTURE"]
    # The design stays plain JSON.
    assert json.loads(json.dumps(design)) == design


def test_accepting_again_changes_nothing_and_a_later_accept_adds_to_the_block() -> None:
    proposal = _proposal()
    first, second = (i.item_id for i in proposal.items)
    once = apply_to_design(DESIGN, proposal, [first])
    assert apply_to_design(once, proposal, [first]) == once
    both = apply_to_design(once, proposal, [second])
    assert list(both[DESIGN_RESEARCH_KEY]["items"]) == sorted([first, second])
    assert both[DESIGN_RESEARCH_KEY]["items"][second]["kind"] == "GAP"


def test_an_empty_or_unknown_selection_is_refused() -> None:
    proposal = _proposal()
    for ids, reason in (([], "empty_selection"), (["DRP-" + "0" * 24], "unknown_item")):
        with pytest.raises(DesignProposalRefused) as refused:
            apply_to_design(DESIGN, proposal, ids)
        assert refused.value.reason == reason


def test_a_block_that_is_not_this_contracts_is_never_overwritten() -> None:
    proposal = _proposal()
    for foreign in ({"notes": "a person's own"}, ["x"], {"contract_version": "other", "items": {}}):
        with pytest.raises(DesignProposalRefused) as refused:
            apply_to_design({**DESIGN, DESIGN_RESEARCH_KEY: foreign}, proposal, ["x"])
        assert refused.value.reason in {"block_invalid", "unknown_item"}
        with pytest.raises(DesignProposalRefused) as refused:
            apply_to_design(
                {**DESIGN, DESIGN_RESEARCH_KEY: foreign}, proposal, [proposal.items[0].item_id]
            )
        assert refused.value.reason == "block_invalid"


def test_the_block_is_bounded_so_the_design_jobs_context_has_room() -> None:
    # Quotes are at most 800 characters, so the bound is crossed by many findings, not one.
    found = [_accepted(n, f"Nález {n}: " + "x" * 780) for n in range(1, 45)]
    assert sum(len(a.evidence.quote) for a in found) > DESIGN_RESEARCH_MAX_BYTES
    bundle = _bundle(*found, fictional=True)
    proposal = design_research_proposal(_provenance(bundle), bundle)
    with pytest.raises(DesignProposalRefused) as refused:
        apply_to_design(DESIGN, proposal, [proposal.items[0].item_id])
    assert refused.value.reason == "block_too_large"


def test_a_selection_is_one_identity_whatever_its_order() -> None:
    assert selection_id("RUN-1", ["b", "a", "a"]) == selection_id("RUN-1", ["a", "b"])
    assert selection_id("RUN-1", ["a"]) != selection_id("RUN-1", ["a", "b"])
    assert selection_id("RUN-1", ["a"]) != selection_id("RUN-2", ["a"])
    assert len(selection_id("RUN-1", ["a"])) <= 64
