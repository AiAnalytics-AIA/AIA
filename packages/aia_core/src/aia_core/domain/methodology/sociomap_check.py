"""What an edited object map does, before it is put in force (ADR 0023 decision 7, plan S4b).

The draft and the methodology in force are computed side by side through the real engine,
on fixed fictional panels only -- never a client's data -- and the differences are reported
per panel: whether each maps, Stress-1 and its band, every pair whose status changes, how far
each object moves once the draft is turned onto the map in force (a view: rotation and
reflection only, F7), each object's height and K100, the support's effective n, and the
terrain's largest change.

The panels are generated here from fixed seeds (``random.Random``), so the check is the same
every time it is asked; they are AIA's own invention and say so. K100 is compared as its
point value (``f9.k100`` of K, as a run computes it); its bootstrap interval costs about 1.5 s
per map and is computed by the run, not by the check, which says so.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from ..sociomap.engine_v2 import compute_object_map
from ..sociomap.metrics import ObjectRole
from ..sociomap.models_v3 import ObjectMapInputs, RatingItem, SociomapArtifactV3
from ..sociomap.slots import K100, Slots
from ..sociomap.specification import SociomapSpecV3
from ..sociomap.terrain import EnvelopeTerrain
from ..sociomap.view import align_to_reference
from .pins import sociomap_methods_for

__all__ = [
    "CHECK_PANELS",
    "K100_INTERVAL_NOTE",
    "CheckPanel",
    "PanelComparison",
    "compare_object_maps",
    "compare_with_in_force",
    "warm_object_maps",
]

#: Why the check compares K100's point and not its interval.
K100_INTERVAL_NOTE: Final = (
    "Kontrola porovnává K100 jako bod (100 · K, nebo vzorec f9.k100); jeho bootstrapový "
    "interval spočítá až běh."
)


@dataclass(frozen=True, slots=True)
class CheckPanel:
    """A fixed fictional panel: who answers, how many, how weighted, how often blank."""

    id: str
    label_cs: str
    seed: int
    respondents: int
    objects: int
    weights: tuple[float, float] | None  # None: equal weights
    blank: float
    secondary: int = 0

    def inputs(self) -> ObjectMapInputs:
        """The panel's ratings, 1-10, from two tastes and a rating habit, drawn by its seed."""
        rng = random.Random(self.seed)
        loadings = [(rng.uniform(-1.6, 1.6), rng.uniform(-1.2, 1.2)) for _ in range(self.objects)]
        rows: list[tuple[float | None, ...]] = []
        for _ in range(self.respondents):
            t1, t2, habit = rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1.1)
            row: list[float | None] = []
            for a, b in loadings:
                value = round(5.5 + habit + a * t1 + b * t2 + rng.gauss(0, 1.4))
                row.append(None if rng.random() < self.blank else float(min(10, max(1, value))))
            rows.append(tuple(row))
        low_high = self.weights
        weights = tuple(
            1.0 if low_high is None else rng.uniform(*low_high) for _ in range(self.respondents)
        )
        ids = tuple(f"objekt {k + 1}" for k in range(self.objects))
        first_secondary = self.objects - self.secondary
        return ObjectMapInputs(
            respondent_ids=tuple(f"R{k + 1}" for k in range(self.respondents)),
            donor_ids=tuple(f"D{k + 1}" for k in range(self.respondents)),
            items=tuple(
                RatingItem(item_id=f"q{k + 1}", scale_min=1.0, scale_max=10.0)
                for k in range(self.objects)
            ),
            values=tuple(rows),
            weights=weights,
            object_ids=ids,
            object_items=tuple(f"q{k + 1}" for k in range(self.objects)),
            roles={
                oid: (ObjectRole.SECONDARY if k >= first_secondary else ObjectRole.PRIMARY).value
                for k, oid in enumerate(ids)
            },
        )


