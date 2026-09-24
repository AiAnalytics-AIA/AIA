"""The workbench's fixture research projects (tools/ui_workbench/fixture_project.py).

They reach the unit only through its save route, with the body the classic
``scheduleServerSave`` sends, and a second run updates the same projects. The
unit is a stub here: these tests pin what is sent, not what the unit stores.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
PATH = REPO / "tools" / "ui_workbench" / "fixture_project.py"

# scheduleServerSave's body, key for key and in its order (ui_app.html @440078).
CLASSIC_SAVE_KEYS = [
    "project_id",
    "parent_project_id",
    "project_type",
    "project",
    "analysis",
    "panel_version",
    "reason",
]


Fx = tuple[ModuleType, list[dict[str, Any]]]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ui_workbench_fixture_project", PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def fx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Fx:
    m = _load()
    sent: list[dict[str, Any]] = []
    store: dict[str, int] = {}

    def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        if path == "/api/projects/load":
            if body["project_id"] not in store:
                raise m.urllib.error.HTTPError(path, 404, "not found", None, None)
            return {"revision": store[body["project_id"]]}
        assert path == "/api/projects/save"
        sent.append(body)
        pid = body["project_id"] or f"PRJ-{len(store):02d}"
        store[pid] = store.get(pid, 0) + 1
        return {"project_id": pid, "revision": store[pid]}

    empty = {"title": "Nový výzkum", "briefing": {"situation": "", "constraints": ""}, "n": 300}
    monkeypatch.setattr(m, "STATE", tmp_path / "fixtures.json")
    monkeypatch.setattr(m, "_post", post)
    monkeypatch.setattr(m, "_boot", lambda: (empty, "18.6.6"))
    return m, sent


def test_every_fixture_is_saved_with_the_classic_body(fx: Fx) -> None:
    m, sent = fx
    m.write()
    assert len(sent) == len(m.FIXTURES)
    for body in sent:
        assert list(body) == CLASSIC_SAVE_KEYS
        assert body["project_type"] == "research"
        assert body["panel_version"] == "18.6.6"
        assert body["project_id"] is None


def test_a_fixture_keeps_the_empty_projects_defaults_under_its_own(fx: Fx) -> None:
    m, sent = fx
    m.write()
    planned = next(b["project"] for b in sent if b["analysis"] is not None)
    # Its own briefing merged over the empty one, the rest of the template kept.
    assert planned["briefing"]["constraints"] == m.BRIEF["briefing"]["constraints"]
    assert planned["briefing"]["problem_types"] == ["product", "portfolio", "price"]
    assert planned["n"] == 300


def test_a_second_run_updates_the_same_projects(fx: Fx) -> None:
    m, sent = fx
    first = m.write()
    second = m.write()
    assert first == second
    assert [b["project_id"] for b in sent[len(first) :]] == list(first.values())


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
