"""Methodology as data: the only reader and writer of its tables (ADR 0023, plan A3).

Two faces, as the Deep Research settings store (ADR 0022) and the prompt store (ADR 0020):

* :class:`MethodologyReader` reads what is in force for a module, its versions and its
  activation log. Any member of the organization may read -- the methodology is not research
  data -- through an issued :class:`~aia_core.domain.scope.OrganizationContext`, which carries
  no client or study. :meth:`~MethodologyReader.in_force` is what a run will pin when it
  starts (chunk A4).
* :class:`MethodologyRepository` writes, and refuses anyone who may not administer the
  organization (ADR 0023 decision 9: no role of its own yet): propose a version (a new
  immutable row, validated by ``domain.methodology.versions``), put a version in force, or
  return to the code's preset. Every change writes an ``access_audit`` row in its
  transaction.

Rules this module keeps:

* Only an editable module of the registry is stored, and only a version the domain validated.
  A specification or a formula is never repaired.
* A version is immutable; activation is append-only, newest row wins, ``NULL`` the preset.
* A version is named ``<base>+e<number>`` by the store, never by its author.

``make layer_check`` keeps the rows inside this module.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aia_core.domain.methodology import MethodModule, module
from aia_core.domain.methodology.versions import (
    MethodologyVersionInvalid,
    named,
    payload_sha256,
    validate_version,
    version_payload,
)
from aia_core.domain.scope import OrganizationContext

from .tables import AccessAuditRow, MethodologyActivationRow, MethodologyVersionRow, as_utc

__all__ = [
    "Activation",
    "InForce",
    "MethodologyReader",
    "MethodologyRefused",
    "MethodologyRepository",
    "StoredVersion",
]

_MAX_NOTE: Final = 500


class MethodologyRefused(ValueError):
    """A change the store will not make. ``reason`` is the wire code; ``problems`` the detail."""

    def __init__(
        self, message: str, *, reason: str, problems: Mapping[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.problems = dict(problems or {})


@dataclass(frozen=True, slots=True)
class StoredVersion:
    module_id: str
    version_number: int
    name: str
    base_preset: str
    payload: dict[str, Any]
    payload_sha256: str
    note: str
    created_by: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Activation:
    activation_id: int
    module_id: str
    version_number: int | None  # None: back to the code's preset
    activated_by: str
    reason: str
    activated_at: datetime


@dataclass(frozen=True, slots=True)
class InForce:
    """What a module runs with now: a stored version, or (``version`` None) the code preset."""

    module_id: str
    version: StoredVersion | None
    preset: str | None  # the code preset in force when no version is

    @property
    def origin(self) -> str:
        return "stored" if self.version is not None else "code"


def _module(module_id: str) -> MethodModule:
    try:
        return module(module_id)
    except KeyError as exc:
        raise MethodologyRefused(
            f"no method module {module_id!r}", reason="unknown_module"
        ) from exc


def _stored(row: MethodologyVersionRow) -> StoredVersion:
    return StoredVersion(
        module_id=row.module_id,
        version_number=row.version_number,
        name=named(row.base_preset, row.version_number),
        base_preset=row.base_preset,
        payload=dict(row.payload),
        payload_sha256=row.payload_sha256,
        note=row.note,
        created_by=row.created_by,
        created_at=as_utc(row.created_at),
    )


def _version_row(
    session: Session, org: str, module_id: str, number: int
) -> MethodologyVersionRow | None:
    return session.scalar(
        select(MethodologyVersionRow).where(
            MethodologyVersionRow.organization_id == org,
            MethodologyVersionRow.module_id == module_id,
            MethodologyVersionRow.version_number == number,
        )
    )


def _newest_activation(
    session: Session, org: str, module_id: str
) -> MethodologyActivationRow | None:
    return session.scalar(
        select(MethodologyActivationRow)
        .where(
            MethodologyActivationRow.organization_id == org,
            MethodologyActivationRow.module_id == module_id,
        )
        .order_by(MethodologyActivationRow.activation_id.desc())
        .limit(1)
    )


def _in_force(session: Session, org: str, found: MethodModule) -> InForce:
    newest = _newest_activation(session, org, found.id)
    if newest is None or newest.version_number is None:
        return InForce(found.id, None, found.in_force)
    row = _version_row(session, org, found.id, newest.version_number)
    if row is None:  # the foreign key forbids it; never read a missing row as the preset
        raise MethodologyRefused(
            f"{found.id}: the version in force is missing", reason="version_missing"
        )
    return InForce(found.id, _stored(row), None)


class MethodologyReader:
    """The organization's methodology, read by any of its members."""

    def __init__(self, session: Session, reader: OrganizationContext) -> None:
        self._session = session
        self._org = reader.organization_id

    def in_force(self, module_id: str) -> InForce:
        """What a run started now would pin for ``module_id``."""
        return _in_force(self._session, self._org, _module(module_id))

    def versions(self, module_id: str) -> list[StoredVersion]:
        """Every stored version of a module, newest first."""
        _module(module_id)
        rows = self._session.scalars(
            select(MethodologyVersionRow)
            .where(
                MethodologyVersionRow.organization_id == self._org,
                MethodologyVersionRow.module_id == module_id,
            )
            .order_by(MethodologyVersionRow.version_number.desc())
        )
        return [_stored(r) for r in rows]

    def history(self, module_id: str, *, limit: int = 50) -> list[Activation]:
        """The activation log of a module, newest first: what was in force, by whom, from when."""
        _module(module_id)
        rows = self._session.scalars(
            select(MethodologyActivationRow)
            .where(
                MethodologyActivationRow.organization_id == self._org,
                MethodologyActivationRow.module_id == module_id,
            )
            .order_by(MethodologyActivationRow.activation_id.desc())
            .limit(limit)
        )
        return [
            Activation(
                activation_id=r.activation_id,
                module_id=r.module_id,
                version_number=r.version_number,
                activated_by=r.activated_by,
                reason=r.reason,
                activated_at=as_utc(r.activated_at),
            )
            for r in rows
        ]


