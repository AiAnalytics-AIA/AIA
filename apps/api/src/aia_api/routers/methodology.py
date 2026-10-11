"""AIA's mathematics, as the Metodika tab shows it: read by any member (ADR 0023).

Organization-level, like the other settings routes: every route takes an
``OrganizationContext``, which carries no client or study and reads no research data.

* ``GET /methodology`` -- every method module: its name, what is in force, its groups.
* ``GET /methodology/{module_id}`` -- one module's steps in computation order, each with its
  formula, symbols, evidence, tests and every value it reads, from the preset in force or
  ``?preset=`` (a value is read from the code by the domain, never stored here).

Nothing here is editable yet: stored methodology versions are chunk A3 of
``methodology-tab.md``. This module only serialises what
:func:`aia_core.domain.methodology.describe` reads.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from aia_core.domain.methodology import (
    ABSENT,
    MODULES,
    MethodModule,
    MethodologyReferenceError,
    StepView,
    describe,
    module,
)
from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict

from ..dependencies import OrganizationDep
from ..schemas.projects import ErrorResponse

router = APIRouter(
    prefix="/methodology",
    tags=["methodology"],
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "No such module or preset"},
    },
)

ModuleId = Annotated[str, Path(max_length=64, pattern=r"^[a-z0-9_]+$")]


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GroupOut(_Strict):
    id: str
    title_cs: str
    step_ids: list[str]
    note_cs: str


class ModuleSummary(_Strict):
    """One module as the tab lists it."""

    id: str
    title_cs: str
    note_cs: str
    presets: list[str]
    in_force: str | None
    steps: int
    groups: list[GroupOut]


class SymbolOut(_Strict):
    latex: str
    meaning_cs: str
    unit: str


class EvidenceOut(_Strict):
    kind: str
    ref: str
    note_cs: str


class ValueOut(_Strict):
    """A value a step reads: where it lives, what it is, and where it comes from.

    ``origin`` is ``specification`` (a field of the module's specification) or
    ``code_constant`` (a module constant, changed only by a code change). ``absent`` is true
    where the preset omits the part the value belongs to; ``value`` is then ``null`` and is
    not a zero.
    """

    reference: str
    label_cs: str
    unit: str
    origin: str
    value: Any
    absent: bool


class StepOut(_Strict):
    id: str
    title_cs: str
    formula_latex: str
    implements: str
    source_sha256: str
    symbols: list[SymbolOut]
    evidence: list[EvidenceOut]
    tests: list[str]
    note_cs: str
    values: list[ValueOut]


class ModuleDetail(ModuleSummary):
    preset: str | None
    step_details: list[StepOut]


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #


def _wire(value: Any) -> Any:
    """Plain JSON: an enum as its value, a tuple as a list, recursively."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple | list):
        return [_wire(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _wire(v) for k, v in value.items()}
    return value


def _summary(m: MethodModule) -> ModuleSummary:
    return ModuleSummary(
        id=m.id,
        title_cs=m.title_cs,
        note_cs=m.note_cs,
        presets=[p.name for p in m.presets],
        in_force=m.in_force,
        steps=len(m.steps),
        groups=[
            GroupOut(id=g.id, title_cs=g.title_cs, step_ids=list(g.step_ids), note_cs=g.note_cs)
            for g in m.groups
        ],
    )


def _step(view: StepView) -> StepOut:
    s = view.step
    return StepOut(
        id=s.id,
        title_cs=s.title_cs,
        formula_latex=s.formula_latex,
        implements=s.implements,
        source_sha256=s.source_sha256,
        symbols=[SymbolOut(latex=y.latex, meaning_cs=y.meaning_cs, unit=y.unit) for y in s.symbols],
        evidence=[EvidenceOut(kind=e.kind.value, ref=e.ref, note_cs=e.note_cs) for e in s.evidence],
        tests=list(s.tests),
        note_cs=s.note_cs,
        values=[
            ValueOut(
                reference=v.reference,
                label_cs=v.label_cs,
                unit=v.unit,
                origin=v.origin.value,
                value=None if v.value is ABSENT else _wire(v.value),
                absent=v.value is ABSENT,
            )
            for v in view.values
        ],
    )


def _not_found(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"code": code, "message": message})


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@router.get("", response_model=list[ModuleSummary], summary="Every method module")
def list_modules(org: OrganizationDep) -> list[ModuleSummary]:
    del org  # any member of the organization reads the methodology
    return [_summary(m) for m in MODULES]


def read_module_detail(module_id: str, preset: str | None = None) -> ModuleDetail:
    """One module as the route serves it; ``KeyError`` / ``MethodologyReferenceError`` when
    the module or preset does not exist. Shared with ``tools/methodology_fixture.py``."""
    found = module(module_id)
    view = describe(found, preset)
    return ModuleDetail(
        **_summary(found).model_dump(),
        preset=view.preset,
        step_details=[_step(s) for s in view.steps],
    )


@router.get("/{module_id}", response_model=ModuleDetail, summary="One module, step by step")
def read_module(
    module_id: ModuleId,
    org: OrganizationDep,
    preset: Annotated[str | None, Query(max_length=64)] = None,
) -> ModuleDetail:
    del org
    try:
        return read_module_detail(module_id, preset)
    except KeyError as exc:
        raise _not_found("unknown_module", f"no method module {module_id!r}") from exc
    except MethodologyReferenceError as exc:
        raise _not_found("unknown_preset", str(exc)) from exc
