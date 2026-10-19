"""The items of a research design, and which of them differ (ADR 0026 decision 5).

An **item** is the unit a person edits and an AI proposal changes, with a stable key. A
pending proposal goes stale only when an edit touches an item the proposal changes; an
edit anywhere else leaves it applicable. This module says what the items are
(:func:`design_items`), and merges a proposal into the working copy item by item
(:func:`merge_items`). It is the server's counterpart of the web's ``proposalDiff`` and
``questionnaireReplacement`` (``apps/web/src/research/proposal-diff.ts``); a shared case file,
``tests/fixtures/design_items/cases.json``, holds the two together.

A design is two documents, the working ``content`` and its separate ``analysis``
(``study_workspace_repository.py`` saves them side by side). Their items:

* ``content``

  - ``brief``: ``title``, ``goal``, ``decision_use`` and each ``briefing.<field>``;
  - ``objective``, ``research_question``, ``hypothesis``: each entry of
    ``research_plan.objectives`` / ``research_questions`` / ``hypotheses``, keyed by its
    normalised text (whitespace collapsed, casefolded), as ``diffLists`` keys them;
  - ``tracked_set``: each of ``research_plan.tracked_sets``, by its ``id``, else by its
    normalised title (a plan's set carries no id today, ``research_agents.TrackedSet``, and the
    web keys it by title);
  - ``plan``: every other field of ``research_plan``;
  - ``section``, ``question``, ``battery``: each questionnaire section by id (its fields, with
    its questions' keys in order standing for its questions), each question by id, and each
    ``object_battery`` section by id, whole;
  - ``audience``, ``dimensions`` (``persona_dimensions``) and ``n``: one item each;
  - ``field``: every other top-level field, so that no difference falls between items.

* ``analysis``: ``objective``, ``research_question``, ``hypothesis`` and ``tracked_set`` as
  above, and each other top-level field as a ``field``.

A list that is not a list of what its items need (strings, objects) is one item, whole: a
shape the rules do not know is compared as a value, never skipped. Two entries of one list
with the same key -- two sets titled alike, a repeated question id -- stay two items, the
second keyed ``<key>#2`` (:func:`occurrence_keys`), so a merge never collapses them. Order
is no item: a merge keeps the person's order and slots in what only the proposal has.
Pure: no I/O.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal

__all__ = [
    "Documents",
    "ItemKey",
    "brief_signature",
    "design_items",
    "item_values",
    "merge_items",
    "occurrence_keys",
]

Document = Literal["content", "analysis"]

#: The plan's text lists, each item keyed by its normalised text, and the kind they become.
TEXT_LISTS: Final[tuple[tuple[str, str], ...]] = (
    ("objectives", "objective"),
    ("research_questions", "research_question"),
    ("hypotheses", "hypothesis"),
)
_TEXT_KINDS: Final = frozenset(kind for _, kind in TEXT_LISTS)
_BRIEF_FIELDS: Final = ("title", "goal", "decision_use")
#: Top-level content fields that are one item each, by the kind they are named.
_SINGLE: Final[dict[str, str]] = {
    "audience": "audience",
    "persona_dimensions": "dimensions",
    "n": "n",
}
_SECTION_KINDS: Final = frozenset({"section", "battery", "question"})


@dataclass(frozen=True, order=True, slots=True)
class ItemKey:
    """One item of a design: the document it is in, its kind, and its key within the kind.

    ``str(key)`` is ``document:kind:key`` (``content:objective:zjistit cenu``), the form it is
    stored and sent in; :meth:`parse` reads it back. A singleton item's key is empty.
    """

    document: Document
    kind: str
    key: str = ""

    def __str__(self) -> str:
        return f"{self.document}:{self.kind}:{self.key}"

    @classmethod
    def parse(cls, text: str) -> ItemKey:
        """The key ``str(key)`` wrote; anything else is a :class:`ValueError`."""
        document, sep, rest = text.partition(":")
        kind, sep2, key = rest.partition(":")
        if not sep or not sep2 or document not in ("content", "analysis") or not kind:
            raise ValueError(f"not an item key: {text!r}")
        return cls("content" if document == "content" else "analysis", kind, key)


@dataclass(frozen=True, slots=True)
class Documents:
    """A design as the working copy holds it: the content and its separate analysis."""

    content: dict[str, Any]
    analysis: dict[str, Any] | None = None

    @classmethod
    def of(cls, value: Mapping[str, Any]) -> Documents:
        """``{content, analysis}`` as a :class:`Documents`; a missing analysis is ``None``."""
        content = value.get("content")
        analysis = value.get("analysis")
        return cls(
            content=dict(content) if isinstance(content, Mapping) else {},
            analysis=dict(analysis) if isinstance(analysis, Mapping) else None,
        )


def normalise(text: str) -> str:
    """A list entry as it is keyed: whitespace collapsed and trimmed, casefolded."""
    return " ".join(text.split()).casefold()


def _mapping(value: Any) -> Mapping[str, Any]:
    """``value`` when it is an object, else an empty one."""
    return value if isinstance(value, Mapping) else {}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


# -- items ------------------------------------------------------------------------------------


def occurrence_keys(keys: Iterable[str]) -> list[str]:
    """Each key as it is keyed in its list: the second ``a`` is ``a#2``, the third ``a#3``.

    Two entries with one key -- two sets titled alike, a question id repeated -- stay two items,
    so a merge never collapses them into one and drops the other with the person's edit in it.
    """
    used: set[str] = set()
    counts: dict[str, int] = {}
    out: list[str] = []
    for k in keys:
        n = counts.get(k, 0) + 1
        candidate = k if n == 1 else f"{k}#{n}"
        while candidate in used:
            n += 1
            candidate = f"{k}#{n}"
        counts[k] = n
        used.add(candidate)
        out.append(candidate)
    return out


def _text_entries(value: Any) -> list[tuple[str, Any]] | None:
    """A list of strings as ``(key, text)``; ``None`` for another shape."""
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        return None
    return list(zip(occurrence_keys(normalise(t) for t in value), value, strict=True))


def _set_key(entry: Mapping[str, Any]) -> str:
    ident = entry.get("id")
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    title = entry.get("title")
    return normalise(title if isinstance(title, str) else "")


def _set_entries(value: Any) -> list[tuple[str, Any]] | None:
    """Tracked sets as ``(key, set)``; ``None`` when the list holds anything but objects."""
    if not isinstance(value, list) or not all(isinstance(x, Mapping) for x in value):
        return None
    keys = occurrence_keys(_set_key(e) for e in value)
    return [(k, dict(e)) for k, e in zip(keys, value, strict=True)]


def _ident(entry: Mapping[str, Any], fallback: str) -> str:
    ident = entry.get("id")
    return ident if isinstance(ident, str) and ident else fallback


def _section_entries(value: Any) -> list[tuple[str, Mapping[str, Any]]] | None:
    if not isinstance(value, list) or not all(isinstance(s, Mapping) for s in value):
        return None
    keys = occurrence_keys(_ident(sec, f"#{i}") for i, sec in enumerate(value))
    return list(zip(keys, value, strict=True))


def _section_questions(
    sections: list[tuple[str, Mapping[str, Any]]],
) -> dict[str, list[tuple[str, Any]] | None]:
    """Each section's questions as ``(key, question)``, keyed across the whole questionnaire.

    ``None`` for a battery or a section whose questions are not a list of objects: it is one
    item, whole.
    """
    raw: list[tuple[str, int, Mapping[str, Any]]] = []
    out: dict[str, list[tuple[str, Any]] | None] = {}
    for key, section in sections:
        questions = section.get("questions")
        if section.get("type") == "object_battery" or (
            not isinstance(questions, list) or not all(isinstance(q, Mapping) for q in questions)
        ):
            out[key] = None
            continue
        out[key] = []
        raw.extend((key, j, q) for j, q in enumerate(questions))
    keys = occurrence_keys(_ident(q, f"{key}#{j}") for key, j, q in raw)
    for qk, (key, _, q) in zip(keys, raw, strict=True):
        listed = out[key]
        assert listed is not None
        listed.append((qk, dict(q)))
    return out


def _section_value(
    section: Mapping[str, Any], questions: list[tuple[str, Any]] | None
) -> tuple[str, Any]:
    """A section's own item: ``battery`` whole, or ``section`` with its questions as keys."""
    if section.get("type") == "object_battery":
        return "battery", dict(section)
    if questions is None:
        return "section", dict(section)
    own = {k: v for k, v in section.items() if k != "questions"}
    own["questions"] = [k for k, _ in questions]
    return "section", own


