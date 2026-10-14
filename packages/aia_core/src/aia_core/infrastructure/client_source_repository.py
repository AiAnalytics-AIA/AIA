"""Persistence for a client's sources (lifecycle K2a).

The only module that reads or writes ``client_sources`` and
``client_source_occurrences`` (`make layer_check`). Every call takes an issued
``ClientContext`` and the client is in the query itself, so a source of another client
is not found (``ScopeDenied``), never filtered out afterwards.

The original and its reading are objects in the artifact store under the client's
prefix -- ``org/<org>/client/<client>/sources/<sha256>/...`` -- so a client-wide
deletion stays one prefix operation, as every artifact's key is laid out
(``storage.build_storage_key``). Each is read back against the hash this table keeps.
Adding the same bytes again keeps one source and records another occurrence.

Reading the sources needs ``VIEW_CLIENT_KNOWLEDGE``; adding one needs
``PROPOSE_CLIENT_KNOWLEDGE``: it brings material, and accepts nothing.
"""

from __future__ import annotations

from typing import Final

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.attachments import extension_of
from ..domain.client_sources import (
    SOURCE_MAX_BYTES,
    ReadingOutcome,
    SourceFamily,
    SourceOccurrence,
    SourceOrigin,
    SourceReading,
    SourceRecord,
    SourceRejected,
    display_name,
    family_of,
    media_type_of,
    new_occurrence_id,
    new_source_id,
)
from ..domain.scope import ClientContext, ClientPermission, ScopeDenied
from .source_reading import READERS, read_source
from .storage import ArtifactStore, sha256_bytes
from .tables import (
    AccessAuditRow,
    ClientSourceOccurrenceRow,
    ClientSourceRow,
    as_utc,
    utcnow,
)

__all__ = ["ClientSourceRepository"]

#: How many sources one listing returns at most, newest first.
LIST_LIMIT: Final = 500


def _client(scope: object) -> ClientContext:
    if not isinstance(scope, ClientContext):
        raise ScopeDenied("a client's sources require a client context", reason="forged_scope")
    return scope


def _prefix(scope: ClientContext, sha256: str) -> str:
    return f"org/{scope.organization_id}/client/{scope.client_id}/sources/{sha256}"


