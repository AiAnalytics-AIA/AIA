"""The truth set: public facts with known values, fixed and recorded before any run.

Plan ``deep-research-web-search.md`` chunk 25. Accuracy is measured against facts a
person has looked up at their primary publisher, not against what a run says. So
the set is data with three rules, all enforced by code:

* **The format is closed and versioned** (:data:`TRUTH_SET_SCHEMA_VERSION`). Each
  :class:`TruthFact` carries its Czech question, the expected figure as the
  publisher prints it (``value_text``) with its unit, scale, period, geography,
  population and denominator in the measure vocabulary's keys
  (:mod:`.measures`: ``%``, ``CZK``, ``HOUSEHOLDS``, ``CZ``, a period
  :func:`~.triangulation.period_span` can place), the tolerance (exact unless
  stated, with its reason), the primary publisher as a reputation-register key
  (``register:cesky statisticky urad``), where the figure is (URL, dataset id, table
  cell), its Class C marker, who recorded it and when, and whether a person has
  verified it at the source.
* **Fixed before any run.** A set is scored only when its hash
  (:meth:`TruthSet.sha256`, over its canonical JSON, so formatting does not matter)
  is pinned for its ``set_id`` in a committed manifest (:class:`TruthSetPins`). A
  set id is pinned once: a corrected set is a new set id, so a score can never be
  improved by editing the answers after the run.
* **Verified before it counts.** A real set is pinned and scored only when every
  fact is ``verified``. ``allow_unverified`` exists for fictional fixtures alone:
  :func:`admit_truth_set` refuses it for a set that is not fictional.

**Fiction is marked, never mistaken.** A fictional set (``fictional: true``) names
its own publishers (:class:`FictionalPublisher`) on reserved hosts only
(``.example``, ``.test``, ``.invalid``: RFC 2606), and its URLs must be on them; a
real set uses :data:`~.reputation.REPUTATION_REGISTER_V1` and may name no
fictional publisher. A real set's values are never written by code or by an agent:
the template (``docs/evaluation/deep-research/czech-public-facts.template.json``) has
every value blank and every fact ``unverified`` until a person fills and checks it.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from typing import Final, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..residency import DataClass
from .contracts import MeasureBasis, digest, normalise_label
from .measures import GEOGRAPHY, PERCENTAGE_POINTS, POPULATIONS, UNITS
from .reputation import (
    REPUTATION_REGISTER_V1,
    REPUTATION_REGISTER_VERSION,
    Publisher,
    RegisterStatus,
    ReputationRegister,
)
from .sources import SourceClass, SourceTier
from .triangulation import period_span, register_key

__all__ = [
    "FICTIONAL_REGISTER_VERSION",
    "RESERVED_SUFFIXES",
    "SCALES",
    "TRUTH_SET_PINS_VERSION",
    "TRUTH_SET_SCHEMA_VERSION",
    "ExpectedValue",
    "FictionalPublisher",
    "PrimarySource",
    "SourceType",
    "Tolerance",
    "ToleranceKind",
    "Topic",
    "TruthFact",
    "TruthSet",
    "TruthSetPin",
    "TruthSetPins",
    "TruthSetRefused",
    "Verification",
    "VerificationStatus",
    "add_pin",
    "admit_truth_set",
    "empty_pins",
    "load_pins",
    "load_truth_set",
    "parse_value",
]

TRUTH_SET_SCHEMA_VERSION: Final = "aia-dr-truth-set-1"
TRUTH_SET_PINS_VERSION: Final = "aia-dr-truth-set-pins-1"
#: The register a fictional set builds from its own publishers.
FICTIONAL_REGISTER_VERSION: Final = "aia-dr-fictional-register-1"
#: Host suffixes no real publisher can have (RFC 2606, RFC 6761).
RESERVED_SUFFIXES: Final = (".example", ".test", ".invalid")
#: The scales a Czech text writes: 1, tis., mil., mld.
SCALES: Final = frozenset({1, 1_000, 1_000_000, 1_000_000_000})

_SET_ID: Final = r"^[a-z0-9][a-z0-9-]{2,62}$"
_REGISTER_KEY: Final = r"^register:[0-9a-z]+(?: [0-9a-z]+)*$"
_SHA256: Final = r"^[0-9a-f]{64}$"
#: A fact's id begins with its topic's prefix.
_PREFIX: Final = {
    "population": "pop",
    "prices": "price",
    "consumption": "cons",
    "trade": "trade",
}
_UNIT_KEYS: Final = frozenset(UNITS) | {PERCENTAGE_POINTS}
_POPULATION_KEYS: Final = frozenset(POPULATIONS)
_GEOGRAPHY_KEYS: Final = frozenset(GEOGRAPHY)
#: A Czech figure as a publisher prints it: an optional minus, digits grouped by a
#: space, a no-break space or a narrow no-break space, and a decimal comma.
_VALUE: Final = re.compile(
    r"^(?P<sign>[-\u2212])?"
    r"(?P<int>\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)"
    r"(?:,(?P<frac>\d+))?$"
)


class TruthSetRefused(ValueError):
    """A truth set that may not be pinned or scored, with the reason in words."""


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def parse_value(text: str) -> tuple[float, int]:
    """A printed Czech figure -> (value, decimals). ``"10 450,6"`` -> ``(10450.6, 1)``.

    Raises ``ValueError`` for anything else: a decimal point, a unit, a word.
    """
    match = _VALUE.match(text.strip())
    if match is None:
        raise ValueError(
            f"{text!r} is not a figure as printed: digits, groups of three separated by a "
            "space, a decimal comma"
        )
    digits = re.sub(r"\D", "", match["int"])
    frac = match["frac"] or ""
    value = float(f"{digits}.{frac}" if frac else digits)
    return (-value if match["sign"] else value), len(frac)


class Topic(StrEnum):
    POPULATION = "population"
    PRICES = "prices"
    CONSUMPTION = "consumption"
    TRADE = "trade"


class SourceType(StrEnum):
    """Where at its publisher a figure stands, by kind."""

    #: A table served by a data interface (DataStat, Eurostat): a dataset cell.
    DATASET = "dataset"
    #: A table inside a published file (XLSX, CSV, a PDF table): a sheet cell or a row/column.
    DOCUMENT_TABLE = "document_table"
    #: A table on a web page.
    WEB_TABLE = "web_table"
    #: Running text: a press release, a report's paragraph.
    WEB_TEXT = "web_text"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"


class ToleranceKind(StrEnum):
    EXACT = "exact"
    #: Within an amount in the fact's own unit and scale, with the reason stated.
    ABSOLUTE = "absolute"


class Tolerance(_Closed):
    """How far a found value may be from the expected one and still be correct."""

    kind: ToleranceKind = ToleranceKind.EXACT
    amount: str | None = None
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _stated(self) -> Tolerance:
        if self.kind is ToleranceKind.EXACT:
            if self.amount is not None:
                raise ValueError("an exact tolerance has no amount")
            return self
        if self.amount is None or not (self.reason or "").strip():
            raise ValueError("an absolute tolerance states its amount and its reason")
        value, _ = parse_value(self.amount)
        if value <= 0:
            raise ValueError("a tolerance amount is positive")
        return self

    def allowed(self, scale: int) -> float:
        """The allowed absolute difference, scaled; 0 for exact."""
        if self.kind is ToleranceKind.EXACT or self.amount is None:
            return 0.0
        return parse_value(self.amount)[0] * scale


class ExpectedValue(_Closed):
    """The figure as its publisher prints it, and what makes it that figure.

    Keys are the measure vocabulary's (:mod:`.measures`). ``None`` is *not part of
    this figure* (a price index has no population), and a run that states one is
    then stating a different figure. ``value_text`` is ``None`` only in a slot not
    yet filled.
    """

    value_text: str | None = Field(default=None, max_length=40)
    unit: str | None = None
    scale: int = 1
    period: str | None = Field(default=None, max_length=40)
    geography: str | None = None
    population: str | None = None
    denominator: str | None = None
    measure_name: str | None = Field(default=None, max_length=200)
    basis: MeasureBasis | None = None

    @model_validator(mode="after")
    def _keys(self) -> ExpectedValue:
        if self.value_text is not None:
            parse_value(self.value_text)
        if self.scale not in SCALES:
            raise ValueError(f"scale {self.scale} is not one of {sorted(SCALES)}")
        if self.unit is not None and self.unit not in _UNIT_KEYS:
            raise ValueError(f"unit {self.unit!r} is not a vocabulary key: {sorted(_UNIT_KEYS)}")
        if self.population is not None and self.population not in _POPULATION_KEYS:
            raise ValueError(f"population {self.population!r} is not a vocabulary key")
        if self.denominator is not None and self.denominator not in (_UNIT_KEYS | _POPULATION_KEYS):
            raise ValueError(f"denominator {self.denominator!r} is not a unit or population key")
        if self.geography is not None and self.geography not in _GEOGRAPHY_KEYS:
            raise ValueError(f"geography {self.geography!r} is not a vocabulary key")
        if self.period is not None and period_span(self.period) is None:
            raise ValueError(f"period {self.period!r} cannot be placed (2024, 2024-Q2, 2024/25)")
        return self

    @property
    def value(self) -> float | None:
        return None if self.value_text is None else parse_value(self.value_text)[0]

    @property
    def decimals(self) -> int:
        return 0 if self.value_text is None else parse_value(self.value_text)[1]


class PrimarySource(_Closed):
    """Who publishes the figure, and exactly where."""

    publisher: str = Field(pattern=_REGISTER_KEY)
    source_type: SourceType
    url: str | None = Field(default=None, max_length=2048)
    dataset_id: str | None = Field(default=None, max_length=300)
    #: The cell: a dataset locator (``<dataset>!<row>/<column>``), ``Sheet!B4``, or
    #: ``p. 3, tab. 2, row …, column …`` for a PDF table.
    cell: str | None = Field(default=None, max_length=500)
    title: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _url(self) -> PrimarySource:
        if self.url is not None:
            parts = urlsplit(self.url)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                raise ValueError(f"{self.url!r} is not an http(s) URL")
        return self

    @property
    def host(self) -> str | None:
        return None if self.url is None else (urlsplit(self.url).hostname or "").lower()


class Verification(_Closed):
    """Whether a person has checked the fact at its source."""

    status: VerificationStatus = VerificationStatus.UNVERIFIED
    verified_by: str | None = Field(default=None, max_length=200)
    verified_at: date | None = None
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _who(self) -> Verification:
        named = self.verified_by is not None and self.verified_at is not None
        if self.status is VerificationStatus.VERIFIED and not named:
            raise ValueError("a verified fact names who verified it and when")
        if self.status is VerificationStatus.UNVERIFIED and (
            self.verified_by is not None or self.verified_at is not None
        ):
            raise ValueError("an unverified fact names no verifier")
        return self


class TruthFact(_Closed):
    """One public fact with its known value and where it is published."""

    fact_id: str = Field(pattern=r"^(pop|price|cons|trade)-[0-9]{2}$")
    topic: Topic
    #: What the fact is, in words, without its value (a template slot's description).
    slot: str = Field(min_length=1, max_length=500)
    question: str | None = Field(default=None, max_length=500)
    expected: ExpectedValue
    tolerance: Tolerance = Tolerance()
    primary: PrimarySource
    data_class: DataClass
    recorded_at: date | None = None
    recorded_by: str | None = Field(default=None, max_length=200)
    verification: Verification = Verification()

    @model_validator(mode="after")
    def _complete(self) -> TruthFact:
        if not self.fact_id.startswith(_PREFIX[self.topic.value] + "-"):
            raise ValueError(
                f"{self.fact_id}: a {self.topic.value} fact's id begins with "
                f"{_PREFIX[self.topic.value]}-"
            )
        if self.data_class is not DataClass.CLASS_C_INTERNAL:
            raise ValueError(f"{self.fact_id}: a truth fact is public, Class C")
        if self.question is not None and not self.question.strip():
            raise ValueError(f"{self.fact_id}: an empty question")
        if self.verification.status is VerificationStatus.VERIFIED:
            missing = [
                name
                for name, value in (
                    ("question", self.question),
                    ("expected.value_text", self.expected.value_text),
                    ("expected.period", self.expected.period),
                    ("expected.geography", self.expected.geography),
                    ("expected.measure_name", self.expected.measure_name),
                    ("primary.url", self.primary.url),
                    ("primary.cell", self.primary.cell),
                    ("recorded_at", self.recorded_at),
                    ("recorded_by", self.recorded_by),
                )
                if value is None
            ]
            if self.primary.source_type is SourceType.DATASET and self.primary.dataset_id is None:
                missing.append("primary.dataset_id")
            if missing:
                raise ValueError(f"{self.fact_id}: verified, and missing {', '.join(missing)}")
            assert self.recorded_at is not None and self.verification.verified_at is not None
            if self.verification.verified_at < self.recorded_at:
                raise ValueError(f"{self.fact_id}: verified before it was recorded")
        return self

    @property
    def scorable(self) -> bool:
        """Whether the fact has what scoring reads: a question, a value, a period, a place."""
        e = self.expected
        return None not in (self.question, e.value_text, e.period, e.geography)


class FictionalPublisher(_Closed):
    """A publisher of a fictional set: a name and hosts no real publisher can have."""

    name: str = Field(min_length=3, max_length=200)
    hosts: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _reserved(self) -> FictionalPublisher:
        for host in self.hosts:
            if not host.endswith(RESERVED_SUFFIXES):
                raise ValueError(f"fictional host {host!r} is not under {RESERVED_SUFFIXES}")
        return self


class TruthSet(_Closed):
    """A versioned, closed set of facts. Its hash is what a manifest pins."""

    kind: Literal["deep_research_truth_set"]
    schema_version: Literal["aia-dr-truth-set-1"]
    set_id: str = Field(pattern=_SET_ID)
    title: str = Field(min_length=1, max_length=300)
    fictional: bool
    register_version: str
    fictional_publishers: tuple[FictionalPublisher, ...] = ()
    facts: tuple[TruthFact, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> TruthSet:
        ids = [f.fact_id for f in self.facts]
        if len(set(ids)) != len(ids):
            raise ValueError("a fact id is used twice")
        questions = [normalise_label(f.question) for f in self.facts if f.question is not None]
        if len(set(questions)) != len(questions):
            raise ValueError("two facts ask the same question; a run could not tell them apart")
        if self.fictional:
            if self.register_version != FICTIONAL_REGISTER_VERSION:
                raise ValueError(f"a fictional set uses {FICTIONAL_REGISTER_VERSION}")
            if not self.fictional_publishers:
                raise ValueError("a fictional set names its fictional publishers")
            for f in self.facts:
                host = f.primary.host
                if host is not None and not host.endswith(RESERVED_SUFFIXES):
                    raise ValueError(f"{f.fact_id}: a fictional fact's URL is on a reserved host")
        else:
            if self.register_version != REPUTATION_REGISTER_VERSION:
                raise ValueError(f"a real set uses the register {REPUTATION_REGISTER_VERSION!r}")
            if self.fictional_publishers:
                raise ValueError("a real set names no fictional publisher")
        keys = {register_key(p) for p in self.register().publishers}
        for f in self.facts:
            if f.primary.publisher not in keys:
                raise ValueError(
                    f"{f.fact_id}: {f.primary.publisher!r} is not a publisher of "
                    f"{self.register_version}"
                )
        return self

    def register(self) -> ReputationRegister:
        """The register publishers are resolved in: the fictional one, or the real one."""
        if not self.fictional:
            return REPUTATION_REGISTER_V1
        return ReputationRegister(
            version=FICTIONAL_REGISTER_VERSION,
            status=RegisterStatus.PROPOSED,
            publishers=tuple(
                Publisher(p.name, (), p.hosts, SourceClass.OFFICIAL_STATISTICS, SourceTier.T1)
                for p in self.fictional_publishers
            ),
        )

    def sha256(self) -> str:
        """The set's identity: SHA256 over its canonical JSON."""
        return digest(self.model_dump(mode="json"))

    def unverified(self) -> tuple[str, ...]:
        return tuple(
            f.fact_id
            for f in self.facts
            if f.verification.status is not VerificationStatus.VERIFIED
        )

    def topics(self) -> Mapping[str, int]:
        counts: dict[str, int] = {}
        for f in self.facts:
            counts[f.topic.value] = counts.get(f.topic.value, 0) + 1
        return counts


