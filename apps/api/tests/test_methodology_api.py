"""The Metodika catalogue over HTTP: any member reads it; every value comes from the code.

ADR 0023; plan ``methodology-tab.md`` chunk A5a. The route only serialises what the domain
reads, so these tests pin the wire: who may read, the shape, a value read from the preset in
force, a value the preset omits marked absent (never a zero), and a code constant labelled as
code.
"""

from __future__ import annotations

from typing import Any

import pytest
from aia_core.domain.methodology import MODULES
from aia_core.domain.sociomap.view import STRESS_QUALITY_BANDS
from fastapi.testclient import TestClient

API = "/api/v1"
METHODOLOGY = f"{API}/methodology"


def _values(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {v["reference"]: v for s in body["step_details"] for v in s["values"]}


def test_unauthenticated_is_refused(client: TestClient) -> None:
    assert client.get(METHODOLOGY).status_code == 401
    assert client.get(f"{METHODOLOGY}/sociomap").status_code == 401


@pytest.mark.parametrize("who", ["lead", "researcher", "outsider"])
def test_every_member_reads_the_methodology(who: str, as_user: Any) -> None:
    member: TestClient = as_user(who)
    assert member.get(METHODOLOGY).status_code == 200
    assert member.get(f"{METHODOLOGY}/sociomap").status_code == 200


def test_the_list_is_every_registered_module_in_order(owner: TestClient) -> None:
    body = owner.get(METHODOLOGY).json()
    assert [m["id"] for m in body] == [m.id for m in MODULES]
    sociomap = body[0]
    assert sociomap["in_force"] == "aia-sociomap-3"
    assert sociomap["presets"] == ["aia-sociomap-3", "aia-sociomap-2"]
    assert [g["id"] for g in sociomap["groups"]][:3] == ["M", "F1", "F2"]


def test_a_module_reads_every_value_from_the_preset_in_force(owner: TestClient) -> None:
    body = owner.get(f"{METHODOLOGY}/sociomap").json()
    assert body["preset"] == "aia-sociomap-3"
    values = _values(body)
    n_min = values["relation.n_min"]
    assert (n_min["value"], n_min["origin"], n_min["absent"]) == (30, "specification", False)
    assert values["relation.basis"]["value"] == "kish_effective_n"  # an enum, as its value
    sigma = values["terrain.sigma"]
    assert (sigma["value"], sigma["unit"]) == (0.25, "jednotky vzdálenosti")


def test_a_code_constant_is_labelled_as_code_and_is_plain_json(owner: TestClient) -> None:
    values = _values(owner.get(f"{METHODOLOGY}/sociomap").json())
    bands = values["aia_core.domain.sociomap.view:STRESS_QUALITY_BANDS"]
    assert bands["origin"] == "code_constant"
    assert bands["value"] == [[bound, label.value] for bound, label in STRESS_QUALITY_BANDS]


def test_another_preset_marks_what_it_omits_absent_not_zero(owner: TestClient) -> None:
    body = owner.get(f"{METHODOLOGY}/sociomap", params={"preset": "aia-sociomap-2"}).json()
    sigma = _values(body)["terrain.sigma"]
    assert (sigma["value"], sigma["absent"]) == (None, True)
    floor = _values(body)["relation.effect_floor"]
    assert (floor["value"], floor["absent"]) == (None, False)  # declared null, not omitted


def test_a_step_carries_its_formula_evidence_and_tests(owner: TestClient) -> None:
    body = owner.get(f"{METHODOLOGY}/sociomap").json()
    step = next(s for s in body["step_details"] if s["id"] == "f6_distance")
    assert r"\sqrt" in step["formula_latex"]
    assert step["implements"] == "aia_core.domain.sociomap.layout:correlation_distance"
    assert len(step["source_sha256"]) == 64
    assert {"kind": "register_rule", "ref": "AUDIT-F6", "note_cs": ""} in step["evidence"]
    assert step["tests"]


def test_an_unknown_module_or_preset_is_404(owner: TestClient) -> None:
    missing = owner.get(f"{METHODOLOGY}/nothing")
    assert missing.status_code == 404
    assert missing.json()["code"] == "unknown_module"
    preset = owner.get(f"{METHODOLOGY}/sociomap", params={"preset": "aia-sociomap-9"})
    assert preset.status_code == 404
    assert preset.json()["code"] == "unknown_preset"


def test_nothing_here_writes() -> None:
    from aia_api.config import Environment, Settings
    from aia_api.main import create_app

    spec = create_app(Settings(env=Environment.LOCAL)).openapi()
    methods = {
        method
        for path, operations in spec["paths"].items()
        if path.startswith(METHODOLOGY)
        for method in operations
    }
    assert methods == {"get"}


def test_the_web_fixture_is_what_the_api_serves() -> None:
    """The web client renders every formula from this file; a stale one tests nothing."""
    import importlib.util
    from pathlib import Path

    repo = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("fixture", repo / "tools/methodology_fixture.py")
    assert spec is not None and spec.loader is not None
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    current = tool.FIXTURE.read_text(encoding="utf-8")
    assert current == tool.render(), "run: python tools/methodology_fixture.py"
