"""External context a module is shown (evidence-integrity 7): the lines, never evidence."""

from __future__ import annotations

from aia_core.domain.analysis.external import (
    MAX_CLAIM_CHARS,
    MAX_EXTERNAL_ITEMS,
    external_context_lines,
)
from aia_core.domain.deep_research.contracts import EvidenceOrigin
from aia_core.domain.deep_research.quarantine import AnalysisContext, AnalysisItem


def context(*claims: str) -> AnalysisContext:
    return AnalysisContext(
        bundle_sha256="a" * 64,
        origins=(EvidenceOrigin.RECORDED_FIXTURE,),
        items=tuple(
            AnalysisItem(
                evidence_id=f"EV-{i}",
                claim=claim,
                source=f"https://example.invalid/{i}",
                role="EXTERNAL_CONTEXT",
                admissible_as_panel_claim=False,
            )
            for i, claim in enumerate(claims)
        ),
    )


def test_each_finding_is_one_line_with_its_id_and_source_in_the_bundles_order() -> None:
    lines = external_context_lines(context("Ovesné nápoje\n  rostou.", "Káva vede."))
    assert lines == (
        "[EV-0] Ovesné nápoje rostou. (https://example.invalid/0)",
        "[EV-1] Káva vede. (https://example.invalid/1)",
    )
    assert external_context_lines(context()) == ()


def test_the_context_is_bounded_in_findings_and_in_each_claim() -> None:
    lines = external_context_lines(context(*["x " * 400] * (MAX_EXTERNAL_ITEMS + 5)))
    assert len(lines) == MAX_EXTERNAL_ITEMS
    claim = lines[0].removeprefix("[EV-0] ").removesuffix(" (https://example.invalid/0)")
    assert len(claim) <= MAX_CLAIM_CHARS and claim.endswith("…")
