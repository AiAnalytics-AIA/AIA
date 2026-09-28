"""A native research run's own artifacts -> the evidence an analysis module is judged on.

The research workflow ends its deterministic part with ``aggregate``: every question
and every tracked object of the compiled specification, weighted, donor-aware and
interval-first (:mod:`aia_core.domain.research_aggregate`). This module reads that
result, together with the specification it was computed from, and builds the three
things the evidence gate needs -- nothing more, and nothing it has to guess:

* **the evidence table.** One row per share (``pct:<answer>``), mean, top-two-box,
  valid n and effective n of each item, each with the support the unit computed
  (``donor_support``) re-assessed by AIA's own thresholds (:func:`assess_support`,
  which is at least as strict: it also needs 50 valid answers), the bootstrap
  interval, and the dataset's origin. A row is **removed, keeping only why** when its
  support is suppressed, when the unit's fidelity rule refuses the question
  (``REFUSE``: absolute willingness-to-pay or market size, ``fidelity.py``), or when an
  estimate has no interval that contains it. Every row is ``MODELED``: simulated
  answers are never measurements.
* **the field policy.** The run's instrument, declared by
  :func:`aia_core.domain.evidence.instrument_policy_book` from these items and the
  dataset's origin -- internal only, aggregate only, never measured.
* **the joint status.** A native run has no population panel, so it has no
  ``CORE_JOINT_STATUS`` certificate: :func:`load_joint_status` is asked with none and
  answers ``MISSING``, which permits nothing client-facing. That is the honest status,
  not a stand-in for one.

:func:`research_questions_of` reads the questions the analysis must answer from the
Design Revision the way the unit does (``analysis_agent._research_questions``), and
:func:`native_preflight` names every reason a module cannot run before anything is
reserved or sent.

What a run has and this does not read: the Sociomap (its map metrics are not allowed
metrics, and it is ``INTERNAL_ONLY`` while D6 is open), open-answer verbatims (synthetic
illustrations, never evidence), and any background research (Deep Research is not
integrated). Pure: no I/O.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

from ..evidence import (
    AnalysisMetric,
    ClaimBasis,
    ClaimLevel,
    ClaimSurface,
    Disclosure,
    EvidenceRow,
    EvidenceTable,
    FieldPolicyBook,
    InstrumentItem,
    Interval,
    JointStatus,
    MetricKind,
    SupportAssessment,
    SupportEvidence,
    Violation,
    ViolationCode,
    assess_support,
    instrument_field,
    instrument_policy_book,
    load_joint_status,
)
from ..fieldwork import NON_EVIDENCE_ORIGINS, DataOrigin
from ..pipeline import fingerprint
from ..research_aggregate import AGGREGATE_VERSION
from ..research_design import ResearchSpecification, SpecQuestion
from .modules import AnalysisModuleSpec

__all__ = [
    "INTERVAL_LEVEL",
    "MAX_RESEARCH_QUESTIONS",
    "NATIVE_EVIDENCE_VERSION",
    "NativeEvidence",
    "NativeEvidenceRefused",
    "native_evidence",
    "native_items",
    "native_preflight",
    "research_questions_of",
]

#: Identity of this mapping. Part of every fingerprint computed on its output.
NATIVE_EVIDENCE_VERSION: Final = "aia-native-evidence-1"

#: ``analysis_agent._research_questions``: at most eight.
MAX_RESEARCH_QUESTIONS: Final = 8

#: The aggregate's intervals are 95 % bootstrap intervals (``dotaznik.py``'s note).
INTERVAL_LEVEL: Final = 0.95

# fidelity.py evidence_rating: the mode that refuses a question as evidence.
_REFUSE: Final = "REFUSE"
_UNIT_SUPPORT: Final = frozenset({"SUPPRESS", "INDICATIVE", "REPORTABLE"})


class NativeEvidenceRefused(ValueError):
    """The run's artifacts do not describe one consistent, known computation."""


@dataclass(frozen=True, slots=True)
class NativeEvidence:
    """What every analysis module of one native run is judged against."""

    table: EvidenceTable
    book: FieldPolicyBook
    joint_status: JointStatus
    origin: DataOrigin
    #: Identity of the system the evidence was computed on: the dataset, the
    #: specification, the aggregate and this mapping, the instrument policy and the
    #: certificate. A validation state would have to be earned on exactly this.
    system_fingerprint: str
    #: How many rows the table would hold had nothing been suppressed.
    rows_considered: int


# --------------------------------------------------------------------------- #
# research questions
# --------------------------------------------------------------------------- #


