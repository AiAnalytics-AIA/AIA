"""The loaded population: the only shape in which research code sees respondents.

A :class:`RuntimePopulation` is issued only by the canonical loader,
``aia_core.application.population.PopulationRuntime``, through a module-private
sentinel -- the same construction that makes ``StudyContext`` unforgeable. That is
what "one canonical loader" means structurally: there is no second way to obtain
population data in this shape, so the API, a research step and a simulation world
cannot each resolve their own semantics (F10, R4). ``make layer_check`` refuses an
issuance anywhere else.

It carries its :class:`~.binding.PopulationBinding`, so every consumer can record
exactly which version, weight scheme and view its numbers were computed over.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final

from .binding import PopulationBinding, PopulationView
from .companions import JointDecision, JointStatus
from .contract import DerivedField
from .errors import PopulationError
from .policy import FieldPolicy, FieldUse, UsageDecision

__all__ = ["FieldOrigin", "RuntimePopulation"]

# Proof that a RuntimePopulation came from the canonical loader.
_LOADER_ISSUER: Final = object()

Cell = str | None


class FieldOrigin(StrEnum):
    """Where a runtime field comes from. Source fields are in the dictionary."""

    SOURCE = "SOURCE"
    ENRICHMENT = "ENRICHMENT"
    ANALYSIS_WEIGHT = "ANALYSIS_WEIGHT"


@dataclass(frozen=True, slots=True)
class RuntimePopulation:
    """Respondent rows under one binding. Immutable; issued only by the loader."""

    binding: PopulationBinding
    source_fields: tuple[str, ...]
    derived_fields: tuple[DerivedField, ...]
    row_count: int
    #: What each field may be used for, from this version's dictionary.
    field_policy: FieldPolicy = field(repr=False)
    #: What may be claimed jointly, from this version's certificate (or the fallback).
    joint_status: JointStatus = field(repr=False)
    _columns: Mapping[str, tuple[Cell, ...]] = field(repr=False)
    _analysis_weight: tuple[float, ...] | None = field(repr=False)
    _issuer: Any = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._issuer is not _LOADER_ISSUER:
            raise PopulationError(
                "a runtime population may only be issued by the canonical loader",
                reason="forged_population",
            )

    @classmethod
    def _issue(
        cls,
        *,
        binding: PopulationBinding,
        source_fields: tuple[str, ...],
        derived_fields: tuple[DerivedField, ...],
        row_count: int,
        field_policy: FieldPolicy,
        joint_status: JointStatus,
        columns: Mapping[str, tuple[Cell, ...]],
        analysis_weight: tuple[float, ...] | None,
    ) -> RuntimePopulation:
        """Issue a loaded population. Internal to the canonical loader.

        The column mapping is frozen: loads are cached and shared between runs, so
        a consumer that could add or replace a column would change every other
        run's population too. The columns themselves are tuples.
        """
        return cls(
            binding=binding,
            source_fields=source_fields,
            derived_fields=derived_fields,
            row_count=row_count,
            field_policy=field_policy,
            joint_status=joint_status,
            _columns=columns
            if isinstance(columns, MappingProxyType)
            else MappingProxyType(dict(columns)),
            _analysis_weight=analysis_weight,
            _issuer=_LOADER_ISSUER,
        )

    @property
    def view(self) -> PopulationView:
        """The named view this population was loaded as."""
        return self.binding.view

    @property
    def fields(self) -> tuple[str, ...]:
        """Every field in this view, source fields first, in runtime order."""
        return (*self.source_fields, *(d.name for d in self.derived_fields))

    def origin(self, name: str) -> FieldOrigin:
        """Where ``name`` comes from. Raises for a field this view does not carry."""
        if name in self.source_fields:
            return FieldOrigin.SOURCE
        for derived in self.derived_fields:
            if derived.name == name:
                return FieldOrigin(derived.origin.value)
        raise PopulationError(f"{name!r} is not a field of this view", reason="unknown_field")

    def decide(self, name: str, use: FieldUse) -> UsageDecision:
        """May ``name`` serve ``use`` in this view? Never raises.

        A field this view does not carry is ``unknown_field`` even when the version's
        policy knows it -- a BASE-view consumer cannot reason about enrichment.
        """
        if name not in self.fields:
            return UsageDecision(field=name, use=use, allowed=False, reason="unknown_field")
        return self.field_policy.decide(name, use)

    def decide_joint(self, names: Sequence[str], *, client_facing: bool) -> JointDecision:
        """May these fields be used jointly -- a cross-tab, a correlation, a segment?

        Every field must be one this view carries; blocks come from the dictionary.
        The certificate then decides (see ``JointStatus.decide``).
        """
        blocks: dict[str, str] = {}
        for name in names:
            entry = self.field_policy.entry(name)
            if name not in self.fields or entry is None:
                return JointDecision(False, "unknown_field")
            blocks[name] = entry.block or "runtime-derived"
        return self.joint_status.decide(blocks, client_facing=client_facing)

    def column(self, name: str) -> tuple[Cell, ...]:
        """Raw text cells of a source or enrichment field."""
        try:
            return self._columns[name]
        except KeyError:
            raise PopulationError(
                f"{name!r} is not a text field of this view", reason="unknown_field"
            ) from None

    @property
    def analysis_weight(self) -> tuple[float, ...]:
        """The canonical analysis weight. Only the ANALYSIS view carries one."""
        if self._analysis_weight is None:
            raise PopulationError(
                f"the {self.view.value} view carries no analysis weight; load ANALYSIS",
                reason="no_analysis_weight",
            )
        return self._analysis_weight
