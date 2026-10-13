"""The holdout item bank: the questions a validation may ask, in the words they were fielded in.

A panel field's answers are a survey's measured responses, but the population dictionary does
not carry the question that was asked (``population/policy.py`` ``POLICY_COLUMNS``). A
validation that asked a question in words AIA chose would test AIA's wording, not the
respondent system. So each item carries the source questionnaire's Czech wording and options
as fielded, the panel code each option is stored as, and the document they were read from
(its URL, the SHA-256 of the file read, the page): a person can check every item against its
source (panel-grounded-respondents 7a, 7g).

The bank is a JSON document, pinned by the SHA-256 of its canonical form. :func:`read_item_bank`
refuses a bank that is not well formed, by name; it never repairs one.

Pure: stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

__all__ = [
    "BANK_VERSION",
    "MAX_OPTIONS",
    "SURVEYS",
    "HoldoutItem",
    "ItemBank",
    "ItemBankRefused",
    "Option",
    "SourceDocument",
    "canonical_json",
    "item_payload",
    "read_item",
    "read_item_bank",
]

BANK_VERSION: Final = "aia-holdout-bank-1"

#: The surveys the panel is built from (``DONOR_BLOCK_REGISTRY.json``, ``CORE_JOINT_STATUS.json``,
#: 17.x): the two cores and the six matched blocks. An item from any other survey is not a
#: panel field's source, so it cannot be held out of the panel.
SURVEYS: Final = frozenset(
    {
        "PIAAC_2023_CZ",
        "ISSP_2022_CZ",
        "NUDZ_CAPI_2022",
        "JRC_LONELINESS_CZ_2022",
        "QOG_EQI_CZ_2024",
        "CSDA_RULE_OF_LAW_2024",
        "CSES_M5_CZE_2021",
    }
)

#: A closed item the respondent contract can answer: a single choice of 2-11 options or an
#: ordinal scale of at most 11 points (7a, eligibility 2).
MAX_OPTIONS: Final = 11
_MIN_OPTIONS: Final = 2
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_MIN_AGE: Final = 15
_MAX_AGE: Final = 120


class ItemBankRefused(ValueError):
    """The bank is not well formed. ``reason`` names the rule; nothing is repaired."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class Option:
    """One answer option: the code the panel stores it as, and its label as fielded."""

    code: str
    label: str


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """Where an item's wording was read: a public document, its bytes' hash, the page."""

    url: str
    sha256: str
    page: str
    item_id: str


@dataclass(frozen=True, slots=True)
class HoldoutItem:
    """One question a validation may hold out of the persona and ask."""

    field: str
    survey: str
    domain: str
    wording: str
    options: tuple[Option, ...]
    #: The ages the survey asked it of (a core item: PIAAC 18-65, ISSP 66+); ``None`` for a
    #: matched block, whose donor answered it for every row it was matched to.
    measured_ages: tuple[int, int] | None
    #: True when the options are ordered (a scale), so association with it is a correlation.
    ordinal: bool
    source: SourceDocument

    @property
    def codes(self) -> tuple[str, ...]:
        """The option codes, in the order fielded."""
        return tuple(o.code for o in self.options)


@dataclass(frozen=True, slots=True)
class ItemBank:
    """Every item, and the hash that pins the bank."""

    items: tuple[HoldoutItem, ...]
    sha256: str

    def item(self, field: str) -> HoldoutItem:
        """The item for ``field``. Raises ``KeyError`` for a field the bank lacks."""
        for item in self.items:
            if item.field == field:
                return item
        raise KeyError(field)


