"""A materialized dimension: the contract extension and the fixed policy of its field.

Population-operations P4 (owner, 2026-10-12): an accepted dimension becomes respondent
values as a **child** :class:`~.versions.DatasetVersion` -- the base version's panel plus
one column per materialized field, the base as its parent -- owned by the organization
and client it was materialized for (M1, M5). The import contract stays pinned to the
base's 400 fields by hash; what a child adds is declared here, in a
:class:`PopulationContractExtension` that is itself pinned by hash and names, per field,
the dimension definition it came from and the method that wrote its values.

Every materialized value is modelled, never measured (M2), and its uses are fixed rather
than read from a dictionary row (M3): persona construction, audience filtering, simulation
and internal aggregate analysis; a client-facing claim only as a disclosed, aggregate,
modelled claim; never a measured claim and never weighting. That policy is one
:class:`~.policy.FieldPolicyEntry`, so :meth:`~.policy.FieldPolicy.decide` answers for a
materialized field through the same rules as every other field.

Nothing here performs I/O.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from .contract import field_names_fingerprint
from .errors import VersionIntegrityError
from .policy import (
    ClaimRule,
    ClientClaimPermit,
    FieldPolicy,
    FieldPolicyEntry,
    ProvenanceClass,
)
from .versions import DatasetVersion, is_sha256

__all__ = [
    "EXTENSION_CONTRACT",
    "MATERIALIZED_BLOCK",
    "MATERIALIZE_PROJECT_OWNER",
    "MaterializedField",
    "MaterializedKind",
    "PopulationContractExtension",
    "check_child_version",
    "materialized_policy_entry",
    "with_materialized_fields",
]

#: The version of this extension's stored form; part of its hash.
EXTENSION_CONTRACT: Final = "population-extension/v1"

#: The block every materialized field is reported under.
MATERIALIZED_BLOCK: Final = "materialized"

#: The owner of a study's population project (``projects.owner``): the project a materialize
#: run hangs off. No generic project route sees it.
MATERIALIZE_PROJECT_OWNER: Final = "study_population"

# 18.6.6 sanitised a dimension id to lowercase letters, digits and underscores
# (audience_dimensions.py:315); a materialized column name is that id.
_FIELD_NAME = re.compile(r"^[a-z0-9_]+$")


class MaterializedKind(StrEnum):
    """What a materialized field holds (18.6.6's two supported kinds)."""

    #: 0 or 1 per respondent, filled to a weighted target prevalence.
    BINARY = "binary"
    #: 1-10 per respondent, shifted to a target mean.
    SCALE_1_10 = "scale_1_10"


@dataclass(frozen=True, slots=True)
class MaterializedField:
    """One column a child version adds, and what it was made from."""

    name: str
    kind: MaterializedKind
    #: The SHA256 of the immutable dimension definition (K5's output) it implements.
    definition_sha256: str
    #: The derivation that wrote its values, by id and version.
    method_id: str
    method_version: str

    def __post_init__(self) -> None:
        if not _FIELD_NAME.match(self.name):
            raise ValueError(
                f"materialized field {self.name!r} must be lowercase letters, digits and "
                "underscores"
            )
        if not is_sha256(self.definition_sha256):
            raise ValueError("definition_sha256 must be a lowercase sha256 digest")
        if not self.method_id or not self.method_version:
            raise ValueError(f"materialized field {self.name} names its method and version")

    def payload(self) -> dict[str, str]:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "definition_sha256": self.definition_sha256,
            "method_id": self.method_id,
            "method_version": self.method_version,
        }