def _plan_items(doc: Document, plan: Mapping[str, Any], out: dict[ItemKey, Any]) -> None:
    """The research plan's items: its text lists, its tracked sets and every other field."""
    for name, value in plan.items():
        kind = dict(TEXT_LISTS).get(name)
        entries = _text_entries(value) if kind else None
        if kind and entries is not None:
            for k, text in entries:
                out[ItemKey(doc, kind, k)] = text
            continue
        if name == "tracked_sets":
            sets = _set_entries(value)
            if sets is not None:
                for k, entry in sets:
                    out[ItemKey(doc, "tracked_set", k)] = entry
                continue
        out[ItemKey(doc, "plan" if doc == "content" else "field", name)] = value


def item_values(docs: Documents) -> dict[ItemKey, Any]:
    """Every item of a design and its value."""
    out: dict[ItemKey, Any] = {}
    content = docs.content
    for name, value in content.items():
        if name in _BRIEF_FIELDS:
            out[ItemKey("content", "brief", name)] = value
        elif name == "briefing" and isinstance(value, Mapping):
            for sub, v in value.items():
                out[ItemKey("content", "brief", f"briefing.{sub}")] = v
        elif name == "research_plan" and isinstance(value, Mapping):
            _plan_items("content", value, out)
        elif name == "sections" and (sections := _section_entries(value)) is not None:
            questions = _section_questions(sections)
            for k, section in sections:
                kind, own = _section_value(section, questions[k])
                out[ItemKey("content", kind, k)] = own
                for qk, q in questions[k] or []:
                    out[ItemKey("content", "question", qk)] = q
        elif name in _SINGLE:
            out[ItemKey("content", _SINGLE[name], "")] = value
        else:
            out[ItemKey("content", "field", name)] = value
    if docs.analysis is not None:
        _plan_items("analysis", docs.analysis, out)
    return out


