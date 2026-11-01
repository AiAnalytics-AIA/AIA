"""A file to the Lead over HTTP (lead-orchestration LO18a).

The file is kept as the study's client's source and listed under the client's Data; the
message carries its ref; the turn answering the message reads it into its ``files`` layer,
bounded, with its locators, and names it in the manifest; a later turn names it and reads
nothing of it; a dataset reaches the turn as its preview, never a row; another client's
source is 404. Nothing here calls a model.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.ai_contracts import canonical_json
from aia_core.domain.client_sources import SOURCE_MAX_BYTES
from aia_core.domain.edit_log import ActorKind, OpSource, WriteBy
from aia_core.domain.workflow_templates import RESEARCH_LEAD_TURN
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository
from aia_core.infrastructure.tables import AccessAuditRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from aia_api.config import Settings

ROOT = Path(__file__).resolve().parents[3] / "packages/aia_core/tests/fixtures"
PDF = ROOT / "attachment_text/inputs/prezentace.pdf"
PNG = ROOT / "attachment_text/inputs/obrazek.png"
CSV = ROOT / "client_sources/utrata.csv"


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"ai_research_lead_enabled": True})


def _lead(world: Any) -> str:
    return f"/api/v1/studies/{world.study_id()}/lead"


def _scope(world: Any, session: Any) -> Any:
    return ScopeResolver(session).study_context(
        AuthenticatedPrincipal(
            user_id=world.users["researcher"], organization_id=world.organization_id
        ),
        study_id=world.study_id(),
    )


def _ready(client: TestClient, app: FastAPI, world: Any) -> None:
    assert client.post("/api/v1/lead").status_code == 201
    with create_session_factory(app.state.engine)() as session:
        scope = _scope(world, session)
        StudyWorkspaceRepository(session).save(
            scope,
            content={"title": "Fiktivní", "sections": []},
            base_revision=None,
            by=WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI),
        )
        session.commit()


def _attach(client: TestClient, world: Any, name: str, data: bytes) -> Any:
    return client.post(
        f"{_lead(world)}/files",
        json={"filename": name, "data_b64": base64.b64encode(data).decode()},
    )


def _send(client: TestClient, world: Any, text: str, files: list[str]) -> Any:
    return client.post(
        f"{_lead(world)}/turns",
        json={"kind": "message", "stage": "brief", "text": text, "files": files},
    )


def _claim(app: FastAPI, world: Any, *, reply: str = "Přečteno.") -> dict[str, Any]:
    """The turn's frozen context, as the worker is handed it; the turn then completed."""
    with create_session_factory(app.state.engine)() as session:
        workflows = WorkflowRepository(session, _scope(world, session))
        work = workflows.claim_next(worker_id="w", kinds={RESEARCH_LEAD_TURN})
        assert work is not None
        context: dict[str, Any] = work.payload["context"]
        workflows.complete_attempt(
            work.attempt_id,
            worker_id="w",
            output={"lead_output": {"reply": reply}, "dropped": [], "self_update_applied": None},
        )
        session.commit()
    return context


def _files_layer(context: dict[str, Any]) -> dict[str, Any] | None:
    return next((e for e in context["layers"] if e["layer"] == "files"), None)


def test_a_pdf_given_on_zadani_reaches_its_turn_bounded_and_is_listed_under_the_clients_data(
    researcher: TestClient, app: FastAPI, world: Any
) -> None:
    _ready(researcher, app, world)
    kept = _attach(researcher, world, "Zadání.pdf", PDF.read_bytes())
    assert kept.status_code == 201, kept.text
    body = kept.json()
    assert (body["family"], body["outcome"], body["segments"]) == ("DOCUMENT", "READ", 2)

    # Kept as the client's source: listed under the client's Data, added from the Lead.
    listed = researcher.get(f"/api/v1/clients/{world.client_id()}/sources").json()
    [source] = [s for s in listed if s["source_id"] == body["source_id"]]
    assert [o["origin"] for o in source["occurrences"]] == ["LEAD"]
    with create_session_factory(app.state.engine)() as session:
        audit = session.scalars(
            select(AccessAuditRow).where(AccessAuditRow.action == "CLIENT_SOURCE_ADDED")
        ).all()
        assert [a.study_id for a in audit] == [world.study_id()]

    posted = _send(researcher, world, "Co v zadání chybí?", [body["source_id"]])
    assert posted.status_code == 201, posted.text
    message = posted.json()["turns"][0]
    assert [(f["source_id"], f["filename"]) for f in message["files"]] == [
        (body["source_id"], "Zadání.pdf")
    ]
    context = _claim(app, world)
    files = _files_layer(context)
    assert files is not None
    [one] = files["files"]
    assert one["name"] == "Zadání.pdf" and one["outcome"] == "READ"
    assert [s["at"] for s in one["segments"]] == [{"page": 1}, {"page": 2}]
    assert all(s["text"] for s in one["segments"])

    # The turn's manifest names the file and what it left out (nothing, here).
    lead_turn = posted.json()["turns"][-1]["turn_id"]
    read = researcher.get(f"{_lead(world)}/turns/{lead_turn}/manifest")
    assert read.status_code == 200 and read.json()["recorded"], read.text
    manifest = read.json()["manifest"]
    row = next(r for r in manifest["layers"] if r["layer"] == "files")
    assert row["included"] == [body["source_id"]] and row["omitted"] == []

    # The file only in its turn: the next turn names it in the conversation, reads none of it.
    assert _send(researcher, world, "A dál?", []).status_code == 201
    later = _claim(app, world)
    assert _files_layer(later) is None
    conversation = next(e for e in later["layers"] if e["layer"] == "conversation")
    assert conversation["turns"][0]["files"] == ["Zadání.pdf"]
    assert one["segments"][0]["text"] not in canonical_json(later)


