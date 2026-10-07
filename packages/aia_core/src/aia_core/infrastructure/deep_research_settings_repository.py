"""Deep Research settings as data: the only reader and writer of their tables (ADR 0022).

Two faces, deliberately separate, as ADR 0020's prompt store:

* :class:`DeepResearchSettingsReader` reads: the catalogue with what is in force, a setting's
  versions and its approval history. Any member of the organization may read -- these are
  policy values, not research data -- through an issued
  :class:`~aia_core.domain.scope.OrganizationContext`, which carries no client or study.
  :meth:`~DeepResearchSettingsReader.effective` is what a run will pin at enqueue (chunk 43).
* :class:`DeepResearchSettingsRepository` writes, and refuses anyone who may not administer
  the organization: propose a value (a new immutable version), approve a version, or withdraw
  an approval (back to the code's proposed default). Every change writes an
  ``access_audit`` row in its own transaction.

Rules this module keeps:

* Only a catalogued setting is stored, and only a value the catalogue validates
  (``domain.deep_research.settings``). A value is never repaired or truncated.
* A version is immutable; approval is append-only, newest row wins, ``NULL`` the default.
* Review follows the organization's self-approval setting (ADR 0019): with it off, whoever
  proposed a version does not approve it unless somebody else already approved that exact
  version. Withdrawing to the default is always allowed.

``make layer_check`` keeps the rows inside this module.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aia_core.domain.ai_contracts import canonical_json
from aia_core.domain.deep_research.settings import (
    CATALOGUE,
    ApprovedValue,
    Effective,
    EffectiveSettings,
    SettingDefinition,
    SettingInvalid,
    SettingValue,
    definition,
    effective,
    validate_value,
)
from aia_core.domain.scope import (
    OrganizationContext,
    SelfApprovalPolicy,
    resolve_self_approval_policy,
)

from .tables import (
    AccessAuditRow,
    DeepResearchSettingApprovalRow,
    DeepResearchSettingVersionRow,
    OrganizationRow,
    as_utc,
)

__all__ = [
    "DeepResearchSettingsReader",
    "DeepResearchSettingsRepository",
    "SettingApproval",
    "SettingOverview",
    "SettingRefused",
    "StoredSettingVersion",
]

_MAX_SOURCE_URL = 500
_MAX_NOTE = 255


class SettingRefused(Exception):
    """A request the store will not honour. ``reason`` is a stable machine word."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class StoredSettingVersion:
    key: str
    version_number: int
    value: SettingValue
    value_sha256: str
    source_url: str
    note: str
    created_by: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SettingApproval:
    """One row of the approval log. ``version_number`` None: back to the code's default."""

    approval_id: int
    key: str
    version_number: int | None
    approved_by: str
    reason: str
    approved_at: datetime


@dataclass(frozen=True, slots=True)
class SettingOverview:
    definition: SettingDefinition
    effective: Effective
    version_count: int
    latest_number: int | None


def _stored(value: SettingValue) -> dict[str, Any]:
    return {"value": list(value) if isinstance(value, tuple) else value}


def _sha256(value: SettingValue) -> str:
    return hashlib.sha256(canonical_json(_stored(value)).encode("utf-8")).hexdigest()


def _version(row: DeepResearchSettingVersionRow) -> StoredSettingVersion:
    # Read back through the catalogue: the normal form (a tuple for a list), and a value
    # the catalogue no longer admits fails here rather than travelling on.
    value = validate_value(definition(row.setting_key), row.value["value"], bound_by_default=False)
    return StoredSettingVersion(
        key=row.setting_key,
        version_number=row.version_number,
        value=value,
        value_sha256=row.value_sha256,
        source_url=row.source_url,
        note=row.note,
        created_by=row.created_by,
        created_at=as_utc(row.created_at),
    )


def _newest_approvals(session: Session, org: str) -> dict[str, DeepResearchSettingApprovalRow]:
    newest = (
        select(
            DeepResearchSettingApprovalRow.setting_key,
            func.max(DeepResearchSettingApprovalRow.approval_id).label("approval_id"),
        )
        .where(DeepResearchSettingApprovalRow.organization_id == org)
        .group_by(DeepResearchSettingApprovalRow.setting_key)
        .subquery()
    )
    rows = session.scalars(
        select(DeepResearchSettingApprovalRow).join(
            newest, DeepResearchSettingApprovalRow.approval_id == newest.c.approval_id
        )
    )
    return {r.setting_key: r for r in rows}


