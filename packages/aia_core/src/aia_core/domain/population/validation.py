"""Import validation: every check in the import contract, all run, all reported.

``data-import-contracts/czech-population.md`` VALIDATION lists what must hold
before an import is accepted. Every check runs even after one fails, so a rejected
bundle is rejected with its full list of defects rather than one per attempt.

Lineage against the *registry* (does the parent exist, is the label already taken
by other bytes) is not decided here: it needs the registry, and is checked by the
application service before anything is written. What is decided here is everything
that can be judged from the bundle and the contract alone.

Companion assets (dimension scorecard, persona catalogue, respondent audit, the
``CORE_JOINT_STATUS.json`` certificate) are **not** validated by this function.
The report says so explicitly -- :attr:`ImportReport.companions_validated` is
``False`` -- rather than implying a completeness it does not have.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from .contract import PopulationImportContract, field_names_fingerprint
from .policy import POLICY_COLUMNS, build_field_policy
from .table import ParsedDictionary, ParsedPanel
from .weights import parse_weight

__all__ = ["CheckResult", "ImportReport", "validate_import"]


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One named check and its outcome."""

    check: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ImportReport:
    """The outcome of validating one bundle against one contract."""

    contract_id: str
    label: str
    content_sha256: str
    checks: tuple[CheckResult, ...]
    #: Companion assets are a later chunk. Never True until they are checked.
    companions_validated: bool = False

    @property
    def passed(self) -> bool:
        """True only when every check passed."""
        return all(c.passed for c in self.checks)

    @property
    def failures(self) -> tuple[str, ...]:
        """``check: detail`` for every failed check."""
        return tuple(f"{c.check}: {c.detail}" for c in self.checks if not c.passed)

    def as_record(self) -> dict[str, object]:
        """A JSON-serialisable form, stored with the version it validated."""
        return {
            "contract_id": self.contract_id,
            "label": self.label,
            "content_sha256": self.content_sha256,
            "passed": self.passed,
            "companions_validated": self.companions_validated,
            "checks": [
                {"check": c.check, "passed": c.passed, "detail": c.detail} for c in self.checks
            ],
        }


