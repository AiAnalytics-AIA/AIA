"""Deep Research's policy values: the catalogue an Admin approves values against (ADR 0022).

Plan ``deep-research-web-search.md`` chunk 40. Every value the data owner signs off before
Deep Research goes live -- the search provider's terms and price, budgets and caps, request
limits, the light model, quotas, retention, the register and weights, the extraction denylist
and rules -- is a **setting** here: a key, a group, a closed type, its bounds, its proposed
default and whether live needs it approved. Nothing else can be stored, and every stored value
is validated by this module.

Three homes, by kind of value (ADR 0022 decision 1). Switches, secrets and the model route
stay in the deployment; rails (``robots.txt``, no access barriers, the personal-data screen,
Class C only, grounding) stay code and no setting can switch one off; policy values live here.
No key may name a secret (:data:`SECRET_WORDS`): a credential is a reference the deployment
holds, never a stored value.

The proposed default of a setting is the constant the code holds today, or ``None`` where the
code holds nothing (an unknown, never a zero -- CLAUDE.md § 8). So storing nothing changes
nothing. A cap is ``lower_only``: an approved value may lower it below the code's ceiling and
never raise it.

:func:`effective` resolves what is in force: each key's approved value, else its proposed
default, with its origin. Its :meth:`~EffectiveSettings.digest` covers every key; its
:meth:`~EffectiveSettings.method_digest` only the keys that shape a result (``method``), which
are the ones a run's reuse keys must carry (chunk 43). :meth:`~EffectiveSettings.missing_for_live`
names every setting live still needs approved (chunk 44).

Pure: stdlib only.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Final
from urllib.parse import urlsplit

from .budgets import ROUTE_ALLOWANCES
from .contracts import digest
from .request_limits import REQUEST_LIMITS

__all__ = [
    "CATALOGUE",
    "CATALOGUE_VERSION",
    "SECRET_WORDS",
    "SETTINGS_PIN_CONTRACT",
    "ApprovedValue",
    "Effective",
    "EffectiveSettings",
    "Origin",
    "SettingDefinition",
    "SettingGroup",
    "SettingInvalid",
    "SettingType",
    "SettingValue",
    "SettingsPinCorrupt",
    "definition",
    "effective",
    "keys",
    "pin",
    "read_pin",
    "validate",
]

#: The catalogue's identity: moves when a setting is added, removed or retyped.
CATALOGUE_VERSION: Final = "aia-dr-settings-catalogue-1"

#: A stored value: JSON-shaped, nothing richer.
type SettingValue = int | float | str | bool | tuple[str, ...] | None

#: Words no key may contain: a secret is a credential reference the deployment holds.
SECRET_WORDS: Final = ("key", "secret", "token", "password", "credential")

_STATUS_VALUES: Final = ("proposed", "approved")
_MAX_TEXT: Final = 500
_MAX_LIST: Final = 500
_MAX_PATTERN: Final = 200
_HOST: Final = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_KEY: Final = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
_EU_PROFILE: Final = re.compile(r"^eu\.[A-Za-z0-9._-]+:\d+$")


class SettingInvalid(ValueError):
    """A value the catalogue refuses: wrong type, out of bounds, or not catalogued."""

    def __init__(self, key: str, reason: str) -> None:
        super().__init__(f"{key}: {reason}")
        self.key = key
        self.reason = reason


class SettingGroup(StrEnum):
    """Where a setting sits on the page."""

    SIGN_OFF = "sign_off"
    PROVIDER = "provider"
    BUDGETS = "budgets"
    LIMITS = "limits"
    MODELS = "models"
    QUOTAS = "quotas"
    RETENTION = "retention"
    SOURCES = "sources"
    EXTRACTION = "extraction"


class SettingType(StrEnum):
    """The closed types a setting can have."""

    INTEGER = "integer"
    USD = "usd"
    DAYS = "days"
    URL = "url"
    DATE = "date"
    TEXT = "text"
    #: A model id: an EU inference profile pinned to a version (``eu.…:N``, ADR 0010).
    MODEL_ID = "model_id"
    #: A yes or no the data owner answers (e.g. "results may be stored").
    DECISION = "decision"
    #: ``proposed`` or ``approved``: a code-owned table (register, weights) approved as is.
    STATUS = "status"
    HOST_LIST = "host_list"
    PATTERN_LIST = "pattern_list"


@dataclass(frozen=True, slots=True)
class SettingDefinition:
    """One policy value: what it is, how it is checked, what it is until approved."""

    key: str
    group: SettingGroup
    type: SettingType
    label: str
    default: SettingValue
    unit: str = ""
    minimum: float | None = None
    maximum: float | None = None
    #: An approved value may lower the default and never raise it (a cap).
    lower_only: bool = False
    #: Live refuses until this setting is approved (and, for a status, approved as ``approved``).
    required_for_live: bool = False
    #: The value shapes a run's result, so it belongs in the run's reuse keys (chunk 43).
    method: bool = False
    #: Where the code's default comes from, for the page ("module:CONSTANT"), or "".
    default_source: str = ""

    def __post_init__(self) -> None:
        if not _KEY.match(self.key):
            raise ValueError(f"{self.key!r} is not a dotted lower-case key")
        lowered = self.key.lower()
        if any(word in lowered.replace("_", ".").split(".") for word in SECRET_WORDS):
            raise ValueError(f"{self.key!r} names a secret; secrets stay in the deployment")
        if self.lower_only and self.type not in (SettingType.INTEGER, SettingType.USD):
            raise ValueError(f"{self.key!r}: only a number can be lower-only")
        if self.default is not None:
            validate_value(self, self.default, bound_by_default=False)


@dataclass(frozen=True, slots=True)
class ApprovedValue:
    """A value an Admin approved: what the store says is in force for one key."""

    value: SettingValue
    version: int
    approved_by: str
    approved_at: datetime


class Origin(StrEnum):
    """Where an effective value comes from."""

    APPROVED = "approved"
    #: The code's proposed default: in force offline, never enough for live.
    PROPOSED_DEFAULT = "proposed_default"


@dataclass(frozen=True, slots=True)
class Effective:
    """One key's value in force, and where it comes from."""

    key: str
    value: SettingValue
    origin: Origin
    version: int | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None


