"""A questionnaire imported from a filled-in template, as 18.6.6 imported it (ADR 0018).

The questionnaire stage can load a questionnaire from the XLSX/CSV template. In 18.6.6
that was ``ui_server.import_questionnaire_payload`` (``ui_server.py:600-650``): read the
rows, turn them into question blocks and tracked sets, then pass the project through
``research_project.normalize_project`` (``research_project.py:204-376``), whose rules --
text cleaned of markup, ids slugified and made unique, objects de-duplicated, tracked-set
limits, ``StudySpec`` validation -- decide what an import finally is. This module is
that, for what an import produces, and nothing more: :func:`import_rows` returns the
normalized sections and the unit's summary, and the stage puts the sections on the
project. ``test_questionnaire_import.py`` compares it with the unit's own function
(fixtures captured by ``tools/questionnaire_import_capture.py``).

Two things the unit did are deliberately not done, both side effects of it normalizing
the *whole* project the browser sent rather than parts of the import:

* it normalized the current project first, so an import was refused when the project it
  was about to replace had an invalid section of its own;
* it returned the whole normalized project, re-cleaning fields the import never touched.

AIA reads the file alone and changes only the sections (and the plan's status, which the
stage sets as the unit did). Messages are the unit's, word for word, where the unit had a
rule; a file that cannot be read at all is refused by AIA's own words
(:mod:`aia_core.infrastructure.questionnaire_file`), not with a Python exception's text.

Pure: no I/O.
"""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Sequence
from typing import Any, Final

from pydantic import BaseModel, ConfigDict

__all__ = [
    "QUESTION_TYPES",
    "REQUIRED_COLUMNS",
    "ImportSummary",
    "ImportedQuestionnaire",
    "QuestionnaireImportRejected",
    "clean_text",
    "import_rows",
    "slugify",
    "tracked_set_warning",
    "unique_id",
]

#: ``research_project.QUESTION_TYPES``.
QUESTION_TYPES: Final = frozenset({"vyber", "multi", "skala", "otevrena"})
#: The columns an import cannot do without (``ui_server.py:612``).
REQUIRED_COLUMNS: Final = frozenset({"id", "otazka", "typ"})
#: ``PRODUCT_POLICY.json`` ``research_design.tracked_set`` for a position map, the only
#: output type an import produces: hard (min, max), recommended (min, max).
_TRACKED_SET_HARD: Final = (3, 40)
_TRACKED_SET_RECOMMENDED: Final = (4, 15)
_TRUE: Final = frozenset({"1", "true", "ano", "yes"})


class QuestionnaireImportRejected(ValueError):
    """The file does not import. ``reason`` is stable; the message is the person's."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class ImportSummary(BaseModel):
    """The unit's summary of an import: counted from the rows, before normalization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_count: int
    tracked_sets: int
    sections: int