def _texts(raw: object) -> list[str]:
    if not isinstance(raw, list | tuple):
        return []
    return [x.strip() for x in raw if isinstance(x, str) and x.strip()]


def research_questions_of(design: Mapping[str, Any]) -> tuple[str, ...]:
    """The questions an analysis answers, as the unit reads them from a design.

    ``research_plan.research_questions``, else ``research_plan.objectives``, else the
    ``goal``, at most eight (``analysis_agent.py`` ``_research_questions``). Two
    readings are this port's, both stricter: only a list of strings counts (the unit
    iterated a string character by character), and an exact repeat is dropped.
    """
    plan = design.get("research_plan")
    plan = plan if isinstance(plan, Mapping) else {}
    questions = _texts(plan.get("research_questions"))
    if not questions:
        questions = _texts(plan.get("objectives"))
    goal = design.get("goal")
    if not questions and isinstance(goal, str) and goal.strip():
        questions = [goal.strip()]
    return tuple(dict.fromkeys(questions))[:MAX_RESEARCH_QUESTIONS]


# --------------------------------------------------------------------------- #
# the instrument and its aggregate
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _Item:
    question: SpecQuestion
    result: Mapping[str, Any]


def native_items(spec: ResearchSpecification) -> tuple[InstrumentItem, ...]:
    """Every item the specification asks: its questions, then each tracked object."""
    items = [InstrumentItem(q.id, q.text) for q in spec.questions]
    for b in spec.batteries:
        for o in b.objects:
            items.append(
                InstrumentItem(b.question_id(o), b.question_template.replace("{object}", o.label))
            )
    return tuple(items)


def _battery_questions(spec: ResearchSpecification) -> list[tuple[str, SpecQuestion]]:
    out: list[tuple[str, SpecQuestion]] = []
    for b in spec.batteries:
        for o in b.objects:
            out.append(
                (
                    b.id,
                    SpecQuestion(
                        id=b.question_id(o),
                        section_id=b.id,
                        text=b.question_template.replace("{object}", o.label),
                        typ="skala",
                        scale=b.scale,
                    ),
                )
            )
    return out


def _results(spec: ResearchSpecification, aggregate: Mapping[str, Any]) -> list[_Item]:
    """Pair every item of ``spec`` with its aggregate, refusing anything that does not match."""
    if aggregate.get("aggregate_version") != AGGREGATE_VERSION:
        raise NativeEvidenceRefused(
            f"the aggregate was computed by {aggregate.get('aggregate_version')!r}; "
            f"this mapping reads {AGGREGATE_VERSION!r}"
        )
    questions = aggregate.get("questions")
    batteries = aggregate.get("batteries")
    if not isinstance(questions, Mapping) or not isinstance(batteries, Mapping):
        raise NativeEvidenceRefused("the aggregate has no questions or batteries")
    asked = {q.id for q in spec.questions}
    if set(questions) != asked:
        raise NativeEvidenceRefused(
            f"the aggregate answers {sorted(set(questions) ^ asked)} differently from the "
            "specification it names"
        )
    items = [_Item(q, questions[q.id]) for q in spec.questions]
    if set(batteries) != {b.id for b in spec.batteries}:
        raise NativeEvidenceRefused("the aggregate's tracked sets are not the specification's")
    for battery_id, question in _battery_questions(spec):
        objects = (
            batteries[battery_id].get("objects")
            if isinstance(batteries[battery_id], Mapping)
            else None
        )
        object_id = question.id.removeprefix(f"{battery_id}_obj_")
        result = objects.get(object_id) if isinstance(objects, Mapping) else None
        if not isinstance(result, Mapping):
            raise NativeEvidenceRefused(f"the aggregate has no result for {question.id!r}")
        items.append(_Item(question, result))
    for item in items:
        if not isinstance(item.result, Mapping) or item.result.get("typ") != item.question.typ:
            raise NativeEvidenceRefused(f"{item.question.id}: the aggregate is of another type")
    return items


# --------------------------------------------------------------------------- #
# rows
# --------------------------------------------------------------------------- #


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _support(result: Mapping[str, Any]) -> SupportAssessment:
    """The unit's donor support, re-assessed by AIA's thresholds. Unknown suppresses."""
    unit = result.get("support_status")
    if unit not in _UNIT_SUPPORT:
        return SupportAssessment(reasons=(f"unknown support status {unit!r}",))
    assessed = assess_support(
        SupportEvidence(
            n=_integer(result.get("n_platnych")),
            effective_n=_number(result.get("effective_n")),
            requires_donor_support=True,
            n_unique_layer_donors=_integer(result.get("n_unique_layer_donors")),
        )
    )
    if unit == "SUPPRESS" and assessed.reportable:
        # Cannot happen with the unit's own thresholds; if it ever does, the stricter wins.
        return SupportAssessment(reasons=("the unit suppressed this cell",))
    return assessed


