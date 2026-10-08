"""How often the independent verifier is wrong, measured on a gold set (plan chunk 48).

The verifier (:mod:`.verifier`) decides what is accepted: code applies its verdict
(:mod:`.verification`), so a verdict the verifier gets wrong becomes a wrong finding
accepted or a good one set aside. Its two error rates are therefore the ones a reader
of a brief needs, and until measured they are unknown -- which this module says, in
every run's versions, as :data:`VERIFIER_CALIBRATION` (``NOT_CALIBRATED``).

**The gold set** (:class:`GoldSet`) is fictional rows, each exactly what the verifier
is shown of one candidate (:meth:`GoldItem.shown` has the shape of
:func:`~.verification.verifier_item`) with the verdict a person decided it deserves:
``supported``, ``overstated``, ``unsupported`` or ``superseded``. Fictional, because a
gold row's verdict must be beyond dispute and no client's or real publisher's words
belong in a fixture. Fixed by its hash (:meth:`GoldSet.sha256`) before any answers are
scored, so a score cannot be improved by editing the answers' key afterwards.

**The answers** (:class:`VerifierAnswers`) are one verifier's judgements over the whole
set, for this prompt and this contract, and say how they were produced: ``RECORDED``
(scripted, in a test or a fixture) or ``LIVE`` (a model, through the gateway, named).

**The rates**, as code applies a verdict:

* a **miss** is a bad row (expected anything but ``supported``) judged ``supported``:
  a wrong finding accepted. Its rate is over the bad rows.
* a **false alarm** is a good row (expected ``supported``) judged anything else, or
  not judged at all (code sets an unjudged candidate aside as ``unverified``): a good
  finding lost. Its rate is over the good rows.
* a bad row set aside under another verdict than expected (``unsupported`` for an
  ``overstated`` claim) is neither: it is not accepted. It counts against the
  *agreement* (the share of rows judged exactly as expected), reported beside them.

With the gold set's size the rates are coarse, so each comes with its Wilson 95 % upper
bound; the status compares the rates themselves with the thresholds and the report
shows how far the bound reaches.

**The status** (:class:`CalibrationStatus`): answers that are ``RECORDED`` prove only
the tooling, and say so (``TOOLING_ONLY``), whatever their rates. Only ``LIVE``
answers meet or miss the thresholds, which are the owner's to approve (chunk 1) and
until then :data:`PROPOSED_THRESHOLDS`. Neither result changes
:data:`VERIFIER_CALIBRATION`: a person changes it, with the live measurement recorded
in the plan's § 13 (chunk 25's acceptance).

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import date
from enum import StrEnum
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .agents import AGENT_IDS, AgentRole
from .contracts import Measure, digest
from .tracing import PrimaryStatus
from .verification import RELATED_LIMIT
from .verifier import (
    VERIFIER_CONTRACT_VERSION,
    VERIFIER_PROMPT_VERSION,
    ClaimJudgement,
    ClaimVerdict,
)

__all__ = [
    "CALIBRATION_VERSION",
    "GOLD_SET_SCHEMA_VERSION",
    "PROPOSED_THRESHOLDS",
    "VERIFIER_CALIBRATION",
    "CalibrationRefused",
    "CalibrationReport",
    "CalibrationStatus",
    "GoldItem",
    "GoldSet",
    "ItemOutcome",
    "Thresholds",
    "VerifierAnswers",
    "calibrate",
    "render_calibration",
    "wilson_upper",
]

#: The rules of this module: what a miss and a false alarm are, and the status.
CALIBRATION_VERSION: Final = "aia-verifier-calibration-1"

#: The gold set's own format.
GOLD_SET_SCHEMA_VERSION: Final = "verifier-gold-1"

#: The independent verifier's calibration, as every agent-directed run records it in its
#: versions. A person changes it, never code: only after a ``LIVE`` measurement is
#: recorded in the plan's § 13, naming the prompt and contract it measured.
VERIFIER_CALIBRATION: Final = "NOT_CALIBRATED"

_Z95: Final = 1.959963984540054


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


_Id = Annotated[str, Field(min_length=1, max_length=100)]


class CalibrationRefused(ValueError):
    """Answers that cannot be scored against this gold set; the message says why."""


# --------------------------------------------------------------------------- #
# The gold set
# --------------------------------------------------------------------------- #


class GoldSource(_Closed):
    """What code established about the source, as the verifier is shown it."""

    title: str = Field(min_length=1, max_length=300)
    publisher: str = Field(min_length=1, max_length=200)
    primary: PrimaryStatus
    cited: list[str] = Field(max_length=10)
    date: str | None = Field(max_length=40)


class GoldRelated(_Closed):
    """Another captured figure of the same publisher, as the verifier is shown it."""

    evidence_id: _Id
    claim: str = Field(min_length=1, max_length=1000)
    measures: list[Measure] = Field(max_length=10)
    date: str | None = Field(max_length=40)


class GoldItem(_Closed):
    """One candidate as the verifier sees it, and the verdict it deserves."""

    evidence_id: _Id
    claim: str = Field(min_length=1, max_length=1000)
    quote: str = Field(min_length=1, max_length=2000)
    excerpt: str = Field(min_length=1, max_length=6000)
    measures: list[Measure] = Field(max_length=10)
    source: GoldSource
    related: list[GoldRelated] = Field(max_length=RELATED_LIMIT)
    expected: ClaimVerdict
    #: Why the row deserves its verdict, for the person who reviews the set.
    why: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _well_formed(self) -> GoldItem:
        if self.quote not in self.excerpt:
            raise ValueError(f"{self.evidence_id}: the quote is not in its excerpt")
        if self.expected is ClaimVerdict.SUPERSEDED and not self.related:
            raise ValueError(f"{self.evidence_id}: superseded needs the newer figure in related")
        if self.evidence_id in {r.evidence_id for r in self.related}:
            raise ValueError(f"{self.evidence_id}: an item cannot be related to itself")
        return self

    def shown(self) -> dict[str, Any]:
        """Exactly what :func:`~.verification.verifier_item` shows of a candidate."""

        def measures(ms: list[Measure]) -> list[dict[str, Any]]:
            return [m.model_dump(mode="json", exclude_none=True) for m in ms]

        return {
            "evidence_id": self.evidence_id,
            "claim": self.claim,
            "quote": self.quote,
            "excerpt": self.excerpt,
            "measures": measures(self.measures),
            "source": self.source.model_dump(mode="json"),
            "related": [
                {
                    "evidence_id": r.evidence_id,
                    "claim": r.claim,
                    "measures": measures(r.measures),
                    "date": r.date,
                }
                for r in sorted(self.related, key=lambda r: r.evidence_id)
            ],
        }


class GoldSet(_Closed):
    """Fictional candidates with the verdicts a person decided, fixed by their hash."""

    schema_version: Literal["verifier-gold-1"]
    set_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,62}$")
    #: Always fictional: a gold row names no real publisher and no client.
    fictional: Literal[True]
    recorded_by: str = Field(min_length=1, max_length=100)
    recorded_at: date
    items: list[GoldItem] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _unique(self) -> GoldSet:
        ids = [i.evidence_id for i in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("an evidence_id is in the gold set twice")
        return self

    def sha256(self) -> str:
        """The set's hash over its canonical JSON: formatting does not move it."""
        return digest(self.model_dump(mode="json"))

    def by_verdict(self) -> dict[str, int]:
        counts = Counter(i.expected.value for i in self.items)
        return {v.value: counts[v.value] for v in ClaimVerdict}


