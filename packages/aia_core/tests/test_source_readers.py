"""The presentation and open/legacy document readers of a client's sources (lifecycle K2b).

The fixtures are fictional documents LibreOffice converted from one source
(``tools/source_fixtures.py``), pinned by SHA-256. The rules pinned here:
- every format reads to the same paragraphs and table rows, each with its place;
- a Word 97 field shows its result, never its code;
- a Word 97 table's cells are the paragraphs Word counts, and no row is guessed;
- a hostile file (a DTD, a ZIP bomb, a missing part, an encrypted or pre-97 DOC) is
  refused by name, never half-read.
"""

from __future__ import annotations

import hashlib
import io
import json
import struct
import zipfile
from pathlib import Path

import pytest

from aia_core.domain.client_sources import ReadingOutcome
from aia_core.domain.deep_research.documents import DocumentRefused
from aia_core.infrastructure.source_reading import piece_text, read_source

FIXTURES = Path(__file__).parent / "fixtures" / "client_sources"
HEADING = "Zadání výzkumu: fiktivní ranní nápoj"
AUDIENCE = "Cílová skupina: lidé 18–65 let, kteří pijí kávu alespoň třikrát týdně."  # noqa: RUF001 -- the document's own dash
PLAIN = "Plain ASCII paragraph for the compressed path."
SOURCE = "Zdroj: fiktivní studie z roku 2026."


def read(name: str) -> list[tuple[dict[str, object], str]]:
    reading = read_source((FIXTURES / name).read_bytes(), name)
    assert reading.outcome is ReadingOutcome.READ, (name, reading.reason)
    return [(s.locator.model_dump(exclude_none=True), s.text) for s in reading.segments]


def test_the_fixtures_are_the_ones_pinned() -> None:
    index = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))
    for name, sha in index.items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == sha, name


@pytest.mark.parametrize("name", ["zadani.odt", "zadani.docx"])
def test_an_odt_reads_as_its_docx_does(name: str) -> None:
    assert read(name) == [
        ({"paragraph": 1}, HEADING),
        ({"paragraph": 2}, AUDIENCE),
        # Paragraph 3 is empty: counted, so the numbers are the ones a reader finds.
        ({"paragraph": 4}, PLAIN),
        ({"table": 1, "row": 1}, "Značka | Podíl"),
        ({"table": 1, "row": 2}, "Ranní Ň | 12 %"),
        ({"paragraph": 5}, SOURCE),
    ]


def test_a_doc_reads_its_cells_as_the_paragraphs_word_counts() -> None:
    assert read("zadani.doc") == [
        ({"paragraph": 1}, HEADING),
        ({"paragraph": 2}, AUDIENCE),
        ({"paragraph": 4}, PLAIN),
        ({"paragraph": 5}, "Značka"),
        ({"paragraph": 6}, "Podíl"),
        # 7 and 10 are the rows' end marks: Word's own paragraphs, empty.
        ({"paragraph": 8}, "Ranní Ň"),
        ({"paragraph": 9}, "12 %"),
        # The link is a field: its result is read, its code never.
        ({"paragraph": 11}, SOURCE),
    ]


def test_a_presentation_reads_slide_by_slide_in_its_own_order() -> None:
    assert read("prezentace.pptx") == [
        (
            {"slide": 1},
            "Fiktivní ranní nápoj\nCíl: porozumět ranním návykům.\nMetoda: online panel.",
        ),
        # Slide 2 has no text and is left out; slide 3 keeps its number.
        ({"slide": 3}, "Doporučení: testovat dvě příchutě."),
    ]


# ------------------------------------------------------------- the Word 97 piece table


def fib(
    *, ccp_text: int, fc_clx: int, lcb_clx: int, flags: int = 0, nfib: int = 0x00C1
) -> bytearray:
    word = bytearray(0x400)
    struct.pack_into("<HH", word, 0, 0xA5EC, nfib)
    struct.pack_into("<H", word, 0x000A, flags)
    struct.pack_into("<i", word, 0x004C, ccp_text)
    struct.pack_into("<II", word, 0x01A2, fc_clx, lcb_clx)
    return word


def clx(pieces: list[tuple[int, int, bool]]) -> bytes:
    """A CLX of one Prc and a piece table: (characters, byte offset, compressed)."""
    cps = [0]
    for chars, _, _ in pieces:
        cps.append(cps[-1] + chars)
    pcds = b"".join(
        struct.pack("<HIH", 0, (offset * 2) | 0x40000000 if compressed else offset, 0)
        for _, offset, compressed in pieces
    )
    plc = struct.pack(f"<{len(cps)}I", *cps) + pcds
    prc = b"\x01" + struct.pack("<H", 2) + b"\x00\x00"
    return prc + b"\x02" + struct.pack("<I", len(plc)) + plc