@dataclass(frozen=True, slots=True)
class PopulationContractExtension:
    """The fields a child version adds to its base, pinned by hash.

    The base contract still judges the base's own fields; the extension names exactly
    which base it extends (contract id, ordered field names, dictionary) and what is
    added after them, in order.
    """

    base_contract_id: str
    base_field_names_sha256: str
    base_dictionary_sha256: str
    fields: tuple[MaterializedField, ...]

    def __post_init__(self) -> None:
        if not self.base_contract_id:
            raise ValueError("an extension names the contract it extends")
        for name in ("base_field_names_sha256", "base_dictionary_sha256"):
            if not is_sha256(getattr(self, name)):
                raise ValueError(f"{name} must be a lowercase sha256 digest")
        if not self.fields:
            raise ValueError("an extension adds at least one field")
        names = [f.name for f in self.fields]
        if len(set(names)) != len(names):
            raise ValueError("an extension adds each field once")

    def payload(self) -> dict[str, Any]:
        """The stored form, in a fixed order: what :attr:`sha256` is the hash of."""
        return {
            "contract": EXTENSION_CONTRACT,
            "base_contract_id": self.base_contract_id,
            "base_field_names_sha256": self.base_field_names_sha256,
            "base_dictionary_sha256": self.base_dictionary_sha256,
            "fields": [f.payload() for f in self.fields],
        }

    @property
    def sha256(self) -> str:
        """The extension's identity: the SHA256 of its canonical JSON."""
        text = json.dumps(self.payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @classmethod
    def from_payload(cls, payload: Any) -> PopulationContractExtension:
        """Read a stored extension; refuse any other contract or shape."""
        if not isinstance(payload, dict) or payload.get("contract") != EXTENSION_CONTRACT:
            raise VersionIntegrityError(f"not a {EXTENSION_CONTRACT} extension")
        try:
            return cls(
                base_contract_id=str(payload["base_contract_id"]),
                base_field_names_sha256=str(payload["base_field_names_sha256"]),
                base_dictionary_sha256=str(payload["base_dictionary_sha256"]),
                fields=tuple(
                    MaterializedField(
                        name=str(f["name"]),
                        kind=MaterializedKind(f["kind"]),
                        definition_sha256=str(f["definition_sha256"]),
                        method_id=str(f["method_id"]),
                        method_version=str(f["method_version"]),
                    )
                    for f in payload["fields"]
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise VersionIntegrityError(f"the stored extension does not read: {exc}") from None

    def field_names(self, base_field_names: Sequence[str]) -> tuple[str, ...]:
        """The child's ordered field names: the base's, unchanged, then the added ones.

        Refused when ``base_field_names`` is not the base this extension names, or when an
        added field would shadow a base field.
        """
        if field_names_fingerprint(base_field_names) != self.base_field_names_sha256:
            raise VersionIntegrityError("these are not the field names this extension extends")
        clash = sorted({f.name for f in self.fields} & set(base_field_names))
        if clash:
            raise VersionIntegrityError(
                f"a materialized field may not replace a base field: {', '.join(clash)}"
            )
        return (*base_field_names, *(f.name for f in self.fields))


def materialized_policy_entry(field: MaterializedField) -> FieldPolicyEntry:
    """The fixed policy of a materialized field (P4, M3).

    Its value is a model's, person by person (``PERSON_VALUE_MODELED``), so every use the
    existing rules allow carries the aggregate-only obligation, a client may be told it
    only as a disclosed modelled aggregate, and it is never a measured claim. There is no
    production grade: the owner's M3 decision, not a dictionary grade, is what permits the
    disclosed modelled claim.
    """
    return FieldPolicyEntry(
        field=field.name,
        block=MATERIALIZED_BLOCK,
        source=f"materialized:{field.method_id}@{field.method_version}",
        evidence_status="",
        provenance_class=ProvenanceClass.MODELLED,
        production_grade="",
        recommended_use="",
        persona_eligible=True,
        claim_rules=frozenset(
            {ClaimRule.PERSON_VALUE_MODELED, ClaimRule.REQUIRES_MODELED_DISCLOSURE}
        ),
        client_permit=ClientClaimPermit.MODELLED_AGGREGATE,
        is_weight=False,
    )


def with_materialized_fields(
    policy: FieldPolicy, extension: PopulationContractExtension
) -> FieldPolicy:
    """The base's policy plus every field the extension adds; a collision is refused."""
    entries = dict(policy.entries)
    for added in extension.fields:
        if added.name in entries:
            raise VersionIntegrityError(
                f"materialized field {added.name} collides with a field the base already has"
            )
        entries[added.name] = materialized_policy_entry(added)
    return FieldPolicy(
        version=policy.version, dictionary_sha256=policy.dictionary_sha256, entries=entries
    )


def check_child_version(
    *,
    base: DatasetVersion,
    child: DatasetVersion,
    extension: PopulationContractExtension,
    base_field_names: Sequence[str],
) -> None:
    """Refuse a child that is not exactly ``base`` extended by ``extension``.

    The child must be owned, name the base as its parent and the extension by hash, keep
    the base's dataset, contract, dictionary and rows, and carry the base's fields in order
    followed by the added ones. The base must be shared: a child is never built on another
    organization's child.
    """
    problems: list[str] = []
    if not base.shared:
        problems.append("the base is itself an owned version")
    if child.shared:
        problems.append("a materialized child names its owner")
    if child.parent_version_id != base.version_id:
        problems.append("the child's parent is not the base")
    if child.dataset_id != base.dataset_id:
        problems.append("the child belongs to another dataset")
    if extension.base_contract_id != base.contract_id or child.contract_id != base.contract_id:
        problems.append("the extension, the child and the base name different contracts")
    if extension.base_dictionary_sha256 != base.dictionary_sha256:
        problems.append("the extension names another dictionary")
    if child.dictionary_sha256 != base.dictionary_sha256:
        problems.append("the child's dictionary is not the base's")
    if child.extension_sha256 != extension.sha256:
        problems.append("the child names another extension")
    if child.row_count != base.row_count:
        problems.append("the child's rows are not the base's")
    if child.column_count != base.column_count + len(extension.fields):
        problems.append("the child's column count is not the base's plus the added fields")
    if base.field_names_sha256 != extension.base_field_names_sha256:
        problems.append("the extension extends other field names than the base's")
    else:
        names = extension.field_names(base_field_names)
        if child.field_names_sha256 != field_names_fingerprint(names):
            problems.append("the child's fields are not the base's followed by the added ones")
    if problems:
        raise VersionIntegrityError(
            f"{child.version_id} is not {base.version_id} extended: " + "; ".join(problems)
        )