def load_truth_set(text: str) -> TruthSet:
    """Parse and validate a truth set's JSON: strict types, no unknown field."""
    return TruthSet.model_validate_json(text, strict=True)


class TruthSetPin(_Closed):
    """One set fixed: its id, its hash, where it lives, who pinned it and when."""

    set_id: str = Field(pattern=_SET_ID)
    sha256: str = Field(pattern=_SHA256)
    path: str = Field(min_length=1, max_length=500)
    facts: int = Field(ge=1)
    fictional: bool
    pinned_at: date
    pinned_by: str = Field(min_length=1, max_length=200)


class TruthSetPins(_Closed):
    """The committed manifest of pinned sets. One pin per set id, for good."""

    kind: Literal["deep_research_truth_set_pins"]
    version: Literal["aia-dr-truth-set-pins-1"]
    pins: tuple[TruthSetPin, ...]

    @model_validator(mode="after")
    def _once(self) -> TruthSetPins:
        ids = [p.set_id for p in self.pins]
        if len(set(ids)) != len(ids):
            raise ValueError("a set id is pinned twice")
        return self

    def pin_for(self, set_id: str) -> TruthSetPin | None:
        return next((p for p in self.pins if p.set_id == set_id), None)


def load_pins(text: str) -> TruthSetPins:
    return TruthSetPins.model_validate_json(text, strict=True)


