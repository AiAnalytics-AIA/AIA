"""The interval cases the audience screen shares with the population (artifact-audience F3).

``fixtures/audience_interval/cases.json`` says which stored values ``_interval`` refuses; the web's
``rangeHolds`` reads the same file (``apps/web/src/research/audience.live.test.ts``), so the screen
warns exactly where a preview or a run would refuse the audience.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.population.audience import Factor, _interval

CASES: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent / "fixtures" / "audience_interval" / "cases.json").read_text("utf-8")
)["cases"]
SPEC = Factor(name="vek", kind="numeric", filterable=True, minimum=18.0, maximum=89.0)


@pytest.mark.parametrize("case", CASES, ids=[json.dumps(c["value"]) for c in CASES])
def test_the_interval_rule_refuses_what_the_case_says(case: dict[str, Any]) -> None:
    assert isinstance(_interval(case["value"], SPEC), str) is case["refused"]
