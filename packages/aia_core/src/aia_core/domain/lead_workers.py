"""The worker contract: one row defines a worker the Lead may call, once (lead-orchestration LO9a).

``mvp-cohesion.md`` F5, adopted 2026-10-19: MVP-12 (the workers), MVP-32 (every prompt editable and
pinned), the card kinds of ``research-lead-workbench`` 23 and Settings' ``ai_runtime`` document each
described a worker separately. A :class:`LeadWorkerSpec` is that description written once:

* ``worker_id``: the worker's stable id (for the eight design workers, the job's action);
* ``task`` and ``output_contract``: the one closed task it runs and the closed output it returns;
* ``context_layer``: what it is shown (:class:`ContextLayer`);
* ``material_rules``: the rules its material is classed by (``domain/material_rules.py``); the
  request's class is the most restrictive of them, an operator's classification only raising it;
* ``capability``: the logical capability it asks the gateway for, never a model;
* ``reservation_key`` and ``schema_repairs``: the deployment key holding what one job reserves (its
  ceiling, ADR 0028) and the repairs that covers beside the primary request;
* ``prompt_id`` and ``prompt_version``: its prompt (ADR 0020; the organization's active version is
  pinned at enqueue) and the version of the wording this code ships;
* ``switch``: the deployment key that turns it on; off, the job parks and calls nothing;
* ``card_kind`` and ``result_kind``: how a person decides on what it returns, and what that is.

Every field is required and checked when a row is registered (:class:`WorkerRegistry`): a row
with a field missing, empty or of the wrong shape is refused by name, never filled with a default,
because a default here would be a guess about money, class or authority. The fixture the rows are
held to is ``tests/fixtures/lead_workers/workers.json`` (:meth:`LeadWorkerSpec.fixture_row`).

This module is the type and the registration rule only; the eight design workers are rows in
``domain/research_agents.py`` (:data:`~aia_core.domain.research_agents.WORKERS`). The results
workers of LO9b/LO9c (map interpreter, report writer, straight-liner check) join as rows with
their own context layer when that chunk lands; none is declared before it exists. Pure.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .ai_material import most_restrictive_material
from .ai_models import ModelCapability
from .material_rules import MaterialRule, rule_class
from .residency import DataClass

__all__ = [
    "CardKind",
    "ContextLayer",
    "LeadWorkerSpec",
    "ResultKind",
    "WorkerRefused",
    "WorkerRegistry",
]


class ContextLayer(StrEnum):
    """What a worker is shown. One member per context builder that exists."""

    #: The Design Revision's content and the client's approved knowledge, frozen at enqueue
    #: and bounded (``research_agents.context_snapshot``, 64 KB).
    DESIGN_SNAPSHOT = "design_snapshot"


class CardKind(StrEnum):
    """How a person decides on what a worker returns."""

    #: A proposal reviewed inline, accepted (``APPROVE_GATE``), dismissed or rebuilt (ADR 0026
    #: decisions 5, 6 and 8).
    PROPOSAL = "proposal"
    #: An answer to read; nothing is accepted into the design.
    ADVICE = "advice"


class ResultKind(StrEnum):
    """What a worker returns."""

    BRIEF_ANALYSIS = "brief_analysis"
    QUESTIONNAIRE = "questionnaire"
    AUDIENCE = "audience"
    DIMENSIONS = "dimensions"
    ADVICE = "advice"


_ID = r"^[a-z][a-z0-9_]{2,63}$"
_PROMPT_ID = r"^aia(\.[a-z][a-z0-9_]*)+$"
_RESERVATION_KEY = r"^AIA_[A-Z0-9_]+_RESERVATION_USD$"
_SWITCH = r"^AIA_[A-Z0-9_]+_ENABLED$"


class LeadWorkerSpec(BaseModel):
    """One worker the Lead may call, defined once. No field has a default."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    worker_id: str = Field(pattern=_ID)
    task: str = Field(pattern=_ID)
    output_contract: type[BaseModel]
    context_layer: ContextLayer
    material_rules: tuple[MaterialRule, ...] = Field(min_length=1)
    capability: ModelCapability
    reservation_key: str = Field(pattern=_RESERVATION_KEY)
    schema_repairs: int = Field(ge=0, le=2)
    prompt_id: str = Field(pattern=_PROMPT_ID, max_length=128)
    prompt_version: str = Field(pattern=r"^[1-9][0-9]*$")
    switch: str = Field(pattern=_SWITCH)
    card_kind: CardKind
    result_kind: ResultKind

    @field_validator("material_rules")
    @classmethod
    def _distinct_rules(cls, rules: tuple[MaterialRule, ...]) -> tuple[MaterialRule, ...]:
        if len(set(rules)) != len(rules):
            raise ValueError("a material rule is named twice")
        return rules

    @field_validator("output_contract")
    @classmethod
    def _closed_contract(cls, contract: type[BaseModel]) -> type[BaseModel]:
        # A closed task returns a closed output: nothing the contract does not name is kept.
        if contract.model_config.get("extra") != "forbid":
            raise ValueError(f"{contract.__name__} is not a closed contract (extra='forbid')")
        return contract

    @model_validator(mode="after")
    def _card_fits_result(self) -> LeadWorkerSpec:
        advice = self.result_kind is ResultKind.ADVICE
        if advice != (self.card_kind is CardKind.ADVICE):
            raise ValueError("an advice result is read on an advice card, and only there")
        return self

    @property
    def data_class(self) -> DataClass:
        """The most restrictive class its rules can give its material, before an operator's
        classification raises it: what a route must be approved for to carry every job of it."""
        known = most_restrictive_material([rule_class(r) for r in self.material_rules])
        assert known is not None  # every rule has a class, and there is at least one
        return known

    def fixture_row(self) -> dict[str, Any]:
        """The row as the fixture holds it: plain JSON, the contract by its class name."""
        row = self.model_dump(mode="json", exclude={"output_contract"})
        row["output_contract"] = self.output_contract.__name__
        return {f: row[f] for f in FIELDS}


