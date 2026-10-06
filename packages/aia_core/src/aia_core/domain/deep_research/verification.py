"""Verification in the agent-directed mode: the independent verifier's verdicts, decided by code.

Plan ``deep-research-web-search.md`` §§ 8.3-8.5, chunk 12. The planned mode keeps
:func:`~.merge.apply_verdicts` and its verifier unchanged; an agent-directed run is
reviewed here instead, over the same merge candidates:

1. **Publisher independence** (:mod:`.triangulation`): a candidate's confirmations
   are its similar claims from *other independence groups* -- one per group, so a
   syndicated press release, or a publisher's two pages, counts once. Confidence is
   the merge's formula over those (:data:`~.merge.CONFIRMATION_BONUS`, at most two).
2. **Primary tracing** (:mod:`.tracing`): primary, secondary (traced to its primary
   finding, or a lead raised), or undetermined.
3. **The independent verifier** (:mod:`.verifier`) judges each candidate; code
   applies its verdict, first reason that holds:

   * no judgement -> ``unverified``;
   * ``unsupported`` / ``overstated`` -> quarantined so;
   * superseded **by code** -> ``superseded``, whatever the verdict says: every
     measure of the finding has a newer figure (:func:`supersessions`) in a
     candidate the verifier itself judged ``supported``;
   * ``superseded`` from the verifier -> stands only when ``superseded_by`` names
     another candidate from the same publisher that the verifier judged
     ``supported`` and that the measures do not show to be older
     (:func:`proposed_supersession_problem`); otherwise ``unverified``, saying why;
   * ``supported`` -> accepted.

**Superseded by code** (§ 8.4: "a newer figure from the same publisher, captured"),
for two measures of one publisher with the same name, unit and place, and the same
population and denominator (both unstated counts as the same):

* ``newer_period`` -- the other's period is entirely later;
* ``revised`` -- the same period, values different beyond rounding, and the other is
  more final (actual over preliminary or estimate over forecast; both stated), or
  equally final and from a source published later (both dates known).

A finding that states several figures is superseded only when every one is; a figure
that only *another* publisher has updated is not superseded but, if the values
overlap in period, a conflict.

4. **Conflicts** among the accepted findings (:func:`~.triangulation.detect_conflicts`)
   and a resolve-track request for each open one.

Everything decided is recorded in :class:`VerificationReview`.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import EvidenceItem, Measure, QuarantinedEvidence, QuarantineReason, digest
from .merge import CONFIRMATION_BONUS, AcceptedEvidence, Candidate
from .reputation import ReputationRegister
from .tracing import TRACING_VERSION, PrimaryLead, PrimaryStatus, TraceRecord
from .triangulation import (
    TRIANGULATION_VERSION,
    Conflict,
    ConflictTolerance,
    IndependenceGroup,
    MeasuredFinding,
    ResolveTrackRequest,
    basis_rank,
    detect_conflicts,
    measure_key,
    period_span,
    resolve_requests,
)
from .verifier import VERIFIER_CONTRACT_VERSION, ClaimJudgement, ClaimVerdict

__all__ = [
    "RELATED_LIMIT",
    "VERIFICATION_RULES_VERSION",
    "ReviewOutcome",
    "Supersession",
    "SupersessionRule",
    "VerificationReview",
    "VerifierLead",
    "independent_confirmations",
    "proposed_supersession_problem",
    "review_candidates",
    "supersessions",
    "verifier_item",
]

#: The rules this module applies, with the rules it depends on.
VERIFICATION_RULES_VERSION: Final = (
    f"aia-dr-verification-1/{TRACING_VERSION}/{TRIANGULATION_VERSION}/{VERIFIER_CONTRACT_VERSION}"
)

#: At most this many of the same publisher's other figures are shown with a finding.
RELATED_LIMIT: Final = 5


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SupersessionRule(StrEnum):
    NEWER_PERIOD = "newer_period"
    REVISED = "revised"
    #: The verifier proposed it, naming a captured figure code could not refuse.
    VERIFIER = "verifier"


class Supersession(_Closed):
    evidence_id: str
    #: The newer figures, one per superseded measure, each verified itself.
    superseded_by: tuple[str, ...]
    rule: SupersessionRule
    detail: str = Field(max_length=1000)


class VerifierLead(_Closed):
    """A search the verifier proposed. Recorded; sent, if ever, by code through the gate."""

    lead_id: str
    evidence_id: str
    query: str
    #: The publisher as the verifier wrote it, and the register's name for it, if any.
    publisher_named: str | None
    publisher: str | None
    why: str


class VerificationReview(_Closed):
    """Everything an agent-directed verify step decided beside acceptance."""

    kind: Literal["deep_research_verification_review"]
    rules_version: str
    register_version: str | None
    independence: tuple[IndependenceGroup, ...]
    traces: tuple[TraceRecord, ...]
    primary_leads: tuple[PrimaryLead, ...]
    verifier_leads: tuple[VerifierLead, ...]
    supersessions: tuple[Supersession, ...]
    conflicts: tuple[Conflict, ...]
    resolve_requests: tuple[ResolveTrackRequest, ...]


# --------------------------------------------------------------------------- #
# Supersession
# --------------------------------------------------------------------------- #


def _same_series(a: Measure, b: Measure) -> bool:
    key = measure_key(a)
    return (
        key is not None
        and key == measure_key(b)
        and a.population == b.population
        and a.denominator == b.denominator
    )


def _newer(
    old: Measure,
    new: Measure,
    old_published: date | None,
    new_published: date | None,
    tolerance: ConflictTolerance,
) -> SupersessionRule | None:
    """Whether ``new`` supersedes ``old`` (rule: module doc), and by which rule."""
    if not _same_series(old, new):
        return None
    old_span, new_span = period_span(old.period), period_span(new.period)
    if old_span is None or new_span is None:
        return None
    if new_span.after(old_span):
        return SupersessionRule.NEWER_PERIOD
    if new_span != old_span or tolerance.agree(old, new):
        return None
    old_rank, new_rank = basis_rank(old.basis), basis_rank(new.basis)
    if old_rank is not None and new_rank is not None and new_rank != old_rank:
        return SupersessionRule.REVISED if new_rank > old_rank else None
    if old.basis == new.basis and old_published and new_published and new_published > old_published:
        return SupersessionRule.REVISED
    return None


def supersessions(
    items: Sequence[EvidenceItem],
    *,
    publishers: Mapping[str, str],
    published: Mapping[str, date | None],
    eligible: frozenset[str],
    tolerance: ConflictTolerance | None = None,
) -> dict[str, Supersession]:
    """Findings every figure of which a newer, ``eligible`` finding of one publisher states.

    ``publishers`` and ``published`` are by evidence id; ``eligible`` names the
    findings that may supersede (the verifier judged them supported).
    """
    tolerance = tolerance or ConflictTolerance()
    found: dict[str, Supersession] = {}
    ordered = sorted(items, key=lambda i: i.evidence_id)
    for item in ordered:
        if not item.measures:
            continue
        by: list[str] = []
        rules: list[SupersessionRule] = []
        for m in item.measures:
            best: tuple[int, str, SupersessionRule] | None = None
            for other in ordered:
                if (
                    other.evidence_id == item.evidence_id
                    or other.evidence_id not in eligible
                    or publishers.get(other.evidence_id) != publishers.get(item.evidence_id)
                ):
                    continue
                for n in other.measures:
                    rule = _newer(
                        m,
                        n,
                        published.get(item.evidence_id),
                        published.get(other.evidence_id),
                        tolerance,
                    )
                    span = period_span(n.period)
                    if rule is not None and span is not None:
                        candidate = (-span.end, other.evidence_id, rule)
                        if best is None or candidate < best:
                            best = candidate
            if best is None:
                break
            by.append(best[1])
            rules.append(best[2])
        else:
            rule = (
                SupersessionRule.NEWER_PERIOD
                if SupersessionRule.NEWER_PERIOD in rules
                else SupersessionRule.REVISED
            )
            newer = tuple(dict.fromkeys(by))
            found[item.evidence_id] = Supersession(
                evidence_id=item.evidence_id,
                superseded_by=newer,
                rule=rule,
                detail=(
                    f"{rule.value}: every figure is stated newer by the same publisher in "
                    + ", ".join(newer)
                )[:1000],
            )
    return found


def proposed_supersession_problem(
    item: EvidenceItem,
    by: str | None,
    *,
    candidates: Mapping[str, EvidenceItem],
    publishers: Mapping[str, str],
    published: Mapping[str, date | None],
    eligible: frozenset[str],
    tolerance: ConflictTolerance | None = None,
) -> str | None:
    """Why a verifier's ``superseded`` cannot stand, in words; ``None`` when it can."""
    tolerance = tolerance or ConflictTolerance()
    if by is None:
        return "it names no newer figure"
    newer = candidates.get(by)
    if newer is None or by == item.evidence_id:
        return f"{by} is not another captured finding of this run"
    if publishers.get(by) != publishers.get(item.evidence_id):
        return f"{by} is not from the same publisher"
    if by not in eligible:
        return f"{by} is not itself verified as supported"
    for m in item.measures:
        for n in newer.measures:
            if not _same_series(m, n):
                continue
            old_span, new_span = period_span(m.period), period_span(n.period)
            if old_span is None or new_span is None:
                continue
            if old_span.after(new_span):
                return f"{by} states an older period ({n.period}) than {m.period}"
            if old_span == new_span and _newer(
                n, m, published.get(by), published.get(item.evidence_id), tolerance
            ):
                return f"{by} is the earlier figure for {m.period}, by its measures"
    return None


