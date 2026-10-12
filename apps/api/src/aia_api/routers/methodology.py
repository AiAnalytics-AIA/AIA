"""AIA's mathematics, as the Metodika tab shows it: read by any member (ADR 0023).

Organization-level, like the other settings routes: every route takes an
``OrganizationContext``, which carries no client or study and reads no research data.

* ``GET /methodology`` -- every method module: its name, what is in force, its groups.
* ``GET /methodology/{module_id}`` -- one module's steps in computation order, each with its
  formula, symbols, evidence, tests and every value it reads, from the code's preset or
  ``?preset=`` (a value is read from the code by the domain, never stored here).
* ``GET /methodology/{module_id}/versions`` -- what is in force (a stored version or the
  code's preset), every stored version and the activation log (chunk A5b).
* ``POST /methodology/{module_id}/check`` -- validate an edit without storing it: every problem
  at once, and the formulas the engine would not yet compute.
* ``POST /methodology/{module_id}/compare`` -- the edit beside the methodology in force on
  fixed fictional panels (plan S4b): maps, Stress-1, status changes, shifts, heights, K100,
  terrain. Nothing stored; any member.
* ``POST /methodology/{module_id}/versions`` -- store an edit as the next version (an
  administrator); it is not in force until put.
* ``PUT /methodology/{module_id}/activation`` -- put a version in force, or with
  ``version_number: null`` return to the code's preset (an administrator). A run started
  afterwards pins it; a run already started keeps its pin.

The catalogue is serialised from :func:`aia_core.domain.methodology.describe`; versions are
validated by the domain and stored only by
:mod:`aia_core.infrastructure.methodology_repository`.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Final

from aia_core.domain.methodology import (
    ABSENT,
    MODULES,
    BuiltinFormula,
    MethodModule,
    MethodologyReferenceError,
    StepView,
    describe,
    module,
)
from aia_core.domain.methodology.expressions import compile_formula, latex
from aia_core.domain.methodology.pins import uncomputed_formulas
from aia_core.domain.methodology.sociomap_check import PanelComparison, compare_with_in_force
from aia_core.domain.methodology.support_check import (
    SupportComparison,
    compare_support_with_in_force,
)
from aia_core.domain.methodology.versions import (
    MethodologyVersionInvalid,
    named,
    validate_version,
    version_payload,
)
from aia_core.domain.scope import ScopeDenied
from aia_core.infrastructure.methodology_repository import (
    Activation,
    InForce,
    MethodologyReader,
    MethodologyRefused,
    MethodologyRepository,
    StoredVersion,
)
from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import OrganizationDep, SessionDep
from ..schemas.projects import ErrorResponse

router = APIRouter(
    prefix="/methodology",
    tags=["methodology"],
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Not an organization administrator"},
        404: {"model": ErrorResponse, "description": "No such module, preset or version"},
    },
)

#: How a refusal reads on the wire. Anything not listed is the caller's input: 422.
_STATUS: dict[str, int] = {
    "unknown_module": 404,
    "unknown_version": 404,
    "concurrent_edit": 409,
    "formula_not_computed": 409,
    "version_missing": 409,
}

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
    #: Whether a version of it may be stored (the reference map is shown, never edited).
    editable: bool
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


class FormulaVariableOut(_Strict):
    name: str
    latex: str
    meaning_cs: str
    unit: str
    vector: bool


class FormulaPropertyOut(_Strict):
    kind: str
    variable: str | None
    description_cs: str


class FormulaOut(_Strict):
    """A step's editable formula: the slot, and the expression the engine computes today.

    ``latex`` is written from ``expression`` by the domain, so the page shows what runs.
    """

    slot_id: str
    title_cs: str
    expression: str
    latex: str
    note_cs: str
    variables: list[FormulaVariableOut]
    properties: list[FormulaPropertyOut]


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
    formulas: list[FormulaOut]


class ModuleDetail(ModuleSummary):
    preset: str | None
    step_details: list[StepOut]


class VersionOut(_Strict):
    """A stored methodology version: immutable, named by the store ``<base>+e<n>``."""

    version_number: int
    name: str
    base_preset: str
    #: The whole specification, as the run that pins it computes it.
    spec: dict[str, Any]
    #: The formula expressions this version replaces, by slot; the rest stay built in.
    formulas: dict[str, str]
    payload_sha256: str
    note: str
    created_by: str
    created_at: datetime


class ActivationOut(_Strict):
    activation_id: int
    #: ``null``: back to the code's preset.
    version_number: int | None
    activated_by: str
    reason: str
    activated_at: datetime


class InForceOut(_Strict):
    """What a run started now pins: a stored version (``origin: stored``) or the code's
    preset (``origin: code``)."""

    origin: str
    preset: str | None
    version_number: int | None
    name: str


class VersionsOut(_Strict):
    in_force: InForceOut
    #: Whether the caller may propose and activate (an organization OWNER or ADMIN).
    may_administer: bool
    #: Each code preset's whole specification, by name: what an edit starts from.
    presets: dict[str, dict[str, Any]]
    versions: list[VersionOut]
    history: list[ActivationOut]


class EditIn(_Strict):
    """An edited methodology: the whole specification and the formulas it replaces."""

    base_preset: str = Field(max_length=64)
    spec: dict[str, Any]
    formulas: dict[str, Annotated[str, Field(max_length=2000)]] = Field(
        default_factory=dict, max_length=64
    )
    note: str = Field(default="", max_length=500)


class CheckOut(_Strict):
    """What storing this edit would meet: ``problems`` (every one, by field or slot) refuse it;
    ``not_computed`` lists replaced formulas it may store but not yet put in force."""

    valid: bool
    problems: dict[str, str]
    not_computed: list[str]
    #: Each replaced formula as LaTeX, written by the domain from the expression checked.
    formulas_latex: dict[str, str]


class MapSummaryOut(_Strict):
    outcome: str
    not_mappable: str | None
    stress_1: float | None
    quality: str | None
    status_counts: dict[str, int]
    effective_n: float | None


class StatusChangeOut(_Strict):
    a: str
    b: str
    in_force: str
    draft: str


class PanelOut(_Strict):
    """The draft beside the methodology in force on one fixed fictional panel."""

    panel: str
    label_cs: str
    respondents: int
    objects: list[str]
    in_force: MapSummaryOut
    draft: MapSummaryOut
    status_changes: list[StatusChangeOut]
    #: Each object's distance from its place on the map in force, the draft turned onto it.
    shifts: dict[str, float]
    alignment_rmsd: float | None
    #: ``[in force, draft]`` per object; ``null`` where an object has none.
    heights: dict[str, list[float | None]]
    k100: dict[str, list[float | None]]
    terrain_max_change: float | None
    terrain_note: str | None
    notes: list[str]


class SupportCellOut(_Strict):
    """One fictional cell: its support, and each surface's status ``[in force, draft]``;
    ``changes`` names each surface whose status moved (``reported``, ``suppressed``,
    ``changed``)."""

    cell: str
    label_cs: str
    n: int
    effective_n: float
    donors: int
    results: list[str]
    analysis: list[str]
    changes: dict[str, str]


class SupportCompareOut(_Strict):
    """The support draft check (plan G1d): every cell, and every ``[cell, surface]`` the draft
    newly reports or newly suppresses."""

    draft: str
    cells: list[SupportCellOut]
    newly_reported: list[list[str]]
    newly_suppressed: list[list[str]]


class CompareOut(_Strict):
    """``problems`` refuse the draft (nothing is computed); otherwise every panel of an
    object map, or every cell of a support rule."""

    valid: bool
    problems: dict[str, str]
    in_force: str
    panels: list[PanelOut]
    support: SupportCompareOut | None = None


class ActivationIn(_Strict):
    #: The version to put in force; ``null`` returns to the code's preset.
    version_number: int | None = Field(ge=1)
    reason: str = Field(default="", max_length=500)


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
        editable=m.editable,
        steps=len(m.steps),
        groups=[
            GroupOut(id=g.id, title_cs=g.title_cs, step_ids=list(g.step_ids), note_cs=g.note_cs)
            for g in m.groups
        ],
    )


def _formula(f: BuiltinFormula) -> FormulaOut:
    return FormulaOut(
        slot_id=f.slot.id,
        title_cs=f.slot.title_cs,
        expression=f.expression,
        latex=latex(compile_formula(f.slot, f.expression)),
        note_cs=f.note_cs,
        variables=[
            FormulaVariableOut(
                name=v.name, latex=v.latex, meaning_cs=v.meaning_cs, unit=v.unit, vector=v.vector
            )
            for v in f.slot.variables
        ],
        properties=[
            FormulaPropertyOut(
                kind=p.kind.value, variable=p.variable, description_cs=p.description_cs
            )
            for p in f.slot.properties
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
        formulas=[_formula(f) for f in view.formulas],
    )


def _not_found(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"code": code, "message": message})


def _version(v: StoredVersion) -> VersionOut:
    return VersionOut(
        version_number=v.version_number,
        name=v.name,
        base_preset=v.base_preset,
        spec=dict(v.payload["spec"]),
        formulas=dict(v.payload["formulas"]),
        payload_sha256=v.payload_sha256,
        note=v.note,
        created_by=v.created_by,
        created_at=v.created_at,
    )


def _activation(a: Activation) -> ActivationOut:
    return ActivationOut(
        activation_id=a.activation_id,
        version_number=a.version_number,
        activated_by=a.activated_by,
        reason=a.reason,
        activated_at=a.activated_at,
    )


def _in_force(found: InForce) -> InForceOut:
    if found.version is None:
        return InForceOut(
            origin=found.origin, preset=found.preset, version_number=None, name=found.preset or ""
        )
    return InForceOut(
        origin=found.origin,
        preset=None,
        version_number=found.version.version_number,
        name=found.version.name,
    )


def _panel(c: PanelComparison) -> PanelOut:
    return PanelOut(
        panel=c.panel,
        label_cs=c.label_cs,
        respondents=c.respondents,
        objects=list(c.objects),
        in_force=MapSummaryOut(**_fields(c.in_force)),
        draft=MapSummaryOut(**_fields(c.draft)),
        status_changes=[
            StatusChangeOut(a=a, b=b, in_force=x, draft=y) for a, b, x, y in c.status_changes
        ],
        shifts=dict(c.shifts),
        alignment_rmsd=c.alignment_rmsd,
        heights={k: list(v) for k, v in c.heights.items()},
        k100={k: list(v) for k, v in c.k100.items()},
        terrain_max_change=c.terrain_max_change,
        terrain_note=c.terrain_note,
        notes=list(c.notes),
    )


def _support_comparison(c: SupportComparison) -> SupportCompareOut:
    return SupportCompareOut(
        draft=c.draft,
        cells=[
            SupportCellOut(
                cell=x.cell,
                label_cs=x.label_cs,
                n=x.n,
                effective_n=x.effective_n,
                donors=x.donors,
                results=list(x.results),
                analysis=list(x.analysis),
                changes=x.changes(),
            )
            for x in c.cells
        ],
        newly_reported=[list(m) for m in c.moved("reported")],
        newly_suppressed=[list(m) for m in c.moved("suppressed")],
    )


#: The modules a draft check is built for.
_COMPARED: Final = frozenset({"sociomap", "support"})


def _fields(summary: Any) -> dict[str, Any]:
    return {name: getattr(summary, name) for name in MapSummaryOut.model_fields}


def _presets(module_id: str) -> dict[str, dict[str, Any]]:
    """An editable module's presets, whole, as JSON; a read-only module offers none."""
    try:
        found = module(module_id)
    except KeyError as exc:
        raise MethodologyRefused(
            f"no method module {module_id!r}", reason="unknown_module"
        ) from exc
    if not found.editable:
        return {}
    return {p.name: p.spec.model_dump(mode="json") for p in found.presets}