def _number(defn: SettingDefinition, value: object, *, integer: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SettingInvalid(defn.key, "is not a number")
    if integer and not isinstance(value, int):
        raise SettingInvalid(defn.key, "is not a whole number")
    if value != value or value in (float("inf"), float("-inf")):
        raise SettingInvalid(defn.key, "is not a finite number")
    return float(value)


def validate_value(
    defn: SettingDefinition, value: object, *, bound_by_default: bool = True
) -> SettingValue:
    """``value`` (as stored, or as JSON sent it: a list for a tuple) for ``defn`` in its normal
    form, or :class:`SettingInvalid`.

    ``bound_by_default`` applies a lower-only setting's ceiling (its default); the catalogue
    itself checks a default without it.
    """
    key = defn.key
    if value is None:
        raise SettingInvalid(key, "a value is required; withdrawing returns the default")
    kind = defn.type
    if kind in (SettingType.INTEGER, SettingType.DAYS, SettingType.USD):
        number = _number(defn, value, integer=kind is not SettingType.USD)
        if defn.minimum is not None and number < defn.minimum:
            raise SettingInvalid(key, f"is below the minimum {defn.minimum:g}")
        if defn.maximum is not None and number > defn.maximum:
            raise SettingInvalid(key, f"is above the maximum {defn.maximum:g}")
        if (
            bound_by_default
            and defn.lower_only
            and defn.default is not None
            and number > float(defn.default)  # type: ignore[arg-type]
        ):
            raise SettingInvalid(key, f"may only lower the code's cap of {defn.default}")
        return float(number) if kind is SettingType.USD else int(number)
    if kind is SettingType.DECISION:
        if not isinstance(value, bool):
            raise SettingInvalid(key, "is not yes or no")
        return value
    if not isinstance(value, (str, tuple, list)):
        raise SettingInvalid(key, "is not text")
    if kind in (SettingType.HOST_LIST, SettingType.PATTERN_LIST):
        if isinstance(value, str):
            raise SettingInvalid(key, "is not a list")
        items = [str(v).strip() for v in value]
        if len(items) > _MAX_LIST:
            raise SettingInvalid(key, f"holds more than {_MAX_LIST} entries")
        if kind is SettingType.HOST_LIST:
            hosts = sorted({h.lower().rstrip(".") for h in items if h})
            bad = [h for h in hosts if not _HOST.match(h)]
            if bad:
                raise SettingInvalid(key, f"not a host name: {', '.join(bad[:3])}")
            return tuple(hosts)
        patterns: list[str] = []
        for p in dict.fromkeys(i for i in items if i):
            if len(p) > _MAX_PATTERN:
                raise SettingInvalid(key, f"a pattern is longer than {_MAX_PATTERN} characters")
            try:
                re.compile(p)
            except re.error as exc:
                raise SettingInvalid(key, f"{p!r} is not a valid pattern: {exc}") from exc
            patterns.append(p)
        return tuple(patterns)
    if not isinstance(value, str):
        raise SettingInvalid(key, "is not text")
    text = value.strip()
    if not text:
        raise SettingInvalid(key, "is empty")
    if len(text) > _MAX_TEXT:
        raise SettingInvalid(key, f"is longer than {_MAX_TEXT} characters")
    if kind is SettingType.URL:
        parts = urlsplit(text)
        if parts.scheme != "https" or not parts.hostname:
            raise SettingInvalid(key, "is not an https URL")
        return text
    if kind is SettingType.DATE:
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError as exc:
            raise SettingInvalid(key, "is not a date (YYYY-MM-DD)") from exc
    if kind is SettingType.MODEL_ID:
        if not _EU_PROFILE.match(text) or text.endswith("latest"):
            raise SettingInvalid(
                key, "is not an EU inference profile pinned to a version (eu.…:N, ADR 0010)"
            )
        return text
    if kind is SettingType.STATUS:
        if text not in _STATUS_VALUES:
            raise SettingInvalid(key, f"is not one of {', '.join(_STATUS_VALUES)}")
        return text
    return text


# --------------------------------------------------------------------------- #
# The catalogue
# --------------------------------------------------------------------------- #


def _s(
    key: str,
    group: SettingGroup,
    type_: SettingType,
    label: str,
    default: SettingValue = None,
    **kwargs: object,
) -> SettingDefinition:
    return SettingDefinition(key, group, type_, label, default, **kwargs)  # type: ignore[arg-type]


_P = SettingGroup.PROVIDER
_LIVE = {"required_for_live": True}

_SIGN_OFF: Final = (
    _s(
        "sign_off.design_and_boundaries",
        SettingGroup.SIGN_OFF,
        SettingType.STATUS,
        "The design and its boundaries (plan § 4)",
        "proposed",
        **_LIVE,
    ),
    _s(
        "sign_off.adr_0017_amendment",
        SettingGroup.SIGN_OFF,
        SettingType.STATUS,
        "The ADR 0017 amendment (plan § 16)",
        "proposed",
        **_LIVE,
    ),
)

_PROVIDER: Final = (
    _s("provider.search.plan", _P, SettingType.TEXT, "Search provider plan", **_LIVE),
    _s("provider.search.terms_url", _P, SettingType.URL, "Terms of service (URL)", **_LIVE),
    _s("provider.search.terms_date", _P, SettingType.DATE, "Terms read on", **_LIVE),
    _s(
        "provider.search.price_per_1000",
        _P,
        SettingType.USD,
        "Price per 1,000 requests",
        unit="USD",
        minimum=0,
        maximum=1000,
        **_LIVE,
    ),
    _s(
        "provider.search.failed_requests_billed",
        _P,
        SettingType.DECISION,
        "Failed requests are billed",
        **_LIVE,
    ),
    _s(
        "provider.search.storage_and_ai_use_granted",
        _P,
        SettingType.DECISION,
        "The plan grants storing results and using them with AI",
        **_LIVE,
    ),
    _s(
        "provider.search.query_log_retention",
        _P,
        SettingType.DAYS,
        "The provider keeps query logs for",
        unit="days",
        minimum=0,
        maximum=3650,
        **_LIVE,
    ),
)

_BUDGETS: Final = tuple(
    _s(
        f"budgets.run_limit.{preset.lower()}",
        SettingGroup.BUDGETS,
        SettingType.USD,
        f"Most a {preset.title()} run may cost",
        unit="USD",
        minimum=0,
        maximum=100_000,
        **_LIVE,
    )
    for preset in ("STANDARD", "DEEP", "EXHAUSTIVE")
)

_PRESETS_STATUS: Final = (
    _s(
        "budgets.presets",
        SettingGroup.BUDGETS,
        SettingType.STATUS,
        "The preset table (tracks, searches, opens, turns per preset)",
        "proposed",
        method=True,
        default_source="domain.deep_research.planning:PRESETS",
        **_LIVE,
    ),
)

_ALLOWANCE_FIELDS: Final = (
    ("triage_reads", "Triage reads"),
    ("crawl_pages", "Crawled pages"),
    ("connector_calls", "Connector calls"),
    ("index_queries", "Common Crawl index queries"),
    ("archive_fetches", "Archived pages"),
)

_ALLOWANCES: Final = tuple(
    _s(
        f"budgets.allowance.{preset.lower()}.{field}",
        SettingGroup.BUDGETS,
        SettingType.INTEGER,
        f"{preset.title()}: {label}",
        getattr(allowance, field),
        unit="per run",
        minimum=0,
        lower_only=True,
        method=True,
        default_source=f"domain.deep_research.budgets:ROUTE_ALLOWANCES[{preset}]",
    )
    for preset, allowance in ROUTE_ALLOWANCES.items()
    for field, label in _ALLOWANCE_FIELDS
    if getattr(allowance, field) > 0
)

_LIMITS: Final = tuple(
    _s(
        f"limits.{kind.value}.{part}",
        SettingGroup.LIMITS,
        SettingType.INTEGER,
        f"{kind.value.replace('_', ' ').capitalize()}: "
        + ("window" if part == "window_tokens" else "answer limit"),
        getattr(limits, part),
        unit="tokens",
        minimum=1024,
        lower_only=True,
        method=True,
        default_source=f"domain.deep_research.request_limits:REQUEST_LIMITS[{kind.value}]",
    )
    for kind, limits in sorted(REQUEST_LIMITS.items())
    for part in ("window_tokens", "answer_tokens")
)

_MODELS: Final = (
    _s(
        "models.lead.model_id",
        SettingGroup.MODELS,
        SettingType.MODEL_ID,
        "The lead researcher's model (its own policy entry)",
        **_LIVE,
    ),
    _s(
        "models.light.model_id",
        SettingGroup.MODELS,
        SettingType.MODEL_ID,
        "The light model (triage, extraction)",
        **_LIVE,
    ),
    _s(
        "models.light.input_price",
        SettingGroup.MODELS,
        SettingType.USD,
        "Light model input price",
        unit="USD per 1M tokens",
        minimum=0,
        maximum=1000,
        **_LIVE,
    ),
    _s(
        "models.light.output_price",
        SettingGroup.MODELS,
        SettingType.USD,
        "Light model output price",
        unit="USD per 1M tokens",
        minimum=0,
        maximum=1000,
        **_LIVE,
    ),
)

_QUOTAS: Final = (
    _s(
        "quotas.model_requests_per_minute",
        SettingGroup.QUOTAS,
        SettingType.INTEGER,
        "Granted model requests per minute",
        unit="requests/min",
        minimum=1,
        maximum=1_000_000,
        **_LIVE,
    ),
    _s(
        "quotas.model_input_per_minute",
        SettingGroup.QUOTAS,
        SettingType.INTEGER,
        "Granted model input per minute",
        unit="tokens/min",
        minimum=1,
        maximum=1_000_000_000,
        **_LIVE,
    ),
)

_RETENTION: Final = (
    _s(
        "retention.snapshots",
        SettingGroup.RETENTION,
        SettingType.DAYS,
        "Keep captured pages for",
        unit="days",
        minimum=1,
        maximum=3650,
        **_LIVE,
    ),
    _s(
        "retention.datasets",
        SettingGroup.RETENTION,
        SettingType.DAYS,
        "Keep extracted datasets for",
        unit="days",
        minimum=1,
        maximum=3650,
        **_LIVE,
    ),
)

_SOURCES: Final = (
    _s(
        "sources.tiers",
        SettingGroup.SOURCES,
        SettingType.STATUS,
        "Source tiers T1-T5 (plan § 8.7)",
        "proposed",
        method=True,
        default_source="domain.deep_research.sources:SOURCE_TABLE_V1",
        **_LIVE,
    ),
    _s(
        "sources.reputation_register",
        SettingGroup.SOURCES,
        SettingType.STATUS,
        "The reputation register",
        "proposed",
        method=True,
        default_source="domain.deep_research.reputation:REPUTATION_REGISTER_V1",
        **_LIVE,
    ),
    _s(
        "sources.confidence_weights",
        SettingGroup.SOURCES,
        SettingType.STATUS,
        "The confidence weights",
        "proposed",
        method=True,
        default_source="domain.deep_research.confidence:CONFIDENCE_WEIGHTS_V1",
        **_LIVE,
    ),
)

#: Proposed with chunks 33-39 (plan § 9): at most this many hosts and pages per inventory run.
_EXTRACTION_CAPS: Final = {
    "deep": {"hosts": 3, "pages": 300, "pages_per_host": 100},
    "exhaustive": {"hosts": 6, "pages": 500, "pages_per_host": 200},
}

_EXTRACTION: Final = (
    _s(
        "extraction.denylist",
        SettingGroup.EXTRACTION,
        SettingType.HOST_LIST,
        "Hosts never crawled (their terms forbid automated collection)",
        (),
        method=True,
        **_LIVE,
    ),
    _s(
        "extraction.personal_data_patterns",
        SettingGroup.EXTRACTION,
        SettingType.PATTERN_LIST,
        "Further personal-data patterns (the built-in screen always runs)",
        (),
        method=True,
    ),
    _s(
        "extraction.record_presets",
        SettingGroup.EXTRACTION,
        SettingType.STATUS,
        "The record presets (product, price, store, organisation, event, listing)",
        "proposed",
        method=True,
        **_LIVE,
    ),
    *(
        _s(
            f"extraction.caps.{preset}.{field}",
            SettingGroup.EXTRACTION,
            SettingType.INTEGER,
            f"{preset.title()}: {field.replace('_', ' ')}",
            value,
            unit="per run",
            minimum=0,
            lower_only=True,
            method=True,
            default_source="plan deep-research-web-search.md § 9",
        )
        for preset, caps in _EXTRACTION_CAPS.items()
        for field, value in caps.items()
    ),
)

#: Every setting, in page order. Keys are unique (checked below).
CATALOGUE: Final[tuple[SettingDefinition, ...]] = (
    *_SIGN_OFF,
    *_PROVIDER,
    *_BUDGETS,
    *_PRESETS_STATUS,
    *_ALLOWANCES,
    *_LIMITS,
    *_MODELS,
    *_QUOTAS,
    *_RETENTION,
    *_SOURCES,
    *_EXTRACTION,
)

_BY_KEY: Final[Mapping[str, SettingDefinition]] = {d.key: d for d in CATALOGUE}
if len(_BY_KEY) != len(CATALOGUE):  # pragma: no cover - a defect in this module
    raise AssertionError("duplicate setting key in the catalogue")


def definition(key: str) -> SettingDefinition:
    """The catalogued setting ``key``, or :class:`SettingInvalid` when it is not one."""
    try:
        return _BY_KEY[key]
    except KeyError as exc:
        raise SettingInvalid(key, "is not a Deep Research setting") from exc


def validate(key: str, value: object) -> SettingValue:
    """``value`` for setting ``key`` in its normal form, or :class:`SettingInvalid`."""
    return validate_value(definition(key), value)


# --------------------------------------------------------------------------- #
# What is in force
# --------------------------------------------------------------------------- #


def _jsonable(value: SettingValue) -> object:
    return list(value) if isinstance(value, tuple) else value


@dataclass(frozen=True, slots=True)
class EffectiveSettings:
    """Every catalogued key's value in force, in catalogue order."""

    values: tuple[Effective, ...]

    def __getitem__(self, key: str) -> Effective:
        for item in self.values:
            if item.key == key:
                return item
        raise SettingInvalid(key, "is not a Deep Research setting")

    def value(self, key: str) -> SettingValue:
        return self[key].value

    def as_dict(self) -> dict[str, object]:
        return {e.key: _jsonable(e.value) for e in self.values}

    def digest(self) -> str:
        """Every value in force, with the catalogue's version: what a run pins."""
        return digest({"catalogue": CATALOGUE_VERSION, "values": self.as_dict()})

    def method_digest(self) -> str:
        """Only the values that shape a result: what a run's reuse keys carry (chunk 43)."""
        method = {e.key: _jsonable(e.value) for e in self.values if _BY_KEY[e.key].method}
        return digest({"catalogue": CATALOGUE_VERSION, "method": method})

    def missing_for_live(self) -> tuple[str, ...]:
        """Every setting live needs that is not approved -- or, for a status, not approved as
        ``approved`` (a table approved while still proposed is not signed off)."""
        missing = []
        for item in self.values:
            defn = _BY_KEY[item.key]
            if not defn.required_for_live:
                continue
            if item.origin is not Origin.APPROVED or (
                defn.type is SettingType.STATUS and item.value != "approved"
            ):
                missing.append(item.key)
        return tuple(missing)


def effective(approved: Mapping[str, ApprovedValue]) -> EffectiveSettings:
    """What is in force: each key's approved value, else its proposed default.

    ``approved`` holds the store's newest approval per key (a withdrawn key is absent). A key
    the catalogue does not hold is refused: a stored value nothing reads would be a guess.
    """
    unknown = sorted(set(approved) - set(_BY_KEY))
    if unknown:
        raise SettingInvalid(unknown[0], "is not a Deep Research setting")
    values: list[Effective] = []
    for defn in CATALOGUE:
        stored = approved.get(defn.key)
        if stored is None:
            values.append(Effective(defn.key, defn.default, Origin.PROPOSED_DEFAULT))
            continue
        values.append(
            Effective(
                defn.key,
                validate_value(defn, stored.value),
                Origin.APPROVED,
                version=stored.version,
                approved_by=stored.approved_by,
                approved_at=stored.approved_at,
            )
        )
    return EffectiveSettings(tuple(values))


def keys(group: SettingGroup | None = None) -> Iterable[str]:
    """Every catalogued key, or one group's, in page order."""
    return (d.key for d in CATALOGUE if group is None or d.group is group)


# --------------------------------------------------------------------------- #
# The run's pin (chunk 43)
# --------------------------------------------------------------------------- #

#: The pin's own contract: moves when what a pin stores changes.
SETTINGS_PIN_CONTRACT: Final = "aia-dr-settings-pin-1"


class SettingsPinCorrupt(ValueError):
    """A run's stored settings do not read, do not hash to their digest, or were pinned under
    another catalogue. The run is failed closed: it never runs under settings it cannot prove.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _pin_body(settings: EffectiveSettings) -> dict[str, object]:
    return {
        "contract": SETTINGS_PIN_CONTRACT,
        "catalogue": CATALOGUE_VERSION,
        "values": [
            {
                "key": e.key,
                "value": _jsonable(e.value),
                "origin": e.origin.value,
                "version": e.version,
                "approved_by": e.approved_by,
                "approved_at": None if e.approved_at is None else e.approved_at.isoformat(),
            }
            for e in settings.values
        ],
    }


def pin(settings: EffectiveSettings) -> dict[str, object]:
    """What a run stores of the settings in force at its enqueue (ADR 0022 decision 4).

    Every key's value *and* where it came from -- an approval (its version, who, when) or the
    code's proposed default -- so the run can later say what it ran under and whether live
    was approved (chunk 44). ``pin_digest`` covers the whole body; ``settings_digest`` and
    ``method_digest`` are :meth:`EffectiveSettings.digest` and
    :meth:`EffectiveSettings.method_digest`, the values a reuse key may carry.
    """
    body = _pin_body(settings)
    return {
        **body,
        "pin_digest": digest(body),
        "settings_digest": settings.digest(),
        "method_digest": settings.method_digest(),
    }


def read_pin(payload: object) -> EffectiveSettings:
    """The settings a run pinned, verified, or :class:`SettingsPinCorrupt`.

    The pin must name this contract and this catalogue (a pin from another catalogue is not
    re-read under this one's keys), hold every catalogued key once with a value the key's
    type accepts, and hash to every digest it states. Nothing is defaulted: a key missing
    from a pin is a corrupt pin, never the code's current default.
    """
    if not isinstance(payload, Mapping):
        raise SettingsPinCorrupt("pin_unreadable", "the run's settings pin is not an object")
    if payload.get("contract") != SETTINGS_PIN_CONTRACT:
        raise SettingsPinCorrupt(
            "pin_unreadable", f"the run's settings pin is not {SETTINGS_PIN_CONTRACT}"
        )
    if payload.get("catalogue") != CATALOGUE_VERSION:
        raise SettingsPinCorrupt(
            "catalogue_changed",
            f"the run pinned catalogue {payload.get('catalogue')!r}, not {CATALOGUE_VERSION}; "
            "start a new run",
        )
    rows = payload.get("values")
    if not isinstance(rows, list):
        raise SettingsPinCorrupt("pin_unreadable", "the run's settings pin holds no values")
    by_key: dict[str, Mapping[str, object]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("key"), str):
            raise SettingsPinCorrupt("pin_unreadable", "a pinned setting is not a keyed object")
        key = str(row["key"])
        if key in by_key:
            raise SettingsPinCorrupt("pin_unreadable", f"{key} is pinned twice")
        by_key[key] = row
    if set(by_key) != set(_BY_KEY):
        missing = sorted(set(_BY_KEY) - set(by_key))
        extra = sorted(set(by_key) - set(_BY_KEY))
        raise SettingsPinCorrupt(
            "pin_unreadable",
            f"the pin does not hold the catalogue: missing {missing}, extra {extra}",
        )
    values: list[Effective] = []
    try:
        for defn in CATALOGUE:
            row = by_key[defn.key]
            origin = Origin(str(row.get("origin")))
            raw = row.get("value")
            value = None if raw is None else validate_value(defn, raw, bound_by_default=False)
            at = row.get("approved_at")
            version = row.get("version")
            by = row.get("approved_by")
            values.append(
                Effective(
                    defn.key,
                    value,
                    origin,
                    version=version if isinstance(version, int) else None,
                    approved_by=by if isinstance(by, str) else None,
                    approved_at=datetime.fromisoformat(at) if isinstance(at, str) else None,
                )
            )
    except (SettingInvalid, ValueError) as exc:
        raise SettingsPinCorrupt(
            "pin_unreadable", f"a pinned setting does not read: {exc}"
        ) from exc
    settings = EffectiveSettings(tuple(values))
    if (
        digest(_pin_body(settings)) != payload.get("pin_digest")
        or settings.digest() != payload.get("settings_digest")
        or settings.method_digest() != payload.get("method_digest")
    ):
        raise SettingsPinCorrupt(
            "pin_altered", "the run's settings pin does not hash to its own digest"
        )
    return settings
