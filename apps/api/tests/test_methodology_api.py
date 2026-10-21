"""The Metodika catalogue over HTTP: any member reads it; every value comes from the code.

ADR 0023; plan ``methodology-tab.md`` chunk A5a. The route only serialises what the domain
reads, so these tests pin the wire: who may read, the shape, a value read from the preset in
force, a value the preset omits marked absent (never a zero), and a code constant labelled as
code.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from aia_core.domain.evidence.support import AIA_SUPPORT_V1
from aia_core.domain.methodology import MODULES
from aia_core.domain.research_aggregate import AIA_AGGREGATE_V1
from aia_core.domain.research_design import AIA_READINESS_V1
from aia_core.domain.respondent_behavior import AIA_RESPONSE_V1
from aia_core.domain.sociomap.specification import AIA_SOCIOMAP_V3, AIA_SOCIOMAP_V5
from aia_core.domain.sociomap.view import STRESS_QUALITY_BANDS
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.tables import MethodologyVersionRow
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

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
    assert sociomap["in_force"] == "aia-sociomap-5"
    # aia-sociomap-5, what every new run pins, is listed first; the earlier ones stay offered.
    assert sociomap["presets"] == [
        "aia-sociomap-5",
        "aia-sociomap-4",
        "aia-sociomap-3",
        "aia-sociomap-2",
    ]
    # The computation by its stages (product owner, 2026-10-14), no longer the audit's F1-F16.
    assert [g["id"] for g in sociomap["groups"]][:3] == ["M", "S1", "S2"]


def test_a_module_reads_every_value_from_the_preset_in_force(owner: TestClient) -> None:
    body = owner.get(f"{METHODOLOGY}/sociomap").json()
    assert body["preset"] == "aia-sociomap-5"
    values = _values(body)
    n_min = values["relation.n_min"]
    assert (n_min["value"], n_min["origin"], n_min["absent"]) == (10, "specification", False)
    assert values["relation.basis"]["value"] == "respondent_count"  # an enum, as its value
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
    # No floor is left out of -2's stored form, so an edit from it cannot set one: absent.
    assert (floor["value"], floor["absent"]) == (None, True)


def test_a_step_carries_its_formula_evidence_and_tests(owner: TestClient) -> None:
    body = owner.get(f"{METHODOLOGY}/sociomap").json()
    step = next(s for s in body["step_details"] if s["id"] == "f6_distance")
    assert r"\sqrt" in step["formula_latex"]
    assert step["implements"] == "aia_core.domain.sociomap.layout:correlation_distance"
    assert len(step["source_sha256"]) == 64
    assert {"kind": "register_rule", "ref": "AUDIT-F6", "note_cs": ""} in step["evidence"]
    assert step["tests"]


def test_a_step_says_where_it_sits_in_the_computation(owner: TestClient) -> None:
    body = owner.get(f"{METHODOLOGY}/sociomap").json()
    step = next(s for s in body["step_details"] if s["id"] == "f6_distance")
    assert step["role_cs"].startswith("Převede korelaci na vzdálenost")
    assert step["inputs"] == ["f3_correlation", "f3_status"]
    # The steps that read it are derived, never declared twice.
    assert step["feeds"] == ["f6_smacof", "f7_stress"]
    assert step["audit"] == "F6"
    first = next(s for s in body["step_details"] if s["id"] == "f1_declared_scale")
    assert first["inputs"] == [] and first["source_cs"].startswith("odpovědi respondentů")


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
    assert any("známé páry" in line for line in formula["kept_cs"])  # what stays code
    algorithm = next(s for s in body["step_details"] if s["id"] == "f6_smacof")
    assert algorithm["formulas"] == []  # an algorithm, not a formula


def test_an_unknown_module_or_preset_is_404(owner: TestClient) -> None:
    missing = owner.get(f"{METHODOLOGY}/nothing")
    assert missing.status_code == 404
    assert missing.json()["code"] == "unknown_module"
    preset = owner.get(f"{METHODOLOGY}/sociomap", params={"preset": "aia-sociomap-9"})
    assert preset.status_code == 404
    assert preset.json()["code"] == "unknown_preset"


def test_the_only_writes_are_a_version_an_activation_and_two_checks() -> None:
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
        ("/{module_id}/compare", "post"),
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
        "preset": "aia-sociomap-5",
        "version_number": None,
        "name": "aia-sociomap-5",
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
    assert set(presets) == {"aia-sociomap-5", "aia-sociomap-4", "aia-sociomap-3", "aia-sociomap-2"}
    assert presets["aia-sociomap-3"] == AIA_SOCIOMAP_V3.model_dump(mode="json")
    assert owner.get(f"{METHODOLOGY}/sociomap_reference/versions").json()["presets"] == {}


def test_check_writes_each_replaced_formula_as_latex(owner: TestClient) -> None:
    edit = _edit({"f12.kernel": "h * exp(-d2 / (2 * sigma ** 2))"})
    written = owner.post(f"{SOCIOMAP}/check", json=edit).json()["formulas_latex"]
    assert set(written) == {"f12.kernel"}
    assert "\\exp" in written["f12.kernel"] and "\\sigma" in written["f12.kernel"]


def test_a_member_compares_an_edit_with_what_is_in_force_on_fictional_panels(
    as_user: Any,
) -> None:
    member: TestClient = as_user("researcher")
    # An edit of what is in force, aia-sociomap-5, with a stricter pair n_min.
    edit = {**_edit(), "base_preset": "aia-sociomap-5"}
    edit["spec"] = AIA_SOCIOMAP_V5.model_dump(mode="json")
    edit["spec"]["relation"]["n_min"] = 34
    body = member.post(f"{SOCIOMAP}/compare", json=edit).json()
    assert (body["valid"], body["in_force"]) == (True, "aia-sociomap-5")
    panels = {p["panel"]: p for p in body["panels"]}
    assert set(panels) == {"balanced", "weighted", "small"}
    small = panels["small"]
    assert small["status_changes"] and all(c["draft"] == "unknown" for c in small["status_changes"])
    assert set(small["heights"]) == set(small["objects"])
    assert all(len(pair) == 2 for pair in small["k100"].values())
    assert any("interval" in n for n in small["notes"])


def test_compare_refuses_an_invalid_edit_with_its_problems_and_computes_nothing(
    owner: TestClient,
) -> None:
    body = owner.post(f"{SOCIOMAP}/compare", json=_edit(relation__n_min=2)).json()
    assert body["valid"] is False and body["panels"] == []
    assert "spec.relation.n_min" in body["problems"]


def test_compare_is_for_the_editable_modules(owner: TestClient) -> None:
    edit = {"base_preset": "aia-sociomap-1", "spec": {}, "formulas": {}}
    reference = owner.post(f"{METHODOLOGY}/sociomap_reference/compare", json=edit)
    assert reference.status_code == 422 and reference.json()["code"] == "no_comparison"
    assert owner.post(f"{METHODOLOGY}/nothing/compare", json=_edit()).status_code == 404


def test_compare_reads_the_stored_version_in_force(owner: TestClient) -> None:
    number = owner.post(f"{SOCIOMAP}/versions", json=_edit(terrain__sigma=0.3)).json()[
        "version_number"
    ]
    owner.put(f"{SOCIOMAP}/activation", json={"version_number": number})
    body = owner.post(f"{SOCIOMAP}/compare", json=_edit()).json()
    assert body["in_force"] == "aia-sociomap-3+e1"
    assert all(p["terrain_max_change"] > 0 for p in body["panels"])  # 0.3 in force, 0.25 drafted


# --------------------------------------------------------------------------- support (G1d)

SUPPORT = f"{METHODOLOGY}/support"


def _support_edit(**lines: Any) -> dict[str, Any]:
    """``aia-support-1`` with lines changed: ``results__min_layer_donors=10``."""
    spec = AIA_SUPPORT_V1.model_dump(mode="json")
    for path, value in lines.items():
        rule, line = path.split("__")
        spec[rule][line] = value
    return {"base_preset": "aia-support-1", "spec": spec, "formulas": {}}


def test_support_is_edited_both_ways_and_put_in_force(owner: TestClient) -> None:
    presets = owner.get(f"{SUPPORT}/versions").json()["presets"]
    assert presets == {"aia-support-1": AIA_SUPPORT_V1.model_dump(mode="json")}
    looser = owner.post(f"{SUPPORT}/versions", json=_support_edit(results__min_layer_donors=10))
    stricter = owner.post(
        f"{SUPPORT}/versions",
        json=_support_edit(results__min_cell=80, analysis__min_cell=80, analysis__n_guard=None),
    )
    assert (looser.status_code, stricter.status_code) == (201, 201)
    assert stricter.json()["spec"]["results"]["min_cell"] == 80
    assert stricter.json()["spec"]["analysis"]["n_guard"] is None
    put = owner.put(f"{SUPPORT}/activation", json={"version_number": 2, "reason": "přísněji"})
    assert put.json()["name"] == "aia-support-1+e2"


def test_a_support_rule_that_suppresses_nothing_is_refused(owner: TestClient) -> None:
    edit = _support_edit(results__min_layer_donors=None)
    checked = owner.post(f"{SUPPORT}/check", json=edit).json()
    assert checked["valid"] is False and set(checked["problems"]) == {"spec.results"}
    refused = owner.post(f"{SUPPORT}/versions", json=edit)
    assert refused.status_code == 422 and refused.json()["code"] == "methodology_invalid"
    backwards = owner.post(f"{SUPPORT}/check", json=_support_edit(analysis__indicative=10.0)).json()
    assert backwards["valid"] is False and "spec.analysis" in backwards["problems"]


def test_the_support_draft_check_lists_every_cell_newly_reported_or_suppressed(
    as_user: Any,
) -> None:
    member: TestClient = as_user("researcher")
    same = member.post(f"{SUPPORT}/compare", json=_support_edit()).json()
    assert (same["valid"], same["in_force"], same["panels"]) == (True, "aia-support-1", [])
    assert len(same["support"]["cells"]) == 16
    assert same["support"]["newly_reported"] == same["support"]["newly_suppressed"] == []
    assert all(c["changes"] == {} for c in same["support"]["cells"])

    looser = member.post(
        f"{SUPPORT}/compare",
        json=_support_edit(results__min_layer_donors=10, results__indicative_layer_donors=20),
    ).json()["support"]
    assert looser["draft"] == "aia-support-1+e1"
    assert ["maly.q1", "results"] in looser["newly_reported"]
    assert ["maly.q1", "analysis"] not in looser["newly_reported"]  # the gate still says no
    assert looser["newly_suppressed"] == []

    stricter = member.post(f"{SUPPORT}/compare", json=_support_edit(analysis__min_cell=200)).json()[
        "support"
    ]
    assert ["stredni.q2", "analysis"] in stricter["newly_suppressed"]
    assert all(surface == "analysis" for _, surface in stricter["newly_suppressed"])


# ----------------------------------------------------------------------- aggregation (G3b)

AGGREGATION = f"{METHODOLOGY}/aggregation"


def _aggregation_edit(formulas: dict[str, str] | None = None, **values: Any) -> dict[str, Any]:
    """``aia-aggregate-1`` with values changed (``bootstrap__reps=200``) and formulas replaced."""
    spec = AIA_AGGREGATE_V1.model_dump(mode="json")
    for path, value in values.items():
        node = spec
        *parents, leaf = path.split("__")
        for p in parents:
            node = node[p]
        node[leaf] = value
    return {"base_preset": "aia-aggregate-1", "spec": spec, "formulas": formulas or {}}


def test_aggregation_is_edited_and_put_in_force_with_its_formulas(owner: TestClient) -> None:
    presets = owner.get(f"{AGGREGATION}/versions").json()["presets"]
    assert presets == {"aia-aggregate-1": AIA_AGGREGATE_V1.model_dump(mode="json")}
    edit = _aggregation_edit({"agg.top_box": "x >= top"}, top_box=1)
    checked = owner.post(f"{AGGREGATION}/check", json=edit).json()
    assert (checked["valid"], checked["not_computed"]) == (True, [])
    assert set(checked["formulas_latex"]) == {"agg.top_box"}
    stored = owner.post(f"{AGGREGATION}/versions", json=edit)
    assert stored.status_code == 201 and stored.json()["name"] == "aia-aggregate-1+e1"
    put = owner.put(f"{AGGREGATION}/activation", json={"version_number": 1, "reason": "test"})
    assert put.status_code == 200 and put.json()["origin"] == "stored"


def test_an_aggregation_formula_that_breaks_its_slot_is_refused(owner: TestClient) -> None:
    edit = _aggregation_edit({"agg.share": "200 * sum(w * hit) / sum(w)"})
    checked = owner.post(f"{AGGREGATION}/check", json=edit).json()
    assert checked["valid"] is False
    assert any(k.startswith("formula.agg.share") for k in checked["problems"])
    assert owner.post(f"{AGGREGATION}/versions", json=edit).status_code == 422


def test_the_aggregation_draft_check_names_every_estimate_it_moves(as_user: Any) -> None:
    member: TestClient = as_user("researcher")
    body = member.post(f"{AGGREGATION}/compare", json=_aggregation_edit(top_box=1)).json()
    assert (body["valid"], body["in_force"], body["panels"]) == (True, "aia-aggregate-1", [])
    check = body["aggregation"]
    assert check["draft"] == "aia-aggregate-1+e1"
    assert [p["panel"] for p in check["panels"]] == ["maly", "vazeny", "velky"]
    for panel in check["panels"]:
        moved = {(r["question"], r["measure"]) for r in panel["rows"] if r["moved"]}
        assert moved == {("spokojenost", "top2box"), ("doporuceni", "top2box")}
        assert panel["status_changes"] == []  # a top box decides no status
        assert set(panel["effective_n"]) == {"spokojenost", "doporuceni", "volba", "kanaly"}


# ------------------------------------------------------------------- response process (R1c)

RESPONSE = f"{METHODOLOGY}/response"


def _response_edit(**values: Any) -> dict[str, Any]:
    """``aia-response-1`` with values changed (``satisficing__cap=0.2``)."""
    spec = AIA_RESPONSE_V1.model_dump(mode="json")
    for path, value in values.items():
        node = spec
        *parents, leaf = path.split("__")
        for p in parents:
            node = node[p]
        node[leaf] = value
    return {"base_preset": "aia-response-1", "spec": spec, "formulas": {}}


def test_the_response_process_is_edited_and_put_in_force(owner: TestClient) -> None:
    presets = owner.get(f"{RESPONSE}/versions").json()["presets"]
    assert presets == {"aia-response-1": AIA_RESPONSE_V1.model_dump(mode="json")}
    edit = _response_edit(extremity=0.5, style_links__sdilnost__education=0.4)
    assert owner.post(f"{RESPONSE}/check", json=edit).json()["valid"] is True
    stored = owner.post(f"{RESPONSE}/versions", json=edit)
    assert stored.status_code == 201 and stored.json()["name"] == "aia-response-1+e1"
    put = owner.put(f"{RESPONSE}/activation", json={"version_number": 1, "reason": "test"})
    assert put.status_code == 200 and put.json()["origin"] == "stored"


def test_a_response_process_that_cannot_be_read_is_refused_with_its_problem(
    owner: TestClient,
) -> None:
    body = owner.post(f"{RESPONSE}/check", json=_response_edit(satisficing__cap=1.5)).json()
    assert body["valid"] is False and "spec.satisficing.cap" in body["problems"]
    refused = owner.post(f"{RESPONSE}/versions", json=_response_edit(style_noise_floor=0.0))
    assert refused.status_code == 422


def test_the_response_draft_check_answers_fixed_questions_under_both_processes(
    as_user: Any,
) -> None:
    member: TestClient = as_user("researcher")
    same = member.post(f"{RESPONSE}/compare", json=_response_edit()).json()
    assert (same["valid"], same["in_force"], same["panels"]) == (True, "aia-response-1", [])
    check = same["response"]
    assert check["respondents"] == 80 and len(check["questions"]) == 4
    assert all(q["in_force"] == q["draft"] and q["moved_pp"] == 0 for q in check["questions"])
    assert check["described_in_force"] == check["described_draft"]

    sharper = member.post(
        f"{RESPONSE}/compare", json=_response_edit(extremity=1.0, describe_threshold=1.5)
    ).json()["response"]
    assert sharper["draft"] == "aia-response-1+e1"
    scale = {q["question"]: q for q in sharper["questions"]}["skala7"]
    assert scale["shift_draft"] > scale["shift_in_force"]  # each respondent moves further
    assert sharper["described_draft"] < sharper["described_in_force"]


# ------------------------------------------------------------- readiness (V1a1, V1a2)

READINESS = f"{METHODOLOGY}/readiness"


def _readiness_edit(**limits: Any) -> dict[str, Any]:
    spec = AIA_READINESS_V1.model_dump(mode="json")
    for path, value in limits.items():
        part, field = path.split("__")
        spec[part][field] = value
    return {"base_preset": "aia-readiness-1", "spec": spec, "formulas": {}}


def _readiness_draft(n: int, items: int) -> dict[str, Any]:
    return {
        "content": {
            "title": "Fiktivní nápoje",
            "n": n,
            "sections": [
                {
                    "type": "object_battery",
                    "title": "Nápoje",
                    "object_family": "nápoje",
                    "objects": [f"Nápoj {i}" for i in range(1, items + 1)],
                }
            ],
        },
        "base_revision": None,
    }


def test_each_limit_says_what_crossing_it_does_and_the_rule_reads_with_its_values(
    owner: TestClient,
) -> None:
    body = owner.get(READINESS).json()
    values = _values(body)
    assert values["sample_size.min"]["effect"] == "blocks_run"
    assert values["tracked_set.max"]["effect"] == "blocks_design"
    assert values["tracked_set.recommended_min"]["effect"] == "warns"
    assert values["methodology_version"]["effect"] == ""
    steps = {s["id"]: s for s in body["step_details"]}
    assert steps["sample_size"]["reading_cs"] == "{sample_size.min} ≤ n ≤ {sample_size.max}"
    assert "chybějící n blokuje vždy" in steps["sample_size"]["keeps_cs"]


def test_the_readiness_check_previews_the_lines_the_code_writes_under_the_draft(
    owner: TestClient,
) -> None:
    preset = owner.post(f"{READINESS}/check", json=_readiness_edit()).json()
    assert [(p["step_id"], p["status"]) for p in preset["preview"]] == [
        ("sample_size", "FAIL"),
        ("sample_size", "PASS"),
        ("tracked_set", "WARN"),
        ("tracked_set", "FAIL"),
    ]
    wider = owner.post(
        f"{READINESS}/check",
        json=_readiness_edit(
            sample_size__min=10, tracked_set__max=50, tracked_set__recommended_max=20
        ),
    ).json()
    assert [p["status"] for p in wider["preview"]] == ["PASS", "PASS", "PASS", "WARN"]
    assert wider["preview"][0]["message_cs"] == "n = 12."
    refused = owner.post(f"{READINESS}/check", json=_readiness_edit(sample_size__max=5)).json()
    assert refused["valid"] is False and refused["preview"] == []
    # A module that shows no preview answers an empty list.
    assert owner.post(f"{SOCIOMAP}/check", json=_edit()).json()["preview"] == []


def test_the_study_reads_the_valid_n_in_force_and_an_activation_moves_it(
    owner: TestClient, world: Any, as_user: Any
) -> None:
    """RQC9: one authority for a valid n. The web reads the readiness limits in force from
    the Study instead of a range of its own, so an activated version is what it refuses by."""
    member = as_user("lead")
    limits = f"{API}/studies/{world.study_id()}/research/limits"
    preset = member.get(limits)
    assert preset.status_code == 200, preset.text
    assert preset.json() == {
        "methodology_version": "aia-readiness-1",
        "version": None,
        "sample_size": {"min": 20, "max": 10000},
    }
    number = owner.post(
        f"{READINESS}/versions",
        json={**_readiness_edit(sample_size__min=100, sample_size__max=800), "note": "užší"},
    ).json()["version_number"]
    put = owner.put(f"{READINESS}/activation", json={"version_number": number, "reason": "test"})
    assert put.status_code == 200, put.text
    edited = member.get(limits).json()
    assert edited["version"] == number and edited["sample_size"] == {"min": 100, "max": 800}
    assert edited["methodology_version"] == "aia-readiness-1+e1"


def test_an_unknown_study_has_no_limits_to_read(as_user: Any) -> None:
    # Read through the Study's scope like every research route: a study not found is a 404.
    got = as_user("lead").get(f"{API}/studies/STU-0000ffff/research/limits")
    assert got.status_code == 404, got.text


def test_readiness_compare_lists_the_studies_whose_verdict_the_draft_moves(
    world: Any, as_user: Any
) -> None:
    lead = as_user("lead")
    for study, n in (("primary", 15), ("sibling", 450)):
        saved = lead.put(
            f"{API}/studies/{world.study_id(study)}/workspace/content",
            json=_readiness_draft(n, 5),
        )
        assert saved.status_code == 200, saved.text
    compared = lead.post(f"{READINESS}/compare", json=_readiness_edit(sample_size__min=10))
    assert compared.status_code == 200, compared.text
    body = compared.json()
    assert body["valid"] is True and body["in_force"] == "aia-readiness-1"
    impact = body["readiness"]
    assert impact["draft"] == "aia-readiness-1+e1"
    (moved,) = impact["studies"]
    assert (moved["study_id"], moved["name"], moved["n"]) == (
        world.study_id("primary"),
        "Acme brand",
        15,
    )
    assert moved["ready"] == [False, True] and moved["source"] == "draft"
    assert [(m["check_id"], m["in_force"], m["draft"]) for m in moved["moves"]] == [
        ("sample_size", "FAIL", "PASS")
    ]
    # The 450 study stays as it was; the other client's study has nothing to check.
    assert (impact["unchanged"], impact["not_assessed"]) == (1, 1)
    # A design is always submitted from a working revision now (ADR 0026 decision 5), so the
    # study that submitted one is checked on that working copy, which holds the same design.
    submitted = world.design(lead, _readiness_draft(18, 5)["content"], study="other_client")
    assert submitted.status_code == 201, submitted.text
    again = lead.post(f"{READINESS}/compare", json=_readiness_edit(sample_size__min=10)).json()
    by_id = {s["study_id"]: s for s in again["readiness"]["studies"]}
    assert by_id[world.study_id("other_client")]["source"] == "draft"
    assert by_id[world.study_id("other_client")]["ready"] == [False, True]
    assert again["readiness"]["not_assessed"] == 0
    # Nothing was written: the study's content and the limits in force are as they were.
    assert lead.get(f"{READINESS}/versions").json()["versions"] == []


def test_a_half_written_draft_is_not_assessed_and_never_stops_the_comparison(
    world: Any, as_user: Any
) -> None:
    lead = as_user("lead")
    broken = lead.put(
        f"{API}/studies/{world.study_id('sibling')}/workspace/content",
        json={"content": {"sections": 1}, "base_revision": None},
    )
    assert broken.status_code == 200, broken.text
    saved = lead.put(
        f"{API}/studies/{world.study_id('primary')}/workspace/content",
        json=_readiness_draft(15, 5),
    )
    assert saved.status_code == 200, saved.text
    compared = lead.post(f"{READINESS}/compare", json=_readiness_edit(sample_size__min=10))
    assert compared.status_code == 200, compared.text
    impact = compared.json()["readiness"]
    assert [s["study_id"] for s in impact["studies"]] == [world.study_id("primary")]
    # The broken draft and the other client's empty study: nothing a check can read.
    assert impact["not_assessed"] == 2


# ------------------------------------------------------- rounding (V1b): stored places


def test_the_rounding_stage_says_what_it_changes_and_previews_results_lines(
    owner: TestClient,
) -> None:
    body = owner.get(AGGREGATION).json()
    values = _values(body)
    assert values["rounding.share_decimals"]["value"] == 1
    assert values["rounding.mean_decimals"]["effect"] == "changes_stored"
    assert body["preview_title_cs"] == "Jak to uvidí výzkumník ve Výsledcích a ve zprávě"
    checked = owner.post(
        f"{AGGREGATION}/check",
        json=_aggregation_edit(rounding__share_decimals=0, rounding__mean_decimals=3),
    ).json()
    assert checked["valid"] is True
    lines = [(p["step_id"], p["status"], p["message_cs"]) for p in checked["preview"]]
    assert lines[0] == ("round_share", "", "Ranní nápoj: Kávu: 38 % (34\u201343 %)")
    refused = owner.post(f"{AGGREGATION}/check", json=_aggregation_edit(rounding__share_decimals=4))
    assert refused.json()["valid"] is False and refused.json()["preview"] == []


def test_a_version_stored_before_rounding_opens_with_the_places_its_runs_read(
    owner: TestClient, app: FastAPI
) -> None:
    """An aggregation version stored before the rounding fields were declared has no
    ``rounding``: it reads back with the places a run pinned to it computes (1 and 2), so the
    editor meets every field it shows; the stored payload and its hash are not touched."""
    stored = owner.post(f"{AGGREGATION}/versions", json=_aggregation_edit(bootstrap__reps=200))
    assert stored.status_code == 201, stored.text
    number = stored.json()["version_number"]
    with create_session_factory(app.state.engine)() as session:
        row = session.scalars(
            select(MethodologyVersionRow).where(
                MethodologyVersionRow.module_id == "aggregation",
                MethodologyVersionRow.version_number == number,
            )
        ).one()
        legacy = copy.deepcopy(row.payload)
        del legacy["spec"]["rounding"]
        row.payload = legacy
        session.commit()
        sha = row.payload_sha256

    (version,) = owner.get(f"{AGGREGATION}/versions").json()["versions"]
    assert version["spec"]["rounding"] == {"share_decimals": 1, "mean_decimals": 2}
    assert version["spec"]["bootstrap"]["reps"] == 200 and version["payload_sha256"] == sha
    checked = owner.post(
        f"{AGGREGATION}/check",
        json={"base_preset": version["base_preset"], "spec": version["spec"], "formulas": {}},
    )
    assert checked.json()["valid"] is True
    with create_session_factory(app.state.engine)() as session:
        kept = session.get(MethodologyVersionRow, row.version_id)
        assert kept is not None and "rounding" not in kept.payload["spec"]


# ------------------------------------------------------- field origin (V1c): read-only


def test_the_field_policy_is_served_from_the_tables_decide_reads(as_user: Any) -> None:
    """Any member reads it; every origin, sentence and grade is the policy's own, so the
    Metodika page explains exactly what ``RuntimePopulation.decide`` applies."""
    from aia_core.domain.population.policy import (
        CLIENT_BLOCKING_GRADES,
        EVIDENCE_STATUS_CLASS,
        FIELD_POLICY_VERSION,
        RECOMMENDED_USE_POLICY,
        FieldUse,
    )

    body = as_user("viewer").get(f"{METHODOLOGY}/field-policy").json()
    assert body["version"] == FIELD_POLICY_VERSION
    assert body["uses"] == [u.value for u in FieldUse]
    measured = {o["id"] for o in body["origins"] if o["measured"]}
    assert measured == {"OBSERVED", "DONOR_MATCHED"}
    codes = [code for o in body["origins"] for code in o["statuses"]]
    assert sorted(codes) == sorted(EVIDENCE_STATUS_CLASS) and len(codes) == len(set(codes))
    phrases = {p["phrase"]: p for p in body["phrases"]}
    assert set(phrases) == set(RECOMMENDED_USE_POLICY) and len(phrases) == 16
    audit = phrases["AUDIT_ONLY"]
    assert audit["rules"] == ["AUDIT_ONLY"] and audit["client_permit"] == "NONE"
    blocking = {g["grade"] for g in body["grades"] if g["client_blocking"]}
    assert blocking == set(CLIENT_BLOCKING_GRADES) == {"D", "T"}
