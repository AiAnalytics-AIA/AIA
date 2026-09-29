"""The workbench's fixture research studies (tools/ui_workbench/fixture_project.py).

They reach AIA only through the route the stages save through, ``PUT
/api/v1/studies/<study>/workspace/content``, over the template AIA serves, and a
second run saves a new revision of the same studies (ADR 0018). Nothing reaches
the 18.6.6 unit. The API is a stub here: these tests pin what is sent, not what
it stores.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
PATH = REPO / "tools" / "ui_workbench" / "fixture_project.py"
TEMPLATE = {"title": "Nový výzkum", "briefing": {"situation": "", "constraints": ""}, "n": 300}

Api = tuple[ModuleType, list[str], dict[str, list[dict[str, Any]]]]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ui_workbench_fixture_project", PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Api:
    """AIA's routes as a stub: one fictional client, its studies, their saves."""
    m = _load()
    calls: list[str] = []
    saves: dict[str, list[dict[str, Any]]] = {}

    def call(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        calls.append(f"{method} {path}")
        if path == "/workspace/clients":
            return [
                {"client_id": "CLI-X", "name": "Lumen"},
                {"client_id": "CLI-H", "name": "Horizont Mobility (fiktivní)"},
            ]
        if method == "POST" and path == "/clients/CLI-H/studies":
            assert body is not None and body["kind"] == "RESEARCH"
            study = f"STU-{sum(c.startswith('POST') for c in calls)}"
            saves[study] = []
            return {"study_id": study}
        study = path.split("/")[2]
        if study not in saves:
            raise m.urllib.error.HTTPError(path, 404, "not found", None, None)  # type: ignore[arg-type]
        if method == "GET" and path.endswith("/workspace/content"):
            n = len(saves[study])
            return {"revision": n or None, "template": TEMPLATE}
        if method == "PUT" and path.endswith("/workspace/content"):
            assert body is not None
            saves[study].append(body)
            return {"revision": len(saves[study])}
        raise AssertionError(path)

    monkeypatch.setattr(m, "STUDIES", tmp_path / "studies.json")
    monkeypatch.setattr(m, "_api", call)
    return m, calls, saves


def test_every_fixture_is_a_study_of_the_workbench_client_saved_through_aia(api: Api) -> None:
    m, calls, saves = api
    out = m.write()
    assert set(out) == set(m.FIXTURES)
    assert {v["client"] for v in out.values()} == {"CLI-H"}
    assert len({v["study"] for v in out.values()}) == len(m.FIXTURES)
    for v in out.values():
        [body] = saves[v["study"]]
        assert list(body) == ["content", "analysis", "base_revision", "reason"]
        assert body["base_revision"] is None and body["reason"] == "workbench_fixture"
    # Nothing but AIA's own routes, and no unit project anywhere.
    assert all(" /studies/" in c or " /clients/" in c or " /workspace/" in c for c in calls)


def test_a_fixture_keeps_the_templates_defaults_under_its_own(api: Api) -> None:
    m, _calls, saves = api
    m.write()
    planned = next(
        b["content"] for bodies in saves.values() for b in bodies if b["analysis"] is not None
    )
    # Its own briefing merged over the template's, the rest of the template kept.
    assert planned["briefing"]["constraints"] == m.BRIEF["briefing"]["constraints"]
    assert planned["briefing"]["problem_types"] == ["product", "portfolio", "price"]
    assert planned["n"] == 300


def test_a_second_run_saves_a_new_revision_of_the_same_studies(api: Api) -> None:
    m, calls, saves = api
    first = m.write()
    second = m.write()
    assert first == second
    assert sum(c.startswith("POST") for c in calls) == len(m.FIXTURES)
    for v in second.values():
        assert [b["base_revision"] for b in saves[v["study"]]] == [None, 1]


def test_a_fresh_api_gets_new_studies(api: Api) -> None:
    m, _calls, saves = api
    first = m.write()
    saves.clear()  # the API was reset: its studies are gone
    again = m.write()
    assert {v["study"] for v in again.values()}.isdisjoint({v["study"] for v in first.values()})


def test_the_plan_is_in_the_shape_render_plan_draws() -> None:
    m = _load()
    a = m.ANALYSIS
    assert a["problem_summary"] and a["objectives"] and a["questions_for_user"]
    for s in a["tracked_sets"]:
        # renderObjectSet: objects are strings put into the question template.
        assert all(isinstance(o, str) for o in s["objects"])
        assert "{object}" in s["object_question"]
        assert len(s["scale_labels"]) == 2


def test_the_questionnaire_is_in_the_shape_the_editor_draws() -> None:
    m = _load()
    fx = m.FIXTURES["questionnaire"]["project"]
    assert fx["ui_state"]["questionnaire_path"] == "manual"
    blocks = [s for s in fx["sections"] if s["type"] == "questions"]
    sets = [s for s in fx["sections"] if s["type"] == "object_battery"]
    # questionnaireEditorHtml: every question type the card offers, and a 4-15 set.
    assert {q["typ"] for q in blocks[0]["questions"]} == {"vyber", "multi", "skala", "otevrena"}
    assert len(sets) == 1 and 4 <= len(sets[0]["objects"]) <= 15
    assert "{object}" in sets[0]["object_question"]


def test_the_audience_is_on_the_branch_the_factor_editor_draws() -> None:
    m = _load()
    fx = m.FIXTURES["audience"]["project"]
    # renderAudience: analytics -> cz18 -> the "filters" strategy draws filterEditor.
    assert fx["ui_state"]["audience_entry"] == "analytics"
    assert fx["ui_state"]["analytics_choice"] == "cz18"
    assert fx["audience"]["strategy"] == "filters"
    # One filter of each shape the editor writes: categorical values, a {min, max} range.
    filters = fx["audience"]["filters"]
    assert isinstance(filters["kraj"], list)
    assert set(filters["vek"]) == {"min", "max"}


def test_the_persona_draws_chosen_requested_and_a_hand_set_sample() -> None:
    m = _load()
    fx = m.FIXTURES["persona"]["project"]
    # renderPersona: a non-empty approval is drawn as it is (an empty one is refilled).
    assert fx["persona_dimensions"]["approved"]
    assert fx["requested_dimensions"][0]["status"] == "needs_evidence"
    # Inside 50-5000 and not the recommendation, so the input shows the project's N.
    assert 50 <= fx["n"] <= 5000 and fx["n"] not in (300, 400, 500)
