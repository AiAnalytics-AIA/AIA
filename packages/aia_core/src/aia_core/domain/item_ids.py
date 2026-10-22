"""Stable item identity in a research design (``working-copy-edit-ops`` WCE1, ADR 0029 decision 2).

An item a person edits keeps one id for its life: a reword is the same item with new words, not a
remove and an add. The ids live **beside** the lists they name, so every reader of a list of
strings reads it exactly as before and nothing a run compiles changes:

* the plan's ``objectives``, ``research_questions`` and ``hypotheses`` (in ``research_plan`` and in
  the separate analysis document) carry ``objective_ids``, ``research_question_ids`` and
  ``hypothesis_ids``;
* a question's options (``kategorie``) carry ``kategorie_ids``;
* a tracked set's objects (an ``object_battery`` section's ``objects``) carry ``object_ids``;
* a section without an id gets the id the compiler already gives it (``research_design``
  ``compile_design``: the section's title, slugged and made unique in order), so the compiled
  specification, its fingerprint and every respondent column stay what they were. A question keeps
  the id it has; one without stays keyed by its place, as before.

Each entry of an id list is ``{"id": ..., "bound": ...}``: the id, and a hash of the (folded)
wording it was last given with. The binding is what lets the list be read correctly after a writer
that does not know the ids changed the wording beside them (the web's stages before WCE3, a model's
proposal spread over its baseline, an accepted Lead edit before WCE2):

1. an entry whose bound wording is still in the list names that wording's position, in order (a
   longest common subsequence, so the anchors never cross), and an item moved elsewhere keeps its
   entry by its wording;
2. between two anchors, as many unread entries as positions are the same items reworded in place,
   in order; any other count is not guessed;
3. every other position takes an id derived from its wording: ``<prefix>`` and ten hex digits of
   FNV-1a 64 over ``kind``, the folded wording and its occurrence (``-2`` … on a clash). Content
   written before WCE1 has no id lists at all, so its ids are exactly these, the same on every read
   and in the web (``apps/web/src/research/item-ids.ts``; one case file,
   ``tests/fixtures/item_ids/cases.json``, holds the two together).

A list without id entries of its own is read against ``previous`` (the baseline a proposal was
made on), by wording only: a model's or an importer's new list is matched to what was there, and a
new wording is a new item, never a guess at which old one it replaced.

Nothing here writes a stored document: :func:`with_item_ids` returns the design with its ids, for a
writer to store (the web, behind ``AIA_WEB_STABLE_ITEM_IDS``) or for :mod:`.design_items` to key by.
:func:`follow_rewords` carries a reworded research question's links (the questionnaire items that
measure it, the comparison that answers it) to its new wording. Pure: stdlib only.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from functools import cache
from types import MappingProxyType
from typing import Any, Final

__all__ = [
    "ID_LISTS",
    "OBJECT_IDS",
    "OPTION_IDS",
    "SIDECAR_KEYS",
    "Entry",
    "bound_of",
    "case_folds",
    "derived_id",
    "fnv10",
    "fold",
    "follow_rewords",
    "ids_by_kind",
    "list_ids",
    "reconcile",
    "section_ids",
    "settle_item_ids",
    "stores_item_ids",
    "with_item_ids",
]

#: The plan's id-bearing lists: the list, its id list, the kind (``design_items``') and its prefix.
ID_LISTS: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("objectives", "objective_ids", "objective", "obj_"),
    ("research_questions", "research_question_ids", "research_question", "rq_"),
    ("hypotheses", "hypothesis_ids", "hypothesis", "hyp_"),
)
#: A question's options' ids (``kategorie``), and a tracked set's objects' ids (``objects``).
OPTION_IDS: Final = "kategorie_ids"
OBJECT_IDS: Final = "object_ids"
#: Every key an id list is kept under: never an item or a field of its own.
SIDECAR_KEYS: Final = frozenset({s for _, s, _, _ in ID_LISTS} | {OPTION_IDS, OBJECT_IDS})

_OPTION_PREFIX: Final = "opt_"
_OBJECT_PREFIX: Final = "o_"
_ID: Final = re.compile(r"^[A-Za-z0-9_.\-]{1,80}$")
_SURROGATE: Final = re.compile("[\ud800-\udfff]")
_REPLACEMENT: Final = "\ufffd"
_FNV_OFFSET: Final = 0xCBF29CE484222325
_FNV_PRIME: Final = 0x100000001B3
_MASK: Final = (1 << 64) - 1


def fold(text: str) -> str:
    """A wording as identity compares it: whitespace collapsed and trimmed (``str.split``'s
    whitespace), case-folded (``str.casefold``): exactly how ``design_items`` keyed a list entry by
    its text before ids (``normalise`` is this function), so content stored before has one derived
    id per old text key, ``ß`` and ``ς`` included. The web folds the same way (``item-ids.ts``:
    lower-casing plus the code points :func:`case_folds` lists)."""
    return " ".join(text.split()).casefold()


@cache
def case_folds() -> Mapping[str, str]:
    """Every code point whose case folding is not its lower-casing (``ß`` -> ``ss``, final sigma to
    sigma): what the web adds to ``toLowerCase`` to fold as :func:`fold` does. The case file pins
    it. Built on first use (it reads every code point once)."""
    out: dict[str, str] = {}
    for code in range(sys.maxunicode + 1):
        if 0xD800 <= code <= 0xDFFF:
            continue
        ch = chr(code)
        if ch.casefold() != ch.lower():
            out[ch] = ch.casefold()
    return MappingProxyType(out)


def fnv10(text: str) -> str:
    """Ten hex digits of FNV-1a 64 over ``text`` as UTF-8 (a lone surrogate as U+FFFD, as the
    browser's ``TextEncoder`` writes it), mixed by MurmurHash3's 64-bit finaliser so that two
    wordings one character apart do not read alike."""
    h = _FNV_OFFSET
    for byte in _SURROGATE.sub(_REPLACEMENT, text).encode("utf-8"):
        h = ((h ^ byte) * _FNV_PRIME) & _MASK
    h ^= h >> 33
    h = (h * 0xFF51AFD7ED558CCD) & _MASK
    h ^= h >> 33
    h = (h * 0xC4CEB9FE1A85EC53) & _MASK
    h ^= h >> 33
    return f"{h:016x}"[:10]


def bound_of(text: str) -> str:
    """The binding an id entry records: the hash of the folded wording."""
    return fnv10(fold(text))


def derived_id(prefix: str, kind: str, text: str, occurrence: int) -> str:
    """The id a wording takes when nothing names it: deterministic, so every read agrees."""
    return prefix + fnv10(f"{kind}\x00{fold(text)}\x00{occurrence}")


@dataclass(frozen=True, slots=True)
class Entry:
    """One id list entry: the id and the bound wording's hash."""

    id: str
    bound: str

    def as_json(self) -> dict[str, str]:
        return {"id": self.id, "bound": self.bound}


def _entry(raw: Any) -> Entry | None:
    if not isinstance(raw, Mapping):
        return None
    ident, bound = raw.get("id"), raw.get("bound")
    if isinstance(ident, str) and _ID.fullmatch(ident) and isinstance(bound, str):
        return Entry(ident, bound)
    return None


def _entries(raw: Any) -> list[Entry | None] | None:
    """An id list as stored: ``None`` when there is none (or it is not a list)."""
    return [_entry(x) for x in raw] if isinstance(raw, list) else None


def _strings(value: Any) -> list[str] | None:
    """A list of strings, or ``None``: only such a list has item ids."""
    if isinstance(value, list) and all(isinstance(x, str) for x in value):
        return list(value)
    return None


def _lcs(a: Sequence[str], b: Sequence[str]) -> list[tuple[int, int]]:
    """The index pairs of one longest common subsequence of ``a`` and ``b``, in order."""
    n, m = len(a), len(b)
    table = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            table[i][j] = (
                table[i + 1][j + 1] + 1 if a[i] == b[j] else max(table[i + 1][j], table[i][j + 1])
            )
    out: list[tuple[int, int]] = []
    i = j = 0
    while i < n and j < m:
        if a[i] == b[j]:
            out.append((i, j))
            i, j = i + 1, j + 1
        elif table[i + 1][j] >= table[i][j + 1]:
            i += 1
        else:
            j += 1
    return out


def reconcile(
    texts: Sequence[str],
    *,
    prefix: str,
    kind: str,
    entries: Sequence[Entry | None] | None,
    previous: Sequence[tuple[str, str]] | None = None,
) -> list[str]:
    """Each position's id: from the list's own ``entries`` (the module's rules 1-2), else by
    wording from ``previous`` (``(id, wording)`` pairs), else derived (rule 3). Unique."""
    ids: list[str | None] = [None] * len(texts)
    bounds = [bound_of(t) for t in texts]
    used: set[str] = set()
    if entries is not None:
        # An entry is read once: a repeated id keeps its first place only.
        seen: set[str] = set()
        live: list[tuple[int, Entry]] = []
        for k, entry in enumerate(entries):
            if entry is not None and entry.id not in seen:
                seen.add(entry.id)
                live.append((k, entry))
        anchors = _lcs([e.bound for _, e in live], bounds)
        taken: set[int] = set()
        for li, pos in anchors:
            ids[pos] = live[li][1].id
            taken.add(li)
        # An item moved out of order keeps its id by its wording.
        for pos, bound in enumerate(bounds):
            if ids[pos] is not None:
                continue
            for li, (_, entry) in enumerate(live):
                if li not in taken and entry.bound == bound:
                    ids[pos] = entry.id
                    taken.add(li)
                    break
        # Between two anchors, as many unread entries as unnamed positions: reworded in place.
        bounds_e = [-1, *[li for li, _ in anchors], len(live)]
        bounds_p = [-1, *[pos for _, pos in anchors], len(texts)]
        for g in range(len(bounds_e) - 1):
            gap_e = [li for li in range(bounds_e[g] + 1, bounds_e[g + 1]) if li not in taken]
            gap_p = [p for p in range(bounds_p[g] + 1, bounds_p[g + 1]) if ids[p] is None]
            if gap_e and len(gap_e) == len(gap_p):
                for li, pos in zip(gap_e, gap_p, strict=True):
                    ids[pos] = live[li][1].id
                    taken.add(li)
    elif previous is not None:
        offered = [(ident, fold(text)) for ident, text in previous]
        claimed: set[int] = set()
        for pos, text in enumerate(texts):
            folded = fold(text)
            for k, (ident, prior) in enumerate(offered):
                if k not in claimed and prior == folded and ident not in used:
                    ids[pos] = ident
                    claimed.add(k)
                    used.add(ident)
                    break
    used.update(i for i in ids if i is not None)
    occurrences: dict[str, int] = {}
    out: list[str] = []
    for pos, text in enumerate(texts):
        folded = fold(text)
        occurrences[folded] = occurrences.get(folded, 0) + 1
        named = ids[pos]
        if named is None:
            base = derived_id(prefix, kind, text, occurrences[folded])
            named, n = base, 2
            while named in used:
                named, n = f"{base}-{n}", n + 1
            used.add(named)
        out.append(named)
    return out


def list_ids(holder: Mapping[str, Any], list_key: str, ids_key: str) -> list[str] | None:
    """The ids ``holder[ids_key]`` gives ``holder[list_key]``, as :func:`with_item_ids` wrote them;
    ``None`` when they are not there or do not line up with the list."""
    texts = _strings(holder.get(list_key))
    entries = _entries(holder.get(ids_key))
    if texts is None or entries is None or len(entries) != len(texts):
        return None
    out = [e.id if e is not None else None for e in entries]
    if any(i is None for i in out) or len(set(out)) != len(out):
        return None
    return [i for i in out if i is not None]


def _with_list(
    holder: dict[str, Any],
    list_key: str,
    ids_key: str,
    *,
    prefix: str,
    kind: str,
    previous: Sequence[tuple[str, str]] | None,
) -> list[tuple[str, str]] | None:
    """``holder``'s list given its ids in place; the ``(id, wording)`` pairs, or ``None``."""
    texts = _strings(holder.get(list_key))
    if texts is None:
        return None
    ids = reconcile(
        texts, prefix=prefix, kind=kind, entries=_entries(holder.get(ids_key)), previous=previous
    )
    holder[ids_key] = [Entry(i, bound_of(t)).as_json() for i, t in zip(ids, texts, strict=True)]
    return list(zip(ids, texts, strict=True))


def _pairs(holder: Any, list_key: str, ids_key: str) -> list[tuple[str, str]] | None:
    if not isinstance(holder, Mapping):
        return None
    ids = list_ids(holder, list_key, ids_key)
    texts = _strings(holder.get(list_key))
    return list(zip(ids, texts, strict=True)) if ids is not None and texts is not None else None


# -- sections: the compiler's ids ---------------------------------------------------------------

_COMPILED_KINDS: Final = frozenset({"questions", "object_battery"})


def _text(value: Any) -> str:
    """``research_design._text``: the compiler's reading of a value as text."""
    return re.sub(r"\s+", " ", str(value if value is not None else "")).strip()


def _slug(value: str, prefix: str) -> str:
    """``research_design._slug``, so a section's id is what the compiler would make of it."""
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "_", folded.lower()).strip("_")
    if not slug:
        return prefix
    return f"{prefix}_{slug}" if slug[0].isdigit() else slug