def test_a_dataset_reaches_the_turn_as_its_preview_never_a_row(
    researcher: TestClient, app: FastAPI, world: Any
) -> None:
    _ready(researcher, app, world)
    kept = _attach(researcher, world, "útrata.csv", CSV.read_bytes()).json()
    assert kept["family"] == "DATASET"
    assert _send(researcher, world, "Co je v datech?", [kept["source_id"]]).status_code == 201
    [one] = (_files_layer(_claim(app, world)) or {})["files"]
    assert "segments" not in one
    [sheet] = one["dataset"]["sheets"]
    phone = next(c for c in sheet["columns"] if c["header"] == "Telefon")
    assert set(phone["sample"]) == {"•••"}
    # No row of the file reaches the context: not one row's text, masked or not.
    rows = CSV.read_text(encoding="utf-8").splitlines()[1:]
    sent = canonical_json(one)
    assert rows and all(row not in sent for row in rows)


def test_an_unreadable_file_is_kept_and_its_turn_says_why(
    researcher: TestClient, app: FastAPI, world: Any
) -> None:
    _ready(researcher, app, world)
    kept = _attach(researcher, world, "logo.png", PNG.read_bytes()).json()
    assert (kept["outcome"], kept["reason"]) == ("UNREADABLE", "not_text_media")
    assert _send(researcher, world, "Co je na obrázku?", [kept["source_id"]]).status_code == 201
    [one] = (_files_layer(_claim(app, world)) or {})["files"]
    assert (one["outcome"], one["reason"]) == ("UNREADABLE", "not_text_media")
    assert "segments" not in one


def test_what_cannot_be_kept_is_refused_before_anything_is_stored(
    researcher: TestClient, app: FastAPI, world: Any
) -> None:
    _ready(researcher, app, world)
    unsupported = _attach(researcher, world, "a.exe", b"MZ")
    assert unsupported.status_code == 422 and unsupported.json()["code"] == "unsupported_format"
    assert _attach(researcher, world, "a.txt", b"").status_code == 422
    too_large = _attach(researcher, world, "velký.txt", b"x" * (SOURCE_MAX_BYTES + 1))
    assert too_large.status_code == 422
    assert too_large.json()["code"] in ("too_large", "request_validation_failed")
    not_b64 = researcher.post(f"{_lead(world)}/files", json={"filename": "a.txt", "data_b64": "@@"})
    assert not_b64.status_code == 422 and not_b64.json()["code"] == "not_base64"
    assert researcher.get(f"/api/v1/clients/{world.client_id()}/sources").json() == []


def test_another_clients_source_is_404_and_nothing_is_stored(
    researcher: TestClient, app: FastAPI, world: Any
) -> None:
    _ready(researcher, app, world)
    other = world.client_id("other")
    theirs = researcher.post(
        f"/api/v1/clients/{other}/sources",
        json={"filename": "jejich.md", "data_b64": base64.b64encode("# Cizí".encode()).decode()},
    )
    assert theirs.status_code == 201, theirs.text
    refused = _send(researcher, world, "Přečti to.", [theirs.json()["source_id"]])
    assert refused.status_code == 404 and refused.json()["code"] == "unknown_source"
    unknown = _send(researcher, world, "Přečti to.", ["SRC-0000000000000000"])
    assert unknown.status_code == 404
    assert researcher.get(f"{_lead(world)}").json()["turns"] == []


def test_files_ride_only_a_message_and_at_most_three(
    researcher: TestClient, app: FastAPI, world: Any
) -> None:
    _ready(researcher, app, world)
    ids = [
        _attach(researcher, world, f"{n}.md", f"# Soubor {n}".encode()).json()["source_id"]
        for n in range(4)
    ]
    too_many = _send(researcher, world, "Přečti.", ids)
    assert too_many.status_code == 422
    greeting = researcher.post(
        f"{_lead(world)}/turns", json={"kind": "greeting", "stage": "brief", "files": ids[:1]}
    )
    assert greeting.status_code == 422
    command = _send(researcher, world, "Spusť výzkum", ids[:1])
    assert command.status_code == 422


def test_no_file_is_kept_while_the_lead_is_off_or_not_hatched(
    researcher: TestClient, app: FastAPI, world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review of LO18a: a file no message could carry is never kept as the client's source."""
    unhatched = _attach(researcher, world, "a.md", b"# Fakt")
    assert unhatched.status_code == 409 and unhatched.json()["code"] == "lead_not_hatched"
    _ready(researcher, app, world)
    monkeypatch.setattr(
        app.state,
        "settings",
        app.state.settings.model_copy(update={"ai_research_lead_enabled": False}),
    )
    off = _attach(researcher, world, "a.md", b"# Fakt")
    assert off.status_code == 409
    assert researcher.get(f"/api/v1/clients/{world.client_id()}/sources").json() == []


def test_the_same_bytes_given_again_reach_the_lead_under_the_name_given(
    researcher: TestClient, app: FastAPI, world: Any
) -> None:
    """Review of LO18a: the person and the Lead see one name for the file."""
    _ready(researcher, app, world)
    first = _attach(researcher, world, "brief_old.md", b"# Zadani").json()
    again = _attach(researcher, world, "Zadání v2.md", b"# Zadani").json()
    assert again["source_id"] == first["source_id"] and again["filename"] == "Zadání v2.md"
    posted = _send(researcher, world, "Přečti.", [again["source_id"]])
    assert posted.json()["turns"][0]["files"][0]["filename"] == "Zadání v2.md"
    [one] = (_files_layer(_claim(app, world)) or {})["files"]
    assert one["name"] == "Zadání v2.md"
