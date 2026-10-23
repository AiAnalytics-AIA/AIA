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
from aia_api.editor_tokens import EditorTokens


def _now() -> Any:
    from datetime import UTC, datetime

    return datetime.now(UTC)


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
        # A fixed time: the same content is the same bytes whenever it is built.
        info = zipfile.ZipInfo("word/document.xml", (2026, 10, 23, 0, 0, 0))
        z.writestr(info, f"<w:document>{text}</w:document>")
    return out.getvalue()


def _reported_run(
    app: FastAPI, researcher: TestClient, world: Any, *, title: str = "Ranní nápoj"
) -> tuple[str, str]:
    """A run of the primary study whose report step stored an internal draft: (run, draft);
    another ``title`` is another design, so another run."""
    revision = world.design(researcher, {**DESIGN, "title": title}).json()["revision_id"]
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
    assert isinstance(signed.pop("exp"), int)  # a config's token expires
    assert signed == config  # the Document Server checks the config as signed
    user = config["editorConfig"]["user"]
    assert user["id"] == world.users["researcher"] and "@" not in user["name"]
    assert "@" not in response.text  # no e-mail anywhere in what the browser gets
    assert config["editorConfig"]["customization"]["forcesave"] is True
    # The Document Server's routes, outside any study: the token's session names it.
    assert config["editorConfig"]["callbackUrl"].startswith(f"{PUBLIC}{API}/report-editor/")
    assert config["document"]["url"].startswith(f"{PUBLIC}{API}/report-editor/document?")
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


def _signed_for(path: str, query: dict[str, Any]) -> dict[str, str]:
    """The Document Server's JWT for a fetch of ``path`` with ``query``."""
    token = query["token"][0] if isinstance(query["token"], list) else query["token"]
    url = f"{PUBLIC}{path}?token={token}"
    return {"Authorization": f"Bearer {jwt.encode({'url': url}, SECRET)}"}


def test_the_document_is_served_only_to_the_document_server_for_its_url(
    app: FastAPI, researcher: TestClient, client: TestClient, world: Any
) -> None:
    run_id, _ = _reported_run(app, researcher, world)
    body = researcher.post(_editor(world, run_id), json={}).json()
    config, url = body["config"], body["config"]["document"]["url"]
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert _fetch(client, url, signed=False).status_code == 403  # no Document Server JWT
    # The browser's own JWT is under the same secret: a config's token is not the Server's.
    as_browser = {"Authorization": f"Bearer {config['token']}"}
    assert client.get(parsed.path, params=query, headers=as_browser).status_code == 403
    # A Document Server JWT for another URL.
    elsewhere = {"Authorization": f"Bearer {jwt.encode({'url': f'{PUBLIC}/x'}, SECRET)}"}
    assert client.get(parsed.path, params=query, headers=elsewhere).status_code == 403
    # The editor's own secret does not sign AIA's URL tokens: they are under a derived key.
    forged = {"token": jwt.encode({"kind": "document", "key": "x", "exp": 9e9}, SECRET)}
    assert (
        client.get(parsed.path, params=forged, headers=_signed_for(parsed.path, forged))
    ).status_code == 403
    # A key no session has: nothing to serve.
    stray = EditorTokens(SECRET).url_token(
        "document", document_key="ART-0.x.1", artifact_id=body["version_artifact_id"], now=_now()
    )
    query = {"token": stray}
    assert (
        client.get(parsed.path, params=query, headers=_signed_for(parsed.path, query)).status_code
        == 404
    )


def test_an_expired_a_callbacks_or_another_lines_token_does_not_fetch(
    app: FastAPI, researcher: TestClient, client: TestClient, world: Any
) -> None:
    from datetime import UTC, datetime, timedelta

    from aia_api.editor_tokens import DOCUMENT_LIFETIME, EditorTokens

    run_id, _ = _reported_run(app, researcher, world)
    body = researcher.post(_editor(world, run_id), json={}).json()
    key = body["config"]["document"]["key"]
    path = urlparse(body["config"]["document"]["url"]).path
    tokens = EditorTokens(SECRET)
    past = datetime.now(UTC) - DOCUMENT_LIFETIME - timedelta(seconds=1)
    expired = tokens.url_token(
        "document", document_key=key, artifact_id=body["version_artifact_id"], now=past
    )
    callback = tokens.url_token("callback", document_key=key, now=datetime.now(UTC))
    for refused in (expired, callback):
        query = {"token": refused}
        assert client.get(path, params=query, headers=_signed_for(path, query)).status_code == 403
    # A version of another line: the run's second draft, which this session's line is not.
    other_run, other_draft = _reported_run(app, researcher, world, title="Večerní nápoj")
    researcher.post(_editor(world, other_run), json={})
    stray = tokens.url_token(
        "document", document_key=key, artifact_id=other_draft, now=datetime.now(UTC)
    )
    query = {"token": stray}
    assert client.get(path, params=query, headers=_signed_for(path, query)).status_code == 404


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
    # Without a token too: the editor's state answers first, never a 422 (MVP-ACCEPT AC01's
    # sweep of every study route as another organization).
    assert client.get(urlparse(url).path).status_code == 404


