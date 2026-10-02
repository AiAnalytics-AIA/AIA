"""System prompts as data: the only reader and writer of the prompt tables (ADR 0020).

Two faces, deliberately separate:

* :class:`PromptRepository` is the **administrative** face. It takes an issued
  :class:`~aia_core.domain.scope.OrganizationContext` and refuses anyone who may not
  administer the organization. It lists, creates versions and activates them, and
  writes an audit row in the same transaction as every change.
* :class:`PromptResolver` is the **read-only** face study-level code uses to *freeze a
  pin when a job is queued*. It takes the organization id of an issued
  ``StudyContext`` and can change nothing. A running job never calls it: it carries
  the pin it was given.

Rules this module keeps:

* A version is immutable. An edit is a new row; nothing here updates or deletes one.
* Activation is append-only. Rolling back is a new row naming the baseline (NULL) or an
  earlier version, so the record of what ran is complete.
* Only a **wired** slot can be edited. Editing a prompt no composition reads would
  promise an effect that does not happen.
* Review follows the organization's self-approval setting (ADR 0019: no approval between
  people by default, the setting kept for a client that wants independent review). With
  the setting off, whoever wrote a version does not activate it unless someone else
  already activated that exact version.
* A prompt that fails validation is refused, never repaired or truncated.

``make layer_check`` keeps the rows inside this module.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aia_core.domain.prompt_slots import PromptSlot, get_slot, slots
from aia_core.domain.prompts import (
    PromptPin,
    PromptRejected,
    prompt_sha256,
    stored_version_label,
)
from aia_core.domain.scope import (
    OrganizationContext,
    SelfApprovalPolicy,
    resolve_self_approval_policy,
)

from .tables import (
    AccessAuditRow,
    OrganizationRow,
    PromptActivationRow,
    PromptVersionRow,
    as_utc,
)

__all__ = [
    "ActiveState",
    "PromptOverview",
    "PromptRefused",
    "PromptRepository",
    "PromptResolver",
    "StoredVersion",
]


class PromptRefused(Exception):
    """A request the store will not honour. ``reason`` is a stable machine word."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class StoredVersion:
    version_number: int
    label: str
    text: str
    text_sha256: str
    based_on: str
    note: str
    created_by: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ActiveState:
    """What runs for one prompt now. ``version_number`` None is the code's wording."""

    prompt_id: str
    version_number: int | None
    label: str
    origin: str  # "baseline" | "stored"
    text_sha256: str
    activated_by: str | None
    activated_at: datetime | None
    reason: str


@dataclass(frozen=True, slots=True)
class PromptOverview:
    slot: PromptSlot
    active: ActiveState
    version_count: int
    latest_number: int | None


def _version(row: PromptVersionRow) -> StoredVersion:
    return StoredVersion(
        version_number=row.version_number,
        label=stored_version_label(row.version_number),
        text=row.text,
        text_sha256=row.text_sha256,
        based_on=row.based_on,
        note=row.note,
        created_by=row.created_by,
        created_at=as_utc(row.created_at),
    )


def _baseline_state(slot: PromptSlot) -> ActiveState:
    return ActiveState(
        prompt_id=slot.prompt_id,
        version_number=None,
        label=slot.baseline_version,
        origin="baseline",
        text_sha256=prompt_sha256(slot.baseline_text),
        activated_by=None,
        activated_at=None,
        reason="",
    )


def _latest_activation(
    session: Session, organization_id: str, prompt_id: str
) -> PromptActivationRow | None:
    return session.scalar(
        select(PromptActivationRow)
        .where(
            PromptActivationRow.organization_id == organization_id,
            PromptActivationRow.prompt_id == prompt_id,
        )
        .order_by(PromptActivationRow.activation_id.desc())
        .limit(1)
    )


def _state(
    session: Session, organization_id: str, slot: PromptSlot
) -> tuple[ActiveState, PromptVersionRow | None]:
    """The active state of one slot, and the stored row behind it when there is one."""
    latest = _latest_activation(session, organization_id, slot.prompt_id)
    if latest is None:
        return _baseline_state(slot), None
    if latest.version_number is None:
        # Rolled back to the code's wording: still a decision somebody made and dated.
        return (
            replace(
                _baseline_state(slot),
                activated_by=latest.activated_by,
                activated_at=as_utc(latest.activated_at),
                reason=latest.reason,
            ),
            None,
        )
    row = session.scalar(
        select(PromptVersionRow).where(
            PromptVersionRow.organization_id == organization_id,
            PromptVersionRow.prompt_id == slot.prompt_id,
            PromptVersionRow.version_number == latest.version_number,
        )
    )
    if row is None:  # pragma: no cover - the composite foreign key forbids it
        raise PromptRefused("active version is missing", reason="active_version_missing")
    return (
        ActiveState(
            prompt_id=slot.prompt_id,
            version_number=row.version_number,
            label=stored_version_label(row.version_number),
            origin="stored",
            text_sha256=row.text_sha256,
            activated_by=latest.activated_by,
            activated_at=as_utc(latest.activated_at),
            reason=latest.reason,
        ),
        row,
    )


