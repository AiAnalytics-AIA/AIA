"""Deep Research settings as data: the only reader and writer of their tables (ADR 0022).

Two faces, deliberately separate, as ADR 0020's prompt store:

* :class:`DeepResearchSettingsReader` reads: the catalogue with what is in force, a setting's
  versions and its approval history. Any member of the organization may read -- these are
  policy values, not research data -- through an issued
  :class:`~aia_core.domain.scope.OrganizationContext`, which carries no client or study.
  :meth:`~DeepResearchSettingsReader.effective` is what a run will pin at enqueue (chunk 43);
  :func:`settings_in_force_for_study` is the same, read through the enqueuing Study's scope.
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
import math
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
    Origin,
    SettingDefinition,
    SettingInvalid,
    SettingValue,
    definition,
    effective,
    validate_value,
)
from aia_core.domain.deployment import parse_environment
from aia_core.domain.scope import (
    OrganizationContext,
    SelfApprovalPolicy,
    StudyContext,
    resolve_self_approval_policy,
)

from .tables import (
    AccessAuditRow,
    DeepResearchSettingApprovalRow,
    DeepResearchSettingVersionRow,
    DeepResearchTestApprovalRow,
    DeepResearchTestPolicyRow,
    OrganizationRow,
    StudyRow,
    as_utc,
    utcnow,
)

__all__ = [
    "DeepResearchSettingsReader",
    "DeepResearchSettingsRepository",
    "SettingApproval",
    "SettingOverview",
    "SettingRefused",
    "StoredSettingVersion",
    "settings_in_force_for_study",
    "test_approval_receipt_for_study",
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


def settings_in_force_for_study(session: Session, scope: StudyContext) -> EffectiveSettings:
    """What the Study's organization has in force now: what a run enqueued in it pins.

    Read through the Study's own resolved scope, so the enqueue boundary needs no
    organization-administration context; only the organization's rows are read, and a Study
    never sees another organization's settings.
    """
    normal = _in_force(session, scope.organization_id)
    active = _active_test_approval(session, scope)
    if active is None:
        return normal
    policy, approval = active
    approved = {
        item.key: ApprovedValue(
            item.value,
            item.version or 1,
            item.approved_by or "",
            item.approved_at or as_utc(approval.approved_at),
        )
        for item in normal.values
        if item.origin is Origin.APPROVED
    }
    for key, value in policy.values_json.items():
        approved[key] = ApprovedValue(
            value, approval.approval_id, approval.approved_by, as_utc(approval.approved_at)
        )
    return effective(approved)


def _test_environment(scope: StudyContext) -> bool:
    environment = parse_environment(os.environ.get("AIA_ENV"))
    clients = {c.strip() for c in os.environ.get("AIA_AI_FICTIONAL_CLIENT_IDS", "").split(",")}
    return bool(
        environment and environment.allows_fictional_material and scope.client_id in clients
    )


def _test_policy_sha(policy: DeepResearchTestPolicyRow) -> str:
    return hashlib.sha256(
        canonical_json(
            {
                "organization_id": policy.organization_id,
                "client_id": policy.client_id,
                "study_id": policy.study_id,
                "values": policy.values_json,
                "budget_cap_usd": float(policy.budget_cap_usd),
                "provider_permission": policy.provider_permission,
                "expires_at": as_utc(policy.expires_at).isoformat(),
                "created_by": policy.created_by,
                "created_at": as_utc(policy.created_at).isoformat(),
            }
        ).encode()
    ).hexdigest()


def _test_values(values: dict[str, Any], cap: float) -> dict[str, Any]:
    cleaned = {
        key: _stored(validate_value(_definition(key), value))["value"]
        for key, value in values.items()
    }
    trial = effective(
        {
            key: ApprovedValue(value, 1, "operator", datetime.now(UTC))
            for key, value in cleaned.items()
        }
    )
    if (
        trial.missing_for_live()
        or cleaned.get("provider.search.storage_and_ai_use_granted") is not True
    ):
        raise SettingRefused(
            "every live setting and test storage permission is required",
            reason="test_policy_incomplete",
        )
    if any(
        float(cleaned[f"budgets.run_limit.{preset}"]) > cap
        for preset in ("standard", "deep", "exhaustive")
    ):
        raise SettingRefused(
            "test run limits exceed the approved cap", reason="test_budget_invalid"
        )
    return cleaned


def _active_test_approval(
    session: Session, scope: StudyContext
) -> tuple[DeepResearchTestPolicyRow, DeepResearchTestApprovalRow] | None:
    if not _test_environment(scope):
        return None
    approval = session.scalar(
        select(DeepResearchTestApprovalRow)
        .where(
            DeepResearchTestApprovalRow.organization_id == scope.organization_id,
            DeepResearchTestApprovalRow.study_id == scope.study_id,
        )
        .order_by(DeepResearchTestApprovalRow.approval_id.desc())
        .limit(1)
    )
    if approval is None or not approval.approved:
        return None
    policy = session.get(DeepResearchTestPolicyRow, approval.policy_id)
    study = session.get(StudyRow, scope.study_id)
    if (
        policy is None
        or study is None
        or policy.organization_id != scope.organization_id
        or policy.study_id != scope.study_id
        or policy.client_id != scope.client_id
        or study.organization_id != scope.organization_id
        or study.client_id != scope.client_id
        or as_utc(policy.expires_at) <= utcnow()
        or study.budget_usd <= 0
        or study.budget_usd > policy.budget_cap_usd
    ):
        return None
    if policy.policy_sha256 != _test_policy_sha(policy):
        raise SettingRefused("test policy seal changed", reason="test_policy_corrupt")
    try:
        _test_values(policy.values_json, policy.budget_cap_usd)
    except SettingInvalid as exc:
        raise SettingRefused(str(exc), reason="test_policy_invalid") from exc
    return policy, approval


def test_approval_receipt_for_study(session: Session, scope: StudyContext) -> dict[str, Any] | None:
    """Operator authority pinned beside a run's settings, never supplied by its request."""
    active = _active_test_approval(session, scope)
    if active is None:
        return None
    policy, approval = active
    return {
        "policy_id": policy.policy_id,
        "policy_sha256": policy.policy_sha256,
        "approval_id": approval.approval_id,
        "organization_id": policy.organization_id,
        "client_id": policy.client_id,
        "study_id": policy.study_id,
        "expires_at": as_utc(policy.expires_at).isoformat(),
        "budget_cap_usd": policy.budget_cap_usd,
        "provider_permission": policy.provider_permission,
        "approved_by": approval.approved_by,
    }


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

    def propose_test_policy(
        self,
        scope: StudyContext,
        *,
        values: dict[str, Any],
        expires_at: datetime,
        budget_cap_usd: float,
        provider_permission: str,
    ) -> str:
        """Propose a complete, expiring policy for an explicitly fictional study only."""
        if scope.organization_id != self._admin.organization_id or not _test_environment(scope):
            raise SettingRefused(
                "test policy requires a scoped fictional study", reason="test_scope_refused"
            )
        now = utcnow()
        if expires_at.tzinfo is None or not now < expires_at <= now + timedelta(days=7):
            raise SettingRefused(
                "test expiry must be within seven days", reason="test_expiry_invalid"
            )
        study = self._session.get(StudyRow, scope.study_id)
        if (
            isinstance(budget_cap_usd, bool)
            or not math.isfinite(budget_cap_usd)
            or not 0 < budget_cap_usd <= 20
            or study is None
            or study.organization_id != scope.organization_id
            or study.client_id != scope.client_id
            or not 0 < study.budget_usd <= budget_cap_usd
        ):
            raise SettingRefused(
                "test budget must cover this study and be at most USD 20",
                reason="test_budget_invalid",
            )
        permission = provider_permission.strip()
        if not permission or len(permission) > 1000:
            raise SettingRefused(
                "record the provider's test permission", reason="test_permission_missing"
            )
        try:
            cleaned = _test_values(values, budget_cap_usd)
        except SettingInvalid as exc:
            raise SettingRefused(str(exc), reason="setting_invalid") from exc
        row = DeepResearchTestPolicyRow(
            policy_id=f"DRT-{uuid.uuid4().hex[:24]}",
            organization_id=scope.organization_id,
            client_id=scope.client_id,
            study_id=scope.study_id,
            values_json=cleaned,
            budget_cap_usd=budget_cap_usd,
            provider_permission=permission,
            expires_at=expires_at.astimezone(UTC),
            created_by=self._admin.actor_id,
            created_at=now,
        )
        row.policy_sha256 = _test_policy_sha(row)
        self._session.add(row)
        self._session.flush()
        self._audit(
            "DR_TEST_POLICY_PROPOSED",
            reason="fictional study test only",
            payload={
                "policy_id": row.policy_id,
                "study_id": row.study_id,
                "client_id": row.client_id,
                "policy_sha256": row.policy_sha256,
                "values": cleaned,
                "budget_cap_usd": budget_cap_usd,
                "expires_at": row.expires_at.isoformat(),
                "provider_permission": permission,
            },
        )
        return row.policy_id

    def approve_test_policy(
        self, scope: StudyContext, policy_id: str, *, approved: bool = True, reason: str
    ) -> None:
        """Append an approval or withdrawal; organization settings are never changed."""
        row = self._session.get(DeepResearchTestPolicyRow, policy_id)
        if (
            row is None
            or row.organization_id != self._admin.organization_id
            or row.organization_id != scope.organization_id
            or row.study_id != scope.study_id
            or row.client_id != scope.client_id
        ):
            raise SettingRefused("no test policy in this scope", reason="test_scope_refused")
        if not reason.strip() or len(reason) > 255:
            raise SettingRefused(
                "a reason of at most 255 characters is required", reason="reason_too_long"
            )
        if approved:
            if not _test_environment(scope) or as_utc(row.expires_at) <= utcnow():
                raise SettingRefused(
                    "test permission unavailable or expired", reason="test_scope_refused"
                )
            if row.policy_sha256 != _test_policy_sha(row):
                raise SettingRefused("test policy seal changed", reason="test_policy_corrupt")
            if row.created_by == self._admin.actor_id and not self._self_approval().allowed:
                raise SettingRefused(
                    "independent approval is required", reason="self_approval_not_allowed"
                )
        approval = DeepResearchTestApprovalRow(
            policy_id=policy_id,
            organization_id=row.organization_id,
            study_id=row.study_id,
            approved=approved,
            approved_by=self._admin.actor_id,
            reason=reason.strip(),
        )
        self._session.add(approval)
        self._session.flush()
        self._audit(
            "DR_TEST_POLICY_APPROVED" if approved else "DR_TEST_POLICY_WITHDRAWN",
            reason=reason,
            payload={
                "policy_id": policy_id,
                "approval_id": approval.approval_id,
                "study_id": row.study_id,
                "client_id": row.client_id,
                "policy_sha256": row.policy_sha256,
            },
        )

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