# --------------------------------------------------------------------------- #
# A verifier's answers
# --------------------------------------------------------------------------- #


class VerifierAnswers(_Closed):
    """One verifier's judgements over a whole gold set, and how they were produced."""

    kind: Literal["deep_research_verifier_answers"]
    set_id: str
    set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    #: ``RECORDED``: scripted (tests, fixtures). ``LIVE``: a model, through the gateway.
    mode: Literal["RECORDED", "LIVE"]
    agent_id: str
    prompt_version: str
    contract_version: str
    #: The model that answered, for ``LIVE`` answers; null for recorded ones.
    model: str | None = Field(max_length=200)
    recorded_at: date
    judgements: list[ClaimJudgement] = Field(max_length=500)

    @model_validator(mode="after")
    def _model_named(self) -> VerifierAnswers:
        if (self.mode == "LIVE") != (self.model is not None):
            raise ValueError("live answers name their model, and recorded ones none")
        return self


# --------------------------------------------------------------------------- #
# The report
# --------------------------------------------------------------------------- #


class Thresholds(_Closed):
    """The most a verifier may get wrong, and whose they are."""

    max_miss_rate: float = Field(gt=0, lt=1)
    max_false_alarm_rate: float = Field(gt=0, lt=1)
    #: ``PROPOSED`` until the owner approves them (chunk 1), then ``APPROVED``.
    status: Literal["PROPOSED", "APPROVED"]