def design_items(
    before: Documents | Mapping[str, Any], after: Documents | Mapping[str, Any]
) -> frozenset[ItemKey]:
    """The items that differ between two designs: added, removed or changed.

    ``before`` and ``after`` are ``{content, analysis}`` (or :class:`Documents`). A text item
    differs only when its normalised text is new or gone; a respelling that normalises the same
    is not a change, as the web reads it.
    """
    a = item_values(before if isinstance(before, Documents) else Documents.of(before))
    b = item_values(after if isinstance(after, Documents) else Documents.of(after))
    changed: set[ItemKey] = set()
    for key in a.keys() | b.keys():
        if key not in a or key not in b:
            changed.add(key)
            continue
        # A text item's value is its spelling: one that normalises the same is no change.
        if key.kind not in _TEXT_KINDS and _canonical(a[key]) != _canonical(b[key]):
            changed.add(key)
    return frozenset(changed)


# -- merge ------------------------------------------------------------------------------------


def _keyed_merge(
    proposed: list[tuple[str, Any]],
    current: list[tuple[str, Any]],
    touched: set[str],
) -> list[Any]:
    """One keyed list, merged: a touched entry as proposed (or gone), every other as now.

    The person's order is kept: order is no item, so a proposal never moves what is there. An
    entry only the proposal has goes in after its predecessor in the proposal, or at the end when
    it has none there. Every entry keeps its own key, so nothing is collapsed into another.
    """
    offered = dict(proposed)
    keys: list[str] = []
    values: dict[str, Any] = {}
    for k, v in current:
        if k not in touched:
            keys.append(k)
            values[k] = v
        elif k in offered:
            keys.append(k)
            values[k] = offered[k]
    order = [k for k, _ in proposed]
    for i, k in enumerate(order):
        if k not in touched or k in values:
            continue
        at = len(keys)
        for before in reversed(order[:i]):
            if before in values:
                at = keys.index(before) + 1
                break
        keys.insert(at, k)
        values[k] = offered[k]
    return [values[k] for k in keys]