# --------------------------------------------------------------------------- #
# Independence and the verifier's input
# --------------------------------------------------------------------------- #


def independent_confirmations(
    candidate: Candidate,
    candidates: Mapping[str, Candidate],
    groups: Mapping[str, IndependenceGroup],
) -> tuple[str, ...]:
    """One confirming finding per independence group other than the candidate's own."""
    own = groups.get(candidate.evidence.source_ref)
    chosen: dict[str, str] = {}
    for evidence_id in sorted(candidate.confirmations):
        other = candidates.get(evidence_id)
        if other is None:
            continue
        group = groups.get(other.evidence.source_ref)
        group_id = group.group_id if group is not None else f"ref:{other.evidence.source_ref}"
        if own is not None and group_id == own.group_id:
            continue
        chosen.setdefault(group_id, evidence_id)
    return tuple(sorted(chosen.values()))


def _measures(item: EvidenceItem) -> list[dict[str, Any]]:
    return [m.model_dump(mode="json", exclude_none=True) for m in item.measures]


def verifier_item(
    candidate: Candidate,
    *,
    excerpt: str,
    trace: TraceRecord,
    related: Sequence[Candidate],
) -> dict[str, Any]:
    """What the independent verifier is shown about one candidate. No agent reasoning.

    ``related`` are other candidates from the same publisher; at most
    :data:`RELATED_LIMIT`, in evidence-id order.
    """
    item = candidate.evidence
    return {
        "evidence_id": item.evidence_id,
        "claim": item.claim,
        "quote": item.quote,
        "excerpt": excerpt,
        "measures": _measures(item),
        "source": {
            "title": item.source_title,
            "publisher": trace.publisher_name,
            "primary": trace.status.value,
            "cited": list(trace.cited),
            "date": item.source_date,
        },
        "related": [
            {
                "evidence_id": r.evidence.evidence_id,
                "claim": r.evidence.claim,
                "measures": _measures(r.evidence),
                "date": r.evidence.source_date,
            }
            for r in sorted(related, key=lambda r: r.evidence.evidence_id)[:RELATED_LIMIT]
        ],
    }


