"""The decision digest: what a researcher's conversation with their Lead decided, exactly.

ADR 0041 decision 4, part 1; plan ``lead-conversation`` LC3. Pure.

The digest is a view of the approval ledger, which is immutable, so no decision is ever lost;
what is bounded is how much of it one turn carries. Built by code, never by a model, and
never summarised. Its share of the conversation-memory layer is filled in four groups, each
with its own cap and order, so no group starves another:

1. decisions on items the message, the focus or a pin names (the newest three per item);
2. proposals still undecided, newest first, as pointers to the turn that holds them;
3. the latest decision on every other item, newest first;
4. counts per kind, and per named item, of what the lines left out, which always fit: the
   latest decisions give way to them line by line.

A decision line names its ledger row; a pointer line, whose proposal is not in the ledger yet,
names its turn and its index in that turn's output. What is left out is counted, with the
ledger range or turn range it pages from, never rewritten.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from .ai_contracts import canonical_json

__all__ = [
    "DIGEST_LINE_MAX_BYTES",
    "DIGEST_SHARE_MAX_BYTES",
    "DIGEST_SHARE_MIN_BYTES",
    "DigestEntry",
    "decision_digest",
    "edit_item",
]

DIGEST_LINE_MAX_BYTES: Final = 200
#: The digest's share of the conversation-memory layer: from the minimum at the layer's floor
#: to the maximum at its ceiling (ADR 0041 decision 4).
DIGEST_SHARE_MIN_BYTES: Final = 5 * 1024
DIGEST_SHARE_MAX_BYTES: Final = 8 * 1024

#: The first two groups' caps at the full share; at a smaller share they scale with it.
_NAMED_CAP: Final = 4 * 1024
_UNDECIDED_CAP: Final = 2 * 1024
_PER_NAMED_ITEM: Final = 3


@dataclass(frozen=True, slots=True)
class DigestEntry:
    """One decision, or one proposal still waiting for one.

    ``item`` names what was decided on (``None`` when the decision names no item, such as a
    prepared job). ``ledger_id`` is the approval-ledger row of a decision and ``None`` for a
    proposal still undecided, which ``index`` places in its turn's output instead. Entries
    are ordered by ``ledger_id`` (decisions) or by turn order (proposals), oldest first.
    """

    kind: str
    item: str | None
    decision: str | None
    turn_id: str
    ledger_id: int | None = None
    index: int | None = None


def edit_item(edit: Mapping[str, Any]) -> str | None:
    """The item an edit of the Lead's closed output names, in the focus's own words where
    there are some (``brief:goal``, ``question:q1``, ``sample:n``), so a named focus finds its
    decisions. A list entry is named by its text, which no focus id carries (the web names an
    objective or a hypothesis by its id): it reaches the latest group, never the named one."""
    op = edit.get("op")
    if op == "set_text":
        return f"brief:{edit['field']}"
    if op in ("list_add", "list_replace", "list_remove"):
        return f"plan:{edit['list']}:{edit.get('old') or edit.get('value')}"
    if op in ("question_edit", "question_remove"):
        return f"question:{edit['question_id']}"
    if op == "question_add":
        return f"question:new:{edit['text']}"
    if op == "set_n":
        return "sample:n"
    return None


def _named(item: str | None, names: Sequence[str]) -> bool:
    """Whether ``item`` is one of ``names`` or within one (``plan:plan.hypotheses`` names each
    of its entries)."""
    return item is not None and any(item == n or item.startswith(n + ":") for n in names)


def _bytes(value: Any) -> int:
    return len(canonical_json(value).encode("utf-8"))


def _line(entry: DigestEntry) -> dict[str, Any]:
    line: dict[str, Any] = {"kind": entry.kind, "item": entry.item, "turn": entry.turn_id}
    if entry.ledger_id is not None:
        line |= {"decision": entry.decision, "ledger": entry.ledger_id}
    else:
        line["index"] = entry.index
    if entry.item is not None and _bytes(line) > DIGEST_LINE_MAX_BYTES:
        # An item's text too long for a line is named by its digest instead.
        line["item"] = "sha256:" + hashlib.sha256(entry.item.encode("utf-8")).hexdigest()[:16]
    return line


def _key(entry: DigestEntry) -> str:
    return entry.item if entry.item is not None else f"{entry.kind}:{entry.turn_id}"


def _fill(candidates: Sequence[DigestEntry], cap: int) -> list[DigestEntry]:
    """The candidates, in order, whose lines fit ``cap`` as one JSON list."""
    used = 2  # the list's brackets
    taken: list[DigestEntry] = []
    for entry in candidates:
        size = _bytes(_line(entry)) + (1 if taken else 0)
        if used + size <= cap:
            taken.append(entry)
            used += size
    return taken


def _digest(
    named: Sequence[DigestEntry],
    pointers: Sequence[DigestEntry],
    latest: Sequence[DigestEntry],
    decided: Sequence[DigestEntry],
    undecided: Sequence[DigestEntry],
    names: Sequence[str],
) -> dict[str, Any]:
    shown = {e.ledger_id for e in (*named, *latest)}
    left = [e for e in decided if e.ledger_id not in shown]
    per_named: dict[str, int] = {}
    for name in names:
        hidden = sum(1 for e in left if _named(e.item, [name]))
        if hidden:
            per_named[name] = hidden
    left_pointers = [e for e in undecided if e not in pointers]
    counts: dict[str, int] = {}
    for entry in left:
        counts[entry.kind] = counts.get(entry.kind, 0) + 1
    ledger_ids = [e.ledger_id for e in left if e.ledger_id is not None]
    turns = [e.turn_id for e in left_pointers]
    return {
        "named": [_line(e) for e in named],
        "undecided": [_line(e) for e in pointers],
        "latest": [_line(e) for e in latest],
        "left_out": {
            "decisions": len(left),
            "by_kind": dict(sorted(counts.items())),
            "by_named_item": per_named,
            "ledger_range": [min(ledger_ids), max(ledger_ids)] if ledger_ids else None,
            "proposals": len(left_pointers),
            "turn_range": [turns[0], turns[-1]] if turns else None,
        },
    }


def decision_digest(
    decided: Sequence[DigestEntry],
    undecided: Sequence[DigestEntry],
    *,
    named: Sequence[str] = (),
    share_bytes: int = DIGEST_SHARE_MAX_BYTES,
) -> dict[str, Any]:
    """The digest within ``share_bytes`` (between the minimum and maximum share).

    ``decided`` are this conversation's ledger decisions and ``undecided`` its proposals
    waiting for one, each oldest first; ``named`` are the items the message, the focus or a
    pin names, in that order. Deterministic: the same entries give the same digest.
    """
    if not DIGEST_SHARE_MIN_BYTES <= share_bytes <= DIGEST_SHARE_MAX_BYTES:
        raise ValueError(
            f"the digest's share is {DIGEST_SHARE_MIN_BYTES}-{DIGEST_SHARE_MAX_BYTES} bytes"
        )
    scale = share_bytes / DIGEST_SHARE_MAX_BYTES
    newest = sorted(decided, key=lambda e: e.ledger_id or 0, reverse=True)

    named_items = list(dict.fromkeys(named))
    named_shown = _fill(
        [
            e
            for item in named_items
            for e in [d for d in newest if _named(d.item, [item])][:_PER_NAMED_ITEM]
        ],
        int(_NAMED_CAP * scale),
    )
    pointers = _fill(list(reversed(undecided)), int(_UNDECIDED_CAP * scale))
    others = {_key(e): e for e in reversed(newest) if not _named(e.item, named_items)}
    latest = _fill(
        sorted(others.values(), key=lambda e: e.ledger_id or 0, reverse=True), share_bytes
    )
    digest = _digest(named_shown, pointers, latest, decided, undecided, named_items)
    # The latest decisions take what the other groups and the counts leave, line by line.
    while latest and _bytes(digest) > share_bytes:
        latest.pop()
        digest = _digest(named_shown, pointers, latest, decided, undecided, named_items)
    return digest
