"""A questionnaire table given to the Lead, made a proposal (lead-orchestration LO18b). Pure.

The table is read by the template import (``questionnaire_import``) with no model; this module
makes the design the proposal would write, in one of two modes the researcher chooses (Nigel,
2026-11-01: "Yes to both" -- replace the existing sections, or "fill in questions that are not
there"):

* **Nahradit** (:attr:`ImportMode.REPLACE`): the question sections and object batteries the
  copy holds are replaced by the imported ones, as an AI build replaces them
  (``research_agents.replaceable_section``: a standard instrument or any other section kept).
* **Doplnit** (:attr:`ImportMode.ADD`): the copy is kept; an imported question is there when a
  question has the same wording, a tracked set when one has the same title (case and spaces
  folded); what is not there joins the questions section of the same title, else a section of
  its own.

Imported ids are kept unless the copy already uses them, then made unique as the AI build makes
its own (``_new`` appended). With no question section in the copy, nothing is asked: the import
replaces (:func:`has_question_sections`).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from enum import StrEnum
from typing import Any, Final

from .ai_contracts import canonical_json
from .research_agents import replaceable_section

__all__ = [
    "IMPORT_MAX_BYTES",
    "ImportMode",
    "ImportTooLarge",
    "has_question_sections",
    "import_proposal",
]

#: The most bytes of imported sections a proposal carries (canonical JSON).
IMPORT_MAX_BYTES: Final = 256 * 1024


class ImportMode(StrEnum):
    REPLACE = "replace"
    ADD = "add"


class ImportTooLarge(ValueError):
    """The imported questionnaire is larger than :data:`IMPORT_MAX_BYTES`."""

    reason = "questionnaire_too_large"


def has_question_sections(content: Mapping[str, Any]) -> bool:
    """Whether the copy holds a section a questionnaire proposal would replace."""
    return any(
        isinstance(s, Mapping) and replaceable_section(s) for s in content.get("sections") or ()
    )


def _fold(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


class _Ids:
    """Ids already used in the design; a taken one is made unique by ``_new``."""

    def __init__(self, sections: Sequence[Mapping[str, Any]]) -> None:
        self._used = {s.get("id") for s in sections}
        self._used.update(q.get("id") for s in sections for q in s.get("questions") or ())

    def take(self, candidate: str) -> str:
        while candidate in self._used:
            candidate += "_new"
        self._used.add(candidate)
        return candidate


def _place(section: dict[str, Any], ids: _Ids) -> dict[str, Any]:
    """An imported section with ids unique in the design, its questions naming it."""
    section["id"] = ids.take(str(section.get("id") or "sec_import"))
    for question in section.get("questions") or ():
        _place_question(question, section["id"], ids)
    return section


def _place_question(question: dict[str, Any], section_id: str, ids: _Ids) -> None:
    question["id"] = ids.take(str(question.get("id") or "q"))
    metadata = question.get("metadata")
    if isinstance(metadata, dict) and "research_section" in metadata:
        metadata["research_section"] = section_id


def _add(kept: list[dict[str, Any]], imported: list[dict[str, Any]], ids: _Ids) -> None:
    wordings = {_fold(q.get("text")) for s in kept for q in s.get("questions") or ()}
    sets = {_fold(s.get("title")) for s in kept if s.get("type") == "object_battery"}
    for section in imported:
        if section.get("type") == "object_battery":
            if _fold(section.get("title")) not in sets:
                kept.append(_place(section, ids))
                sets.add(_fold(section.get("title")))
            continue
        new = [q for q in section.get("questions") or () if _fold(q.get("text")) not in wordings]
        if not new:
            continue
        wordings.update(_fold(q.get("text")) for q in new)
        home = next(
            (
                s
                for s in kept
                # Never into a standard instrument: a proposal keeps it as it is.
                if s.get("type") == "questions"
                and replaceable_section(s)
                and _fold(s.get("title")) == _fold(section.get("title"))
            ),
            None,
        )
        if home is None:
            kept.append(_place({**section, "questions": new}, ids))
            continue
        for question in new:
            _place_question(question, str(home.get("id")), ids)
            home.setdefault("questions", []).append(question)


def import_proposal(
    baseline: Mapping[str, Any], sections: Sequence[Mapping[str, Any]], mode: ImportMode
) -> dict[str, Any]:
    """What a proposal from an imported questionnaire holds, as an agent job's result does:
    ``proposal`` (the imported sections and the mode, what the review reads) and ``project``
    (the design it would write). Refused (:class:`ImportTooLarge`) above the bound."""
    if len(canonical_json(list(sections)).encode("utf-8")) > IMPORT_MAX_BYTES:
        raise ImportTooLarge(f"the imported questionnaire exceeds {IMPORT_MAX_BYTES} bytes")
    project = deepcopy(dict(baseline))
    imported = [deepcopy(dict(s)) for s in sections]
    current = [dict(s) for s in project.get("sections") or ()]
    if mode is ImportMode.REPLACE:
        kept = [s for s in current if not replaceable_section(s)]
        ids = _Ids(kept)
        project["sections"] = kept + [_place(s, ids) for s in imported]
    else:
        ids = _Ids(current)
        _add(current, imported, ids)
        project["sections"] = current
    return {
        "proposal": {"sections": [deepcopy(dict(s)) for s in sections], "mode": mode.value},
        "project": project,
    }
