"""Project memory's match: does a past study's design say what a person searched for? (M1a)

A person searches the past studies of one client (``plans/project-memory-reuse.md`` M1).
A study is searched on its name and on its design document -- the latest Design Revision,
or, for a study that has none, its working draft (owner, 2026-10-12): the title, goal,
decision use, the research plan's questions and objectives, the questionnaire's section titles
and object families, and the dimensions it chose, **by their titles**. A design stores
dimension ids (``persona_dimensions.approved``); the canonical titles are
:data:`DIMENSION_LABELS`, and a client's own dimension takes its title from that client's
knowledge, which the caller passes in.

The match is plain and explainable: every word of the query must occur in some field once
both are folded (decomposed, combining marks dropped, case-folded), so "zdravi" finds
"Zdraví". Czech inflects its nouns, so a word of four letters or more also matches without
its last letter: "káva" finds "kávu" and "kávové" (through "kav"). That is all the stemming
there is. The answer names each field that matched and the text that did.

Pure: no I/O.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Final

__all__ = [
    "DIMENSION_LABELS",
    "FIELDS",
    "FieldMatch",
    "StudyText",
    "fold",
    "match",
    "query_words",
    "study_text",
]

#: The system's own dimensions and their Czech titles: ``PERSONA_DIM_LABELS`` of
#: ``apps/web/src/research/persona.ts``, which ``tests/test_project_memory_match.py``
#: holds this equal to.
DIMENSION_LABELS: Final[Mapping[str, str]] = {
    "media": "Média a informační chování",
    "nakup": "Nákupní chování",
    "finance": "Finance a cenová citlivost",
    "cena": "Cena / value for money",
    "hodnoty": "Hodnoty a postoje",
    "prace": "Práce a profesní kontext",
    "zdravi": "Zdraví",
    "duvera": "Důvěra",
    "politika": "Politické postoje",
    "ekologie": "Ekologie",
    "technologie": "Technologie a digital",
    "znacka": "Vztah ke značkám",
    "komunikace": "Komunikační styl",
    "reklama": "Reakce na reklamu",
    "vztahy": "Vztahy / domácnost",
    "rodina": "Rodina",
    "socialni_site": "Sociální sítě",
    "online": "Online chování",
}

#: The fields a study is searched on, in the order a hit lists them.
FIELDS: Final = (
    "name",
    "title",
    "goal",
    "decision_use",
    "research_questions",
    "objectives",
    "sections",
    "dimensions",
)


def fold(text: str) -> str:
    """``text`` decomposed, its combining marks dropped, case-folded: "Zdraví" -> "zdravi"."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _occurs(word: str, folded: str) -> bool:
    """``word`` in ``folded``, or -- for a word of four letters or more -- its stem."""
    return word in folded or (len(word) >= 4 and word[:-1] in folded)


def query_words(query: str) -> tuple[str, ...]:
    """The folded words of a query, each once, in order."""
    return tuple(dict.fromkeys(fold(query).split()))


@dataclass(frozen=True, slots=True)
class StudyText:
    """The texts of one study a search reads, by field. Every value is a person's text."""

    fields: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class FieldMatch:
    """A field where the query's words occur, and the texts in it that hold them."""

    field: str
    texts: tuple[str, ...]


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, Mapping):  # a question kept as an object: {"text": ...}
        for key in ("text", "question", "title"):
            found = value.get(key)
            if isinstance(found, str) and found.strip():
                return found.strip()
    return None


def _texts(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    return tuple(t for t in (_text(v) for v in values) if t)


def study_text(
    name: str,
    content: Mapping[str, Any] | None,
    *,
    client_dimension_titles: Mapping[str, str],
) -> StudyText:
    """The searchable texts of a study: its name, and its design document's when it has one.

    ``client_dimension_titles`` is the client's own dimensions (knowledge item id -> title);
    a chosen dimension that is neither canonical nor the client's is kept by its id, so it is
    still found by what the design stored.
    """
    fields: dict[str, tuple[str, ...]] = {"name": (name.strip(),) if name.strip() else ()}
    if content:
        plan = content.get("research_plan")
        plan = plan if isinstance(plan, Mapping) else {}
        fields["title"] = tuple(t for t in (_text(content.get("title")),) if t)
        fields["goal"] = tuple(t for t in (_text(content.get("goal")),) if t)
        fields["decision_use"] = tuple(t for t in (_text(content.get("decision_use")),) if t)
        fields["research_questions"] = _texts(plan.get("research_questions"))
        fields["objectives"] = _texts(plan.get("objectives"))
        sections: list[str] = []
        raw_sections = content.get("sections")
        for section in raw_sections if isinstance(raw_sections, list) else []:
            if not isinstance(section, Mapping):
                continue
            for key in ("title", "object_family"):
                found = _text(section.get(key))
                if found and found not in sections:
                    sections.append(found)
        fields["sections"] = tuple(sections)
        persona = content.get("persona_dimensions")
        approved = persona.get("approved") if isinstance(persona, Mapping) else None
        dimensions: list[str] = []
        for dimension_id in approved if isinstance(approved, list) else []:
            if not isinstance(dimension_id, str) or not dimension_id.strip():
                continue
            key = dimension_id.strip()
            title = DIMENSION_LABELS.get(key) or client_dimension_titles.get(key) or key
            if title not in dimensions:
                dimensions.append(title)
        fields["dimensions"] = tuple(dimensions)
    return StudyText(fields={f: fields.get(f, ()) for f in FIELDS})


def match(words: Iterable[str], text: StudyText) -> tuple[FieldMatch, ...] | None:
    """The fields that hold the query's words, or ``None`` when some word occurs nowhere.

    Every word must occur, folded, in at least one field of the study. A field is listed
    when it holds at least one of the words, with the texts in it that do.
    """
    wanted = tuple(words)
    if not wanted:
        return None
    folded = {f: tuple((t, fold(t)) for t in texts) for f, texts in text.fields.items()}
    for word in wanted:
        if not any(_occurs(word, f) for pairs in folded.values() for _, f in pairs):
            return None
    found: list[FieldMatch] = []
    for field_name in FIELDS:
        texts = tuple(
            t for t, f in folded.get(field_name, ()) if any(_occurs(w, f) for w in wanted)
        )
        if texts:
            found.append(FieldMatch(field_name, texts))
    return tuple(found)
