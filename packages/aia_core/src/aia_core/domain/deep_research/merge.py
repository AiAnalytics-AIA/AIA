"""Merge and verification: grounded findings -> candidates -> accepted evidence.

What decides acceptance, in order, each deterministic except the verifier's verdict:

1. **Grounding** -- already decided per track (:mod:`.grounding`); only grounded
   findings arrive here.
2. **Source quality** from the declared tables (:mod:`.sources`), never the agent's
   own score: below :data:`~.sources.ACCEPT_THRESHOLD` is ``low_source_quality``.
3. **Dedupe** -- the same source saying the same thing twice (claim similarity at
   the legacy 0.42) is one candidate that remembers the others.
4. **Independent confirmation** is a bonus to confidence, never the gate: a similar
   claim from a *different* source raises it (ADR 0017: two agents can agree on the
   same invention, so agreement alone proves nothing).
5. **The verifier** judges each candidate against its own excerpt; anything but
   ``supported`` is quarantined, and a candidate the verifier did not answer for is
   ``unverified``.

The **leakage rule** (18.6.6, :mod:`.legacy`) is not an acceptance rule here. A
finding that reports a survey question's answer -- by the agent's own label, or by
the deterministic screen against the questionnaire the design holds -- stays in
the bundle as alignment evidence for the researcher, and is excluded from
respondent context, for good (:mod:`.quarantine` re-screens the rest against the
final questionnaire).

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from .agents import Verdict
from .contracts import (
    EvidenceItem,
    QuarantinedEvidence,
    QuarantineReason,
    RecommendedUse,
    ScreenQuestion,
    SourceKind,
)
from .legacy import canonical_url, deterministic_target_overlap, similarity
from .sources import SourceScore, SourceTable, score_knowledge_source, score_web_source
from .works import WORKS_VERSION, WorkStatusRecord

__all__ = [
    "CONFIRMATION_BONUS",
    "MERGE_RULES_VERSION",
    "SIMILAR",
    "AcceptedEvidence",
    "Candidate",
    "MergeResult",
    "RespondentUse",
    "ScoreRecord",
    "SourceFacts",
    "TrackEvidence",
    "apply_verdicts",
    "excerpt_window",
    "merge_evidence",
    "respondent_screen",
    "verification_batches",
]

#: Carries the works rule's version: what a retraction quarantines (chunk 46).
MERGE_RULES_VERSION: Final = f"aia-merge-2/{WORKS_VERSION}"
#: The unit's claim-similarity threshold for "the same finding" (research_context.py:360).
SIMILAR: Final = 0.42
#: Confidence added per independent confirmation, for at most two.
CONFIRMATION_BONUS: Final = 0.1


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RespondentUse(StrEnum):
    """Whether a finding may ever become respondent context."""

    ELIGIBLE = "ELIGIBLE"
    EXCLUDED = "EXCLUDED"


class ScoreRecord(_Closed):
    """A source's score and every term of it, as stored with the finding."""

    source_class: str
    base: float
    age: str
    age_adjustment: float
    score: float
    geography: str
    table_version: str

    @classmethod
    def of(cls, score: SourceScore) -> ScoreRecord:
        return cls(
            source_class=score.source_class.value,
            base=score.base,
            age=score.age,
            age_adjustment=score.age_adjustment,
            score=score.score,
            geography=score.geography,
            table_version=score.table_version,
        )


class Candidate(_Closed):
    """A grounded finding from an acceptable source, awaiting the verifier."""

    evidence: EvidenceItem
    score: ScoreRecord
    respondent_use: RespondentUse
    respondent_exclusion: QuarantineReason | None
    merged_ids: tuple[str, ...]
    confirmations: tuple[str, ...]
    confidence: float = Field(ge=0.0, le=1.0)


class AcceptedEvidence(_Closed):
    """A finding the bundle may be used for: grounded, adequately sourced, verified."""

    evidence: EvidenceItem
    score: ScoreRecord
    respondent_use: RespondentUse
    respondent_exclusion: QuarantineReason | None
    merged_ids: tuple[str, ...]
    confirmations: tuple[str, ...]
    confidence: float = Field(ge=0.0, le=1.0)
    verifier_reason: str


