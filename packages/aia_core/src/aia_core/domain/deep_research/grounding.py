"""Grounding: a finding is admissible only when its quote is in the source it cites.

ADR 0017 decision 4, plan decision I-5. Four checks, in order, each deterministic:

1. **The source is this track's.** A web finding may cite only a snapshot fetched
   for its own track; an internal finding only an item retrieved for it. A model
   naming another track's page, another client's item or a URL nobody fetched is
   refused (``citation_outside_track``), whatever the quote says.
2. **The quote occurs in the source**, after :func:`normalise_text` on both sides,
   and is long enough to mean something (``ungrounded_excerpt``).
3. **Every number in the claim is in the quote** (``number_not_in_quote``): a
   claim may paraphrase its quote, never add a figure to it.
4. **Every number means in the claim what it means in the source**
   (``measure_not_in_source``): the unit, scale, period, population, denominator
   and place the claim attaches to a number are the ones the quote's context in
   the source gives it (:mod:`.measures`). A household share is not a share of
   adults, "450" is not "450 tis.". The finding keeps its span: the quote is in
   the source; the claim misstates it.
5. **Only for an agent that states its measures** (the agent-directed
   investigator): every number of the claim has one (``measure_missing``), and
   each says what the source says (``measure_not_in_source``).

A table cell (plan § 8.2) is grounded by :func:`ground_cell`: the quote must be
exactly that cell's line in the table's rendering -- its row and column labels,
period, unit, value and status -- so a value read off a neighbouring cell, or a
prefix of a longer value, does not ground.

Separately, :func:`detect_instructions` names the prompt-injection patterns in a
source's text. A source that carries instructions is kept for provenance, and its
findings are quarantined (``source_contains_instructions``): text is data, and a
page that talks to the model is not evidence of anything but that.

Pure: stdlib only.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from ..analysis.draft import numbers_in, uncovered_numbers
from .contracts import Measure, QuarantineReason, SourceSnapshot
from .datasets import DatasetCell
from .measures import MEASURES_VERSION, check_measures, check_stated_measures, context_window

__all__ = [
    "GROUNDING_VERSION",
    "INSTRUCTIONS_VERSION",
    "INSTRUCTION_PATTERNS",
    "MAX_QUOTE_CHARS",
    "MIN_QUOTE_CHARS",
    "CellGrounding",
    "GroundableSource",
    "Grounding",
    "detect_instructions",
    "ground",
    "ground_cell",
    "locate_quote",
    "normalise_text",
]

#: The instruction detector's version (plan chunk 45); carried by GROUNDING_VERSION, so a
#: track grounded under another detector is grounded again.
INSTRUCTIONS_VERSION: Final = "aia-instructions-2"

#: The grounding rules' version; part of every track and merge fingerprint.
#: It carries the measures vocabulary's and the instruction detector's versions: a change
#: to either regrounds.
GROUNDING_VERSION: Final = f"aia-grounding-3/{MEASURES_VERSION}/{INSTRUCTIONS_VERSION}"

#: A shorter quote matches too easily to prove anything ("the market").
MIN_QUOTE_CHARS: Final = 20
MAX_QUOTE_CHARS: Final = 800

# Typographic forms folded to one spelling, so a quote copied with other quotation
# marks or dashes still matches. None of them changes what the text says.
_FOLD: Final = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u00ab": '"',
        "\u00bb": '"',
        "\u2039": "'",
        "\u203a": "'",
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2026": "...",
    }
)
_SPACE: Final = re.compile(r"\s+")


def normalise_text(text: str) -> str:
    """The form quotes are matched in: NFKC, folded punctuation, single spaces.

    NFKC turns a non-breaking space, a ligature or a full-width digit into its plain
    form; quotation marks and dashes are folded to ASCII; every run of whitespace is
    one space. Case is kept: a quote is verbatim.
    """
    return _SPACE.sub(" ", unicodedata.normalize("NFKC", text).translate(_FOLD)).strip()


def locate_quote(source_text: str, quote: str) -> tuple[int, int] | None:
    """Where ``quote`` occurs in ``source_text`` (both normalised), or None."""
    needle = normalise_text(quote)
    if not needle:
        return None
    haystack = normalise_text(source_text)
    at = haystack.find(needle)
    return (at, at + len(needle)) if at >= 0 else None


# Any characters within one sentence, line breaks included: a page's text keeps the
# breaks of its HTML, and an instruction split over three lines is still one.
_S = r"[^.!?]{0,80}?"
#: Who an instruction to a model is addressed to, in English and Czech.
_ADDRESSEE = (
    r"(ai|a\.i\.|llms?|language models?|chatbots?|(ai )?assistants?|ai (agents?|systems?|"
    r"reviewers?|models?)|automated (fact[- ]?checkers?|reviewers?|systems?|agents?)|"
    r"jazykov\w* model\w*|umělá inteligence|umělé inteligenc\w*|ai systém\w*|"
    r"automatizovan\w* (ověřovatel\w*|recenzent\w*|systém\w*)|asistent\w*)"
)
#: Prompt-injection patterns, by id. Case-insensitive; a match anywhere in a source.
INSTRUCTION_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "ignore_instructions": re.compile(
        rf"\b(ignore|disregard|forget|override)\b{_S}"
        rf"\b(previous|prior|above|earlier|all|any|your)\b{_S}"
        r"\b(instructions?|prompts?|rules?|directions?|guidelines?)\b"
        rf"|\b(ignore|disregard|forget)\b{_S}\b(what you were told|you were told)\b",
        re.I,
    ),
    "ignore_instructions_cs": re.compile(
        rf"\b(ignoruj(te)?|zapomeň(te)?|nedbej(te)?|přepiš(te)?)\b{_S}"
        r"\b(předchozí\w*|všechn\w*|dřívější\w*|sv\w*)\b"
        rf"{_S}\b(instrukc\w*|pokyn\w*|pravid\w*)",
        re.I,
    ),
    "role_override": re.compile(
        r"\b(you are now (an?|the|my|our)\b|from now on,? you\b|pretend to be|"
        r"act as (an?|the) (ai|assistant|model)\b|od teď jsi\b|od nynějška jsi\b)",
        re.I,
    ),
    "system_prompt": re.compile(
        r"(\bsystem prompt\b|\b(your|this) system message\b|\bdeveloper message\b|"
        r"<\s*/?\s*system\s*>|\bsystémov\w* prompt\w*\b)",
        re.I,
    ),
    "tool_call": re.compile(
        r"(\"(tool_use|tool_calls|function_call)\"|\btoolUse\b|<\s*/?\s*tool_call\b)", re.I
    ),
    "verdict_override": re.compile(
        # The verb as an order: at a sentence's start, after "please", a modal, an
        # addressee, or chained to another order by "and"/"then".
        r"(^|[.!?:\n]|\bplease\b|\b(should|must|shall|and|then)\b|" + _ADDRESSEE + r"[,:]?)\s*"
        rf"\b(mark|label|treat|classify|rate|accept|approve)\b{_S}"
        r"\b(this|these|all|every|them|it)\b"
        rf"({_S}\b(claims?|findings?|sources?|evidence|figures?|numbers?|page)\b)?"
        rf"{_S}\b(supported|verified|accepted|trusted|reliable|correct|final|primary)\b"
        rf"|\b(accept|approve)\b{_S}\bwithout (further )?(checking|verification|review)\b",
        re.I | re.M,
    ),
    "verdict_override_cs": re.compile(
        # Imperatives only: "označte" asks; "úřad označí" and "redakce označuje" describe.
        rf"\b(označ(te)?|považuj(te)?|přijm(i|ěte)|schval(te)?)\b{_S}"
        r"\b(ověřen\w*|spolehliv\w*|konečn\w*|důvěryhodn\w*|správn\w*)",
        re.I,
    ),
    "exfiltration": re.compile(
        rf"\b(send|post|upload|reveal|print|share)\b{_S}"
        r"\b(api keys?|credentials?|passwords?|secrets?|tokens?|system prompt)\b"
        rf"|\b(vypiš|pošli|odhal|zobraz|sděl)\w*\b{_S}"
        r"\b(systémov\w* prompt\w*|přístupov\w* klíč\w*|hesl\w*|přihlašovací\w*)",
        re.I,
    ),
    "addressed_to_model": re.compile(
        r"\b(note|notice|instructions?|message|oznámení|pokyny?)\s+(to|for|pro)\s+"
        r"(any\s+|all\s+)?" + _ADDRESSEE + r"\b"
        r"|\bif you are (an? )?" + _ADDRESSEE + r"\b"
        r"|\bpokud (jste|jsi) " + _ADDRESSEE + r"\b"
        r"|\bpro " + _ADDRESSEE + r"\s*:"
        r"|<!--[^>]{0,40}\b(llm|ai|assistant|model|gpt|claude|gemini)\b"
        r"|^\s*" + _ADDRESSEE + r"\s*:",
        re.I | re.M,
    ),
    "search_steer": re.compile(
        rf"\b(search|look up|google|find)\b{_S}\b(your|the) client'?s?\b"
        rf"|\b(vyhledej\w*|najdi\w*|dohledej\w*)\b{_S}\b(svého|tvého|vašeho)? ?klient\w*",
        re.I,
    ),
    "output_suppression": re.compile(
        rf"\b(when|while|before) (you )?(summari[sz]|answer|respond|writ|report)\w*{_S}"
        r"\b(do not|don'?t|never|avoid|omit)\b"
        rf"|\bpři (shrnutí|odpovědi|psaní)\b{_S}\b(neuváděj\w*|nezmiňuj\w*|vynech\w*)",
        re.I,
    ),
}

#: A warning that an act is never to be done is not an instruction to do it: "never send
#: your password by email". Checked in the words just before the match.
_NEGATED: Final = re.compile(r"\b(never|don'?t|do not|nikdy|ne\w*te)\s*\S*\s*$", re.I)
#: The patterns a preceding negation disarms.
_NEGATABLE: Final = frozenset({"exfiltration"})


def _hits(pid: str, pattern: re.Pattern[str], text: str) -> bool:
    for match in pattern.finditer(text):
        if pid in _NEGATABLE and _NEGATED.search(text[max(0, match.start() - 24) : match.start()]):
            continue
        return True
    return False


def detect_instructions(text: str) -> tuple[str, ...]:
    """The ids of every instruction pattern ``text`` contains, sorted; empty when none.

    Read after NFKC and the same punctuation folding quotes are matched under, line
    breaks kept (two patterns read a line's start): full-width or ligature letters are
    the same words to a model as to grounding.

    A tripwire, not the boundary (plan chunk 45, measured): on a held-out set it caught 4
    of 15 hostile pages. What keeps a hostile page out of the evidence is that an
    unknown host scores below acceptance, every quote must be in its own track's capture,
    and every query a model proposes after reading a page passes the gate.
    """
    text = unicodedata.normalize("NFKC", text).translate(_FOLD)
    return tuple(sorted(pid for pid, rx in INSTRUCTION_PATTERNS.items() if _hits(pid, rx, text)))


@dataclass(frozen=True, slots=True)
class GroundableSource:
    """What grounding needs to know about one source a track holds."""

    ref: str
    text: str
    instructions_detected: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Grounding:
    """The verdict on one proposed finding: a span, or the one reason it failed."""

    span: tuple[int, int] | None
    failure: QuarantineReason | None
    detail: str

    @property
    def grounded(self) -> bool:
        return self.failure is None


def ground(
    *,
    source_ref: str,
    quote: str,
    claim: str,
    sources: Mapping[str, GroundableSource],
    measures: Sequence[Measure] | None = None,
) -> Grounding:
    """Check one proposed finding against the sources its track holds.

    ``measures`` is what the proposing agent says each number means (an
    agent-directed turn states them; the planned mode's agents do not, and pass
    ``None``, which changes nothing). Given, check 5 runs after the other four:
    every number of the claim has a measure (``measure_missing``), and every
    measure is the source's (``measure_not_in_source``), by
    :func:`~.measures.check_stated_measures`.
    """
    source = sources.get(source_ref)
    if source is None:
        return Grounding(
            None,
            QuarantineReason.CITATION_OUTSIDE_TRACK,
            f"{source_ref!r} is not a source this track retrieved",
        )
    needle = normalise_text(quote)
    if not MIN_QUOTE_CHARS <= len(needle) <= MAX_QUOTE_CHARS:
        return Grounding(
            None,
            QuarantineReason.UNGROUNDED_EXCERPT,
            f"a quote is {MIN_QUOTE_CHARS} to {MAX_QUOTE_CHARS} characters; this is {len(needle)}",
        )
    haystack = normalise_text(source.text)
    at = haystack.find(needle)
    span = (at, at + len(needle)) if at >= 0 else None
    if span is None:
        return Grounding(
            None, QuarantineReason.UNGROUNDED_EXCERPT, f"the quote does not occur in {source_ref}"
        )
    backing = [value for value, _ in numbers_in(needle)]
    missing = uncovered_numbers(claim, backing, ())
    if missing:
        shown = ", ".join(f"{n:g}" for n in missing)
        return Grounding(
            None,
            QuarantineReason.NUMBER_NOT_IN_QUOTE,
            f"the claim states {shown}; the quote does not",
        )
    lo, hi = context_window(haystack, span)
    mismatch = check_measures(normalise_text(claim), haystack[lo:hi])
    if mismatch is not None:
        return Grounding(span, QuarantineReason.MEASURE_NOT_IN_SOURCE, mismatch.detail)
    if measures is not None:
        problem = check_stated_measures(
            claim=normalise_text(claim), quote=needle, context=haystack[lo:hi], measures=measures
        )
        if problem is not None:
            reason = (
                QuarantineReason.MEASURE_MISSING
                if problem.missing
                else QuarantineReason.MEASURE_NOT_IN_SOURCE
            )
            return Grounding(span, reason, problem.detail)
    if source.instructions_detected:
        return Grounding(
            span,
            QuarantineReason.SOURCE_CONTAINS_INSTRUCTIONS,
            "the source contains instructions: " + ", ".join(source.instructions_detected),
        )
    return Grounding(span, None, "")


@dataclass(frozen=True, slots=True)
class CellGrounding:
    """The verdict on a quote of one table cell: the cell and its span, or why not."""

    cell: DatasetCell | None
    span: tuple[int, int] | None
    failure: QuarantineReason | None
    detail: str

    @property
    def grounded(self) -> bool:
        return self.failure is None


def ground_cell(*, snapshot: SourceSnapshot, locator: str, quote: str) -> CellGrounding:
    """Check that ``quote`` is the cell at ``locator`` of a dataset snapshot, exactly.

    The quote is the cell's line with or without its ``[locator]`` prefix, compared
    after :func:`normalise_text`. A quote that is another cell's line names that
    cell in the detail; a quote that is part of a line (a value cut short, a label
    dropped) is not a cell. The source's instruction flags apply as for any quote.
    """
    table = snapshot.dataset
    if table is None:
        return CellGrounding(
            None,
            None,
            QuarantineReason.UNGROUNDED_EXCERPT,
            f"{snapshot.snapshot_id} is not a table; a cell is cited only in a dataset snapshot",
        )
    cell = table.cell(locator)
    if cell is None:
        return CellGrounding(
            None,
            None,
            QuarantineReason.UNGROUNDED_EXCERPT,
            f"{locator!r} is not a cell of {table.dataset_id}",
        )
    needle = normalise_text(quote)
    if needle not in (normalise_text(cell.line()), normalise_text(cell.text())):
        other = next(
            (
                c.locator
                for c in table.cells()
                if needle in (normalise_text(c.line()), normalise_text(c.text()))
            ),
            None,
        )
        detail = (
            f"the quote is the cell {other}, not {locator}"
            if other is not None
            else f"the quote is not the cell {locator} as the table states it"
        )
        return CellGrounding(cell, None, QuarantineReason.UNGROUNDED_EXCERPT, detail)
    span = locate_quote(snapshot.text, cell.line())
    if span is None:  # the validator makes the text the rendering; this cannot happen
        return CellGrounding(
            cell, None, QuarantineReason.UNGROUNDED_EXCERPT, "the cell is not in the snapshot text"
        )
    if snapshot.instructions_detected:
        return CellGrounding(
            cell,
            span,
            QuarantineReason.SOURCE_CONTAINS_INSTRUCTIONS,
            "the source contains instructions: " + ", ".join(snapshot.instructions_detected),
        )
    return CellGrounding(cell, span, None, "")