def _refused(exc: ScopeDenied | MethodologyRefused) -> HTTPException:
    if isinstance(exc, ScopeDenied):
        return HTTPException(
            status_code=403,
            detail={
                "code": "insufficient_role",
                "message": "Changing the methodology requires an organization OWNER or ADMIN.",
                "details": {"reason": exc.reason},
            },
        )
    detail: dict[str, Any] = {"code": exc.reason, "message": str(exc)}
    if exc.problems:
        detail["details"] = {"problems": exc.problems}
    return HTTPException(status_code=_STATUS.get(exc.reason, 422), detail=detail)


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


@router.get(
    "/{module_id}/versions",
    response_model=VersionsOut,
    summary="What is in force, every stored version and the activation log",
)
def read_versions(module_id: ModuleId, org: OrganizationDep, session: SessionDep) -> VersionsOut:
    try:
        reader = MethodologyReader(session, org)
        return VersionsOut(
            in_force=_in_force(reader.in_force(module_id)),
            may_administer=org.may_administer,
            presets=_presets(module_id),
            versions=[_version(v) for v in reader.versions(module_id)],
            history=[_activation(a) for a in reader.history(module_id)],
        )
    except MethodologyRefused as exc:
        raise _refused(exc) from exc


@router.post(
    "/{module_id}/check",
    response_model=CheckOut,
    summary="Validate an edit without storing it",
)
def check(module_id: ModuleId, body: EditIn, org: OrganizationDep) -> CheckOut:
    """Any member may check: nothing is stored, and the answer is the domain's own."""
    del org
    try:
        found = module(module_id)
    except KeyError as exc:
        raise _not_found("unknown_module", f"no method module {module_id!r}") from exc
    try:
        validated = validate_version(
            found,
            base_preset=body.base_preset,
            spec=body.spec,
            formulas=body.formulas,
            version_name=named(body.base_preset, 1),
        )
    except MethodologyVersionInvalid as exc:
        return CheckOut(
            valid=False, problems=dict(exc.problems), not_computed=[], formulas_latex={}
        )
    slots = {f.slot.id: f.slot for f in found.formulas}
    return CheckOut(
        valid=True,
        problems={},
        not_computed=list(uncomputed_formulas(version_payload(validated))),
        formulas_latex={
            slot: latex(compile_formula(slots[slot], text))
            for slot, text in validated.formulas.items()
        },
    )


