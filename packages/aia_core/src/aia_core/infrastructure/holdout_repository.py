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

And it keeps the Study's **validation** (7f): the verdict its confirmation run computed, as a
person recorded it, once. A recorded ``PASS`` is the respondent system's ``HOLDOUT_VALIDATED``
state for the organization, read by :meth:`HoldoutRepository.current_validation`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.evidence.validation import ValidationState, ValidationStatus, ValidationTruth
from ..domain.holdout.bank import canonical_json
from ..domain.holdout.preregistration import HoldoutRefused, Preregistration, read_preregistration
from ..domain.holdout.scoring import SCORING_VERSION
from ..domain.scope import Permission, ScopeDenied, StudyContext, StudyKind
from .tables import (
    HoldoutConfirmationRow,
    HoldoutPreregistrationRow,
    RespondentValidationRow,
    StudyRow,
    as_utc,
)

__all__ = [
    "HoldoutRepository",
    "StoredConfirmation",
    "StoredPreregistration",
    "StoredValidation",
]

_STATUS_OF: dict[str, ValidationStatus] = {
    "PASS": ValidationStatus.HOLDOUT_VALIDATED,
    "FAIL": ValidationStatus.NOT_VALIDATED,
}


@dataclass(frozen=True, slots=True)
class StoredValidation:
    """A Study's recorded validation: the verdict copied from its run, who recorded it, when."""

    study_id: str
    run_id: str
    respondent_system_fingerprint: str
    verdict: str
    truth: ValidationTruth
    preregistration_sha256: str
    verdict_artifact_id: str
    verdict_sha256: str
    recorded_by: str
    recorded_at: datetime

    @property
    def state(self) -> ValidationState:
        """The system's validation state this record is: its status, system and evidence."""
        return ValidationState(
            status=_STATUS_OF[self.verdict],
            system_fingerprint=self.respondent_system_fingerprint,
            validated_at=self.recorded_at,
            truth=self.truth,
            preregistration_sha256=self.preregistration_sha256,
            verdict_sha256=self.verdict_sha256,
        )


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

    # -- the validation ---------------------------------------------------------

    def validation(self) -> StoredValidation | None:
        """The Study's recorded validation, or ``None`` before a person records it."""
        self._scope.require(Permission.VIEW_STUDY)
        s = self._scope
        row = self._session.scalar(
            select(RespondentValidationRow).where(
                RespondentValidationRow.study_id == s.study_id,
                RespondentValidationRow.client_id == s.client_id,
                RespondentValidationRow.organization_id == s.organization_id,
            )
        )
        return _validation(row) if row is not None else None

    def record_validation(
        self,
        *,
        verdict: str,
        truth: ValidationTruth,
        verdict_artifact_id: str,
        verdict_sha256: str,
    ) -> StoredValidation:
        """Record, once, the verdict the Study's confirmation run computed.

        The caller (:meth:`~aia_core.application.validation.ValidationRuns.record`) has read
        ``verdict`` from the run's verdict artifact; nothing here chooses it. The run, the
        system and the preregistration are the Study's confirmation's. Needs ``APPROVE_GATE``
        on an open Study. A second record is refused (``holdout_validation_recorded``). The
        caller commits.
        """
        s = self._scope
        s.require(Permission.APPROVE_GATE)
        s.require_open_study()
        if verdict not in _STATUS_OF:
            raise ValueError(f"a verdict is PASS or FAIL, not {verdict!r}")
        confirmation = self.confirmation()
        if confirmation is None:
            raise HoldoutRefused(
                "the Study has no confirmation run to record", reason="holdout_not_confirmed"
            )
        if self.validation() is not None:
            raise HoldoutRefused(
                "the Study's validation is already recorded", reason="holdout_validation_recorded"
            )
        row = RespondentValidationRow(
            study_id=s.study_id,
            organization_id=s.organization_id,
            client_id=s.client_id,
            run_id=confirmation.run_id,
            respondent_system_fingerprint=confirmation.respondent_system_fingerprint,
            verdict=verdict,
            status=_STATUS_OF[verdict].value,
            truth=truth.value,
            preregistration_sha256=confirmation.preregistration_sha256,
            verdict_artifact_id=verdict_artifact_id,
            verdict_sha256=verdict_sha256,
            recorded_by=s.actor_id,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError:
            raise HoldoutRefused(
                "the Study's validation is already recorded", reason="holdout_validation_recorded"
            ) from None
        return _validation(row)

    def current_validation(self, respondent_system_fingerprint: str) -> ValidationState | None:
        """The organization's recorded validation of this respondent system, or ``None``.

        A system is confirmed once in an organization, so at most one Study holds it. Read by
        any member: what it says is the system's state, not the validation Study's content.
        """
        s = self._scope
        s.require(Permission.VIEW_STUDY)
        row = self._session.scalar(
            select(RespondentValidationRow).where(
                RespondentValidationRow.organization_id == s.organization_id,
                RespondentValidationRow.respondent_system_fingerprint
                == respondent_system_fingerprint,
            )
        )
        return _validation(row).state if row is not None else None

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


def _validation(row: RespondentValidationRow) -> StoredValidation:
    return StoredValidation(
        study_id=row.study_id,
        run_id=row.run_id,
        respondent_system_fingerprint=row.respondent_system_fingerprint,
        verdict=row.verdict,
        truth=ValidationTruth(row.truth),
        preregistration_sha256=row.preregistration_sha256,
        verdict_artifact_id=row.verdict_artifact_id,
        verdict_sha256=row.verdict_sha256,
        recorded_by=row.recorded_by,
        recorded_at=as_utc(row.recorded_at),
    )
