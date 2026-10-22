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

from dataclasses import dataclass
from typing import Final

from ..deep_research.bundle import EvidenceBundle
from ..deep_research.quarantine import AnalysisContext, analysis_context
from ..residency import DataClass

__all__ = [
    "MAX_CLAIM_CHARS",
    "MAX_EXTERNAL_ITEMS",
    "ShownContext",
    "ShownFinding",
    "external_context_lines",
    "public_context",
    "shown_context",
]

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


@dataclass(frozen=True, slots=True)
class ShownFinding:
    """One finding as a module is shown it: its claim with whitespace collapsed and cut."""

    evidence_id: str
    claim: str
    source: str

    def line(self) -> str:
        return f"[{self.evidence_id}] {self.claim} ({self.source})"


@dataclass(frozen=True, slots=True)
class ShownContext:
    """The findings every module of a run is shown, and the Deep Research run they come from.
    Analýza lists these very findings, so a person reads exactly what the modules read."""

    deep_research_run_id: str
    findings: tuple[ShownFinding, ...]

    def lines(self) -> tuple[str, ...]:
        return tuple(f.line() for f in self.findings)


def _shown(claim: str) -> str:
    claim = " ".join(claim.split())
    return claim if len(claim) <= MAX_CLAIM_CHARS else claim[: MAX_CLAIM_CHARS - 1].rstrip() + "…"


def shown_context(deep_research_run_id: str, context: AnalysisContext) -> ShownContext:
    """The bundle's first :data:`MAX_EXTERNAL_ITEMS` findings in its own order, as shown.
    Deterministic: the modules' fingerprint moves only with the bundle."""
    return ShownContext(
        deep_research_run_id=deep_research_run_id,
        findings=tuple(
            ShownFinding(evidence_id=i.evidence_id, claim=_shown(i.claim), source=i.source)
            for i in context.items[:MAX_EXTERNAL_ITEMS]
        ),
    )


def external_context_lines(context: AnalysisContext) -> tuple[str, ...]:
    """The shown findings (:func:`shown_context`) as lines: ``[evidence id] claim (source)``."""
    return shown_context("", context).lines()
