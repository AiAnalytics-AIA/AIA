"""The agent-directed brief: findings with confidence, conflicts, gaps, and the prose's numbers.

Plan ``deep-research-web-search.md`` § 8.8, chunk 13. The brief is written per research
objective from accepted findings only. Code builds every part it can
(:func:`brief_material`): each accepted finding with its full measures, source,
publisher, tier, primary or secondary, verifier's reason and **confidence computed by
code** (:mod:`.confidence`); each conflict with both sides and its cause
(:mod:`.triangulation`); the gaps and acquisition gaps (:mod:`.gaps`). The synthesizer
(:mod:`.synthesizer`) writes only the prose around them, and :func:`check_brief`
decides what of it may be published, saying why when the answer is no:

* an **answer** must name a subject of the run (``unknown_subject``), cite only
  accepted findings (``citation_not_accepted``), and state no number that is not in
  the quote or a measure of a finding it cites (``number_not_in_cited_evidence``);
* a **conflict note** must name a conflict code found (``unknown_conflict``) and state
  only the numbers of the conflict's two sides (``number_not_in_cited_evidence``);
* a **limitation** cites nothing, so it may state no number at all
  (``number_without_citation``);
* the **summary** may state only the numbers of the findings the published answers
  cite; otherwise it is withheld.

A number is *in* a finding when it is a number of its quote, a measure's value (or
the value times its scale), or a year of a measure's period; the rounding the prose
shows is allowed, and a range or bound the subject itself names (``18-29``) is a
name, not a number (``analysis.draft.uncovered_numbers``). A record id in prose is a
citation and its digits are not numbers. That is the analysis modules' rule, the
planned synthesis's "write only its quotes' numbers", widened to the measures the
investigator stated and code checked.

**Repair once, then refuse.** The executor sends a draft that failed back once, with
every problem; what still fails is excluded with its reason, never rewritten. With
accepted findings and no answer left, the brief is ``BLOCKED``.

Every number the brief prints therefore cites an evidence id: the prose's through its
answers' citations, a finding's claim and measures through the finding itself, and a
gap's text, which cites nothing, keeps only years (:func:`~.gaps.only_years`).
:func:`uncited_numbers` walks the whole brief and says where one does not.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..analysis.draft import numbers_in, uncovered_numbers
from .confidence import (
    CONFIDENCE_RULES_VERSION,
    ConfidenceRecord,
    ConfidenceWeights,
    Provenance,
    confidence,
    confidence_inputs,
    evidence_tier,
)
from .contracts import Measure, QuarantinedEvidence, ResearchSubject
from .gaps import (
    GAPS_VERSION,
    AcquisitionGap,
    LeadSource,
    ResearchGap,
    TrackFacts,
    acquisition_gaps,
    conflict_gaps,
    only_years,
    research_gaps,
    strip_ids,
)
from .measures import render_measure
from .merge import AcceptedEvidence, RespondentUse
from .reputation import ReputationRegister
from .sources import SourceTable, SourceTier
from .synthesis import ExcludedFinding, PublishedFinding, SynthesisCheck, SynthesisStatus
from .synthesizer import BRIEF_CONTRACT_VERSION, BRIEF_PROMPT_VERSION, BriefProposal
from .tracing import TraceRecord
from .triangulation import Conflict, period_span
from .verification import VerificationReview
from .verifier import ClaimVerdict

__all__ = [
    "BRIEF_VERSION",
    "BriefAnswer",
    "BriefCheck",
    "BriefConflict",
    "BriefExclusion",
    "BriefFinding",
    "BriefMaterial",
    "BriefRepair",
    "ResearchBrief",
    "brief_material",
    "brief_payload",
    "check_brief",
    "research_brief",
    "synthesis_check",
    "uncited_numbers",
]

#: The brief's rules: this module, the contract, the prompt, the confidence and gap rules.
BRIEF_VERSION: Final = (
    f"aia-dr-brief-1/{BRIEF_CONTRACT_VERSION}/prompt-{BRIEF_PROMPT_VERSION}"
    f"/{CONFIDENCE_RULES_VERSION}/{GAPS_VERSION}"
)


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --------------------------------------------------------------------------- #
# What code builds
# --------------------------------------------------------------------------- #


class BriefFinding(_Closed):
    """One accepted finding as the brief prints it: everything about it is code's."""

    evidence_id: str
    subject_key: str
    claim: str
    quote: str
    measures: tuple[Measure, ...]
    #: Each measure as one Czech phrase (``render_measure``), or None where none reads.
    measures_text: tuple[str | None, ...]
    source_title: str
    source_url: str | None
    publisher: str
    tier: SourceTier
    provenance: Provenance
    traced_to: str | None
    confidence: ConfidenceRecord
    verifier_reason: str
    respondent_use: RespondentUse


