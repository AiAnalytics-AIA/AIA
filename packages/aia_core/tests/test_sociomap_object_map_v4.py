"""``aia-sociomap-4``: the object map's own constants declared in the spec (plan
``methodology-tab``, chunk S2a).

The three-object minimum, the Stress-1 quality bands and K100's interval quantiles were
module constants; contract 3 now carries each as an optional member, left out of the stored
form when undeclared, so ``aia-sociomap-3`` -- the subject of the D6 sign-off -- keeps its
stored form and fingerprint byte for byte. ``aia-sociomap-4`` declares them at the values
the code used, and computes exactly what ``aia-sociomap-3`` computes; an edit made from it
can move them.
"""

from __future__ import annotations

import math
import random
from typing import Any

import pytest

from aia_core.domain.methodology.sociomap_check import CHECK_PANELS
from aia_core.domain.research_sociomap import default_methods
from aia_core.domain.sociomap import (
    AIA_SOCIOMAP_V3,
    AIA_SOCIOMAP_V4,
    MapOutcome,
    NotMappableReason,
    ObjectMapInputs,
    RatingItem,
    SociomapSpecV3,
    UnsupportedMethodology,
    compute_object_map,
    read_spec,
    require_supported,
    spec_payload,
)
from aia_core.domain.sociomap.metrics import CONNECTEDNESS_QUANTILES, ObjectRole
from aia_core.domain.sociomap.specification import (
    LEGACY_CONNECTEDNESS_QUANTILES,
    LEGACY_MIN_OBJECTS,
    LEGACY_STRESS_BANDS,
)
from aia_core.domain.sociomap.view import STRESS_QUALITY_BANDS, StressQuality, stress_quality

#: ``aia-sociomap-3``'s fingerprint, the one docs/architecture/sociomapa-methodology-decision.md
#: asks the owner to sign. S2a must not move it.
V3_FINGERPRINT_PREFIX = "e16dc0d06361"


def _v4_with(
    *, layout: dict[str, Any] | None = None, connectedness: dict[str, Any] | None = None
) -> SociomapSpecV3:
    return AIA_SOCIOMAP_V4.model_copy(
        update={
            "methodology_version": "aia-sociomap-4+test",
            "layout": AIA_SOCIOMAP_V4.layout.model_copy(update=layout or {}),
            "connectedness": AIA_SOCIOMAP_V4.connectedness.model_copy(update=connectedness or {}),
        }
    )


def _inputs(seed: int, n: int, m: int) -> ObjectMapInputs:
    rng = random.Random(seed)
    loadings = [rng.uniform(-1.5, 1.5) for _ in range(m)]
    rows: list[tuple[float | None, ...]] = []
    for _ in range(n):
        habit, taste = rng.gauss(0, 1.1), rng.gauss(0, 1)
        rows.append(
            tuple(
                float(min(10, max(1, round(5.5 + habit + a * taste + rng.gauss(0, 1.4)))))
                for a in loadings
            )
        )
    ids = tuple(f"o{j}" for j in range(m))
    return ObjectMapInputs(
        respondent_ids=tuple(f"R{i}" for i in range(n)),
        donor_ids=tuple(f"D{i}" for i in range(n)),
        items=tuple(RatingItem(item_id=f"i{j}", scale_min=1.0, scale_max=10.0) for j in range(m)),
        values=tuple(rows),
        weights=tuple([1.0] * n),
        object_ids=ids,
        object_items=tuple(f"i{j}" for j in range(m)),
        roles=dict.fromkeys(ids, ObjectRole.PRIMARY.value),
    )


# --------------------------------------------------------------------- the spec --


def test_the_d6_subject_keeps_its_stored_form_and_fingerprint() -> None:
    assert AIA_SOCIOMAP_V3.fingerprint().startswith(V3_FINGERPRINT_PREFIX)
    stored = spec_payload(AIA_SOCIOMAP_V3)
    spec = stored["spec"]
    assert "min_objects" not in spec["layout"] and "stress_bands" not in spec["layout"]
    assert "quantiles" not in spec["connectedness"]
    assert read_spec(stored) == AIA_SOCIOMAP_V3


def test_new_runs_still_pin_the_d6_subject() -> None:
    assert [m.method_id for m in default_methods()][-1] == "aia-sociomap-3"


