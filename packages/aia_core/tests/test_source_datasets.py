"""A client's datasets: CSV, XLSX, XLS and ODS read into rows and a preview (lifecycle K2c).

The rules pinned here:
- the four formats of one fictional export read to the same rows and the same columns;
- row 1 is the header only when it is all text over numbers or dates below;
- a column that looks like personal data is flagged and its samples are masked, by
  patterns pinned in ``fixtures/client_datasets/personal.json`` (fictional values);
- a sheet's empty rest -- repeated rows and cells, declared but unfilled columns -- is
  never materialized and never listed;
- a source kept before its format had a reader is read again, the first reading kept
  (OI-110).
"""

from __future__ import annotations

import dataclasses
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.client_datasets import (
    DISTINCT_CAP,
    MASK,
    SAMPLE_SIZE,
    ColumnKind,
    PersonalHint,
    kind_of,
    personal_value,
    preview_sheet,
)
from aia_core.domain.client_sources import ReadingOutcome, SourceReading
from aia_core.domain.scope import ClientContext, ClientPermission, ScopeDenied
from aia_core.infrastructure import client_source_repository as repository_module
from aia_core.infrastructure.client_source_repository import ClientSourceRepository
from aia_core.infrastructure.source_reading import read_source
from aia_core.infrastructure.storage import InMemoryArtifactStore

FIXTURES = Path(__file__).parent / "fixtures"
SOURCES = FIXTURES / "client_sources"
ATTACHMENTS = FIXTURES / "attachment_text" / "inputs"


def read(name: str, folder: Path = SOURCES) -> SourceReading:
    return read_source((folder / name).read_bytes(), name)


# ------------------------------------------------------------------ the four formats


@pytest.mark.parametrize("name", ["odpovedi.ods", "odpovedi.xlsx", "odpovedi.xls"])
def test_one_export_reads_the_same_in_every_workbook_format(name: str) -> None:
    reading = read(name)
    assert (reading.outcome, reading.reader) == (ReadingOutcome.READ, f"{name[-4:].strip('.')}/1")
    rows = [(s.locator.sheet, s.locator.row, s.text) for s in reading.segments[:3]]
    assert rows == [
        ("Odpovědi", 1, "ID | Věk | Kraj | Spokojenost | Datum | E-mail"),
        ("Odpovědi", 2, "1 | 34 | Praha | 4.5 | 2026-09-01 | jana.fikt@example.test"),
        ("Odpovědi", 3, "2 | 51 | Jihomoravský | 3 | 2026-09-02 | petr.fikt@example.test"),
    ]
    assert reading.dataset is not None
    answers, notes = reading.dataset.sheets
    assert (answers.name, answers.header_row, answers.rows) == ("Odpovědi", 1, 4)
    assert [(c.header, c.kind) for c in answers.columns] == [
        ("ID", ColumnKind.NUMBER),
        ("Věk", ColumnKind.NUMBER),
        ("Kraj", ColumnKind.TEXT),
        ("Spokojenost", ColumnKind.NUMBER),
        ("Datum", ColumnKind.DATE),
        ("E-mail", ColumnKind.TEXT),
    ]
    region = answers.columns[2]
    assert (region.filled, region.distinct, region.sample) == (
        4,
        3,
        ("Praha", "Jihomoravský", "Olomoucký"),
    )
    mail = answers.columns[5]
    assert (mail.personal, mail.sample) == (PersonalHint.EMAIL, (MASK,) * 4)
    # A sheet of one text cell has no header: nothing below it to tell one from data.
    assert (notes.name, notes.header_row, notes.rows) == ("Poznámky", None, 1)


def test_a_czech_csv_reads_with_its_bom_semicolons_and_decimal_commas() -> None:
    reading = read("utrata.csv")
    assert (reading.outcome, reading.reader) == (ReadingOutcome.READ, "csv/1")
    assert reading.segments[0].text == "ID | Věk | Kraj | Útrata | Telefon"
    assert reading.segments[0].locator.model_dump(exclude_none=True) == {"row": 1}
    assert reading.dataset is not None
    [sheet] = reading.dataset.sheets
    assert sheet.name is None and sheet.rows == 3
    spend, phone = sheet.columns[3], sheet.columns[4]
    assert (spend.kind, spend.sample[0]) == (ColumnKind.NUMBER, "1 250,50")
    # A phone number is an identifier, not a quantity, and it is personal.
    assert (phone.kind, phone.personal, set(phone.sample)) == (
        ColumnKind.TEXT,
        PersonalHint.PHONE,
        {MASK},
    )


