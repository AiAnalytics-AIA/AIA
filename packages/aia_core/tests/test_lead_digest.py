"""The decision digest (ADR 0041 decision 4, plan lead-conversation LC3)."""

from __future__ import annotations

import pytest

from aia_core.domain.ai_contracts import canonical_json
from aia_core.domain.lead_digest import (
    DIGEST_LINE_MAX_BYTES,
    DIGEST_SHARE_MAX_BYTES,
    DIGEST_SHARE_MIN_BYTES,
    DigestEntry,
    decision_digest,
    edit_item,
)
from aia_core.domain.research_lead import FOCUS_ID


def _edit(ledger_id: int, item: str, decision: str = "accept") -> DigestEntry:
    return DigestEntry(
        kind="edit", item=item, decision=decision, turn_id=f"T-{ledger_id}", ledger_id=ledger_id
    )


def _size(digest: dict[str, object]) -> int:
    return len(canonical_json(digest).encode("utf-8"))


def test_the_same_entries_give_the_same_digest() -> None:
    decided = [_edit(i, f"question:q{i % 5}") for i in range(1, 30)]
    assert decision_digest(decided, []) == decision_digest(decided, [])


def test_a_dismissed_edit_from_an_early_turn_is_there_when_its_item_is_named() -> None:
    decided = [_edit(3, "brief:goal", "dismiss")] + [
        _edit(i, f"question:q{i}") for i in range(10, 400)
    ]
    digest = decision_digest(decided, [], named=["brief:goal"])
    assert digest["named"] == [
        {"kind": "edit", "item": "brief:goal", "turn": "T-3", "decision": "dismiss", "ledger": 3}
    ]


def test_a_named_item_shows_its_newest_three_decisions_and_counts_the_rest() -> None:
    decided = [_edit(i, "question:q1", "accept" if i % 2 else "dismiss") for i in range(1, 41)]
    digest = decision_digest(decided, [], named=["question:q1"])
    assert [line["ledger"] for line in digest["named"]] == [40, 39, 38]
    assert digest["left_out"]["decisions"] == 37
    assert digest["left_out"]["ledger_range"] == [1, 37]
    assert digest["left_out"]["by_named_item"] == {"question:q1": 37}


def test_every_other_item_shows_only_its_latest_decision() -> None:
    decided = [_edit(1, "brief:goal", "dismiss"), _edit(2, "brief:goal"), _edit(3, "plan:n")]
    digest = decision_digest(decided, [])
    assert [(line["item"], line["ledger"]) for line in digest["latest"]] == [
        ("plan:n", 3),
        ("brief:goal", 2),
    ]
    assert digest["left_out"]["decisions"] == 1


def test_undecided_proposals_are_pointers_without_a_ledger_row() -> None:
    waiting = [DigestEntry(kind="edit", item="question:q9", decision=None, turn_id="T-50", index=2)]
    digest = decision_digest([], waiting)
    assert digest["undecided"] == [
        {"kind": "edit", "item": "question:q9", "turn": "T-50", "index": 2}
    ]


def test_a_busy_conversation_stays_within_its_share_and_every_group_within_its_cap() -> None:
    decided = [_edit(i, "question:q1") for i in range(1, 41)] + [
        _edit(i, f"question:q{i}") for i in range(41, 541)
    ]
    waiting = [
        DigestEntry(kind="edit", item=f"question:w{i}", decision=None, turn_id=f"W-{i}", index=0)
        for i in range(60)
    ]
    for share in (DIGEST_SHARE_MIN_BYTES, DIGEST_SHARE_MAX_BYTES):
        digest = decision_digest(decided, waiting, named=["question:q1"], share_bytes=share)
        scale = share / DIGEST_SHARE_MAX_BYTES
        assert _size(digest["named"]) <= 4 * 1024 * scale
        assert _size(digest["undecided"]) <= 2 * 1024 * scale
        assert _size(digest) <= share
        left = digest["left_out"]
        assert left["decisions"] + len(digest["named"]) + len(digest["latest"]) == len(decided)
        assert left["proposals"] + len(digest["undecided"]) == len(waiting)
        assert left["ledger_range"] is not None and left["turn_range"] is not None


def test_a_line_is_never_longer_than_its_bound() -> None:
    long_item = "plan.hypotheses:" + "ž" * 300
    digest = decision_digest([_edit(1, long_item)], [])
    (line,) = digest["latest"]
    assert len(canonical_json(line).encode("utf-8")) <= DIGEST_LINE_MAX_BYTES
    assert str(line["item"]).startswith("sha256:")


def test_a_share_outside_the_range_is_refused() -> None:
    with pytest.raises(ValueError):
        decision_digest([], [], share_bytes=DIGEST_SHARE_MAX_BYTES + 1)


@pytest.mark.parametrize(
    ("edit", "focus"),
    [
        ({"op": "set_text", "field": "goal", "value": "x"}, "brief:goal"),
        ({"op": "question_edit", "question_id": "Q1", "text": "x"}, "question:Q1"),
        ({"op": "set_n", "value": 400}, "sample:n"),
    ],
)
def test_an_edit_is_named_by_the_id_the_web_focuses(edit: dict[str, object], focus: str) -> None:
    # The ids the stages put in data-aia (Brief, Dotazník, Vzorek), as the focus sends them.
    assert FOCUS_ID.match(focus)
    assert edit_item(edit) == focus
