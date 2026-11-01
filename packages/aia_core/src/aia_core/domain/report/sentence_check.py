"""A report's sentence-level claim check (report-delivery RD7; the product owner, MVPQ-09).

The evidence validation checks numbers: every printed number is a claim the gate admitted. A
sentence can still claim a comparison in words alone -- "nejvíc důvěřují lidé v Praze" -- with
no admitted claim behind it. This reads a stored document model (``document_model``) and names
each such sentence. Since 2026-10-22 it marks, never blocks (the product owner, as RD0; ADR
0035, amended): the pane marks the sentence and the approval records it.

A sentence claims a comparison when it holds a comparative (vyšší, spokojenější, častěji; or
"než"), a superlative ("nej…", not the few words that only look like one), or a word that
states a difference or a lead (:data:`COMPARISON_WORDS`), and does not ask (a question, or
"zda": a research question or goal restated claims nothing). The lists are PROVISIONAL, for
the methodology owner to review. It is supported when it prints a number from the ledger: a value in
it (a ``value`` inline), a figure or table of them it points at (a ``cross_ref``), or the
number its block cites, as prose writes it (analysis prose writes its numbers as text and cites
their claims on the paragraph; a decimal point or comma and any thousands space read alike).
Anything else is
``unsupported_comparison``. A reading rule, deliberately plain: it flags a comparison the text
states without a number, and says nothing about whether a cited number bears the comparison out.

Read: the paragraphs, list items and callouts of each section written from an analysis module
(its section sources, ``report/sources.py``), the prose a model wrote. Not read: the composer's
own text elsewhere (a map's reading guide, a chapter's method, the questionnaire as asked), which
names how a number is read rather than claiming one; a lead-in (a title, such as a research
question); and a block code wrote whole from a stored source (``control``).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from aia_core.domain.analysis.artifact import ANALYSIS_MODULE_ARTIFACT

# PROVISIONAL (the PM, 2026-10-24): the word list below is AIA's starting reading of a Czech
# comparison, for the methodology owner to review. It only marks a sentence, never refuses one.
# Every form is written folded -- lower case, no diacritics (:func:`fold`) -- and the text is
# folded the same way, so "vyšší", "vyššího" and "VYSSI" read alike.
#
#: Whole words that state a comparison.
COMPARISON_WORDS: Final = frozenset(
    {"nez", "oproti", "prevysuje", "prevysuji", "prevazuje", "prevazuji", "prevlada"}
)
COMPARISON_PHRASES: Final = ("ve srovnani", "v porovnani")
#: Word starts: a superlative ("nej…"), a difference, and the irregular comparatives in any
#: inflection (vyšší, vyššího, vyšším; nižší, větší, menší, lepší, horší, delší, kratší,
#: dražší, mladší, starší).
COMPARISON_STARTS: Final = (
    "nej",
    "rozdil",
    "vyss",
    "nizs",
    "vets",
    "mens",
    "leps",
    "hors",
    "dels",
    "krats",
    "drazs",
    "mlads",
    "stars",
)
#: Inside a word: the regular comparative's "-ější" / "-ejší" (silnější, spokojenějšího). Its
#: adverb's "-ěji" ends verbs too (rozumějí), so those adverbs are listed instead.
COMPARISON_INFIXES: Final = ("ejs",)
COMPARISON_ADVERBS: Final = frozenset(
    {"casteji", "silneji", "slabeji", "vyrazneji", "lepe", "hure"}
)
#: Words that read like one of the above and are none: "ne-" before "j…" (nejsou, nejde,
#: nejistota), the adverbs of order and likelihood, and většina / menšina (a majority, a
#: minority: a share, which a number states or not, but no comparison of two).
NOT_COMPARISON: Final = frozenset(
    {
        "nejsem",
        "nejsi",
        "nejsme",
        "nejste",
        "nejsou",
        "nejde",
        "nejdou",
        "nejen",
        "nejprve",
        "nejdriv",
        "nejdrive",
        "nejspis",
        "nejspise",
        "nejpozdeji",
    }
)
NOT_COMPARISON_STARTS: Final = ("nejist", "nejedn", "vetsin", "mensin")
#: A sentence that asks -- "…?", or "zda" / "zdali" / "jestli" (whether) -- claims nothing: a
#: research question or a study's goal restated ("Zjistit, zda …, komu nejvíc …").
QUESTION_WORDS: Final = frozenset({"zda", "zdali", "jestli"})
#: A metric's name, not a comparison: the share of the top two points of a scale.
METRIC_NAMES: Final = ("dvou nejvyssich bodu", "dva nejvyssi body")
UNSUPPORTED_COMPARISON: Final = "unsupported_comparison"
#: The source that makes a section's text a model's prose (``domain/analysis/artifact.py``).
_WRITTEN_FROM: Final = ANALYSIS_MODULE_ARTIFACT
_VALUE: Final = "\u0000"
_WORD: Final = re.compile(r"\w+")
# A sentence ends at . ! ? or … followed by space and a capital, a digit or an opening quote.
# Its closing quote or bracket may follow the stop: „… 48,2 %.“ Nejvíc … is two sentences.
_END: Final = re.compile(
    '(?:(?<=[.!?…])|(?<=[.!?…][“”"»\u2019)]))\\s+(?=[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ0-9„"(])'
)
# A number as prose or the ledger prints it: thousands grouped by a space of any width, a
# decimal comma or point, a minus or a hyphen before it.
_NUMBER: Final = re.compile(
    "[\u2212-]?\\d{1,3}(?:[ \u00a0\u202f]\\d{3})+(?:[.,]\\d+)?|[\u2212-]?\\d+(?:[.,]\\d+)?"
)


@dataclass(frozen=True, slots=True)
class SentenceFinding:
    """A sentence the check marks: its block, its index in the block's text from 0, its text."""

    where: str
    sentence: int
    text: str

    def to_json(self) -> dict[str, Any]:
        return {
            "code": UNSUPPORTED_COMPARISON,
            "where": self.where,
            "message": f"srovnání bez doloženého čísla: „{self.text}“",
            "sentence": self.sentence,
            "text": self.text,
        }