class ImportedQuestionnaire(BaseModel):
    """What an import yields: the sections the stage puts on the project."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sections: list[dict[str, Any]]
    summary: ImportSummary
    filename: str


# --------------------------------------------------------------------------- #
# The unit's text and id rules
# --------------------------------------------------------------------------- #


def clean_text(x: Any, fallback: str = "") -> str:
    """``research_project._clean_text``: entities decoded, markup removed, spaces folded."""
    text = html.unescape(str(x if x is not None else fallback)).strip()
    # The unit's defence against malformed tool output: <item> tags and text that
    # arrives one character per line.
    text = re.sub(r"<\s*/?\s*i\s*t\s*e\s*m\s*>", "", text, flags=re.I)
    text = re.sub(r"<[^>]{1,80}>", "", text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) >= 5 and sum(len(ln) == 1 for ln in lines) / len(lines) >= 0.65:
        text = "".join(lines)
    else:
        text = "\n".join(lines) if len(lines) > 1 else (lines[0] if lines else "")
    return re.sub(r"[ \t]+", " ", text).strip()


def slugify(text: str) -> str:
    """``study_contract.slugify``: ASCII, underscores, lower case; ``x`` when nothing is left."""
    s = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s or "x"


def unique_id(base: str, used: set[str], prefix: str = "q") -> str:
    """``research_project._unique_id``: the slug, prefixed when it starts with a digit,
    numbered from ``_2`` when taken. Records the id in ``used``."""
    root = slugify(base) or prefix
    if root[0].isdigit():
        root = f"{prefix}_{root}"
    candidate, i = root, 2
    while candidate in used:
        candidate = f"{root}_{i}"
        i += 1
    used.add(candidate)
    return candidate


def tracked_set_warning(count: int) -> str:
    """``product_policy.tracked_set_warning`` for a position map."""
    (hard_min, hard_max), (rec_min, rec_max) = _TRACKED_SET_HARD, _TRACKED_SET_RECOMMENDED
    if count < hard_min or count > hard_max:
        return ""
    if count < rec_min:
        return (
            f"Sada má jen {count} položek; pro stabilnější srovnání bývá vhodné "
            f"přibližně {rec_min}\u2013{rec_max}."
        )
    if count > rec_max:
        return (
            f"Sada má {count} položek; nad {rec_max} zvaž kratší baterii, split nebo "
            "MaxDiff, ale běh není automaticky blokován."
        )
    return ""


# --------------------------------------------------------------------------- #
# The rows: import_questionnaire_payload's loop
# --------------------------------------------------------------------------- #


def _split(value: str) -> list[str]:
    return [v.strip() for v in str(value or "").replace("\n", "|").split("|") if v.strip()]


def _scale(low: str, high: str) -> tuple[int, int]:
    # int(float(...)) as the unit reads it: "5,5" or "abc" fall back to 1-10, both ends.
    try:
        return int(float(low or 1)), int(float(high or 10))
    except (ValueError, OverflowError):
        return 1, 10


def _raw_sections(rows: Sequence[Sequence[str]]) -> tuple[list[dict[str, Any]], ImportSummary]:
    if not rows:
        raise QuestionnaireImportRejected("Soubor je prázdný.", reason="empty")
    headers = [str(x).strip().lower() for x in rows[0]]
    missing = REQUIRED_COLUMNS - set(headers)
    if missing:
        raise QuestionnaireImportRejected(
            "Chybí povinné sloupce: " + ", ".join(sorted(missing)), reason="missing_columns"
        )
    index = {h: i for i, h in enumerate(headers)}

    def get(row: Sequence[str], key: str) -> str:
        i = index.get(key)
        return str(row[i]).strip() if i is not None and i < len(row) else ""

    sections: list[dict[str, Any]] = []
    blocks: dict[str, dict[str, Any]] = {}
    tracked_sets = 0
    question_count = 0
    for row in rows[1:]:
        if not any(str(x).strip() for x in row):
            continue
        qid = get(row, "id") or f"Q{question_count + 1}"
        text = get(row, "otazka")
        typ = get(row, "typ").lower()
        block = get(row, "blok") or "Dotazník"
        if not text:
            raise QuestionnaireImportRejected(f"{qid}: chybí znění otázky.", reason="invalid_row")
        if typ == "objektova_sada":
            objects = _split(get(row, "moznosti"))
            if not 4 <= len(objects) <= 15:
                raise QuestionnaireImportRejected(
                    f"{qid}: sledovaná sada potřebuje 4\u201315 srovnatelných položek.",
                    reason="invalid_row",
                )
            low, high = _scale(get(row, "skala_min"), get(row, "skala_max"))
            family = get(row, "sledovana_sada") or block or "objekty"
            sections.append(
                {
                    "id": qid,
                    "type": "object_battery",
                    "title": get(row, "sledovana_sada") or block or qid,
                    "purpose": get(row, "poznamka"),
                    "object_family": family,
                    "object_type": family,
                    "objects": objects,
                    "object_question": text
                    if "{object}" in text
                    else text.rstrip("?") + " \u2014 {object}?",
                    "scale": [low, high],
                    "scale_labels": ["minimum", "maximum"],
                    "familiarity_required": False,
                    "output_type": "pozicni_mapa",
                    "visualize": True,
                    "metadata": {"tracked_set": True, "imported": True},
                }
            )
            tracked_sets += 1
            continue
        if typ not in QUESTION_TYPES:
            raise QuestionnaireImportRejected(f"{qid}: neznámý typ {typ}.", reason="invalid_row")
        if block not in blocks:
            blocks[block] = {
                "id": f"sec_import_{len(blocks) + 1}",
                "type": "questions",
                "title": block,
                "purpose": "",
                "questions": [],
            }
            sections.append(blocks[block])
        question: dict[str, Any] = {
            "id": qid,
            "text": text,
            "typ": typ,
            "povolit_nevim": get(row, "povolit_nevim").lower() in _TRUE,
        }
        if typ in ("vyber", "multi"):
            categories = _split(get(row, "moznosti"))
            if len(categories) < 2:
                raise QuestionnaireImportRejected(
                    f"{qid}: výběrová otázka potřebuje alespoň 2 možnosti.", reason="invalid_row"
                )
            question["kategorie"] = categories
        elif typ == "skala":
            question["skala"] = list(_scale(get(row, "skala_min"), get(row, "skala_max")))
            question["popisky_skaly"] = ["minimum", "maximum"]
        else:
            question["max_slov"] = 35
        blocks[block]["questions"].append(question)
        question_count += 1
    summary = ImportSummary(
        question_count=question_count, tracked_sets=tracked_sets, sections=len(sections)
    )
    return sections, summary


# --------------------------------------------------------------------------- #
# normalize_project's rules, for the keys an import produces
# --------------------------------------------------------------------------- #


def _question(
    q: dict[str, Any], *, section_id: str, used: set[str], ordinal: int
) -> dict[str, Any]:
    """``research_project._normalize_question`` for an imported question (no filter,
    topics or metadata of its own: an import row has none)."""
    typ = clean_text(q.get("typ") or "vyber")
    if typ not in QUESTION_TYPES:  # pragma: no cover - the rows allow only these
        raise QuestionnaireImportRejected(f"Neznámý typ otázky: {typ}", reason="invalid_row")
    text = clean_text(q.get("text"))
    if not text:
        raise QuestionnaireImportRejected("Otázka nemá text.", reason="invalid_row")
    qid = unique_id(clean_text(q.get("id") or f"{section_id}_{ordinal}"), used)
    out: dict[str, Any] = {"id": qid, "text": text, "typ": typ}
    categories = [clean_text(x) for x in (q.get("kategorie") or []) if clean_text(x)]
    if typ in ("vyber", "multi"):
        if len(categories) < 2:
            raise QuestionnaireImportRejected(
                f"{qid}: výběrová otázka potřebuje alespoň 2 kategorie.", reason="invalid_row"
            )
        out["kategorie"] = categories[:24]
    if typ == "skala":
        scale = list(q.get("skala") or [1, 10])[:2]
        if len(scale) != 2:  # pragma: no cover - the rows always give two ends
            scale = [1, 10]
        out["skala"] = [int(scale[0]), int(scale[1])]
        labels = [clean_text(x) for x in (q.get("popisky_skaly") or [])][:2]
        if len(labels) == 2 and all(labels):
            out["popisky_skaly"] = labels
    if typ == "otevrena":
        out["max_slov"] = max(5, min(120, int(q.get("max_slov") or 35)))
    out["povolit_nevim"] = bool(q.get("povolit_nevim", False))
    metadata = dict(q.get("metadata") or {})
    metadata.update(
        {
            "research_section": section_id,
            "research_section_type": "questions",
            "mapped_object": False,
        }
    )
    out["metadata"] = metadata
    return out


def _battery(sec: dict[str, Any], *, section_id: str, title: str, purpose: str) -> dict[str, Any]:
    """normalize_project's tracked-set branch, and the ``StudySpec`` checks it makes."""
    family = clean_text(sec.get("object_family") or sec.get("object_type"))
    objects = list(
        dict.fromkeys(clean_text(x) for x in (sec.get("objects") or []) if clean_text(x))
    )
    if not family:
        raise QuestionnaireImportRejected(
            f"{title}: pojmenuj typ sledovaných položek (např. média, emoce, značky, vztahy).",
            reason="invalid_row",
        )
    output_type = clean_text(sec.get("output_type") or "pozicni_mapa")
    if output_type != "pozicni_mapa":  # pragma: no cover - an import makes position maps only
        raise QuestionnaireImportRejected("unsupported output type", reason="invalid_row")
    hard_min, hard_max = _TRACKED_SET_HARD
    if not hard_min <= len(objects) <= hard_max:
        raise QuestionnaireImportRejected(
            f"{title}: tento typ výstupu potřebuje {hard_min}\u2013{hard_max} srovnatelných "
            "položek stejného typu.",
            reason="invalid_row",
        )
    familiarity = bool(sec.get("familiarity_required", False))
    question = clean_text(sec.get("object_question") or "Jak hodnotíte položku {object}?")
    if "{object}" not in question:  # pragma: no cover - the rows always carry {object}
        question = question.rstrip(" ?") + " {object}?"
    labels = [clean_text(x) for x in (sec.get("scale_labels") or ["vůbec", "velmi"])][:2]
    if len(labels) != 2 or not all(labels):  # pragma: no cover - the rows give both
        labels = ["vůbec", "velmi"]
    metadata = dict(sec.get("metadata") or {})
    metadata.setdefault("tracked_set", True)
    metadata.setdefault("object_type", family)
    warning = tracked_set_warning(len(objects))
    if warning:
        metadata.setdefault("design_warning", warning)
    # StudySpec(**spec) (study_contract.py:81-121,188-214): it writes these two into the
    # metadata it is given -- the same dict the section keeps -- and refuses objects
    # whose slugs collide. Its other checks cannot fail for an import.
    metadata.setdefault("object_family", family)
    metadata.setdefault("familiarity_required", familiarity)
    slugs = [slugify(o) for o in objects]
    if len(set(slugs)) != len(slugs):
        raise QuestionnaireImportRejected(
            "Objekty po slugifikaci nemají unikátní názvy.", reason="invalid_row"
        )
    return {
        "id": section_id,
        "type": "object_battery",
        "title": title,
        "purpose": purpose,
        "object_family": family,
        "object_type": family,
        "objects": objects,
        "object_question": question,
        "scale_labels": labels,
        "familiarity_required": familiarity,
        "output_type": output_type,
        "visualize": bool(sec.get("visualize", True)),
        "metadata": metadata,
    }


