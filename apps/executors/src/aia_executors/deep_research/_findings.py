"""A track's grounded and quarantined findings, and a track refused before it began."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from aia_core.domain.deep_research.agents import ProposedEvidence, TurnEvidence
from aia_core.domain.deep_research.contracts import (
    EvidenceItem,
    QuarantinedEvidence,
    ResearchTrack,
    RetrievalMode,
    SourceKind,
    StopReason,
    TrackStatus,
    evidence_id,
)
from aia_core.domain.deep_research.grounding import GroundableSource, ground
from aia_core.domain.deep_research.measures import normalised_measure
from aia_core.domain.deep_research.steps import TrackResult
from aia_core.domain.residency import DataClass
from aia_worker.executor import StepInput

__all__ = ["_Findings", "_blocked_result"]


def _blocked_result(
    step: StepInput, track: ResearchTrack, stop: StopReason, detail: str, mode: RetrievalMode | None
) -> TrackResult:
    return TrackResult(
        kind="deep_research_track",
        run_id=step.run_id,
        track=track,
        status=TrackStatus.BLOCKED,
        stop_reason=stop,
        detail=detail[:2000],
        retrieval_mode=mode,
        sub_questions=(),
        queries=(),
        snapshots=(),
        knowledge_refs=(),
        sources=(),
        evidence=(),
        quarantined=(),
        gaps=(),
        calls=(),
        search_calls=0,
        fetches=0,
        credits=0,
        model_cost_usd=0.0,
        tool_cost_usd=0.0,
    )


@dataclass(slots=True)
class _Findings:
    """One track's grounded and quarantined findings, deduplicated by evidence id."""

    track: ResearchTrack
    data_class: DataClass
    evidence: list[EvidenceItem]
    quarantined: list[QuarantinedEvidence]

    def add(
        self,
        proposals: Sequence[ProposedEvidence],
        *,
        sources: dict[str, GroundableSource],
        kind: SourceKind,
        urls: dict[str, str],
        titles: dict[str, str],
    ) -> tuple[list[str], list[str]]:
        """Ground each proposal against the track's own sources.

        Returns the evidence ids newly grounded and newly quarantined. A
        :class:`TurnEvidence` (the agent-directed investigator's) states its measures,
        and grounding checks them too (check 5); the planned mode's proposals state
        none and are grounded exactly as before.
        """
        seen = {e.evidence_id for e in self.evidence} | {q.evidence_id for q in self.quarantined}
        grounded: list[str] = []
        quarantined: list[str] = []
        for p in proposals:
            eid = evidence_id(self.track.fingerprint, p.source_id, p.quote, p.claim)
            if eid in seen:
                continue
            seen.add(eid)
            stated = [m.to_measure() for m in p.measures] if isinstance(p, TurnEvidence) else None
            verdict = ground(
                source_ref=p.source_id,
                quote=p.quote,
                claim=p.claim,
                sources=sources,
                measures=stated,
            )
            item = None
            if verdict.span is not None:
                item = EvidenceItem(
                    evidence_id=eid,
                    track_id=self.track.track_id,
                    subject_key=self.track.subject.key,
                    channel=self.track.channel,
                    source_kind=kind,
                    source_ref=p.source_id,
                    source_url=urls.get(p.source_id),
                    source_title=titles.get(p.source_id, ""),
                    claim=p.claim,
                    quote=p.quote,
                    quote_span=verdict.span,
                    evidence_type=p.evidence_type,
                    source_date=p.source_date,
                    geography=p.geography,
                    population=p.population,
                    topics=tuple(p.topics),
                    data_class=self.data_class,
                    agent_outcome_overlap=p.outcome_overlap,
                    agent_recommended_use=p.recommended_use,
                    agent_source_quality=p.source_quality,
                    measures=tuple(normalised_measure(m) for m in stated or ()),
                )
            if verdict.grounded and item is not None:
                self.evidence.append(item)
                grounded.append(eid)
                continue
            assert verdict.failure is not None
            detail = verdict.detail if item is not None else f"{verdict.detail}; quote: {p.quote}"
            self.quarantined.append(
                QuarantinedEvidence(
                    evidence_id=eid,
                    track_id=self.track.track_id,
                    reason=verdict.failure,
                    detail=detail[:2000],
                    claim=p.claim,
                    source_ref=p.source_id,
                    evidence=item,
                )
            )
            quarantined.append(eid)
        return grounded, quarantined
