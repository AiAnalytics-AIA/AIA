"""Text code wrote from one stored source, put under that source's locked control
(domain/report/controls.py; artifact-report RPT8a, part 3)."""

from __future__ import annotations

from aia_core.domain.report.controls import under_blocks
from aia_core.domain.report.model import (
    BulletList,
    Column,
    ListItem,
    Paragraph,
    Table,
    TableRow,
    Text,
    TextCell,
    Value,
    text,
)

TAG = "run:RUN-1"


def test_a_block_printing_a_number_is_put_under_the_source_and_the_rest_left_alone() -> None:
    counted = Paragraph(text("Běh vybral 300 respondentů."))
    words = Paragraph(text("Běh nezaznamenal populaci."))
    ledger = Paragraph((Text("Podíl 42 "), Value("q1.pct")))
    owned = Paragraph(text("Mapa: 4 objekty."), control="map:s/m")
    listed = BulletList((ListItem(text("Pravidlo podpory: n ≥ 30")),))
    table = Table(
        id="tab",
        title="Pravidla",
        columns=(Column("Modul"), Column("Verze")),
        rows=(TableRow((TextCell("Analýza"), TextCell("aia-analysis-2"))),),
        source="Záznam běhu",
        notes=("Zaokrouhleno na 1 místo.",),
    )
    out = under_blocks((counted, words, ledger, owned, listed, table), TAG)
    assert out[0].control == TAG  # type: ignore[union-attr]
    assert out[1] is words  # no number, no lock
    assert out[2] is ledger  # a ledger value keeps its own control, never one within another
    assert out[3] is owned  # a block already under its source keeps it
    assert out[4].control == TAG  # type: ignore[union-attr]
    locked = out[5]
    assert isinstance(locked, Table)
    (row,) = locked.rows
    assert [c.control for c in row.cells if isinstance(c, TextCell)] == [None, TAG]
    assert locked.notes_control == TAG
