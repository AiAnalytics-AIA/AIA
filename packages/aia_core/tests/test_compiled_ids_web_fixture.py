"""The web resolves a link to Dotazník by the ids the server compiles, and they agree.

A gap names a question or a tracked set by its compiled id (the outlook's ``question_id`` and
``battery_id``), which ``compile_design`` slugs and makes unique; Dotazník draws each item under
the id the web gave it. ``apps/web/src/lib/answerability.ts`` ports the rule to find the item a
link names (``compiledPlaces``), and its test reads ``apps/web/src/lib/fixtures/compiled-ids.json``
as this one does: the ids listed there are what the server writes for those sections, so the
port and the compiler are checked against one file (review, 2026-10-18).
"""

from __future__ import annotations

import json
from pathlib import Path

from aia_core.domain.research_design import compile_design

REPO = Path(__file__).resolve().parents[3]
FIXTURE = REPO / "apps/web/src/lib/fixtures/compiled-ids.json"


def test_the_server_compiles_the_fixture_to_the_ids_it_lists() -> None:
    body = json.loads(FIXTURE.read_text("utf-8"))
    spec, problems = compile_design({"sections": body["sections"]})
    assert problems == () and spec is not None
    assert [q.id for q in spec.questions] == body["questions"]
    assert [b.id for b in spec.batteries] == body["sets"]


def test_the_fixture_holds_every_case_the_rule_has() -> None:
    body = json.loads(FIXTURE.read_text("utf-8"))
    questions, sets = body["questions"], body["sets"]
    assert "q1_2" in questions, "two ids that slug alike, made unique in order"
    assert "q_1a" in questions and "q_12" in questions, "a leading digit, a whole number"
    assert "ci" in questions, "diacritics folded"
    assert "sec_brands_4" in questions, "an item without an id, by its section's"
    assert "sekce_5" in sets, "a set without id or title, by its place among the sections"
    assert "sada_bank_2_2" in questions, "a section id taken by an earlier section"
    kinds = [s.get("type") for s in body["sections"]]
    assert "intro" in kinds, "a section the server skips"
    assert None in kinds, "a section without a type, which the server reads as questions"