def test_a_row_ends_at_its_last_filled_cell() -> None:
    # tabulka.xlsx declares 35 columns on its first sheet; row 1 fills six, row 7 all 35.
    reading = read("tabulka.xlsx", ATTACHMENTS)
    assert reading.dataset is not None
    assert reading.segments[0].text == "Značka | Podíl | Cena | Nový | Uvedeno | Čas"
    assert not any(s.text.endswith("|") or s.text.endswith("| ") for s in reading.segments)
    assert [len(sheet.columns) for sheet in reading.dataset.sheets] == [35, 2, 1]


def test_a_broken_workbook_is_refused_never_half_read() -> None:
    for name in ("a.xls", "a.ods", "a.xlsx"):
        reading = read_source(b"not a workbook", name)
        assert reading.outcome is ReadingOutcome.REFUSED, name
        assert reading.dataset is None


# ------------------------------------------------------------------- the preview rules


def test_the_header_is_row_one_only_over_numbers_or_dates() -> None:
    over_numbers = preview_sheet("S", [(1, ["Kraj", "Počet"]), (2, ["Praha", "12"])])
    assert over_numbers.header_row == 1 and over_numbers.rows == 1
    all_text = preview_sheet("S", [(1, ["Kraj", "Město"]), (2, ["Praha", "Brno"])])
    assert all_text.header_row is None and all_text.rows == 2
    assert [c.header for c in all_text.columns] == [None, None]
    assert [c.letter for c in all_text.columns] == ["A", "B"]
    numbers_first = preview_sheet("S", [(1, ["1", "2"]), (2, ["3", "4"])])
    assert numbers_first.header_row is None


def test_kinds_counts_and_samples_are_bounded() -> None:
    rows = [(1, ["Hodnota", "Směs", "Prázdný"])] + [
        (n + 2, [str(n), "x" if n % 2 else "5", ""]) for n in range(DISTINCT_CAP + 10)
    ]
    sheet = preview_sheet("S", rows)
    value, mixed, empty = sheet.columns
    assert (value.kind, value.distinct, value.distinct_capped) == (
        ColumnKind.NUMBER,
        DISTINCT_CAP,
        True,
    )
    assert len(value.sample) == SAMPLE_SIZE
    assert (mixed.kind, mixed.distinct, mixed.distinct_capped) == (ColumnKind.MIXED, 2, False)
    assert (empty.kind, empty.filled) == (ColumnKind.EMPTY, 0)


@pytest.mark.parametrize(
    ("value", "kind"),
    [
        ("1 234,5", ColumnKind.NUMBER),
        ("1\xa0234", ColumnKind.NUMBER),
        ("12 %", ColumnKind.NUMBER),
        ("-0.5", ColumnKind.NUMBER),
        ("2026-10-13", ColumnKind.DATE),
        ("13. 10. 2026", ColumnKind.DATE),
        ("+420 600 000 001", ColumnKind.TEXT),
        ("Praha 4", ColumnKind.TEXT),
        ("  ", ColumnKind.EMPTY),
    ],
)
def test_a_cell_reads_as_one_kind(value: str, kind: ColumnKind) -> None:
    assert kind_of(value) is kind


def test_the_personal_data_patterns_are_the_ones_pinned() -> None:
    pinned = json.loads((FIXTURES / "client_datasets" / "personal.json").read_text("utf-8"))
    for case in pinned["values"]:
        found = personal_value(case["value"])
        assert (found.value if found else None) == case["hint"], case
    for case in pinned["headers"]:
        sheet = preview_sheet("S", [(1, [case["header"]]), (2, ["1"])])
        found = sheet.columns[0].personal
        assert (found.value if found else None) == case["hint"], case


def test_a_column_is_personal_from_a_third_of_its_values() -> None:
    def sheet(values: list[str]) -> Any:
        return preview_sheet(
            "S", [(1, ["Pole", "N"])] + [(i + 2, [v, "1"]) for i, v in enumerate(values)]
        )

    mostly = sheet(["a@example.test", "b", "c"])
    assert mostly.columns[0].personal is PersonalHint.EMAIL
    assert set(mostly.columns[0].sample) == {MASK}
    rarely = sheet(["a@example.test", "b", "c", "d"])
    assert rarely.columns[0].personal is None


# ------------------------------------------------------------------ hostile ODS files


