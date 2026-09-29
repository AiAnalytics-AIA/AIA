"""A brief attachment's text is the text 18.6.6 read of it (ADR 0018).

``fixtures/attachment_text`` holds fictional documents and the unit's own
``data_library._extract_text`` output on each, captured by
``tools/attachment_text_capture.py`` with the libraries the unit read them with. The
unit's attachment code turned its failure marker into ``""``
(``ui_server.py:1031-1034``); AIA returns ``""`` directly, so the comparison applies
that same rule to the unit's output.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

from aia_core.domain.attachments import TEXT_MAX_CHARS
from aia_core.infrastructure import document_text
from aia_core.infrastructure.document_text import extract_text

FIXTURES = Path(__file__).parent / "fixtures" / "attachment_text"
UNIT_SOURCE = (
    Path(__file__).resolve().parents[3] / "legacy" / "npc-panel-18.6.6" / "app" / "data_library.py"
)
INDEX = json.loads((FIXTURES / "index.json").read_text())
EXPECTED = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
FAILED = "[TEXT_EXTRACTION_FAILED:"


def _as_attached(unit_text: str) -> str:
    """What the unit's attachment code kept of ``_extract_text``'s answer."""
    return "" if unit_text.startswith(FAILED) else unit_text


def test_the_fixtures_are_the_ones_captured() -> None:
    assert sorted(INDEX["inputs"]) == sorted(EXPECTED)
    for name, digest in INDEX["inputs"].items():
        assert hashlib.sha256((FIXTURES / "inputs" / name).read_bytes()).hexdigest() == digest
    assert (
        hashlib.sha256((FIXTURES / "expected.json").read_bytes()).hexdigest()
        == INDEX["expected_sha256"]
    )


def test_the_unit_function_the_fixtures_came_from_is_unchanged() -> None:
    """If the vendored function changed, the fixtures no longer describe it: recapture."""
    import ast

    source = UNIT_SOURCE.read_text(encoding="utf-8")
    node = next(
        n
        for n in ast.parse(source).body
        if isinstance(n, ast.FunctionDef) and n.name == "_extract_text"
    )
    segment = ast.get_source_segment(source, node)
    assert segment is not None
    assert hashlib.sha256(segment.encode("utf-8")).hexdigest() == INDEX["unit_function_sha256"]


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_aia_reads_what_the_unit_read(name: str) -> None:
    data = (FIXTURES / "inputs" / name).read_bytes()
    assert extract_text(data, name) == _as_attached(EXPECTED[name])


def test_the_fixtures_cover_every_kind_and_every_way_of_failing() -> None:
    read = {name for name, text in EXPECTED.items() if _as_attached(text)}
    failed = {name for name, text in EXPECTED.items() if text.startswith(FAILED)}
    assert {".txt", ".md", ".csv", ".docx", ".xlsx", ".xlsm", ".pdf"} <= {
        Path(n).suffix for n in read
    }
    # A corrupt Word file, a truncated PDF, and a sheet that declares no size: the
    # unit kept no text of any of them, and neither does AIA.
    assert failed == {"poskozeny.docx", "poskozeny.pdf", "bez_rozmeru.xlsx"}
    # A kind with no reader is kept as a reference, silently, in both.
    assert EXPECTED["obrazek.png"] == ""
    # The unit's own limits hold: 30 columns, 300 rows, tables not read.
    assert EXPECTED["tabulka.xlsx"].count("řádek") == 300
    assert "S30\n" in EXPECTED["tabulka.xlsx"] and "S31" not in EXPECTED["tabulka.xlsx"]
    assert "Tabulka se nečte" not in EXPECTED["zadani.docx"]


def test_text_is_cut_at_the_units_limit() -> None:
    assert len(extract_text(b"a" * (TEXT_MAX_CHARS + 10), "long.txt")) == TEXT_MAX_CHARS
    assert extract_text("Příliš".encode() + b"\xff", "zadani.TXT") == "Příliš�"


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in members.items():
            z.writestr(name, body)
    return buf.getvalue()


def test_an_office_file_that_declares_too_much_is_not_opened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The unit inflated whatever it was given; AIA looks at the declared sizes first."""
    real = (FIXTURES / "inputs" / "zadani.docx").read_bytes()
    assert extract_text(real, "zadani.docx")
    monkeypatch.setattr(document_text, "ZIP_MAX_UNCOMPRESSED", 1024)
    assert extract_text(real, "zadani.docx") == ""
    monkeypatch.undo()
    many = _zip({f"part{i}.xml": b"<x/>" for i in range(6)})
    monkeypatch.setattr(document_text, "ZIP_MAX_MEMBERS", 5)
    assert extract_text(many, "many.xlsx") == ""


def test_a_missing_reader_library_is_a_defect_not_an_unreadable_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "pypdf", None)
    with pytest.raises(ImportError):
        extract_text((FIXTURES / "inputs" / "prezentace.pdf").read_bytes(), "prezentace.pdf")
