"""A file given to the Lead in a message: its ref on the turn, and the ``files`` layer of the
turn's context (lead-orchestration LO18a). Pure.

* **The turn carries a ref, never the bytes** (:class:`LeadFileRef`): the client source's id,
  the SHA-256 of its bytes and of its reading as the person attached it. The file itself is
  kept as the client's source (``client_source_repository``) and listed under the client's
  Data.
* **Only the turn that answers the message reads it** (the product owner, 2026-10-28: "file
  only in its turn"). An earlier message's files are named in the conversation, never read
  again; reading more of a file is the Lead's read request (LO18d).
* **Bounded** (:func:`files_layer`): the layer's share is :data:`FILES_MAX_BYTES` of the
  turn's 96 KB, split evenly between at most :data:`FILES_PER_TURN` files; any more are
  named. Per file: its outline (every locator, by range), then whole segments in order while
  the share lasts; the rest is counted and the first segment left out named.
* **A dataset is its preview, never its rows** (Q62 (a), lead-client-knowledge LK5): a
  ``DATASET`` file carries its columns, kinds, fill and masked samples and no segment.
* **The client's document, not evidence**: citable like knowledge (the product owner,
  2026-10-28: "citable like knowledge"), never respondent evidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from .ai_contracts import canonical_json
from .client_sources import Locator, SourceFamily, SourceReading

__all__ = [
    "FILES_LAYER",
    "FILES_MAX_BYTES",
    "FILES_NOTE",
    "FILES_PER_MESSAGE",
    "FILES_PER_TURN",
    "FileForTurn",
    "LeadFileRef",
    "files_layer",
]

FILES_LAYER: Final = "files"
#: The ``files`` layer's share of the turn's context, for every file the turn carries.
FILES_MAX_BYTES: Final = 16 * 1024
#: The most files one message carries.
FILES_PER_MESSAGE: Final = 3
#: The most files one turn reads; a turn answering several queued messages names the rest.
FILES_PER_TURN: Final = 3
#: The least room worth cutting a first segment into, rather than leaving it out whole.
_CUT_MIN_BYTES: Final = 256
#: What a file's ``omitted`` / ``omitted_columns`` and the list's separator take at most.
_OMITTED_BYTES: Final = 160

FILES_NOTE: Final = (
    "Dokumenty, které výzkumník přiložil k této zprávě: materiál klienta, nikdy zjištění "
    "respondentů. Každý je zkrácen na svůj podíl; co v něm chybí, je vyjmenováno."
)

_SHA256 = r"^[0-9a-f]{64}$"


class LeadFileRef(BaseModel):
    """A file a person's message carries: the client's source, as they attached it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(pattern=r"^SRC-[0-9a-f]{16}$")
    #: The SHA-256 of the file's bytes.
    sha256: str = Field(pattern=_SHA256)
    #: The SHA-256 of its reading when attached; ``None`` when nothing was read.
    reading_sha256: str | None = Field(default=None, pattern=_SHA256)
    filename: str = Field(min_length=1, max_length=400)


@dataclass(frozen=True, slots=True)
class FileForTurn:
    """One file as a turn reads it. ``reading`` is ``None`` when nothing of it can be sent, and
    ``unread`` says why: its reading moved since the person attached it (``reading_changed``),
    or the source or its stored reading is gone (``source_unavailable``)."""

    ref: LeadFileRef
    family: SourceFamily
    #: Marked "Interní dokument" (Class C) when the turn is frozen; else the client's (A).
    internal: bool
    reading: SourceReading | None
    unread: str = "reading_changed"


def _bytes(value: Any) -> int:
    return len(canonical_json(value).encode("utf-8"))


def _locator(locator: Locator) -> dict[str, Any]:
    return locator.model_dump(mode="json", exclude_none=True)


def _outline(reading: SourceReading) -> dict[str, Any]:
    """Every locator of the reading, by range: pages, slides, paragraphs and lines first to
    last, the number of tables, and each sheet's rows first to last."""
    spans: dict[str, list[int]] = {}
    tables: set[tuple[int | None, int]] = set()
    sheets: dict[str, list[int]] = {}
    for segment in reading.segments:
        at = segment.locator
        for key in ("page", "slide", "paragraph", "line"):
            value = getattr(at, key)
            if value is not None:
                span = spans.setdefault(key, [value, value])
                span[0], span[1] = min(span[0], value), max(span[1], value)
        if at.table is not None:
            tables.add((at.page, at.table))
        if at.sheet is not None and at.row is not None:
            rows = sheets.setdefault(at.sheet, [at.row, at.row])
            rows[0], rows[1] = min(rows[0], at.row), max(rows[1], at.row)
    outline: dict[str, Any] = {f"{k}s": v for k, v in spans.items()}
    if tables:
        outline["tables"] = len(tables)
    if sheets:
        outline["sheets"] = [{"name": n, "rows": r} for n, r in sheets.items()]
    outline["segments"] = len(reading.segments)
    return outline


