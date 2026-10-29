"""A file given to the Lead: the ``files`` layer of the turn's context (lead-orchestration LO18a).

Each file within its share, its outline and whole segments in order, the rest counted; a
dataset its preview and never a row; a moved reading nothing; the file's class its source rule's,
an attached dataset's lineage the unrecorded client-knowledge one; the manifest names each file
and what it left out.
"""

from __future__ import annotations

from typing import Any

from aia_core.domain.ai_contracts import canonical_json
from aia_core.domain.client_datasets import ColumnKind, ColumnPreview, DatasetPreview, SheetPreview
from aia_core.domain.client_sources import (
    Locator,
    ReadingOutcome,
    Segment,
    SourceFamily,
    SourceReading,
)
from aia_core.domain.knowledge import UNRECORDED_KNOWLEDGE_LINEAGE
from aia_core.domain.lead_context import context_manifest
from aia_core.domain.lead_files import (
    FILES_LAYER,
    FILES_MAX_BYTES,
    FileForTurn,
    LeadFileRef,
    files_layer,
)
from aia_core.domain.prompt_slots import get_slot
from aia_core.domain.research_lead import (
    DEFAULT_LEAD_NAME,
    DEFAULT_SOUL,
    LEAD_PROMPT_ID,
    citable_context,
    context_classification,
    freeze_context,
    layer,
    lead_request,
    model_message,
)
from aia_core.domain.residency import DataClass

SHA = "a" * 64
READ_SHA = "b" * 64


def _ref(n: int = 1, name: str = "Zadání.pdf") -> LeadFileRef:
    return LeadFileRef(
        source_id=f"SRC-{n:016x}", sha256=SHA, reading_sha256=READ_SHA, filename=name
    )


def _pdf(pages: int, text: str = "Klient chce 120 prodejen do roku 2027.") -> SourceReading:
    return SourceReading(
        outcome=ReadingOutcome.READ,
        reader="pdf/1",
        segments=tuple(
            Segment(locator=Locator(page=p), text=f"{text} (strana {p})")
            for p in range(1, pages + 1)
        ),
    )


def _file(reading: SourceReading | None, **kw: Any) -> FileForTurn:
    return FileForTurn(
        ref=kw.pop("ref", _ref()),
        family=kw.pop("family", SourceFamily.DOCUMENT),
        internal=kw.pop("internal", False),
        reading=reading,
        **kw,
    )


def _bytes(value: Any) -> int:
    return len(canonical_json(value).encode("utf-8"))


def _context(files: dict[str, Any] | None) -> dict[str, Any]:
    slot = get_slot(LEAD_PROMPT_ID)
    assert slot is not None
    return freeze_context(
        prompt=slot.baseline_pin(),
        lead={
            "name": DEFAULT_LEAD_NAME,
            "soul": DEFAULT_SOUL,
            "user": "",
            "notes": [],
            "first_conversation": False,
        },
        knowledge=[],
        omitted_knowledge_ids=[],
        study={"name": "S", "client_name": "C", "budget_usd": 25.0, "spent_usd": 0.0},
        design={"workspace_revision": 1, "design_revision_id": "REV-1", "content": {}},
        runs=[],
        view={"kind": "message", "stage": "brief", "focus": None, "message": "Přečti to."},
        conversation=[],
        files=files,
    )


def test_a_short_document_reaches_the_turn_whole_with_its_locators() -> None:
    entry = files_layer([_file(_pdf(2))])
    assert entry is not None
    [one] = entry["files"]
    assert one["name"] == "Zadání.pdf" and one["outcome"] == "READ"
    assert one["outline"] == {"pages": [1, 2], "segments": 2}
    assert [s["at"] for s in one["segments"]] == [{"page": 1}, {"page": 2}]
    assert "omitted" not in one


def test_a_long_document_is_cut_at_its_share_and_the_rest_named() -> None:
    entry = files_layer([_file(_pdf(2000))])
    assert entry is not None
    [one] = entry["files"]
    assert _bytes({"layer": FILES_LAYER, **entry}) <= FILES_MAX_BYTES
    kept = len(one["segments"])
    assert 0 < kept < 2000
    # Whole segments, in order, from the first; the first left out named, the rest counted.
    assert [s["at"]["page"] for s in one["segments"]] == list(range(1, kept + 1))
    assert one["omitted"] == {"segments": 2000 - kept, "first": {"page": kept + 1}}
    # The outline covers every locator, not only what was sent.
    assert one["outline"]["pages"] == [1, 2000]


def test_three_files_share_the_layer_evenly() -> None:
    files = [_file(_pdf(2000), ref=_ref(n, f"{n}.pdf")) for n in (1, 2, 3)]
    entry = files_layer(files)
    assert entry is not None
    assert _bytes({"layer": FILES_LAYER, **entry}) <= FILES_MAX_BYTES
    sizes = [_bytes(f) for f in entry["files"]]
    assert max(sizes) - min(sizes) < 400