def _version_row(
    session: Session, org: str, key: str, number: int
) -> DeepResearchSettingVersionRow | None:
    return session.scalar(
        select(DeepResearchSettingVersionRow).where(
            DeepResearchSettingVersionRow.organization_id == org,
            DeepResearchSettingVersionRow.setting_key == key,
            DeepResearchSettingVersionRow.version_number == number,
        )
    )


def _in_force(session: Session, org: str) -> EffectiveSettings:
    approved: dict[str, ApprovedValue] = {}
    for key, approval in _newest_approvals(session, org).items():
        if approval.version_number is None:
            continue  # withdrawn: the code's default
        row = _version_row(session, org, key, approval.version_number)
        if row is None:  # pragma: no cover - the foreign key forbids it
            raise SettingRefused("an approval names no version", reason="store_inconsistent")
        approved[key] = ApprovedValue(
            value=row.value["value"],
            version=approval.version_number,
            approved_by=approval.approved_by,
            approved_at=as_utc(approval.approved_at),
        )
    try:
        return effective(approved)
    except SettingInvalid as exc:
        raise SettingRefused(
            f"an approved value is no longer valid ({exc}); approve a valid one or withdraw it",
            reason="approved_value_invalid",
        ) from exc


def _definition(key: str) -> SettingDefinition:
    try:
        return definition(key)
    except SettingInvalid as exc:
        raise SettingRefused(str(exc), reason="unknown_setting") from exc


class DeepResearchSettingsReader:
    """The organization's Deep Research settings, read by any of its members."""

    def __init__(self, session: Session, reader: OrganizationContext) -> None:
        self._session = session
        self._org = reader.organization_id

    def effective(self) -> EffectiveSettings:
        """What is in force now: what a run enqueued now would pin."""
        return _in_force(self._session, self._org)

    def overview(self) -> list[SettingOverview]:
        """Every catalogued setting, what is in force, and how many versions it has."""
        counts = {
            key: (int(count), latest)
            for key, count, latest in self._session.execute(
                select(
                    DeepResearchSettingVersionRow.setting_key,
                    func.count(),
                    func.max(DeepResearchSettingVersionRow.version_number),
                )
                .where(DeepResearchSettingVersionRow.organization_id == self._org)
                .group_by(DeepResearchSettingVersionRow.setting_key)
            )
        }
        in_force = self.effective()
        return [
            SettingOverview(defn, in_force[defn.key], *counts.get(defn.key, (0, None)))
            for defn in CATALOGUE
        ]

    def versions(self, key: str) -> list[StoredSettingVersion]:
        """Every proposed value of a setting, newest first."""
        _definition(key)
        rows = self._session.scalars(
            select(DeepResearchSettingVersionRow)
            .where(
                DeepResearchSettingVersionRow.organization_id == self._org,
                DeepResearchSettingVersionRow.setting_key == key,
            )
            .order_by(DeepResearchSettingVersionRow.version_number.desc())
        )
        return [_version(r) for r in rows]

    def history(self, key: str, *, limit: int = 50) -> list[SettingApproval]:
        """The approval log of a setting, newest first: what was in force, by whom, from when."""
        _definition(key)
        rows = self._session.scalars(
            select(DeepResearchSettingApprovalRow)
            .where(
                DeepResearchSettingApprovalRow.organization_id == self._org,
                DeepResearchSettingApprovalRow.setting_key == key,
            )
            .order_by(DeepResearchSettingApprovalRow.approval_id.desc())
            .limit(limit)
        )
        return [
            SettingApproval(
                approval_id=r.approval_id,
                key=r.setting_key,
                version_number=r.version_number,
                approved_by=r.approved_by,
                reason=r.reason,
                approved_at=as_utc(r.approved_at),
            )
            for r in rows
        ]