def _unique(base: str, used: set[str]) -> str:
    """``research_design._unique``."""
    candidate, i = base, 2
    while candidate in used:
        candidate, i = f"{base}_{i}", i + 1
    used.add(candidate)
    return candidate


def section_ids(sections: Sequence[Any]) -> list[str | None]:
    """The id each section has, or is given: the compiler's for one without (``compile_design``:
    ``sec.get("id") or sec.get("title")``, slugged, unique in order over the sections it compiles),
    so the specification compiled before and after is the same. A section the compiler skips (an
    unknown type) is given its title's slug, unique against every other; ``None`` for an entry that
    is not an object. A section that has an id keeps it as written."""
    out: list[str | None] = []
    compiled: set[str] = set()
    for i, sec in enumerate(sections, start=1):
        if not isinstance(sec, Mapping):
            out.append(None)
            continue
        kind = _text(sec.get("type") or "questions")
        made = _slug(_text(sec.get("id") or sec.get("title")) or f"sekce_{i}", "sec")
        if kind in _COMPILED_KINDS:
            made = _unique(made, compiled)
        out.append(sec.get("id") if sec.get("id") else (made if kind in _COMPILED_KINDS else None))
    taken = {x for x in out if isinstance(x, str)} | compiled
    for i, sec in enumerate(sections, start=1):
        if isinstance(sec, Mapping) and out[i - 1] is None:
            out[i - 1] = _unique(_slug(_text(sec.get("title")) or f"sekce_{i}", "sec"), taken)
    return out


