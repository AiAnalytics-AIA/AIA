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
import re
import sys
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
    # Python's whitespace is not JavaScript's \s (review web#9): an id of only U+001C or U+0085
    # is none here, one of only U+FEFF is text.
    assert "sec_brands_9" in questions and "sec_brands_10" in questions, "Python-only whitespace"
    assert "q" in questions, "U+FEFF, whitespace to JavaScript alone"
    assert "sekce_9" in sets, "a set whose id is only Python whitespace"
    # Python's ``or`` reads an empty list or object as nothing; JavaScript's ``||`` does not.
    typs = [q.get("typ") for s in body["sections"] for q in s.get("questions") or []]
    assert [] in typs and {} in typs, "a question whose type is an empty list or object"
    assert questions[-6:-3] == ["t1", "t1_2", "t2"], "compiled as 'vyber', so later ids move on"
    assert [] in kinds and {} in kinds, "a section whose type is an empty list or object"
    assert "e1" in questions and "e2" in questions, "its questions compiled as questions"
    assert [] in [s.get("id") for s in body["sections"]], "a section whose id is an empty list"
    assert "titulek_1" in questions, "named by its title instead"


def test_the_fixture_lists_the_whitespace_the_server_collapses() -> None:
    """``_text`` collapses ``re``'s ``\\s`` and strips with ``str.strip()``: one set, listed whole,
    which the web's port (``pythonCollapse``) checks code point by code point."""
    body = json.loads(FIXTURE.read_text("utf-8"))
    every = [chr(c) for c in range(sys.maxunicode + 1)]
    by_re = [ord(c) for c in every if re.fullmatch(r"\s", c)]
    by_strip = [ord(c) for c in every if c.strip() == ""]
    assert body["whitespace"] == by_re == by_strip