def canonical_json(obj: Any) -> bytes:
    """The bytes a record is hashed over: sorted keys, no whitespace, UTF-8 (18.6.6's
    ``holdout_protocol._canonical``, ``holdout_protocol.py:23-28``)."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _refuse(message: str, reason: str) -> ItemBankRefused:
    return ItemBankRefused(message, reason=reason)


def _text(raw: Mapping[str, Any], key: str, where: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _refuse(f"{where}: {key!r} must be non-blank text", "item_bank_malformed")
    return value


def _ages(value: Any, where: str) -> tuple[int, int] | None:
    if value is None:
        return None
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(v, int) and not isinstance(v, bool) for v in value)
    ):
        raise _refuse(f"{where}: measured_ages must be [min, max] or null", "item_bank_malformed")
    low, high = value
    if not _MIN_AGE <= low <= high <= _MAX_AGE:
        raise _refuse(f"{where}: measured_ages {value} is not an age range", "item_bank_malformed")
    return (low, high)


def _options(value: Any, where: str) -> tuple[Option, ...]:
    if not isinstance(value, list):
        raise _refuse(f"{where}: options must be a list", "item_bank_malformed")
    if not _MIN_OPTIONS <= len(value) <= MAX_OPTIONS:
        raise _refuse(
            f"{where}: {len(value)} options; a closed item has {_MIN_OPTIONS}-{MAX_OPTIONS}",
            "item_not_closed",
        )
    options = []
    for i, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise _refuse(f"{where}: option {i} must be an object", "item_bank_malformed")
        options.append(
            Option(_text(raw, "code", f"{where} option {i}"), _text(raw, "label", f"{where}"))
        )
    codes = [o.code for o in options]
    if len(set(codes)) != len(codes):
        raise _refuse(f"{where}: option codes repeat", "item_bank_malformed")
    # The respondent answers with a label and code maps it back to its code: a label shown
    # twice could not say which code was meant.
    labels = [o.label for o in options]
    if len(set(labels)) != len(labels):
        raise _refuse(f"{where}: option labels repeat", "item_bank_malformed")
    return tuple(options)


def _source(value: Any, where: str) -> SourceDocument:
    if not isinstance(value, Mapping):
        raise _refuse(f"{where}: source must be an object", "item_source_missing")
    url = _text(value, "url", f"{where} source")
    if not url.startswith("https://"):
        raise _refuse(f"{where}: the source must be a public https document", "item_source_missing")
    sha = _text(value, "sha256", f"{where} source")
    if not _SHA256.match(sha):
        raise _refuse(f"{where}: the source's sha256 is not a SHA-256", "item_source_missing")
    return SourceDocument(
        url=url,
        sha256=sha,
        page=_text(value, "page", f"{where} source"),
        item_id=_text(value, "item_id", f"{where} source"),
    )


def _item(raw: Any, i: int) -> HoldoutItem:
    where = f"item {i}"
    if not isinstance(raw, Mapping):
        raise _refuse(f"{where} must be an object", "item_bank_malformed")
    field = _text(raw, "field", where)
    where = f"item {field!r}"
    survey = _text(raw, "survey", where)
    if survey not in SURVEYS:
        raise _refuse(f"{where}: {survey!r} is not a survey the panel is built from", "item_survey")
    ordinal = raw.get("ordinal")
    if not isinstance(ordinal, bool):
        raise _refuse(f"{where}: ordinal must be true or false", "item_bank_malformed")
    return HoldoutItem(
        field=field,
        survey=survey,
        domain=_text(raw, "domain", where),
        wording=_text(raw, "wording", where),
        options=_options(raw.get("options"), where),
        measured_ages=_ages(raw.get("measured_ages"), where),
        ordinal=ordinal,
        source=_source(raw.get("source"), where),
    )


def read_item(raw: Any) -> HoldoutItem:
    """One item as :func:`item_payload` wrote it, checked as the bank's are."""
    return _item(raw, 0)


def item_payload(item: HoldoutItem) -> dict[str, Any]:
    """An item as the bank's JSON holds it; :func:`read_item` reads it back."""
    return {
        "field": item.field,
        "survey": item.survey,
        "domain": item.domain,
        "wording": item.wording,
        "options": [{"code": o.code, "label": o.label} for o in item.options],
        "measured_ages": list(item.measured_ages) if item.measured_ages is not None else None,
        "ordinal": item.ordinal,
        "source": {
            "url": item.source.url,
            "sha256": item.source.sha256,
            "page": item.source.page,
            "item_id": item.source.item_id,
        },
    }


def read_item_bank(data: bytes) -> ItemBank:
    """Read and check a bank. Its hash is over its canonical form, so formatting never moves it."""
    try:
        document = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _refuse(f"the bank is not JSON: {exc}", "item_bank_malformed") from None
    if not isinstance(document, Mapping) or document.get("bank_version") != BANK_VERSION:
        raise _refuse(f"the bank must declare bank_version {BANK_VERSION!r}", "item_bank_version")
    raw_items = document.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise _refuse("the bank has no items", "item_bank_malformed")
    items = tuple(_item(raw, i) for i, raw in enumerate(raw_items))
    fields = [item.field for item in items]
    if len(set(fields)) != len(fields):
        raise _refuse("a field appears twice in the bank", "item_bank_malformed")
    return ItemBank(items=items, sha256=hashlib.sha256(canonical_json(document)).hexdigest())
