"""A run's results as Výsledky shows them: admitted rows only (evidence-integrity 6).

The screen read the raw aggregate artifact and decided in the browser what to hide, so a
suppressed number reached the page and was only not drawn. Here the run's evidence table is
built from its verified sources exactly as its analysis builds it (``sources_evidence``), and
each question's numbers are admitted for the internal surface through the report's own rule
(:func:`~aia_core.application.report_tables.admit_question`). A number leaves only as an
:class:`~aia_core.domain.evidence.AdmittedClaim`; a suppressed row arrives with the codes of its
reasons, whose words carry the very numbers withheld, and a question the gate refuses arrives
with the gate's violation codes. Nothing here computes a number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from sqlalchemy.orm import Session

from aia_core.application.analysis_results import (
    SourcesRefused,
    native_sources,
    sources_evidence,
)
from aia_core.application.report_tables import admit_question
from aia_core.application.research import ResearchRuns
from aia_core.domain.analysis.native import native_items, ref_metric
from aia_core.domain.evidence import ClaimSurface
from aia_core.domain.evidence.support import Interval
from aia_core.domain.fieldwork import DataOrigin
from aia_core.domain.scope import Permission, StudyContext
from aia_core.infrastructure.storage import ArtifactStore

#: Why a row was suppressed, by the words its producers write (``evidence/support.py``
#: ``_decide``, ``analysis/native.py`` ``_Rows.add``, ``_interval``, ``_fidelity_refusal`` and
#: ``reassess_support``): the code alone leaves the API, since the words name the withheld estimate,
#: its interval, n and effective n. Words no pattern knows read ``other``, never their text.
_REASON_CODES: Final = (
    (re.compile(r"^support unknown"), "support_unknown"),
    (re.compile(r"inconsistent support$"), "support_inconsistent"),
    (re.compile(r"^n \S+ < min_cell "), "below_min_cell"),
    (re.compile(r"^effective n \S+ < "), "below_effective_n"),
    (re.compile(r"^donor-layer support unknown$"), "donor_support_unknown"),
    (re.compile(r"^\S+ unique layer donors < "), "below_layer_donors"),
    (re.compile(r"^no estimate$"), "no_estimate"),
    (re.compile(r"^the estimate \S+ is not rounded to "), "not_rounded"),
    (re.compile(r"^the estimate has no interval$"), "no_interval"),
    (re.compile(r"^the estimate's interval is malformed$"), "interval_malformed"),
    (re.compile(r"^the estimate \S+ lies outside its interval "), "outside_interval"),
    (re.compile(r"^the aggregate carries no fidelity rating$"), "no_fidelity_rating"),
    (re.compile(r"^fidelity "), "fidelity_refused"),
    (re.compile(r"^the unit suppressed this cell$"), "unit_suppressed"),
    (re.compile(r"^unknown support status "), "support_status_unknown"),
)


def reason_codes(reasons: tuple[str, ...]) -> tuple[str, ...]:
    """Each reason's code, in order, once."""
    codes: list[str] = []
    for reason in reasons:
        code = next((c for pattern, c in _REASON_CODES if pattern.search(reason)), "other")
        if code not in codes:
            codes.append(code)
    return tuple(codes)


@dataclass(frozen=True, slots=True)
class ResultRow:
    """One row of a question: an admitted number, or a suppressed ref with why and no number."""

    evidence_ref: str
    #: The metric's kind (``pct``, ``mean``, ``top2box_pct``, ``n``, ``effective_n``) and, for a
    #: share, the exact answer it is the share of; ``None`` for a ref this system does not mint.
    metric: str | None
    answer: str | None
    value: float | None = None
    decimals: int | None = None
    interval: Interval | None = None
    #: The row's support: ``REPORTABLE`` or ``INDICATIVE`` with a number, ``SUPPRESS`` without;
    #: ``None`` in a question the gate refused, whose rows were never judged one by one.
    support: str | None = None
    effective_n: float | None = None
    #: Why a suppressed row has no number, as codes (:func:`reason_codes`); empty otherwise.
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class QuestionResult:
    question_id: str
    text: str
    rows: tuple[ResultRow, ...]
    #: The gate's violation codes when it refused the question's numbers; its rows carry none.
    refused: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AdmittedResults:
    run_id: str
    data_origin: DataOrigin | None
    questions: tuple[QuestionResult, ...]


def admitted_results(
    session: Session, scope: StudyContext, store: ArtifactStore, *, run_id: str
) -> AdmittedResults:
    """``run_id``'s admitted rows, question by question in the specification's order.

    Needs ``VIEW_RESULTS``. Raises
    :class:`~aia_core.application.research.ResearchRunNotFound` for a run not in the Study, and
    :class:`~aia_core.application.analysis_results.SourcesRefused` while the run has no verified
    aggregate, or (``evidence_refused``) when its sources make no evidence table.
    """
    scope.require(Permission.VIEW_RESULTS)
    run = ResearchRuns(session, scope).get(run_id)
    # The data alone: what the analysis was shown as context is not a result.
    sources = native_sources(session, scope, store, run, with_context=False)
    try:
        evidence = sources_evidence(sources)
    except ValueError as exc:
        # Every refusal of the evidence build is one: NativeEvidenceRefused,
        # InstrumentPolicyRefused, UnsupportedEstimate. Its words can name a number, so they stay
        # on the chained cause, out of the answer.
        raise SourcesRefused(
            "evidence_refused", "the run's sources make no evidence table"
        ) from exc
    table = evidence.table
    options = {q.id: q.options for q in sources.specification.questions}
    questions: list[QuestionResult] = []
    for item in native_items(sources.specification):
        qid = item.question_id
        refs, admission = admit_question(
            table,
            qid,
            book=evidence.book,
            joint_status=evidence.joint_status,
            surface=ClaimSurface.INTERNAL,
        )
        if not refs:
            continue
        admitted = {claim.row.evidence_ref: claim for claim in admission.admitted}
        rows: list[ResultRow] = []
        for ref in refs:
            claim = admitted.get(ref)
            if claim is not None:
                row = claim.row
                rows.append(
                    ResultRow(
                        evidence_ref=ref,
                        metric=row.metric.kind.value,
                        answer=row.metric.answer,
                        value=claim.value,
                        decimals=row.decimals,
                        interval=row.interval,
                        support=row.support.status.value,
                        effective_n=row.support.effective_n,
                    )
                )
                continue
            # A suppressed row keeps only its ref and its reasons (EvidenceTable); a row of a
            # refused question is named by its ref alike, judged not alone but with its question.
            metric = ref_metric(ref.removeprefix(f"{qid}."), options.get(qid, ()))
            suppressed = table.suppressed.get(ref)
            rows.append(
                ResultRow(
                    evidence_ref=ref,
                    metric=metric.kind.value if metric else None,
                    answer=metric.answer if metric else None,
                    support="SUPPRESS" if suppressed is not None else None,
                    reasons=reason_codes(suppressed.reasons) if suppressed is not None else (),
                )
            )
        questions.append(
            QuestionResult(
                question_id=qid,
                text=item.text,
                rows=tuple(rows),
                refused=tuple(dict.fromkeys(v.code.value for v in admission.decision.violations)),
            )
        )
    return AdmittedResults(
        run_id=run_id, data_origin=sources.dataset_origin, questions=tuple(questions)
    )
