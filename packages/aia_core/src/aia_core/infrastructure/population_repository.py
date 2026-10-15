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

**An owned child is its organization's** (population-operations P4c, M5). A version
materialized for one client names its organization, its client and its contract
extension. Every read that answers a person -- :meth:`versions`, :meth:`visible_version`
-- returns the shared versions plus only the asking organization's own, and the lookups
the import uses (:meth:`version_by_sha`, :meth:`version_by_label`) see shared versions
alone. :meth:`get_version` reads any version by id, for the run that recorded it and the
operator's planning, and is not for a person's request (``tools/layer_check.sh``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, or_, select, update
from sqlalchemy.orm import Session

from aia_core.domain.population import (
    CompanionReport,
    CompanionSet,
    CompanionSpec,
    DatasetVersion,
    JointState,
    Population,
    PopulationContractExtension,
    PopulationKind,
    PromotionConflict,
    PromotionRecord,
    VersionIntegrityError,
    VersionOwner,
)
from aia_core.domain.population.materialized import EXTENSION_CONTRACT

from .tables import (
    PopulationCompanionAssetRow,
    PopulationCompanionSetRow,
    PopulationContractExtensionRow,
    PopulationDatasetVersionRow,
    PopulationPromotionRow,
    PopulationRow,
    PopulationVersionAudienceCatalogueRow,
    PopulationVersionDictionaryRow,
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
        owner=(
            VersionOwner(organization_id=row.owner_organization_id, client_id=row.owner_client_id)
            if row.owner_organization_id is not None and row.owner_client_id is not None
            else None
        ),
        extension_sha256=row.extension_sha256,
    )


_SHARED = PopulationDatasetVersionRow.owner_client_id.is_(None)


def _visible_to(organization_id: str | None) -> ColumnElement[bool]:
    """Shared versions, plus the owned ones of ``organization_id`` when it is given."""
    if organization_id is None:
        return _SHARED
    return or_(_SHARED, PopulationDatasetVersionRow.owner_organization_id == organization_id)


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
        """Return one version by id, shared or owned, or ``None``.

        Not for a person's request: the API reads :meth:`visible_version`.
        """
        row = self._session.get(PopulationDatasetVersionRow, version_id)
        return _version(row) if row is not None else None

    def visible_version(self, version_id: str, *, organization_id: str) -> DatasetVersion | None:
        """Return one version as ``organization_id`` sees it: shared, or its own.

        Another organization's child answers ``None``, exactly as an unknown id does.
        """
        row = self._session.scalar(
            select(PopulationDatasetVersionRow).where(
                PopulationDatasetVersionRow.version_id == version_id,
                _visible_to(organization_id),
            )
        )
        return _version(row) if row is not None else None

    def version_by_sha(self, sha256: str) -> DatasetVersion | None:
        """Return the shared version with these bytes, whatever its label."""
        row = self._session.scalar(
            select(PopulationDatasetVersionRow).where(
                PopulationDatasetVersionRow.content_sha256 == sha256, _SHARED
            )
        )
        return _version(row) if row is not None else None

    def version_by_label(self, dataset_id: str, label: str) -> DatasetVersion | None:
        """Return the shared version a dataset's label names, whatever its bytes."""
        row = self._session.scalar(
            select(PopulationDatasetVersionRow).where(
                PopulationDatasetVersionRow.dataset_id == dataset_id,
                PopulationDatasetVersionRow.label == label,
                _SHARED,
            )
        )
        return _version(row) if row is not None else None

    def versions(
        self, dataset_id: str, *, organization_id: str | None = None
    ) -> dict[str, DatasetVersion]:
        """A dataset's shared versions by id, plus ``organization_id``'s own when given.

        Without an organization no owned child is returned: the default never shows one
        organization's version to anyone else.
        """
        rows = self._session.scalars(
            select(PopulationDatasetVersionRow).where(
                PopulationDatasetVersionRow.dataset_id == dataset_id,
                _visible_to(organization_id),
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
                owner_organization_id=version.owner.organization_id if version.owner else None,
                owner_client_id=version.owner.client_id if version.owner else None,
                extension_sha256=version.extension_sha256,
            )
        )
        self._session.flush()

    # ------------------------------------------------------------- extensions --

    def extension(self, sha256: str) -> PopulationContractExtension | None:
        """The stored extension with this hash, re-hashed; ``None`` when there is none.

        A payload that no longer hashes to its key is refused (``VersionIntegrityError``).
        """
        row = self._session.get(PopulationContractExtensionRow, sha256)
        if row is None:
            return None
        extension = PopulationContractExtension.from_payload(dict(row.payload))
        if extension.sha256 != row.extension_sha256:
            raise VersionIntegrityError(
                f"the stored extension {row.extension_sha256} does not hash to its key"
            )
        return extension

    def insert_extension(
        self,
        extension: PopulationContractExtension,
        *,
        recorded_at: datetime,
        recorded_by: str,
    ) -> None:
        """Keep an extension by its hash. Insert-once: a stored one is the same, kept."""
        if self._session.get(PopulationContractExtensionRow, extension.sha256) is not None:
            return
        self._session.add(
            PopulationContractExtensionRow(
                extension_sha256=extension.sha256,
                contract=EXTENSION_CONTRACT,
                payload=extension.payload(),
                recorded_at=recorded_at,
                recorded_by=recorded_by,
            )
        )
        self._session.flush()

    def dictionary(self, version_id: str) -> tuple[str, bytes] | None:
        """The stored dictionary of a version, ``(sha256, bytes)``, or ``None``."""
        row = self._session.get(PopulationVersionDictionaryRow, version_id)
        return None if row is None else (row.sha256, row.content)

    def insert_dictionary(
        self,
        version_id: str,
        *,
        sha256: str,
        content: bytes,
        recorded_at: datetime,
        recorded_by: str,
    ) -> None:
        """Keep a version's dictionary bytes. Insert-once; there is no update."""
        self._session.add(
            PopulationVersionDictionaryRow(
                version_id=version_id,
                sha256=sha256,
                byte_size=len(content),
                content=content,
                recorded_at=recorded_at,
                recorded_by=recorded_by,
            )
        )
        self._session.flush()

    def audience_catalogue(self, version_id: str, catalogue_version: str) -> tuple[str, str] | None:
        """The kept audience catalogue of a version, ``(sha256, json)``, or ``None``."""
        row = self._session.get(
            PopulationVersionAudienceCatalogueRow, (version_id, catalogue_version)
        )
        return None if row is None else (row.sha256, row.content)

    def insert_audience_catalogue(
        self,
        version_id: str,
        *,
        catalogue_version: str,
        sha256: str,
        content: str,
        recorded_at: datetime,
        recorded_by: str,
    ) -> None:
        """Keep a version's audience catalogue. Insert-once; there is no update."""
        self._session.add(
            PopulationVersionAudienceCatalogueRow(
                version_id=version_id,
                catalogue_version=catalogue_version,
                sha256=sha256,
                content=content,
                recorded_at=recorded_at,
                recorded_by=recorded_by,
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

    # ------------------------------------------------------------- companions --

    def companion_set(self, version_id: str) -> CompanionSet | None:
        """The companion set attached to a version, or ``None``."""
        row = self._session.get(PopulationCompanionSetRow, version_id)
        if row is None:
            return None
        assets = self._session.scalars(
            select(PopulationCompanionAssetRow).where(
                PopulationCompanionAssetRow.version_id == version_id
            )
        )
        return CompanionSet(
            version_id=row.version_id,
            set_sha256=row.set_sha256,
            joint_state=JointState(row.joint_state),
            assets={a.asset_id: (a.sha256, a.location) for a in assets},
            attached_at=as_utc(row.attached_at),
            attached_by=row.attached_by,
        )

    def companion_report(self, version_id: str) -> dict[str, Any] | None:
        """The report a companion set was accepted on."""
        row = self._session.get(PopulationCompanionSetRow, version_id)
        return dict(row.report_json) if row is not None else None

    def insert_companion_set(
        self,
        version_id: str,
        *,
        specs: Sequence[CompanionSpec],
        report: CompanionReport,
        locations: Mapping[str, str],
        attached_by: str,
        attached_at: datetime,
    ) -> None:
        """Record a validated companion set. Insert-once: a second set is refused by key."""
        self._session.add(
            PopulationCompanionSetRow(
                version_id=version_id,
                set_sha256=report.set_sha256,
                joint_state=report.joint.state.value,
                report_json=report.as_record(),
                attached_at=attached_at,
                attached_by=attached_by,
            )
        )
        self._session.flush()
        for spec in specs:
            self._session.add(
                PopulationCompanionAssetRow(
                    version_id=version_id,
                    asset_id=spec.asset_id,
                    kind=spec.kind.value,
                    sha256=report.hashes[spec.asset_id],
                    byte_size=spec.byte_size,
                    location=locations[spec.asset_id],
                )
            )
        self._session.flush()

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
