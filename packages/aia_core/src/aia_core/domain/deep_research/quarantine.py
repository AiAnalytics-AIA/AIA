"""What leaves a bundle, for whom: respondents, the design, analysis. Quarantine first.

Three consumers, three contracts, one rule each (DR-4 outputs 1, 2 and 4):

* **Respondent context** (:func:`respondent_context`) -- the legacy
  ``bundle_to_kontext`` shape, built only from accepted evidence that is
  respondent-eligible **and** passes the leakage screen again, against the
  *final* questionnaire. A finding accepted when the design had no survey yet
  becomes leakage the moment a question asks what it reports; that is the case
  the re-screen exists for (``questionnaire_leakage``). Alignment evidence -- a
  finding already excluded for reporting a target outcome -- never becomes a
  respondent's hint, whatever the questionnaire says later.
* **Design input** (:func:`design_input`) -- every accepted finding per subject,
  with its quote, source and whether it may reach respondents, and the subjects
  with nothing: for the researcher and the design jobs, never as a measurement.
* **Analysis context** (:func:`analysis_context`) -- external context only. An
  external figure is never a panel result, so nothing here is admissible as a
  numeric claim; the evidence gate admits numbers from the population alone.

Recorded fixtures and fictional clients never feed a real study:
:func:`require_live_evidence` refuses them for anything client-facing, and
respondent context refuses a recorded bundle unless its caller is a test or the
workbench and says so.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from .bundle import EvidenceBundle
from .contracts import EvidenceOrigin, QuarantineReason, ScreenQuestion, digest
from .legacy import deterministic_target_overlap
from .merge import AcceptedEvidence, RespondentUse

__all__ = [
    "EXTERNAL_CONTEXT",
    "MAX_CONTEXT_BLOCKS",
    "AnalysisContext",
    "AnalysisItem",
    "ContextBlock",
    "DesignFinding",
    "DesignInput",
    "RecordedEvidenceRefused",
    "RespondentContext",
    "RespondentExclusion",
    "analysis_context",
    "design_input",
    "require_live_evidence",
    "respondent_context",
]

#: The evidence role external research carries everywhere it goes.
EXTERNAL_CONTEXT: Final = "EXTERNAL_CONTEXT"
#: The unit's ``max_context_blocks`` default (research_context.py ResearchConfig).
MAX_CONTEXT_BLOCKS: Final = 8


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RecordedEvidenceRefused(PermissionError):
    """Recorded or fictional evidence offered where only real evidence may go."""


def require_live_evidence(bundle: EvidenceBundle) -> None:
    """Refuse a bundle for client-facing use unless its evidence is real and its client too."""
    if EvidenceOrigin.RECORDED_FIXTURE in bundle.origins:
        raise RecordedEvidenceRefused("this bundle rests on recorded fixtures, not retrieval")
    if bundle.fictional_client:
        raise RecordedEvidenceRefused("this bundle researched a fictional client")


# --------------------------------------------------------------------------- #
# Respondents
# --------------------------------------------------------------------------- #


class ContextBlock(_Closed):
    """One respondent context block: the unit's ``KontextovyBlok`` fields, and its source."""

    id: str
    text: str
    temata: tuple[str, ...]
    datum: str
    zdroj: str
    jistota: float = Field(ge=0.0, le=1.0)
    evidence_id: str
    role: Literal["EXTERNAL_CONTEXT"]


class RespondentExclusion(_Closed):
    evidence_id: str
    reason: QuarantineReason
    detail: str = Field(max_length=2000)


class RespondentContext(_Closed):
    """What respondents may be told, what they may not, and what it was screened against."""

    bundle_sha256: str
    questionnaire_fingerprint: str
    blocks: tuple[ContextBlock, ...]
    excluded: tuple[RespondentExclusion, ...]
    #: Eligible findings beyond the block limit: not excluded, just not included.
    beyond_limit: tuple[str, ...]


def _block_id(position: int, claim: str) -> str:
    # The unit's id: research_<nn>_<sha1(claim)[:8]> (bundle_to_kontext).
    return f"research_{position:02d}_{hashlib.sha1(claim.encode('utf-8')).hexdigest()[:8]}"


