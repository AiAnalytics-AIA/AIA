"""Which data class a search query is: by where it came from, then by what it says.

ADR 0017 decision 2, as amended by plan decision I-2. A query is written by a
model, from a context code assembled; it is at least as confidential as that
context, because a query paraphrasing a client's brief is the client's brief with
the names taken out. So the class is the **most restrictive** of three:

1. **Derivation** -- the class of the context the proposing call saw
   (``context:<class>``). Nothing below can lower it.
2. **Client terms** -- the client's name, the study's name and codename, and every
   approved ``ENTITY``/``TERM`` item not marked public: a match makes the query at
   least Class B (``client_term:<source>``). Matching survives case, diacritics,
   German transliteration (``Müller`` / ``Mueller``), punctuation and spacing
   (``A C M E``, ``ac-me``), because each of those is how a term slips past a
   literal check.
3. **Class A text** -- a run of :data:`NGRAM` words shared with any Class A text
   the run holds makes the query Class A (``class_a_overlap``), and a Class A query
   never leaves.

What counts as a client term is the data owner's list (DR-2): this module only
reads it. It never decides that a term is harmless -- a term is harmless only when
the person who approved it said so (``KnowledgeSource.public``).

Pure: stdlib only.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from ..residency import DataClass
from .contracts import ClientTerm

__all__ = [
    "CLASSIFIER_VERSION",
    "NGRAM",
    "QueryClassification",
    "classify_query",
    "fold",
    "most_restrictive",
    "term_variants",
]

CLASSIFIER_VERSION: Final = "aia-query-classifier-1"

#: Words in a row a query may share with Class A text before it *is* Class A text.
NGRAM: Final = 5

#: Compacted terms shorter than this are matched as whole words only; "ab" inside
#: "about" is not the client "AB".
_COMPACT_MIN: Final = 4

_RANK: Final[dict[DataClass, int]] = {
    DataClass.CLASS_C_INTERNAL: 0,
    DataClass.CLASS_B_DERIVED_CLIENT: 1,
    DataClass.CLASS_A_CLIENT_CONFIDENTIAL: 2,
}

# Letters NFKD does not decompose, and the German spellings a term may be written in.
_SINGLE: Final = str.maketrans({"ß": "ss", "æ": "ae", "ø": "o", "đ": "d", "ł": "l", "œ": "oe"})
_GERMAN: Final = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue"})
_NON_WORD: Final = re.compile(r"[^0-9a-z]+")


def most_restrictive(classes: Iterable[DataClass]) -> DataClass:
    """The most restrictive class of those given (A over B over C). Needs at least one."""
    ranked = sorted(classes, key=_RANK.__getitem__)
    if not ranked:
        raise ValueError("a class of nothing is not Class C; classify the material")
    return ranked[-1]


def _strip_marks(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def fold(text: str) -> str:
    """Lower-case ASCII words: no diacritics, no punctuation, single spaces."""
    ascii_ish = _strip_marks(text.casefold().translate(_SINGLE))
    return " ".join(_NON_WORD.sub(" ", ascii_ish).split())


def term_variants(term: str) -> frozenset[str]:
    """Every folded spelling of a term: plain, and with German transliteration."""
    lowered = term.casefold()
    return frozenset(v for v in (fold(lowered), fold(lowered.translate(_GERMAN))) if v)


def _contains_words(haystack: str, needle: str) -> bool:
    return f" {needle} " in f" {haystack} "


def _ngrams(words: Sequence[str]) -> set[tuple[str, ...]]:
    return {tuple(words[i : i + NGRAM]) for i in range(len(words) - NGRAM + 1)}


@dataclass(frozen=True, slots=True)
class QueryClassification:
    """A query's class and every reason for it, in the order they were found."""

    data_class: DataClass
    reasons: tuple[str, ...]


def classify_query(
    text: str,
    *,
    context_class: DataClass,
    client_terms: Sequence[ClientTerm],
    class_a_texts: Sequence[str],
) -> QueryClassification:
    """Classify one proposed query. The result is never below ``context_class``."""
    reasons = [f"context:{context_class.value}"]
    found = [context_class]
    folded = fold(text)
    # The query as written and with German transliteration, spaced and squeezed.
    spellings = term_variants(text) | {folded}
    squeezed_query = {s.replace(" ", "") for s in spellings}
    for term in client_terms:
        for spelling in term_variants(term.term):
            squeezed = spelling.replace(" ", "")
            if any(_contains_words(s, spelling) for s in spellings) or (
                len(squeezed) >= _COMPACT_MIN and any(squeezed in q for q in squeezed_query)
            ):
                found.append(DataClass.CLASS_B_DERIVED_CLIENT)
                reasons.append(f"client_term:{term.source}")
                break
    grams = _ngrams(folded.split())
    if grams and any(grams & _ngrams(fold(a).split()) for a in class_a_texts):
        found.append(DataClass.CLASS_A_CLIENT_CONFIDENTIAL)
        reasons.append("class_a_overlap")
    return QueryClassification(most_restrictive(found), tuple(reasons))
