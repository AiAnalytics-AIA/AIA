"""Measures: what a number in a claim *means*, read by code, checked against its source.

Plan ``deep-research-web-search.md`` § 8.1 and chunk 7. Grounding already proves
that every number in a claim is in its quote (``number_not_in_quote``). That is
not enough: "45 % domácností" in the source and "45 % dospělých" in the claim have
the same digits and say different things. This module reads, for each number a
claim states, the words that make it that number -- its unit, scale, period,
geography, population and denominator -- and :func:`check_measures` asks whether
the quote's context in the source says the same. A mis-statement is quarantined as
``measure_not_in_source``; an *omission* is not (a claim that drops the
population is the verifier's concern, not a mis-statement this check can prove).

**The vocabulary** is closed and versioned (:data:`MEASURES_VERSION`): Czech
units, scale words, periods, population nouns and geography, matched on
:func:`fold` (NFKC, no diacritics, case-folded) by explicit inflected forms or by
stems long enough not to collide (``domacnost*`` yes; ``muz*`` no, because
"může" folds to "muze"). A change to it is a change to grounding, and
``grounding.GROUNDING_VERSION`` carries this version, so a track grounded under
the old vocabulary is not reused under the new one.

**Attaching a term to a number** (the claim side; the same rule reads the source):

* *scale* and *unit* only where they are written right after the number ("450
  tis. domácností", "2,1 mld. Kč", "41 milionů litrů"), or a currency sign right
  before it ("€ 45");
* *denominator*: "na", "za", "per" or "/" right after the unit (or the number),
  then a unit or a population noun ("42 Kč za litr", "3 l na osobu");
* *population*: the population nouns within :data:`ATTACH_AFTER` tokens after the
  number ("45 % všech dospělých lidí"), or, when there are none, within
  :data:`ATTACH_BEFORE` tokens before it ("mezi dospělými je to 45 %"); in the
  same clause, never past another number;
* *period* and *geography*: anywhere in the number's clause ("v březnu 2025",
  "v Česku").

A clause ends at ``; : ( ) [ ]``, a spaced dash, a comma that is not a decimal
comma, and a sentence end. A year (a whole number from 1900 to 2099 written with four
digits and no unit) and an ordinal quarter are periods, not measures: they carry
no population of their own, so a claim whose only number is a year is not read.

**Periods** (keys): a year ``Y2025``, a season ``Y2024/2025``; a quarter, half or
month is placed in the year written right after it ("ve 2. čtvrtletí 2025",
"v březnu roku 2025", "Q2/2025") as ``2025-Q2``, ``2025-H1``, ``2025-03``; with
no year next to it, it stays ``Q2``, ``H1``, ``M03`` and is never placed in a year
written elsewhere. A date is one period, and its day and month are not numbers:

* ``31. 12. 2091`` and ``31.12.2091`` -- a numeric day and month count only with
  their year, so "vzrostl o 12. 12 obchodů" is two numbers;
* ``2091-12-31`` (ISO);
* ``31. prosince`` / ``1. ledna 2025`` / ``k 31. prosinci roku 2091`` -- a month
  name in any case, in lower case: "o 12. Prosinec byl..." starts a new sentence,
  and its 12 is a number. "vzrostl o 12. Poté..." is a number at a sentence end.

A date is ``2091-12-31``, or ``M12-31`` with no year; an impossible one (31. 2.)
is no date. A placed period also names its year and its yearless part, so a
source writing "ve 2. čtvrtletí 2025" names 2025 and ``Q2`` too.

**The context window** (:func:`context_window`) is the source's sentence(s) the
quote stands in, one sentence either side, at most :data:`CONTEXT_MAX_CHARS`
characters either side of the quote, never cutting a word. Snapshot text is
normalised (``grounding.normalise_text``), so paragraph breaks are not kept and a
sentence is the unit; a table read as a grid (chunk 6) will bring its own window.

**The check** (:func:`check_measures`), for every number the claim states that is
not a period, against every occurrence of the same value in the window:

* *scale* -- the claim's scale (1 when it writes none) is a scale the source
  writes on that value, or the source writes the value bare and names the claim's
  scale elsewhere in the window (a header, "v tis."). "450" for "450 tis." fails;
* *unit* -- a unit the claim writes is the source's on that value, or the source
  writes the value bare and names the unit elsewhere in the window;
* *denominator* -- named in the window;
* *population* -- named in the window, and, where the source attaches population
  nouns to that value itself, one of them ("45 % domácností, tedy 1,9 milionu
  lidí" does not make the 45 % a share of people);
* *period* -- named in the window ("2023" is not "2023/24", March is not
  January, Q3 is not Q1), or, for a placed one, its yearless part and its year
  both named ("V roce 2025: ... ve 2. čtvrtletí" names ``2025-Q2``; "2. čtvrtletí
  2024 ... rok 2025" does not);
* *geography* -- when the window names any geography, it names the claim's (a
  Prague figure claimed for the whole country fails; a page that names no place
  leaves the claim's place to the verifier).

Pure: stdlib only.
"""

from __future__ import annotations

import re
import unicodedata
from bisect import bisect_left, bisect_right
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Final

from ..analysis.draft import number_spans
from .contracts import Measure

__all__ = [
    "ATTACH_AFTER",
    "ATTACH_BEFORE",
    "CONTEXT_MAX_CHARS",
    "CONTEXT_SENTENCES",
    "MEASURES_VERSION",
    "STATED_MEASURES_VERSION",
    "Attribute",
    "MeasureMismatch",
    "StatedMeasureProblem",
    "StatedNumber",
    "Term",
    "check_measures",
    "check_stated_measures",
    "claim_measures",
    "context_window",
    "fold",
    "normalised_measure",
    "render_measure",
    "stated_numbers",
]