#: The panels every draft is checked on. Fictional; fixed; never a client's data.
CHECK_PANELS: Final = (
    CheckPanel(
        id="balanced",
        label_cs="Vyrovnaný panel: 120 respondentů, stejné váhy, bez mezer",
        seed=20261011,
        respondents=120,
        objects=8,
        weights=None,
        blank=0.0,
    ),
    CheckPanel(
        id="weighted",
        label_cs=(
            "Vážený panel: 90 respondentů, váhy 0,3 až 3, 8 % nevyplněno, jeden kontextový objekt"
        ),
        seed=20261012,
        respondents=90,
        objects=7,
        weights=(0.3, 3.0),
        blank=0.08,
        secondary=1,
    ),
    CheckPanel(
        id="small",
        label_cs="Malý panel: 36 respondentů, stejné váhy, 5 % nevyplněno (u hranice n_min)",
        seed=20261013,
        respondents=36,
        objects=6,
        weights=None,
        blank=0.05,
    ),
)


@dataclass(frozen=True, slots=True)
class MapSummary:
    """One map of a panel, as the comparison reads it."""

    outcome: str
    not_mappable: str | None
    stress_1: float | None
    quality: str | None
    status_counts: dict[str, int]
    effective_n: float | None


@dataclass(frozen=True, slots=True)
class PanelComparison:
    """The draft beside the methodology in force on one panel."""

    panel: str
    label_cs: str
    respondents: int
    objects: tuple[str, ...]
    in_force: MapSummary
    draft: MapSummary
    #: ``(a, b, in force, draft)`` for every pair whose status changes.
    status_changes: tuple[tuple[str, str, str, str], ...]
    #: Each object's distance from its place on the map in force, after the draft is turned
    #: onto it; empty when either does not map.
    shifts: dict[str, float]
    alignment_rmsd: float | None
    heights: dict[str, tuple[float | None, float | None]]
    k100: dict[str, tuple[float | None, float | None]]
    #: The largest change of a terrain cell both maps reach; ``None`` when the grids differ
    #: or either map has no terrain.
    terrain_max_change: float | None
    terrain_note: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


def _summary(art: SociomapArtifactV3) -> MapSummary:
    layout = art.layout
    return MapSummary(
        outcome=art.outcome,
        not_mappable=None if art.not_mappable is None else art.not_mappable.reason,
        stress_1=None if layout is None else layout.stress_1,
        quality=None if layout is None else layout.quality,
        status_counts=dict(art.status_counts),
        effective_n=art.support.effective_n,
    )


def _k100(art: SociomapArtifactV3, slots: Slots) -> dict[str, float | None]:
    scale = slots.get(K100)
    out: dict[str, float | None] = {}
    for score in art.scores.get("objects", ()):
        k = score.get("connectedness")
        out[score["id"]] = (
            None if k is None else (100.0 * k if scale is None else float(scale(k=k)))
        )
    return out


def _changes(
    ids: Sequence[str], before: SociomapArtifactV3, after: SociomapArtifactV3
) -> tuple[tuple[str, str, str, str], ...]:
    out: list[tuple[str, str, str, str]] = []
    at0 = {oid: k for k, oid in enumerate(before.object_ids)}
    at1 = {oid: k for k, oid in enumerate(after.object_ids)}
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a = before.relations.status[at0[ids[i]]][at0[ids[j]]]
            b = after.relations.status[at1[ids[i]]][at1[ids[j]]]
            if a != b:
                out.append((ids[i], ids[j], str(_value(a)), str(_value(b))))
    return tuple(out)


def _value(status: Any) -> Any:
    return getattr(status, "value", status)


def _terrain_change(
    before: SociomapArtifactV3, after: SociomapArtifactV3
) -> tuple[float | None, str | None]:
    t0, t1 = before.terrain, after.terrain
    if not isinstance(t0, EnvelopeTerrain) or not isinstance(t1, EnvelopeTerrain):
        return None, "terén nemá jedna z map"
    if t0.parameters.axes() != t1.parameters.axes():
        return None, "mřížka terénu se liší, buňky nejde porovnat"
    largest = 0.0
    for row0, row1 in zip(t0.height, t1.height, strict=True):
        for z0, z1 in zip(row0, row1, strict=True):
            if z0 is not None and z1 is not None:
                largest = max(largest, abs(z1 - z0))
    return largest, None


