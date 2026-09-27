"""Grounding: a finding is admissible only when its quote is in the source it cites.

ADR 0017 decision 4, plan decision I-5. Three checks, in order, each deterministic:

1. **The source is this track's.** A web finding may cite only a snapshot fetched
   for its own track; an internal finding only an item retrieved for it. A model
   naming another track's page, another client's item or a URL nobody fetched is
   refused (``citation_outside_track``), whatever the quote says.
2. **The quote occurs in the source**, after :func:`normalise_text` on both sides,
   and is long enough to mean something (``ungrounded_excerpt``).
3. **Every number in the claim is in the quote** (``number_not_in_quote``): a
   claim may paraphrase its quote, never add a figure to it.

Separately, :func:`detect_instructions` names the prompt-injection patterns in a
source's text. A source that carries instructions is kept for provenance, and its
findings are quarantined (``source_contains_instructions``): text is data, and a
page that talks to the model is not evidence of anything but that.

Pure: stdlib only.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from ..analysis.draft import numbers_in, uncovered_numbers
from .contracts import QuarantineReason

__all__ = [
    "GROUNDING_VERSION",
    "INSTRUCTION_PATTERNS",
    "MAX_QUOTE_CHARS",
    "MIN_QUOTE_CHARS",
    "GroundableSource",
    "Grounding",
    "detect_instructions",
    "ground",
    "locate_quote",
    "normalise_text",
]

#: The grounding rules' version; part of every track and merge fingerprint.
GROUNDING_VERSION: Final = "aia-grounding-1"

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


#: Prompt-injection patterns, by id. Case-insensitive; a match anywhere in a source.
INSTRUCTION_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "ignore_instructions": re.compile(
        r"\b(ignore|disregard|forget|override)\b[^.\n]{0,60}"
        r"\b(previous|prior|above|earlier|all|any|your)\b[^.\n]{0,60}"
        r"\b(instructions?|prompts?|rules?|directions?|guidelines?)\b",
        re.I,
    ),
    "ignore_instructions_cs": re.compile(
        r"\b(ignoruj(te)?|zapomeň(te)?|nedbej(te)?|přepiš(te)?)\b[^.\n]{0,60}"
        r"\b(předchozí|všechny|dřívější|své)\b"
        r"[^.\n]{0,60}\b(instrukce|pokyny|pravidla)\b",
        re.I,
    ),
    "role_override": re.compile(
        r"\b(you are now|from now on,? you|pretend to be|act as (an?|the) (ai|assistant|model))\b",
        re.I,
    ),
    "system_prompt": re.compile(
        r"(\bsystem prompt\b|\bsystem message\b|\bdeveloper message\b|<\s*/?\s*system\s*>)",
        re.I,
    ),
    "tool_call": re.compile(
        r"(\"(tool_use|tool_calls|function_call)\"|\btoolUse\b|<\s*/?\s*tool_call\b)", re.I
    ),
    "verdict_override": re.compile(
        r"\b(mark|label|treat|classify|rate)\b[^.\n]{0,60}\b(this|these|all|every)\b[^.\n]{0,60}"
        r"\b(claims?|findings?|sources?|evidence)\b[^.\n]{0,60}"
        r"\b(supported|verified|accepted|trusted|reliable)\b",
        re.I,
    ),
    "exfiltration": re.compile(
        r"\b(send|post|upload|reveal|print)\b[^.\n]{0,60}"
        r"\b(api keys?|credentials?|passwords?|secrets?|tokens?|system prompt)\b",
        re.I,
    ),
}


def detect_instructions(text: str) -> tuple[str, ...]:
    """The ids of every instruction pattern ``text`` contains, sorted; empty when none."""
    return tuple(sorted(pid for pid, rx in INSTRUCTION_PATTERNS.items() if rx.search(text)))


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
    *, source_ref: str, quote: str, claim: str, sources: Mapping[str, GroundableSource]
) -> Grounding:
    """Check one proposed finding against the sources its track holds."""
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
    span = locate_quote(source.text, needle)
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
    if source.instructions_detected:
        return Grounding(
            span,
            QuarantineReason.SOURCE_CONTAINS_INSTRUCTIONS,
            "the source contains instructions: " + ", ".join(source.instructions_detected),
        )
    return Grounding(span, None, "")
