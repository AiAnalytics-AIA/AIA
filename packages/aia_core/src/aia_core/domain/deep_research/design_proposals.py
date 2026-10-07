"""What a Design Research run proposes, and what a person's accept adds to a design (ADR 0021).

A ``DESIGN_RESEARCH`` run is advisory (ADR 0021 decision 1): it may *propose*; only a person
turns a proposal into a new Design Revision (ADR 0019 gate 1). The engine is frozen
(decision 7), so the proposal is built here **by code** from the sealed bundle the run
already published -- no step, no model call, nothing in the bundle changed::

    EvidenceBundle (sealed)  ──design_input──►  DesignResearchProposal
                                                 ├── EVIDENCE item per subject with findings
                                                 └── GAP item per subject with none

    baseline design + accepted item ids  ──apply_to_design──►  the new revision's content
                                                 (one AIA-owned key, ``design_research``;
                                                  every other key unchanged)

Deep Research never writes the research plan, the questionnaire, the audience, the
dimensions or the sample plan: the accepted evidence sits beside them as
``EXTERNAL_CONTEXT``, cited, for a person and the design jobs to act on. It is not
respondent context, which :func:`~.quarantine.respondent_context` builds on its own against
the final questionnaire.

Recorded fixtures never enter a real client's design: a proposal whose bundle rests on
them is admissible only when the bundle's client is fictional.

This module names no writer of a design (``layer_check``); the application layer
(``application/design_research.py``) writes the revision.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from copy import deepcopy
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from .bundle import EvidenceBundle
from .contracts import EvidenceOrigin, digest
from .integration import (
    DeepResearchProvenance,
    DeepResearchPurpose,
    DesignLineage,
)
from .quarantine import EXTERNAL_CONTEXT, DesignFinding, design_input

__all__ = [
    "DESIGN_PROPOSAL_CONTRACT",
    "DESIGN_RESEARCH_KEY",
    "DESIGN_RESEARCH_MAX_BYTES",
    "DesignProposalRefused",
    "DesignResearchProposal",
    "ItemKind",
    "ProposalItem",
    "apply_to_design",
    "design_research_proposal",
    "selection_id",
]

#: The proposal's and the stored block's contract. A change to either shape is a new value.
DESIGN_PROPOSAL_CONTRACT: Final = "aia-design-research-proposal-1"
#: The one design key an accept writes. AIA's own: not the unit's ``research_context``,
#: which is a respondent-context toggle.
DESIGN_RESEARCH_KEY: Final = "design_research"
#: The most the block may hold, serialised. The design jobs read the whole design inside a
#: 64 KB context (``research_agents.CONTEXT_MAX_BYTES``); accepted evidence must leave room.
DESIGN_RESEARCH_MAX_BYTES: Final = 32 * 1024

_SHA = r"^[0-9a-f]{64}$"


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DesignProposalRefused(ValueError):
    """A proposal that cannot be made, or an accept that cannot be applied, and why."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class ItemKind(StrEnum):
    #: A subject with accepted findings: the findings, verbatim, as evidence.
    EVIDENCE = "EVIDENCE"
    #: A subject the run found nothing for: worth knowing before the design is frozen.
    GAP = "GAP"


class ProposalItem(_Closed):
    """One subject of the run, and what the run found for it."""

    item_id: str = Field(pattern=r"^DRP-[0-9a-f]{24}$")
    kind: ItemKind
    subject_key: str
    subject_kind: str
    subject_text: str
    #: Where in the design the subject came from ("research_plan.research_questions[0]").
    subject_origin: str
    findings: tuple[DesignFinding, ...]


class DesignResearchProposal(_Closed):
    """Everything a Design Research run proposes, anchored to the design it researched."""

    contract_version: Literal["aia-design-research-proposal-1"]
    run_id: str
    run_spec_fingerprint: str = Field(pattern=_SHA)
    evidence_bundle_artifact_id: str
    evidence_bundle_seal: str = Field(pattern=_SHA)
    #: The Design Revision the run was frozen on: the only baseline an accept may land on.
    design_revision_id: str
    design_revision: int = Field(ge=1)
    role: Literal["EXTERNAL_CONTEXT"]
    origins: tuple[EvidenceOrigin, ...]
    fictional_client: bool
    #: Whether a person may accept it into this Study's design, and if not, why.
    admissible: bool
    refusal: str | None
    items: tuple[ProposalItem, ...]

    def item(self, item_id: str) -> ProposalItem | None:
        return next((i for i in self.items if i.item_id == item_id), None)


def _item_id(seal: str, subject_key: str) -> str:
    return "DRP-" + digest([DESIGN_PROPOSAL_CONTRACT, seal, subject_key])[:24]