def validate_import(
    contract: PopulationImportContract,
    *,
    label: str,
    panel_sha256: str,
    panel_byte_size: int,
    dictionary_sha256: str,
    dictionary: ParsedDictionary,
    panel: ParsedPanel,
) -> ImportReport:
    """Judge one bundle against ``contract``. Never raises for a bad bundle."""
    checks: list[CheckResult] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append(CheckResult(name, passed, detail))

    # -- identity ---------------------------------------------------------------
    known = contract.known_version(label)
    by_sha = contract.known_version_by_sha(panel_sha256)
    if known is not None:
        check(
            "identity.checksum",
            known.sha256 == panel_sha256,
            f"{label} must hash to {known.sha256}; got {panel_sha256}",
        )
        check(
            "identity.byte_size",
            known.byte_size == panel_byte_size,
            f"{label} must be {known.byte_size} bytes; got {panel_byte_size}",
        )
    else:
        check("identity.checksum", True, f"{label} is not a preserved version; lineage required")
    if by_sha is not None and by_sha.label != label:
        check(
            "identity.distinct_labels",
            False,
            f"these bytes are {by_sha.label}; they cannot be imported as {label}",
        )
    else:
        check("identity.distinct_labels", True, "label and bytes agree")

    # -- the dictionary ---------------------------------------------------------
    fields = dictionary.fields
    check(
        "dictionary.checksum",
        dictionary_sha256 == contract.dictionary_sha256,
        f"dictionary must hash to {contract.dictionary_sha256}; got {dictionary_sha256}",
    )
    check(
        "dictionary.field_count",
        len(fields) == contract.field_count,
        f"expected {contract.field_count} fields; dictionary declares {len(fields)}",
    )
    duplicated = sorted(n for n, k in Counter(fields).items() if k > 1)
    check(
        "dictionary.unique_fields",
        not duplicated,
        f"duplicated dictionary fields: {duplicated}" if duplicated else "unique",
    )
    fingerprint = field_names_fingerprint(fields)
    check(
        "dictionary.field_names",
        fingerprint == contract.field_names_sha256,
        f"ordered field names must fingerprint to {contract.field_names_sha256}; got {fingerprint}",
    )

    # -- the field policy the dictionary states --------------------------------
    missing_policy_columns = [c for c in POLICY_COLUMNS if c not in dictionary.columns]
    if missing_policy_columns:
        check(
            "dictionary.policy_mapped",
            False,
            f"the dictionary lacks the policy columns {missing_policy_columns}",
        )
    else:
        policy = build_field_policy(
            dictionary.rows,
            dictionary_sha256=dictionary_sha256,
            weight_columns=contract.weight_columns,
        )
        unmapped = policy.unmapped
        check(
            "dictionary.policy_mapped",
            not unmapped,
            (
                f"{len(unmapped)} fields have unmapped policy, e.g. "
                f"{unmapped[0].field}: {'; '.join(unmapped[0].unmapped)}"
                if unmapped
                else f"all {len(policy.entries)} fields map to {policy.version}"
            ),
        )

    # -- the header against the dictionary -------------------------------------
    header = panel.header
    check(
        "schema.column_count",
        len(header) == contract.field_count,
        f"expected {contract.field_count} columns; panel has {len(header)}",
    )
    header_dupes = sorted(n for n, k in Counter(header).items() if k > 1)
    check(
        "schema.unique_columns",
        not header_dupes,
        f"duplicated columns: {header_dupes}" if header_dupes else "unique",
    )
    check("schema.columns_in_order", header == fields, _first_difference(header, fields))
    prefixed = sorted(n for n in header if n.startswith(contract.forbidden_prefixes))
    check(
        "schema.forbidden_prefixes",
        not prefixed,
        f"columns with forbidden prefixes: {prefixed}" if prefixed else "none",
    )
    derived_in_source = sorted(f.name for f in contract.derived_fields if f.name in set(header))
    check(
        "schema.derived_not_in_source",
        not derived_in_source,
        (
            f"runtime-derived fields present in the source: {derived_in_source}"
            if derived_in_source
            else "the source carries no derived runtime field"
        ),
    )
    missing_text = sorted(f for f in contract.text_fields if not panel.has(f))
    check(
        "schema.text_fields_present",
        not missing_text,
        f"text fields missing: {missing_text}" if missing_text else "present",
    )

    # -- rows and key -----------------------------------------------------------
    check(
        "rows.count",
        panel.row_count == contract.expected_rows,
        f"expected {contract.expected_rows} rows; panel has {panel.row_count}",
    )
    if panel.has(contract.primary_key):
        keys = panel.column(contract.primary_key)
        null_keys = sum(1 for k in keys if k is None)
        dup_keys = sum(1 for k, n in Counter(k for k in keys if k is not None).items() if n > 1)
        check(
            "rows.primary_key",
            null_keys == 0 and dup_keys == 0,
            f"{contract.primary_key}: {null_keys} null, {dup_keys} duplicated values",
        )
    else:
        check("rows.primary_key", False, f"{contract.primary_key} is not a column")

    # -- weights ----------------------------------------------------------------
    for scheme in contract.weight_schemes:
        name = f"weights.{scheme.role}"
        if not panel.has(scheme.column):
            check(f"{name}.present", False, f"{scheme.column} is not a column")
            continue
        check(f"{name}.present", True, scheme.column)
        values: list[float] = []
        malformed = 0
        for cell in panel.column(scheme.column):
            if cell is None:
                continue
            try:
                values.append(parse_weight(cell))
            except ValueError:
                malformed += 1
        check(
            f"{name}.parseable",
            malformed == 0,
            f"{scheme.column}: {malformed} malformed, non-finite or negative values",
        )
        if scheme.expected_total is not None and scheme.tolerance is not None:
            total = math.fsum(values)
            check(
                f"{name}.total",
                abs(total - scheme.expected_total) <= scheme.tolerance,
                f"{scheme.column} sums to {total!r}; expected "
                f"{scheme.expected_total!r} ± {scheme.tolerance!r}",
            )

    return ImportReport(
        contract_id=contract.contract_id,
        label=label,
        content_sha256=panel_sha256,
        checks=tuple(checks),
    )


def _first_difference(header: tuple[str, ...], fields: tuple[str, ...]) -> str:
    for position, (have, want) in enumerate(zip(header, fields, strict=False)):
        if have != want:
            return f"column {position} is {have!r}; the dictionary declares {want!r}"
    if len(header) != len(fields):
        return f"header has {len(header)} names; the dictionary declares {len(fields)}"
    return "header equals the dictionary, in order"
