"""The report's document model as stored data (report-delivery RD5a).

The stored form is what the Zpráva pane reads and what every later edit names a paragraph in, so
these tests pin: every section and block has an id, the ids are positional and fixed, every ref a
block cites is in the ledger with the text the DOCX prints, a suppressed ref carries no text, no
bytes are stored, and the bytes are canonical.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from report_samples import KINDS, build

from aia_core.domain.report import numbers
from aia_core.domain.report.document_model import (
    DOCUMENT_MODEL_CONTRACT,
    DocumentModelInvalid,
    document_bytes,
    document_payload,
    read_document_payload,
)
from aia_core.domain.report.model import (
    Column,
    NumberCell,
    Paragraph,
    ReportDocument,
    Section,
    SociomapFigure,
    Table,
    TableRow,
    Text,
    TextCell,
    Value,
)


def _blocks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [block for section in payload["sections"] for block in section["blocks"]]


@pytest.mark.parametrize("kind", KINDS)
def test_every_section_and_block_has_a_unique_positional_id(kind: str, report_ledger: Any) -> None:
    document = build(kind, report_ledger)
    payload = document_payload(document)

    section_ids = [section["id"] for section in payload["sections"]]
    assert len(section_ids) == len(set(section_ids)) == len(document.sections)
    for section, stored in zip(document.sections, payload["sections"], strict=True):
        # The composer's own id when it gave one; never replaced.
        if section.id is not None:
            assert stored["id"] == section.id
        assert [b["id"] for b in stored["blocks"]] == [
            f"{stored['id']}.{n}" for n in range(1, len(section.blocks) + 1)
        ]
    block_ids = [block["id"] for block in _blocks(payload)]
    assert len(block_ids) == len(set(block_ids))


@pytest.mark.parametrize("kind", KINDS)
def test_every_cited_ref_resolves_in_the_ledger(kind: str, report_ledger: Any) -> None:
    payload = document_payload(build(kind, report_ledger))
    ledger = payload["ledger"]["refs"]
    cited = {ref for block in _blocks(payload) for ref in block["refs"]}
    assert cited, "the samples cite evidence"
    assert cited == set(ledger)
    for section in payload["sections"]:
        assert set(section["refs"]) == {r for b in section["blocks"] for r in b["refs"]}


@pytest.mark.parametrize("kind", KINDS)
def test_the_ledger_prints_what_the_docx_prints(kind: str, report_ledger: Any) -> None:
    document = build(kind, report_ledger)
    stored = document_payload(document)["ledger"]
    assert stored["surface"] == document.ledger.surface.value
    for ref, entry in stored["refs"].items():
        if entry["suppressed"]:
            assert set(entry) == {"suppressed", "reasons"}
            assert entry["reasons"] == list(document.ledger.suppressed[ref])
            continue
        row = document.ledger.row(ref)
        assert entry["value_text"] == numbers.with_unit(row.value, row.decimals, row.unit)
        assert entry["number_text"] == numbers.number(row.value, row.decimals)
        assert entry["grade"] == document.ledger.grade(ref).value
        if row.interval is None:
            assert entry["interval_text"] is None
        else:
            assert entry["interval_text"] == numbers.interval(row.interval, row.decimals, row.unit)
        if row.support.effective_n is None:
            assert entry["base_text"] is None  # unknown, never a guess
        else:
            assert entry["base_text"] == numbers.base_n(row.support.effective_n)


def test_a_client_estimate_always_shows_its_interval(report_ledger: Any) -> None:
    payload = document_payload(build("client", report_ledger))
    ledger = payload["ledger"]["refs"]
    values = [
        inline
        for block in _blocks(payload)
        for inline in block.get("content", [])
        if inline["type"] == "value"
    ]
    cells = [
        cell
        for block in _blocks(payload)
        if block["type"] == "table"
        for row in block["rows"]
        for cell in row["cells"]
        if cell["type"] == "number"
    ]
    shown = [v for v in [*values, *cells] if ledger[v["ref"]].get("interval_text")]
    assert shown
    assert all(v["with_interval"] for v in shown)


def test_a_suppressed_ref_carries_no_number(report_ledger: Any) -> None:
    document = build("internal", report_ledger)
    suppressed = next(iter(document.ledger.suppressed))
    first = document.sections[0]
    cited = replace(
        first,
        blocks=(*first.blocks, Paragraph((Text("Potlačeno: "), Value(suppressed)))),
    )
    payload = document_payload(replace(document, sections=(cited, *document.sections[1:])))
    entry = payload["ledger"]["refs"][suppressed]
    assert entry["suppressed"] is True
    assert "value_text" not in entry
    last = payload["sections"][0]["blocks"][-1]
    assert last["content"][1] == {"type": "value", "ref": suppressed, "with_interval": False}


def test_no_bytes_are_stored_only_their_hash(report_ledger: Any) -> None:
    document = build("internal", report_ledger)
    image = b"\x89PNG fictional map bytes"
    figure = SociomapFigure(
        id="fig-map",
        title="Mapa",
        image_png=image,
        methodology_status="INTERNAL_ONLY",
        stress_1=0.083,
        source="Fiktivní běh",
        alt="Mapa objektů",
    )
    first = replace(document.sections[0], blocks=(*document.sections[0].blocks, figure))
    data = document_bytes(replace(document, sections=(first, *document.sections[1:])))
    stored = json.loads(data)["sections"][0]["blocks"][-1]
    assert stored["type"] == "sociomap_figure"
    assert stored["image_sha256"] == hashlib.sha256(image).hexdigest()
    assert "image_png" not in stored
    assert image.hex() not in data.decode()
    assert "fictional map bytes" not in data.decode()


def test_identifiers_are_internal_only(report_ledger: Any) -> None:
    internal = build("internal", report_ledger)
    with_ids = replace(internal, meta=replace(internal.meta, identifiers=(("Běh", "run-1"),)))
    assert document_payload(with_ids)["meta"]["identifiers"] == [["Běh", "run-1"]]
    client = build("client", report_ledger)
    with_ids = replace(client, meta=replace(client.meta, identifiers=(("Běh", "run-1"),)))
    assert document_payload(with_ids)["meta"]["identifiers"] == []


def test_a_section_without_an_id_takes_its_position(report_ledger: Any) -> None:
    document = build("internal", report_ledger)
    unnamed = Section("Bez id", (Paragraph((Text("Text."),)),))
    payload = document_payload(replace(document, sections=(*document.sections, unnamed)))
    last = payload["sections"][-1]
    n = len(document.sections) + 1
    assert last["id"] == f"section-{n}"
    assert last["blocks"][0]["id"] == f"section-{n}.1"


def test_the_bytes_are_canonical_and_read_back(report_ledger: Any) -> None:
    document = build("internal", report_ledger)
    data = document_bytes(document)
    assert data == document_bytes(document)
    payload = read_document_payload(data)
    assert payload == document_payload(document)
    assert payload["contract"] == DOCUMENT_MODEL_CONTRACT
    assert (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        == data
    )


@pytest.mark.parametrize(
    "data",
    [
        b"not json",
        b"\xff",
        b"[]",
        json.dumps({"contract": "aia-report-document-0", "sections": [], "ledger": {}}).encode(),
        json.dumps({"contract": DOCUMENT_MODEL_CONTRACT, "ledger": {}}).encode(),
    ],
)
def test_other_bytes_are_refused(data: bytes) -> None:
    with pytest.raises(DocumentModelInvalid):
        read_document_payload(data)


def test_an_unknown_ref_fails_as_it_fails_the_render(report_ledger: Any) -> None:
    document = build("internal", report_ledger)
    bad = Section("X", (Paragraph((Value("no-such-ref"),)),), id="x")
    with pytest.raises(KeyError):
        document_payload(ReportDocument(document.meta, (bad,), document.ledger))


def test_a_table_drops_the_rows_the_docx_removes_and_counts_them(report_ledger: Any) -> None:
    """``render_table`` removes a row citing a suppressed ref and prints how many; the stored
    table holds the same rows and the same count (review of #584)."""
    document = build("internal", report_ledger)
    suppressed = next(iter(document.ledger.suppressed))
    admitted = next(iter(document.ledger.rows))
    table = Table(
        id="tab-x",
        title="Fiktivní tabulka",
        columns=(Column("Skupina"), Column("Hodnota")),
        rows=(
            TableRow((TextCell("Kept"), NumberCell(admitted))),
            TableRow((TextCell("Malá skupina"), NumberCell(suppressed))),
        ),
        source="Fiktivní běh",
    )
    first = replace(document.sections[0], blocks=(table,))
    payload = document_payload(replace(document, sections=(first,)))
    stored = payload["sections"][0]["blocks"][0]
    assert stored["suppressed_rows"] == 1
    assert [row["cells"][0]["text"] for row in stored["rows"]] == ["Kept"]
    assert stored["refs"] == [admitted]
    assert suppressed not in payload["ledger"]["refs"]


#: The stored form the web reads (apps/web/src/lib/artifacts/report.test.ts): one internal sample,
#: with a map figure and a table row the DOCX removes, so every block kind the pane draws is in it.
SHARED_FIXTURE = Path(__file__).parent / "fixtures" / "report_document" / "internal.json"


def _shared_document(report_ledger: Any) -> ReportDocument:
    document = build("internal", report_ledger)
    suppressed = next(iter(document.ledger.suppressed))
    admitted = next(iter(document.ledger.rows))
    extra = Section(
        "Fiktivní doplněk",
        (
            Table(
                id="tab-shared",
                title="Fiktivní tabulka",
                columns=(Column("Skupina"), Column("Hodnota")),
                rows=(
                    TableRow((TextCell("Kept"), NumberCell(admitted, with_interval=True))),
                    TableRow((TextCell("Malá skupina"), NumberCell(suppressed))),
                ),
                source="Fiktivní běh",
            ),
            SociomapFigure(
                id="fig-shared",
                title="Fiktivní mapa",
                image_png=b"\x89PNG fictional",
                methodology_status="INTERNAL_ONLY",
                stress_1=0.083,
                source="Fiktivní běh",
                alt="Mapa objektů",
            ),
        ),
        id="ch-shared",
    )
    return replace(document, sections=(*document.sections, extra))


def test_the_web_reads_the_document_model_this_writes(report_ledger: Any) -> None:
    """The web's fixture is this serializer's output, byte for byte. After a change to the stored
    form, rewrite it with AIA_WRITE_REPORT_DOCUMENT_FIXTURE=1 and bump DOCUMENT_MODEL_CONTRACT
    when a reader of the old form would misread the new one."""
    data = json.dumps(
        document_payload(_shared_document(report_ledger)),
        ensure_ascii=False,
        indent=1,
        sort_keys=True,
    )
    if os.environ.get("AIA_WRITE_REPORT_DOCUMENT_FIXTURE") == "1":
        SHARED_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        SHARED_FIXTURE.write_text(data + "\n", encoding="utf-8")
    assert SHARED_FIXTURE.read_text(encoding="utf-8") == data + "\n"
