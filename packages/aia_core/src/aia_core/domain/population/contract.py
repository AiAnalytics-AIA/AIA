"""The import contract: what a dataset version must be before it is accepted.

A contract is data, not code paths. It names the expected schema, the preserved
versions and their lineage, the declared weight schemes and the derived runtime
fields, and :func:`~aia_core.domain.population.validation.validate_import` judges
a bundle against it. Tests build small synthetic contracts through the same type;
production uses :data:`~aia_core.domain.population.czech.CZ_SYNTHETIC_V17`.

**The schema is pinned by hash, not copied.** The 400-field dictionary is detailed
reference material and stays in ``AiAnalytics-AIA/AIA-reference``. A contract pins
the dictionary file's SHA256 and a fingerprint of its ordered field names; the
dictionary travels with the panel in the import bundle and is checked against both.
A dictionary that is edited, reordered, truncated or swapped fails the import.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from .errors import WeightResolutionError
from .versions import is_sha256

__all__ = [
    "DerivedField",
    "DerivedOrigin",
    "KnownVersion",
    "PopulationImportContract",
    "WeightScheme",
    "field_names_fingerprint",
]


def field_names_fingerprint(names: Sequence[str]) -> str:
    """Return the SHA256 of the ordered field names, newline-joined, UTF-8.

    Order is part of the fingerprint on purpose: the import contract requires the
    panel header to equal the dictionary *in order*.
    """
    return hashlib.sha256("\n".join(names).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class KnownVersion:
    """A preserved version whose bytes and parent are fact, not caller input."""

    label: str
    sha256: str
    byte_size: int
    parent_label: str | None = None

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("a known version needs a label")
        if not is_sha256(self.sha256):
            raise ValueError(f"known version {self.label} needs a lowercase sha256")
        if self.byte_size <= 0:
            raise ValueError(f"known version {self.label} needs a positive byte size")
        if self.parent_label == self.label:
            raise ValueError(f"known version {self.label} cannot be its own parent")


@dataclass(frozen=True, slots=True)
class WeightScheme:
    """One declared weighting scheme: a role name bound to exactly one column.

    ``expected_total`` and ``tolerance`` are set only where the reference's own
    validation declared a population total. Where it declared none, none is
    invented: an unasserted property stays unasserted.
    """

    role: str
    column: str
    expected_total: float | None = None
    tolerance: float | None = None

    def __post_init__(self) -> None:
        if not self.role or not self.column:
            raise ValueError("a weight scheme needs a role and a column")
        if (self.expected_total is None) != (self.tolerance is None):
            raise ValueError(f"weight scheme {self.role}: total and tolerance go together")
        if self.tolerance is not None and self.tolerance < 0:
            raise ValueError(f"weight scheme {self.role}: tolerance cannot be negative")


class DerivedOrigin(StrEnum):
    """How a runtime field that is not in the source dictionary comes to exist."""

    #: Computed at load time from source fields by the configured enricher.
    ENRICHMENT = "ENRICHMENT"
    #: The canonical analysis weight, copied from the resolved weight scheme.
    ANALYSIS_WEIGHT = "ANALYSIS_WEIGHT"


@dataclass(frozen=True, slots=True)
class DerivedField:
    """A runtime field with no dictionary entry.

    It is named here so that nothing can pretend it is one of the source fields:
    it carries no ``evidence_status``, no ``production_grade`` and no claim rule.
    Until the data owner classifies it, it may not back a client-facing claim.
    """

    name: str
    origin: DerivedOrigin

    @property
    def in_source_dictionary(self) -> bool:
        """Always False. The source dictionary is exactly the source fields."""
        return False

    @property
    def client_claims_allowed(self) -> bool:
        """Always False until classified. Unclassified is never scored as allowed."""
        return False


@dataclass(frozen=True, slots=True)
class PopulationImportContract:
    """Everything an import is judged against, for one dataset."""

    contract_id: str
    dataset_id: str
    field_count: int
    field_names_sha256: str
    dictionary_sha256: str
    primary_key: str
    expected_rows: int
    weight_schemes: tuple[WeightScheme, ...]
    default_weight_role: str
    known_versions: tuple[KnownVersion, ...]
    static_reference_label: str
    enrichment_fields: tuple[str, ...]
    analysis_weight_field: str = "_analysis_weight"
    #: Fields whose values must never be numerically coerced by any typed view.
    text_fields: frozenset[str] = field(default_factory=frozenset)
    #: No source column may start with one of these.
    forbidden_prefixes: tuple[str, ...] = ()
    #: The column in the dictionary CSV that names each field.
    dictionary_field_column: str = "field"

    def __post_init__(self) -> None:
        if not self.contract_id or not self.dataset_id:
            raise ValueError("a contract needs an id and a dataset id")
        if self.field_count <= 0 or self.expected_rows <= 0:
            raise ValueError("a contract needs positive field and row counts")
        for name in ("field_names_sha256", "dictionary_sha256"):
            if not is_sha256(getattr(self, name)):
                raise ValueError(f"{name} must be a lowercase sha256 digest")
        if not self.primary_key:
            raise ValueError("a contract needs a primary key")

        roles = [s.role for s in self.weight_schemes]
        if len(set(roles)) != len(roles):
            raise ValueError("weight roles must be unique")
        columns = [s.column for s in self.weight_schemes]
        if len(set(columns)) != len(columns):
            raise ValueError("a weight column may back only one role")
        if self.default_weight_role not in roles:
            raise ValueError(f"default weight role {self.default_weight_role!r} is not declared")

        labels = [v.label for v in self.known_versions]
        hashes = [v.sha256 for v in self.known_versions]
        if len(set(labels)) != len(labels) or len(set(hashes)) != len(hashes):
            # Two labels for one hash would collapse versions that must stay distinct.
            raise ValueError("known versions must have distinct labels and distinct hashes")
        for version in self.known_versions:
            if version.parent_label is not None and version.parent_label not in labels:
                raise ValueError(f"{version.label} names unknown parent {version.parent_label}")
        if self.static_reference_label not in labels:
            raise ValueError("the static reference must be a known version")

        derived = [*self.enrichment_fields, self.analysis_weight_field]
        if len(set(derived)) != len(derived):
            raise ValueError("derived field names must be unique")

    # ----------------------------------------------------------------- lookups

    def weight_scheme(self, role: str) -> WeightScheme:
        """Return the scheme declared for ``role``. There is no fallback role."""
        for scheme in self.weight_schemes:
            if scheme.role == role:
                return scheme
        raise WeightResolutionError(
            f"weight role {role!r} is not declared by {self.contract_id}; declared roles "
            f"are {sorted(s.role for s in self.weight_schemes)}",
            reason="unknown_weight_role",
        )

    def known_version(self, label: str) -> KnownVersion | None:
        """Return the preserved version named ``label``, if there is one."""
        for version in self.known_versions:
            if version.label == label:
                return version
        return None

    def known_version_by_sha(self, sha256: str) -> KnownVersion | None:
        """Return the preserved version with these bytes, if there is one."""
        for version in self.known_versions:
            if version.sha256 == sha256:
                return version
        return None

    @property
    def derived_fields(self) -> tuple[DerivedField, ...]:
        """The runtime fields that are not source fields, in runtime order."""
        return (
            *(DerivedField(name, DerivedOrigin.ENRICHMENT) for name in self.enrichment_fields),
            DerivedField(self.analysis_weight_field, DerivedOrigin.ANALYSIS_WEIGHT),
        )

    @property
    def derived_policy_fields(self) -> tuple[tuple[str, bool], ...]:
        """``(name, is_weight)`` per derived field, as the field policy takes them."""
        return tuple(
            (d.name, d.origin is DerivedOrigin.ANALYSIS_WEIGHT) for d in self.derived_fields
        )

    @property
    def weight_columns(self) -> tuple[str, ...]:
        """Every declared weight column, in declaration order."""
        return tuple(s.column for s in self.weight_schemes)