# -- a design -----------------------------------------------------------------------------------


def _plan_lists(
    plan: dict[str, Any],
    previous: Mapping[str, Any] | None,
    fallback: Mapping[str, Any] | None = None,
) -> None:
    for list_key, ids_key, kind, prefix in ID_LISTS:
        source = _pairs(previous, list_key, ids_key) if previous is not None else None
        if source is None and fallback is not None:
            source = _pairs(fallback, list_key, ids_key)
        _with_list(plan, list_key, ids_key, prefix=prefix, kind=kind, previous=source)


def _by_id(sections: Any) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    if not isinstance(sections, list):
        return out
    for sec in sections:
        if not isinstance(sec, Mapping):
            continue
        if isinstance(sec.get("id"), str):
            out.setdefault(f"s:{sec['id']}", sec)
        questions = sec.get("questions")
        for q in questions if isinstance(questions, list) else ():
            if isinstance(q, Mapping) and isinstance(q.get("id"), str):
                out.setdefault(f"q:{q['id']}", q)
    return out


def _sections(content: dict[str, Any], previous: Mapping[str, Any] | None) -> None:
    raw = content.get("sections")
    if not isinstance(raw, list):
        return
    prior = _by_id(previous.get("sections")) if previous is not None else {}
    given = section_ids(raw)
    sections: list[Any] = []
    for sec, ident in zip(raw, given, strict=True):
        if not isinstance(sec, Mapping):
            sections.append(sec)
            continue
        section = dict(sec)
        if not section.get("id") and ident is not None:
            section["id"] = ident
        sid = str(section.get("id"))
        if section.get("type") == "object_battery":
            _with_list(
                section,
                "objects",
                OBJECT_IDS,
                prefix=_OBJECT_PREFIX,
                kind="object",
                previous=_pairs(prior.get(f"s:{sid}"), "objects", OBJECT_IDS),
            )
        elif isinstance(section.get("questions"), list):
            questions: list[Any] = []
            for q in section["questions"]:
                if not isinstance(q, Mapping):
                    questions.append(q)
                    continue
                question = dict(q)
                qid = question.get("id")
                _with_list(
                    question,
                    "kategorie",
                    OPTION_IDS,
                    prefix=_OPTION_PREFIX,
                    kind="option",
                    previous=_pairs(prior.get(f"q:{qid}"), "kategorie", OPTION_IDS)
                    if isinstance(qid, str)
                    else None,
                )
                questions.append(question)
            section["questions"] = questions
        sections.append(section)
    content["sections"] = sections