class BriefConflict(_Closed):
    """A conflict code found, both sides and cause, with the synthesizer's note if it held."""

    conflict: Conflict
    note: str | None
    #: Why a note was refused, when one was written and refused.
    note_refused: str | None


class BriefMaterial(_Closed):
    """Everything code builds for a brief before a model writes a word of it."""

    findings: tuple[BriefFinding, ...]
    conflicts: tuple[Conflict, ...]
    gaps: tuple[ResearchGap, ...]
    acquisition_gaps: tuple[AcquisitionGap, ...]
    weights: ConfidenceWeights

    def by_id(self) -> dict[str, BriefFinding]:
        return {f.evidence_id: f for f in self.findings}


def brief_material(
    accepted: Sequence[AcceptedEvidence],
    *,
    quarantined: Sequence[QuarantinedEvidence],
    review: VerificationReview | None,
    subjects: Sequence[ResearchSubject],
    tracks: Sequence[TrackFacts],
    read: Mapping[str, date | None],
    table: SourceTable,
    register: ReputationRegister | None,
    weights: ConfidenceWeights,
) -> BriefMaterial:
    """The brief's findings, conflicts, gaps and acquisition gaps, by code.

    ``read`` is, by evidence id, the date the finding's source was read. A finding
    accepted in the agent-directed mode was judged ``supported`` and is not
    superseded (anything else is quarantined), and those are its inputs.
    """
    traces: dict[str, TraceRecord] = (
        {t.evidence_id: t for t in review.traces} if review is not None else {}
    )
    conflicts = review.conflicts if review is not None else ()
    superseded = {s.evidence_id for s in review.supersessions} if review is not None else set()
    findings = []
    for a in accepted:
        item = a.evidence
        trace = traces.get(item.evidence_id)
        inputs = confidence_inputs(
            item,
            tier=evidence_tier(
                item, source_class=a.score.source_class, table=table, register=register
            ),
            trace=trace,
            confirmation_groups=len(a.confirmations),
            verdict=ClaimVerdict.SUPPORTED,
            superseded=item.evidence_id in superseded,
            conflicts=conflicts,
            read=read.get(item.evidence_id),
            weights=weights,
        )
        findings.append(
            BriefFinding(
                evidence_id=item.evidence_id,
                subject_key=item.subject_key,
                claim=item.claim,
                quote=item.quote,
                measures=item.measures,
                measures_text=tuple(render_measure(m) for m in item.measures),
                source_title=item.source_title,
                source_url=item.source_url,
                publisher=trace.publisher_name if trace is not None else item.source_ref,
                tier=inputs.tier,
                provenance=inputs.provenance,
                traced_to=trace.traced_to if trace is not None else None,
                confidence=confidence(item.evidence_id, inputs, weights),
                verifier_reason=a.verifier_reason,
                respondent_use=a.respondent_use,
            )
        )
    answered = frozenset(a.evidence.subject_key for a in accepted)
    # A lead may name a finding the verifier quarantined; it still names its subject.
    subjects_of = {
        q.evidence.evidence_id: q.evidence.subject_key for q in quarantined if q.evidence
    }
    subjects_of |= {a.evidence.evidence_id: a.evidence.subject_key for a in accepted}
    leads = LeadSource(
        primary=review.primary_leads if review is not None else (),
        verifier=review.verifier_leads if review is not None else (),
        subjects=subjects_of,
    )
    return BriefMaterial(
        findings=tuple(findings),
        conflicts=tuple(conflicts),
        gaps=(
            *research_gaps(subjects, tracks, answered=answered),
            *conflict_gaps(conflicts),
        ),
        acquisition_gaps=acquisition_gaps(tracks, leads, register=register),
        weights=weights,
    )


def _written(value: float) -> str:
    """A value as Czech prose writes it: a decimal comma, never an exponent."""
    if float(value).is_integer() and abs(value) < 1e15:
        return str(int(value))
    return repr(float(value)).replace(".", ",")