#: The plan's proposed thresholds (chunk 48): miss < 0.15, false alarm < 0.10.
PROPOSED_THRESHOLDS: Final = Thresholds(
    max_miss_rate=0.15, max_false_alarm_rate=0.10, status="PROPOSED"
)


class CalibrationStatus(StrEnum):
    """What a report establishes about the verifier."""

    #: Recorded answers: the tooling works; nothing is known about a model.
    TOOLING_ONLY = "TOOLING_ONLY"
    #: Live answers within both thresholds.
    MEETS_THRESHOLDS = "MEETS_THRESHOLDS"
    #: Live answers beyond either threshold.
    MISSES_THRESHOLDS = "MISSES_THRESHOLDS"


class ItemOutcome(StrEnum):
    """One row, as code would apply the verifier's verdict."""

    #: Judged exactly as expected.
    AGREED = "agreed"
    #: A bad row accepted.
    MISS = "miss"
    #: A good row set aside (judged otherwise, or not judged).
    FALSE_ALARM = "false_alarm"
    #: A bad row set aside, under another verdict than expected.
    OTHER_REJECTION = "other_rejection"
    #: A bad row not judged: set aside as unverified.
    UNJUDGED_REJECTION = "unjudged_rejection"


class ItemResult(_Closed):
    evidence_id: str
    expected: ClaimVerdict
    said: ClaimVerdict | None
    outcome: ItemOutcome


class CalibrationReport(_Closed):
    """A verifier's error rates on a gold set, and what they establish."""

    version: str = CALIBRATION_VERSION
    set_id: str
    set_sha256: str
    mode: Literal["RECORDED", "LIVE"]
    agent_id: str
    prompt_version: str
    contract_version: str
    model: str | None
    items: int
    good: int
    bad: int
    misses: int
    false_alarms: int
    unjudged: int
    miss_rate: float
    miss_upper_95: float
    false_alarm_rate: float
    false_alarm_upper_95: float
    agreement: float
    #: expected verdict -> the verdict said ("none" when not judged) -> rows.
    confusion: dict[str, dict[str, int]]
    thresholds: Thresholds
    status: CalibrationStatus
    #: What the bundle's versions say until a person changes it.
    recorded_calibration: str = VERIFIER_CALIBRATION
    rows: tuple[ItemResult, ...]


def wilson_upper(failures: int, n: int, z: float = _Z95) -> float:
    """The Wilson score interval's upper bound for ``failures`` out of ``n``."""
    if n <= 0:
        raise ValueError("a rate needs at least one row")
    p = failures / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return min(1.0, (centre + spread) / (1 + z * z / n))


def _outcome(expected: ClaimVerdict, said: ClaimVerdict | None) -> ItemOutcome:
    good = expected is ClaimVerdict.SUPPORTED
    if said is None:
        return ItemOutcome.FALSE_ALARM if good else ItemOutcome.UNJUDGED_REJECTION
    if said is expected:
        return ItemOutcome.AGREED
    if good:
        return ItemOutcome.FALSE_ALARM
    if said is ClaimVerdict.SUPPORTED:
        return ItemOutcome.MISS
    return ItemOutcome.OTHER_REJECTION


