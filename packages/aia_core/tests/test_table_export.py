"""A report's per-question tables as an export (report-delivery RD12, D-41): every number as the
report prints it, the rows it left out counted, nothing computed, and no cell a formula."""

from __future__ import annotations

import csv
import io
from dataclasses import replace
from typing import Any

from report_samples import build

from aia_core.domain.fieldwork import MODELLED_DISCLOSURE
from aia_core.domain.report.copy import t
from aia_core.domain.report.document_model import document_payload
from aia_core.domain.report.model import (
    Align,
    Column,
    NumberCell,
    Section,
    Table,
    TableRow,
    TextCell,
)
from aia_core.domain.report.table_export import HEADER, question_rows, to_csv


def _document(report_ledger: Any, *, anchor: str = "tab-question-1") -> dict[str, Any]:
    base = build("client", report_ledger)
    table = Table(
        id=anchor,
        title='=HYPERLINK("fiktivní")',
        columns=(Column("Ukazatel"), Column("Hodnota (95% interval)", align=Align.RIGHT)),
        rows=(
            TableRow((TextCell("Praha"), NumberCell("trust_praha", True))),
            TableRow((TextCell("Zlín"), NumberCell("trust_zlin", True))),
            TableRow((TextCell("-celkem"), NumberCell("n_total", False))),
            TableRow((TextCell("Přechod"), NumberCell("switch_modelled", True))),
        ),
        source="Fiktivní výsledek",
        base_ref="n_total",
    )
    section = Section("Výsledky jednotlivých otázek", (table,), id="ch-tables")
    return document_payload(replace(base, sections=(*base.sections, section)))


def test_each_printed_number_is_a_row_as_the_report_prints_it(report_ledger: Any) -> None:
    document = _document(report_ledger)
    refs = document["ledger"]["refs"]
    rows = question_rows(document)
    assert rows[0] == HEADER
    title = '\'=HYPERLINK("fiktivní")'  # kept as text, never a formula
    praha, total, switch, left_out = rows[1:]
    assert praha == (
        title,
        "Praha",
        refs["trust_praha"]["value_text"],
        refs["trust_praha"]["interval_text"],
        refs["trust_praha"]["base_text"] or "",
        t(f"grade_{refs['trust_praha']['grade'].replace('-', '_')}"),
        MODELLED_DISCLOSURE if refs["trust_praha"]["modelled_panel"] else "",
    )
    assert total[1] == "'-celkem" and total[3] == ""  # asked without its interval
    assert switch[5] == "Modelováno"
    # The suppressed row is no number here either: the export counts it, as the report does.
    assert left_out == (title, "vynecháno pro nedostatečnou oporu: 1", "", "", "", "", "")
    assert not any("trust_zlin" in cell or "51" in cell for row in rows for cell in row[2:4])


def test_only_the_question_tables_are_exported(report_ledger: Any) -> None:
    assert question_rows(_document(report_ledger, anchor="tab-regions")) == [HEADER]


def test_the_csv_reads_back_in_a_czech_spreadsheet(report_ledger: Any) -> None:
    rows = question_rows(_document(report_ledger))
    data = to_csv(rows)
    assert data.startswith("﻿".encode())  # Excel reads UTF-8 by its mark
    back = list(csv.reader(io.StringIO(data.decode("utf-8-sig")), delimiter=";"))
    assert [tuple(r) for r in back] == rows