#: The vocabulary and the attachment rule's version; carried by GROUNDING_VERSION.
#: aia-measures-2: a written date is one period, never its day and month as numbers,
#: and a quarter, half or month is placed in the year written next to it.
MEASURES_VERSION: Final = "aia-measures-2"

#: Tokens before / after a number in which a population noun is attached to it.
ATTACH_BEFORE: Final = 3
ATTACH_AFTER: Final = 6
#: Whole sentences of the source taken on either side of the quote's own.
CONTEXT_SENTENCES: Final = 1
#: The window never reaches further than this either side of the quote.
CONTEXT_MAX_CHARS: Final = 400


class Attribute(StrEnum):
    """What a term says about a number."""

    UNIT = "unit"
    SCALE = "scale"
    PERIOD = "period"
    POPULATION = "population"
    DENOMINATOR = "denominator"
    GEOGRAPHY = "geography"


def fold(text: str) -> str:
    """The matching form: NFKC, diacritics removed, case-folded."""
    decomposed = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", text))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


# --------------------------------------------------------------------------- #
# The vocabulary (MEASURES_VERSION). Every form is folded.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _Forms:
    """A word's accepted spellings: exact folded forms, and stems it may start with."""

    exact: frozenset[str] = frozenset()
    stems: tuple[str, ...] = ()

    def match(self, word: str) -> bool:
        return word in self.exact or any(word.startswith(s) for s in self.stems)


def _forms(exact: Iterable[str] = (), stems: Iterable[str] = ()) -> _Forms:
    return _Forms(frozenset(exact), tuple(stems))


def _words(text: str) -> tuple[str, ...]:
    """A list of forms written as one space-separated string."""
    return tuple(text.split())


#: Population and denominator nouns, by class. Words of one class name the same
#: population ("obyvatel" and "osob"); different classes never match each other.
POPULATIONS: Final[Mapping[str, _Forms]] = {
    "HOUSEHOLDS": _forms(stems=("domacnost",)),
    "PERSONS": _forms(
        # Explicit forms: the stems "osob" and "lid" would take "osobní" and "lidový".
        exact=_words(
            "osoba osoby osob osobam osobach osobami osobe osobu osobou "
            "lid lide lidi lidem lidmi lidech lidu clovek cloveka cloveku clovekem "
            "jedinec jedincu jedince jedinci jedincum"
        ),
        stems=("obyvatel", "obcan"),
    ),
    "ADULTS": _forms(
        exact=tuple(
            "dospel" + e for e in ("y", "ych", "ym", "ymi", "i", "e", "eho", "emu", "ou", "a")
        )
    ),
    "RESPONDENTS": _forms(stems=("respondent", "dotazan", "dotazovan")),
    "CONSUMERS": _forms(stems=("spotrebitel",)),
    "CUSTOMERS": _forms(stems=("zakaznik",)),
    "USERS": _forms(stems=("uzivatel",)),
    "FIRMS": _forms(exact=("firem",), stems=("firm", "podnik", "spolecnost")),
    "PUPILS": _forms(
        exact=("zak", "zaka", "zaku", "zaci", "zaky", "zakum", "zacich", "zakem", "zakyne", "zakyn")
    ),
    "STUDENTS": _forms(stems=("student",)),
    "MEN": _forms(
        exact=("muz", "muzi", "muzu", "muzum", "muzich", "muzove", "muzem"), stems=("muzsk",)
    ),
    "WOMEN": _forms(
        exact=("zena", "zeny", "zen", "zene", "zenam", "zenach", "zenami", "zenu", "zenou"),
        stems=("zensk",),
    ),
    "CHILDREN": _forms(
        exact=("deti", "detem", "detmi", "detech", "dite", "ditete", "diteti", "ditetem")
    ),
    "SENIORS": _forms(stems=("senior",)),
}

#: Units, by key. Single letters count only right after a number.
UNITS: Final[Mapping[str, _Forms]] = {
    "%": _forms(stems=("procent",)),
    "CZK": _forms(exact=("kc", "czk"), stems=("korun",)),
    "EUR": _forms(exact=("eur", "euro", "eura", "eurum", "eurech", "eury")),
    "USD": _forms(exact=("usd",), stems=("dolar",)),
    "l": _forms(exact=("l",), stems=("litr",)),
    "hl": _forms(exact=("hl",), stems=("hektolitr",)),
    "ml": _forms(exact=("ml",), stems=("mililitr",)),
    "kg": _forms(exact=("kg",), stems=("kilogram",)),
    "g": _forms(exact=("g",), stems=("gram",)),
    "t": _forms(exact=("t", "tuna", "tun", "tuny", "tunach", "tunami", "tunu", "tune", "tunam")),
    "ks": _forms(exact=("ks", "kus", "kusy", "kusu", "kusech", "kusum", "kusem")),
}
_UNIT_SIGNS: Final = {"%": "%", "€": "EUR", "$": "USD"}
#: Percentage points: "p. b.", "p.b.", "procentní bod(y/ů)". Never the same as %.
PERCENTAGE_POINTS: Final = "pp"

