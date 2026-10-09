"""What a run looked at, in the order a reader asks (plan chunk 47): the coverage ledger.

A brief says what was found. A reader also needs what was *not*: how many searches went
out and what came back, which pages were opened, which were refused and why, which
findings were set aside and for what reason. PRISMA's flow diagram is the model: the
excluded are counted, by reason, beside the kept.

Every count here is code's, never a model's, taken from two records the run already
keeps and cannot be edited: the sealed bundle (tracks, their queries and hits, the
snapshots, the accepted and the quarantined) and the run's tool journal (every call,
journaled before it left, with its outcome). A view computed on read: nothing new is
sealed, and the bundle's hash does not move.

A reused track was researched by an earlier run: its calls are in that run's journal,
not this one's, and it cost this run nothing. It is counted as found once, in
``reused_tracks``, and its calls are not this run's.

Pure: no I/O.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from .bundle import EvidenceBundle
from .contracts import QueryDecision
from .tooling import ToolKind, ToolOutcome, ToolUsageEvent

__all__ = ["COVERAGE_VERSION", "CoverageLedger", "ToolCoverage", "TrackCoverage", "coverage_ledger"]

COVERAGE_VERSION: Final = "aia-coverage-1"


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ToolCoverage(_Closed):
    """One kind of tool call in this run, by outcome; refusals and failures by reason."""

    tool: ToolKind
    sent: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    uncertain: int = Field(ge=0)
    #: Refused by AIA before anything was sent (class, route, address, robots.txt, budget).
    refused: int = Field(ge=0)
    #: Answered from what this run had already captured: nothing sent.
    cached: int = Field(ge=0)
    refused_by_reason: dict[str, int]
    failed_by_reason: dict[str, int]


class TrackCoverage(_Closed):
    """One track's funnel: proposed, sent, found, captured, kept, set aside."""

    track_id: str
    subject_key: str
    status: str
    stop_reason: str
    reused: bool
    queries_proposed: int = Field(ge=0)
    queries_sent: int = Field(ge=0)
    queries_refused: int = Field(ge=0)
    hits: int = Field(ge=0)
    sources_captured: int = Field(ge=0)
    findings_grounded: int = Field(ge=0)
    findings_quarantined: int = Field(ge=0)


class CoverageLedger(_Closed):
    """The run's coverage, totals first, then per tool and per track."""

    version: str = COVERAGE_VERSION
    bundle_sha256: str
    tracks: int = Field(ge=0)
    reused_tracks: int = Field(ge=0)
    blocked_tracks: int = Field(ge=0)
    queries_proposed: int = Field(ge=0)
    queries_sent: int = Field(ge=0)
    queries_refused: int = Field(ge=0)
    queries_refused_by_reason: dict[str, int]
    hits: int = Field(ge=0)
    sources_captured: int = Field(ge=0)
    findings_grounded: int = Field(ge=0)
    findings_accepted: int = Field(ge=0)
    findings_quarantined: int = Field(ge=0)
    quarantined_by_reason: dict[str, int]
    tools: tuple[ToolCoverage, ...]
    by_track: tuple[TrackCoverage, ...]


def _sorted(counts: Counter[str]) -> dict[str, int]:
    """Most frequent first, then by name: the order a reader scans."""
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def _tools(journal: Iterable[ToolUsageEvent]) -> tuple[ToolCoverage, ...]:
    by_tool: dict[ToolKind, Counter[ToolOutcome]] = {}
    refused: dict[ToolKind, Counter[str]] = {}
    failed: dict[ToolKind, Counter[str]] = {}
    for event in journal:
        by_tool.setdefault(event.tool, Counter())[event.outcome] += 1
        if event.outcome is ToolOutcome.REFUSED:
            refused.setdefault(event.tool, Counter())[event.note or "unstated"] += 1
        elif event.outcome is ToolOutcome.FAILED:
            failed.setdefault(event.tool, Counter())[event.note or "unstated"] += 1
    return tuple(
        ToolCoverage(
            tool=tool,
            sent=counts[ToolOutcome.DISPATCHED],
            succeeded=counts[ToolOutcome.SUCCEEDED],
            failed=counts[ToolOutcome.FAILED],
            uncertain=counts[ToolOutcome.UNCERTAIN],
            refused=counts[ToolOutcome.REFUSED],
            cached=counts[ToolOutcome.CACHED],
            refused_by_reason=_sorted(refused.get(tool, Counter())),
            failed_by_reason=_sorted(failed.get(tool, Counter())),
        )
        for tool, counts in sorted(by_tool.items(), key=lambda kv: kv[0].value)
    )


def coverage_ledger(bundle: EvidenceBundle, journal: Iterable[ToolUsageEvent]) -> CoverageLedger:
    """The ledger of one run, from its sealed bundle and its own tool journal."""
    quarantined_reason: Mapping[str, str] = {
        q.evidence_id: q.reason.value for q in bundle.quarantined
    }
    by_track = []
    refused_reasons: Counter[str] = Counter()
    for t in bundle.tracks:
        sent = sum(1 for q in t.queries if q.decision is QueryDecision.SENT)
        refused = [q for q in t.queries if q.decision is not QueryDecision.SENT]
        refused_reasons.update(q.refusal or "unstated" for q in refused)
        by_track.append(
            TrackCoverage(
                track_id=t.track_id,
                subject_key=t.subject_key,
                status=t.status.value,
                stop_reason=t.stop_reason.value,
                reused=t.reused,
                queries_proposed=len(t.queries),
                queries_sent=sent,
                queries_refused=len(refused),
                hits=sum(q.hits for q in t.queries),
                sources_captured=len(t.snapshot_ids),
                findings_grounded=len(t.evidence_ids),
                findings_quarantined=sum(1 for i in t.quarantined_ids if i in quarantined_reason),
            )
        )
    return CoverageLedger(
        bundle_sha256=bundle.sha256,
        tracks=len(bundle.tracks),
        reused_tracks=sum(1 for t in bundle.tracks if t.reused),
        blocked_tracks=sum(1 for t in bundle.tracks if t.status.value == "BLOCKED"),
        queries_proposed=sum(c.queries_proposed for c in by_track),
        queries_sent=sum(c.queries_sent for c in by_track),
        queries_refused=sum(c.queries_refused for c in by_track),
        queries_refused_by_reason=_sorted(refused_reasons),
        hits=sum(c.hits for c in by_track),
        sources_captured=len(bundle.snapshots),
        findings_grounded=sum(c.findings_grounded for c in by_track),
        findings_accepted=len(bundle.accepted),
        findings_quarantined=len(bundle.quarantined),
        quarantined_by_reason=_sorted(Counter(quarantined_reason.values())),
        tools=_tools(journal),
        by_track=tuple(by_track),
    )