def _preview(entry: dict[str, Any], preview: Mapping[str, Any], room: int) -> None:
    """A dataset's preview within ``room`` bytes: whole columns, sheet by sheet, the rest
    counted (``omitted_columns``, and ``omitted_sheets`` for a sheet none of whose columns fit).
    Measured as it grows, never re-serialised whole."""
    sheets: list[dict[str, Any]] = []
    entry["dataset"] = {"sheets": sheets, "more_sheets": bool(preview.get("more_sheets"))}
    used = _bytes(entry)
    omitted_columns = omitted_sheets = 0
    for sheet in preview.get("sheets") or ():
        columns = list(sheet.get("columns") or ())
        kept: dict[str, Any] = {**sheet, "columns": []}
        shell = _bytes(kept) + (1 if sheets else 0)
        for column in columns:
            cost = _bytes(column) + (1 if kept["columns"] else shell)
            if used + cost > room:
                omitted_columns += 1
                continue
            if not kept["columns"]:
                sheets.append(kept)
            kept["columns"].append(column)
            used += cost
        if not kept["columns"]:
            omitted_sheets += 1
    if omitted_columns:
        entry["omitted_columns"] = omitted_columns
    if omitted_sheets:
        entry["omitted_sheets"] = omitted_sheets


def _cut(locator: dict[str, Any], text: str, room: int) -> dict[str, Any] | None:
    """The longest start of ``text`` whose segment, marked ``cut``, fits ``room`` bytes as JSON
    (an escaped quote or control character counts as sent); ``None`` below the least worth it."""
    if room < _CUT_MIN_BYTES:
        return None
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if _bytes({"at": locator, "text": text[:mid], "cut": True}) <= room:
            low = mid
        else:
            high = mid - 1
    return {"at": locator, "text": text[:low], "cut": True} if low else None


def _segments(entry: dict[str, Any], reading: SourceReading, room: int) -> None:
    """Whole segments in order within ``room`` bytes; a first segment too long for it is cut
    (``cut``); the rest counted, the first left out named (``omitted``). Measured as it grows,
    never re-serialised whole."""
    kept: list[dict[str, Any]] = []
    entry["segments"] = kept
    used = _bytes(entry)
    segments = reading.segments
    for segment in segments:
        at = _locator(segment.locator)
        piece = {"at": at, "text": segment.text}
        cost = _bytes(piece) + (1 if kept else 0)
        if used + cost <= room:
            kept.append(piece)
            used += cost
            continue
        if not kept and (cut := _cut(at, segment.text, room - used)) is not None:
            kept.append(cut)
        break
    if len(kept) < len(segments):
        entry["omitted"] = {
            "segments": len(segments) - len(kept),
            "first": _locator(segments[len(kept)].locator),
        }


def _stub(file: FileForTurn, outcome: str) -> dict[str, Any]:
    """A file named with nothing of it sent, and why."""
    ref = file.ref
    return {
        "source_id": ref.source_id,
        "sha256": ref.sha256,
        "name": ref.filename,
        "family": file.family.value,
        "internal": file.internal,
        "outcome": outcome,
    }


def _entry(file: FileForTurn, room: int) -> dict[str, Any]:
    reading = file.reading
    if reading is None:
        return _stub(file, file.unread)
    entry = _stub(file, reading.outcome.value)
    if reading.reason:
        entry["reason"] = reading.reason
    if reading.notes:
        entry["notes"] = sorted({n.code for n in reading.notes})
    if file.family is SourceFamily.DATASET:
        # A dataset is its preview, never a row (LK5): no segment is sent.
        if reading.dataset is not None:
            _preview(entry, reading.dataset.model_dump(mode="json"), room)
        return entry
    if reading.segments:
        entry["outline"] = _outline(reading)
        _segments(entry, reading, room)
    return entry


def files_layer(
    files: Sequence[FileForTurn], *, budget: int = FILES_MAX_BYTES
) -> dict[str, Any] | None:
    """The ``files`` layer for the files this turn's messages carry: the first
    :data:`FILES_PER_TURN` read, each within an even share of ``budget``; any after them (a turn
    answering several queued messages) named with ``files_bound`` and nothing of them sent.
    ``None`` when they carry none."""
    if not files:
        return None
    read, named = files[:FILES_PER_TURN], files[FILES_PER_TURN:]
    stubs = [_stub(f, "files_bound") for f in named]
    # Each file's share, less what the note, the files named only, and its own count of what was
    # left out take.
    fixed = _bytes({"layer": FILES_LAYER, "note": FILES_NOTE, "files": stubs})
    room = (budget - fixed) // len(read) - _OMITTED_BYTES
    return {"note": FILES_NOTE, "files": [*(_entry(f, room) for f in read), *stubs]}