#: Scale words. An abbreviation counts only with its full stop ("tis.", "mil.").
SCALES: Final[Mapping[int, tuple[_Forms, frozenset[str]]]] = {
    1_000: (_forms(stems=("tisic",)), frozenset({"tis"})),
    1_000_000: (_forms(exact=("mio",), stems=("milion",)), frozenset({"mil"})),
    1_000_000_000: (_forms(exact=("mld",), stems=("miliard",)), frozenset()),
}

#: Months by number, every case form.
MONTHS: Final[Mapping[int, frozenset[str]]] = {
    1: frozenset({"leden", "ledna", "lednu", "lednem"}),
    2: frozenset({"unor", "unora", "unoru", "unorem"}),
    3: frozenset({"brezen", "brezna", "breznu", "breznem"}),
    4: frozenset({"duben", "dubna", "dubnu", "dubnem"}),
    5: frozenset({"kveten", "kvetna", "kvetnu", "kvetnem"}),
    6: frozenset({"cerven", "cervna", "cervnu", "cervnem"}),
    7: frozenset({"cervenec", "cervence", "cervenci", "cervencem"}),
    8: frozenset({"srpen", "srpna", "srpnu", "srpnem"}),
    9: frozenset({"zari", "zarim"}),
    10: frozenset({"rijen", "rijna", "rijnu", "rijnem"}),
    11: frozenset({"listopad", "listopadu", "listopadem"}),
    12: frozenset({"prosinec", "prosince", "prosinci", "prosincem"}),
}
_ORDINALS: Final = {
    1: ("prvni", "prvnim", "i"),
    2: ("druhe", "druhem", "ii"),
    3: ("treti", "tretim", "iii"),
    4: ("ctvrte", "ctvrtem", "iv"),
}
_QUARTER: Final = re.compile(r"^(?:q([1-4])|([1-4])q)$")

#: Geography, by key: the country, the EU, Prague and the 14 regions (ISO 3166-2:CZ
#: region letters) with their regional capitals.
GEOGRAPHY: Final[Mapping[str, _Forms]] = {
    "CZ": _forms(exact=("cr", "cz", "cesko", "ceska", "cesku"), stems=("cesk",)),
    "SK": _forms(exact=("sr", "sk"), stems=("slovensk",)),
    "EU": _forms(exact=("eu", "eu27")),
    "EUROPE": _forms(stems=("evrop",)),
    "CZ-PR": _forms(exact=("praha", "prahy", "praze", "prahu", "prahou"), stems=("prazsk",)),
    "CZ-ST": _forms(stems=("stredocesk",)),
    "CZ-JC": _forms(stems=("jihocesk", "budejovic")),
    "CZ-PL": _forms(exact=("plzen", "plzne", "plzni"), stems=("plzensk",)),
    "CZ-KA": _forms(stems=("karlovarsk",)),
    "CZ-US": _forms(stems=("usteck",)),
    "CZ-LI": _forms(stems=("libereck", "liberec", "liberc")),
    "CZ-KR": _forms(stems=("kralovehradeck",)),
    "CZ-PA": _forms(stems=("pardubic",)),
    "CZ-VY": _forms(stems=("vysocin", "jihlav")),
    "CZ-JM": _forms(
        exact=("brno", "brna", "brne", "brnu", "brnem"), stems=("jihomoravsk", "brnensk")
    ),
    "CZ-OL": _forms(stems=("olomouc",)),
    "CZ-ZL": _forms(exact=("zlin", "zlina", "zline", "zlinem"), stems=("zlinsk",)),
    "CZ-MO": _forms(stems=("moravskoslezsk", "ostrav")),
}
#: Longest stem first, so "jihocesk" is a region before "cesk" could be the country.
_GEOGRAPHY_ORDER: Final = sorted(
    GEOGRAPHY, key=lambda k: -max((len(s) for s in GEOGRAPHY[k].stems), default=0)
)

#: Words after which a full stop does not end a sentence.
_ABBREVIATIONS: Final = frozenset(
    {"tis", "mil", "mld", "tzv", "napr", "resp", "cca", "c", "r", "p", "b", "mj", "tj", "popr"}
)
_DENOMINATOR_WORDS: Final = frozenset({"na", "za", "per"})


# --------------------------------------------------------------------------- #
# Tokens and clauses
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str  # "num" | "word" | "sign"
    start: int
    end: int
    text: str
    folded: str
    value: float = 0.0
    decimals: int = 0
    dot_after: bool = False


_WORD: Final = re.compile(r"[^\W_]+")
_SIGN: Final = re.compile(r"[%€$/]")
_SENTENCE_END: Final = re.compile(r"[.!?]+[\"')\]]*\s+(?=[\"'(\[]?\w)")
_CLAUSE_MARK: Final = re.compile(r"[;:()\[\]]|\s-\s|,(?!\d)|(?<!\d),")