def design_research_proposal(
    provenance: DeepResearchProvenance, bundle: EvidenceBundle
) -> DesignResearchProposal:
    """The proposal a governed Design Research run makes from its own sealed bundle.

    Refuses anything but ``DESIGN_RESEARCH`` anchored to a design, and a bundle that is
    not the one the provenance names or no longer hashes to its seal.
    """
    if provenance.purpose is not DeepResearchPurpose.DESIGN_RESEARCH:
        raise DesignProposalRefused(
            "only Design Research proposes a design change", reason="not_design_research"
        )
    lineage = provenance.lineage
    if not isinstance(lineage, DesignLineage):  # pragma: no cover - the run spec forbids it
        raise DesignProposalRefused("not anchored to a design", reason="not_design_research")
    if not bundle.verify() or bundle.sha256 != provenance.evidence_bundle_seal:
        raise DesignProposalRefused(
            "the bundle is not the one this run sealed", reason="bundle_mismatch"
        )
    if (bundle.design_revision_id, bundle.design_revision) != (
        lineage.design_revision_id,
        lineage.design_revision,
    ):
        raise DesignProposalRefused(
            "the bundle researched another Design Revision", reason="bundle_mismatch"
        )
    view = design_input(bundle)
    items = []
    for subject in bundle.subjects:
        findings = view.findings.get(subject.key, ())
        items.append(
            ProposalItem(
                item_id=_item_id(bundle.sha256, subject.key),
                kind=ItemKind.EVIDENCE if findings else ItemKind.GAP,
                subject_key=subject.key,
                subject_kind=subject.kind.value,
                subject_text=subject.text,
                subject_origin=subject.origin,
                findings=findings,
            )
        )
    recorded = EvidenceOrigin.RECORDED_FIXTURE in bundle.origins
    refusal = (
        "this run rests on recorded fixtures; only a fictional client's design may take them"
        if recorded and not bundle.fictional_client
        else None
    )
    return DesignResearchProposal(
        contract_version=DESIGN_PROPOSAL_CONTRACT,
        run_id=provenance.run_id,
        run_spec_fingerprint=provenance.run_spec_fingerprint,
        evidence_bundle_artifact_id=provenance.evidence_bundle_artifact_id,
        evidence_bundle_seal=bundle.sha256,
        design_revision_id=lineage.design_revision_id,
        design_revision=lineage.design_revision,
        role=EXTERNAL_CONTEXT,
        origins=bundle.origins,
        fictional_client=bundle.fictional_client,
        admissible=refusal is None,
        refusal=refusal,
        items=tuple(items),
    )


def selection_id(run_id: str, item_ids: Iterable[str]) -> str:
    """One accept's identity: the run and the set of items taken, in any order."""
    return "DRS-" + digest([DESIGN_PROPOSAL_CONTRACT, run_id, sorted(set(item_ids))])[:40]


def _entry(proposal: DesignResearchProposal, item: ProposalItem) -> dict[str, Any]:
    return {
        "item_id": item.item_id,
        "kind": item.kind.value,
        "role": EXTERNAL_CONTEXT,
        "subject": {
            "key": item.subject_key,
            "kind": item.subject_kind,
            "text": item.subject_text,
            "origin": item.subject_origin,
        },
        "findings": [f.model_dump(mode="json") for f in item.findings],
        "provenance": {
            "run_id": proposal.run_id,
            "run_spec_fingerprint": proposal.run_spec_fingerprint,
            "evidence_bundle_artifact_id": proposal.evidence_bundle_artifact_id,
            "evidence_bundle_seal": proposal.evidence_bundle_seal,
            "design_revision_id": proposal.design_revision_id,
            "origins": [o.value for o in proposal.origins],
            "fictional_client": proposal.fictional_client,
        },
    }


def apply_to_design(
    content: Mapping[str, Any], proposal: DesignResearchProposal, item_ids: Iterable[str]
) -> dict[str, Any]:
    """The baseline design with the accepted items added under :data:`DESIGN_RESEARCH_KEY`.

    Every other key is returned unchanged. Items already in the block stay; an item
    accepted again is the same entry, so an unchanged accept is an unchanged design.
    Refuses an inadmissible proposal, an empty selection, an id the proposal does not
    hold, a block that is not this contract's, and a block over the size bound.
    """
    if not proposal.admissible:
        raise DesignProposalRefused(proposal.refusal or "not admissible", reason="inadmissible")
    chosen = sorted(set(item_ids))
    if not chosen:
        raise DesignProposalRefused("no item was accepted", reason="empty_selection")
    unknown = [i for i in chosen if proposal.item(i) is None]
    if unknown:
        raise DesignProposalRefused(
            f"not items of this proposal: {', '.join(unknown)}", reason="unknown_item"
        )
    design = deepcopy(dict(content))
    block = design.get(DESIGN_RESEARCH_KEY)
    if block is None:
        entries: dict[str, Any] = {}
    elif (
        isinstance(block, dict)
        and block.get("contract_version") == DESIGN_PROPOSAL_CONTRACT
        and isinstance(block.get("items"), dict)
    ):
        entries = dict(block["items"])
    else:
        raise DesignProposalRefused(
            f"the design's {DESIGN_RESEARCH_KEY} is not this contract's", reason="block_invalid"
        )
    for item_id in chosen:
        item = proposal.item(item_id)
        assert item is not None
        entries[item_id] = _entry(proposal, item)
    new_block = {
        "contract_version": DESIGN_PROPOSAL_CONTRACT,
        "items": dict(sorted(entries.items())),
    }
    size = len(json.dumps(new_block, sort_keys=True, ensure_ascii=False).encode())
    if size > DESIGN_RESEARCH_MAX_BYTES:
        raise DesignProposalRefused(
            f"the accepted evidence would be {size} bytes; the limit is "
            f"{DESIGN_RESEARCH_MAX_BYTES}. Accept fewer items.",
            reason="block_too_large",
        )
    design[DESIGN_RESEARCH_KEY] = new_block
    return design
