"""The Metodika catalogue over HTTP: any member reads it; every value comes from the code.

ADR 0023; plan ``methodology-tab.md`` chunk A5a. The route only serialises what the domain
reads, so these tests pin the wire: who may read, the shape, a value read from the preset in
force, a value the preset omits marked absent (never a zero), and a code constant labelled as
code.
"""

from __future__ import annotations

from typing import Any

import pytest
from aia_core.domain.evidence.support import AIA_SUPPORT_V1
from aia_core.domain.methodology import MODULES
from aia_core.domain.research_aggregate import AIA_AGGREGATE_V1
from aia_core.domain.respondent_behavior import AIA_RESPONSE_V1
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
    assert sociomap["presets"] == ["aia-sociomap-4", "aia-sociomap-3", "aia-sociomap-2"]
    # The computation by its stages (product owner, 2026-10-14), no longer the audit's F1-F16.
    assert [g["id"] for g in sociomap["groups"]][:3] == ["M", "S1", "S2"]


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
    assert set(presets) == {"aia-sociomap-4", "aia-sociomap-3", "aia-sociomap-2"}
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
    body = member.post(f"{SOCIOMAP}/compare", json=_edit(relation__n_min=34)).json()
    assert (body["valid"], body["in_force"]) == (True, "aia-sociomap-3")
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


def test_compare_is_for_the_object_map_and_support(owner: TestClient) -> None:
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