def _wired_slot(prompt_id: str) -> PromptSlot:
    slot = get_slot(prompt_id)
    if slot is None:
        raise PromptRefused(f"unknown prompt {prompt_id}", reason="unknown_prompt")
    if not slot.wired:
        raise PromptRefused(
            f"{prompt_id} is not read by any running step yet ({slot.unwired_reason}); "
            "an edit would change nothing",
            reason="not_editable",
        )
    return slot


class PromptResolver:
    """Read-only: the pin a job takes when it is queued. Scoped by the organization.

    The organization id comes from an issued scope, never from a request. With no
    activation the code's wording is pinned as the baseline, and the pin says so.
    """

    def __init__(self, session: Session, organization_id: str) -> None:
        self._session = session
        self._organization_id = organization_id

    def pin_for(self, prompt_id: str) -> PromptPin:
        slot = _wired_slot(prompt_id)
        state, row = _state(self._session, self._organization_id, slot)
        if row is None:
            return slot.baseline_pin()
        return PromptPin.of(
            prompt_id=slot.prompt_id,
            version=state.label,
            origin="stored",
            text=row.text,
        )

    def pin_for_version(self, prompt_id: str, version_number: int) -> PromptPin:
        """A specific stored version, active or not -- for testing a draft (ADR 0020)."""
        slot = _wired_slot(prompt_id)
        row = self._session.scalar(
            select(PromptVersionRow).where(
                PromptVersionRow.organization_id == self._organization_id,
                PromptVersionRow.prompt_id == slot.prompt_id,
                PromptVersionRow.version_number == version_number,
            )
        )
        if row is None:
            raise PromptRefused("no such version", reason="unknown_version")
        return PromptPin.of(
            prompt_id=slot.prompt_id,
            version=stored_version_label(row.version_number),
            origin="stored",
            text=row.text,
        )