def _merge_plan(
    doc: Document,
    proposed: Mapping[str, Any],
    current: Mapping[str, Any],
    touched: set[ItemKey],
) -> dict[str, Any]:
    """A research plan (or an analysis), merged field by field and list item by list item."""
    out = dict(current)
    other = "plan" if doc == "content" else "field"
    for name in sorted(proposed.keys() | current.keys()):
        kind = dict(TEXT_LISTS).get(name) or ("tracked_set" if name == "tracked_sets" else None)
        reader = _set_entries if kind == "tracked_set" else _text_entries
        mine = {t.key for t in touched if t.kind == kind} if kind else set()
        p_entries = reader(proposed.get(name)) if kind else None
        c_entries = reader(current.get(name)) if kind and name in current else []
        if kind and mine and p_entries is not None and c_entries is not None:
            out[name] = _keyed_merge(p_entries, c_entries, mine)
            continue
        if ItemKey(doc, other, name) in touched:
            if name in proposed:
                out[name] = proposed[name]
            else:
                out.pop(name, None)
    return out


def _merge_sections(
    proposed: Any, current: Any, touched: set[ItemKey]
) -> Any:  # a list of sections, or the current value untouched
    mine = {t for t in touched if t.document == "content" and t.kind in _SECTION_KINDS}
    if not mine:
        return current
    p_sections = _section_entries(proposed) or []
    c_sections = _section_entries(current) or []
    p_by, c_by = dict(p_sections), dict(c_sections)
    p_questions, c_questions = _section_questions(p_sections), _section_questions(c_sections)
    section_keys = {t.key for t in mine if t.kind in ("section", "battery")}
    question_keys = {t.key for t in mine if t.kind == "question"}
    order = _keyed_merge(
        [(k, k) for k, _ in p_sections], [(k, k) for k, _ in c_sections], section_keys
    )
    out: list[Any] = []
    for key in order:
        section = p_by[key] if key in section_keys or key not in c_by else c_by[key]
        mine_q, theirs_q = c_questions.get(key), p_questions.get(key)
        if section.get("type") == "object_battery" or (mine_q is None and theirs_q is None):
            out.append(dict(section))
            continue
        questions = (
            _keyed_merge(theirs_q or [], mine_q, question_keys)
            if key in c_by and mine_q is not None
            else [q for _, q in theirs_q or []]
        )
        out.append({**section, "questions": questions})
    return out


def merge_items(proposed: Documents, current: Documents, touched: Iterable[ItemKey]) -> Documents:
    """The proposal merged into the working copy now, item by item (ADR 0026 decision 6).

    Each item in ``touched`` takes the proposal's value, or is removed where the proposal has
    none; every other item keeps the person's. The caller has refused the merge when a touched
    item also changed in the working copy since the proposal's baseline, so no edit of the
    person's is overwritten here. An analysis the proposal leaves alone is kept as it is, never
    cleared.
    """
    touched_set = set(touched)
    content = dict(current.content)
    p = proposed.content
    for key in sorted(touched_set):
        if key.document != "content":
            continue
        if key.kind == "brief" and key.key.startswith("briefing."):
            sub = key.key[len("briefing.") :]
            briefing = dict(content.get("briefing") or {})
            p_brief = _mapping(p.get("briefing"))
            if sub in p_brief:
                briefing[sub] = p_brief[sub]
            else:
                briefing.pop(sub, None)
            content["briefing"] = briefing
            continue
        name = (
            key.key
            if key.kind in ("brief", "field")
            else next((n for n, k in _SINGLE.items() if k == key.kind), None)
        )
        if name is None:
            continue
        if name in p:
            content[name] = p[name]
        else:
            content.pop(name, None)
    plan_kinds = {"plan", "tracked_set"} | {k for _, k in TEXT_LISTS}
    if any(t.document == "content" and t.kind in plan_kinds for t in touched_set):
        p_plan = p.get("research_plan")
        c_plan = content.get("research_plan")
        content["research_plan"] = _merge_plan(
            "content",
            _mapping(p_plan),
            _mapping(c_plan),
            touched_set,
        )
    if "sections" in content or "sections" in p:
        merged = _merge_sections(p.get("sections"), content.get("sections"), touched_set)
        if merged is not None:
            content["sections"] = merged
    analysis = current.analysis
    if any(t.document == "analysis" for t in touched_set):
        analysis = _merge_plan(
            "analysis", proposed.analysis or {}, current.analysis or {}, touched_set
        )
    return Documents(content=content, analysis=analysis)