#: The fields a row must carry, in the fixture's order.
FIELDS: Final[tuple[str, ...]] = tuple(LeadWorkerSpec.model_fields)


class WorkerRefused(ValueError):
    """A row was refused at registration; ``fields`` names what was missing or wrong."""

    def __init__(self, worker: str, fields: Iterable[str], why: str) -> None:
        self.worker = worker
        self.fields = tuple(fields)
        super().__init__(f"worker {worker!r} refused: {why}")


def _spec(row: LeadWorkerSpec | Mapping[str, Any]) -> LeadWorkerSpec:
    if isinstance(row, LeadWorkerSpec):
        return row
    name = str(row.get("worker_id") or "?")
    missing = [f for f in FIELDS if f not in row]
    if missing:
        raise WorkerRefused(name, missing, f"missing {', '.join(missing)}")
    try:
        return LeadWorkerSpec.model_validate(dict(row))
    except ValidationError as exc:
        wrong = sorted({str(e["loc"][0]) for e in exc.errors() if e["loc"]})
        raise WorkerRefused(name, wrong, str(exc)) from exc


class WorkerRegistry(Mapping[str, LeadWorkerSpec]):
    """The workers, by id. Registration refuses a row with any field missing or wrong, and two
    rows with one id or one prompt (a prompt is pinned per worker, ADR 0020)."""

    def __init__(self, rows: Iterable[LeadWorkerSpec | Mapping[str, Any]] = ()) -> None:
        self._rows: dict[str, LeadWorkerSpec] = {}
        for row in rows:
            self.register(row)

    def register(self, row: LeadWorkerSpec | Mapping[str, Any]) -> LeadWorkerSpec:
        spec = _spec(row)
        if spec.worker_id in self._rows:
            raise WorkerRefused(spec.worker_id, ["worker_id"], "the id is registered already")
        if any(r.prompt_id == spec.prompt_id for r in self._rows.values()):
            raise WorkerRefused(spec.worker_id, ["prompt_id"], "another worker has this prompt")
        self._rows[spec.worker_id] = spec
        return spec

    def __getitem__(self, worker_id: str) -> LeadWorkerSpec:
        return self._rows[worker_id]

    def __iter__(self) -> Iterator[str]:
        return iter(self._rows)

    def __len__(self) -> int:
        return len(self._rows)

    def fixture(self) -> list[dict[str, Any]]:
        """Every row as the fixture holds it, in registration order."""
        return [r.fixture_row() for r in self._rows.values()]
