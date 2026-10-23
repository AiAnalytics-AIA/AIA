"""The working copy's operation log as values (working-copy-edit-ops WCE2a, ADR 0029 decision 3)."""

from __future__ import annotations

import copy

import pytest

from aia_core.domain.design_items import Documents, ItemKey
from aia_core.domain.edit_log import (
    FIELD_MAX,
    ITEM_KEY_MAX,
    WHOLE_COPY,
    ActorKind,
    OpSource,
    WriteBy,
    op_rows,
    whole_copy_rows,
    whole_copy_touches,
    write_rows,
)
from aia_core.domain.research_template import research_template

PERSON = WriteBy(ActorKind.PERSON, "USR-1", OpSource.UI)


def _questionnaire() -> dict:
    content = research_template()
    content["sections"] = [
        {
            "id": "sec_a",
            "type": "questions",
            "questions": [
                {"id": "Q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                {"id": "Q2", "text": "Kde nakupujete?", "typ": "vyber", "kategorie": ["A", "B"]},
            ],
        }
    ]
    return content


def _rows(before: dict | None, after: dict, **kw: object) -> tuple:
    return whole_copy_rows(
        None if before is None else Documents(content=before),
        Documents(content=after),
        reason=str(kw.get("reason", "autosave")),
        by=kw.get("by", PERSON),  # type: ignore[arg-type]
        batch_id="BATCH-1",
        base_revision=None if before is None else 1,
        result_revision=2,
    )


def test_a_whole_copy_write_logs_one_row_per_field_it_changed() -> None:
    before = _questionnaire()
    after = copy.deepcopy(before)
    after["sections"][0]["questions"][0]["text"] = "Jak často pijete čaj?"
    after["sections"][0]["questions"][1]["kategorie"] = ["A", "B", "C"]
    rows = _rows(before, after)
    assert [(r.item_key, r.field) for r in rows] == [
        ("content:question:Q1", "text"),
        ("content:question:Q2", "kategorie"),
    ]
    assert {r.op["op"] for r in rows} == {"whole_copy"} and rows[0].op["reason"] == "autosave"
    assert len({r.op_id for r in rows}) == 2 and {r.batch_id for r in rows} == {"BATCH-1"}
    assert all(r.base_revision == 1 and r.result_revision == 2 for r in rows)


def test_a_write_whose_changes_no_field_counts_still_logs_one_row() -> None:
    """A re-spaced list entry is the same item to design_fields, but a new revision: it logs the
    copy as a whole, so no write skips the log."""
    before = research_template()
    before["research_plan"] = {"research_questions": ["Kdo kupuje kávu?"]}
    after = copy.deepcopy(before)
    after["research_plan"]["research_questions"] = ["Kdo  kupuje kávu? "]
    assert whole_copy_touches(Documents(content=before), Documents(content=after)) == {WHOLE_COPY}
    assert [(r.item_key, r.field) for r in _rows(before, after)] == [("content:copy:", "value")]


def test_a_first_write_names_every_item_it_wrote() -> None:
    rows = _rows(None, _questionnaire())
    keys = {(r.item_key, r.field) for r in rows}
    assert ("content:question:Q1", "item") in keys and ("content:section:sec_a", "item") in keys
    assert all(r.base_revision is None for r in rows)


def test_an_analysis_change_is_logged() -> None:
    touched = whole_copy_touches(
        Documents(content={}, analysis={"summary": "a"}),
        Documents(content={}, analysis={"summary": "b"}),
    )
    assert touched == {(ItemKey("analysis", "field", "summary"), "value")}


def test_only_a_migrated_revision_is_logged_without_its_author() -> None:
    assert WriteBy(ActorKind.PERSON, None, OpSource.MIGRATION).actor_user_id is None
    for source in OpSource:
        for kind in ActorKind:
            if (source, kind) == (OpSource.MIGRATION, ActorKind.PERSON):
                continue
            # 18.6.6 had no Lead: a Lead's write always names its researcher, migrated or not.
            with pytest.raises(ValueError, match="without its author"):
                WriteBy(kind, None, source)
    with pytest.raises(ValueError, match="never empty"):
        WriteBy(ActorKind.PERSON, "", OpSource.UI)


def test_a_key_or_field_longer_than_its_column_is_kept_deterministically() -> None:
    long = "x" * 300
    before = _questionnaire()
    after = copy.deepcopy(before)
    after[long] = 1  # an unknown top-level key: an item key past its column
    after["sections"][0]["questions"][0][long] = 2  # a field past its column
    first, second = _rows(before, after), _rows(before, after)
    assert {len(r.item_key) for r in first} >= {ITEM_KEY_MAX}
    assert {len(r.field or "") for r in first} >= {FIELD_MAX}
    for row in first:
        assert len(row.item_key) <= ITEM_KEY_MAX and len(row.field or "") <= FIELD_MAX
    assert [(r.item_key, r.field) for r in first] == [(r.item_key, r.field) for r in second]


def test_rows_name_a_resulting_revision() -> None:
    with pytest.raises(ValueError, match="results in a working revision"):
        op_rows(
            [WHOLE_COPY],
            op={"op": "whole_copy", "reason": "autosave"},
            by=PERSON,
            batch_id="B",
            base_revision=None,
            result_revision=0,
        )


def test_a_write_of_operations_logs_each_under_its_own_and_the_rest_as_the_copy() -> None:
    before = _questionnaire()
    after = copy.deepcopy(before)
    after["title"] = "Nový název"
    after["ui_state"] = {"plan_manual_changed": True}
    title = (ItemKey("content", "brief", "title"), "text")
    op = {"op": "set_text", "field": "title", "value": "Nový název"}
    rows = write_rows(
        Documents(content=before),
        Documents(content=after),
        ops=[(op, frozenset({title}))],
        reason="lead_edit_accepted",
        by=PERSON,
        batch_id="B",
        base_revision=1,
        result_revision=2,
    )
    assert [(r.item_key, r.field, r.op["op"]) for r in rows] == [
        ("content:brief:title", "text", "set_text"),
        ("content:field:ui_state", "value", "whole_copy"),
    ]
    assert rows[1].op == {"op": "whole_copy", "reason": "lead_edit_accepted"}