def test_a_fetch_without_a_token_is_refused_not_invalid(
    app: FastAPI, researcher: TestClient, client: TestClient, world: Any
) -> None:
    run_id, _ = _reported_run(app, researcher, world)
    url = researcher.post(_editor(world, run_id), json={}).json()["config"]["document"]["url"]
    path = urlparse(url).path
    assert client.get(path).status_code == 403
    assert client.get(path, params={"token": "x" * 3000}).status_code == 403
    app.state.settings = app.state.settings.model_copy(update={"onlyoffice_callback_base": ""})
    assert client.get(path, params={"token": "x" * 3000}).status_code == 404  # off: never 422


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


# -- the Document Server's routes are outside the study tree: their scope, tested here ---------
# (MVP-ACCEPT AC01 sweeps only routes naming {study_id}; these are scoped by the editor session the
# signed URL token names, resolved through ScopeResolver for the person who opened it.)


def _document_url(researcher: TestClient, world: Any, run_id: str) -> tuple[str, dict[str, Any]]:
    body = researcher.post(_editor(world, run_id), json={}).json()
    return body["config"]["document"]["url"], body


def test_a_removed_opener_s_session_serves_nothing(
    app: FastAPI, researcher: TestClient, client: TestClient, world: Any
) -> None:
    from datetime import UTC, datetime

    from aia_core.infrastructure.scope_repository import ScopeRepository

    run_id, _ = _reported_run(app, researcher, world)
    url, _body = _document_url(researcher, world, run_id)
    assert _fetch(client, url).status_code == 200
    factory = create_session_factory(app.state.engine)
    with factory() as session:
        owner = AuthenticatedPrincipal(
            user_id=world.users["owner"], organization_id=world.organization_id
        )
        admin = ScopeResolver(session).organization_context(owner)
        ScopeRepository(session).deactivate_member(
            admin, user_id=world.users["researcher"], now=datetime.now(UTC)
        )
        session.commit()
    removed = _fetch(client, url)
    assert removed.status_code == 404 and removed.json()["code"] == "editor_session_not_found"


def test_a_token_pairing_a_session_with_another_organizations_version_serves_nothing(
    app: FastAPI, researcher: TestClient, client: TestClient, world: Any
) -> None:
    """A URL token can only be minted under the editor's secret, but even so: a session key of
    this organization naming another organization's artifact finds no version of its line."""
    from aia_core.infrastructure.scope_repository import ScopeRepository
    from aia_core.infrastructure.study_design_repository import StudyDesignRepository

    run_id, _ = _reported_run(app, researcher, world)
    url, body = _document_url(researcher, world, run_id)
    factory = create_session_factory(app.state.engine)
    with factory() as session:
        repo, resolver = ScopeRepository(session), ScopeResolver(session)
        org, owner = repo.create_organization(
            slug="other-org", name="Other", owner_email="o@other.invalid", owner_name="O"
        )
        principal = AuthenticatedPrincipal(
            user_id=owner.user_id, organization_id=org.organization_id
        )
        admin = resolver.organization_context(principal)
        foreign_client = repo.create_client(admin, slug="c", name="C")
        study = repo.create_study(admin, client_id=foreign_client.client_id, slug="s", name="S")
        scope = resolver.study_context(principal, study_id=study.study_id)
        designs = StudyDesignRepository(session, scope)
        revision, _ = designs.submit_as_working_copy(content=DESIGN, source_stage="run")
        foreign, _ = research_artifacts(session, scope, app.state.artifact_store).put(
            project_id=str(designs.project_id()),
            revision=revision.revision,
            stage_type="REPORT",
            artifact_type=INTERNAL_REPORT_ARTIFACT_TYPE,
            data=_docx("Cizí"),
            content_type=INTERNAL_REPORT_MEDIA_TYPE,
            metadata={"run_id": run_id, "report_kind": "internal"},
            reuse=False,
        )
        session.commit()
    stray = EditorTokens(SECRET).url_token(
        "document",
        document_key=body["config"]["document"]["key"],
        artifact_id=foreign.artifact_id,
        now=_now(),
    )
    path = urlparse(url).path
    query = {"token": stray}
    answer = client.get(path, params=query, headers=_signed_for(path, query))
    assert answer.status_code == 404 and answer.json()["code"] == "editor_version_not_found"