def test_one_paragraph_longer_than_the_share_is_cut_never_dropped_whole() -> None:
    reading = SourceReading(
        outcome=ReadingOutcome.READ,
        reader="txt/1",
        segments=(
            Segment(locator=Locator(paragraph=1), text="ř" * 40_000),
            Segment(locator=Locator(paragraph=2), text="Konec."),
        ),
    )
    entry = files_layer([_file(reading)])
    assert entry is not None
    [one] = entry["files"]
    [cut] = one["segments"]
    assert cut["cut"] is True and cut["at"] == {"paragraph": 1} and cut["text"]
    assert one["omitted"] == {"segments": 1, "first": {"paragraph": 2}}
    assert _bytes({"layer": FILES_LAYER, **entry}) <= FILES_MAX_BYTES


def _dataset() -> SourceReading:
    columns = (
        ColumnPreview(
            index=1,
            letter="A",
            header="Obec",
            kind=ColumnKind.TEXT,
            filled=3,
            distinct=3,
            sample=("Brno",),
        ),
        ColumnPreview(
            index=2,
            letter="B",
            header="Telefon",
            kind=ColumnKind.TEXT,
            filled=3,
            distinct=3,
            personal="PHONE",
            sample=("•••",),
        ),
    )
    rows = tuple(
        Segment(locator=Locator(sheet="List1", row=r), text=f"Brno | +420 777 000 00{r}")
        for r in range(2, 5)
    )
    return SourceReading(
        outcome=ReadingOutcome.READ,
        reader="csv/1",
        segments=rows,
        dataset=DatasetPreview(
            sheets=(SheetPreview(name="List1", header_row=1, rows=3, columns=columns),)
        ),
    )


def test_a_dataset_is_its_preview_and_never_a_row() -> None:
    entry = files_layer([_file(_dataset(), family=SourceFamily.DATASET)])
    assert entry is not None
    [one] = entry["files"]
    assert "segments" not in one and "outline" not in one
    [sheet] = one["dataset"]["sheets"]
    assert [c["header"] for c in sheet["columns"]] == ["Obec", "Telefon"]
    assert sheet["columns"][1]["sample"] == ["•••"]
    assert "777" not in canonical_json(entry)


def test_a_wide_dataset_keeps_whole_columns_within_its_share() -> None:
    columns = tuple(
        ColumnPreview(
            index=i,
            letter="A",
            header=f"Sloupec {i}",
            kind=ColumnKind.NUMBER,
            filled=10,
            distinct=10,
            sample=tuple(str(i * 1000 + k) for k in range(5)),
        )
        for i in range(1, 600)
    )
    reading = SourceReading(
        outcome=ReadingOutcome.READ,
        reader="xlsx/1",
        dataset=DatasetPreview(
            sheets=(SheetPreview(name="Data", header_row=1, rows=10, columns=columns),)
        ),
    )
    entry = files_layer([_file(reading, family=SourceFamily.DATASET)])
    assert entry is not None
    [one] = entry["files"]
    kept = len(one["dataset"]["sheets"][0]["columns"])
    assert 0 < kept < 599 and one["omitted_columns"] == 599 - kept
    assert _bytes({"layer": FILES_LAYER, **entry}) <= FILES_MAX_BYTES


def test_a_reading_that_moved_or_a_file_never_read_sends_no_text() -> None:
    moved = files_layer([_file(None)])
    assert moved is not None
    assert moved["files"][0]["outcome"] == "reading_changed"
    assert "segments" not in moved["files"][0]
    image = SourceReading(outcome=ReadingOutcome.UNREADABLE, reason="not_text_media")
    unread = files_layer([_file(image, family=SourceFamily.IMAGE)])
    assert unread is not None
    assert (unread["files"][0]["outcome"], unread["files"][0]["reason"]) == (
        "UNREADABLE",
        "not_text_media",
    )


def test_no_file_no_layer() -> None:
    assert files_layer([]) is None
    context = _context(None)
    assert FILES_LAYER not in [e["layer"] for e in context["layers"]]


def test_the_layer_sits_before_the_view_and_is_sent_and_citable() -> None:
    context = _context(files_layer([_file(_pdf(1))]))
    names = [e["layer"] for e in context["layers"]]
    assert names.index(FILES_LAYER) == names.index("view") - 1
    assert "120 prodejen" in model_message(context)
    # Citable like knowledge (the product owner, 2026-10-28), its ids left out.
    citable = canonical_json(citable_context(context))
    assert "120 prodejen" in citable and "SRC-" not in citable and SHA not in citable