@router.post(
    "/{module_id}/compare",
    response_model=CompareOut,
    summary="The edit beside the methodology in force, on fictional panels",
)
def compare(
    module_id: ModuleId, body: EditIn, org: OrganizationDep, session: SessionDep
) -> CompareOut:
    """Any member may compare: nothing is stored, and only fixed fictional panels are read."""
    try:
        found = module(module_id)
    except KeyError as exc:
        raise _not_found("unknown_module", f"no method module {module_id!r}") from exc
    if module_id not in _COMPARED:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "no_comparison",
                "message": f"{module_id}: no draft check is built for this module yet",
            },
        )
    try:
        validated = validate_version(
            found,
            base_preset=body.base_preset,
            spec=body.spec,
            formulas=body.formulas,
            version_name=named(body.base_preset, 1),
        )
    except MethodologyVersionInvalid as exc:
        return CompareOut(valid=False, problems=dict(exc.problems), in_force="", panels=[])
    try:
        in_force = MethodologyReader(session, org).in_force(module_id)
    except MethodologyRefused as exc:
        raise _refused(exc) from exc
    stored = None if in_force.version is None else in_force.version.payload
    if module_id == "support":
        return CompareOut(
            valid=True,
            problems={},
            in_force=_in_force(in_force).name,
            panels=[],
            support=_support_comparison(
                compare_support_with_in_force(stored, version_payload(validated))
            ),
        )
    panels = compare_with_in_force(stored, version_payload(validated))
    return CompareOut(
        valid=True,
        problems={},
        in_force=_in_force(in_force).name,
        panels=[_panel(p) for p in panels],
    )


@router.post(
    "/{module_id}/versions",
    response_model=VersionOut,
    status_code=201,
    summary="Store an edit as the next version (it is not in force until put)",
)
def propose(
    module_id: ModuleId, body: EditIn, org: OrganizationDep, session: SessionDep
) -> VersionOut:
    try:
        stored = MethodologyRepository(session, org).propose(
            module_id,
            base_preset=body.base_preset,
            spec=body.spec,
            formulas=body.formulas,
            note=body.note,
        )
    except (ScopeDenied, MethodologyRefused) as exc:
        raise _refused(exc) from exc
    return _version(stored)


@router.put(
    "/{module_id}/activation",
    response_model=InForceOut,
    summary="Put a version in force, or return to the code's preset",
)
def activate(
    module_id: ModuleId, body: ActivationIn, org: OrganizationDep, session: SessionDep
) -> InForceOut:
    """Takes effect for runs started afterwards; a run already started keeps its pin."""
    try:
        return _in_force(
            MethodologyRepository(session, org).activate(
                module_id, body.version_number, reason=body.reason
            )
        )
    except (ScopeDenied, MethodologyRefused) as exc:
        raise _refused(exc) from exc