@dataclass(frozen=True, slots=True)
class SourceFacts:
    """What scoring needs about one source: where it is, and when it was written and read."""

    ref: str
    kind: SourceKind
    url: str | None
    published: date | None
    retrieved: date | None
    #: The cited work's standing, when the source named a DOI and an index was asked
    #: (chunk 46); ``None`` when nobody asked.
    work_status: WorkStatusRecord | None = None


@dataclass(frozen=True, slots=True)
class TrackEvidence:
    """One track's grounded findings and the facts about the sources they cite."""

    track_id: str
    evidence: tuple[EvidenceItem, ...]
    sources: Mapping[str, SourceFacts]


@dataclass(frozen=True, slots=True)
class MergeResult:
    candidates: tuple[Candidate, ...]
    quarantined: tuple[QuarantinedEvidence, ...]


def _as_screen(questions: Sequence[ScreenQuestion]) -> list[dict[str, object]]:
    return [{"text": q.text, "kategorie": list(q.kategorie)} for q in questions]


def respondent_screen(
    item: EvidenceItem, questionnaire: Sequence[ScreenQuestion]
) -> QuarantineReason | None:
    """The 18.6.6 leakage rule for one finding: the agent's label, then the screen."""
    if item.agent_outcome_overlap or item.agent_recommended_use is not RecommendedUse.CONTEXT_ONLY:
        return QuarantineReason.TARGET_OUTCOME_OVERLAP
    if deterministic_target_overlap(item.claim, _as_screen(questionnaire)):
        return QuarantineReason.DETERMINISTIC_TARGET_OVERLAP
    return None


def _score(item: EvidenceItem, facts: SourceFacts | None, table: SourceTable) -> SourceScore:
    if item.source_kind is SourceKind.CLIENT_KNOWLEDGE:
        return score_knowledge_source(table)
    if facts is None or facts.url is None or facts.retrieved is None:
        # A web finding whose source facts are missing is unscored, and unscored
        # is not "fine": it gets the unknown host's score.
        return score_web_source("", published=None, retrieved=date.min, table=table)
    return score_web_source(
        facts.url, published=facts.published, retrieved=facts.retrieved, table=table
    )


def _same_source(a: EvidenceItem, b: EvidenceItem) -> bool:
    if a.source_url and b.source_url:
        return canonical_url(a.source_url) == canonical_url(b.source_url)
    return a.source_ref == b.source_ref


