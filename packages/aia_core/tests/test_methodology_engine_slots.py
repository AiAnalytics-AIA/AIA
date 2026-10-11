"""The engine computes a methodology version's replaced formulas (ADR 0023 decision 4, S4c).

Each slot is proved twice on a weighted panel with missing ratings, the bootstrap on and the
terrain drawn:

* replaced by its own built-in expression, the map is the code's map, bit for bit. That
  proves the slot sits exactly where the code's formula ran and reads exactly its inputs;
* replaced by another expression, what that slot computes moves. That proves the engine
  reads the slot rather than ignoring it.

Then the pin: a version's formulas travel with its specification, a code preset's pin stores
and fingerprints exactly as before, and a formula that does not compile, names no slot or
sits on the reference map is refused by name, never computed as the code's.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

import pytest

from aia_core.domain.methodology.expressions import compile_formula
from aia_core.domain.methodology.pins import COMPUTED_SLOTS, sociomap_methods_for
from aia_core.domain.methodology.sociomap_formulas import SOCIOMAP_FORMULAS
from aia_core.domain.research_sociomap import (
    SociomapMethod,
    SociomapMethodsInvalid,
    default_methods,
    methods_fingerprint,
    read_methods,
)
from aia_core.domain.sociomap import (
    AIA_SOCIOMAP_V1,
    AIA_SOCIOMAP_V3,
    ObjectMapInputs,
    RatingItem,
    compute_object_map,
)
from aia_core.domain.sociomap.models_v3 import ObjectRole, SociomapArtifactV3
from aia_core.domain.sociomap.slots import ENGINE_SLOTS

BUILTIN = {f.slot.id: f for f in SOCIOMAP_FORMULAS}
SPEC = AIA_SOCIOMAP_V3.model_copy(
    update={"connectedness": AIA_SOCIOMAP_V3.connectedness.model_copy(update={"resamples": 30})}
)


def _inputs() -> ObjectMapInputs:
    """60 people, five objects plus one standalone rating, 1-10, unequal weights, gaps."""
    rng = random.Random(20261011)
    m, extra = 5, 1
    rows: list[tuple[float | None, ...]] = []
    for _ in range(60):
        taste, habit = rng.gauss(0, 1), rng.gauss(0, 1.2)
        row: list[float | None] = []
        for j in range(m + extra):
            value = round(5.5 + habit + (1.6 if j % 2 else -1.6) * taste + rng.gauss(0, 1.4))
            row.append(None if rng.random() < 0.06 else float(min(10, max(1, value))))
        rows.append(tuple(row))
    return ObjectMapInputs(
        respondent_ids=tuple(f"R{k}" for k in range(60)),
        donor_ids=tuple(f"D{k // 2}" for k in range(60)),
        items=tuple(
            RatingItem(item_id=f"i{j}", scale_min=1.0, scale_max=10.0) for j in range(m + extra)
        ),
        values=tuple(rows),
        weights=tuple(rng.uniform(0.4, 2.5) for _ in range(60)),
        object_ids=tuple(f"o{j}" for j in range(m)),
        object_items=tuple(f"i{j}" for j in range(m)),
        roles={f"o{j}": ObjectRole.PRIMARY.value for j in range(m)},
    )


INPUTS = _inputs()


def _map(slots: dict[str, Any] | None = None) -> SociomapArtifactV3:
    return compute_object_map(INPUTS, SPEC, connectedness_interval=True, slots=slots or {})


def _compiled(slot_id: str, text: str) -> Any:
    return compile_formula(BUILTIN[slot_id].slot, text)


CODE = _map()

#: Another formula for each slot, and what of the map it must move.
Read = Callable[[SociomapArtifactV3], Any]
OTHER: dict[str, tuple[str, Read]] = {
    "f1.scale": ("((a - lo) / (hi - lo)) ** 2", lambda a: a.heights.values),
    "f2.person": ("((a - low) / (high - low)) ** 2", lambda a: a.relations.r),
    "f3.effective_n": ("count(w)", lambda a: a.relations.n_effective),
    "f3.interval_low": ("max(-1, r - 0.5)", lambda a: a.relations.interval),
    "f3.interval_high": ("min(1, r + 0.5)", lambda a: a.relations.interval),
    "f3.effect_floor": ("abs(r) >= 4 * floor", lambda a: a.relations.meets_effect_floor),
    "f6.distance": ("1 - r", lambda a: a.layout and a.layout.points),
    "f7.stress_1": (
        "sum((d - delta) ** 2) / sum(delta * delta) if sum(delta * delta) > 0 else 0",
        lambda a: a.layout and a.layout.stress_1,
    ),
    "f8.alignment": ("max(r)", lambda a: a.scores),
    "f8.connectedness": ("max(abs(r))", lambda a: a.scores),
    "f8.height": ("sum(a) / count(a)", lambda a: a.heights.values),
    "f9.k100": ("50 * k", lambda a: a.connectedness_100),
    "f12.kernel": ("h * exp(-d2 / (sigma * sigma))", lambda a: a.terrain),
    "support.effective_n": ("count(w)", lambda a: a.support.effective_n),
}


def test_the_engine_computes_every_slot_and_the_catalogue_has_no_other() -> None:
    assert set(BUILTIN) == ENGINE_SLOTS == COMPUTED_SLOTS == set(OTHER)


def test_the_panel_reaches_every_slot() -> None:
    """A map that never placed, never bootstrapped or drew no terrain would prove nothing."""
    assert CODE.layout is not None
    assert CODE.connectedness_100["status"] == "computed"
    assert CODE.terrain is not None and getattr(CODE.terrain, "height", None)
    assert CODE.relations.n_effective is not None and CODE.relations.meets_effect_floor
    assert CODE.support.effective_n is not None and CODE.support.effective_n < 60


@pytest.mark.parametrize("slot_id", sorted(BUILTIN))
def test_a_slot_replaced_by_its_built_in_expression_is_the_codes_map_bit_for_bit(
    slot_id: str,
) -> None:
    replaced = _map({slot_id: _compiled(slot_id, BUILTIN[slot_id].expression)})
    assert replaced.model_dump(mode="json") == CODE.model_dump(mode="json")


@pytest.mark.parametrize("slot_id", sorted(OTHER))
def test_a_slot_replaced_by_another_formula_moves_what_it_computes(slot_id: str) -> None:
    text, read = OTHER[slot_id]
    replaced = _map({slot_id: _compiled(slot_id, text)})
    assert read(replaced) != read(CODE)


def test_a_replaced_interval_decides_the_status() -> None:
    """The status reads the replaced interval: a band so wide it always crosses zero leaves
    no pair RELIABLE."""
    wide = _map(
        {
            "f3.interval_low": _compiled("f3.interval_low", "-1"),
            "f3.interval_high": _compiled("f3.interval_high", "1"),
        }
    )
    assert any(s == "reliable" for row in CODE.relations.status for s in row if s)
    assert not any(s == "reliable" for row in wide.relations.status for s in row if s)


# --------------------------------------------------------------------------- the pin


def test_a_code_presets_pin_stores_and_fingerprints_as_before() -> None:
    for method in default_methods():
        assert "formulas" not in method.model_dump(mode="json")
        assert method.slots() == {}
    assert read_methods([m.model_dump(mode="json") for m in default_methods()]) == default_methods()


def test_a_versions_formulas_travel_with_its_specification() -> None:
    # As a stored version holds it (``versions.version_payload``).
    spec = AIA_SOCIOMAP_V3.model_copy(
        update={"methodology_version": "aia-sociomap-3+e4"}
    ).model_dump(mode="json")
    kernel = "h * exp(-d2 / (2 * sigma ** 2))"
    methods = sociomap_methods_for({"spec": spec, "formulas": {"f12.kernel": kernel}})
    edited = methods[1]
    assert edited.method_id == "aia-sociomap-3+e4"
    assert edited.model_dump(mode="json")["formulas"] == {"f12.kernel": kernel}
    stored = read_methods([m.model_dump(mode="json") for m in methods])
    assert stored == methods
    assert set(stored[1].slots()) == {"f12.kernel"}
    plain = sociomap_methods_for({"spec": spec, "formulas": {}})
    assert methods_fingerprint(plain) != methods_fingerprint(methods)


@pytest.mark.parametrize(
    ("formulas", "words"),
    [
        ({"f12.kernel": "h * open(d2)"}, "does not compile"),
        ({"f99.nothing": "1"}, "no formula slot"),
    ],
)
def test_a_pinned_formula_that_cannot_be_computed_is_refused_by_name(
    formulas: dict[str, str], words: str
) -> None:
    method = SociomapMethod.of(AIA_SOCIOMAP_V3, formulas)
    with pytest.raises(SociomapMethodsInvalid, match=words):
        method.slots()


def test_the_reference_map_carries_no_formula() -> None:
    method = SociomapMethod.of(AIA_SOCIOMAP_V1, {"f6.distance": "1 - r"})
    with pytest.raises(SociomapMethodsInvalid, match="only an object map"):
        method.slots()
