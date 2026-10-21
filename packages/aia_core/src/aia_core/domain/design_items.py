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
    ``research_plan.objectives`` / ``research_questions`` / ``hypotheses``, keyed by its stable id
    (:mod:`.item_ids`, WCE1): the id its id list gives it, or, for content written before ids, the
    id derived from its wording -- one id per normalised wording and occurrence, so such content
    has exactly the items it had when they were keyed by text (:func:`legacy_keys` reads an id
    key back as the text key it replaces, and the shared cases are checked through it);
  - ``tracked_set``: each of ``research_plan.tracked_sets``, by its ``id``, else by its
    normalised title (a plan's set carries no id today, ``research_agents.TrackedSet``, and the
    web keys it by title);
  - ``plan``: every other field of ``research_plan``;
  - ``section``, ``question``, ``battery``: each questionnaire section by id (its fields, with
    its questions' keys in order standing for its questions; a section without one by the id the
    compiler gives it, ``item_ids.section_ids``), each question by id, and each
    ``object_battery`` section by id, whole. An id list (``kategorie_ids``, ``object_ids``) is no
    part of an item's value: it names the parts, it does not change them;
  - ``audience``, ``dimensions`` (``persona_dimensions``) and ``n``: one item each;
  - ``field``: every other top-level field, so that no difference falls between items.

* ``analysis``: ``objective``, ``research_question``, ``hypothesis`` and ``tracked_set`` as
  above, and each other top-level field as a ``field``.

A list that is not a list of what its items need (strings, objects) is one item, whole: a
shape the rules do not know is compared as a value, never skipped. Two entries of one list
with the same key -- two sets titled alike, a repeated question id -- stay two items, the
second keyed ``<key>#2`` (:func:`occurrence_keys`), so a merge never collapses them. Order
is no item: a merge keeps the person's order and slots in what only the proposal has. (Order and
the field-level view, D-06, are :mod:`.design_fields`'.) Pure: no I/O.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal

from .item_ids import ID_LISTS, SIDECAR_KEYS, Entry, bound_of, fold, list_ids, with_item_ids