def test_v4_declares_the_constants_the_code_used() -> None:
    require_supported(AIA_SOCIOMAP_V4)
    assert AIA_SOCIOMAP_V4.layout.min_objects == LEGACY_MIN_OBJECTS == 3
    assert AIA_SOCIOMAP_V4.layout.stress_bands == LEGACY_STRESS_BANDS
    assert tuple(bound for bound, _ in STRESS_QUALITY_BANDS) == LEGACY_STRESS_BANDS
    assert (
        AIA_SOCIOMAP_V4.connectedness.quantiles
        == LEGACY_CONNECTEDNESS_QUANTILES
        == CONNECTEDNESS_QUANTILES
    )
    stored = spec_payload(AIA_SOCIOMAP_V4)
    assert stored["spec"]["layout"]["min_objects"] == 3
    assert read_spec(stored) == AIA_SOCIOMAP_V4
    assert AIA_SOCIOMAP_V4.fingerprint() != AIA_SOCIOMAP_V3.fingerprint()


@pytest.mark.parametrize(
    ("layout", "connectedness", "field"),
    [
        ({"min_objects": 2}, None, "min_objects"),
        ({"stress_bands": (0.10, 0.05, 0.20)}, None, "stress_bands"),
        ({"stress_bands": (0.0, 0.10, 0.20)}, None, "stress_bands"),
        ({"stress_bands": (0.05, 0.10, math.inf)}, None, "stress_bands"),
        (None, {"quantiles": (0.975, 0.025)}, "quantiles"),
        (None, {"quantiles": (0.0, 0.975)}, "quantiles"),
        (None, {"quantiles": (0.025, 1.0)}, "quantiles"),
    ],
)
def test_a_constant_outside_its_domain_is_refused_by_name(
    layout: dict[str, Any] | None, connectedness: dict[str, Any] | None, field: str
) -> None:
    with pytest.raises(UnsupportedMethodology, match=field):
        require_supported(_v4_with(layout=layout, connectedness=connectedness))


# ------------------------------------------------------------------- the engine --


@pytest.mark.parametrize("panel", CHECK_PANELS, ids=lambda p: p.id)
def test_v4_computes_exactly_what_v3_computes(panel: Any) -> None:
    inputs = panel.inputs()
    v3 = compute_object_map(inputs, AIA_SOCIOMAP_V3, connectedness_interval=False)
    v4 = compute_object_map(inputs, AIA_SOCIOMAP_V4, connectedness_interval=False)
    dump3, dump4 = v3.model_dump(mode="json"), v4.model_dump(mode="json")
    dump3.pop("spec"), dump4.pop("spec")
    assert dump3 == dump4


def test_the_quality_reads_the_declared_bands() -> None:
    inputs = CHECK_PANELS[0].inputs()
    base = compute_object_map(inputs, AIA_SOCIOMAP_V4, connectedness_interval=False)
    assert base.layout is not None
    stress = base.layout.stress_1
    lenient = (stress * 2, stress * 3, stress * 4)  # the same fit, judged good
    edited = compute_object_map(
        inputs, _v4_with(layout={"stress_bands": lenient}), connectedness_interval=False
    )
    assert edited.layout is not None
    assert edited.layout.stress_1 == stress
    assert base.layout.quality == stress_quality(stress) != StressQuality.GOOD
    assert edited.layout.quality == stress_quality(stress, lenient) == StressQuality.GOOD


def test_a_raised_minimum_makes_a_small_family_not_mappable() -> None:
    inputs = _inputs(5, 120, 3)
    assert (
        compute_object_map(inputs, AIA_SOCIOMAP_V4, connectedness_interval=False).outcome
        == MapOutcome.MAPPED
    )
    art = compute_object_map(
        inputs, _v4_with(layout={"min_objects": 4}), connectedness_interval=False
    )
    assert art.outcome == MapOutcome.NOT_MAPPABLE
    assert art.not_mappable is not None
    assert art.not_mappable.reason == NotMappableReason.TOO_FEW_OBJECTS


def test_the_k100_interval_reads_the_declared_quantiles() -> None:
    inputs = _inputs(7, 120, 5)
    small = {"resamples": 40}
    wide = compute_object_map(inputs, _v4_with(connectedness=small), connectedness_interval=True)
    narrow = compute_object_map(
        inputs,
        _v4_with(connectedness={**small, "quantiles": (0.25, 0.75)}),
        connectedness_interval=True,
    )
    assert wide.connectedness_100["quantiles"] == list(LEGACY_CONNECTEDNESS_QUANTILES)
    assert narrow.connectedness_100["quantiles"] == [0.25, 0.75]
    assert "2.5 % / 97.5 %" in wide.connectedness_100["rule_text"]
    assert "25 % / 75 %" in narrow.connectedness_100["rule_text"]
    pairs = list(
        zip(wide.connectedness_100["objects"], narrow.connectedness_100["objects"], strict=True)
    )
    for w, n in pairs:
        assert w["k100"] == n["k100"]
        if w["low"] is not None:
            assert w["low"] <= n["low"] <= n["high"] <= w["high"]
    assert any(w["low"] is not None and w["low"] < n["low"] for w, n in pairs)