class PromptRepository:
    """Administration of the prompts for one organization, by an issued administrator."""

    def __init__(self, session: Session, admin: OrganizationContext) -> None:
        admin.require_administer()
        self._session = session
        self._admin = admin

    # ---------------------------------------------------------------- reads --

    def overview(self) -> list[PromptOverview]:
        org = self._admin.organization_id
        counts = {
            prompt_id: (count, latest)
            for prompt_id, count, latest in self._session.execute(
                select(
                    PromptVersionRow.prompt_id,
                    func.count(),
                    func.max(PromptVersionRow.version_number),
                )
                .where(PromptVersionRow.organization_id == org)
                .group_by(PromptVersionRow.prompt_id)
            )
        }
        out: list[PromptOverview] = []
        for slot in slots():
            state, _ = _state(self._session, org, slot)
            count, latest = counts.get(slot.prompt_id, (0, None))
            out.append(PromptOverview(slot, state, int(count), latest))
        return out

    def versions(self, prompt_id: str) -> list[StoredVersion]:
        """Every stored version of a prompt, newest first."""
        if get_slot(prompt_id) is None:
            raise PromptRefused(f"unknown prompt {prompt_id}", reason="unknown_prompt")
        rows = self._session.scalars(
            select(PromptVersionRow)
            .where(
                PromptVersionRow.organization_id == self._admin.organization_id,
                PromptVersionRow.prompt_id == prompt_id,
            )
            .order_by(PromptVersionRow.version_number.desc())
        )
        return [_version(r) for r in rows]

    def get_version(self, prompt_id: str, version_number: int) -> StoredVersion:
        row = self._row(prompt_id, version_number)
        if row is None:
            raise PromptRefused("no such version", reason="unknown_version")
        return _version(row)

    def history(self, prompt_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """The activation log of a prompt, newest first (who ran what, from when)."""
        if get_slot(prompt_id) is None:
            raise PromptRefused(f"unknown prompt {prompt_id}", reason="unknown_prompt")
        rows = self._session.scalars(
            select(PromptActivationRow)
            .where(
                PromptActivationRow.organization_id == self._admin.organization_id,
                PromptActivationRow.prompt_id == prompt_id,
            )
            .order_by(PromptActivationRow.activation_id.desc())
            .limit(limit)
        )
        return [
            {
                "activation_id": r.activation_id,
                "version_number": r.version_number,
                "label": None
                if r.version_number is None
                else stored_version_label(r.version_number),
                "activated_by": r.activated_by,
                "reason": r.reason,
                "activated_at": as_utc(r.activated_at),
            }
            for r in rows
        ]

    def active(self, prompt_id: str) -> ActiveState:
        slot = get_slot(prompt_id)
        if slot is None:
            raise PromptRefused(f"unknown prompt {prompt_id}", reason="unknown_prompt")
        return _state(self._session, self._admin.organization_id, slot)[0]

    # --------------------------------------------------------------- writes --

    def create_version(
        self, prompt_id: str, text: str, *, note: str = "", based_on: str | None = None
    ) -> StoredVersion:
        """Store an edit as the next version. It does not run until it is activated."""
        slot = _wired_slot(prompt_id)
        try:
            cleaned = slot.check(text)
        except PromptRejected as exc:
            raise PromptRefused(str(exc), reason=exc.reason) from exc
        if len(note) > 255:
            raise PromptRefused("the note is longer than 255 characters", reason="note_too_long")
        org = self._admin.organization_id
        number = (
            self._session.scalar(
                select(func.max(PromptVersionRow.version_number)).where(
                    PromptVersionRow.organization_id == org,
                    PromptVersionRow.prompt_id == prompt_id,
                )
            )
            or 0
        ) + 1
        row = PromptVersionRow(
            version_id=f"PV-{uuid.uuid4().hex[:24]}",
            organization_id=org,
            prompt_id=prompt_id,
            version_number=number,
            text=cleaned,
            text_sha256=prompt_sha256(cleaned),
            based_on=based_on or "baseline",
            note=note.strip(),
            created_by=self._admin.actor_id,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError as exc:
            # Two administrators saved at the same moment and took the same number.
            raise PromptRefused(
                "another version was saved at the same time; reload and save again",
                reason="concurrent_edit",
            ) from exc
        self._audit(
            "PROMPT_VERSION_CREATED",
            reason=f"{prompt_id} {stored_version_label(number)}",
            payload={
                "prompt_id": prompt_id,
                "version": stored_version_label(number),
                "text_sha256": row.text_sha256,
                "based_on": row.based_on,
            },
        )
        return _version(row)

    def activate(
        self, prompt_id: str, version_number: int | None, *, reason: str = ""
    ) -> ActiveState:
        """Make a stored version (or, with ``None``, the code's wording) what runs.

        Takes effect for jobs queued after this call; a job already queued keeps the
        pin it was given. Activating what is already active changes nothing.
        """
        slot = _wired_slot(prompt_id)
        if len(reason) > 255:
            raise PromptRefused(
                "the reason is longer than 255 characters", reason="reason_too_long"
            )
        org = self._admin.organization_id
        before, _ = _state(self._session, org, slot)
        if version_number == before.version_number:
            return before
        if version_number is not None:
            row = self._row(prompt_id, version_number)
            if row is None:
                raise PromptRefused("no such version", reason="unknown_version")
            self._require_independent_activation(row)
        self._session.add(
            PromptActivationRow(
                organization_id=org,
                prompt_id=prompt_id,
                version_number=version_number,
                activated_by=self._admin.actor_id,
                reason=reason.strip(),
            )
        )
        self._session.flush()
        after, _ = _state(self._session, org, slot)
        self._audit(
            "PROMPT_ACTIVATED" if version_number is not None else "PROMPT_RESET_TO_BASELINE",
            reason=f"{prompt_id} {before.label} -> {after.label}",
            payload={
                "prompt_id": prompt_id,
                "from": before.label,
                "to": after.label,
                "to_text_sha256": after.text_sha256,
                "why": reason.strip(),
            },
        )
        return after

    # ------------------------------------------------------------- internals --

    def _row(self, prompt_id: str, version_number: int) -> PromptVersionRow | None:
        return self._session.scalar(
            select(PromptVersionRow).where(
                PromptVersionRow.organization_id == self._admin.organization_id,
                PromptVersionRow.prompt_id == prompt_id,
                PromptVersionRow.version_number == version_number,
            )
        )

    def _self_approval(self) -> SelfApprovalPolicy:
        org = self._session.get(OrganizationRow, self._admin.organization_id)
        return resolve_self_approval_policy(
            organization=None if org is None else org.allow_self_approval
        )

    def _require_independent_activation(self, row: PromptVersionRow) -> None:
        """With independent review required, the author does not put a version live alone.

        Rolling back to a version somebody else already ran is not a new decision, so
        it is allowed: that exact text has been put live by a different person before.
        """
        actor = self._admin.actor_id
        if row.created_by != actor or self._self_approval().allowed:
            return
        reviewed = self._session.scalar(
            select(func.count())
            .select_from(PromptActivationRow)
            .where(
                PromptActivationRow.organization_id == row.organization_id,
                PromptActivationRow.prompt_id == row.prompt_id,
                PromptActivationRow.version_number == row.version_number,
                PromptActivationRow.activated_by != actor,
            )
        )
        if not reviewed:
            raise PromptRefused(
                "a prompt version is put live by someone other than its author "
                "(organization self-approval is off)",
                reason="self_activation_not_allowed",
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