def _fidelity_refusal(result: Mapping[str, Any]) -> str | None:
    rating = result.get("evidence")
    if not isinstance(rating, Mapping):
        return "the aggregate carries no fidelity rating"
    if rating.get("mode") == _REFUSE:
        return f"fidelity {rating.get('rating')}: {rating.get('reason')}"
    return None


def _interval(raw: object, value: float) -> Interval | str:
    """The row's 95 % interval, or why it has none it could be reported with."""
    if not isinstance(raw, Mapping):
        return "the estimate has no interval"
    low, high = _number(raw.get("low")), _number(raw.get("high"))
    if low is None or high is None or low > high:
        return "the estimate's interval is malformed"
    if not low <= value <= high:
        return f"the estimate {value:g} lies outside its interval [{low:g}, {high:g}]"
    return Interval(low, high, INTERVAL_LEVEL)


@dataclass
class _Rows:
    kept: list[EvidenceRow]
    removed: dict[str, SupportAssessment]
    origin: DataOrigin

    def add(
        self,
        item: _Item,
        suffix: str,
        metric: AnalysisMetric,
        value: object,
        decimals: int,
        detail: str,
        *,
        support: SupportAssessment,
        interval: object = None,
        refusal: str | None = None,
    ) -> None:
        ref = f"{item.question.id}.{suffix}"
        if ref in self.removed or any(r.evidence_ref == ref for r in self.kept):
            raise NativeEvidenceRefused(f"evidence_ref {ref!r} would appear twice")
        why: list[str] = [refusal] if refusal else []
        number = _number(value)
        if number is None:
            why.append("no estimate")
        elif round(number, decimals) != number:
            why.append(f"the estimate {number!r} is not rounded to {decimals} decimals")
        bounds: Interval | None = None
        estimate = metric.kind not in (MetricKind.N, MetricKind.EFFECTIVE_N)
        if number is not None and estimate:
            checked = _interval(interval, number)
            if isinstance(checked, str):
                why.append(checked)
            else:
                bounds = checked
        if not support.reportable:
            why.extend(support.reasons)
        if why or number is None:
            self.removed[ref] = SupportAssessment(
                reasons=tuple(why), effective_n=support.effective_n
            )
            return
        self.kept.append(
            EvidenceRow(
                evidence_ref=ref,
                metric=metric,
                value=number,
                decimals=decimals,
                support=support,
                fields=(instrument_field(item.question.id),),
                basis=ClaimBasis.MODELED,
                level=ClaimLevel.AGGREGATE,
                cell=f"{item.question.text} | {detail}",
                question_id=item.question.id,
                interval=bounds,
                disclosures=frozenset({Disclosure.MODELED_VALUE}),
                data_origin=self.origin,
            )
        )


def _scale(q: SpecQuestion) -> str:
    return f"{q.scale[0]}-{q.scale[1]}" if q.scale else "?"


def _item_rows(rows: _Rows, item: _Item) -> None:
    q, r = item.question, item.result
    support = _support(r)
    refusal = _fidelity_refusal(r)
    rows.add(
        item,
        "n",
        AnalysisMetric(MetricKind.N),
        r.get("n_platnych"),
        0,
        "platné odpovědi",
        support=support,
        refusal=refusal,
    )
    rows.add(
        item,
        "effective_n",
        AnalysisMetric(MetricKind.EFFECTIVE_N),
        r.get("effective_n"),
        1,
        "efektivní n",
        support=support,
        refusal=refusal,
    )
    if q.typ in ("vyber", "multi"):
        shares = r.get("celkem_pct")
        intervals = r.get("intervaly_95")
        shares = shares if isinstance(shares, Mapping) else {}
        intervals = intervals if isinstance(intervals, Mapping) else {}
        for index, option in enumerate(q.options, start=1):
            rows.add(
                item,
                f"pct.{index}",
                AnalysisMetric(MetricKind.PCT, option),
                shares.get(option),
                1,
                f"odpověď: {option}",
                support=support,
                interval=intervals.get(option),
                refusal=refusal,
            )
    elif q.typ == "skala":
        rows.add(
            item,
            "mean",
            AnalysisMetric(MetricKind.MEAN),
            r.get("prumer"),
            2,
            f"průměr, škála {_scale(q)}",
            support=support,
            interval=r.get("prumer_interval_95"),
            refusal=refusal,
        )
        rows.add(
            item,
            "top2box",
            AnalysisMetric(MetricKind.TOP2BOX_PCT),
            r.get("top2box_pct"),
            1,
            f"podíl dvou nejvyšších bodů, škála {_scale(q)}",
            support=support,
            interval=r.get("top2box_interval_95"),
            refusal=refusal,
        )


