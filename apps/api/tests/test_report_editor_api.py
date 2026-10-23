"""Zpráva in the report editor: the signed config and the Document Server's fetch of a version
(artifact-report RPT8c, part 2)."""

from __future__ import annotations

import io
import os
import zipfile
from typing import Any
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from aia_core.application.report import INTERNAL_REPORT_ARTIFACT_TYPE, INTERNAL_REPORT_MEDIA_TYPE
from aia_core.application.research import research_artifacts
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aia_api.config import Environment, Settings

API = "/api/v1"
EDITOR = "https://docs.aia.example.test"
PUBLIC = "https://aia.example.test"
SECRET = "k" * 48
DESIGN = {
    "title": "Ranní nápoj",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
    "n": 450,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
            ],
        }
    ],
}


@pytest.fixture
def settings() -> Settings:
    return Settings(
        env=Environment.TEST,
        database_url=os.environ.get("DATABASE_URL", "sqlite+pysqlite:///:memory:"),
        identity_provider="test",
        log_level="WARNING",
        log_format="console",
        onlyoffice_url=EDITOR,
        onlyoffice_jwt_secret=SECRET,
        onlyoffice_callback_base=PUBLIC,
        # A run has a report step only with its analysis (no model is called here).
        ai_analysis_enabled=True,
    )


def _docx(text: str = "Koncept") -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("word/document.xml", f"<w:document>{text}</w:document>")
    return out.getvalue()


def _reported_run(app: FastAPI, researcher: TestClient, world: Any) -> tuple[str, str]:
    """A run of the primary study whose report step stored an internal draft: (run, draft)."""
    revision = world.design(researcher, DESIGN).json()["revision_id"]
    runs = f"{API}/studies/{world.study_id()}/research/runs"
    started = researcher.post(runs, json={"design_revision_id": revision})
    assert started.status_code == 201, started.text
    run_id = started.json()["run_id"]
    factory = create_session_factory(app.state.engine)
    with factory() as session:
        principal = AuthenticatedPrincipal(
            user_id=world.users["researcher"], organization_id=world.organization_id
        )
        scope = ScopeResolver(session).study_context(principal, study_id=world.study_id())
        workflow = WorkflowRepository(session, scope)
        draft = ""
        while (work := workflow.claim_next(worker_id="editor-fixture")) is not None:
            output: dict[str, Any] = {}
            if work.node_key == "report":
                artifact, _ = research_artifacts(session, scope, app.state.artifact_store).put(
                    project_id=work.project_id,
                    revision=work.project_revision,
                    stage_type="REPORT",
                    artifact_type=INTERNAL_REPORT_ARTIFACT_TYPE,
                    data=_docx(),
                    content_type=INTERNAL_REPORT_MEDIA_TYPE,
                    metadata={"run_id": run_id, "report_kind": "internal"},
                    reuse=False,
                )
                draft = artifact.artifact_id
                output = {"artifact_id": draft}
            workflow.complete_attempt(work.attempt_id, worker_id="editor-fixture", output=output)
        session.commit()
    assert draft
    return run_id, draft


def _editor(world: Any, run_id: str) -> str:
    return f"{API}/studies/{world.study_id()}/research/runs/{run_id}/report/editor"


def _fetch(client: TestClient, url: str, *, signed: bool = True) -> Any:
    """``url`` fetched as the Document Server does: with its JWT unless ``signed`` is false."""
    parsed = urlparse(url)
    assert f"{parsed.scheme}://{parsed.netloc}" == PUBLIC
    headers = {"Authorization": f"Bearer {jwt.encode({'url': url}, SECRET)}"} if signed else {}
    return client.get(parsed.path, params=parse_qs(parsed.query), headers=headers)


