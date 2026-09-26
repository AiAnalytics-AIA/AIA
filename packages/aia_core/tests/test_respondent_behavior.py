"""The ported response process against captures of the unit's own functions.

``fixtures/response_process/`` was written by ``tools/respondent_capture.py``,
which ran 18.6.6's unmodified ``behavior.adjust_probabilities`` and
``styly.prirad_styly`` on fictional inputs. The pins below make a change to either
the fixture or the unit's source visible.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.respondent_behavior import (
    STYLES,
    ResponseQuestion,
    adjust_probabilities,
    assign_styles,
    draw_index,
    normalise,
)

FIXTURES = Path(__file__).parent / "fixtures" / "response_process"
UNIT = Path(__file__).resolve().parents[3] / "legacy" / "npc-panel-18.6.6" / "app"
INDEX = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))


def _load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_fixtures_are_pinned_and_the_unit_sources_are_the_ones_captured() -> None:
    for name, sha in INDEX["fixtures"].items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == sha, name
    for name, sha in INDEX["unit_sources"].items():
        assert hashlib.sha256((UNIT / name).read_bytes()).hexdigest() == sha, name


CASES = _load("behavior.json")["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_adjust_probabilities_matches_the_unit(case: dict[str, Any]) -> None:
    question = ResponseQuestion(
        typ=case["typ"],
        labels=tuple(case["labels"]),
        scale=tuple(case["scale"]) if case["scale"] else None,
        allow_dont_know=case["dk"],
        process=case["process"],
    )
    p, meta = adjust_probabilities(case["probabilities"], question, case["style"])
    want = case["expected"]
    assert p == pytest.approx(want["probabilities"], abs=1e-12)
    assert list(meta.applied) == want["applied"]
    assert meta.l1_shift == pytest.approx(want["l1_shift"], abs=1e-6)
    assert meta.base_max_prob == want["base_max_prob"]
    assert meta.adjusted_max_prob == pytest.approx(want["adjusted_max_prob"], abs=1e-6)


def test_every_mechanism_is_exercised_by_the_captures() -> None:
    seen = {m.split(":")[0] for c in CASES for m in c["expected"]["applied"]}
    assert seen == {"social_desirability", "acquiescence", "extremity", "dont_know", "satisficing"}


def test_styles_match_the_unit() -> None:
    captured = _load("styles.json")
    mine = assign_styles(captured["rows"])
    for got, want in zip(mine, captured["expected"], strict=True):
        assert set(got) == set(STYLES)
        for style in STYLES:
            assert got[style] == pytest.approx(want[style], abs=1e-9)


def test_a_respondent_keeps_their_style_whoever_else_is_in_the_roster() -> None:
    """Stable noise: the hash part depends on the id alone (styly._stabilni_sum)."""
    rows = [{"respondent_id": f"FIC-R{i}"} for i in range(5)]
    alone = assign_styles(rows[:1] + rows[1:])
    again = assign_styles(rows)
    assert alone == again


@pytest.mark.parametrize("bad", [[0.0, 0.0], [-1.0, 0.0], [float("nan"), 1.0], []])
def test_a_vector_without_positive_finite_mass_is_refused(bad: list[float]) -> None:
    with pytest.raises(ValueError):
        normalise(bad)


def test_the_draw_is_seeded_and_follows_the_distribution() -> None:
    p = [0.2, 0.5, 0.3]
    assert draw_index(p, 7) == draw_index(p, 7)
    counts = [0, 0, 0]
    for seed in range(20000):
        counts[draw_index(p, seed)] += 1
    assert [c / 20000 for c in counts] == pytest.approx(p, abs=0.02)
    assert draw_index([0.0, 0.0, 1.0], 3) == 2