def ods(rows_xml: str) -> bytes:
    content = (
        '<?xml version="1.0"?><office:document-content'
        ' xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"'
        ' xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"'
        ' xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        '<office:body><office:spreadsheet><table:table table:name="S">'
        f"{rows_xml}</table:table></office:spreadsheet></office:body></office:document-content>"
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
        archive.writestr("content.xml", content)
    return out.getvalue()


def cell(text: str, repeat: int = 1) -> str:
    return (
        f'<table:table-cell office:value-type="string" table:number-columns-repeated="{repeat}">'
        f"<text:p>{text}</text:p></table:table-cell>"
    )


def test_the_empty_rest_of_a_sheet_is_counted_never_materialized() -> None:
    empty_cells = '<table:table-cell table:number-columns-repeated="16384"/>'
    data = ods(
        f"<table:table-row>{cell('Kraj')}{cell('Počet')}{empty_cells}</table:table-row>"
        f'<table:table-row table:number-rows-repeated="1048570">{empty_cells}</table:table-row>'
        f"<table:table-row>{cell('Praha')}{cell('12')}</table:table-row>"
    )
    reading = read_source(data, "a.ods")
    assert reading.outcome is ReadingOutcome.PARTIAL and reading.reason == "rows_bound"
    assert reading.dataset is not None
    [sheet] = reading.dataset.sheets
    assert sheet.truncated and len(sheet.columns) == 2


def test_a_filled_cell_repeated_past_the_bounds_is_cut() -> None:
    data = ods(f"<table:table-row>{cell('x', repeat=1_000_000)}</table:table-row>")
    reading = read_source(data, "a.ods")
    assert reading.dataset is not None
    assert reading.dataset.sheets[0].truncated
    assert reading.outcome is ReadingOutcome.PARTIAL


# ------------------------------------------------------------- re-reading (OI-110)


def client_scope(scoped: Any, user: str = "lead") -> ClientContext:
    return scoped.resolver.client_context(
        scoped.principal(scoped.users[user]), client_id=scoped.clients["primary"].client_id
    )


def test_a_source_kept_before_its_reader_is_read_again_and_its_first_reading_kept(
    scoped: Any, session: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = InMemoryArtifactStore()
    sources = ClientSourceRepository(session, store)
    lead = client_scope(scoped)
    data = (SOURCES / "utrata.csv").read_bytes()

    # As it was before K2c: the CSV kept, read by an older reader that saw only lines.
    def older(raw: bytes, name: str) -> SourceReading:
        from aia_core.domain.client_sources import Locator, Segment, reading_of_segments

        return reading_of_segments(
            "csv/0", [Segment(locator=Locator(line=1), text=raw.decode("utf-8-sig"))]
        )

    monkeypatch.setattr(repository_module, "read_source", older)
    kept, _ = sources.add(lead, filename="útrata.csv", data=data)
    assert kept.reader == "csv/0"
    monkeypatch.undo()

    record, changed = sources.reread(lead, kept.source_id)
    assert changed and (record.reader, record.outcome) == ("csv/1", ReadingOutcome.READ)
    reading = sources.reading(lead, kept.source_id)
    assert reading.dataset is not None and reading.dataset.sheets[0].rows == 3
    # The original is unchanged and both readings stay, each under its reader's name.
    names = sorted(k.rsplit("/", 1)[-1] for k in store.keys)
    assert names == ["original", "reading-csv-0.json", "reading-csv-1.json"]
    # Read by the current reader already: nothing to do.
    assert sources.reread(lead, kept.source_id)[1] is False


def test_adding_the_same_bytes_again_reads_them_with_the_current_reader(
    scoped: Any, session: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = ClientSourceRepository(session, InMemoryArtifactStore())
    lead = client_scope(scoped)
    data = (SOURCES / "utrata.csv").read_bytes()
    monkeypatch.setattr(
        repository_module,
        "read_source",
        lambda raw, name: SourceReading(
            outcome=ReadingOutcome.UNSUPPORTED, reason="reader_pending"
        ),
    )
    kept, _ = sources.add(lead, filename="útrata.csv", data=data)
    assert kept.outcome is ReadingOutcome.UNSUPPORTED
    monkeypatch.undo()
    again, created = sources.add(lead, filename="kopie.csv", data=data)
    assert not created and (again.outcome, again.reader) == (ReadingOutcome.READ, "csv/1")


def test_reading_again_needs_the_right_to_add_and_the_client(scoped: Any, session: Any) -> None:
    sources = ClientSourceRepository(session, InMemoryArtifactStore())
    lead = client_scope(scoped)
    kept, _ = sources.add(lead, filename="a.csv", data=b"a;b\n1;2\n")
    reader_only = dataclasses.replace(
        lead,
        permissions=frozenset(
            p for p in lead.permissions if p is not ClientPermission.PROPOSE_CLIENT_KNOWLEDGE
        ),
    )
    with pytest.raises(ScopeDenied):
        sources.reread(reader_only, kept.source_id)
    other = scoped.resolver.client_context(
        scoped.principal(scoped.users["other_lead"]), client_id=scoped.clients["other"].client_id
    )
    with pytest.raises(ScopeDenied):
        sources.reread(other, kept.source_id)