def test_compressed_and_unicode_pieces_are_read_in_order_up_to_the_main_text() -> None:
    first, second = "Káva ", "Čaj"
    table = clx([(len(first), 0x200, True), (len(second), 0x300, False), (4, 0x340, False)])
    word = fib(ccp_text=len(first) + len(second), fc_clx=0, lcb_clx=len(table))
    word[0x200 : 0x200 + len(first)] = first.encode("cp1252")
    word[0x300 : 0x300 + 2 * len(second)] = second.encode("utf-16-le")
    # The third piece is past the main text (a footnote's): not read.
    word[0x340:0x348] = "Pozn".encode("utf-16-le")
    assert piece_text(bytes(word), table) == "Káva Čaj"


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"flags": 0x0100}, "document_encrypted"),
        ({"nfib": 0x0065}, "document_too_old"),
        ({"fc_clx": 10_000}, "document_malformed"),
    ],
)
def test_a_doc_it_cannot_trust_is_refused_by_name(change: dict[str, int], reason: str) -> None:
    table = clx([(3, 0x200, True)])
    args = {"ccp_text": 3, "fc_clx": 0, "lcb_clx": len(table), **change}
    word = fib(**args)
    word[0x200:0x203] = b"abc"
    with pytest.raises(DocumentRefused) as refused:
        piece_text(bytes(word), table)
    assert refused.value.reason == reason


def test_a_piece_past_the_stream_is_refused() -> None:
    table = clx([(50, 0x3F0, False)])
    word = fib(ccp_text=50, fc_clx=0, lcb_clx=len(table))
    with pytest.raises(DocumentRefused) as refused:
        piece_text(bytes(word), table)
    assert refused.value.reason == "document_malformed"


def test_a_file_named_doc_that_is_not_one_is_refused() -> None:
    reading = read_source(b"not a compound file", "a.doc")
    assert (reading.outcome, reading.reason) == (ReadingOutcome.REFUSED, "document_malformed")


# ------------------------------------------------------------------ hostile ZIP files


def zip_of(parts: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    return out.getvalue()


def test_a_part_declaring_a_dtd_is_refused_before_it_is_parsed() -> None:
    laughs = (
        b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
        b'<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0">'
        b"&b;</office:document-content>"
    )
    reading = read_source(zip_of({"content.xml": laughs}), "a.odt")
    assert (reading.outcome, reading.reason) == (ReadingOutcome.REFUSED, "document_malformed")


@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le", "utf-16-be"])
def test_a_dtd_is_refused_in_whatever_encoding_the_part_declares(encoding: str) -> None:
    # In UTF-16 neither b"<!DOCTYPE" nor b"<!ENTITY" occurs in the bytes, yet expat
    # reads the declaration and expands its entities.
    laughs = (
        f'<?xml version="1.0" encoding="{encoding.upper()}"?>'
        '<!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"'
        ' xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        "<office:body><office:text><text:p>&b;</text:p></office:text></office:body>"
        "</office:document-content>"
    )
    data = laughs.encode(encoding)
    if encoding != "utf-16":
        data = "\ufeff".encode(encoding) + data
    assert b"<!DOCTYPE" not in data and b"<!ENTITY" not in data
    reading = read_source(zip_of({"content.xml": data}), "a.odt")
    assert (reading.outcome, reading.reason) == (ReadingOutcome.REFUSED, "document_malformed")
    assert not reading.segments


def _xlsx_with_entity() -> bytes:
    """A workbook whose one cell is an entity its sheet's own DTD declares."""
    from openpyxl import Workbook

    book = Workbook()
    book.active["A1"] = "PLACEHOLDER"
    plain = io.BytesIO()
    book.save(plain)
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(plain.getvalue())) as source,
        zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "xl/worksheets/sheet1.xml":
                data = b'<!DOCTYPE w [<!ENTITY a "AAAA"><!ENTITY b "&a;&a;&a;&a;">]>' + (
                    data.replace(b"PLACEHOLDER", b"&b;")
                )
            target.writestr(info, data)
    return out.getvalue()


def test_a_workbook_part_declaring_a_dtd_is_refused_before_openpyxl_parses_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Without defusedxml (the images do not install it), openpyxl parses with expat and
    # expands internal entities. Whether it is installed here or not, the workbook must
    # never reach it: refused as an ODS part is.
    import openpyxl

    opened: list[object] = []
    monkeypatch.setattr(openpyxl, "load_workbook", lambda *a, **k: opened.append(a))
    reading = read_source(_xlsx_with_entity(), "a.xlsx")
    assert (reading.outcome, reading.reason) == (ReadingOutcome.REFUSED, "document_malformed")
    assert not reading.segments
    assert opened == []


def test_a_zip_that_inflates_far_past_its_size_is_refused() -> None:
    bomb = zip_of({"content.xml": b"\0" * (20 * 1024 * 1024)})
    for name in ("a.odt", "a.pptx"):
        reading = read_source(bomb, name)
        assert (reading.outcome, reading.reason) == (ReadingOutcome.REFUSED, "document_zip_bounds")


def test_a_presentation_without_its_parts_is_refused() -> None:
    reading = read_source(zip_of({"ppt/other.xml": b"<x/>"}), "a.pptx")
    assert (reading.outcome, reading.reason) == (ReadingOutcome.REFUSED, "document_malformed")