def brief_payload(
    material: BriefMaterial, subjects: Sequence[ResearchSubject]
) -> dict[str, object]:
    """What the brief synthesizer is shown: code's parts, confidence as a band only.

    No agent's own rating is in it, and no confidence number to copy.
    """
    return {
        "subjects": [
            {"subject_key": s.key, "kind": s.kind.value, "text": s.text} for s in subjects
        ],
        "findings": [
            {
                "evidence_id": f.evidence_id,
                "subject_key": f.subject_key,
                "claim": f.claim,
                "quote": f.quote,
                "measures": [t for t in f.measures_text if t is not None],
                "source_title": f.source_title,
                "publisher": f.publisher,
                "tier": f.tier.value,
                "primary": f.provenance.value,
                "confidence": f.confidence.band.value,
            }
            for f in material.findings
        ],
        "conflicts": [
            {
                "conflict_id": c.conflict_id,
                "measure_name": c.measure_name,
                "cause": c.cause.value,
                "status": c.status.value,
                "sides": [
                    {
                        "evidence_id": s.evidence_id,
                        "value": _written(s.measure.value),
                        "unit": s.measure.unit,
                        "period": s.measure.period,
                        "publisher": s.publisher_name,
                    }
                    for s in c.sides
                ],
            }
            for c in material.conflicts
        ],
        "gaps": [
            {"kind": g.kind.value, "subject_key": g.subject_key, "need": g.need, "reason": g.reason}
            for g in material.gaps
        ],
        "acquisition_gaps": [
            {"publisher": g.publisher, "title": g.title, "reason": g.reason.value}
            for g in material.acquisition_gaps
        ],
    }


# --------------------------------------------------------------------------- #
# What the synthesizer wrote, checked
# --------------------------------------------------------------------------- #


