"""A report's printed text as XML 1.0 can hold it (domain/report/printable.py)."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from typing import Any

from test_report_docx_render import _doc

from aia_core.domain.evidence.metrics import parse_metric
from aia_core.domain.report.document_model import document_bytes
from aia_core.domain.report.model import CrossRef, NumberCell, Paragraph, Section, Text, Value
from aia_core.domain.report.printable import printable, xml_text


def test_words_characters_keep_their_meaning_and_the_rest_are_dropped() -> None:
    assert xml_text("řádek\x0bdruhý\x0cstrana\x0esloupec") == "řádek druhý strana sloupec"
    assert xml_text("e\x1email") == "e-mail"  # Word's non-breaking hyphen
    assert xml_text("a\x00b\x07c\x1fd\ud800e\ufffef\uffff") == "abcdef"
    assert xml_text("tab\tnew\nreturn\r") == "tab\tnew\nreturn\r"  # what XML holds stays


def test_a_clean_report_is_returned_as_itself(report_ledger: Any) -> None:
    doc = _doc(report_ledger())
    assert printable(doc) is doc


def test_only_printed_text_is_cleaned_never_a_name(report_ledger: Any) -> None:
    """A ref or a target names a ledger row or an outline entry; rewriting it would part it
    from what it names."""
    ref, target = "q\x07.share", "ch\x07-x"
    paragraph = Paragraph((Text("a\x07b"), Value(ref), CrossRef(target)), refs=(ref,))
    cleaned = printable((paragraph, NumberCell(ref)))
    assert cleaned == (
        Paragraph((Text("ab"), Value(ref), CrossRef(target)), refs=(ref,)),
        NumberCell(ref),
    )


def test_a_choices_label_in_the_stored_ledger_is_stored_as_printable(report_ledger: Any) -> None:
    """A share's metric names the choice as typed (``pct:<answer>``); the stored model writes
    it, so a lone surrogate in it failed the model's UTF-8 store after the DOCX had rendered."""
    ledger = report_ledger()
    row = ledger.rows["trust_total"]
    rows = {**ledger.rows, "trust_total": replace(row, metric=parse_metric("pct:Ano\ud800\x07"))}
    doc = _doc(replace(ledger, rows=MappingProxyType(rows)))
    doc = replace(doc, sections=(Section("Čísla", (Paragraph((Value("trust_total"),)),)),))
    assert '"metric":"pct:Ano"' in document_bytes(doc).decode()