def empty_pins() -> TruthSetPins:
    return TruthSetPins(
        kind="deep_research_truth_set_pins", version="aia-dr-truth-set-pins-1", pins=()
    )


def add_pin(
    pins: TruthSetPins, truth: TruthSet, *, path: str, pinned_at: date, pinned_by: str
) -> TruthSetPins:
    """``pins`` with ``truth`` pinned. Idempotent for the same hash; a changed set is refused.

    A real set is pinned only when every fact is verified and scorable: pinning is
    the moment the answers are fixed.
    """
    sha = truth.sha256()
    existing = pins.pin_for(truth.set_id)
    if existing is not None:
        if existing.sha256 == sha:
            return pins
        raise TruthSetRefused(
            f"{truth.set_id} is pinned at {existing.sha256[:12]}; this set hashes to "
            f"{sha[:12]}. A pinned set is never changed: give the corrected set a new set_id"
        )
    unverified = truth.unverified()
    if unverified and not truth.fictional:
        raise TruthSetRefused(
            f"{truth.set_id}: {len(unverified)} fact(s) not verified at the source "
            f"({', '.join(unverified[:5])}...); a real set is pinned only when all are"
        )
    unscorable = [f.fact_id for f in truth.facts if not f.scorable]
    if unscorable:
        raise TruthSetRefused(
            f"{truth.set_id}: {', '.join(unscorable)} lack a question, value, period or place"
        )
    pin = TruthSetPin(
        set_id=truth.set_id,
        sha256=sha,
        path=path,
        facts=len(truth.facts),
        fictional=truth.fictional,
        pinned_at=pinned_at,
        pinned_by=pinned_by,
    )
    return pins.model_copy(update={"pins": (*pins.pins, pin)})


