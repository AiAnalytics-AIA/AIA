"""The evidence bundle: what one Deep Research run publishes, hashed.

The bundle is the review surface and the handoff (DR-4 output 1): every track and
why it stopped, every accepted finding with its quote, source and score, every
quarantined one with its reason, the snapshots they rest on, the coverage matrix,
the brief, and what it cost. It is sealed with a SHA256 over its canonical JSON,
like 18.6.6's ``ResearchBundle.finalize_hash``.

It is never a client deliverable by itself (``client_facing`` is always false):
recorded evidence is a fixture, a fictional client's is fiction, and anything
else still needs a person's sign-off before it leaves AIA.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import (
    Channel,
    CoverageCell,
    DeepResearchRequest,
    EvidenceOrigin,
    GridCell,
    QualityStatus,
    QuarantinedEvidence,
    QueryRecord,
    ResearchSubject,
    RetrievalMode,
    StopReason,
    TrackStatus,
    digest,
)
from .merge import AcceptedEvidence
from .planning import PRESET_STATUS, coverage_grid
from .synthesis import SynthesisCheck

__all__ = [
    "EvidenceBundle",
    "SnapshotRef",
    "SynthesisRecord",
    "TrackRecord",
    "seal_bundle",
]


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TrackRecord(_Closed):
    """One track as it ran (or did not), with its counts and costs."""

    track_id: str
    subject_key: str
    channel: Channel
    fingerprint: str
    status: TrackStatus
    stop_reason: StopReason
    #: The gate that refused a blocked track, in words; empty otherwise.
    detail: str = Field(max_length=2000)
    reused: bool
    artifact_id: str | None
    retrieval_mode: RetrievalMode | None
    queries: tuple[QueryRecord, ...]
    snapshot_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    quarantined_ids: tuple[str, ...]
    model_requests: int = Field(ge=0)
    search_calls: int = Field(ge=0)
    fetches: int = Field(ge=0)
    credits: int = Field(ge=0)
    model_cost_usd: float = Field(ge=0.0)
    tool_cost_usd: float = Field(ge=0.0)


class SnapshotRef(_Closed):
    """A stored snapshot the bundle's findings cite: enough to fetch and check it."""

    snapshot_id: str
    artifact_id: str
    url: str
    final_url: str
    title: str
    retrieved_at: datetime
    text_sha256: str
    retrieval_mode: RetrievalMode
    instructions_detected: tuple[str, ...]


class SynthesisRecord(_Closed):
    artifact_id: str | None
    check: SynthesisCheck


class EvidenceBundle(_Closed):
    """The published result of one run. ``sha256`` is over everything else."""

    kind: Literal["deep_research_bundle"]
    harness_version: str
    versions: dict[str, str]
    design_revision_id: str
    design_revision: int
    request_fingerprint: str
    preset: str
    preset_status: str
    channels: tuple[Channel, ...]
    subjects: tuple[ResearchSubject, ...]
    tracks: tuple[TrackRecord, ...]
    coverage: tuple[CoverageCell, ...]
    grid: tuple[GridCell, ...]
    accepted: tuple[AcceptedEvidence, ...]
    quarantined: tuple[QuarantinedEvidence, ...]
    snapshots: tuple[SnapshotRef, ...]
    synthesis: SynthesisRecord | None
    quality_status: QualityStatus
    origins: tuple[EvidenceOrigin, ...]
    fictional_client: bool
    client_facing: Literal[False]
    counts: dict[str, int]
    spend_usd: dict[str, float]
    sha256: str

    def verify(self) -> bool:
        """True when the bundle still hashes to its seal."""
        return _seal_of(self.model_dump(mode="json")) == self.sha256


def _seal_of(payload: Mapping[str, object]) -> str:
    return digest({**payload, "sha256": ""})


def _quality(tracks: Sequence[TrackRecord], accepted: Sequence[AcceptedEvidence]) -> QualityStatus:
    if any(t.status is not TrackStatus.COMPLETED for t in tracks):
        return QualityStatus.PARTIAL
    return QualityStatus.GROUNDED if accepted else QualityStatus.NO_EVIDENCE


def seal_bundle(
    *,
    request: DeepResearchRequest,
    subjects: Sequence[ResearchSubject],
    versions: Mapping[str, str],
    tracks: Sequence[TrackRecord],
    accepted: Sequence[AcceptedEvidence],
    quarantined: Sequence[QuarantinedEvidence],
    snapshots: Sequence[SnapshotRef],
    synthesis: SynthesisRecord | None,
    fictional_client: bool,
    counts: Mapping[str, int],
    spend_usd: Mapping[str, float],
) -> EvidenceBundle:
    """Assemble the coverage matrix, the quality status and the origins, then seal.

    ``subjects`` are every subject the run tracked: the request's, and the crosses
    a preset opened.
    """
    accepted_by_track: dict[str, int] = {}
    for a in accepted:
        accepted_by_track[a.evidence.track_id] = accepted_by_track.get(a.evidence.track_id, 0) + 1
    quarantined_by_track: dict[str, int] = {}
    for q in quarantined:
        quarantined_by_track[q.track_id] = quarantined_by_track.get(q.track_id, 0) + 1
    coverage = tuple(
        CoverageCell(
            subject_key=t.subject_key,
            channel=t.channel,
            track_id=t.track_id,
            status=t.status,
            stop_reason=t.stop_reason,
            reused=t.reused,
            accepted=accepted_by_track.get(t.track_id, 0),
            quarantined=quarantined_by_track.get(t.track_id, 0),
        )
        for t in tracks
    )
    origins: set[EvidenceOrigin] = set()
    for t in tracks:
        if t.status is TrackStatus.BLOCKED:
            continue
        if t.channel is Channel.INTERNAL:
            origins.add(EvidenceOrigin.CLIENT_KNOWLEDGE)
        elif t.retrieval_mode is RetrievalMode.RECORDED:
            origins.add(EvidenceOrigin.RECORDED_FIXTURE)
        elif t.retrieval_mode is RetrievalMode.LIVE:
            origins.add(EvidenceOrigin.LIVE_RETRIEVAL)
    fields: dict[str, object] = {
        "kind": "deep_research_bundle",
        "harness_version": request.harness_version,
        "versions": dict(versions),
        "design_revision_id": request.design_revision_id,
        "design_revision": request.design_revision,
        "request_fingerprint": request.fingerprint(),
        "preset": request.preset,
        "preset_status": PRESET_STATUS,
        "channels": request.channels,
        "subjects": tuple(subjects),
        "tracks": tuple(tracks),
        "coverage": coverage,
        "grid": coverage_grid(subjects, coverage),
        "accepted": tuple(accepted),
        "quarantined": tuple(quarantined),
        "snapshots": tuple(snapshots),
        "synthesis": synthesis,
        "quality_status": _quality(tracks, accepted),
        "origins": tuple(sorted(origins)),
        "fictional_client": fictional_client,
        "client_facing": False,
        "counts": dict(counts),
        "spend_usd": dict(spend_usd),
        "sha256": "",
    }
    unsealed = EvidenceBundle.model_validate(fields)
    return unsealed.model_copy(update={"sha256": _seal_of(unsealed.model_dump(mode="json"))})
