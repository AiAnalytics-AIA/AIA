"""A questionnaire table given to the Lead, over HTTP (lead-orchestration LO18b).

On a study with no questions the table's proposal is filed at once; with questions the person
chooses Nahradit or Doplnit on their own message, once; a table breaking a template rule is
refused in the import's words and files nothing; any other table stays LO18a's file alone.
Nothing here calls a model.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest
from aia_core.application.research import ResearchAgentJobs
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.design import DesignRejected
from aia_core.domain.edit_log import ActorKind, OpSource, WriteBy
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.questionnaire_file import TEMPLATE_HEADER
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aia_api.config import Settings

ROOT = Path(__file__).resolve().parents[3] / "packages/aia_core/tests/fixtures"
TEMPLATE = ROOT / "questionnaire_import/inputs/aia_sablona.xlsx"
BROKEN = ROOT / "questionnaire_import/inputs/neznamy_typ.csv"
DATASET = ROOT / "client_sources/utrata.csv"
#: A second table in the template, valid on its own.
SECOND = ROOT / "questionnaire_import/inputs/bom.csv"
QUESTIONS = {
    "id": "mine",
    "type": "questions",
    "title": "Moje",
    "questions": [{"id": "my_q", "text": "Moje otázka?", "typ": "skala"}],
}


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"ai_research_lead_enabled": True})


def _lead(world: Any) -> str:
    return f"/api/v1/studies/{world.study_id()}/lead"


def _ready(client: TestClient, app: FastAPI, world: Any, sections: list[Any]) -> None:
    assert client.post("/api/v1/lead").status_code == 201
    with create_session_factory(app.state.engine)() as session:
        scope = ScopeResolver(session).study_context(
            AuthenticatedPrincipal(
                user_id=world.users["researcher"], organization_id=world.organization_id
            ),
            study_id=world.study_id(),
        )
        StudyWorkspaceRepository(session).save(
            scope,
            content={"title": "Fiktivní", "sections": sections},
            base_revision=None,
            by=WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI),
        )
        session.commit()


def _keep(client: TestClient, world: Any, data: bytes, name: str) -> str:
    kept = client.post(
        f"{_lead(world)}/files",
        json={"filename": name, "data_b64": base64.b64encode(data).decode()},
    )
    assert kept.status_code == 201, kept.text
    return str(kept.json()["source_id"])


def _give(
    client: TestClient, world: Any, path: Path | bytes, name: str, *more: str
) -> dict[str, Any]:
    data = path if isinstance(path, bytes) else path.read_bytes()
    posted = client.post(
        f"{_lead(world)}/turns",
        json={
            "kind": "message",
            "stage": "questionnaire",
            "text": "Udělej z toho dotazník.",
            "files": [_keep(client, world, data, name), *more],
        },
    )
    assert posted.status_code == 201, posted.text
    message: dict[str, Any] = posted.json()["turns"][0]
    return message


def _jobs(client: TestClient, world: Any) -> list[dict[str, Any]]:
    jobs = client.get(f"/api/v1/studies/{world.study_id()}/research/agent-jobs")
    assert jobs.status_code == 200, jobs.text
    return list(jobs.json())


def test_a_table_on_a_study_with_no_questions_files_its_proposal_at_once(
    researcher: TestClient, app: FastAPI, world: Any
) -> None:
    _ready(researcher, app, world, [])
    message = _give(researcher, world, TEMPLATE, "dotaznik.xlsx")
    [file] = message["files"]
    questionnaire = file["questionnaire"]
    assert questionnaire["status"] == "filed"
    assert (questionnaire["questions"], questionnaire["tracked_sets"]) == (2, 1)
    [job] = _jobs(researcher, world)
    assert questionnaire["run_id"] == job["run_id"]
    assert (job["action"], job["origin"], job["filename"], job["mode"]) == (
        "build_questionnaire",
        "file",
        "dotaznik.xlsx",
        "replace",
    )
    # Nothing to choose: the proposal is filed.
    refused = researcher.post(
        f"{_lead(world)}/turns/{message['turn_id']}/questionnaire",
        json={"source_id": file["source_id"], "mode": "add"},
    )
    assert refused.status_code == 422 and refused.json()["code"] == "questionnaire_not_choosable"


def test_with_questions_the_person_chooses_and_the_choice_files_once(
    researcher: TestClient, app: FastAPI, world: Any
) -> None:
    _ready(researcher, app, world, [QUESTIONS])
    message = _give(researcher, world, TEMPLATE, "dotaznik.xlsx")
    [file] = message["files"]
    assert file["questionnaire"]["status"] == "choose"
    assert file["questionnaire"]["run_id"] is None
    assert _jobs(researcher, world) == []
    url = f"{_lead(world)}/turns/{message['turn_id']}/questionnaire"
    chosen = researcher.post(url, json={"source_id": file["source_id"], "mode": "add"})
    assert chosen.status_code == 201, chosen.text
    [job] = _jobs(researcher, world)
    assert job["run_id"] == chosen.json()["run_id"] and job["mode"] == "add"
    again = researcher.post(url, json={"source_id": file["source_id"], "mode": "replace"})
    assert again.status_code == 409 and again.json()["code"] == "questionnaire_already_filed"
    assert again.json()["details"]["run_id"] == job["run_id"]
    state = researcher.get(_lead(world)).json()["turns"]
    mine = next(t for t in state if t["turn_id"] == message["turn_id"])
    assert mine["files"][0]["questionnaire"]["run_id"] == job["run_id"]


def test_a_table_breaking_a_template_rule_is_refused_in_words_and_files_nothing(
    researcher: TestClient, app: FastAPI, world: Any
) -> None:
    _ready(researcher, app, world, [])
    message = _give(researcher, world, BROKEN, "dotaznik.csv")
    questionnaire = message["files"][0]["questionnaire"]
    assert questionnaire["status"] == "refused" and questionnaire["reason"] == "invalid_row"
    assert questionnaire["message"]
    assert _jobs(researcher, world) == []


def test_a_table_not_in_the_template_stays_a_file(
    researcher: TestClient, app: FastAPI, world: Any
) -> None:
    _ready(researcher, app, world, [])
    message = _give(researcher, world, DATASET, "utrata.csv")
    assert message["files"][0]["questionnaire"] is None
    assert _jobs(researcher, world) == []


def test_another_researchers_message_is_not_found(
    researcher: TestClient, viewer: TestClient, app: FastAPI, world: Any
) -> None:
    _ready(researcher, app, world, [QUESTIONS])
    message = _give(researcher, world, TEMPLATE, "dotaznik.xlsx")
    theirs = viewer.post(
        f"{_lead(world)}/turns/{message['turn_id']}/questionnaire",
        json={"source_id": message["files"][0]["source_id"], "mode": "add"},
    )
    assert theirs.status_code == 404


def test_a_blank_template_is_refused_by_name_and_replaces_nothing(
    researcher: TestClient, app: FastAPI, world: Any
) -> None:
    _ready(researcher, app, world, [QUESTIONS])
    header = (",".join(TEMPLATE_HEADER) + "\n").encode()
    message = _give(researcher, world, header, "prazdna.csv")
    questionnaire = message["files"][0]["questionnaire"]
    assert (questionnaire["status"], questionnaire["reason"]) == ("refused", "questionnaire_empty")
    assert _jobs(researcher, world) == []


def test_one_questionnaire_a_message_the_second_refused(
    researcher: TestClient, app: FastAPI, world: Any
) -> None:
    _ready(researcher, app, world, [])
    second = _keep(researcher, world, SECOND.read_bytes(), "druhy.csv")
    message = _give(researcher, world, TEMPLATE, "dotaznik.xlsx", second)
    first, other = message["files"]
    assert first["questionnaire"]["status"] == "filed"
    assert other["questionnaire"]["reason"] == "one_questionnaire_per_message"
    assert len(_jobs(researcher, world)) == 1


def test_a_copy_the_design_refuses_keeps_the_message_and_says_why(
    researcher: TestClient, app: FastAPI, world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ready(researcher, app, world, [])

    def refused(*_args: Any, **_kwargs: Any) -> Any:
        raise DesignRejected("the design is not the working revision it names", reason="stale")

    # The filing refused by the design (a copy that moved under it, say): only the table's
    # proposal is refused, never the message.
    monkeypatch.setattr(ResearchAgentJobs, "start_import", refused)
    message = _give(researcher, world, TEMPLATE, "dotaznik.xlsx")
    questionnaire = message["files"][0]["questionnaire"]
    assert (questionnaire["status"], questionnaire["reason"]) == ("refused", "stale")
    assert message["text"] == "Udělej z toho dotazník."
    assert _jobs(researcher, world) == []