def admit_truth_set(truth: TruthSet, pins: TruthSetPins, *, allow_unverified: bool) -> None:
    """Refuse, with the reason, a set that may not be scored. Returns when it may.

    * its hash is pinned for its set id;
    * every fact is verified -- or ``allow_unverified`` and the set is fictional;
    * every fact is scorable.
    """
    pin = pins.pin_for(truth.set_id)
    sha = truth.sha256()
    if pin is None:
        raise TruthSetRefused(
            f"{truth.set_id} is not pinned; pin it (tools/dr_accuracy.py pin) and commit the "
            "manifest before any run"
        )
    if pin.sha256 != sha:
        raise TruthSetRefused(
            f"{truth.set_id} hashes to {sha[:12]}, the manifest pins {pin.sha256[:12]}: the set "
            "changed after it was fixed"
        )
    if allow_unverified and not truth.fictional:
        raise TruthSetRefused("unverified facts are allowed only in a fictional set")
    unverified = truth.unverified()
    if unverified and not allow_unverified:
        raise TruthSetRefused(
            f"{truth.set_id}: {len(unverified)} fact(s) not verified at the source "
            f"({', '.join(unverified[:5])})"
        )
    unscorable = [f.fact_id for f in truth.facts if not f.scorable]
    if unscorable:
        raise TruthSetRefused(
            f"{truth.set_id}: {', '.join(unscorable)} lack a question, value, period or place"
        )
