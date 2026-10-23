"""A validation Study's holdout records (panel-grounded-respondents 7a, 7e2).

Every method takes an issued ``StudyContext``; the record is found from the Study, never from
anything the caller names. Today it keeps one thing, the Study's **preregistration**: written
once, before the confirmation run's first call, and never changed. The bytes are the record's
canonical JSON, kept as written, and every read re-hashes them and checks them as
:func:`~aia_core.domain.holdout.preregistration.read_preregistration` does, so a row edited
behind AIA's back is refused rather than scored.

Recording the same record again answers the stored one; a different record for a Study that
has one is refused: a preregistration that could be replaced after a look at anything would
pin nothing.

It also keeps the Study's **confirmation**: the run that confirms the preregistered system,
recorded once when it starts (7e3). A respondent system is confirmed once in an organization,
and a database constraint holds that, so two Studies racing to confirm one system cannot both
start.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.holdout.bank import canonical_json
from ..domain.holdout.preregistration import HoldoutRefused, Preregistration, read_preregistration
from ..domain.holdout.scoring import SCORING_VERSION
from ..domain.scope import Permission, ScopeDenied, StudyContext, StudyKind
from .tables import HoldoutConfirmationRow, HoldoutPreregistrationRow, StudyRow, as_utc

__all__ = [
    "HoldoutRepository",
    "StoredConfirmation",
    "StoredPreregistration",
    "erase_client_holdouts",
]


@dataclass(frozen=True, slots=True)
class StoredConfirmation:
    """A Study's confirmation run, as recorded when it started."""

    study_id: str
    run_id: str
    respondent_system_fingerprint: str
    preregistration_sha256: str
    started_by: str
    started_at: datetime


@dataclass(frozen=True, slots=True)
class StoredPreregistration:
    """A Study's preregistration as stored: the record, who fixed it and when."""

    study_id: str
    sha256: str
    respondent_system_fingerprint: str
    population_version: str
    preregistration: Preregistration
    created_by: str
    created_at: datetime