__all__ = [
    "Documents",
    "ItemKey",
    "ambiguous_legacy_keys",
    "brief_signature",
    "design_items",
    "from_legacy_keys",
    "item_values",
    "legacy_keys",
    "merge_items",
    "named_items",
    "occurrence_keys",
    "wordings",
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
    """A list entry as it is keyed: whitespace collapsed and trimmed, casefolded. The one folding,
    :func:`.item_ids.fold`, so a derived id and the text key it replaces are one to one."""
    return fold(text)


def _mapping(value: Any) -> Mapping[str, Any]:
    """``value`` when it is an object, else an empty one."""
    return value if isinstance(value, Mapping) else {}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


# -- items ------------------------------------------------------------------------------------

#: The plan's text lists: each list's id list and the kind its items are (``item_ids.ID_LISTS``).
_TEXT_LIST_IDS: Final[dict[str, tuple[str, str]]] = {
    list_key: (ids_key, kind) for list_key, ids_key, kind, _ in ID_LISTS
}


def _resolve(docs: Documents, previous: Documents | None = None) -> Documents:
    """``docs`` with every item's id written in (:func:`.item_ids.with_item_ids`)."""
    content, analysis = with_item_ids(
        docs.content,
        docs.analysis,
        previous=(previous.content, previous.analysis) if previous is not None else None,
    )
    return Documents(content=content, analysis=analysis)


def _documents(value: Documents | Mapping[str, Any]) -> Documents:
    return value if isinstance(value, Documents) else Documents.of(value)


def _strip(value: Any) -> Any:
    """An item's value without the id lists that name its parts (they are no part of it)."""
    if isinstance(value, Mapping):
        return {k: v for k, v in value.items() if k not in SIDECAR_KEYS}
    return value


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


def _text_entries(holder: Mapping[str, Any], name: str) -> list[tuple[str, Any]] | None:
    """A plan list of strings as ``(id, text)``, by the ids written in; ``None`` for another
    shape (or a list without them)."""
    spec = _TEXT_LIST_IDS.get(name)
    value = holder.get(name)
    if spec is None or not isinstance(value, list):
        return None
    ids = list_ids(holder, name, spec[0])
    return list(zip(ids, value, strict=True)) if ids is not None else None


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


def _section_entries(value: Any, raw: Any = None) -> list[tuple[str, Mapping[str, Any]]] | None:
    """Sections as ``(key, section)``: keyed by ``value``'s ids (the sections with their ids
    written in), each valued as ``raw``'s section at the same place when ``raw`` is given."""
    if not isinstance(value, list) or not all(isinstance(s, Mapping) for s in value):
        return None
    keys = occurrence_keys(_ident(sec, f"#{i}") for i, sec in enumerate(value))
    values = raw if isinstance(raw, list) and len(raw) == len(value) else value
    if not all(isinstance(s, Mapping) for s in values):
        values = value
    return list(zip(keys, values, strict=True))


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
        return "battery", _strip(section)
    if questions is None:
        return "section", dict(section)
    own = {k: v for k, v in section.items() if k != "questions"}
    own["questions"] = [k for k, _ in questions]
    return "section", own


def _plan_items(doc: Document, plan: Mapping[str, Any], out: dict[ItemKey, Any]) -> None:
    """The research plan's items: its text lists, its tracked sets and every other field."""
    for name, value in plan.items():
        if name in SIDECAR_KEYS:
            continue
        entries = _text_entries(plan, name)
        if entries is not None:
            kind = _TEXT_LIST_IDS[name][1]
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


def item_values(docs: Documents, *, previous: Documents | None = None) -> dict[ItemKey, Any]:
    """Every item of a design and its value, keyed by its id (read against ``previous``, the
    baseline, where a list carries no ids of its own; :mod:`.item_ids`)."""
    out: dict[ItemKey, Any] = {}
    resolved = _resolve(docs, previous)
    content = resolved.content
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
                    out[ItemKey("content", "question", qk)] = _strip(q)
        elif name in _SINGLE:
            out[ItemKey("content", _SINGLE[name], "")] = value
        else:
            out[ItemKey("content", "field", name)] = value
    if resolved.analysis is not None:
        _plan_items("analysis", resolved.analysis, out)
    return out


def _same(key: ItemKey, a: Any, b: Any) -> bool:
    # A text item's value is its spelling: one that normalises the same is no change.
    if key.kind in _TEXT_KINDS and isinstance(a, str) and isinstance(b, str):
        return normalise(a) == normalise(b)
    return _canonical(a) == _canonical(b)


def design_items(
    before: Documents | Mapping[str, Any], after: Documents | Mapping[str, Any]
) -> frozenset[ItemKey]:
    """The items that differ between two designs: added, removed or changed.

    ``before`` and ``after`` are ``{content, analysis}`` (or :class:`Documents`); ``after``'s ids
    are read against ``before``. A text item differs when its id is new or gone, or its
    normalised wording changed (a reword its id list records is one changed item); a respelling
    that normalises the same is not a change, as the web reads it.
    """
    b_docs = _documents(before)
    a = item_values(b_docs)
    b = item_values(_documents(after), previous=b_docs)
    changed: set[ItemKey] = set()
    for key in a.keys() | b.keys():
        if key not in a or key not in b or not _same(key, a[key], b[key]):
            changed.add(key)
    return frozenset(changed)


# -- the text keys ids replace ------------------------------------------------------------------


def _text_key_map(docs: Documents) -> dict[ItemKey, ItemKey]:
    """Each plan-list item's id key and the text key it had before ids (normalised, counted)."""
    out: dict[ItemKey, ItemKey] = {}
    plan = docs.content.get("research_plan")
    homes: tuple[tuple[Document, Any], ...] = (("content", plan), ("analysis", docs.analysis))
    for doc, holder in homes:
        if not isinstance(holder, Mapping):
            continue
        for list_key, ids_key, kind, _ in ID_LISTS:
            ids = list_ids(holder, list_key, ids_key)
            if ids is None:
                continue
            texts = occurrence_keys(normalise(t) for t in holder[list_key])
            for ident, text in zip(ids, texts, strict=True):
                out[ItemKey(doc, kind, ident)] = ItemKey(doc, kind, text)
    return out


def _section_keys(sections: Any) -> list[tuple[ItemKey, list[ItemKey]]] | None:
    """Each section's key and its questions' keys, in order; ``None`` for a shape keyed whole."""
    entries = _section_entries(sections)
    if entries is None:
        return None
    questions = _section_questions(entries)
    out: list[tuple[ItemKey, list[ItemKey]]] = []
    for key, section in entries:
        kind = "battery" if section.get("type") == "object_battery" else "section"
        held = [ItemKey("content", "question", q) for q, _ in questions[key] or []]
        out.append((ItemKey("content", kind, key), held))
    return out


def _section_key_map(raw: Documents, resolved: Documents) -> dict[ItemKey, ItemKey]:
    """Each section's and question's key now and the key it had before ids, where they differ: a
    section without an id was ``#<i>`` and is the compiler's id now, and its questions without an
    id were ``#<i>#<j>`` and are ``<id>#<j>``."""
    before = _section_keys(raw.content.get("sections"))
    now = _section_keys(resolved.content.get("sections"))
    if before is None or now is None or len(before) != len(now):
        return {}
    out: dict[ItemKey, ItemKey] = {}
    for (old_key, old_held), (new_key, new_held) in zip(before, now, strict=True):
        if old_key != new_key:
            out[new_key] = old_key
        for old_q, new_q in zip(old_held, new_held, strict=True):
            if old_q != new_q:
                out[new_q] = old_q
    return out


def _legacy_map(docs: Documents, previous: Documents | None = None) -> dict[ItemKey, ItemKey]:
    """Every key ``design_items`` gives now with the key it gave before ids, where they differ."""
    resolved = _resolve(docs, previous)
    return {**_text_key_map(resolved), **_section_key_map(docs, resolved)}


def _key_maps(
    before: Documents | Mapping[str, Any], after: Documents | Mapping[str, Any]
) -> tuple[dict[ItemKey, ItemKey], dict[ItemKey, ItemKey]]:
    b_docs = _documents(before)
    return _legacy_map(b_docs), _legacy_map(_documents(after), b_docs)


def legacy_keys(
    keys: Iterable[ItemKey],
    before: Documents | Mapping[str, Any],
    after: Documents | Mapping[str, Any],
) -> frozenset[ItemKey]:
    """``keys`` (``design_items(before, after)``) read back as the keys ``design_items`` returned
    before ids: a plan-list item by its normalised text, a section without an id by its place
    (``#<i>``) and its questions without one by theirs (``#<i>#<j>``). What the shared cases are
    written in. For content without id lists the two are one to one (one folding for both)."""
    in_before, in_after = _key_maps(before, after)
    return frozenset(in_before.get(k) or in_after.get(k) or k for k in keys)


def from_legacy_keys(
    keys: Iterable[ItemKey],
    before: Documents | Mapping[str, Any],
    after: Documents | Mapping[str, Any],
) -> frozenset[ItemKey]:
    """Keys recorded before WCE1 as ``design_items`` keys them now: a plan-list item by its id, a
    section without an id by the compiler's, its questions without one under it. A worker recorded
    a proposal's ``touched_items`` before the deploy and a person accepts it after. A key that
    already names an item now is kept; one that names nothing in either design is kept too, and
    the caller refuses it (:func:`named_items`), never merging past it."""
    in_before, in_after = _key_maps(before, after)
    ids = in_before.keys() | in_after.keys()
    by_old: dict[ItemKey, ItemKey] = {}
    for source in (in_after, in_before):  # the baseline's reading wins
        by_old.update({old: new for new, old in source.items()})
    return frozenset(k if k in ids else by_old.get(k, k) for k in keys)


def ambiguous_legacy_keys(
    keys: Iterable[ItemKey],
    before: Documents | Mapping[str, Any],
    after: Documents | Mapping[str, Any],
) -> frozenset[ItemKey]:
    """The keys recorded before WCE1 that name one item in ``before`` and another in ``after``: a
    place (``#0``) held by one section in the baseline and by a different one in the proposal. Read
    by either side alone, the other's change would be dropped; the caller refuses them."""
    in_before, in_after = _key_maps(before, after)
    ids = in_before.keys() | in_after.keys()
    old_before = {old: new for new, old in in_before.items()}
    old_after = {old: new for new, old in in_after.items()}
    return frozenset(
        k
        for k in keys
        if k not in ids and k in old_before and k in old_after and old_before[k] != old_after[k]
    )


def named_items(
    before: Documents | Mapping[str, Any], after: Documents | Mapping[str, Any]
) -> frozenset[ItemKey]:
    """Every item key either design has (``after`` read against ``before``): what a recorded
    ``touched_items`` may name."""
    b_docs = _documents(before)
    return frozenset(item_values(b_docs).keys() | item_values(_documents(after), previous=b_docs))


def wordings(
    keys: Iterable[ItemKey],
    baseline: Documents | Mapping[str, Any],
    current: Documents | Mapping[str, Any],
) -> dict[ItemKey, str]:
    """The wording each of ``keys`` names, to say a refusal to a person: a plan-list item's text or
    a question's, as ``current`` has it (read against ``baseline``), else as ``baseline`` had it --
    an item the person reworded or removed is named by an id ``current`` may no longer hold."""
    b_docs = _documents(baseline)
    values = {**item_values(b_docs), **item_values(_documents(current), previous=b_docs)}
    out: dict[ItemKey, str] = {}
    for key in keys:
        value = values.get(key)
        if key.kind == "question" and isinstance(value, Mapping):
            value = value.get("text")
        elif key.kind not in _TEXT_KINDS:
            continue
        if isinstance(value, str) and value.strip():
            out[key] = value.strip()
    return out


# -- merge ------------------------------------------------------------------------------------


def _keyed_merge(
    proposed: list[tuple[str, Any]],
    current: list[tuple[str, Any]],
    touched: set[str],
) -> list[tuple[str, Any]]:
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
    return [(k, values[k]) for k in keys]


Side = tuple[Mapping[str, Any], Mapping[str, Any]]


def _merge_plan(
    doc: Document, proposed: Side, current: Side, touched: set[ItemKey]
) -> dict[str, Any]:
    """A research plan (or an analysis), merged field by field and list item by list item.

    Each side is ``(as stored, with its ids written in)``: keyed by the ids, valued as stored. A
    merged text list keeps an id list when the person's copy has one."""
    (p_raw, p_ids), (c_raw, c_ids) = proposed, current
    out = dict(c_raw)
    other = "plan" if doc == "content" else "field"
    for name in sorted(p_raw.keys() | c_raw.keys()):
        if name in SIDECAR_KEYS:
            continue
        if name in _TEXT_LIST_IDS:
            ids_key, kind = _TEXT_LIST_IDS[name]
            mine = {t.key for t in touched if t.kind == kind}
            p_entries = _text_entries(p_ids, name) if name in p_raw else None
            c_entries = _text_entries(c_ids, name) if name in c_raw else []
            if mine and p_entries is not None and c_entries is not None:
                merged = _keyed_merge(p_entries, c_entries, mine)
                out[name] = [v for _, v in merged]
                if ids_key in c_raw:
                    out[ids_key] = [Entry(k, bound_of(v)).as_json() for k, v in merged]
                continue
        elif name == "tracked_sets":
            mine = {t.key for t in touched if t.kind == "tracked_set"}
            p_sets = _set_entries(p_raw.get(name))
            c_sets = _set_entries(c_raw.get(name)) if name in c_raw else []
            if mine and p_sets is not None and c_sets is not None:
                out[name] = [v for _, v in _keyed_merge(p_sets, c_sets, mine)]
                continue
        if ItemKey(doc, other, name) in touched:
            if name in p_raw:
                out[name] = p_raw[name]
            else:
                out.pop(name, None)
    return out


def _merge_sections(
    proposed: tuple[Any, Any], current: tuple[Any, Any], touched: set[ItemKey]
) -> Any:  # a list of sections, or the current value untouched
    """The questionnaire, merged section by section and question by question. Each side is
    ``(as stored, with its ids written in)``: keyed by the ids, valued as stored."""
    (p_raw, p_ids), (c_raw, c_ids) = proposed, current
    mine = {t for t in touched if t.document == "content" and t.kind in _SECTION_KINDS}
    if not mine:
        return c_raw
    p_sections = _section_entries(p_ids, p_raw) or []
    c_sections = _section_entries(c_ids, c_raw) or []
    p_by, c_by = dict(p_sections), dict(c_sections)
    p_questions, c_questions = _section_questions(p_sections), _section_questions(c_sections)
    section_keys = {t.key for t in mine if t.kind in ("section", "battery")}
    question_keys = {t.key for t in mine if t.kind == "question"}
    order = _keyed_merge(
        [(k, k) for k, _ in p_sections], [(k, k) for k, _ in c_sections], section_keys
    )
    out: list[Any] = []
    for key, _ in order:
        section = p_by[key] if key in section_keys or key not in c_by else c_by[key]
        mine_q, theirs_q = c_questions.get(key), p_questions.get(key)
        if section.get("type") == "object_battery" or (mine_q is None and theirs_q is None):
            out.append(dict(section))
            continue
        questions = (
            [v for _, v in _keyed_merge(theirs_q or [], mine_q, question_keys)]
            if key in c_by and mine_q is not None
            else [q for _, q in theirs_q or []]
        )
        out.append({**section, "questions": questions})
    return out


def merge_items(
    proposed: Documents,
    current: Documents,
    touched: Iterable[ItemKey],
    *,
    baseline: Documents | None = None,
) -> Documents:
    """The proposal merged into the working copy now, item by item (ADR 0026 decision 6).

    Each item in ``touched`` takes the proposal's value, or is removed where the proposal has
    none; every other item keeps the person's. The caller has refused the merge when a touched
    item also changed in the working copy since the proposal's baseline, so no edit of the
    person's is overwritten here. An analysis the proposal leaves alone is kept as it is, never
    cleared. ``baseline`` is the design ``touched`` was computed against: both sides' ids are read
    against it, as :func:`design_items` read them. Nothing is stored with an id it did not have,
    but a merged plan list whose working copy keeps an id list keeps it, lined up.
    """
    touched_set = set(touched)
    p_res, c_res = _resolve(proposed, baseline), _resolve(current, baseline)
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
        content["research_plan"] = _merge_plan(
            "content",
            (_mapping(p.get("research_plan")), _mapping(p_res.content.get("research_plan"))),
            (
                _mapping(content.get("research_plan")),
                _mapping(c_res.content.get("research_plan")),
            ),
            touched_set,
        )
    if "sections" in content or "sections" in p:
        merged = _merge_sections(
            (p.get("sections"), p_res.content.get("sections")),
            (content.get("sections"), c_res.content.get("sections")),
            touched_set,
        )
        if merged is not None:
            content["sections"] = merged
    analysis = current.analysis
    if any(t.document == "analysis" for t in touched_set):
        analysis = _merge_plan(
            "analysis",
            (proposed.analysis or {}, p_res.analysis or {}),
            (current.analysis or {}, c_res.analysis or {}),
            touched_set,
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
