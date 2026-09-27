"""The research brief: what the synthesizer wrote, and what of it may be published.

The synthesizer sees accepted evidence only -- never a raw page -- and writes a
Czech brief whose every finding cites evidence ids. Code then decides, per
finding, and says why when the answer is no (plan decision I-5; the analysis
modules' number rule, ``domain/analysis/draft.py``):

* the subject must be one of the run's (``unknown_subject``);
* every cited id must be accepted evidence (``citation_not_accepted``) -- a
  quarantined finding, an unknown id or another run's cannot be cited;
* every number in the text must be in the quote of an item it cites
  (``number_not_in_cited_evidence``), except where the text writes the subject's
  own range or bound (``18-29``) as the subject names it.

A finding that fails is **excluded with its reason**, never published and never
rewritten. The summary cites nothing itself, so its numbers must be in the
quotes of what the published findings cite; a summary that fails is withheld.
With accepted evidence and no finding left, the brief is ``BLOCKED``.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ..analysis.draft import numbers_in, uncovered_numbers
from .agents import Finding, SynthesisProposal
from .contracts import ResearchSubject
from .merge import AcceptedEvidence

__all__ = [
    "ExcludedFinding",
    "PublishedFinding",
    "SynthesisCheck",
    "SynthesisStatus",
    "validate_synthesis",
]


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SynthesisStatus(StrEnum):
    #: Every finding and the summary passed.
    COMPLETE = "COMPLETE"
    #: Something was excluded or withheld; the reasons are in the brief.
    PARTIAL = "PARTIAL"
    #: There was accepted evidence, and no finding survived.
    BLOCKED = "BLOCKED"
    #: Nothing was accepted, so nothing was written.
    EMPTY = "EMPTY"


class PublishedFinding(_Closed):
    subject_key: str
    text: str
    evidence_ids: tuple[str, ...]


class ExcludedFinding(_Closed):
    index: int
    subject_key: str
    text: str
    reason: str
    detail: str = Field(max_length=2000)


class SynthesisCheck(_Closed):
    status: SynthesisStatus
    summary: str | None
    summary_withheld: str | None
    findings: tuple[PublishedFinding, ...]
    excluded: tuple[ExcludedFinding, ...]
    gaps: tuple[str, ...]
    limitations: tuple[str, ...]


def _quote_numbers(ids: Sequence[str], accepted: Mapping[str, AcceptedEvidence]) -> list[float]:
    return [v for i in ids if i in accepted for v, _ in numbers_in(accepted[i].evidence.quote)]


def _refusal(
    finding: Finding,
    *,
    accepted: Mapping[str, AcceptedEvidence],
    subjects: Mapping[str, ResearchSubject],
) -> tuple[str, str] | None:
    """Why one finding may not be published, or ``None`` when it may."""
    subject = subjects.get(finding.subject_key)
    if subject is None:
        return "unknown_subject", f"{finding.subject_key!r} is not a subject of this run"
    foreign = [i for i in finding.evidence_ids if i not in accepted]
    if foreign:
        return "citation_not_accepted", "cites no accepted evidence: " + ", ".join(foreign)
    missing = uncovered_numbers(
        finding.text, _quote_numbers(finding.evidence_ids, accepted), [subject.text]
    )
    if missing:
        shown = ", ".join(f"{n:g}" for n in missing)
        return "number_not_in_cited_evidence", f"{shown} is in no quote this finding cites"
    return None


def validate_synthesis(
    proposal: SynthesisProposal,
    *,
    accepted: Mapping[str, AcceptedEvidence],
    subjects: Mapping[str, ResearchSubject],
) -> SynthesisCheck:
    """Check the synthesizer's brief against the evidence it was given."""
    published: list[PublishedFinding] = []
    excluded: list[ExcludedFinding] = []
    for index, finding in enumerate(proposal.findings):
        refusal = _refusal(finding, accepted=accepted, subjects=subjects)
        if refusal is not None:
            excluded.append(
                ExcludedFinding(
                    index=index,
                    subject_key=finding.subject_key,
                    text=finding.text,
                    reason=refusal[0],
                    detail=refusal[1][:2000],
                )
            )
            continue
        published.append(
            PublishedFinding(
                subject_key=finding.subject_key,
                text=finding.text,
                evidence_ids=tuple(dict.fromkeys(finding.evidence_ids)),
            )
        )

    cited = [i for f in published for i in f.evidence_ids]
    summary_missing = uncovered_numbers(
        proposal.summary, _quote_numbers(cited, accepted), [s.text for s in subjects.values()]
    )
    withheld = (
        "the summary states "
        + ", ".join(f"{n:g}" for n in summary_missing)
        + ", which no published finding's evidence carries"
        if summary_missing
        else None
    )
    if accepted and not published:
        status = SynthesisStatus.BLOCKED
    elif excluded or withheld:
        status = SynthesisStatus.PARTIAL
    else:
        status = SynthesisStatus.COMPLETE
    return SynthesisCheck(
        status=status,
        summary=None if withheld else proposal.summary,
        summary_withheld=withheld,
        findings=tuple(published),
        excluded=tuple(excluded),
        gaps=tuple(proposal.gaps),
        limitations=tuple(proposal.limitations),
    )