def merge_evidence(
    tracks: Sequence[TrackEvidence],
    *,
    questionnaire: Sequence[ScreenQuestion],
    table: SourceTable,
) -> MergeResult:
    """Score, screen and deduplicate every track's grounded findings, in track order."""
    quarantined: list[QuarantinedEvidence] = []
    scored: list[tuple[EvidenceItem, SourceScore]] = []
    for track in tracks:
        for item in track.evidence:
            facts = track.sources.get(item.source_ref)
            standing = facts.work_status if facts is not None else None
            if standing is not None and standing.quarantines:
                # A retracted work is a known bad source, whatever its host scores.
                notice = next((n for n in standing.notices if n.notice_doi), None)
                quarantined.append(
                    QuarantinedEvidence(
                        evidence_id=item.evidence_id,
                        track_id=item.track_id,
                        reason=QuarantineReason.RETRACTED_SOURCE,
                        detail=(
                            f"{standing.doi} is {standing.status.value} "
                            f"(per {', '.join(standing.checked_by)}"
                            + (f"; notice {notice.notice_doi}" if notice else "")
                            + ")"
                        )[:500],
                        claim=item.claim,
                        source_ref=item.source_ref,
                    )
                )
                continue
            score = _score(item, facts, table)
            if not score.acceptable:
                quarantined.append(
                    QuarantinedEvidence(
                        evidence_id=item.evidence_id,
                        track_id=item.track_id,
                        reason=QuarantineReason.LOW_SOURCE_QUALITY,
                        detail=(
                            f"{score.source_class.value} source scored {score.score} "
                            f"(table {score.table_version})"
                        ),
                        claim=item.claim,
                        source_ref=item.source_ref,
                        evidence=item,
                    )
                )
            else:
                scored.append((item, score))

    kept: list[tuple[EvidenceItem, SourceScore, list[str]]] = []
    for item, score in scored:
        twin = next(
            (
                k
                for k in kept
                if _same_source(k[0], item) and similarity(k[0].claim, item.claim) >= SIMILAR
            ),
            None,
        )
        if twin is not None:
            twin[2].append(item.evidence_id)
        else:
            kept.append((item, score, []))

    candidates = []
    for item, score, merged in kept:
        confirmations = tuple(
            other.evidence_id
            for other, _, _ in kept
            if other.evidence_id != item.evidence_id
            and not _same_source(other, item)
            and similarity(other.claim, item.claim) >= SIMILAR
        )
        exclusion = respondent_screen(item, questionnaire)
        candidates.append(
            Candidate(
                evidence=item,
                score=ScoreRecord.of(score),
                respondent_use=RespondentUse.EXCLUDED if exclusion else RespondentUse.ELIGIBLE,
                respondent_exclusion=exclusion,
                merged_ids=tuple(merged),
                confirmations=confirmations,
                confidence=round(
                    min(0.98, score.score + CONFIRMATION_BONUS * min(2, len(confirmations))), 3
                ),
            )
        )
    return MergeResult(candidates=tuple(candidates), quarantined=tuple(quarantined))


def verification_batches(
    candidates: Sequence[Candidate], *, size: int
) -> tuple[tuple[Candidate, ...], ...]:
    """Candidates grouped by the track that found them, then in chunks of ``size``.

    Grouping by track keeps a batch's identity stable across passes: an unchanged
    track's candidates make the same batch, whose verification is then reused.
    """
    if size <= 0:
        raise ValueError("a verification batch holds at least one candidate")
    by_track: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        by_track.setdefault(candidate.evidence.track_id, []).append(candidate)
    return tuple(
        tuple(group[i : i + size])
        for group in by_track.values()
        for i in range(0, len(group), size)
    )


def excerpt_window(text: str, span: tuple[int, int], *, chars: int = 400) -> str:
    """The quote with up to ``chars`` characters either side: what the verifier reads."""
    start, end = span
    if not 0 <= start <= end <= len(text):
        raise ValueError("the span is not inside the text")
    return text[max(0, start - chars) : min(len(text), end + chars)]


def apply_verdicts(
    candidates: Sequence[Candidate], verdicts: Mapping[str, tuple[Verdict, str]]
) -> tuple[tuple[AcceptedEvidence, ...], tuple[QuarantinedEvidence, ...]]:
    """Supported candidates become accepted evidence; every other one is quarantined."""
    accepted: list[AcceptedEvidence] = []
    quarantined: list[QuarantinedEvidence] = []
    reasons = {
        Verdict.UNSUPPORTED: QuarantineReason.UNSUPPORTED_BY_VERIFIER,
        Verdict.OVERSTATED: QuarantineReason.OVERSTATED_BY_VERIFIER,
    }
    for candidate in candidates:
        item = candidate.evidence
        verdict = verdicts.get(item.evidence_id)
        if verdict is not None and verdict[0] is Verdict.SUPPORTED:
            accepted.append(
                AcceptedEvidence(
                    **candidate.model_dump(exclude={"evidence", "score"}),
                    evidence=item,
                    score=candidate.score,
                    verifier_reason=verdict[1],
                )
            )
            continue
        reason = reasons[verdict[0]] if verdict is not None else QuarantineReason.UNVERIFIED
        quarantined.append(
            QuarantinedEvidence(
                evidence_id=item.evidence_id,
                track_id=item.track_id,
                reason=reason,
                detail=verdict[1][:2000] if verdict is not None else "no verdict was returned",
                claim=item.claim,
                source_ref=item.source_ref,
                evidence=item,
            )
        )
    return tuple(accepted), tuple(quarantined)