def respondent_context(
    bundle: EvidenceBundle,
    questionnaire: Sequence[ScreenQuestion],
    *,
    allow_recorded: bool = False,
    max_blocks: int = MAX_CONTEXT_BLOCKS,
) -> RespondentContext:
    """Context blocks for the questionnaire respondents will actually answer.

    ``questionnaire`` must be the final one -- the compiled design fieldwork runs.
    ``allow_recorded`` is for tests and the workbench, which run on fixtures.
    """
    if not allow_recorded and EvidenceOrigin.RECORDED_FIXTURE in bundle.origins:
        raise RecordedEvidenceRefused(
            "recorded evidence is a fixture; it may not become a respondent's context"
        )
    screen = [{"text": q.text, "kategorie": list(q.kategorie)} for q in questionnaire]
    excluded: list[RespondentExclusion] = []
    eligible: list[AcceptedEvidence] = []
    for item in bundle.accepted:
        evidence = item.evidence
        if item.respondent_use is RespondentUse.EXCLUDED:
            excluded.append(
                RespondentExclusion(
                    evidence_id=evidence.evidence_id,
                    reason=item.respondent_exclusion or QuarantineReason.TARGET_OUTCOME_OVERLAP,
                    detail="excluded from respondent context when the bundle was merged",
                )
            )
        elif deterministic_target_overlap(evidence.claim, screen):
            excluded.append(
                RespondentExclusion(
                    evidence_id=evidence.evidence_id,
                    reason=QuarantineReason.QUESTIONNAIRE_LEAKAGE,
                    detail="the final questionnaire asks what this finding reports",
                )
            )
        else:
            eligible.append(item)
    eligible.sort(key=lambda a: (-a.confidence, a.evidence.evidence_id))
    blocks = tuple(
        ContextBlock(
            id=_block_id(i, a.evidence.claim),
            text=a.evidence.claim,
            temata=a.evidence.topics,
            datum=a.evidence.source_date or "",
            zdroj=a.evidence.source_url or a.evidence.source_ref,
            jistota=a.confidence,
            evidence_id=a.evidence.evidence_id,
            role=EXTERNAL_CONTEXT,
        )
        for i, a in enumerate(eligible[:max_blocks], 1)
    )
    return RespondentContext(
        bundle_sha256=bundle.sha256,
        questionnaire_fingerprint=digest([q.model_dump(mode="json") for q in questionnaire]),
        blocks=blocks,
        excluded=tuple(excluded),
        beyond_limit=tuple(a.evidence.evidence_id for a in eligible[max_blocks:]),
    )


# --------------------------------------------------------------------------- #
# Design and analysis
# --------------------------------------------------------------------------- #


class DesignFinding(_Closed):
    evidence_id: str
    claim: str
    quote: str
    source_title: str
    source: str
    source_class: str
    confidence: float
    respondent_use: RespondentUse


class DesignInput(_Closed):
    """What the design stage may read: findings per subject, and where there are none."""

    bundle_sha256: str
    role: Literal["EXTERNAL_CONTEXT"]
    origins: tuple[EvidenceOrigin, ...]
    fictional_client: bool
    findings: dict[str, tuple[DesignFinding, ...]]
    gaps: tuple[str, ...]


def design_input(bundle: EvidenceBundle) -> DesignInput:
    """Every accepted finding, by subject; subjects with none are gaps."""
    findings: dict[str, list[DesignFinding]] = {s.key: [] for s in bundle.subjects}
    for a in bundle.accepted:
        e = a.evidence
        findings.setdefault(e.subject_key, []).append(
            DesignFinding(
                evidence_id=e.evidence_id,
                claim=e.claim,
                quote=e.quote,
                source_title=e.source_title,
                source=e.source_url or e.source_ref,
                source_class=a.score.source_class,
                confidence=a.confidence,
                respondent_use=a.respondent_use,
            )
        )
    return DesignInput(
        bundle_sha256=bundle.sha256,
        role=EXTERNAL_CONTEXT,
        origins=bundle.origins,
        fictional_client=bundle.fictional_client,
        findings={k: tuple(v) for k, v in findings.items()},
        gaps=tuple(k for k, v in findings.items() if not v),
    )


class AnalysisItem(_Closed):
    evidence_id: str
    claim: str
    source: str
    role: Literal["EXTERNAL_CONTEXT"]
    #: Always false: an external figure is context for a finding, never a panel result.
    admissible_as_panel_claim: Literal[False]


class AnalysisContext(_Closed):
    bundle_sha256: str
    origins: tuple[EvidenceOrigin, ...]
    items: tuple[AnalysisItem, ...]


def analysis_context(bundle: EvidenceBundle) -> AnalysisContext:
    """Accepted findings as external context for interpretation, labelled as such."""
    return AnalysisContext(
        bundle_sha256=bundle.sha256,
        origins=bundle.origins,
        items=tuple(
            AnalysisItem(
                evidence_id=a.evidence.evidence_id,
                claim=a.evidence.claim,
                source=a.evidence.source_url or a.evidence.source_ref,
                role=EXTERNAL_CONTEXT,
                admissible_as_panel_claim=False,
            )
            for a in bundle.accepted
        ),
    )
