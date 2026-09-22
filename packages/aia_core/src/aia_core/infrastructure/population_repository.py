"""Persistence for the population registry: versions, populations, history.

Holds the rules' results; decides nothing. Every establish and promote is planned
by ``aia_core.domain.population.versions`` and orchestrated by
``aia_core.application.population``. What this layer adds is what only the database
can guarantee:

* versions are **insert-only** -- there is no update method, and the unique keys on
  ``content_sha256`` and ``(dataset_id, label)`` make a second copy or a re-pointed
  label a constraint violation rather than a convention;
* promotion is a **compare-and-set** ``UPDATE ... WHERE current_version_id = :from``,
  so two concurrent promotions cannot both succeed even when both passed the
  domain check against the same snapshot;
* a STATIC population's pointer is never written after establishment -- the update
  statement is restricted to ``kind = 'LIVE'``.

Platform reference data: not study-scoped, so no scope context is taken. Which
population a *run* used is study-scoped and lives with the run
(``WorkflowRepository``).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from aia_core.domain.population import (
    DatasetVersion,
    Population,
    PopulationKind,
    PromotionConflict,
    PromotionRecord,
)

from .tables import (
    PopulationDatasetVersionRow,
    PopulationPromotionRow,
    PopulationRow,
    as_utc,
)

__all__ = ["PopulationRegistryRepository"]


def _version(row: PopulationDatasetVersionRow) -> DatasetVersion:
    return DatasetVersion(
        version_id=row.version_id,
        dataset_id=row.dataset_id,
        label=row.label,
        content_sha256=row.content_sha256,
        byte_size=row.byte_size,
        row_count=row.row_count,
        column_count=row.column_count,
        contract_id=row.contract_id,
        dictionary_sha256=row.dictionary_sha256,
        field_names_sha256=row.field_names_sha256,
        parent_version_id=row.parent_version_id,
        storage_location=row.storage_location,
        dictionary_location=row.dictionary_location,
        provenance=row.provenance,
        imported_at=as_utc(row.imported_at),
        imported_by=row.imported_by,
    )


def _population(row: PopulationRow) -> Population:
    return Population(
        population_id=row.population_id,
        dataset_id=row.dataset_id,
        kind=PopulationKind(row.kind),
        current_version_id=row.current_version_id,
        established_at=as_utc(row.established_at),
        established_by=row.established_by,
    )


def _promotion(row: PopulationPromotionRow) -> PromotionRecord:
    return PromotionRecord(
        promotion_id=row.promotion_id,
        population_id=row.population_id,
        from_version_id=row.from_version_id,
        to_version_id=row.to_version_id,
        actor_id=row.actor_id,
        reason=row.reason,
        promoted_at=as_utc(row.promoted_at),
    )


class PopulationRegistryRepository:
    """Reads and append-only writes over the population registry tables."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --------------------------------------------------------------- versions --

    def get_version(self, version_id: str) -> DatasetVersion | None:
        """Return one version, or ``None``."""
        row = self._session.get(PopulationDatasetVersionRow, version_id)
        return _version(row) if row is not None else None

    def version_by_sha(self, sha256: str) -> DatasetVersion | None:
        """Return the version with these bytes, whatever its label."""
        row = self._session.scalar(
            select(PopulationDatasetVersionRow).where(
                PopulationDatasetVersionRow.content_sha256 == sha256
            )
        )
        return _version(row) if row is not None else None

    def version_by_label(self, dataset_id: str, label: str) -> DatasetVersion | None:
        """Return the version a dataset's label names, whatever its bytes."""
        row = self._session.scalar(
            select(PopulationDatasetVersionRow).where(
                PopulationDatasetVersionRow.dataset_id == dataset_id,
                PopulationDatasetVersionRow.label == label,
            )
        )
        return _version(row) if row is not None else None

    def versions(self, dataset_id: str) -> dict[str, DatasetVersion]:
        """Every version of a dataset, by id."""
        rows = self._session.scalars(
            select(PopulationDatasetVersionRow).where(
                PopulationDatasetVersionRow.dataset_id == dataset_id
            )
        )
        return {row.version_id: _version(row) for row in rows}

    def validation_record(self, version_id: str) -> dict[str, Any] | None:
        """The import report a version was accepted on."""
        row = self._session.get(PopulationDatasetVersionRow, version_id)
        return dict(row.validation_json) if row is not None else None

    def insert_version(self, version: DatasetVersion, *, validation: dict[str, Any]) -> None:
        """Register a validated version. Insert-only; there is no update."""
        self._session.add(
            PopulationDatasetVersionRow(
                version_id=version.version_id,
                dataset_id=version.dataset_id,
                label=version.label,
                content_sha256=version.content_sha256,
                byte_size=version.byte_size,
                row_count=version.row_count,
                column_count=version.column_count,
                contract_id=version.contract_id,
                dictionary_sha256=version.dictionary_sha256,
                field_names_sha256=version.field_names_sha256,
                parent_version_id=version.parent_version_id,
                storage_location=version.storage_location,
                dictionary_location=version.dictionary_location,
                provenance=version.provenance,
                validation_json=validation,
                imported_at=version.imported_at,
                imported_by=version.imported_by,
            )
        )
        self._session.flush()

    # ------------------------------------------------------------ populations --

    def populations(self, dataset_id: str) -> list[Population]:
        """Every population of a dataset."""
        rows = self._session.scalars(
            select(PopulationRow)
            .where(PopulationRow.dataset_id == dataset_id)
            .order_by(PopulationRow.population_id)
        )
        return [_population(row) for row in rows]

    def population(self, population_id: str, *, for_update: bool = False) -> Population | None:
        """Return one population, optionally locking its row (PostgreSQL)."""
        statement = select(PopulationRow).where(PopulationRow.population_id == population_id)
        if for_update:
            statement = statement.with_for_update()
        row = self._session.scalar(statement)
        return _population(row) if row is not None else None

    def promotions(self, dataset_id: str) -> list[PromotionRecord]:
        """The establish/promote history of a dataset's populations, oldest first.

        Entries with the same ``promoted_at`` are ordered by id: deterministic, not
        chronological. Nothing derives meaning from that order -- version status is
        set membership -- and LIVE promotions are serialised by compare-and-set.
        """
        rows = self._session.scalars(
            select(PopulationPromotionRow)
            .join(
                PopulationRow, PopulationRow.population_id == PopulationPromotionRow.population_id
            )
            .where(PopulationRow.dataset_id == dataset_id)
            .order_by(PopulationPromotionRow.promoted_at, PopulationPromotionRow.promotion_id)
        )
        return [_promotion(row) for row in rows]

    def insert_population(self, population: Population, record: PromotionRecord) -> None:
        """Create a population and its establishing history entry."""
        self._session.add(
            PopulationRow(
                population_id=population.population_id,
                dataset_id=population.dataset_id,
                kind=population.kind.value,
                current_version_id=population.current_version_id,
                established_at=population.established_at,
                established_by=population.established_by,
            )
        )
        self._session.flush()
        self._add_record(record)

    def apply_promotion(self, promoted: Population, record: PromotionRecord) -> None:
        """Move a LIVE pointer from ``record.from_version_id``, or raise.

        The ``WHERE`` clause is the compare-and-set. Zero rows updated means the
        pointer moved since the caller read it -- or the population is STATIC,
        which the statement can never touch.
        """
        result = self._session.execute(
            update(PopulationRow)
            .where(
                PopulationRow.population_id == promoted.population_id,
                PopulationRow.kind == PopulationKind.LIVE.value,
                PopulationRow.current_version_id == record.from_version_id,
            )
            .values(current_version_id=promoted.current_version_id)
        )
        if getattr(result, "rowcount", 0) != 1:
            raise PromotionConflict(
                f"{promoted.population_id} is no longer at {record.from_version_id}"
            )
        self._add_record(record)

    def _add_record(self, record: PromotionRecord) -> None:
        self._session.add(
            PopulationPromotionRow(
                promotion_id=record.promotion_id,
                population_id=record.population_id,
                from_version_id=record.from_version_id,
                to_version_id=record.to_version_id,
                actor_id=record.actor_id,
                reason=record.reason,
                promoted_at=record.promoted_at,
            )
        )
        self._session.flush()
