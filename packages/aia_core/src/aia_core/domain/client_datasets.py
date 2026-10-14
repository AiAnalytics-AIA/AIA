"""What a client's dataset holds, read before anyone decides what its columns mean (K2c).

A sheet (or a CSV) is previewed column by column: the header the first row gives, the kind
of values below it, how many cells are filled and how many distinct values they hold, and
a few sample values. What a column *means* -- an identifier, a demographic, an answer, a
weight -- is the person's to say (client-workspace C8, lifecycle K3); this module only
reads.

**Personal data.** A column whose header names a person, an address, an e-mail or a phone,
or where at least ``PERSONAL_SHARE`` of the filled cells look like an e-mail, a phone number
or a Czech birth number, carries a :class:`PersonalHint`, and its samples are masked. The
detector errs towards flagging: a false flag costs a person one click, a missed one shows a
client's customer list on a screen. Its patterns are pinned by a fixture of fictional values
(``fixtures/client_datasets/personal.json``).

**The header rule.** Row 1 is the header when every filled cell in it reads as text and some
filled cell below it does not -- a number or a date. Otherwise there is no header and the
columns are named by their letters. The rule is the reader's; a person can say otherwise.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "DISTINCT_CAP",
    "MASK",
    "PERSONAL_SHARE",
    "SAMPLE_SIZE",
    "ColumnKind",
    "ColumnPreview",
    "DatasetPreview",
    "PersonalHint",
    "SheetPreview",
    "column_letters",
    "kind_of",
    "personal_value",
    "preview_sheet",
]

#: Distinct values counted per column; past it the count says "at least".
DISTINCT_CAP: Final = 1000
#: Sample values kept per column.
SAMPLE_SIZE: Final = 5
#: The share of a column's filled cells that must look personal for it to be flagged.
PERSONAL_SHARE: Final = 0.3
#: What a masked sample value reads as.
MASK: Final = "•••"


class ColumnKind(StrEnum):
    """What the filled cells below the header read as."""

    EMPTY = "EMPTY"
    NUMBER = "NUMBER"
    DATE = "DATE"
    TEXT = "TEXT"
    #: Some cells read as one kind and some as another.
    MIXED = "MIXED"


class PersonalHint(StrEnum):
    """Why a column is treated as personal data."""

    EMAIL = "EMAIL"
    PHONE = "PHONE"
    BIRTH_NUMBER = "BIRTH_NUMBER"
    PERSON_NAME = "PERSON_NAME"
    ADDRESS = "ADDRESS"


_NUMBER: Final = re.compile(r"^[+-]?(\d{1,3}([ \xa0.]\d{3})+|\d+)([.,]\d+)?\s?%?$|^[+-]?[.,]\d+$")
_DATE: Final = re.compile(
    r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$|^\d{1,2}\.\s?\d{1,2}\.\s?\d{4}$"
)
_EMAIL: Final = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
# A Czech number with or without +420/00420, in groups of three; or nine digits plain.
_PHONE: Final = re.compile(r"^(\+|00)420[ ]?\d{3}[ ]?\d{3}[ ]?\d{3}$|^\d{3}[ ]\d{3}[ ]\d{3}$")
# YYMMDD/XXXX or YYMMDD/XXX, with or without the slash.
_BIRTH: Final = re.compile(r"^(\d{2})(\d{2})(\d{2})/?(\d{3,4})$")

# A header's words that name a person, an address or a contact; accent-folded, lower-case.
_HEADER_HINTS: Final[tuple[tuple[frozenset[str], PersonalHint], ...]] = (
    (frozenset({"email", "e-mail", "mail", "emailova", "e-mailova"}), PersonalHint.EMAIL),
    (frozenset({"telefon", "phone", "mobil", "mobile", "tel", "tel."}), PersonalHint.PHONE),
    (frozenset({"rodne", "rc", "r.c.", "birth"}), PersonalHint.BIRTH_NUMBER),
    (
        frozenset({"jmeno", "prijmeni", "name", "surname", "firstname", "lastname"}),
        PersonalHint.PERSON_NAME,
    ),
    (frozenset({"adresa", "ulice", "address", "street", "bydliste"}), PersonalHint.ADDRESS),
)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def kind_of(value: str) -> ColumnKind:
    """What one filled cell reads as: a number, a date, or text."""
    text = value.strip()
    if not text:
        return ColumnKind.EMPTY
    if _PHONE.match(text):
        # A phone number is an identifier, however much it looks like grouped digits.
        return ColumnKind.TEXT
    if _NUMBER.match(text):
        return ColumnKind.NUMBER
    if _DATE.match(text):
        return ColumnKind.DATE
    return ColumnKind.TEXT


def _birth_number(text: str) -> bool:
    found = _BIRTH.match(text.replace(" ", ""))
    if not found:
        return False
    month = int(found.group(2))
    day = int(found.group(3))
    # A woman's month is +50; since 2004 either may also be +20 (70+ or 20+).
    for shift in (70, 50, 20, 0):
        if month > shift:
            month -= shift
            break
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        return False
    digits = "".join(found.groups())
    if len(digits) == 10:
        # A ten-digit number divides by 11 (the rule since 1954; a remainder of 10 ended in 0).
        whole = int(digits)
        return whole % 11 == 0 or (int(digits[:9]) % 11 == 10 and digits[9] == "0")
    return True


def personal_value(value: str) -> PersonalHint | None:
    """What a single value looks like, if it looks like a person's data."""
    text = value.strip()
    if _EMAIL.match(text):
        return PersonalHint.EMAIL
    if _PHONE.match(text):
        return PersonalHint.PHONE
    if _birth_number(text):
        return PersonalHint.BIRTH_NUMBER
    return None


