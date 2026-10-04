"""The first acceptance journey: the fictional reference study R1 through every stage built so far.

``tools/sociomapping_journey.py`` runs the stages; this test runs the same function. The
pinned values are regression pins of AIA's own implementation -- they say the journey has
not changed, not that the original method agrees. Where a value can be checked by hand
arithmetic from the study's raw answers, the test does that instead.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
STUDY = json.loads(
    (Path(__file__).parent / "fixtures/sociomapping_reference/study.json").read_text("utf-8")
)


def _journey() -> Any:
    spec = importlib.util.spec_from_file_location("journey", REPO / "tools/sociomapping_journey.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_reference_study_runs_through_every_built_stage() -> None:
    result = _journey().run(STUDY)
    current = result["people"]["current_communication"]
    assert current["fuzzy_matrix"]["rules"] == ["RTS-P1", "RTS-N1"]
    assert not current["fuzzy_matrix"]["symmetric"]
    # Hand arithmetic from the raw 1-5 ratings: Alena received 5, 3, 2, 1, 3 -> 2.8.
    assert current["heights_on_scale"]["received (column average, QED-W1)"][0] == pytest.approx(2.8)
    # Filip gave everyone 3 -> 3.0.
    assert current["heights_on_scale"]["given (row average, QED-W2)"][5] == pytest.approx(3.0)
    assert current["coherences"] == "((Cyril, (Alena, Boris)1)0.5, (Filip, (Dana, Emil)1)0.5)0"

    objects = result["objects"]
    assert objects["support"] == 12 and objects["negative_pairs"] == []
    altair = [row[0] for row in STUDY["objects"]["ratings"]]
    borealis = [row[1] for row in STUDY["objects"]["ratings"]]
    assert objects["signed_correlations"][0][1] == pytest.approx(
        _pearson(altair, borealis), abs=1e-6
    )
    assert objects["relation_matrix"]["rules"] == ["RTS-N1", "RTS-O1", "RTS-O2"]
    assert objects["average_answer_on_scale (RTS-W3)"][0] == pytest.approx(sum(altair) / 12)
    assert objects["coherences"] == (
        "((Cirrus, Delta)0.839652, (Borealis, (Altair, Echo)0.933413)0.889569)0.749596"
    )


def test_unbuilt_stages_say_what_blocks_them() -> None:
    pending = {p["stage"]: p["blocked_by"] for p in _journey().run(STUDY)["pending"]}
    assert pending["H-Model layout"] == ["AIA-H8", "M2"]
    assert set(pending) == {
        "H-Model layout",
        "H-Model significance",
        "STORM map (respondents)",
        "WIND surface",
        "Interactive 3D",
        "Report",
    }


def test_the_journey_prints() -> None:
    assert _journey().main(["--summary"]) == 0


def _pearson(a: list[float], b: list[float]) -> float:
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True))
    return num / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