def test_the_config_is_signed_names_no_e_mail_and_fetches_its_version(
    app: FastAPI, researcher: TestClient, client: TestClient, world: Any
) -> None:
    run_id, draft = _reported_run(app, researcher, world)
    response = researcher.post(_editor(world, run_id), json={"variant": "internal"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document_server"] == EDITOR
    assert body["line_id"] == draft and body["koncept"] == 1
    config = body["config"]
    signed = jwt.decode(config.pop("token"), SECRET, algorithms=["HS256"])
    assert signed == config  # the Document Server checks the config as signed
    user = config["editorConfig"]["user"]
    assert user["id"] == world.users["researcher"] and "@" not in user["name"]
    assert "@" not in response.text  # no e-mail anywhere in what the browser gets
    assert config["editorConfig"]["customization"]["forcesave"] is True
    assert config["editorConfig"]["callbackUrl"].startswith(f"{PUBLIC}{API}/studies/")
    fetched = _fetch(client, config["document"]["url"])
    assert fetched.status_code == 200 and fetched.content == _docx()


def test_a_second_researcher_gets_the_same_key(
    app: FastAPI, researcher: TestClient, lead: TestClient, world: Any
) -> None:
    run_id, _ = _reported_run(app, researcher, world)
    first = researcher.post(_editor(world, run_id), json={}).json()["config"]
    second = lead.post(_editor(world, run_id), json={}).json()["config"]
    assert first["document"]["key"] == second["document"]["key"]
    assert second["editorConfig"]["user"]["id"] == world.users["lead"]


def test_the_document_is_served_only_to_the_document_server_for_its_url(
    app: FastAPI, researcher: TestClient, client: TestClient, world: Any
) -> None:
    run_id, _ = _reported_run(app, researcher, world)
    url = researcher.post(_editor(world, run_id), json={}).json()["config"]["document"]["url"]
    assert _fetch(client, url, signed=False).status_code == 403  # no Document Server JWT
    parsed = urlparse(url)
    forged = {"token": jwt.encode({"kind": "document", "key": "x", "exp": 9e9}, SECRET)}
    signed = {"Authorization": f"Bearer {jwt.encode({}, SECRET)}"}
    # The editor's own secret does not sign AIA's URL tokens: they are under a derived key.
    assert client.get(parsed.path, params=forged, headers=signed).status_code == 403
    other = parsed.path.replace(world.study_id(), world.study_id("sibling"))
    assert client.get(other, params=parse_qs(parsed.query), headers=signed).status_code == 404


def test_the_client_report_is_refused_by_name(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    run_id, _ = _reported_run(app, researcher, world)
    refused = researcher.post(_editor(world, run_id), json={"variant": "client"})
    assert refused.status_code == 409
    assert refused.json()["code"] == "client_report_not_editable"


def test_with_the_editor_off_every_route_is_404(
    app: FastAPI, researcher: TestClient, client: TestClient, world: Any
) -> None:
    run_id, _ = _reported_run(app, researcher, world)
    url = researcher.post(_editor(world, run_id), json={}).json()["config"]["document"]["url"]
    app.state.settings = app.state.settings.model_copy(update={"onlyoffice_callback_base": ""})
    assert researcher.post(_editor(world, run_id), json={}).status_code == 404
    assert _fetch(client, url).status_code == 404


@pytest.mark.parametrize(
    "base",
    [
        "http://aia.example.test",
        "https://aia.example.test/api",
        "https://u@aia.example.test",
        "https://aia.example.test:8443",
    ],
)
def test_the_public_origin_is_an_https_origin_and_nothing_else(base: str) -> None:
    with pytest.raises(ValueError):
        Settings(env=Environment.TEST, onlyoffice_callback_base=base)


def test_the_editor_is_on_only_with_its_origin_its_secret_and_aias_public_origin() -> None:
    on = Settings(
        env=Environment.TEST,
        onlyoffice_url=EDITOR,
        onlyoffice_jwt_secret=SECRET,
        onlyoffice_callback_base=PUBLIC,
    )
    assert on.report_editor_on
    for missing in ("onlyoffice_url", "onlyoffice_callback_base"):
        assert not on.model_copy(update={missing: ""}).report_editor_on