def _backing(ids: Iterable[str], findings: Mapping[str, BriefFinding]) -> list[float]:
    """Every number the findings ``ids`` name stand behind (module doc)."""
    values: list[float] = []
    for i in ids:
        f = findings.get(i)
        if f is None:
            continue
        values += [v for v, _ in numbers_in(f.quote)]
        for m in f.measures:
            values += [m.value, m.value * m.scale]
            span = period_span(m.period)
            if span is not None:
                values += [float(span.start // 12), float(span.end // 12)]
    return [v for v in values if math.isfinite(v)]


def _uncovered(
    text: str, ids: Iterable[str], findings: Mapping[str, BriefFinding], names: Sequence[str]
) -> tuple[float, ...]:
    return uncovered_numbers(strip_ids(text), _backing(ids, findings), names)


def _shown(numbers: Sequence[float]) -> str:
    return ", ".join(f"{n:g}" for n in numbers)


class BriefAnswer(_Closed):
    subject_key: str
    text: str
    evidence_ids: tuple[str, ...]


class BriefExclusion(_Closed):
    """A part of the synthesizer's prose that may not be published, and why."""

    where: str
    subject_key: str | None
    text: str
    reason: str
    detail: str = Field(max_length=2000)


class BriefCheck(_Closed):
    """One draft checked: what may be published, and every refusal with its reason."""

    summary: str | None
    summary_withheld: str | None
    answers: tuple[BriefAnswer, ...]
    notes: dict[str, str]
    refused_notes: dict[str, str]
    limitations: tuple[str, ...]
    excluded: tuple[BriefExclusion, ...]

    @property
    def problems(self) -> tuple[BriefExclusion, ...]:
        """Everything a repair would have to fix: exclusions, and a withheld summary."""
        withheld = (
            (
                BriefExclusion(
                    where="summary",
                    subject_key=None,
                    text="",
                    reason="summary_withheld",
                    detail=self.summary_withheld,
                ),
            )
            if self.summary_withheld
            else ()
        )
        return (*self.excluded, *withheld)


def check_brief(
    proposal: BriefProposal,
    *,
    material: BriefMaterial,
    subjects: Mapping[str, ResearchSubject],
) -> BriefCheck:
    """Check the synthesizer's prose against the material it was given (module doc)."""
    findings = material.by_id()
    conflicts = {c.conflict_id: c for c in material.conflicts}
    names = [s.text for s in subjects.values()]
    answers: list[BriefAnswer] = []
    excluded: list[BriefExclusion] = []

    def refuse(where: str, subject: str | None, text: str, reason: str, detail: str) -> None:
        excluded.append(
            BriefExclusion(
                where=where, subject_key=subject, text=text, reason=reason, detail=detail[:2000]
            )
        )

    for index, answer in enumerate(proposal.answers):
        where = f"answers[{index}]"
        subject = subjects.get(answer.subject_key)
        if subject is None:
            refuse(
                where,
                answer.subject_key,
                answer.text,
                "unknown_subject",
                f"{answer.subject_key!r} is not a subject of this run",
            )
            continue
        foreign = [i for i in answer.evidence_ids if i not in findings]
        if foreign:
            refuse(
                where,
                subject.key,
                answer.text,
                "citation_not_accepted",
                "cites no accepted finding: " + ", ".join(foreign),
            )
            continue
        missing = _uncovered(answer.text, answer.evidence_ids, findings, [subject.text])
        if missing:
            refuse(
                where,
                subject.key,
                answer.text,
                "number_not_in_cited_evidence",
                f"{_shown(missing)} is in no quote or measure this answer cites",
            )
            continue
        answers.append(
            BriefAnswer(
                subject_key=subject.key,
                text=answer.text,
                evidence_ids=tuple(dict.fromkeys(answer.evidence_ids)),
            )
        )

    notes: dict[str, str] = {}
    refused_notes: dict[str, str] = {}
    for index, note in enumerate(proposal.conflict_notes):
        where = f"conflict_notes[{index}]"
        conflict = conflicts.get(note.conflict_id)
        if conflict is None:
            refuse(
                where,
                None,
                note.text,
                "unknown_conflict",
                f"{note.conflict_id!r} is not a conflict of this run",
            )
            continue
        missing = _uncovered(
            note.text, [s.evidence_id for s in conflict.sides], findings, [conflict.measure_name]
        )
        if missing:
            refuse(
                where,
                None,
                note.text,
                "number_not_in_cited_evidence",
                f"{_shown(missing)} is the number of neither side of {conflict.conflict_id}",
            )
            refused_notes.setdefault(conflict.conflict_id, f"{_shown(missing)} is uncited")
            continue
        notes.setdefault(conflict.conflict_id, note.text)

    limitations: list[str] = []
    for index, line in enumerate(proposal.limitations):
        missing = _uncovered(line, (), findings, names)
        if missing:
            refuse(
                f"limitations[{index}]",
                None,
                line,
                "number_without_citation",
                f"{_shown(missing)} is stated where nothing is cited",
            )
            continue
        limitations.append(line)

    cited = [i for a in answers for i in a.evidence_ids]
    summary_missing = _uncovered(proposal.summary, cited, findings, names)
    withheld = (
        f"the summary states {_shown(summary_missing)}, which no published answer's findings carry"
        if summary_missing
        else None
    )
    return BriefCheck(
        summary=None if withheld else proposal.summary,
        summary_withheld=withheld,
        answers=tuple(answers),
        notes=notes,
        refused_notes={k: v for k, v in refused_notes.items() if k not in notes},
        limitations=tuple(limitations),
        excluded=tuple(excluded),
    )


# --------------------------------------------------------------------------- #
# The brief
# --------------------------------------------------------------------------- #


class BriefRepair(_Closed):
    """The one repair a draft got: what was wrong with the first, and how it ended."""

    problems: tuple[BriefExclusion, ...]
    #: Why the repair was not requested (``gate:reason``); the first draft's refusals stand.
    refused: str | None


class ResearchBrief(_Closed):
    """The agent-directed brief: per objective, every finding, conflict and gap, by code."""

    kind: Literal["deep_research_brief"]
    version: str
    status: SynthesisStatus
    summary: str | None
    summary_withheld: str | None
    answers: tuple[BriefAnswer, ...]
    findings: tuple[BriefFinding, ...]
    conflicts: tuple[BriefConflict, ...]
    gaps: tuple[ResearchGap, ...]
    acquisition_gaps: tuple[AcquisitionGap, ...]
    limitations: tuple[str, ...]
    #: What the synthesizer wrote that may not be published, after the repair.
    excluded: tuple[BriefExclusion, ...]
    #: The repair, when the first draft needed one.
    repair: BriefRepair | None
    weights: ConfidenceWeights


def _status(material: BriefMaterial, check: BriefCheck | None) -> SynthesisStatus:
    if not material.findings:
        return SynthesisStatus.EMPTY
    if check is None or not check.answers:
        return SynthesisStatus.BLOCKED
    if check.problems:
        return SynthesisStatus.PARTIAL
    return SynthesisStatus.COMPLETE


def research_brief(
    material: BriefMaterial,
    check: BriefCheck | None,
    *,
    repair: BriefRepair | None,
    withheld: str | None = None,
) -> ResearchBrief:
    """The brief from code's material and the checked prose (``None``: none was written).

    ``withheld`` says why no prose was written, when none was (the gate's refusal).
    """
    return ResearchBrief(
        kind="deep_research_brief",
        version=BRIEF_VERSION,
        status=_status(material, check),
        summary=check.summary if check is not None else None,
        summary_withheld=check.summary_withheld if check is not None else withheld,
        answers=check.answers if check is not None else (),
        findings=material.findings,
        conflicts=tuple(
            BriefConflict(
                conflict=c,
                note=check.notes.get(c.conflict_id) if check is not None else None,
                note_refused=check.refused_notes.get(c.conflict_id) if check is not None else None,
            )
            for c in material.conflicts
        ),
        gaps=material.gaps,
        acquisition_gaps=material.acquisition_gaps,
        limitations=check.limitations if check is not None else (),
        excluded=check.excluded if check is not None else (),
        repair=repair,
        weights=material.weights,
    )


def synthesis_check(brief: ResearchBrief) -> SynthesisCheck:
    """The brief in the planned mode's shape, for every reader of a synthesis.

    Answers are its findings, the answers' exclusions its excluded findings (by their
    index in the draft), every gap a gap line.
    """
    excluded = [
        ExcludedFinding(
            index=int(e.where.removeprefix("answers[").removesuffix("]")),
            subject_key=e.subject_key or "",
            text=e.text,
            reason=e.reason,
            detail=e.detail,
        )
        for e in brief.excluded
        if e.where.startswith("answers[")
    ]
    return SynthesisCheck(
        status=brief.status,
        summary=brief.summary,
        summary_withheld=brief.summary_withheld,
        findings=tuple(
            PublishedFinding(subject_key=a.subject_key, text=a.text, evidence_ids=a.evidence_ids)
            for a in brief.answers
        ),
        excluded=tuple(excluded),
        gaps=tuple(f"{g.need} -- {g.reason}" for g in brief.gaps),
        limitations=brief.limitations,
    )


def uncited_numbers(
    brief: ResearchBrief, subjects: Sequence[ResearchSubject]
) -> tuple[tuple[str, float], ...]:
    """Every number the brief prints that cites no evidence id, with where it is.

    Empty for every brief :func:`research_brief` builds. Answers by their citations;
    the summary by the published answers' citations; conflict notes by their sides;
    each finding's claim and measures by the finding itself; limitations, gaps and
    acquisition gaps cite nothing, so only years (a gap's period) may stand there.
    """
    findings = {f.evidence_id: f for f in brief.findings}
    names = [s.text for s in subjects]
    found: list[tuple[str, float]] = []

    def check(where: str, text: str | None, ids: Iterable[str], extra: Sequence[str] = ()) -> None:
        if text:
            found.extend(
                (where, n) for n in _uncovered(text, list(ids), findings, [*names, *extra])
            )

    for i, a in enumerate(brief.answers):
        check(f"answers[{i}]", a.text, a.evidence_ids)
    check("summary", brief.summary, [i for a in brief.answers for i in a.evidence_ids])
    for c in brief.conflicts:
        check(
            f"conflict {c.conflict.conflict_id}",
            c.note,
            [s.evidence_id for s in c.conflict.sides],
            [c.conflict.measure_name],
        )
    for f in brief.findings:
        check(f"finding {f.evidence_id}", f.claim, [f.evidence_id])
        for t in f.measures_text:
            check(f"finding {f.evidence_id} measure", t, [f.evidence_id])
    for i, line in enumerate(brief.limitations):
        check(f"limitations[{i}]", line, ())
    for g in brief.gaps:
        for text in (g.need, g.reason, g.tried):
            if text and not only_years(text, names):
                found.extend((f"gap {g.gap_id}", n) for n, _ in numbers_in(strip_ids(text)))
    for q in brief.acquisition_gaps:
        for text in (q.title, q.how_to_obtain):
            if not only_years(text, names):
                where = f"acquisition gap {q.gap_id}"
                found.extend((where, n) for n, _ in numbers_in(strip_ids(text)))
    return tuple(found)