# --------------------------------------------------------------------------- #
# Applying the verdicts
# --------------------------------------------------------------------------- #


class ReviewOutcome(_Closed):
    accepted: tuple[AcceptedEvidence, ...]
    quarantined: tuple[QuarantinedEvidence, ...]
    supersessions: tuple[Supersession, ...]
    verifier_leads: tuple[VerifierLead, ...]
    conflicts: tuple[Conflict, ...]
    resolve_requests: tuple[ResolveTrackRequest, ...]


def _quarantine(item: EvidenceItem, reason: QuarantineReason, detail: str) -> QuarantinedEvidence:
    return QuarantinedEvidence(
        evidence_id=item.evidence_id,
        track_id=item.track_id,
        reason=reason,
        detail=detail[:2000],
        claim=item.claim,
        source_ref=item.source_ref,
        evidence=item,
    )


def _reason(judgement: ClaimJudgement) -> str:
    tried = ", ".join(a.value for a in judgement.attacks)
    return judgement.reason + (f" [attacks: {tried}]" if tried else "")


def _verifier_leads(
    judgements: Mapping[str, ClaimJudgement], register: ReputationRegister | None
) -> tuple[VerifierLead, ...]:
    leads = []
    for evidence_id in sorted(judgements):
        search = judgements[evidence_id].search
        if search is None:
            continue
        resolved = (
            register.resolve_publisher(search.publisher)
            if register is not None and search.publisher
            else None
        )
        leads.append(
            VerifierLead(
                lead_id="VL-" + digest([evidence_id, search.query])[:12],
                evidence_id=evidence_id,
                query=search.query,
                publisher_named=search.publisher,
                publisher=resolved.canonical_name if resolved is not None else None,
                why=search.why,
            )
        )
    return tuple(leads)


