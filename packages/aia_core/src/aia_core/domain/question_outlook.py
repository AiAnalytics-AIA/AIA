"""Before a run: which of its questions it will answer, question by question.

The support forecast (:mod:`.support_forecast`) says whether a run's numbers will be shown
at all. A design can pass it and still pay for questions that come back empty, for
reasons that are just as certain before launch, and the Run screen named none of them.
The unit's fidelity rule refuses a question about absolute willingness to pay or market
size (``fidelity.py``, :func:`~.research_aggregate.evidence_rating`), and the analysis
gate removes every row of a refused question (``analysis/native.py``). An open question's
answers are synthetic illustrations, never evidence. A conditional question, or a tracked
set that requires familiarity, cannot be asked at all.

:func:`question_outlook` gives every item a respondent will answer (each question, and
each object of each tracked set) one verdict and every reason behind it, decided by the
same rules that decide after the run:

* **UNANSWERABLE**: the run cannot ask it, or nothing it returns can be cited.
* **AT_RISK**: it returns something, but less than a finding: indicative support, or
  illustrations only.
* **UNKNOWN**: support is decided only at fieldwork (a population-drawn run, or a source
  with no forecast). Unknown is never answerable.
* **ANSWERABLE**: none of the above. That is still an upper bound: a respondent who
  leaves the answer empty lowers its support.

The worst verdict wins. Reasons are codes the screen puts into words; nothing here
renders a sentence. Pure: no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from .evidence import SupportStatus
from .research_aggregate import evidence_rating
from .research_design import ResearchSpecification
from .support_forecast import SupportForecast

__all__ = [
    "OutlookReason",
    "QuestionOutlook",
    "Verdict",
    "question_outlook",
]


class Verdict(StrEnum):
    ANSWERABLE = "ANSWERABLE"
    UNKNOWN = "UNKNOWN"
    AT_RISK = "AT_RISK"
    UNANSWERABLE = "UNANSWERABLE"


class OutlookReason(StrEnum):
    #: A conditional question (``filtr``): AIA asks every respondent every question.
    CONDITIONAL = "conditional"
    #: A tracked set that requires familiarity with its objects: AIA cannot ask it.
    FAMILIARITY = "familiarity"
    #: The fidelity rule refuses it (absolute willingness to pay, market size).
    FIDELITY_REFUSED = "fidelity_refused"
    #: An open question: its answers are shown as illustrations, the analysis cites none.
    OPEN_ENDED = "open_ended"
    #: The forecast support suppresses its numbers for the analysis.
    SUPPORT_SUPPRESSED = "support_suppressed"
    #: The forecast support makes its numbers indicative.
    SUPPORT_INDICATIVE = "support_indicative"
    #: Support is decided only at fieldwork.
    SUPPORT_UNKNOWN = "support_unknown"


_VERDICT: Final[dict[OutlookReason, Verdict]] = {
    OutlookReason.CONDITIONAL: Verdict.UNANSWERABLE,
    OutlookReason.FAMILIARITY: Verdict.UNANSWERABLE,
    OutlookReason.FIDELITY_REFUSED: Verdict.UNANSWERABLE,
    OutlookReason.SUPPORT_SUPPRESSED: Verdict.UNANSWERABLE,
    OutlookReason.OPEN_ENDED: Verdict.AT_RISK,
    OutlookReason.SUPPORT_INDICATIVE: Verdict.AT_RISK,
    OutlookReason.SUPPORT_UNKNOWN: Verdict.UNKNOWN,
}

_RANK: Final = {v: i for i, v in enumerate(Verdict)}


@dataclass(frozen=True, slots=True)
class QuestionOutlook:
    """One item a respondent will answer, as the respondent reads it.

    ``battery_id`` is the tracked set an object's rating belongs to (``None`` for a
    question); ``text`` is the wording fieldwork asks, an object's with its label in it.
    """

    question_id: str
    text: str
    section_id: str
    battery_id: str | None
    verdict: Verdict
    reasons: tuple[OutlookReason, ...]


def _support_reason(forecast: SupportForecast | None) -> OutlookReason | None:
    if forecast is None or forecast.analysis is None:
        return OutlookReason.SUPPORT_UNKNOWN
    if forecast.analysis is SupportStatus.SUPPRESS:
        return OutlookReason.SUPPORT_SUPPRESSED
    if forecast.analysis is SupportStatus.INDICATIVE:
        return OutlookReason.SUPPORT_INDICATIVE
    return None


def _outlook(
    question_id: str,
    text: str,
    section_id: str,
    battery_id: str | None,
    reasons: list[OutlookReason],
) -> QuestionOutlook:
    verdict = max((_VERDICT[r] for r in reasons), key=_RANK.__getitem__, default=Verdict.ANSWERABLE)
    return QuestionOutlook(
        question_id=question_id,
        text=text,
        section_id=section_id,
        battery_id=battery_id,
        verdict=verdict,
        reasons=tuple(reasons),
    )


def question_outlook(
    spec: ResearchSpecification, forecast: SupportForecast | None
) -> tuple[QuestionOutlook, ...]:
    """Every item of ``spec`` with its verdict, in questionnaire order (questions, then each
    tracked set's objects). ``forecast`` ``None``: no forecast was made, so support is
    unknown for every item."""
    support = _support_reason(forecast)
    out: list[QuestionOutlook] = []
    for q in spec.questions:
        reasons: list[OutlookReason] = []
        if q.has_filter:
            reasons.append(OutlookReason.CONDITIONAL)
        # The aggregate's own rating, at the validation status every AIA run has: the mode
        # (REFUSE or not) does not depend on it.
        if evidence_rating(q.text, q.typ, validation_status="")["mode"] == "REFUSE":
            reasons.append(OutlookReason.FIDELITY_REFUSED)
        if q.typ == "otevrena":
            reasons.append(OutlookReason.OPEN_ENDED)
        if support is not None:
            reasons.append(support)
        out.append(_outlook(q.id, q.text, q.section_id, None, reasons))
    for b in spec.batteries:
        for o in b.objects:
            text = b.question_template.replace("{object}", o.label)
            reasons = []
            if b.familiarity_required:
                reasons.append(OutlookReason.FAMILIARITY)
            if evidence_rating(text, "skala", validation_status="")["mode"] == "REFUSE":
                reasons.append(OutlookReason.FIDELITY_REFUSED)
            if support is not None:
                reasons.append(support)
            out.append(_outlook(b.question_id(o), text, b.id, b.id, reasons))
    return tuple(out)