def _header_hint(header: str | None) -> PersonalHint | None:
    if not header:
        return None
    words = set(re.split(r"[\s_/()\-:,;]+", _fold(header))) | {_fold(header).strip()}
    for keys, hint in _HEADER_HINTS:
        # A word matches a key, or begins with one of five letters or more: Czech endings
        # ("telefonní", "adresy") keep their stem.
        if any(w == k or (len(k) >= 5 and w.startswith(k)) for w in words for k in keys):
            return hint
    return None


def column_letters(index: int) -> str:
    """``1`` -> ``A``, ``27`` -> ``AA``."""
    out = ""
    while index > 0:
        index, rest = divmod(index - 1, 26)
        out = chr(ord("A") + rest) + out
    return out


class ColumnPreview(BaseModel):
    """One column as read: its header, kind, fill and a few values (masked when personal)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=1)
    letter: str
    header: str | None
    kind: ColumnKind
    filled: int = Field(ge=0)
    distinct: int = Field(ge=0)
    #: True when there were more distinct values than ``DISTINCT_CAP``.
    distinct_capped: bool = False
    personal: PersonalHint | None = None
    sample: tuple[str, ...] = ()


class SheetPreview(BaseModel):
    """One sheet (or the CSV) as read. ``rows`` counts the rows below the header."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: The sheet's name; a CSV has none.
    name: str | None
    header_row: int | None
    rows: int = Field(ge=0)
    columns: tuple[ColumnPreview, ...]
    #: A bound stopped the reader: rows, columns or cells past it were not read.
    truncated: bool = False


class DatasetPreview(BaseModel):
    """A dataset's sheets as read; ``more_sheets`` when the workbook had more than were read."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sheets: tuple[SheetPreview, ...]
    more_sheets: bool = False


def preview_sheet(
    name: str | None, rows: Sequence[tuple[int, Sequence[str]]], *, truncated: bool = False
) -> SheetPreview:
    """A sheet's preview from its non-empty rows as ``(row number, values)``, in order."""
    width = max((len(values) for _, values in rows), default=0)
    first = rows[0] if rows else None
    header_row: int | None = None
    if first is not None and len(rows) > 1:
        head_kinds = {kind_of(v) for v in first[1] if v.strip()}
        below = any(
            kind_of(v) in (ColumnKind.NUMBER, ColumnKind.DATE)
            for _, values in rows[1:]
            for v in values
        )
        if head_kinds == {ColumnKind.TEXT} and below:
            header_row = first[0]
    body = rows[1:] if header_row is not None else rows
    columns: list[ColumnPreview] = []
    for i in range(width):
        header = None
        if header_row is not None and first is not None and i < len(first[1]):
            header = first[1][i].strip() or None
        values = [values[i].strip() for _, values in body if i < len(values) and values[i].strip()]
        kinds = {kind_of(v) for v in values}
        kind = (
            ColumnKind.EMPTY
            if not kinds
            else next(iter(kinds))
            if len(kinds) == 1
            else ColumnKind.MIXED
        )
        distinct: set[str] = set()
        capped = False
        for v in values:
            if v not in distinct:
                if len(distinct) >= DISTINCT_CAP:
                    capped = True
                    break
                distinct.add(v)
        hint = _header_hint(header)
        if hint is None and values:
            looks = [personal_value(v) for v in values]
            found = [h for h in looks if h is not None]
            if found and len(found) >= PERSONAL_SHARE * len(values):
                hint = max(set(found), key=found.count)
        sample: list[str] = []
        for v in values:
            if v not in sample:
                sample.append(v)
            if len(sample) >= SAMPLE_SIZE:
                break
        columns.append(
            ColumnPreview(
                index=i + 1,
                letter=column_letters(i + 1),
                header=header,
                kind=kind,
                filled=len(values),
                distinct=len(distinct),
                distinct_capped=capped,
                personal=hint,
                sample=tuple(MASK for _ in sample) if hint else tuple(sample),
            )
        )
    return SheetPreview(
        name=name,
        header_row=header_row,
        rows=len(body),
        columns=tuple(columns),
        truncated=truncated,
    )