def review_candidates(
    candidates: Sequence[Candidate],
    judgements: Mapping[str, ClaimJudgement],
    *,
    groups: Mapping[str, IndependenceGroup],
    traces: Mapping[str, TraceRecord],
    published: Mapping[str, date | None],
    register: ReputationRegister | None,
    tolerance: ConflictTolerance | None = None,
) -> ReviewOutcome:
    """The verdicts applied by code (rule: module doc), in ``candidates`` order.

    ``traces`` and ``published`` are by evidence id; every candidate has a trace.
    """
    tolerance = tolerance or ConflictTolerance()
    by_id = {c.evidence.evidence_id: c for c in candidates}
    items = {k: c.evidence for k, c in by_id.items()}
    publishers = {k: traces[k].publisher for k in by_id}
    eligible = frozenset(
        k for k, j in judgements.items() if k in by_id and j.verdict is ClaimVerdict.SUPPORTED
    )
    by_code = supersessions(
        list(items.values()),
        publishers=publishers,
        published=published,
        eligible=eligible,
        tolerance=tolerance,
    )
    accepted: list[AcceptedEvidence] = []
    quarantined: list[QuarantinedEvidence] = []
    superseded: list[Supersession] = []
    for candidate in candidates:
        item = candidate.evidence
        key = item.evidence_id
        judgement = judgements.get(key)
        if judgement is None:
            quarantined.append(
                _quarantine(item, QuarantineReason.UNVERIFIED, "no verdict was returned")
            )
            continue
        if judgement.verdict is ClaimVerdict.UNSUPPORTED:
            quarantined.append(
                _quarantine(item, QuarantineReason.UNSUPPORTED_BY_VERIFIER, _reason(judgement))
            )
            continue
        if judgement.verdict is ClaimVerdict.OVERSTATED:
            quarantined.append(
                _quarantine(item, QuarantineReason.OVERSTATED_BY_VERIFIER, _reason(judgement))
            )
            continue
        if key in by_code:
            superseded.append(by_code[key])
            quarantined.append(_quarantine(item, QuarantineReason.SUPERSEDED, by_code[key].detail))
            continue
        if judgement.verdict is ClaimVerdict.SUPERSEDED:
            problem = proposed_supersession_problem(
                item,
                judgement.superseded_by,
                candidates=items,
                publishers=publishers,
                published=published,
                eligible=eligible,
                tolerance=tolerance,
            )
            if problem is not None:
                quarantined.append(
                    _quarantine(
                        item,
                        QuarantineReason.UNVERIFIED,
                        f"the verifier said superseded and code cannot accept it: {problem}",
                    )
                )
                continue
            assert judgement.superseded_by is not None
            record = Supersession(
                evidence_id=key,
                superseded_by=(judgement.superseded_by,),
                rule=SupersessionRule.VERIFIER,
                detail=f"verifier: {_reason(judgement)}"[:1000],
            )
            superseded.append(record)
            quarantined.append(_quarantine(item, QuarantineReason.SUPERSEDED, record.detail))
            continue
        confirmations = independent_confirmations(candidate, by_id, groups)
        accepted.append(
            AcceptedEvidence(
                **candidate.model_dump(
                    exclude={"evidence", "score", "confirmations", "confidence"}
                ),
                evidence=item,
                score=candidate.score,
                confirmations=confirmations,
                confidence=round(
                    min(
                        0.98,
                        candidate.score.score + CONFIRMATION_BONUS * min(2, len(confirmations)),
                    ),
                    3,
                ),
                verifier_reason=_reason(judgement),
            )
        )
    findings = [
        MeasuredFinding(
            evidence_id=a.evidence.evidence_id,
            publisher=traces[a.evidence.evidence_id].publisher,
            publisher_name=traces[a.evidence.evidence_id].publisher_name,
            primary=traces[a.evidence.evidence_id].status is PrimaryStatus.PRIMARY,
            source_url=a.evidence.source_url,
            measure=m,
        )
        for a in accepted
        for m in a.evidence.measures
    ]
    conflicts = detect_conflicts(findings, tolerance)
    return ReviewOutcome(
        accepted=tuple(accepted),
        quarantined=tuple(quarantined),
        supersessions=tuple(superseded),
        verifier_leads=_verifier_leads(
            {k: j for k, j in judgements.items() if k in by_id}, register
        ),
        conflicts=conflicts,
        resolve_requests=resolve_requests(conflicts),
    )