class HoldoutRepository:
    """Reads and writes the holdout records of the research Study in scope."""

    def __init__(self, session: Session, scope: StudyContext) -> None:
        if not isinstance(scope, StudyContext):
            raise TypeError("HoldoutRepository needs an issued StudyContext")
        self._session = session
        self._scope = scope

    def _require_research(self) -> None:
        s = self._scope
        study = self._session.scalar(
            select(StudyRow)
            .where(StudyRow.study_id == s.study_id, StudyRow.client_id == s.client_id)
            .with_for_update()
        )
        if study is None:  # pragma: no cover - an issued scope names an existing study
            raise ScopeDenied("not found", reason="unknown_study")
        if study.kind != StudyKind.RESEARCH.value:
            raise HoldoutRefused(
                "only a research study runs a validation", reason="holdout_not_research"
            )

    def _row(self) -> HoldoutPreregistrationRow | None:
        s = self._scope
        return self._session.scalar(
            select(HoldoutPreregistrationRow).where(
                HoldoutPreregistrationRow.study_id == s.study_id,
                HoldoutPreregistrationRow.client_id == s.client_id,
                HoldoutPreregistrationRow.organization_id == s.organization_id,
            )
        )

    def record_preregistration(self, preregistration: Preregistration) -> StoredPreregistration:
        """Fix the Study's preregistration, once.

        Needs ``EDIT_STUDY`` on an open research Study. The record must read back as written
        and name this code's scoring version (``holdout_scoring_stale`` otherwise). The same
        record again answers the stored one; another is refused
        (``holdout_preregistration_recorded``). The caller commits.
        """
        s = self._scope
        s.require(Permission.EDIT_STUDY)
        s.require_open_study()
        content = canonical_json(preregistration.document)
        checked = read_preregistration(content)
        if checked.document.get("scoring_version") != SCORING_VERSION:
            raise HoldoutRefused(
                "the preregistration names another scoring version than this code's",
                reason="holdout_scoring_stale",
            )
        self._require_research()
        sha256 = hashlib.sha256(content).hexdigest()
        existing = self._row()
        if existing is not None:
            if existing.sha256 != sha256:
                raise HoldoutRefused(
                    "the Study's preregistration is already fixed",
                    reason="holdout_preregistration_recorded",
                )
            return self._to_domain(existing)
        row = HoldoutPreregistrationRow(
            study_id=s.study_id,
            organization_id=s.organization_id,
            client_id=s.client_id,
            sha256=sha256,
            respondent_system_fingerprint=checked.respondent_system_fingerprint,
            population_version=str(checked.document["population_version"]),
            content=content,
            created_by=s.actor_id,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def preregistration(self) -> StoredPreregistration | None:
        """The Study's preregistration, re-hashed and checked, or ``None`` before one is fixed.

        A row whose bytes no longer hash to its recorded hash, or no longer read as a
        preregistration, is refused (``holdout_preregistration_altered``), never returned.
        """
        self._scope.require(Permission.VIEW_STUDY)
        row = self._row()
        return self._to_domain(row) if row is not None else None

    # -- the confirmation -------------------------------------------------------

    def confirmation(self) -> StoredConfirmation | None:
        """The Study's confirmation run, or ``None`` before it starts."""
        self._scope.require(Permission.VIEW_STUDY)
        s = self._scope
        row = self._session.scalar(
            select(HoldoutConfirmationRow).where(
                HoldoutConfirmationRow.study_id == s.study_id,
                HoldoutConfirmationRow.client_id == s.client_id,
                HoldoutConfirmationRow.organization_id == s.organization_id,
            )
        )
        return _confirmation(row) if row is not None else None

    def system_confirmed_elsewhere(self, respondent_system_fingerprint: str) -> bool:
        """Whether another Study of the organization has started confirming this system.

        Says yes or no and nothing else: the other Study is outside this scope.
        """
        s = self._scope
        found = self._session.scalar(
            select(HoldoutConfirmationRow.study_id).where(
                HoldoutConfirmationRow.organization_id == s.organization_id,
                HoldoutConfirmationRow.respondent_system_fingerprint
                == respondent_system_fingerprint,
                HoldoutConfirmationRow.study_id != s.study_id,
            )
        )
        return found is not None

    def record_confirmation(
        self, *, run_id: str, preregistration_sha256: str
    ) -> StoredConfirmation:
        """Record, once, that the Study's confirmation run has started.

        ``preregistration_sha256`` must be the Study's stored preregistration's. A second
        record for the Study, or a confirmation of a system another Study of the organization
        has started confirming, is refused (``holdout_system_confirmation_started``). The
        caller commits, or rolls back the run it created.
        """
        s = self._scope
        s.require(Permission.RUN_WORKFLOW)
        s.require_open_study()
        stored = self.preregistration()
        if stored is None or stored.sha256 != preregistration_sha256:
            raise HoldoutRefused(
                "a confirmation runs the Study's own preregistration",
                reason="holdout_preregistration_missing",
            )
        row = HoldoutConfirmationRow(
            study_id=s.study_id,
            organization_id=s.organization_id,
            client_id=s.client_id,
            respondent_system_fingerprint=stored.respondent_system_fingerprint,
            preregistration_sha256=stored.sha256,
            run_id=run_id,
            started_by=s.actor_id,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError:
            raise HoldoutRefused(
                "this respondent system's confirmation has already started",
                reason="holdout_system_confirmation_started",
            ) from None
        return _confirmation(row)

    @staticmethod
    def _to_domain(row: HoldoutPreregistrationRow) -> StoredPreregistration:
        content = bytes(row.content)
        altered = HoldoutRefused(
            "the stored preregistration is not the one fixed",
            reason="holdout_preregistration_altered",
        )
        if hashlib.sha256(content).hexdigest() != row.sha256:
            raise altered
        try:
            checked = read_preregistration(content)
        except HoldoutRefused:
            raise altered from None
        if (
            checked.respondent_system_fingerprint != row.respondent_system_fingerprint
            or checked.document["population_version"] != row.population_version
        ):
            raise altered
        return StoredPreregistration(
            study_id=row.study_id,
            sha256=row.sha256,
            respondent_system_fingerprint=row.respondent_system_fingerprint,
            population_version=row.population_version,
            preregistration=checked,
            created_by=row.created_by,
            created_at=as_utc(row.created_at),
        )


def _confirmation(row: HoldoutConfirmationRow) -> StoredConfirmation:
    return StoredConfirmation(
        study_id=row.study_id,
        run_id=row.run_id,
        respondent_system_fingerprint=row.respondent_system_fingerprint,
        preregistration_sha256=row.preregistration_sha256,
        started_by=row.started_by,
        started_at=as_utc(row.started_at),
    )


def erase_client_holdouts(session: Session, *, client_id: str) -> None:
    """Delete a deleted client's holdout preregistrations and confirmations (SB5)."""
    session.execute(
        delete(HoldoutConfirmationRow).where(HoldoutConfirmationRow.client_id == client_id)
    )
    session.execute(
        delete(HoldoutPreregistrationRow).where(HoldoutPreregistrationRow.client_id == client_id)
    )
    session.flush()