def _tokens(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    numbers = number_spans(text)
    taken = [(start, end) for _, _, start, end in numbers]
    for value, decimals, start, end in numbers:
        raw = text[start:end]
        tokens.append(
            _Token("num", start, end, raw, raw, value, decimals, text[end : end + 1] == ".")
        )
    for m in _WORD.finditer(text):
        if any(s < m.end() and m.start() < e for s, e in taken):
            continue
        tokens.append(
            _Token(
                "word",
                m.start(),
                m.end(),
                m[0],
                fold(m[0]),
                dot_after=text[m.end() : m.end() + 1] == ".",
            )
        )
    for m in _SIGN.finditer(text):
        tokens.append(_Token("sign", m.start(), m.end(), m[0], m[0]))
    return sorted(tokens, key=lambda t: t.start)


def _sentence_starts(text: str) -> list[int]:
    """Where each sentence after the first begins."""
    starts = []
    for m in _SENTENCE_END.finditer(text):
        rest = text[m.end() :].lstrip("\"'([")
        if not rest or not rest[0].isupper():
            continue
        if text[m.start()] == ".":
            before = re.search(r"([^\W\d_]+)$", text[: m.start()])
            if before and fold(before[1]) in _ABBREVIATIONS:
                continue
        starts.append(m.end())
    return starts


def _clause_breaks(text: str) -> list[int]:
    breaks = [m.start() for m in _CLAUSE_MARK.finditer(text)]
    breaks.extend(_sentence_starts(text))
    return sorted(breaks)


# --------------------------------------------------------------------------- #
# Terms
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Term:
    """One attribute as written: what it says, its normalised key, and its words."""

    attribute: Attribute
    key: str
    text: str


def _match(table: Mapping[str, _Forms], word: str, order: Sequence[str] | None = None) -> str:
    for key in order or table:
        if table[key].match(word):
            return key
    return ""


def _scale_at(tokens: Sequence[_Token], i: int) -> tuple[Term, int] | None:
    if i >= len(tokens) or tokens[i].kind != "word":
        return None
    tok = tokens[i]
    for scale, (forms, needs_dot) in SCALES.items():
        if tok.folded in needs_dot and not tok.dot_after:
            continue
        if forms.match(tok.folded) or tok.folded in needs_dot:
            abbreviated = tok.dot_after and tok.folded in _ABBREVIATIONS
            return Term(Attribute.SCALE, str(scale), tok.text + ("." if abbreviated else "")), 1
    return None


def _unit_at(tokens: Sequence[_Token], i: int, attribute: Attribute) -> tuple[Term, int] | None:
    if i >= len(tokens):
        return None
    tok = tokens[i]
    if tok.kind == "sign" and tok.text in _UNIT_SIGNS:
        return Term(attribute, _UNIT_SIGNS[tok.text], tok.text), 1
    if tok.kind != "word":
        return None
    nxt = tokens[i + 1] if i + 1 < len(tokens) else None
    if nxt is not None and nxt.kind == "word":
        if tok.folded == "p" and tok.dot_after and nxt.folded == "b":
            return Term(attribute, PERCENTAGE_POINTS, f"{tok.text}. {nxt.text}."), 2
        if tok.folded.startswith("procentn") and nxt.folded.startswith("bod"):
            return Term(attribute, PERCENTAGE_POINTS, f"{tok.text} {nxt.text}"), 2
    key = _match(UNITS, tok.folded)
    return (Term(attribute, key, tok.text), 1) if key else None


def _population(tok: _Token, attribute: Attribute = Attribute.POPULATION) -> Term | None:
    if tok.kind != "word":
        return None
    key = _match(POPULATIONS, tok.folded)
    return Term(attribute, key, tok.text) if key else None


def _geography(tokens: Sequence[_Token], i: int) -> Term | None:
    tok = tokens[i]
    if tok.kind != "word":
        return None
    nxt = tokens[i + 1] if i + 1 < len(tokens) else None
    if tok.folded.startswith("evropsk") and nxt is not None and nxt.folded.startswith("uni"):
        return Term(Attribute.GEOGRAPHY, "EU", f"{tok.text} {nxt.text}")
    key = _match(GEOGRAPHY, tok.folded, _GEOGRAPHY_ORDER)
    return Term(Attribute.GEOGRAPHY, key, tok.text) if key else None


def _is_year(tok: _Token) -> bool:
    return (
        tok.kind == "num"
        and tok.decimals == 0
        and re.fullmatch(r"\d{4}", tok.text) is not None
        and 1900 <= tok.value <= 2099
    )


_SPACE_CHARS: Final = "[ \u00a0\u202f]"
_YEAR_RE: Final = r"(?:19|20)\d{2}"
#: "31. 12. 2091", "31.12.2091", "1. 1. 2025": a numeric day and month need the year.
_NUMERIC_DATE: Final = re.compile(
    rf"(?<![\w.,])(\d{{1,2}})\.{_SPACE_CHARS}?(\d{{1,2}})\.{_SPACE_CHARS}?({_YEAR_RE})(?!\w|[.,]\d)"
)
#: "2091-12-31".
_ISO_DATE: Final = re.compile(rf"(?<![\w.,/-])({_YEAR_RE})-(\d{{2}})-(\d{{2}})(?![\w-])")
#: "31. prosince", "1. ledna 2025", "k 31. prosinci roku 2091": the month name is
#: written in lower case (a capital after "12." starts a sentence).
_NAMED_DATE: Final = re.compile(
    rf"(?<![\w.,])(\d{{1,2}})\.{_SPACE_CHARS}?([^\W\d_]+)"
    rf"(?:{_SPACE_CHARS}(?:roku{_SPACE_CHARS})?({_YEAR_RE})(?!\w|[.,]\d))?"
)
#: A period key with no year of its own: a quarter, a half, a month, a day of a month.
_YEARLESS: Final = re.compile(r"^(?:Q[1-4]|H[12]|M\d{2}(?:-\d{2})?)$")
#: A sub-year period placed in its year: "2025-Q2", "2025-H1", "2025-03", "2091-12-31".
_PLACED: Final = re.compile(r"^(\d{4})-(Q[1-4]|H[12]|\d{2}(?:-\d{2})?)$")
#: Words between a sub-year term and its year that keep them one phrase.
_YEAR_JOINERS: Final = frozenset({"roku", "r"})


def _month_of(word: str) -> int:
    folded = fold(word)
    return next((m for m, words in MONTHS.items() if folded in words), 0)


def _valid_day(year: int | None, month: int, day: int) -> bool:
    try:
        date(year if year is not None else 2000, month, day)  # 2000: 29 February exists
    except ValueError:
        return False
    return True


def _placed(year: str | None, sub: str) -> tuple[str, frozenset[str]]:
    """The key of a sub-year term (``Q2``, ``H1``, ``M03``, ``M12-31``) in ``year``, if any.

    Returns the key and every key the period names: itself, and, when placed, its
    year and its sub-year part, so a source that writes "ve 2. čtvrtletí 2025" also
    names 2025 and the second quarter.
    """
    day = sub[1:].split("-") if sub.startswith("M") else None
    names = {sub}
    if day is not None and len(day) == 2:
        names.add(f"M{day[0]}")
    if year is None:
        return sub, frozenset(names)
    key = f"{year}-{'-'.join(day) if day is not None else sub}"
    names |= {key, f"Y{year}"}
    if day is not None and len(day) == 2:
        names.add(f"{year}-{day[0]}")
    return key, frozenset(names)


@dataclass(frozen=True, slots=True)
class _Period:
    term: Term
    #: The token indexes the period is written with.
    used: frozenset[int]
    #: Every key it names (:func:`_placed`).
    names: frozenset[str]


def _dates(text: str) -> list[tuple[int, int, str | None, int, int]]:
    """Every written date: (start, end, year or None, month, day). Never overlapping."""
    found: list[tuple[int, int, str | None, int, int]] = []

    def free(a: int, b: int) -> bool:
        return all(b <= s or e <= a for s, e, *_ in found)

    for m in _NUMERIC_DATE.finditer(text):
        day, month, year = int(m[1]), int(m[2]), m[3]
        if _valid_day(int(year), month, day) and free(m.start(), m.end()):
            found.append((m.start(), m.end(), year, month, day))
    for m in _ISO_DATE.finditer(text):
        year, month, day = m[1], int(m[2]), int(m[3])
        if _valid_day(int(year), month, day) and free(m.start(), m.end()):
            found.append((m.start(), m.end(), year, month, day))
    for m in _NAMED_DATE.finditer(text):
        day, month = int(m[1]), _month_of(m[2])
        if not month or not m[2][0].islower():
            continue
        year = m[3]
        if _valid_day(int(year) if year else None, month, day) and free(m.start(), m.end()):
            found.append((m.start(), m.end(), year, month, day))
    return sorted(found)


def _year_after(tokens: Sequence[_Token], k: int) -> int | None:
    """The index of a year that places the sub-year term ending before ``k``, or None.

    The year must follow at once ("2. čtvrtletí 2025", "Q2/2025"), or after "roku"
    or "r." ("v březnu roku 2025"). A year that opens a range ("Q1 2023/24") places
    nothing: which of its years is meant is not written.
    """
    if k < len(tokens) and (
        (tokens[k].kind == "word" and tokens[k].folded in _YEAR_JOINERS)
        or (tokens[k].text == "/" and k > 0 and tokens[k - 1].end == tokens[k].start)
    ):
        k += 1
    if k >= len(tokens) or not _is_year(tokens[k]):
        return None
    nxt = tokens[k + 1] if k + 1 < len(tokens) else None
    if nxt is not None and nxt.text == "/" and nxt.start == tokens[k].end:
        return None
    return k


def _periods(text: str, tokens: Sequence[_Token]) -> dict[int, _Period]:
    """Every period, by the index of its first token (rule: module doc)."""
    found: dict[int, _Period] = {}
    taken: set[int] = set()
    for start, end, year, month, day in _dates(text):
        used = frozenset(k for k, t in enumerate(tokens) if start <= t.start < end)
        if not used:
            continue
        key, names = _placed(year, f"M{month:02d}-{day:02d}")
        found[min(used)] = _Period(Term(Attribute.PERIOD, key, text[start:end]), used, names)
        taken |= used

    def sub_year(i: int, last: int, sub: str) -> int:
        """Record the sub-year term at tokens i..last, with its year when adjacent."""
        y = _year_after(tokens, last + 1)
        if y is not None and y in taken:
            y = None
        stop = y if y is not None else last
        key, names = _placed(tokens[y].text if y is not None else None, sub)
        term = Term(Attribute.PERIOD, key, text[tokens[i].start : tokens[stop].end])
        found[i] = _Period(term, frozenset({i, last} | ({y} if y is not None else set())), names)
        return stop + 1

    i = 0
    while i < len(tokens):
        if i in taken:
            i += 1
            continue
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        after = tokens[i + 2] if i + 2 < len(tokens) else None
        if _is_year(tok):
            if (
                nxt is not None
                and nxt.text == "/"
                and after is not None
                and after.kind == "num"
                and re.fullmatch(r"\d{2}|\d{4}", after.text)
                and nxt.start == tok.end
            ):
                last_year = after.text if len(after.text) == 4 else tok.text[:2] + after.text
                key = f"Y{tok.text}/{last_year}"
                season = Term(Attribute.PERIOD, key, tok.text + "/" + after.text)
                found[i] = _Period(season, frozenset({i, i + 2}), frozenset({key}))
                i += 3
                continue
            key = f"Y{tok.text}"
            whole_year = Term(Attribute.PERIOD, key, tok.text)
            found[i] = _Period(whole_year, frozenset({i}), frozenset({key}))
        elif tok.kind == "word" and (q := _QUARTER.match(tok.folded)):
            i = sub_year(i, i, f"Q{q[1] or q[2]}")
            continue
        elif nxt is not None and nxt.kind == "word" and nxt.folded in ("ctvrtleti", "pololeti"):
            half = nxt.folded == "pololeti"
            n = 0
            if tok.kind == "num" and tok.dot_after and tok.decimals == 0:
                n = int(tok.value)
            elif tok.kind == "word":
                n = next((k for k, words in _ORDINALS.items() if tok.folded in words), 0)
            if 1 <= n <= (2 if half else 4):
                i = sub_year(i, i + 1, f"{'H' if half else 'Q'}{n}")
                continue
        elif tok.kind == "word" and (month := _month_of(tok.text)):
            i = sub_year(i, i, f"M{month:02d}")
            continue
        i += 1
    return found


# --------------------------------------------------------------------------- #
# Numbers with their terms
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class StatedNumber:
    """One number as a text states it, with every term attached to it."""

    value: float
    decimals: int
    start: int
    end: int
    text: str
    #: A year, a season, a quarter's ordinal or a date's day and month: a period, not
    #: a measure.
    is_period: bool
    unit: Term | None
    #: The written scale word, or None for "as written" (scale 1).
    scale: Term | None
    denominators: tuple[Term, ...]
    populations: tuple[Term, ...]
    periods: tuple[Term, ...]
    geographies: tuple[Term, ...]

    @property
    def scale_factor(self) -> int:
        return int(self.scale.key) if self.scale is not None else 1


@dataclass(frozen=True, slots=True)
class _Reading:
    """A text read once: its numbers with their terms, and every term it names."""

    numbers: tuple[StatedNumber, ...]
    named: dict[Attribute, frozenset[str]]
    #: Sub-year periods written with no year of their own ("ve 2. čtvrtletí").
    unplaced: frozenset[str]


def _read(text: str) -> _Reading:
    tokens = _tokens(text)
    breaks = _clause_breaks(text)

    def clause(tok: _Token) -> int:
        return bisect_right(breaks, tok.start)

    periods = _periods(text, tokens)
    period_tokens = {k for p in periods.values() for k in p.used}
    geographies = {i: g for i in range(len(tokens)) if (g := _geography(tokens, i)) is not None}

    named: dict[Attribute, set[str]] = {a: set() for a in Attribute}
    for period in periods.values():
        named[Attribute.PERIOD] |= period.names
    for g in geographies.values():
        named[Attribute.GEOGRAPHY].add(g.key)
    for i, tok in enumerate(tokens):
        if (p := _population(tok)) is not None:
            named[Attribute.POPULATION].add(p.key)
        if (u := _unit_at(tokens, i, Attribute.UNIT)) is not None:
            named[Attribute.UNIT].add(u[0].key)
        if (s := _scale_at(tokens, i)) is not None:
            named[Attribute.SCALE].add(s[0].key)

    numbers: list[StatedNumber] = []
    for i, tok in enumerate(tokens):
        if tok.kind != "num":
            continue
        c = clause(tok)
        j = i + 1
        unit = scale = None
        if (s := _scale_at(tokens, j)) is not None and clause(tokens[j]) == c:
            scale, j = s[0], j + s[1]
        if (u := _unit_at(tokens, j, Attribute.UNIT)) is not None and clause(tokens[j]) == c:
            unit, j = u[0], j + u[1]
        if unit is None and i > 0 and tokens[i - 1].kind == "sign" and tokens[i - 1].text in "€$":
            unit = Term(Attribute.UNIT, _UNIT_SIGNS[tokens[i - 1].text], tokens[i - 1].text)
        is_period = i in period_tokens and unit is None and scale is None
        denominators: list[Term] = []
        per_index = -1
        if (
            j < len(tokens)
            and clause(tokens[j]) == c
            and (tokens[j].folded in _DENOMINATOR_WORDS or tokens[j].text == "/")
        ):
            k = j + 1
            # "na 1000 obyvatel" is per a count of people; "na 45 %" is a new value.
            per_count = k < len(tokens) and tokens[k].kind == "num"
            k += int(per_count)
            if k < len(tokens) and clause(tokens[k]) == c:
                per = None if per_count else _unit_at(tokens, k, Attribute.DENOMINATOR)
                per_term = (
                    per[0] if per is not None else _population(tokens[k], Attribute.DENOMINATOR)
                )
                if per_term is not None:
                    denominators.append(per_term)
                    per_index = k
        populations: list[Term] = []
        # After the number first ("45 % domácností"); before it only when nothing
        # follows ("mezi dospělými je to 45 %"), so "45 % domácností a 30 % firem"
        # does not lend the households to the 30.
        for window in (range(i + 1, i + 1 + ATTACH_AFTER), range(i - 1, i - 1 - ATTACH_BEFORE, -1)):
            if populations:
                break
            for k in window:
                if not 0 <= k < len(tokens):
                    break
                if tokens[k].kind == "num" or clause(tokens[k]) != c:
                    break
                # "12 l na osobu" is per person, not a share of persons.
                if k != per_index and (p := _population(tokens[k])) is not None:
                    populations.append(p)
        numbers.append(
            StatedNumber(
                value=tok.value,
                decimals=tok.decimals,
                start=tok.start,
                end=tok.end,
                text=tok.text,
                is_period=is_period,
                unit=unit,
                scale=scale,
                denominators=tuple(denominators),
                populations=tuple(populations),
                periods=tuple(p.term for k, p in sorted(periods.items()) if clause(tokens[k]) == c),
                geographies=tuple(
                    g for k, g in sorted(geographies.items()) if clause(tokens[k]) == c
                ),
            )
        )
    unplaced = frozenset(p.term.key for p in periods.values() if _YEARLESS.match(p.term.key))
    return _Reading(tuple(numbers), {a: frozenset(v) for a, v in named.items()}, unplaced)


def stated_numbers(text: str) -> tuple[StatedNumber, ...]:
    """Every number ``text`` states, with the terms attached to it (rule: module doc)."""
    return _read(text).numbers


def claim_measures(claim: str) -> tuple[Measure, ...]:
    """The :class:`~.contracts.Measure` of each number a claim states that is not a period.

    The first attached term of each attribute; ``measure_name`` and ``basis`` are
    not read from prose and stay ``None`` (not stated). A period is the first one the
    claim places in a year: a quarter, half, month or day written with no year
    ("ve 2. čtvrtletí") leaves the period ``None``, never guessed from a year written
    elsewhere.
    """
    return tuple(
        Measure(
            value=n.value,
            unit=n.unit.key if n.unit else None,
            scale=n.scale_factor,
            period=next((t.key for t in n.periods if not _YEARLESS.match(t.key)), None),
            geography=n.geographies[0].key if n.geographies else None,
            population=n.populations[0].key if n.populations else None,
            denominator=n.denominators[0].key if n.denominators else None,
        )
        for n in stated_numbers(claim)
        if not n.is_period
    )


# --------------------------------------------------------------------------- #
# The context window and the check
# --------------------------------------------------------------------------- #


def context_window(text: str, span: tuple[int, int]) -> tuple[int, int]:
    """The part of ``text`` (normalised) a quote at ``span`` is read in (rule: module doc)."""
    a, b = span
    starts = [0, *_sentence_starts(text)]
    first = bisect_right(starts, a) - 1
    after = bisect_left(starts, b)
    lo = starts[max(first - CONTEXT_SENTENCES, 0)]
    end = after + CONTEXT_SENTENCES
    hi = starts[end] if end < len(starts) else len(text)
    if lo < a - CONTEXT_MAX_CHARS:
        lo = a - CONTEXT_MAX_CHARS
        if lo > 0 and not text[lo - 1].isspace():
            space = text.find(" ", lo, a)
            lo = space + 1 if space >= 0 else a
    if hi > b + CONTEXT_MAX_CHARS:
        hi = b + CONTEXT_MAX_CHARS
        if hi < len(text) and not text[hi].isspace():
            space = text.rfind(" ", b, hi)
            hi = space if space >= 0 else b
    return lo, hi


@dataclass(frozen=True, slots=True)
class MeasureMismatch:
    """The first attribute a claim gives a number that the quote's context does not."""

    attribute: Attribute
    value: float
    term: str
    detail: str


def _same_value(claimed: StatedNumber, other: StatedNumber) -> bool:
    return abs(claimed.value - other.value) <= 0.5 * 10.0**-claimed.decimals + 1e-9


def _listed(texts: Iterable[str]) -> str:
    return ", ".join(dict.fromkeys(sorted(texts)))


def _shown(n: StatedNumber) -> str:
    return f"{n.value:g}"


def _period_named(key: str, source: _Reading) -> bool:
    """The source names the period ``key``, or names its sub-year part unplaced and its year.

    "ve 2. čtvrtletí 2025" is named by a source that writes it, or by one that writes
    "V roce 2025: ... ve 2. čtvrtletí" (the quarter in no year of its own); not by
    "ve 2. čtvrtletí 2024 ... v roce 2025", which places the quarter in another year.
    """
    named = source.named[Attribute.PERIOD]
    if key in named:
        return True
    placed = _PLACED.match(key)
    if placed is None:
        return False
    year, sub = placed[1], placed[2]
    sub = sub if sub[0] in "QH" else f"M{sub}"
    return sub in source.unplaced and f"Y{year}" in named


def check_measures(claim: str, context: str) -> MeasureMismatch | None:
    """The first mis-stated attribute of a number in ``claim``, read against ``context``."""
    source = _read(context)
    named = source.named
    for n in stated_numbers(claim):
        if n.is_period:
            continue
        found = [o for o in source.numbers if _same_value(n, o)]
        if not found:
            continue  # grounding's number check answers for a number the quote lacks
        scales = {o.scale_factor for o in found}
        if n.scale_factor not in scales and not (
            n.scale is not None and 1 in scales and n.scale.key in named[Attribute.SCALE]
        ):
            claimed = repr(n.scale.text) if n.scale else "no scale word"
            given = _listed(repr(o.scale.text) if o.scale else "no scale word" for o in found)
            return MeasureMismatch(
                Attribute.SCALE,
                n.value,
                n.scale.text if n.scale else "",
                f"the claim states {_shown(n)} with {claimed}; the source states it with {given}",
            )
        if n.unit is not None:
            units = {o.unit.key if o.unit else None for o in found}
            if n.unit.key not in units and not (
                None in units and n.unit.key in named[Attribute.UNIT]
            ):
                units_given = _listed(repr(o.unit.text) if o.unit else "no unit" for o in found)
                return MeasureMismatch(
                    Attribute.UNIT,
                    n.value,
                    n.unit.text,
                    f"the claim states {_shown(n)} in {n.unit.text!r}; "
                    f"the source states it in {units_given}",
                )
        for d in n.denominators:
            if d.key not in named[Attribute.UNIT] | named[Attribute.POPULATION]:
                return MeasureMismatch(
                    Attribute.DENOMINATOR,
                    n.value,
                    d.text,
                    f"the claim states {_shown(n)} per {d.text!r} ({d.key}); "
                    "the quote's context in the source names no such denominator",
                )
        attached = {p.key for o in found for p in o.populations}
        for p in n.populations:
            if p.key not in named[Attribute.POPULATION]:
                return MeasureMismatch(
                    Attribute.POPULATION,
                    n.value,
                    p.text,
                    f"the claim gives {_shown(n)} the population {p.text!r} ({p.key}); "
                    "the quote's context in the source does not name it",
                )
            if attached and p.key not in attached:
                return MeasureMismatch(
                    Attribute.POPULATION,
                    n.value,
                    p.text,
                    f"the claim gives {_shown(n)} the population {p.text!r} ({p.key}); "
                    f"the source gives it {', '.join(sorted(attached))}",
                )
        for t in n.periods:
            if not _period_named(t.key, source):
                return MeasureMismatch(
                    Attribute.PERIOD,
                    n.value,
                    t.text,
                    f"the claim dates {_shown(n)} to {t.text!r} ({t.key}); "
                    "the quote's context in the source does not",
                )
        places = named[Attribute.GEOGRAPHY]
        for g in n.geographies:
            if places and g.key not in places:
                return MeasureMismatch(
                    Attribute.GEOGRAPHY,
                    n.value,
                    g.text,
                    f"the claim places {_shown(n)} in {g.text!r} ({g.key}); "
                    f"the quote's context in the source names {', '.join(sorted(places))}",
                )
    return None


# --------------------------------------------------------------------------- #
# Stated measures: what an agent says a number means, checked the same way
# --------------------------------------------------------------------------- #

#: The stated-measure rule's version: what an agent-directed track's findings are
#: checked by on top of ``GROUNDING_VERSION`` (plan § 8.1, chunk 9).
STATED_MEASURES_VERSION: Final = f"aia-stated-measures-1/{MEASURES_VERSION}"

_SCALE_WORDS: Final[Mapping[int, str]] = {
    1: "",
    1_000: "tis.",
    1_000_000: "mil.",
    1_000_000_000: "mld.",
}
_PER_WORDS: Final = ("na ", "za ", "per ", "/")


def _written(value: float) -> str:
    """A value as Czech prose writes it: a decimal comma, no exponent."""
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return repr(value).replace(".", ",")


def render_measure(measure: Measure) -> str | None:
    """A stated measure as one Czech phrase the vocabulary reads, or None.

    Value, scale word, unit, denominator ("na" + it), population, period, place, in
    the order :func:`stated_numbers` attaches them. None when the scale is not one a
    Czech text writes (1, tis., mil., mld.): such a measure cannot be checked.
    """
    scale = _SCALE_WORDS.get(measure.scale)
    if scale is None:
        return None
    parts = [_written(measure.value), scale, measure.unit or ""]
    if measure.denominator:
        per = measure.denominator.strip()
        parts.append(per if per.casefold().startswith(_PER_WORDS) else f"na {per}")
    parts += [measure.population or "", measure.period or "", measure.geography or ""]
    return " ".join(" ".join(p.split()) for p in parts if p.strip())


@dataclass(frozen=True, slots=True)
class StatedMeasureProblem:
    """Why a finding's stated measures do not stand: missing, or mis-stated, in words."""

    missing: bool
    detail: str


def _equal(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def check_stated_measures(
    *, claim: str, quote: str, context: str, measures: Sequence[Measure]
) -> StatedMeasureProblem | None:
    """Whether an agent's measures cover its claim and say what the source says.

    ``claim``, ``quote`` and ``context`` (the quote's window in the source) are
    normalised text. In order, the first failure wins:

    1. every number the claim states (not a period) has a measure of the same value
       and scale -- a cited number without its measure is *missing*;
    2. every measure's value is a number of the quote;
    3. every measure, rendered as one phrase (:func:`render_measure`), passes
       :func:`check_measures` against the context: the unit, scale, population,
       denominator, period and place it states are the source's for that value.
    """
    for number in stated_numbers(claim):
        if number.is_period:
            continue
        if not any(
            _equal(m.value, number.value) and m.scale == number.scale_factor for m in measures
        ):
            return StatedMeasureProblem(
                True, f"the claim states {_shown(number)} and no measure states it"
            )
    quoted = stated_numbers(quote)
    for m in measures:
        if not any(_equal(m.value, n.value) for n in quoted):
            return StatedMeasureProblem(
                False, f"a measure states {_written(m.value)}; the quote does not"
            )
        phrase = render_measure(m)
        if phrase is None:
            return StatedMeasureProblem(
                False,
                f"a measure gives {_written(m.value)} the scale {m.scale}, which no text writes",
            )
        mismatch = check_measures(phrase, context)
        if mismatch is not None:
            return StatedMeasureProblem(False, f"the measure {phrase!r}: {mismatch.detail}")
    return None


def normalised_measure(measure: Measure) -> Measure:
    """A stated measure in the vocabulary's keys (``CZK``, ``HOUSEHOLDS``, ``Y2025``...).

    What the vocabulary does not read stays ``None`` -- not stated, never a guess;
    the name and the basis are the agent's, kept as given.
    """
    phrase = render_measure(measure)
    read = claim_measures(phrase) if phrase is not None else ()
    match = next(
        (m for m in read if _equal(m.value, measure.value) and m.scale == measure.scale), None
    )
    base = match or Measure(value=measure.value, scale=measure.scale)
    return base.model_copy(update={"measure_name": measure.measure_name, "basis": measure.basis})