# -- the brief's signature --------------------------------------------------------------------

#: ``PROBLEM_TYPES``' keys (``apps/web/src/research/model.ts``), in their order.
PROBLEM_TYPE_KEYS: Final = (
    "price",
    "product",
    "audience",
    "communication",
    "brand",
    "innovation",
    "portfolio",
    "campaign",
    "tracking",
    "other",
)


def _js_string(value: Any) -> str:
    """``String(value || "")`` as the browser computes it, for JSON values."""
    if (
        value is None
        or value is False
        or value == ""
        or (isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0)
    ):
        return ""
    if value is True:
        return "true"
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return str(int(value)) if value.is_integer() else repr(value)
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return ",".join("" if v is None else _js_string(v) for v in value)
    return "[object Object]"


#: What ``String.prototype.trim`` removes beside the ASCII whitespace ``str.strip`` agrees on.
_JS_WHITESPACE: Final = " \t\n\r\x0b\x0c" + "".join(
    chr(c)
    for c in (0xFEFF, 0xA0, 0x1680, *range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F, 0x205F, 0x3000)
)


def _trim(text: str) -> str:
    return text.strip(_JS_WHITESPACE)


def _problem_types(content: Mapping[str, Any]) -> list[str]:
    """``selectedProblemTypes``: the brief's known problem types, first occurrence kept."""
    briefing = _mapping(content.get("briefing"))
    ui = _mapping(content.get("ui_state"))
    a: Any = briefing.get("problem_types")
    if not isinstance(a, list) or not a:
        a = ui.get("problem_types") or []
    if (not isinstance(a, list) or not a) and briefing.get("problem_type"):
        a = [briefing.get("problem_type")]
    out: list[str] = []
    for x in a if isinstance(a, list) else []:
        if isinstance(x, str) and x in PROBLEM_TYPE_KEYS and x not in out:
            out.append(x)
    return out


def brief_signature(content: Mapping[str, Any]) -> str:
    """The brief an analysis was made from: ``briefFingerprint`` (``model.ts``), byte for byte.

    The stages keep it on the analysis as ``_brief_signature`` and reuse an analysis only for the
    brief it signs. An accept that installs a brief analysis on the server signs it as the
    browser did; the shared cases pin the two to the same string.
    """
    briefing = _mapping(content.get("briefing"))
    attachments = briefing.get("attachments") or []
    signed = {
        "goal": _trim(_js_string(content.get("goal"))),
        "decision_use": _trim(_js_string(content.get("decision_use"))),
        "product_description": _trim(_js_string(briefing.get("product_description"))),
        "situation": _trim(_js_string(briefing.get("situation"))),
        "what_is_known": _trim(_js_string(briefing.get("what_is_known"))),
        "constraints": _trim(_js_string(briefing.get("constraints"))),
        "problem_types": sorted(_problem_types(content)),
        "review_comments": _js_string(briefing.get("review_comments")),
        "attachments": [
            (x.get("sha256") or x.get("url") or x.get("filename") or None)
            if isinstance(x, Mapping)
            else None
            for x in (attachments if isinstance(attachments, list) else [])
        ],
    }
    return json.dumps(signed, ensure_ascii=False, separators=(",", ":"))