def _normalize(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    section_ids: set[str] = set()
    question_ids: set[str] = set()
    for i, sec in enumerate(raw, start=1):
        kind = clean_text(sec.get("type") or "questions")
        sid = unique_id(
            clean_text(sec.get("id") or sec.get("title") or f"sekce_{i}"), section_ids, "sec"
        )
        title = clean_text(
            sec.get("title") or ("Sledovaná sada" if kind == "object_battery" else f"Blok {i}")
        )
        purpose = clean_text(sec.get("purpose"))
        if kind == "questions":
            questions = [
                _question(q, section_id=sid, used=question_ids, ordinal=qi)
                for qi, q in enumerate(sec.get("questions") or [], start=1)
            ]
            sections.append(
                {
                    "id": sid,
                    "type": kind,
                    "title": title,
                    "purpose": purpose,
                    "questions": questions,
                }
            )
            continue
        sections.append(_battery(sec, section_id=sid, title=title, purpose=purpose))
    return sections


def import_rows(rows: Sequence[Sequence[str]], *, filename: str) -> ImportedQuestionnaire:
    """The questionnaire in ``rows`` (the header first), as the unit imported it.

    Raises :class:`QuestionnaireImportRejected` with the unit's message when a row
    breaks one of its rules. The summary counts what the rows held, as the unit's did.
    """
    raw, summary = _raw_sections(rows)
    return ImportedQuestionnaire(sections=_normalize(raw), summary=summary, filename=filename)