class DeepResearchSettingsRepository:
    """Changes to the organization's Deep Research settings, by an issued administrator."""

    def __init__(self, session: Session, admin: OrganizationContext) -> None:
        admin.require_administer()
        self._session = session
        self._admin = admin

    def propose(
        self, key: str, value: object, *, source_url: str = "", note: str = ""
    ) -> StoredSettingVersion:
        """Store a value as the setting's next version. It is not in force until approved."""
        defn = _definition(key)
        try:
            cleaned = validate_value(defn, value)
        except SettingInvalid as exc:
            raise SettingRefused(str(exc), reason="setting_invalid") from exc
        source = source_url.strip()
        if source:
            parts = urlsplit(source)
            if len(source) > _MAX_SOURCE_URL or parts.scheme != "https" or not parts.hostname:
                raise SettingRefused(
                    f"the source is not an https URL of at most {_MAX_SOURCE_URL} characters",
                    reason="source_invalid",
                )
        if len(note) > _MAX_NOTE:
            raise SettingRefused("the note is longer than 255 characters", reason="note_too_long")
        org = self._admin.organization_id
        number = (
            self._session.scalar(
                select(func.max(DeepResearchSettingVersionRow.version_number)).where(
                    DeepResearchSettingVersionRow.organization_id == org,
                    DeepResearchSettingVersionRow.setting_key == key,
                )
            )
            or 0
        ) + 1
        row = DeepResearchSettingVersionRow(
            version_id=f"DRS-{uuid.uuid4().hex[:24]}",
            organization_id=org,
            setting_key=key,
            version_number=number,
            value=_stored(cleaned),
            value_sha256=_sha256(cleaned),
            source_url=source,
            note=note.strip(),
            created_by=self._admin.actor_id,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError as exc:
            raise SettingRefused(
                "another value was proposed at the same time; reload and propose again",
                reason="concurrent_edit",
            ) from exc
        self._audit(
            "DR_SETTING_PROPOSED",
            reason=f"{key} v{number}",
            payload={
                "key": key,
                "version": number,
                "value": _stored(cleaned)["value"],
                "value_sha256": row.value_sha256,
                "source_url": source,
            },
        )
        return _version(row)

    def approve(self, key: str, version_number: int | None, *, reason: str = "") -> Effective:
        """Put a version in force, or with ``None`` return to the code's proposed default.

        Takes effect for runs enqueued afterwards; a run already enqueued keeps what it pinned.
        Approving what is already in force changes nothing.
        """
        _definition(key)
        if len(reason) > _MAX_NOTE:
            raise SettingRefused(
                "the reason is longer than 255 characters", reason="reason_too_long"
            )
        org = self._admin.organization_id
        newest = _newest_approvals(self._session, org).get(key)
        current = None if newest is None else newest.version_number
        if version_number == current:
            return _in_force(self._session, org)[key]
        if version_number is not None:
            row = _version_row(self._session, org, key, version_number)
            if row is None:
                raise SettingRefused("no such version", reason="unknown_version")
            try:
                validate_value(definition(key), row.value["value"])
            except SettingInvalid as exc:
                raise SettingRefused(str(exc), reason="setting_invalid") from exc
            self._require_independent_approval(row)
        self._session.add(
            DeepResearchSettingApprovalRow(
                organization_id=org,
                setting_key=key,
                version_number=version_number,
                approved_by=self._admin.actor_id,
                reason=reason.strip(),
            )
        )
        self._session.flush()
        self._audit(
            "DR_SETTING_APPROVED" if version_number is not None else "DR_SETTING_WITHDRAWN",
            reason=f"{key} {_label(current)} -> {_label(version_number)}",
            payload={
                "key": key,
                "from": current,
                "to": version_number,
                "why": reason.strip(),
            },
        )
        return _in_force(self._session, org)[key]

    def _self_approval(self) -> SelfApprovalPolicy:
        org = self._session.get(OrganizationRow, self._admin.organization_id)
        return resolve_self_approval_policy(
            organization=None if org is None else org.allow_self_approval
        )

    def _require_independent_approval(self, row: DeepResearchSettingVersionRow) -> None:
        """With independent review required, the proposer does not approve alone.

        Approving again a version somebody else already approved is not a new decision.
        """
        actor = self._admin.actor_id
        if row.created_by != actor or self._self_approval().allowed:
            return
        reviewed = self._session.scalar(
            select(func.count())
            .select_from(DeepResearchSettingApprovalRow)
            .where(
                DeepResearchSettingApprovalRow.organization_id == row.organization_id,
                DeepResearchSettingApprovalRow.setting_key == row.setting_key,
                DeepResearchSettingApprovalRow.version_number == row.version_number,
                DeepResearchSettingApprovalRow.approved_by != actor,
            )
        )
        if not reviewed:
            raise SettingRefused(
                "a setting is approved by someone other than whoever proposed it "
                "(organization self-approval is off)",
                reason="self_approval_not_allowed",
            )

    def _audit(self, action: str, *, reason: str, payload: dict[str, Any]) -> None:
        self._session.add(
            AccessAuditRow(
                organization_id=self._admin.organization_id,
                actor_id=self._admin.actor_id,
                action=action,
                role=self._admin.organization_role.value,
                reason=reason[:255],
                payload=payload,
                request_id=self._admin.request_id,
            )
        )
        self._session.flush()


def _label(version_number: int | None) -> str:
    return "default" if version_number is None else f"v{version_number}"
