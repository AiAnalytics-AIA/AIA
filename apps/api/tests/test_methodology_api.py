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
from aia_core.domain.sociomap.specification import AIA_SOCIOMAP_V3
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


def test_a_step_carries_its_editable_formula_written_from_its_expression(
    owner: TestClient,
) -> None:
    body = owner.get(f"{METHODOLOGY}/sociomap").json()
    step = next(s for s in body["step_details"] if s["id"] == "f6_distance")
    (formula,) = step["formulas"]
    assert formula["slot_id"] == "f6.distance"
    assert formula["expression"] == "sqrt(max(0, 2 * (1 - r)))"
    assert formula["latex"] == r"\sqrt{\max\left(0, 2 \cdot \left(1 - r_{ij}\right)\right)}"
    assert [v["name"] for v in formula["variables"]] == ["r"]
    assert {p["kind"] for p in formula["properties"]} >= {"non_negative", "equals_at"}
    algorithm = next(s for s in body["step_details"] if s["id"] == "f6_smacof")
    assert algorithm["formulas"] == []  # an algorithm, not a formula


def test_an_unknown_module_or_preset_is_404(owner: TestClient) -> None:
    missing = owner.get(f"{METHODOLOGY}/nothing")
    assert missing.status_code == 404
    assert missing.json()["code"] == "unknown_module"
    preset = owner.get(f"{METHODOLOGY}/sociomap", params={"preset": "aia-sociomap-9"})
    assert preset.status_code == 404
    assert preset.json()["code"] == "unknown_preset"


def test_the_only_writes_are_a_version_a_check_and_an_activation() -> None:
    from aia_api.config import Environment, Settings
    from aia_api.main import create_app

    spec = create_app(Settings(env=Environment.LOCAL)).openapi()
    writes = {
        (path.removeprefix(METHODOLOGY), method)
        for path, operations in spec["paths"].items()
        if path.startswith(METHODOLOGY)
        for method in operations
        if method != "get"
    }
    assert writes == {
        ("/{module_id}/check", "post"),
        ("/{module_id}/versions", "post"),
        ("/{module_id}/activation", "put"),
    }


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


# --------------------------------------------------------------------------- versions (A5b)

SOCIOMAP = f"{METHODOLOGY}/sociomap"


def _edit(formulas: dict[str, str] | None = None, **changes: Any) -> dict[str, Any]:
    spec = AIA_SOCIOMAP_V3.model_dump(mode="json")
    for path, value in changes.items():
        node = spec
        *parents, leaf = path.split("__")
        for p in parents:
            node = node[p]
        node[leaf] = value
    return {"base_preset": "aia-sociomap-3", "spec": spec, "formulas": formulas or {}}


@pytest.mark.parametrize("who", ["lead", "researcher", "outsider"])
def test_a_member_reads_and_checks_but_cannot_change(who: str, as_user: Any) -> None:
    member: TestClient = as_user(who)
    versions = member.get(f"{SOCIOMAP}/versions")
    assert versions.status_code == 200 and versions.json()["may_administer"] is False
    assert member.post(f"{SOCIOMAP}/check", json=_edit()).json()["valid"] is True
    proposed = member.post(f"{SOCIOMAP}/versions", json=_edit())
    assert proposed.status_code == 403 and proposed.json()["code"] == "insufficient_role"
    put = member.put(f"{SOCIOMAP}/activation", json={"version_number": None})
    assert put.status_code == 403


def test_with_nothing_stored_the_codes_preset_is_in_force(owner: TestClient) -> None:
    body = owner.get(f"{SOCIOMAP}/versions").json()
    assert body["in_force"] == {
        "origin": "code",
        "preset": "aia-sociomap-3",
        "version_number": None,
        "name": "aia-sociomap-3",
    }
    assert (body["may_administer"], body["versions"], body["history"]) == (True, [], [])


