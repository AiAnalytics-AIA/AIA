"""Companion assets and the joint-claim certificate.

A panel alone is not a usable population version: it cannot say what its fields
mean, how good they are, or what may be claimed from them jointly. The reference's
``DATA_CONTRACT_v17.json`` declares the assets that must travel with it
(AIA-reference ``population-subsystem.md`` §9), and its import contract lists the
checks that must hold before an import is accepted (``czech-population.md``
VALIDATION; methodology M14).

Every companion is pinned by SHA256 and byte size -- the same bytes the reference
validated, or nothing. The shape checks that the reference recorded are re-run on
top: row and column counts, the persona catalogue's ``column`` values being panel
columns, zero ``FAIL`` in the respondent audit's ``audit_status``. A check whose
input the reference did not record (for example, which scorecard column names the
field) is not invented; the report says it was not asserted.

**The joint certificate.** ``CORE_JOINT_STATUS.json`` (methodology M03, risk R6)
certifies what may be claimed *jointly* -- across fields, across donor-matched
blocks -- for the exact panel bytes named in ``panel_sha256``. It is evaluated by
a fail-closed gate, as the reference's ``load_joint_status`` did: a missing or
unparseable file, an unknown status, a structure that did not pass QC, any
permission flag that is not a literal boolean, or a panel hash that is not this
version's all yield the **fallback**, in which every joint permission is False.
Only a certificate that binds to this exact panel can grant anything, and it can
only grant what it states.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Final

from .table import ParsedPanel
from .versions import content_sha256, is_sha256

__all__ = [
    "KNOWN_JOINT_STATUSES",
    "CompanionKind",
    "CompanionReport",
    "CompanionSet",
    "CompanionSpec",
    "JointDecision",
    "JointState",
    "JointStatus",
    "companion_set_sha256",
    "evaluate_joint_certificate",
    "validate_companions",
]

#: Certificate statuses whose meaning is recovered. Anything else is unknown and
#: falls back. ``COHERENT_CORE_MATCHED_BLOCKS`` is the v17 status (M03).
KNOWN_JOINT_STATUSES: Final = frozenset({"COHERENT_CORE_MATCHED_BLOCKS"})
_QC_PASSED: Final = "QC_PASSED"

_JOINT_FLAGS: Final = (
    "client_joint_outputs_allowed",
    "cross_block_joint_claims_allowed",
    "cross_block_same_person_joint",
    "core_same_person_joint",
    "descriptive_core_outputs_allowed",
    "matched_block_outputs_allowed",
)


class CompanionKind(StrEnum):
    """What a companion asset is, and therefore which shape checks apply to it."""

    DIMENSION_SCORECARD = "DIMENSION_SCORECARD"
    PERSONA_SIGNAL_CATALOG = "PERSONA_SIGNAL_CATALOG"
    RESPONDENT_AUDIT = "RESPONDENT_AUDIT"
    CORE_JOINT_STATUS = "CORE_JOINT_STATUS"
    #: Declared by the data contract; validated for identity and recorded shape only.
    INTEGRITY_ONLY = "INTEGRITY_ONLY"


@dataclass(frozen=True, slots=True)
class CompanionSpec:
    """One required companion: its identity, and the shape checks recovered for it."""

    asset_id: str
    kind: CompanionKind
    sha256: str
    byte_size: int
    #: ``csv`` (checked for rows/columns), ``json`` or ``gz`` (identity only).
    fmt: str
    rows: int | None = None
    columns: int | None = None
    #: The catalogue column whose values must all be panel columns.
    panel_column_field: str | None = None
    #: The audit column that must never hold ``forbidden_status``.
    status_column: str | None = None
    forbidden_status: str | None = None

    def __post_init__(self) -> None:
        if not self.asset_id:
            raise ValueError("a companion needs an asset id")
        if not is_sha256(self.sha256):
            raise ValueError(f"companion {self.asset_id} needs a lowercase sha256")
        if self.byte_size <= 0:
            raise ValueError(f"companion {self.asset_id} needs a positive byte size")
        if self.fmt not in ("csv", "json", "gz"):
            raise ValueError(f"companion {self.asset_id} has unknown format {self.fmt!r}")
        if (self.status_column is None) != (self.forbidden_status is None):
            raise ValueError(f"companion {self.asset_id}: status column and value go together")
        if self.kind is CompanionKind.CORE_JOINT_STATUS and self.fmt != "json":
            raise ValueError("the joint certificate is JSON")


# --------------------------------------------------------------------------- #
# The joint certificate
# --------------------------------------------------------------------------- #


class JointState(StrEnum):
    """How a certificate evaluated. Only CERTIFIED grants anything."""

    CERTIFIED = "CERTIFIED"
    NOT_THIS_PANEL = "NOT_THIS_PANEL"
    UNKNOWN_STATUS = "UNKNOWN_STATUS"
    UNPARSEABLE = "UNPARSEABLE"
    MISSING = "MISSING"


@dataclass(frozen=True, slots=True)
class JointDecision:
    """The answer to "may these fields be claimed jointly?"."""

    allowed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class JointStatus:
    """What may be claimed jointly for one panel. The fallback forbids everything."""

    state: JointState
    detail: str
    certified_panel_sha256: str | None = None
    status: str | None = None
    client_joint_outputs_allowed: bool = False
    cross_block_joint_claims_allowed: bool = False
    cross_block_same_person_joint: bool = False
    core_same_person_joint: bool = False
    descriptive_core_outputs_allowed: bool = False
    matched_block_outputs_allowed: bool = False
    matched_blocks: frozenset[str] = frozenset()
    prediction_validation_status: str | None = None

    @classmethod
    def fallback(cls, state: JointState, detail: str) -> JointStatus:
        """The fail-closed status: nothing joint is permitted."""
        if state is JointState.CERTIFIED:
            raise ValueError("the fallback is never CERTIFIED")
        return cls(state=state, detail=detail)

    @property
    def certified(self) -> bool:
        """True only for a certificate that binds to this panel and passed every check."""
        return self.state is JointState.CERTIFIED

    def decide(self, field_blocks: Mapping[str, str], *, client_facing: bool) -> JointDecision:
        """May the fields in ``field_blocks`` (field -> dictionary block) be used jointly?

        A single field is not a joint claim and is decided by the field policy.
        Two or more fields are joint. For a client-facing output that needs
        ``client_joint_outputs_allowed``. Internally, fields drawn from more than
        one block where any block is donor-matched are a cross-block relationship,
        which is not same-person truth unless the certificate says it is.
        """
        if len(field_blocks) < 2:
            return JointDecision(True, "not_joint")
        if not self.certified:
            return JointDecision(False, f"certificate_{self.state.value.lower()}")
        if client_facing and not self.client_joint_outputs_allowed:
            return JointDecision(False, "client_joint_outputs_forbidden")
        blocks = set(field_blocks.values())
        cross_block = len(blocks) > 1 and bool(blocks & self.matched_blocks)
        if cross_block and not (
            self.cross_block_same_person_joint and self.cross_block_joint_claims_allowed
        ):
            return JointDecision(False, "cross_block_same_person_forbidden")
        return JointDecision(True, "certified_joint")

    def as_record(self) -> dict[str, Any]:
        """A JSON-serialisable form, for reports and provenance."""
        return {
            "state": self.state.value,
            "detail": self.detail,
            "certified_panel_sha256": self.certified_panel_sha256,
            "status": self.status,
            **{flag: getattr(self, flag) for flag in _JOINT_FLAGS},
            "matched_blocks": sorted(self.matched_blocks),
            "prediction_validation_status": self.prediction_validation_status,
        }


def evaluate_joint_certificate(data: bytes | None, *, panel_sha256: str) -> JointStatus:
    """Evaluate ``CORE_JOINT_STATUS.json`` against the panel it must certify."""
    if data is None:
        return JointStatus.fallback(JointState.MISSING, "no certificate")
    try:
        document = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return JointStatus.fallback(JointState.UNPARSEABLE, f"not JSON: {exc}")
    if not isinstance(document, dict):
        return JointStatus.fallback(JointState.UNPARSEABLE, "not a JSON object")

    status = document.get("status")
    if status not in KNOWN_JOINT_STATUSES:
        return JointStatus.fallback(JointState.UNKNOWN_STATUS, f"status {status!r} is not known")
    if document.get("structure_status") != _QC_PASSED:
        return JointStatus.fallback(
            JointState.UNKNOWN_STATUS,
            f"structure_status {document.get('structure_status')!r} is not {_QC_PASSED}",
        )
    flags: dict[str, bool] = {}
    for flag in _JOINT_FLAGS:
        value = document.get(flag)
        if not isinstance(value, bool):
            # "true", 1, null or absent: not a statement the gate can rely on.
            return JointStatus.fallback(
                JointState.UNPARSEABLE, f"{flag} is {value!r}, not a boolean"
            )
        flags[flag] = value
    blocks = document.get("matched_blocks")
    if not isinstance(blocks, list) or not all(isinstance(b, str) for b in blocks):
        return JointStatus.fallback(JointState.UNPARSEABLE, "matched_blocks is not a list")
    certified = document.get("panel_sha256")
    if not isinstance(certified, str) or not is_sha256(certified):
        return JointStatus.fallback(JointState.UNPARSEABLE, "panel_sha256 is not a digest")
    if certified != panel_sha256:
        return JointStatus.fallback(
            JointState.NOT_THIS_PANEL,
            f"certifies {certified}, not this panel {panel_sha256}",
        )
    prediction = document.get("prediction_validation_status")
    return JointStatus(
        state=JointState.CERTIFIED,
        detail="certificate binds to this panel",
        certified_panel_sha256=certified,
        status=status,
        matched_blocks=frozenset(blocks),
        prediction_validation_status=prediction if isinstance(prediction, str) else None,
        **flags,
    )


# --------------------------------------------------------------------------- #
# Companion validation
# --------------------------------------------------------------------------- #


def companion_set_sha256(hashes: Mapping[str, str]) -> str:
    """One digest over a companion set: ``asset_id<TAB>sha256`` lines, sorted.

    Recorded on every run binding, so a run names exactly which certificate,
    audit and catalogue its population carried.
    """
    lines = "".join(f"{asset}\t{sha}\n" for asset, sha in sorted(hashes.items()))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CompanionReport:
    """The outcome of validating a companion set against a contract."""

    checks: tuple[tuple[str, bool, str], ...]
    joint: JointStatus
    hashes: Mapping[str, str]

    @property
    def passed(self) -> bool:
        """True only when every companion check passed."""
        return all(passed for _, passed, _ in self.checks)

    @property
    def failures(self) -> tuple[str, ...]:
        """``check: detail`` for every failed check."""
        return tuple(f"{name}: {detail}" for name, passed, detail in self.checks if not passed)

    @property
    def set_sha256(self) -> str:
        """The digest of the validated set."""
        return companion_set_sha256(self.hashes)

    def as_record(self) -> dict[str, Any]:
        """A JSON-serialisable form, stored with the companion set."""
        return {
            "passed": self.passed,
            "set_sha256": self.set_sha256,
            "checks": [{"check": n, "passed": p, "detail": d} for n, p, d in self.checks],
            "joint": self.joint.as_record(),
        }


@dataclass(frozen=True, slots=True)
class CompanionSet:
    """The companion set recorded for a version: what was attached, and where."""

    version_id: str
    set_sha256: str
    joint_state: JointState
    #: asset_id -> (sha256, location)
    assets: Mapping[str, tuple[str, str]]
    attached_at: datetime
    attached_by: str

    @property
    def hashes(self) -> dict[str, str]:
        """asset_id -> sha256."""
        return {asset: sha for asset, (sha, _) in self.assets.items()}


def _csv_rows(data: bytes) -> tuple[list[str], list[dict[str, str]]] | str:
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        return f"not readable CSV: {exc}"
    return list(reader.fieldnames or []), rows


def validate_companions(
    specs: Sequence[CompanionSpec],
    *,
    assets: Mapping[str, bytes],
    panel: ParsedPanel,
    panel_sha256: str,
    field_count: int,
    joint_must_certify: bool,
) -> CompanionReport:
    """Judge a companion set. Never raises for a bad asset; every check is reported.

    ``joint_must_certify`` is True for the version the contract names as certified
    (``v17_4_0``). For any other version a non-binding certificate is correct and
    recorded -- its joint permissions are the fallback -- rather than an error.
    """
    checks: list[tuple[str, bool, str]] = []
    hashes: dict[str, str] = {}
    joint = JointStatus.fallback(JointState.MISSING, "the contract declares no certificate")

    declared = {s.asset_id for s in specs}
    for extra in sorted(set(assets) - declared):
        checks.append((f"companions.{extra}.declared", False, "not a declared companion"))

    for spec in specs:
        name = f"companions.{spec.asset_id}"
        data = assets.get(spec.asset_id)
        if data is None:
            checks.append((f"{name}.present", False, "missing"))
            if spec.kind is CompanionKind.CORE_JOINT_STATUS:
                joint = JointStatus.fallback(JointState.MISSING, "certificate missing")
            continue
        sha = content_sha256(data)
        hashes[spec.asset_id] = sha
        checks.append(
            (f"{name}.checksum", sha == spec.sha256, f"expected {spec.sha256}, got {sha}")
        )
        checks.append(
            (
                f"{name}.byte_size",
                len(data) == spec.byte_size,
                f"expected {spec.byte_size}, got {len(data)}",
            )
        )

        if spec.fmt == "csv":
            parsed = _csv_rows(data)
            if isinstance(parsed, str):
                checks.append((f"{name}.readable", False, parsed))
                continue
            header, rows = parsed
            if spec.rows is not None:
                checks.append(
                    (
                        f"{name}.rows",
                        len(rows) == spec.rows,
                        f"expected {spec.rows}, got {len(rows)}",
                    )
                )
            if spec.columns is not None:
                checks.append(
                    (
                        f"{name}.columns",
                        len(header) == spec.columns,
                        f"expected {spec.columns}, got {len(header)}",
                    )
                )
            if spec.kind is CompanionKind.DIMENSION_SCORECARD:
                checks.append(
                    (
                        f"{name}.one_row_per_field",
                        len(rows) == field_count,
                        f"{len(rows)} rows for {field_count} fields",
                    )
                )
            if spec.kind is CompanionKind.RESPONDENT_AUDIT:
                checks.append(
                    (
                        f"{name}.one_row_per_respondent",
                        len(rows) == panel.row_count,
                        f"{len(rows)} rows for {panel.row_count} respondents",
                    )
                )
            if spec.panel_column_field is not None:
                if spec.panel_column_field not in header:
                    checks.append(
                        (f"{name}.panel_columns", False, f"no {spec.panel_column_field!r} column")
                    )
                else:
                    unknown = sorted({r[spec.panel_column_field] for r in rows} - set(panel.header))
                    checks.append(
                        (
                            f"{name}.panel_columns",
                            not unknown,
                            f"not panel columns: {unknown[:5]}" if unknown else "all panel columns",
                        )
                    )
            if spec.status_column is not None:
                if spec.status_column not in header:
                    checks.append((f"{name}.status", False, f"no {spec.status_column!r} column"))
                else:
                    bad = sum(1 for r in rows if r[spec.status_column] == spec.forbidden_status)
                    checks.append(
                        (
                            f"{name}.status",
                            bad == 0,
                            f"{bad} rows with {spec.status_column} = {spec.forbidden_status}",
                        )
                    )

        if spec.kind is CompanionKind.CORE_JOINT_STATUS:
            joint = evaluate_joint_certificate(data, panel_sha256=panel_sha256)
            if joint_must_certify:
                checks.append((f"{name}.certifies_panel", joint.certified, joint.detail))
            else:
                checks.append(
                    (
                        f"{name}.certifies_panel",
                        True,
                        f"not required for this version; joint claims fall back ({joint.detail})",
                    )
                )

    return CompanionReport(checks=tuple(checks), joint=joint, hashes=hashes)
