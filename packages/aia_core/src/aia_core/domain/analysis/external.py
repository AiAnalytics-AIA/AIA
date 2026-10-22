"""External context a module is shown beside its evidence (evidence-integrity 7).

A sealed Deep Research bundle's accepted findings, as
:func:`~aia_core.domain.deep_research.quarantine.analysis_context` labels them: external context
for interpreting the run's own numbers, never a panel result. The lines go into the module's
payload under ``external_context_not_evidence`` and its input fingerprint; the evidence gate still
admits numbers from the run's aggregate alone, so a figure quoted from a source and written into
a draft is refused like any uncited number.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from typing import Final

from ..deep_research.bundle import EvidenceBundle
from ..deep_research.quarantine import AnalysisContext, analysis_context
from ..residency import DataClass

__all__ = ["MAX_CLAIM_CHARS", "MAX_EXTERNAL_ITEMS", "external_context_lines", "public_context"]

#: The most findings a module is shown: what the payload, and every repair turn, carries.
MAX_EXTERNAL_ITEMS: Final = 24
#: A finding's claim beyond this is cut, with an ellipsis; its source still names where it is.
MAX_CLAIM_CHARS: Final = 400


def public_context(bundle: EvidenceBundle) -> AnalysisContext:
    """The bundle's analysis context, its public (Class C) findings only.

    A module's request is classed from its dataset and design, never from this context, so a
    finding drawn from a client's own knowledge (Class A or B) is left out rather than sent
    under a class that would not admit it."""
    public = {
        a.evidence.evidence_id
        for a in bundle.accepted
        if a.evidence.data_class is DataClass.CLASS_C_INTERNAL
    }
    context = analysis_context(bundle)
    return context.model_copy(
        update={"items": tuple(i for i in context.items if i.evidence_id in public)}
    )


def external_context_lines(context: AnalysisContext) -> tuple[str, ...]:
    """The bundle's first :data:`MAX_EXTERNAL_ITEMS` findings in its own order, one line each:
    ``[evidence id] claim (source)``. Deterministic: the fingerprint moves only with the bundle."""
    lines = []
    for item in context.items[:MAX_EXTERNAL_ITEMS]:
        claim = " ".join(item.claim.split())
        if len(claim) > MAX_CLAIM_CHARS:
            claim = claim[: MAX_CLAIM_CHARS - 1].rstrip() + "…"
        lines.append(f"[{item.evidence_id}] {claim} ({item.source})")
    return tuple(lines)