def compare_object_maps(
    in_force: tuple[SociomapSpecV3, Slots], draft: tuple[SociomapSpecV3, Slots]
) -> tuple[PanelComparison, ...]:
    """The draft beside the methodology in force on every :data:`CHECK_PANELS` panel."""
    out: list[PanelComparison] = []
    for panel in CHECK_PANELS:
        inputs = panel.inputs()
        before = compute_object_map(
            inputs, in_force[0], connectedness_interval=False, slots=in_force[1]
        )
        after = compute_object_map(inputs, draft[0], connectedness_interval=False, slots=draft[1])
        # The objects both maps place: the signed-off methodology maps the PRIMARY, rated
        # objects only, so a draft of another method is compared over what both have.
        ids = [o for o in inputs.object_ids if o in before.object_ids and o in after.object_ids]
        shifts: dict[str, float] = {}
        rmsd: float | None = None
        if before.layout is not None and after.layout is not None:
            reference = {
                o: p
                for o, p in zip(before.object_ids, before.layout.points, strict=True)
                if o in ids
            }
            placed = {
                o: p for o, p in zip(after.object_ids, after.layout.points, strict=True) if o in ids
            }
            turned = align_to_reference(placed, reference)
            rmsd = turned.rmsd
            shifts = {
                oid: math.hypot(
                    turned.points[oid][0] - reference[oid][0],
                    turned.points[oid][1] - reference[oid][1],
                )
                for oid in ids
            }
        k_before, k_after = _k100(before, in_force[1]), _k100(after, draft[1])
        terrain, terrain_note = _terrain_change(before, after)
        out.append(
            PanelComparison(
                panel=panel.id,
                label_cs=panel.label_cs,
                respondents=panel.respondents,
                objects=tuple(ids),
                in_force=_summary(before),
                draft=_summary(after),
                status_changes=_changes(ids, before, after),
                shifts=shifts,
                alignment_rmsd=rmsd,
                heights={
                    oid: (
                        before.heights.values[before.object_ids.index(oid)],
                        after.heights.values[after.object_ids.index(oid)],
                    )
                    for oid in ids
                },
                k100={oid: (k_before.get(oid), k_after.get(oid)) for oid in k_before | k_after},
                terrain_max_change=terrain,
                terrain_note=terrain_note,
                notes=(K100_INTERVAL_NOTE,),
            )
        )
    return tuple(out)


def _pin(payload: dict[str, Any] | None) -> tuple[SociomapSpecV3, Slots]:
    """The object map's specification and formula slots a run started under ``payload`` pins
    (``None``: the code's preset)."""
    method = sociomap_methods_for(payload)[-1]
    spec = method.resolve()
    if not isinstance(spec, SociomapSpecV3):  # pragma: no cover - the pins guarantee it
        raise TypeError("the object map's pin is not a contract-3 specification")
    return spec, method.slots()


def compare_with_in_force(
    in_force: dict[str, Any] | None, draft: dict[str, Any]
) -> tuple[PanelComparison, ...]:
    """:func:`compare_object_maps` for two version payloads, as a run would pin them:
    ``in_force`` is the stored version in force (``None``: the code's preset), ``draft`` an
    edit validated by ``versions.validate_version``. Each is resolved through the run's own
    pin, formulas compiled, so the check computes exactly what a run would."""
    return compare_object_maps(_pin(in_force), _pin(draft))


def warm_object_maps() -> int:
    """Compute the code's preset map once on every :data:`CHECK_PANELS` panel and discard it.

    The signed-off methodology's kernels are numba's, compiled on their first call in a process
    whose kernel cache is empty -- every container start, since the image's filesystem is read
    only (deploy/docker/python.Dockerfile) -- and that first compile takes about 40 s. Run once
    in the background after start, the first comparison a person asks for meets compiled
    kernels. Returns the number of panels computed."""
    spec, slots = _pin(None)
    for panel in CHECK_PANELS:
        compute_object_map(panel.inputs(), spec, connectedness_interval=False, slots=slots)
    return len(CHECK_PANELS)
