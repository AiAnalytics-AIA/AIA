"""Accuracy on a truth set: what a run's accepted findings got right, decided by code.

Plan ``deep-research-web-search.md`` chunk 25 (§ 8). Given a pinned truth set
(:mod:`.truth_set`) and one or more runs, it measures per preset: exact-value
accuracy with the right unit, period and geography; the primary-source rate; the
share grounded to a table cell; false acceptances (a wrong number accepted); gaps
and acquisition gaps -- and compares them with the owner's *proposed* targets
without changing them.

**The input** is a :class:`RunRecord`: what scoring needs of a run, whatever shape
produced it -- the question each subject asked, the accepted findings with their
measures, source, grounding kind and (when the run traced it) provenance, and the
acquisition gaps when the run reports them. :func:`run_from_bundle` builds one from
a sealed :class:`~.bundle.EvidenceBundle` as it exists today. That bundle carries no
provenance, no cell locator and no acquisition gap (the agent-directed brief and
the ladder that add them are separate chunks): the record says so
(``reports_provenance``, ``reports_acquisition_gaps`` false) and the report then
says *not measured*, never zero. A brief-shaped adapter is a function beside this
one, producing the same record.

**A finding is on a fact** when its subject's text is the fact's question
(:func:`~.contracts.normalise_label`): a truth-set run asks each fact as one
subject. A fact whose question no subject of the run asked is *not asked*, and
counts against exact accuracy like an unanswered one.

**A measure answers a fact** when its finding is on the fact, the measure names
*what* the fact measures, and nothing it states contradicts the fact. Each
attribute is, against the expected figure: ``match`` (the same key -- or both
absent), ``contradict`` (both stated and different; or the fact has none and the
finding states one: a household share is a different figure from a price index),
or ``unstated`` (the finding states none, or states one the vocabulary cannot
read). *What* is measured is the unit (``%`` and ``p. b.`` are different units),
the population and the denominator: all three must ``match``, so a bare number
("k 31. 12.", "4,1" with no unit) answers nothing. *When* and *where* -- the period
(compared as the months it covers, :func:`~.triangulation.period_span`) and the
geography -- may be ``unstated`` and the measure still answers; stated and
different, it does not (a 2090 figure is not the 2091 one, Prague is not the
country). The scale is not an attribute: it is part of the value, so "450 tis."
and "450 000" are one number and "450" is another.

Of an answering measure, the **value** is:

* ``exact`` -- the scaled values are equal (or within an absolute tolerance the
  fact states);
* ``rounded`` -- not exact, but the expected figure rounds to it at the finding's
  own, coarser precision ("10,5 mil." for 10 450 tis.): a coarser statement, not a
  wrong one;
* ``wrong`` -- anything else.

A **false acceptance** is an answering measure whose value is ``wrong``: an
accepted finding that, on the fact's question and not contradicting what is
measured, gives a different number. A finding that names what is measured but
leaves the period or place unstated still answers: an accepted number with no
period that differs from the truth is a wrong number accepted (CLAUDE.md § 8:
unknown is never scored as good).
A measure is **exact** only when it answers, its value is exact and every
attribute matches: an unstated period is not the right period.

Known limit, stated rather than hidden: two figures of one subject with the same
unit, population, place and period -- a level and its change -- are one identity
to code. A change stated as such ("vzrostl o 12 tis. obyvatel") has the level's
attributes, and a finding citing it is scored as a false acceptance. The report
lists every false acceptance with its claim, so a person can see it.

**Per fact**: answered (some measure answers), exact (some measure is exact),
primary-source used (an answering finding was captured from the fact's primary
publisher: its URL's host belongs to that publisher in the truth set's register,
:func:`~.triangulation.publisher_identity` -- code decides, whatever the run
said), cell-grounded (an answering finding is grounded to a table cell), the
false acceptances, gap (asked and not answered) and the acquisition gaps naming
the fact's publisher. **Per run and per preset** (pooled): exact accuracy over
every fact of the set; primary-source rate and cell-grounded share over answered
facts (``None`` when none was answered); false acceptances; gaps; acquisition gaps
(``None`` when no run of the preset reports them).

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .bundle import EvidenceBundle
from .contracts import Measure, normalise_label
from .datasets import parse_locator
from .measures import GEOGRAPHY, PERCENTAGE_POINTS, POPULATIONS, UNITS, claim_measures
from .measures import normalised_measure as _vocabulary_measure
from .reputation import ReputationRegister, normalise_name
from .triangulation import period_span, publisher_identity, register_key
from .truth_set import ToleranceKind, TruthFact, TruthSet, TruthSetPins, admit_truth_set

__all__ = [
    "ACCURACY_REPORT_VERSION",
    "ACCURACY_RULES_VERSION",
    "PROPOSED_TARGETS",
    "RUN_RECORD_VERSION",
    "AccuracyReport",
    "AcquisitionGapRecord",
    "AttributeCheck",
    "BundleRefused",
    "FactScore",
    "GroundingKind",
    "MeasureMatch",
    "Metrics",
    "Provenance",
    "RunFinding",
    "RunRecord",
    "RunScore",
    "Target",
    "TargetCheck",
    "TargetStatus",
    "TruthSetIdentity",
    "ValueVerdict",
    "accuracy_report",
    "render_summary",
    "run_from_bundle",
    "score_run",
]

ACCURACY_RULES_VERSION: Final = "aia-dr-accuracy-1"
ACCURACY_REPORT_VERSION: Final = "aia-dr-accuracy-report-1"
RUN_RECORD_VERSION: Final = "aia-dr-accuracy-run-1"

_UNIT_KEYS: Final = frozenset(UNITS) | {PERCENTAGE_POINTS}
_POPULATION_KEYS: Final = frozenset(POPULATIONS)
_GEOGRAPHY_KEYS: Final = frozenset(GEOGRAPHY)
#: The attributes that say what is measured: an answer must match all three.
_WHAT: Final = ("unit", "population", "denominator")


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --------------------------------------------------------------------------- #
# The run, as scoring reads it
# --------------------------------------------------------------------------- #


class GroundingKind(StrEnum):
    #: A quote of running text.
    TEXT = "text"
    #: A cell of a dataset snapshot (``<dataset>!<row>/<column>``).
    DATASET_CELL = "dataset_cell"
    #: A cell of a document's table (``Sheet!B4``, a PDF table's row and column).
    DOCUMENT_CELL = "document_cell"


class Provenance(StrEnum):
    """What the run itself said of a finding's source (tracing, § 8.3)."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    UNDETERMINED = "undetermined"