def sentences(content: Sequence[Mapping[str, Any]], ledger: Mapping[str, Any]) -> list[str]:
    """``content`` (a block's inlines) as its sentences, a value printed as the ledger prints
    it and marked with :data:`_VALUE` before it, so a sentence knows it holds one."""
    out: list[str] = []
    for inline in content:
        if inline["type"] == "value":
            entry = ledger.get(inline["ref"]) or {}
            out.append(_VALUE + str(entry.get("value_text") or ""))
        elif inline["type"] == "cross_ref":
            # A figure or table of admitted numbers the sentence points at.
            out.append(_VALUE)
        elif inline["type"] in ("text", "link"):
            out.append(str(inline.get("text") or ""))
    return [s.strip() for s in _END.split("".join(out)) if s.strip()]


def fold(text: str) -> str:
    """``text`` in lower case without diacritics, as the word lists are written."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def claims_comparison(sentence: str) -> bool:
    folded = fold(sentence)
    if folded.rstrip(' "“”)').endswith("?") or QUESTION_WORDS & set(_WORD.findall(folded)):
        return False
    for name in METRIC_NAMES:
        folded = folded.replace(name, " ")
    if any(p in folded for p in COMPARISON_PHRASES):
        return True
    for word in _WORD.findall(folded):
        if word in NOT_COMPARISON or word.startswith(NOT_COMPARISON_STARTS):
            continue
        if (
            word in COMPARISON_WORDS
            or word in COMPARISON_ADVERBS
            or word.startswith(COMPARISON_STARTS)
            or any(i in word for i in COMPARISON_INFIXES)
        ):
            return True
    return False


def numbers(text: str) -> set[str]:
    """The numbers ``text`` states, each in one form whatever its print: "1 204", "1\u00a0204"
    and "1204" alike, "48,2" and "48.2" alike, a minus sign (U+2212) and a hyphen alike."""
    return {
        re.sub(r"[ \u00a0\u202f]", "", n).replace(",", ".").replace("\u2212", "-")
        for n in _NUMBER.findall(text)
    }


def _supported(sentence: str, cited: Sequence[Mapping[str, Any]]) -> bool:
    if _VALUE in sentence:
        return True
    printed = {
        n
        for entry in cited
        if not entry.get("suppressed")
        for n in numbers(str(entry.get("number_text") or ""))
    }
    return bool(printed & numbers(sentence))


def _texts(section: Mapping[str, Any]) -> Iterator[tuple[str, list[Any], list[str]]]:
    """Each block read: its id, its texts (a list's items one by one, each its own sentence or
    more) and the refs it cites."""
    for block in section["blocks"]:
        if block.get("control") or block.get("role") == "lead_in":
            continue
        refs = list(block.get("refs") or ())
        if block["type"] in ("paragraph", "callout"):
            yield block["id"], [block["content"]], refs
        elif block["type"] == "list":
            items, pending = [], list(block["items"])
            while pending:
                item = pending.pop(0)
                items.append(item["content"])
                pending[:0] = item["children"]
            yield block["id"], items, refs


def sentence_findings(document: Mapping[str, Any]) -> tuple[SentenceFinding, ...]:
    """Every sentence of a stored document model that claims a comparison with no number from
    the ledger in it; empty when there is none."""
    ledger: Mapping[str, Any] = document["ledger"]["refs"]
    found: list[SentenceFinding] = []
    for section in document["sections"]:
        if not any(
            source.get("artifact_type") == _WRITTEN_FROM for source in section.get("sources") or ()
        ):
            continue
        for where, texts, refs in _texts(section):
            cited = [ledger[r] for r in refs if r in ledger]
            read = [sentence for content in texts for sentence in sentences(content, ledger)]
            for n, sentence in enumerate(read):
                if claims_comparison(sentence) and not _supported(sentence, cited):
                    found.append(SentenceFinding(where, n, sentence.replace(_VALUE, "")))
    return tuple(found)