def native_evidence(
    spec: ResearchSpecification,
    aggregate: Mapping[str, Any],
    *,
    dataset_sha256: str,
    origin: DataOrigin | None,
) -> NativeEvidence:
    """Build the evidence of one native run from its specification and aggregate.

    ``origin`` is the fieldwork dataset's, as the dataset artifact records it; the
    aggregate must say the same. Raises :class:`NativeEvidenceRefused` when the two
    artifacts do not describe one computation this mapping knows, and
    :class:`~aia_core.domain.evidence.InstrumentPolicyRefused` when the answers' origin
    has no instrument policy.
    """
    if aggregate.get("data_origin") != (origin.value if origin else None):
        raise NativeEvidenceRefused(
            f"the aggregate's data origin {aggregate.get('data_origin')!r} is not the "
            f"dataset's {origin.value if origin else None!r}"
        )
    if len(dataset_sha256) != 64:
        raise NativeEvidenceRefused("the fieldwork dataset is identified by its SHA-256")
    book = instrument_policy_book(
        native_items(spec),
        origin=origin,
        source=f"fieldwork dataset {dataset_sha256} ({origin.value if origin else '?'})",
    )
    assert origin is not None  # the book refuses an unknown origin
    rows = _Rows(kept=[], removed={}, origin=origin)
    for item in _results(spec, aggregate):
        _item_rows(rows, item)
    built = EvidenceTable.build(rows.kept)
    table = EvidenceTable(
        rows=built.rows, suppressed=MappingProxyType({**built.suppressed, **rows.removed})
    )
    joint = load_joint_status(None, measured_panel_sha256=None)
    return NativeEvidence(
        table=table,
        book=book,
        joint_status=joint,
        origin=origin,
        system_fingerprint=fingerprint(
            {
                "kind": "native_research_run",
                "evidence": NATIVE_EVIDENCE_VERSION,
                "aggregate": aggregate.get("aggregate_version"),
                "bootstrap": aggregate.get("bootstrap_generator"),
                "dataset_sha256": dataset_sha256,
                "specification": spec.fingerprint(),
                "instrument_policy": book.source_sha256,
                "joint_status": joint.fingerprint(),
            }
        ),
        rows_considered=len(table.rows) + len(table.suppressed),
    )


# --------------------------------------------------------------------------- #
# preflight
# --------------------------------------------------------------------------- #


def native_preflight(
    spec: AnalysisModuleSpec,
    evidence: NativeEvidence,
    *,
    surface: ClaimSurface,
    research_questions: Sequence[str],
) -> tuple[Violation, ...]:
    """Every reason this module cannot run, known before anything is reserved or sent.

    Empty means it may run; the evidence gate still judges every draft. Nothing here
    is softened later: a module refused here is ``BLOCKED`` with these violations.
    """
    found: list[Violation] = []
    if surface is ClaimSurface.CLIENT_FACING:
        if evidence.origin in NON_EVIDENCE_ORIGINS:
            found.append(
                Violation(
                    ViolationCode.SYNTHETIC_DATA_ORIGIN,
                    "preflight",
                    f"the respondents are simulated ({evidence.origin.value}); nothing from "
                    "them is a client-facing finding",
                )
            )
        found.append(
            Violation(
                ViolationCode.FIELD_INTERNAL_ONLY,
                "preflight",
                "the study instrument's evidence policy is internal only (decision ANL-1)",
            )
        )
        if not evidence.joint_status.certified:
            joint = evidence.joint_status
            found.append(
                Violation(
                    ViolationCode.JOINT_CERTIFICATE_DEGRADED,
                    "preflight",
                    f"{joint.degradation}: {joint.detail}; no client claim can be admitted",
                )
            )
    if not evidence.table.rows:
        found.append(
            Violation(
                ViolationCode.SUPPORT_SUPPRESSED,
                "preflight",
                f"no citable evidence: all {evidence.rows_considered} rows were removed "
                "(thin support, a refused question, or an estimate without its interval)",
            )
        )
    if spec.answers_research_questions and not research_questions:
        found.append(
            Violation(
                ViolationCode.RESEARCH_QUESTION_UNANSWERED,
                "preflight",
                "the design states no research question (research_plan.research_questions, "
                "objectives or goal)",
            )
        )
    return tuple(found)