class RunFinding(_Closed):
    """One accepted finding: what it says, what its numbers mean, and where it rests."""

    evidence_id: str = Field(min_length=1, max_length=100)
    subject_key: str = Field(min_length=1, max_length=100)
    claim: str = Field(min_length=1, max_length=1200)
    quote: str = Field(min_length=1, max_length=800)
    source_ref: str = Field(min_length=1, max_length=300)
    source_url: str | None = Field(max_length=2048)
    measures: tuple[Measure, ...]
    #: ``stated`` by the agent, or ``read`` from the claim by code (planned mode).
    measures_from: Literal["stated", "read"]
    grounding: GroundingKind
    cell_locator: str | None = Field(default=None, max_length=500)
    provenance: Provenance | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _cell(self) -> RunFinding:
        if (self.grounding is GroundingKind.TEXT) != (self.cell_locator is None):
            raise ValueError(f"{self.evidence_id}: a cell finding names its cell, a text one none")
        return self


class AcquisitionGapRecord(_Closed):
    """A source the run needed and could not lawfully reach (the ladder's gap)."""

    gap_id: str = Field(min_length=1, max_length=100)
    #: A register key (``register:…``) or the publisher's name as the run gave it.
    publisher: str | None = Field(max_length=300)
    title: str = Field(max_length=500)
    reason: str = Field(max_length=300)


