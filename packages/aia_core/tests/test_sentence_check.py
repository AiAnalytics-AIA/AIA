"""The sentence-level claim check (report-delivery RD7): a sentence of a model's prose that
claims a comparison with no number from the ledger in it is marked, never refused."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.analysis.artifact import ANALYSIS_MODULE_ARTIFACT
from aia_core.domain.report.sentence_check import UNSUPPORTED_COMPARISON, sentence_findings

FIXTURES = Path(__file__).parent / "fixtures"
CASES = json.loads((FIXTURES / "report_sentences" / "cases.json").read_text())["cases"]
WRITTEN = [{"kind": "artifact", "artifact_type": ANALYSIS_MODULE_ARTIFACT}]


def _text(value: str) -> dict[str, Any]:
    return {"type": "text", "text": value, "emphasis": "none"}


def _document(
    *blocks: dict[str, Any],
    refs: dict[str, Any] | None = None,
    sources: list[dict[str, Any]] = WRITTEN,
) -> dict[str, Any]:
    section = {"id": "ch-findings", "blocks": list(blocks), "sources": sources}
    return {"sections": [section], "ledger": {"refs": refs or {}}}


def _paragraph(*content: dict[str, Any], refs: tuple[str, ...] = (), **extra: Any) -> Any:
    return {
        "id": "ch-findings.1",
        "type": "paragraph",
        "content": list(content),
        "refs": list(refs),
        **extra,
    }


def _entry(value_text: str) -> dict[str, Any]:
    # The number before its unit, as the ledger prints it: split at an ordinary space only, a
    # thousands no-break space stays inside the number.
    return {"suppressed": False, "value_text": value_text, "number_text": value_text.split(" ")[0]}


@pytest.mark.parametrize("case", CASES, ids=[c["text"] for c in CASES])
def test_each_case_reads_as_the_rule_says(case: dict[str, Any]) -> None:
    cites = case["cites"]
    refs = {"r1": _entry(cites)} if cites else {}
    block = _paragraph(_text(case["text"]), refs=("r1",) if cites else ())
    assert bool(sentence_findings(_document(block, refs=refs))) is case["marked"], case["why"]


def test_a_finding_names_its_block_its_sentence_and_its_words() -> None:
    block = _paragraph(_text("Bankám důvěřuje většina. Nejvíc v Praze, nejméně v Ostravě."))
    (finding,) = sentence_findings(_document(block))
    assert finding.to_json() == {
        "code": UNSUPPORTED_COMPARISON,
        "where": "ch-findings.1",
        "message": "srovnání bez doloženého čísla: „Nejvíc v Praze, nejméně v Ostravě.“",
        "sentence": 1,
        "text": "Nejvíc v Praze, nejméně v Ostravě.",
    }


def test_a_value_or_a_figure_in_the_sentence_supports_it() -> None:
    refs = {"trust_praha": _entry("48,2 %")}
    value = _paragraph(
        _text("Nejvyšší je v Praze ("),
        {"type": "value", "ref": "trust_praha", "with_interval": False},
        _text(")."),
        refs=("trust_praha",),
    )
    figure = _paragraph(
        _text("Rozdíly ukazuje "), {"type": "cross_ref", "target": "fig-1"}, _text(".")
    )
    assert sentence_findings(_document(value, refs=refs)) == ()
    assert sentence_findings(_document(figure)) == ()
    # A suppressed number is no support: the report prints none.
    hidden = {"r1": {"suppressed": True, "reasons": ["low_support"]}}
    said = _paragraph(_text("Nejvíc v Praze, 48,2 %."), refs=("r1",))
    assert len(sentence_findings(_document(said, refs=hidden))) == 1


def test_only_a_models_prose_is_read() -> None:
    """The composer's own text names how a number is read; a title and a block code wrote
    whole from a stored source are not claims either."""
    comparison = _text("Nejvýše hodnocený objekt má plnou výšku.")
    assert sentence_findings(_document(_paragraph(comparison), sources=[])) == ()
    fixed = [{"kind": "fixed", "text_id": "map-reading"}]
    assert sentence_findings(_document(_paragraph(comparison), sources=fixed)) == ()
    assert sentence_findings(_document(_paragraph(comparison, role="lead_in"))) == ()
    assert sentence_findings(_document(_paragraph(comparison, control="aia:map"))) == ()
    assert len(sentence_findings(_document(_paragraph(comparison)))) == 1


def test_a_lists_items_and_a_callout_are_read_sentence_by_sentence() -> None:
    items = {
        "id": "ch-findings.2",
        "type": "list",
        "items": [
            {
                "content": [_text("bez srovnání")],
                "children": [
                    {"content": [_text("nejvíc v Praze")], "children": []},
                ],
            },
            {"content": [_text("vyšší než loni")], "children": []},
        ],
        "refs": [],
    }
    callout = {
        "id": "ch-findings.3",
        "type": "callout",
        "content": [_text("Nejlepší je Brno.")],
        "refs": [],
    }
    found = sentence_findings(_document(items, callout))
    assert [(f.where, f.sentence, f.text) for f in found] == [
        ("ch-findings.2", 1, "nejvíc v Praze"),
        ("ch-findings.2", 2, "vyšší než loni"),
        ("ch-findings.3", 0, "Nejlepší je Brno."),
    ]


def test_the_stored_internal_draft_is_marked_where_it_compares_in_words() -> None:
    stored = json.loads((FIXTURES / "report_document" / "internal.json").read_text())
    found = sentence_findings(stored.get("document", stored))
    assert [(f.where, f.sentence) for f in found] == [("ch-summary.1", 1), ("ch-confidence.1", 0)]