def test_the_files_class_is_its_source_rule_and_a_dataset_declares_its_lineage() -> None:
    files = [
        _file(_pdf(1)),
        _file(_pdf(1), ref=_ref(2, "interní.pdf"), internal=True),
        _file(_dataset(), ref=_ref(3, "data.csv"), family=SourceFamily.DATASET),
    ]
    context = _context(files_layer(files))
    slot = get_slot(LEAD_PROMPT_ID)
    assert slot is not None
    parts = [
        p
        for p in context_classification(context, (), slot.baseline_pin())
        if p["part"] == "client_file"
    ]
    assert [(p["data_class"], p["source"]) for p in parts] == [
        (DataClass.CLASS_A_CLIENT_CONFIDENTIAL.value, "rule:client_source"),
        (DataClass.CLASS_C_INTERNAL.value, "rule:internal_document"),
        (DataClass.CLASS_A_CLIENT_CONFIDENTIAL.value, "rule:client_source"),
    ]
    request = lead_request(context, policy_version="p", max_output_tokens=1000)
    assert request.data_classification is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
    assert UNRECORDED_KNOWLEDGE_LINEAGE in request.data_lineage.datasets
    # Without a dataset, the documents declare no dataset lineage.
    plain = lead_request(
        _context(files_layer(files[:2])), policy_version="p", max_output_tokens=1000
    )
    assert UNRECORDED_KNOWLEDGE_LINEAGE not in plain.data_lineage.datasets


def test_the_manifest_names_each_file_and_what_it_left_out() -> None:
    files = [
        _file(_pdf(2), ref=_ref(1, "krátký.pdf")),
        _file(_pdf(2000), ref=_ref(2, "dlouhý.pdf")),
        _file(None, ref=_ref(3, "změněný.pdf")),
    ]
    context = _context(files_layer(files))
    row = next(r for r in context_manifest(context)["layers"] if r["layer"] == FILES_LAYER)
    assert row["included"] == [f"SRC-{n:016x}" for n in (1, 2, 3)]
    assert row["omitted"] == [
        {"id": f"SRC-{2:016x}", "reason": "over_budget"},
        {"id": f"SRC-{3:016x}", "reason": "reading_changed"},
    ]
    assert row["ceiling_bytes"] == FILES_MAX_BYTES
    assert layer(context, FILES_LAYER)["note"]


def test_a_cut_is_measured_as_sent_so_escaped_text_never_overruns_the_share() -> None:
    """Review of LO18a: a quote or a control character takes more bytes as JSON than as UTF-8."""
    for text in ('"' * 40_000, "a\u0001b" * 15_000, "\\\n\t" * 15_000):
        reading = SourceReading(
            outcome=ReadingOutcome.READ,
            reader="txt/1",
            segments=(Segment(locator=Locator(paragraph=1), text=text),),
        )
        entry = files_layer([_file(reading), _file(reading, ref=_ref(2, "b.txt"))])
        assert entry is not None
        assert _bytes({"layer": FILES_LAYER, **entry}) <= FILES_MAX_BYTES
        assert all(f["segments"][0]["cut"] for f in entry["files"])


def test_a_turn_reads_three_files_and_names_the_rest() -> None:
    """Review of LO18a: a turn answering several queued messages could carry eighteen files."""
    files = [_file(_pdf(50), ref=_ref(n, f"{n}.pdf")) for n in range(1, 8)]
    entry = files_layer(files)
    assert entry is not None
    assert _bytes({"layer": FILES_LAYER, **entry}) <= FILES_MAX_BYTES
    read, named = entry["files"][:3], entry["files"][3:]
    assert all(f["segments"] for f in read)
    assert [f["outcome"] for f in named] == ["files_bound"] * 4
    assert all("segments" not in f for f in named)
    row = next(r for r in context_manifest(_context(entry))["layers"] if r["layer"] == FILES_LAYER)
    assert {o["id"] for o in row["omitted"]} >= {f"SRC-{n:016x}" for n in range(4, 8)}


def test_a_sheet_none_of_whose_columns_fit_is_counted_not_dropped_unsaid() -> None:
    def sheet(name: str, width: int) -> SheetPreview:
        return SheetPreview(
            name=name,
            header_row=1,
            rows=10,
            columns=tuple(
                ColumnPreview(
                    index=i,
                    letter="A",
                    header=f"{name} {i}",
                    kind=ColumnKind.NUMBER,
                    filled=10,
                    distinct=10,
                    sample=tuple(str(k) for k in range(5)),
                )
                for i in range(1, width + 1)
            ),
        )

    reading = SourceReading(
        outcome=ReadingOutcome.READ,
        reader="xlsx/1",
        dataset=DatasetPreview(sheets=(sheet("Široký", 600), sheet("Druhý", 3))),
    )
    entry = files_layer([_file(reading, family=SourceFamily.DATASET)])
    assert entry is not None
    [one] = entry["files"]
    assert [s["name"] for s in one["dataset"]["sheets"]] == ["Široký"]
    assert one["omitted_sheets"] == 1 and one["omitted_columns"] > 3


def test_a_document_cut_inside_its_only_segment_is_named_as_left_out() -> None:
    """Codex on #1129: one segment longer than the share is sent cut; the manifest must say so."""
    reading = SourceReading(
        outcome=ReadingOutcome.READ,
        reader="txt/1",
        segments=(Segment(locator=Locator(paragraph=1), text="slovo " * 10_000),),
    )
    entry = files_layer([_file(reading)])
    assert entry is not None
    assert entry["files"][0]["segments"][0]["cut"] is True
    row = next(r for r in context_manifest(_context(entry))["layers"] if r["layer"] == FILES_LAYER)
    assert row["omitted"] == [{"id": f"SRC-{1:016x}", "reason": "over_budget"}]