class MethodologyRepository:
    """Changes to the organization's methodology, by an issued administrator."""

    def __init__(self, session: Session, admin: OrganizationContext) -> None:
        admin.require_administer()
        self._session = session
        self._admin = admin

    def propose(
        self,
        module_id: str,
        *,
        base_preset: str,
        spec: Mapping[str, Any],
        formulas: Mapping[str, str],
        note: str = "",
    ) -> StoredVersion:
        """Store an edited methodology as the module's next version. Not in force until put."""
        found = _module(module_id)
        if len(note) > _MAX_NOTE:
            raise MethodologyRefused(
                f"the note is longer than {_MAX_NOTE} characters", reason="note_too_long"
            )
        org = self._admin.organization_id
        number = (
            self._session.scalar(
                select(func.max(MethodologyVersionRow.version_number)).where(
                    MethodologyVersionRow.organization_id == org,
                    MethodologyVersionRow.module_id == module_id,
                )
            )
            or 0
        ) + 1
        try:
            validated = validate_version(
                found,
                base_preset=base_preset,
                spec=spec,
                formulas=formulas,
                version_name=named(base_preset, number),
            )
        except MethodologyVersionInvalid as exc:
            raise MethodologyRefused(
                str(exc), reason="methodology_invalid", problems=exc.problems
            ) from exc
        payload = version_payload(validated)
        row = MethodologyVersionRow(
            version_id=f"MTV-{uuid.uuid4().hex[:24]}",
            organization_id=org,
            module_id=module_id,
            version_number=number,
            base_preset=base_preset,
            payload=payload,
            payload_sha256=payload_sha256(payload),
            note=note.strip(),
            created_by=self._admin.actor_id,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError as exc:
            raise MethodologyRefused(
                "another version was proposed at the same time; reload and propose again",
                reason="concurrent_edit",
            ) from exc
        self._audit(
            "METHODOLOGY_PROPOSED",
            reason=f"{module_id} {named(base_preset, number)}",
            payload={
                "module": module_id,
                "version": number,
                "base_preset": base_preset,
                "payload_sha256": row.payload_sha256,
                "formulas": sorted(validated.formulas),
            },
        )
        return _stored(row)

    def activate(self, module_id: str, version_number: int | None, *, reason: str = "") -> InForce:
        """Put a version in force, or with ``None`` return to the code's preset.

        Takes effect for runs started afterwards; a run already started keeps its pin.
        Putting in force what is already in force changes nothing.
        """
        found = _module(module_id)
        if len(reason) > _MAX_NOTE:
            raise MethodologyRefused(
                f"the reason is longer than {_MAX_NOTE} characters", reason="reason_too_long"
            )
        org = self._admin.organization_id
        newest = _newest_activation(self._session, org, module_id)
        current = None if newest is None else newest.version_number
        if version_number == current:
            return _in_force(self._session, org, found)
        if version_number is not None:
            row = _version_row(self._session, org, module_id, version_number)
            if row is None:
                raise MethodologyRefused("no such version", reason="unknown_version")
            # Re-validated: a version stored under an older engine may no longer compute.
            try:
                validate_version(
                    found,
                    base_preset=row.base_preset,
                    spec=row.payload["spec"],
                    formulas=row.payload["formulas"],
                    version_name=named(row.base_preset, row.version_number),
                )
            except MethodologyVersionInvalid as exc:
                raise MethodologyRefused(
                    str(exc), reason="methodology_invalid", problems=exc.problems
                ) from exc
        self._session.add(
            MethodologyActivationRow(
                organization_id=org,
                module_id=module_id,
                version_number=version_number,
                activated_by=self._admin.actor_id,
                reason=reason.strip(),
            )
        )
        self._session.flush()
        self._audit(
            "METHODOLOGY_ACTIVATED" if version_number is not None else "METHODOLOGY_RESET",
            reason=f"{module_id} {_label(current)} -> {_label(version_number)}",
            payload={"module": module_id, "from": current, "to": version_number, "why": reason},
        )
        return _in_force(self._session, org, found)

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
    return "preset" if version_number is None else f"e{version_number}"