def _resolved(previous: Any) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    """``previous`` (``{content, analysis}`` or a pair of documents) with its own ids."""
    if previous is None:
        return None, None
    content, analysis = previous
    return with_item_ids(content, analysis)


def with_item_ids(
    content: Mapping[str, Any],
    analysis: Mapping[str, Any] | None = None,
    *,
    previous: tuple[Mapping[str, Any], Mapping[str, Any] | None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """The design (``content`` and its separate ``analysis``) with every item's id written in.

    Copies; the inputs are not changed. A list keeps the ids its own id list gives it (read as the
    module says); a list without one is matched by wording to the same list in ``previous`` (the
    baseline, ``(content, analysis)``), else its ids are derived. The analysis's plan lists, without
    ids of their own and nothing in ``previous``, take the ids of the same wording in this design's
    plan. A section without an id is given the compiler's (:func:`section_ids`)."""
    prev_content, prev_analysis = _resolved(previous)
    body: dict[str, Any] = deepcopy(dict(content))
    plan_raw = body.get("research_plan")
    prev_plan = prev_content.get("research_plan") if prev_content is not None else None
    if isinstance(plan_raw, Mapping):
        plan = dict(plan_raw)
        _plan_lists(plan, prev_plan if isinstance(prev_plan, Mapping) else None)
        body["research_plan"] = plan
    _sections(body, prev_content)
    working: dict[str, Any] | None = None
    if analysis is not None:
        working = deepcopy(dict(analysis))
        own_plan = body.get("research_plan")
        _plan_lists(
            working,
            prev_analysis
            if prev_analysis is not None
            else (prev_plan if isinstance(prev_plan, Mapping) else None),
            own_plan if isinstance(own_plan, Mapping) else None,
        )
    return body, working


# -- links follow a reword ----------------------------------------------------------------------


def _link_key(text: str) -> str:
    """A research question as a link names it: ``research_trace._key``."""
    return re.sub(r"\s+", " ", text).strip()


def _stated(content: Mapping[str, Any]) -> tuple[str, str] | None:
    """Which plan list the links name (``research_questions_of``): its research questions, else its
    objectives; ``None`` when the plan states neither."""
    plan = content.get("research_plan")
    if not isinstance(plan, Mapping):
        return None
    for list_key, ids_key, _, _ in ID_LISTS[:2][::-1]:
        texts = _strings(plan.get(list_key))
        if texts and any(t.strip() for t in texts):
            return list_key, ids_key
    return None


def _relink(links: Any, renamed: Mapping[str, str]) -> Any:
    if not isinstance(links, list):
        return links
    out: list[Any] = []
    keys: set[str] = set()
    for link in links:
        text = renamed.get(_link_key(link), link) if isinstance(link, str) else link
        key = _link_key(text) if isinstance(text, str) else None
        if key is not None and key in keys:
            continue
        if key is not None:
            keys.add(key)
        out.append(text)
    return out


def follow_rewords(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """``after`` (a design's content, ids written in) with each reworded research question's
    links carried to its new wording: the ``research_questions`` of every questionnaire item that
    measures it and the key of its comparison (``research_question_comparisons``).

    A research question is reworded when its id names one wording in ``before`` and another in
    ``after``; a link names it by its wording (``research_trace``), so without this the item would
    measure nothing the plan states. The old wording still stated by another research question is
    left alone: the link still names a research question as written."""
    out = dict(after)
    stated = _stated(after)
    if stated is None:
        return out
    list_key, ids_key = stated
    old = dict(_pairs(before.get("research_plan"), list_key, ids_key) or [])
    new = _pairs(after.get("research_plan"), list_key, ids_key) or []
    still = {_link_key(t) for _, t in new}
    renamed: dict[str, str] = {}
    for ident, text in new:
        was = old.get(ident)
        if was is None or _link_key(was) == _link_key(text) or _link_key(was) in still:
            continue
        renamed.setdefault(_link_key(was), text.strip())
    if not renamed:
        return out
    sections = out.get("sections")
    if isinstance(sections, list):
        relinked: list[Any] = []
        for sec in sections:
            if not isinstance(sec, Mapping):
                relinked.append(sec)
                continue
            section = dict(sec)
            if "research_questions" in section:
                section["research_questions"] = _relink(section["research_questions"], renamed)
            if isinstance(section.get("questions"), list):
                section["questions"] = [
                    {**q, "research_questions": _relink(q["research_questions"], renamed)}
                    if isinstance(q, Mapping) and "research_questions" in q
                    else q
                    for q in section["questions"]
                ]
            relinked.append(section)
        out["sections"] = relinked
    plan = out.get("research_plan")
    comparisons = plan.get("research_question_comparisons") if isinstance(plan, Mapping) else None
    if isinstance(plan, Mapping) and isinstance(comparisons, Mapping):
        moved: dict[str, Any] = {}
        for text, kind in comparisons.items():
            key = renamed.get(_link_key(text), text) if isinstance(text, str) else text
            if key not in moved or key == text:
                moved[key] = kind
        out["research_plan"] = {**plan, "research_question_comparisons": moved}
    return out


def settle_item_ids(
    before: tuple[Mapping[str, Any], Mapping[str, Any] | None],
    after: tuple[Mapping[str, Any], Mapping[str, Any] | None],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """What a writer stores after it changed ``before`` into ``after``: ``after`` with its ids
    (read against ``before``) and every reworded research question's links followed. The web's
    store applies it on each change (``item-ids.ts`` ``settleItemIds``); WCE2's one writer will."""
    base = with_item_ids(*before)
    content, analysis = with_item_ids(*after, previous=base)
    return follow_rewords(base[0], content), analysis


def stores_item_ids(content: Mapping[str, Any], analysis: Mapping[str, Any] | None = None) -> bool:
    """Whether a stored design keeps id lists of its own: the web's store wrote them
    (``AIA_WEB_STABLE_ITEM_IDS`` on). A server writer settles such a copy (:func:`settle_item_ids`)
    as the store does, and leaves a copy without them as it is, so with the switch off nothing
    writes an id."""
    holders: list[Any] = [content.get("research_plan"), analysis]
    for section in content.get("sections") or ():
        if isinstance(section, Mapping):
            holders.append(section)
            holders.extend(section.get("questions") or ())
    return any(isinstance(h, Mapping) and not SIDECAR_KEYS.isdisjoint(h) for h in holders)


def ids_by_kind(content: Mapping[str, Any]) -> Iterable[tuple[str, str]]:
    """Every ``(kind, id)`` a design's content (ids written in) names; for checks and tests."""
    plan = content.get("research_plan")
    if isinstance(plan, Mapping):
        for list_key, ids_key, kind, _ in ID_LISTS:
            for ident, _ in _pairs(plan, list_key, ids_key) or []:
                yield kind, ident
    sections = content.get("sections")
    for sec in sections if isinstance(sections, list) else ():
        if not isinstance(sec, Mapping):
            continue
        if isinstance(sec.get("id"), str):
            yield "section", sec["id"]
        for ident, _ in _pairs(sec, "objects", OBJECT_IDS) or []:
            yield "object", ident
        questions = sec.get("questions")
        for q in questions if isinstance(questions, list) else ():
            if isinstance(q, Mapping):
                if isinstance(q.get("id"), str):
                    yield "question", q["id"]
                for ident, _ in _pairs(q, "kategorie", OPTION_IDS) or []:
                    yield "option", ident