def calibrate(
    gold: GoldSet,
    answers: VerifierAnswers,
    *,
    thresholds: Thresholds = PROPOSED_THRESHOLDS,
) -> CalibrationReport:
    """Score one verifier's answers against the gold set they were given.

    Refused: answers to another set or another version of it; answers from another
    agent, prompt or contract than this one's (they calibrate a different verifier);
    a judgement twice, or of a row the set does not have. A row with no judgement is
    scored as code applies it: set aside as unverified.
    """
    if answers.set_id != gold.set_id or answers.set_sha256 != gold.sha256():
        raise CalibrationRefused("the answers are to another gold set, or another version of it")
    expected_agent = AGENT_IDS[AgentRole.INDEPENDENT_VERIFIER]
    if (answers.agent_id, answers.prompt_version, answers.contract_version) != (
        expected_agent,
        VERIFIER_PROMPT_VERSION,
        VERIFIER_CONTRACT_VERSION,
    ):
        raise CalibrationRefused(
            f"the answers are from {answers.agent_id} prompt {answers.prompt_version} "
            f"contract {answers.contract_version}; this verifier is {expected_agent} prompt "
            f"{VERIFIER_PROMPT_VERSION} contract {VERIFIER_CONTRACT_VERSION}"
        )
    said: dict[str, ClaimVerdict] = {}
    known = {i.evidence_id for i in gold.items}
    for j in answers.judgements:
        if j.evidence_id not in known:
            raise CalibrationRefused(f"a judgement of {j.evidence_id}, which the set does not have")
        if j.evidence_id in said:
            raise CalibrationRefused(f"{j.evidence_id} is judged twice")
        said[j.evidence_id] = j.verdict

    rows = tuple(
        ItemResult(
            evidence_id=i.evidence_id,
            expected=i.expected,
            said=said.get(i.evidence_id),
            outcome=_outcome(i.expected, said.get(i.evidence_id)),
        )
        for i in gold.items
    )
    good = sum(1 for r in rows if r.expected is ClaimVerdict.SUPPORTED)
    bad = len(rows) - good
    if good == 0 or bad == 0:
        raise CalibrationRefused("a gold set needs good rows and bad rows to measure both rates")
    outcomes = Counter(r.outcome for r in rows)
    misses, false_alarms = outcomes[ItemOutcome.MISS], outcomes[ItemOutcome.FALSE_ALARM]
    miss_rate, false_alarm_rate = misses / bad, false_alarms / good
    confusion: dict[str, dict[str, int]] = {}
    for r in rows:
        cell = confusion.setdefault(r.expected.value, {})
        key = r.said.value if r.said is not None else "none"
        cell[key] = cell.get(key, 0) + 1
    if answers.mode == "RECORDED":
        status = CalibrationStatus.TOOLING_ONLY
    elif (
        miss_rate < thresholds.max_miss_rate and false_alarm_rate < thresholds.max_false_alarm_rate
    ):
        status = CalibrationStatus.MEETS_THRESHOLDS
    else:
        status = CalibrationStatus.MISSES_THRESHOLDS
    return CalibrationReport(
        set_id=gold.set_id,
        set_sha256=gold.sha256(),
        mode=answers.mode,
        agent_id=answers.agent_id,
        prompt_version=answers.prompt_version,
        contract_version=answers.contract_version,
        model=answers.model,
        items=len(rows),
        good=good,
        bad=bad,
        misses=misses,
        false_alarms=false_alarms,
        unjudged=sum(1 for r in rows if r.said is None),
        miss_rate=miss_rate,
        miss_upper_95=wilson_upper(misses, bad),
        false_alarm_rate=false_alarm_rate,
        false_alarm_upper_95=wilson_upper(false_alarms, good),
        agreement=outcomes[ItemOutcome.AGREED] / len(rows),
        confusion={k: dict(sorted(v.items())) for k, v in sorted(confusion.items())},
        thresholds=thresholds,
        status=status,
        rows=rows,
    )


def render_calibration(report: CalibrationReport) -> str:
    """A few lines a person reads first; the JSON report has the rest."""
    model = f" {report.model}" if report.model else ""
    lines = [
        f"{report.set_id} ({report.items} rows: {report.good} good, {report.bad} bad), "
        f"{report.mode}{model}, prompt {report.prompt_version}",
        f"miss {report.misses}/{report.bad} = {report.miss_rate:.3f} "
        f"(95 % upper {report.miss_upper_95:.3f}; threshold < "
        f"{report.thresholds.max_miss_rate}, {report.thresholds.status})",
        f"false alarm {report.false_alarms}/{report.good} = {report.false_alarm_rate:.3f} "
        f"(95 % upper {report.false_alarm_upper_95:.3f}; threshold < "
        f"{report.thresholds.max_false_alarm_rate}, {report.thresholds.status})",
        f"agreement {report.agreement:.3f}; unjudged {report.unjudged}",
        f"status {report.status.value}; the runs record {report.recorded_calibration}",
    ]
    if report.status is CalibrationStatus.TOOLING_ONLY:
        lines.append("recorded answers: this proves the tooling, not a verifier")
    return "\n".join(lines)