class ClientSourceRepository:
    """Adds and reads one client's sources. The caller owns the transaction."""

    def __init__(self, session: Session, store: ArtifactStore) -> None:
        self._session = session
        self._store = store

    # ------------------------------------------------------------------ reading

    def _rows(
        self, scope: ClientContext, source_ids: list[str] | None = None
    ) -> list[ClientSourceRow]:
        query = select(ClientSourceRow).where(
            ClientSourceRow.organization_id == scope.organization_id,
            ClientSourceRow.client_id == scope.client_id,
        )
        if source_ids is not None:
            query = query.where(ClientSourceRow.source_id.in_(source_ids))
        return list(self._session.scalars(query).all())

    def _row(self, scope: ClientContext, source_id: str) -> ClientSourceRow:
        rows = self._rows(scope, [source_id])
        if not rows:
            raise ScopeDenied("not found", reason="unknown_source")
        return rows[0]

    def _records(self, rows: list[ClientSourceRow]) -> list[SourceRecord]:
        if not rows:
            return []
        occurrences: dict[str, list[SourceOccurrence]] = {r.source_id: [] for r in rows}
        found = self._session.scalars(
            select(ClientSourceOccurrenceRow)
            .where(ClientSourceOccurrenceRow.source_id.in_(list(occurrences)))
            .order_by(ClientSourceOccurrenceRow.added_at.desc())
        ).all()
        for o in found:
            occurrences[o.source_id].append(
                SourceOccurrence(
                    occurrence_id=o.occurrence_id,
                    source_id=o.source_id,
                    filename=o.filename,
                    origin=SourceOrigin(o.origin),
                    added_by=o.added_by,
                    added_at=as_utc(o.added_at),
                )
            )
        records = [
            SourceRecord(
                source_id=r.source_id,
                client_id=r.client_id,
                sha256=r.sha256,
                size_bytes=r.size_bytes,
                media_type=r.media_type,
                family=SourceFamily(r.family),
                # The name it was last added under; every name is in its occurrences.
                filename=occurrences[r.source_id][0].filename if occurrences[r.source_id] else "",
                outcome=ReadingOutcome(r.outcome),
                reason=r.reason,
                reader=r.reader,
                characters=r.characters,
                segments=r.segment_count,
                occurrences=tuple(occurrences[r.source_id]),
                created_at=as_utc(r.created_at),
            )
            for r in rows
        ]

        def newest(record: SourceRecord) -> float:
            at = record.occurrences[0].added_at if record.occurrences else record.created_at
            return at.timestamp() if at else 0.0

        return sorted(records, key=newest, reverse=True)

    def sources(self, scope: ClientContext) -> list[SourceRecord]:
        """The client's sources, the most recently added first."""
        scope = _client(scope)
        scope.require(ClientPermission.VIEW_CLIENT_KNOWLEDGE)
        return self._records(self._rows(scope))[:LIST_LIMIT]

    def source(self, scope: ClientContext, source_id: str) -> SourceRecord:
        scope = _client(scope)
        scope.require(ClientPermission.VIEW_CLIENT_KNOWLEDGE)
        return self._records([self._row(scope, source_id)])[0]

    def reading(self, scope: ClientContext, source_id: str) -> SourceReading:
        """What reading the source produced, its segments verified against the kept hash."""
        scope = _client(scope)
        scope.require(ClientPermission.VIEW_CLIENT_KNOWLEDGE)
        row = self._row(scope, source_id)
        if row.reading_key is None:
            # Nothing was read: the row says all there is.
            return SourceReading(outcome=ReadingOutcome(row.outcome), reason=row.reason)
        data = self._store.get(row.reading_key, expected_sha256=row.reading_sha256)
        return SourceReading.model_validate_json(data)

    def original(self, scope: ClientContext, source_id: str) -> tuple[str, bytes]:
        """The original's bytes, verified, and the name it was last added under."""
        record = self.source(scope, source_id)
        row = self._row(scope, source_id)
        return record.filename, self._store.get(row.storage_key, expected_sha256=row.sha256)

    # ------------------------------------------------------------------- adding

    def add(
        self,
        scope: ClientContext,
        *,
        filename: str,
        data: bytes,
        origin: SourceOrigin = SourceOrigin.UPLOAD,
    ) -> tuple[SourceRecord, bool]:
        """Keep a source, or record another occurrence of one kept; ``True`` when new.

        Refused before anything is stored (``SourceRejected``): an empty file
        (``empty``), one over ``SOURCE_MAX_BYTES`` (``too_large``), and a format
        outside the owner's list (``unsupported_format``).
        """
        scope = _client(scope)
        scope.require(ClientPermission.PROPOSE_CLIENT_KNOWLEDGE)
        name = display_name(filename)
        if not data:
            raise SourceRejected("the file is empty", reason="empty")
        if len(data) > SOURCE_MAX_BYTES:
            raise SourceRejected(
                f"the file is larger than {SOURCE_MAX_BYTES // (1024 * 1024)} MiB",
                reason="too_large",
            )
        family = family_of(name)
        if family is SourceFamily.UNKNOWN:
            raise SourceRejected(f"AIA does not take {name!r}", reason="unsupported_format")
        sha256 = sha256_bytes(data)

        existing = self._rows_by_sha(scope, sha256)
        created = False
        if existing is None:
            kept = self._keep(scope, name=name, data=data, sha256=sha256, family=family)
            if kept is None:  # another request kept the same bytes first
                existing = self._rows_by_sha(scope, sha256)
                if existing is None:
                    raise RuntimeError("a source refused as a duplicate is not there")
            else:
                existing, created = kept, True
        if not created:
            # The same bytes again: read them again if a newer reader has come (OI-110).
            self._reread(scope, existing)
        occurrence = ClientSourceOccurrenceRow(
            occurrence_id=new_occurrence_id(),
            source_id=existing.source_id,
            organization_id=scope.organization_id,
            client_id=scope.client_id,
            filename=name,
            origin=origin.value,
            added_by=scope.actor_id,
            added_at=utcnow(),
        )
        self._session.add(occurrence)
        self._session.add(
            AccessAuditRow(
                organization_id=scope.organization_id,
                client_id=scope.client_id,
                actor_id=scope.actor_id,
                action="CLIENT_SOURCE_ADDED",
                reason="",
                payload={
                    "source_id": existing.source_id,
                    "occurrence_id": occurrence.occurrence_id,
                    "filename": name,
                    "sha256": sha256,
                    "new": created,
                    "outcome": existing.outcome,
                },
                request_id=scope.request_id,
            )
        )
        self._session.flush()
        return self._records([existing])[0], created

    def _rows_by_sha(self, scope: ClientContext, sha256: str) -> ClientSourceRow | None:
        return self._session.scalar(
            select(ClientSourceRow).where(
                ClientSourceRow.organization_id == scope.organization_id,
                ClientSourceRow.client_id == scope.client_id,
                ClientSourceRow.sha256 == sha256,
            )
        )

    def _keep(
        self, scope: ClientContext, *, name: str, data: bytes, sha256: str, family: SourceFamily
    ) -> ClientSourceRow | None:
        """Store the original and its reading, then the row; ``None`` if another won."""
        prefix = _prefix(scope, sha256)
        media_type = media_type_of(name)
        # The objects go first: a crash between them and the row leaves an object no
        # row trusts (reaped later), never a row pointing at nothing.
        self._store.put(f"{prefix}/original", data, content_type=media_type)
        reading = read_source(data, name)
        reading_key, reading_sha = self._put_reading(prefix, reading)
        row = ClientSourceRow(
            source_id=new_source_id(),
            organization_id=scope.organization_id,
            client_id=scope.client_id,
            sha256=sha256,
            size_bytes=len(data),
            media_type=media_type,
            family=family.value,
            storage_key=f"{prefix}/original",
            reading_key=reading_key,
            reading_sha256=reading_sha,
            outcome=reading.outcome.value,
            reason=reading.reason,
            reader=reading.reader,
            characters=reading.characters,
            segment_count=len(reading.segments),
            created_by=scope.actor_id,
            created_at=utcnow(),
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
        except IntegrityError:
            return None
        return row

    def _put_reading(self, prefix: str, reading: SourceReading) -> tuple[str | None, str | None]:
        """Store a reading beside the original, under its reader's name; nothing if empty."""
        if not (reading.segments or reading.notes):
            return None, None
        body = reading.model_dump_json().encode()
        key = f"{prefix}/reading-{(reading.reader or 'none').replace('/', '-')}.json"
        return key, self._store.put(key, body, content_type="application/json").sha256

    # ------------------------------------------------------------------ re-reading

    def _kept_name(self, row: ClientSourceRow) -> str:
        """The name the source was first kept under: its format is the one it was read as."""
        first = self._session.scalar(
            select(ClientSourceOccurrenceRow.filename)
            .where(ClientSourceOccurrenceRow.source_id == row.source_id)
            .order_by(ClientSourceOccurrenceRow.added_at, ClientSourceOccurrenceRow.occurrence_id)
            .limit(1)
        )
        return first or ""

    def _reread(self, scope: ClientContext, row: ClientSourceRow) -> bool:
        """Read the kept original again when its format's reader is not the one that read it.

        The original never changes; the new reading is stored beside the old one (the
        reader is in its key), and the row moves to it. ``False`` when there is nothing
        newer to read it with.
        """
        name = self._kept_name(row)
        current = READERS.get(extension_of(name))
        if current is None or current == row.reader:
            return False
        data = self._store.get(row.storage_key, expected_sha256=row.sha256)
        reading = read_source(data, name)
        before = row.reader
        reading_key, reading_sha = self._put_reading(_prefix(scope, row.sha256), reading)
        row.reading_key, row.reading_sha256 = reading_key, reading_sha
        row.outcome, row.reason, row.reader = reading.outcome.value, reading.reason, reading.reader
        row.characters, row.segment_count = reading.characters, len(reading.segments)
        self._session.add(
            AccessAuditRow(
                organization_id=scope.organization_id,
                client_id=scope.client_id,
                actor_id=scope.actor_id,
                action="CLIENT_SOURCE_REREAD",
                reason="",
                payload={
                    "source_id": row.source_id,
                    "from_reader": before,
                    "to_reader": reading.reader,
                    "outcome": row.outcome,
                },
                request_id=scope.request_id,
            )
        )
        self._session.flush()
        return True

    def reread(self, scope: ClientContext, source_id: str) -> tuple[SourceRecord, bool]:
        """Read a source again with its format's current reader; ``True`` when it was.

        Needs ``PROPOSE_CLIENT_KNOWLEDGE``, as adding does. A source already read by the
        current reader is left as it is.
        """
        scope = _client(scope)
        scope.require(ClientPermission.PROPOSE_CLIENT_KNOWLEDGE)
        row = self._row(scope, source_id)
        changed = self._reread(scope, row)
        return self._records([row])[0], changed