def test_propose_then_activate_puts_an_edit_in_force_and_reset_returns_the_preset(
    owner: TestClient,
) -> None:
    proposed = owner.post(
        f"{SOCIOMAP}/versions", json={**_edit(terrain__sigma=0.3), "note": "širší kopec"}
    )
    assert proposed.status_code == 201
    version = proposed.json()
    assert (version["version_number"], version["name"]) == (1, "aia-sociomap-3+e1")
    assert version["spec"]["terrain"]["sigma"] == 0.3
    assert version["spec"]["methodology_version"] == "aia-sociomap-3+e1"
    assert owner.get(f"{SOCIOMAP}/versions").json()["in_force"]["origin"] == "code"

    put = owner.put(f"{SOCIOMAP}/activation", json={"version_number": 1, "reason": "ověřeno"})
    assert put.status_code == 200
    assert put.json() == {
        "origin": "stored",
        "preset": None,
        "version_number": 1,
        "name": "aia-sociomap-3+e1",
    }
    back = owner.put(f"{SOCIOMAP}/activation", json={"version_number": None, "reason": "zpět"})
    assert back.json()["origin"] == "code"
    body = owner.get(f"{SOCIOMAP}/versions").json()
    assert [v["version_number"] for v in body["versions"]] == [1]
    assert [(a["version_number"], a["reason"]) for a in body["history"]] == [
        (None, "zpět"),
        (1, "ověřeno"),
    ]


def test_an_invalid_edit_is_422_with_every_problem_and_check_says_the_same(
    owner: TestClient,
) -> None:
    edit = _edit({"f6.distance": "open('x')"}, relation__n_min=2)
    checked = owner.post(f"{SOCIOMAP}/check", json=edit).json()
    assert checked["valid"] is False
    assert {"spec.relation.n_min", "formula.f6.distance"} <= set(checked["problems"])
    refused = owner.post(f"{SOCIOMAP}/versions", json=edit)
    assert refused.status_code == 422 and refused.json()["code"] == "methodology_invalid"
    assert refused.json()["details"]["problems"] == checked["problems"]
    assert owner.get(f"{SOCIOMAP}/versions").json()["versions"] == []


def test_a_replaced_formula_is_stored_and_put_in_force(owner: TestClient) -> None:
    """The engine computes every slot from its expression (plan S4c), so nothing is left
    that a version could store but not put in force."""
    edit = _edit({"f12.kernel": "h * exp(-d2 / (2 * sigma ** 2))"})
    checked = owner.post(f"{SOCIOMAP}/check", json=edit).json()
    assert (checked["valid"], checked["not_computed"]) == (True, [])
    number = owner.post(f"{SOCIOMAP}/versions", json=edit).json()["version_number"]
    put = owner.put(f"{SOCIOMAP}/activation", json={"version_number": number})
    assert put.status_code == 200 and put.json()["origin"] == "stored"


def test_the_reference_map_is_never_edited(owner: TestClient) -> None:
    edit = {"base_preset": "aia-sociomap-1", "spec": {}, "formulas": {}}
    refused = owner.post(f"{METHODOLOGY}/sociomap_reference/versions", json=edit)
    assert refused.status_code == 422 and "module" in refused.json()["details"]["problems"]


def test_unknown_module_or_version_is_404(owner: TestClient) -> None:
    for response in (
        owner.get(f"{METHODOLOGY}/nothing/versions"),
        owner.post(f"{METHODOLOGY}/nothing/check", json=_edit()),
        owner.post(f"{METHODOLOGY}/nothing/versions", json=_edit()),
    ):
        assert response.status_code == 404 and response.json()["code"] == "unknown_module"
    missing = owner.put(f"{SOCIOMAP}/activation", json={"version_number": 7})
    assert missing.status_code == 404 and missing.json()["code"] == "unknown_version"


def test_a_malformed_request_is_422_before_the_domain(owner: TestClient) -> None:
    assert owner.post(f"{SOCIOMAP}/versions", json={"spec": {}}).status_code == 422
    zero = owner.put(f"{SOCIOMAP}/activation", json={"version_number": 0})
    assert zero.status_code == 422
    long_note = owner.post(f"{SOCIOMAP}/versions", json={**_edit(), "note": "x" * 501})
    assert long_note.status_code == 422


def test_an_edit_starts_from_a_preset_the_versions_route_serves_whole(owner: TestClient) -> None:
    presets = owner.get(f"{SOCIOMAP}/versions").json()["presets"]
    assert set(presets) == {"aia-sociomap-3", "aia-sociomap-2"}
    assert presets["aia-sociomap-3"] == AIA_SOCIOMAP_V3.model_dump(mode="json")
    assert owner.get(f"{METHODOLOGY}/sociomap_reference/versions").json()["presets"] == {}


def test_check_writes_each_replaced_formula_as_latex(owner: TestClient) -> None:
    edit = _edit({"f12.kernel": "h * exp(-d2 / (2 * sigma ** 2))"})
    written = owner.post(f"{SOCIOMAP}/check", json=edit).json()["formulas_latex"]
    assert set(written) == {"f12.kernel"}
    assert "\\exp" in written["f12.kernel"] and "\\sigma" in written["f12.kernel"]