class RunRecord(_Closed):
    """What scoring needs of one run. JSON form: ``kind`` ``deep_research_accuracy_run``."""

    kind: Literal["deep_research_accuracy_run"]
    version: Literal["aia-dr-accuracy-run-1"]
    run_id: str = Field(min_length=1, max_length=200)
    preset: str = Field(min_length=1, max_length=40)
    #: Where its evidence came from (``LIVE_RETRIEVAL``, ``RECORDED_FIXTURE``…).
    origins: tuple[str, ...]
    fictional_client: bool
    #: Every subject the run asked, by key: its text.
    subjects: dict[str, str]
    findings: tuple[RunFinding, ...]
    reports_provenance: bool
    reports_acquisition_gaps: bool
    acquisition_gaps: tuple[AcquisitionGapRecord, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> RunRecord:
        for f in self.findings:
            if f.subject_key not in self.subjects:
                raise ValueError(f"{f.evidence_id}: subject {f.subject_key} is not the run's")
            if f.provenance is not None and not self.reports_provenance:
                raise ValueError(f"{f.evidence_id}: provenance in a run that reports none")
        if self.acquisition_gaps and not self.reports_acquisition_gaps:
            raise ValueError("acquisition gaps in a run that reports none")
        ids = [f.evidence_id for f in self.findings]
        if len(set(ids)) != len(ids):
            raise ValueError("an evidence id is listed twice")
        return self


class BundleRefused(ValueError):
    """A bundle that cannot be scored: its seal does not hold."""


def _quote_cell(quote: str) -> str | None:
    """The locator a dataset cell's line begins with (``[<locator>] …``), or None."""
    text = quote.strip()
    if not text.startswith("["):
        return None
    inner, close, _ = text[1:].partition("]")
    if not close or parse_locator(inner) is None:
        return None
    return inner


def run_from_bundle(bundle: EvidenceBundle) -> RunRecord:
    """A sealed bundle's accepted findings as a :class:`RunRecord`.

    The bundle has no trace records, cell locators or acquisition gaps: provenance
    and acquisition gaps are reported as *not reported*; a finding is a dataset cell
    when its quote is a cell's line with its locator (what a dataset snapshot's
    rendering writes), otherwise text -- so a document table's cell is counted as
    text and the cell-grounded share is a lower bound on this shape. A finding with
    no stated measures (the planned mode) has its claim read by code.
    """
    if not bundle.verify():
        raise BundleRefused("the bundle does not hash to its seal; it was changed after sealing")
    findings: list[RunFinding] = []
    for accepted in bundle.accepted:
        item = accepted.evidence
        cell = _quote_cell(item.quote)
        stated = bool(item.measures)
        findings.append(
            RunFinding(
                evidence_id=item.evidence_id,
                subject_key=item.subject_key,
                claim=item.claim,
                quote=item.quote,
                source_ref=item.source_ref,
                source_url=item.source_url,
                measures=item.measures if stated else claim_measures(item.claim),
                measures_from="stated" if stated else "read",
                grounding=GroundingKind.TEXT if cell is None else GroundingKind.DATASET_CELL,
                cell_locator=cell,
                provenance=None,
                confidence=accepted.confidence,
            )
        )
    return RunRecord(
        kind="deep_research_accuracy_run",
        version="aia-dr-accuracy-run-1",
        run_id="bundle:" + bundle.sha256[:16],
        preset=bundle.preset,
        origins=tuple(o.value for o in bundle.origins),
        fictional_client=bundle.fictional_client,
        subjects={s.key: s.text for s in bundle.subjects},
        findings=tuple(findings),
        reports_provenance=False,
        reports_acquisition_gaps=False,
    )


# --------------------------------------------------------------------------- #
# One measure against one fact
# --------------------------------------------------------------------------- #


class AttributeCheck(StrEnum):
    MATCH = "match"
    CONTRADICT = "contradict"
    UNSTATED = "unstated"


class ValueVerdict(StrEnum):
    EXACT = "exact"
    ROUNDED = "rounded"
    WRONG = "wrong"


class MeasureMatch(_Closed):
    """One measure of an on-fact finding, judged against the fact."""

    evidence_id: str
    measure: Measure
    attributes: dict[str, AttributeCheck]
    answers: bool
    value: ValueVerdict | None
    exact: bool
    false_acceptance: bool
    publisher: str
    from_primary_publisher: bool
    grounding: GroundingKind
    cell_locator: str | None
    run_provenance: Provenance | None
    claim: str


def _decimals(value: float) -> int:
    if float(value).is_integer():
        return 0
    text = repr(float(value))
    if "e" in text or "E" in text:
        return 6
    return min(6, len(text.split(".", 1)[1]))


def _key(raw: str | None, read: str | None, known: frozenset[str]) -> str | None:
    """A stated attribute in the vocabulary's key: as written when it is one, else as read."""
    if raw is not None and raw in known:
        return raw
    return read


def _normalised(measure: Measure) -> tuple[Measure, set[str]]:
    """The measure in vocabulary keys, and the attributes stated but not readable."""
    read = _vocabulary_measure(measure)
    unit = _key(measure.unit, read.unit, _UNIT_KEYS)
    population = _key(measure.population, read.population, _POPULATION_KEYS)
    denominator = _key(measure.denominator, read.denominator, _UNIT_KEYS | _POPULATION_KEYS)
    geography = _key(measure.geography, read.geography, _GEOGRAPHY_KEYS)
    period = measure.period if period_span(measure.period) is not None else read.period
    out = Measure(
        value=measure.value,
        scale=measure.scale,
        unit=unit,
        population=population,
        denominator=denominator,
        geography=geography,
        period=period,
        measure_name=measure.measure_name,
        basis=measure.basis,
    )
    unreadable = {
        name
        for name, stated, key in (
            ("unit", measure.unit, unit),
            ("population", measure.population, population),
            ("denominator", measure.denominator, denominator),
            ("geography", measure.geography, geography),
        )
        if stated is not None and key is None
    }
    if measure.period is not None and period_span(period) is None:
        unreadable.add("period")
    return out, unreadable


def _check(expected: str | None, found: str | None, unreadable: bool) -> AttributeCheck:
    if unreadable:
        return AttributeCheck.UNSTATED
    if found is None:
        return AttributeCheck.MATCH if expected is None else AttributeCheck.UNSTATED
    return AttributeCheck.MATCH if found == expected else AttributeCheck.CONTRADICT


def _period_check(expected: str | None, found: str | None, unreadable: bool) -> AttributeCheck:
    """As :func:`_check`, with periods compared as the months they cover."""
    if unreadable:
        return AttributeCheck.UNSTATED
    if found is None:
        return AttributeCheck.MATCH if expected is None else AttributeCheck.UNSTATED
    if expected is None:
        return AttributeCheck.CONTRADICT
    a, b = period_span(expected), period_span(found)
    if a is None or b is None:
        return AttributeCheck.UNSTATED
    return AttributeCheck.MATCH if a == b else AttributeCheck.CONTRADICT


def _value(fact: TruthFact, measure: Measure) -> ValueVerdict:
    expected = fact.expected
    assert expected.value is not None  # admitted sets are scorable
    want = expected.value * expected.scale
    got = measure.value * measure.scale
    allowed = fact.tolerance.allowed(expected.scale)
    if abs(got - want) <= allowed + 1e-9 * max(1.0, abs(want)):
        return ValueVerdict.EXACT
    step_found = 10.0 ** -_decimals(measure.value) * measure.scale
    step_expected = 10.0**-expected.decimals * expected.scale
    if (
        fact.tolerance.kind is ToleranceKind.EXACT
        and step_found > step_expected
        and abs(got - want) <= 0.5 * step_found + 1e-9 * max(1.0, abs(want))
    ):
        return ValueVerdict.ROUNDED
    return ValueVerdict.WRONG


def _judge(
    fact: TruthFact, finding: RunFinding, measure: Measure, register: ReputationRegister
) -> MeasureMatch:
    found, unreadable = _normalised(measure)
    e = fact.expected
    attributes = {
        "unit": _check(e.unit, found.unit, "unit" in unreadable),
        "population": _check(e.population, found.population, "population" in unreadable),
        "denominator": _check(e.denominator, found.denominator, "denominator" in unreadable),
        "geography": _check(e.geography, found.geography, "geography" in unreadable),
        "period": _period_check(e.period, found.period, "period" in unreadable),
    }
    answers = AttributeCheck.CONTRADICT not in attributes.values() and all(
        attributes[name] is AttributeCheck.MATCH for name in _WHAT
    )
    value = _value(fact, found) if answers else None
    identity = publisher_identity(
        url=finding.source_url, source_ref=finding.source_ref, register=register
    )
    return MeasureMatch(
        evidence_id=finding.evidence_id,
        measure=found,
        attributes=attributes,
        answers=answers,
        value=value,
        exact=answers
        and value is ValueVerdict.EXACT
        and all(a is AttributeCheck.MATCH for a in attributes.values()),
        false_acceptance=answers and value is ValueVerdict.WRONG,
        publisher=identity.key,
        from_primary_publisher=identity.key == fact.primary.publisher,
        grounding=finding.grounding,
        cell_locator=finding.cell_locator,
        run_provenance=finding.provenance,
        claim=finding.claim,
    )


# --------------------------------------------------------------------------- #
# Facts, runs, presets
# --------------------------------------------------------------------------- #


class FactScore(_Closed):
    fact_id: str
    topic: str
    subject_key: str | None
    asked: bool
    answered: bool
    exact: bool
    primary_used: bool
    cell_grounded: bool
    false_acceptances: tuple[str, ...]
    gap: bool
    acquisition_gaps: tuple[str, ...]
    #: Every measure of every on-fact finding: the answering ones and the near misses.
    measures: tuple[MeasureMatch, ...]


class Metrics(_Closed):
    facts: int
    asked: int
    answered: int
    exact: int
    exact_accuracy: float
    primary_answered: int
    primary_source_rate: float | None
    cell_grounded_answered: int
    cell_grounded_share: float | None
    false_acceptances: int
    gaps: int
    not_asked: int
    #: None when no run counted here reports acquisition gaps: not measured, not zero.
    acquisition_gaps: int | None


class RunScore(_Closed):
    run_id: str
    preset: str
    origins: tuple[str, ...]
    fictional_client: bool
    reports_provenance: bool
    reports_acquisition_gaps: bool
    facts: tuple[FactScore, ...]
    metrics: Metrics


def _publisher_names(key: str, register: ReputationRegister) -> frozenset[str]:
    for p in register.publishers:
        if register_key(p) == key:
            return frozenset({key, *(normalise_name(n) for n in p.all_names)})
    return frozenset({key})


def _score_fact(
    fact: TruthFact, run: RunRecord, by_question: Mapping[str, str], register: ReputationRegister
) -> FactScore:
    assert fact.question is not None
    subject = by_question.get(normalise_label(fact.question))
    matches = tuple(
        _judge(fact, finding, measure, register)
        for finding in run.findings
        if subject is not None and finding.subject_key == subject
        for measure in finding.measures
    )
    answering = [m for m in matches if m.answers]
    names = _publisher_names(fact.primary.publisher, register)
    gaps = tuple(
        g.gap_id
        for g in run.acquisition_gaps
        if g.publisher is not None
        and (g.publisher in names or normalise_name(g.publisher) in names)
    )
    return FactScore(
        fact_id=fact.fact_id,
        topic=fact.topic.value,
        subject_key=subject,
        asked=subject is not None,
        answered=bool(answering),
        exact=any(m.exact for m in matches),
        primary_used=any(m.from_primary_publisher for m in answering),
        cell_grounded=any(m.grounding is not GroundingKind.TEXT for m in answering),
        false_acceptances=tuple(
            dict.fromkeys(m.evidence_id for m in matches if m.false_acceptance)
        ),
        gap=subject is not None and not answering,
        acquisition_gaps=gaps,
        measures=matches,
    )


def _metrics(facts: Sequence[FactScore], acquisition_gaps: int | None) -> Metrics:
    answered = [f for f in facts if f.answered]
    exact = sum(f.exact for f in facts)
    primary = sum(f.primary_used for f in answered)
    cells = sum(f.cell_grounded for f in answered)
    return Metrics(
        facts=len(facts),
        asked=sum(f.asked for f in facts),
        answered=len(answered),
        exact=exact,
        exact_accuracy=exact / len(facts) if facts else 0.0,
        primary_answered=primary,
        primary_source_rate=primary / len(answered) if answered else None,
        cell_grounded_answered=cells,
        cell_grounded_share=cells / len(answered) if answered else None,
        false_acceptances=sum(len(f.false_acceptances) for f in facts),
        gaps=sum(f.gap for f in facts),
        not_asked=sum(not f.asked for f in facts),
        acquisition_gaps=acquisition_gaps,
    )


def score_run(truth: TruthSet, run: RunRecord) -> RunScore:
    """Score one run against a truth set. Admission (:func:`accuracy_report`) is separate."""
    register = truth.register()
    by_question: dict[str, str] = {}
    for key, text in sorted(run.subjects.items()):
        by_question.setdefault(normalise_label(text), key)
    facts = tuple(_score_fact(f, run, by_question, register) for f in truth.facts)
    gaps = len(run.acquisition_gaps) if run.reports_acquisition_gaps else None
    return RunScore(
        run_id=run.run_id,
        preset=run.preset,
        origins=run.origins,
        fictional_client=run.fictional_client,
        reports_provenance=run.reports_provenance,
        reports_acquisition_gaps=run.reports_acquisition_gaps,
        facts=facts,
        metrics=_metrics(facts, gaps),
    )


# --------------------------------------------------------------------------- #
# Targets and the report
# --------------------------------------------------------------------------- #


class Target(_Closed):
    """One proposed target: a metric, a bound, and the presets it applies to."""

    target_id: str
    metric: Literal["false_acceptances", "exact_accuracy"]
    comparison: Literal["at_most", "at_least"]
    bound: float
    #: None: every preset scored.
    preset: str | None
    text: str


#: The owner's proposed targets (plan chunk 25), unchanged by any measurement.
PROPOSED_TARGETS: Final = (
    Target(
        target_id="zero-false-acceptances",
        metric="false_acceptances",
        comparison="at_most",
        bound=0,
        preset=None,
        text="zero false acceptances",
    ),
    Target(
        target_id="exact-accuracy-deep",
        metric="exact_accuracy",
        comparison="at_least",
        bound=0.9,
        preset="DEEP",
        text="at least 90 % exact accuracy at Deep",
    ),
)


class TargetStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_MEASURED = "not_measured"


class TargetCheck(_Closed):
    target_id: str
    preset: str | None
    text: str
    measured: float | None
    status: TargetStatus


class TruthSetIdentity(_Closed):
    set_id: str
    sha256: str
    fictional: bool
    facts: int
    unverified_allowed: bool


class AccuracyReport(_Closed):
    kind: Literal["deep_research_accuracy_report"]
    version: Literal["aia-dr-accuracy-report-1"]
    rules_version: str
    truth_set: TruthSetIdentity
    runs: tuple[RunScore, ...]
    presets: dict[str, Metrics]
    targets_status: Literal["proposed"]
    targets: tuple[TargetCheck, ...]


def _pooled(runs: Sequence[RunScore]) -> Metrics:
    facts = [f for r in runs for f in r.facts]
    reported = [r.metrics.acquisition_gaps for r in runs if r.reports_acquisition_gaps]
    gaps = sum(g or 0 for g in reported) if reported else None
    return _metrics(facts, gaps)


def _check_target(target: Target, presets: Mapping[str, Metrics]) -> Iterable[TargetCheck]:
    names = sorted(presets) if target.preset is None else [target.preset]
    for name in names:
        metrics = presets.get(name)
        measured = None if metrics is None else float(getattr(metrics, target.metric))
        if measured is None:
            status = TargetStatus.NOT_MEASURED
        elif target.comparison == "at_most":
            status = TargetStatus.PASS if measured <= target.bound else TargetStatus.FAIL
        else:
            status = TargetStatus.PASS if measured >= target.bound else TargetStatus.FAIL
        yield TargetCheck(
            target_id=target.target_id,
            preset=name,
            text=target.text,
            measured=measured,
            status=status,
        )


def accuracy_report(
    truth: TruthSet,
    pins: TruthSetPins,
    runs: Sequence[RunRecord],
    *,
    allow_unverified: bool,
) -> AccuracyReport:
    """Admit the truth set (pinned, verified), score every run, pool per preset, compare.

    Raises :class:`~.truth_set.TruthSetRefused` before anything is scored when the
    set may not be.
    """
    admit_truth_set(truth, pins, allow_unverified=allow_unverified)
    scores = tuple(score_run(truth, r) for r in runs)
    by_preset: dict[str, list[RunScore]] = {}
    for s in scores:
        by_preset.setdefault(s.preset, []).append(s)
    presets = {name: _pooled(group) for name, group in sorted(by_preset.items())}
    checks = tuple(c for t in PROPOSED_TARGETS for c in _check_target(t, presets))
    return AccuracyReport(
        kind="deep_research_accuracy_report",
        version="aia-dr-accuracy-report-1",
        rules_version=ACCURACY_RULES_VERSION,
        truth_set=TruthSetIdentity(
            set_id=truth.set_id,
            sha256=truth.sha256(),
            fictional=truth.fictional,
            facts=len(truth.facts),
            unverified_allowed=allow_unverified,
        ),
        runs=scores,
        presets=presets,
        targets_status="proposed",
        targets=checks,
    )


def _pct(value: float | None) -> str:
    return "not measured" if value is None else f"{100 * value:.1f} %"


def render_summary(report: AccuracyReport) -> str:
    """The report in a few lines a person reads; the JSON is the record."""
    t = report.truth_set
    lines = [
        f"Truth set {t.set_id} ({t.facts} facts, sha256 {t.sha256[:12]})"
        + (" -- FICTIONAL" if t.fictional else "")
        + (" -- unverified facts allowed" if t.unverified_allowed else ""),
    ]
    for name, m in report.presets.items():
        runs = [r for r in report.runs if r.preset == name]
        origins = sorted({o for r in runs for o in r.origins})
        lines.append(
            f"{name}: {len(runs)} run(s), origins {', '.join(origins) or 'none'}\n"
            f"  exact {m.exact}/{m.facts} ({_pct(m.exact_accuracy)}); answered {m.answered}; "
            f"not asked {m.not_asked}\n"
            f"  primary source {_pct(m.primary_source_rate)}; "
            f"cell-grounded {_pct(m.cell_grounded_share)}\n"
            f"  false acceptances {m.false_acceptances}; gaps {m.gaps}; acquisition gaps "
            + ("not reported" if m.acquisition_gaps is None else str(m.acquisition_gaps))
        )
    for r in report.runs:
        for f in r.facts:
            for judged in f.measures:
                if judged.false_acceptance:
                    lines.append(
                        f"  FALSE ACCEPTANCE {r.run_id} {f.fact_id} {judged.evidence_id}: "
                        f"{judged.claim}"
                    )
    lines.append("Targets (proposed, unchanged):")
    for c in report.targets:
        measured = "-" if c.measured is None else f"{c.measured:g}"
        lines.append(f"  [{c.status.value}] {c.text} @ {c.preset}: {measured}")
    return "\n".join(lines)
