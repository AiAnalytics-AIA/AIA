"""A client's sources over HTTP (lifecycle K2a).

A file is kept for the client, read at once with every segment's place in the original,
kept once per client by its bytes, served only as a download, and never found under
another client (404).
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi.testclient import TestClient

API = "/api/v1"
SOURCES = Path(__file__).resolve().parents[3] / "packages/aia_core/tests/fixtures/client_sources"
FIXTURES = (
    Path(__file__).resolve().parents[3] / "packages/aia_core/tests/fixtures/attachment_text/inputs"
)


def upload(c: TestClient, client_id: str, name: str, data: bytes) -> Any:
    return c.post(
        f"{API}/clients/{client_id}/sources",
        json={"filename": name, "data_b64": base64.b64encode(data).decode()},
    )


def test_a_file_is_kept_read_and_listed_and_the_same_bytes_are_one_source(
    lead: TestClient, world: Any
) -> None:
    client = world.client_id("primary")
    pdf = (FIXTURES / "prezentace.pdf").read_bytes()
    first = upload(lead, client, "Zadání.pdf", pdf)
    assert first.status_code == 201, first.text
    body = first.json()
    assert (body["created"], body["family"], body["outcome"], body["reader"]) == (
        True,
        "DOCUMENT",
        "READ",
        "pdf/1",
    )
    assert body["filename"] == "Zadání.pdf" and body["segments"] == 2

    again = upload(lead, client, "kopie.pdf", pdf)
    assert again.status_code == 200 and again.json()["created"] is False
    assert again.json()["source_id"] == body["source_id"]
    assert [o["filename"] for o in again.json()["occurrences"]] == ["kopie.pdf", "Zadání.pdf"]

    listed = lead.get(f"{API}/clients/{client}/sources").json()
    assert [s["source_id"] for s in listed] == [body["source_id"]]

    detail = lead.get(f"{API}/clients/{client}/sources/{body['source_id']}").json()
    assert [s["locator"]["page"] for s in detail["reading"]["segments"]] == [1, 2]
    assert detail["reading"]["outcome"] == "READ"


def test_the_original_is_only_ever_a_download_under_the_name_as_written(
    lead: TestClient, world: Any
) -> None:
    client = world.client_id("primary")
    kept = upload(lead, client, "Poznámky.md", b"# Fakt").json()
    got = lead.get(f"{API}/clients/{client}/sources/{kept['source_id']}/original")
    assert got.status_code == 200 and got.content == b"# Fakt"
    assert got.headers["content-type"] == "application/octet-stream"
    assert got.headers["x-content-type-options"] == "nosniff"
    disposition = got.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="Pozn_mky.md"')
    assert f"filename*=UTF-8''{quote('Poznámky.md')}" in disposition


def test_another_clients_source_is_not_found(
    lead: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    client = world.client_id("primary")
    kept = upload(lead, client, "a.txt", b"Fakt.").json()
    other = world.client_id("other")
    assert other_client_lead.get(f"{API}/clients/{other}/sources").json() == []
    for path in ("", "/original"):
        # Under the other client's own path, the source is not there.
        assert (
            other_client_lead.get(
                f"{API}/clients/{other}/sources/{kept['source_id']}{path}"
            ).status_code
            == 404
        )


def test_what_cannot_be_kept_or_read_says_so_by_name(lead: TestClient, world: Any) -> None:
    client = world.client_id("primary")
    for name, data, code in (
        ("a.exe", b"MZ", "unsupported_format"),
        ("a.txt", b"", None),
    ):
        refused = lead.post(
            f"{API}/clients/{client}/sources",
            json={"filename": name, "data_b64": base64.b64encode(data).decode()},
        )
        assert refused.status_code == 422
        if code:
            assert refused.json()["code"] == code
    not_b64 = lead.post(
        f"{API}/clients/{client}/sources", json={"filename": "a.txt", "data_b64": "@@@"}
    )
    assert not_b64.status_code == 422 and not_b64.json()["code"] == "not_base64"

    image = upload(lead, client, "logo.png", (FIXTURES / "obrazek.png").read_bytes()).json()
    assert (image["outcome"], image["reason"]) == ("UNREADABLE", "not_text_media")
    sheet = upload(lead, client, "data.xlsx", (FIXTURES / "tabulka.xlsx").read_bytes()).json()
    assert (sheet["outcome"], sheet["reader"]) == ("READ", "xlsx/1")


def test_an_unknown_source_id_is_404(lead: TestClient, world: Any) -> None:
    client = world.client_id("primary")
    assert lead.get(f"{API}/clients/{client}/sources/SRC-0000000000000000").status_code == 404
    assert lead.get(f"{API}/clients/{client}/sources/not-an-id").status_code == 422


def test_a_dataset_answers_its_columns_and_masks_what_is_personal(
    lead: TestClient, world: Any
) -> None:
    client = world.client_id("primary")
    csv = SOURCES / "utrata.csv"
    kept = upload(lead, client, "útrata.csv", csv.read_bytes()).json()
    detail = lead.get(f"{API}/clients/{client}/sources/{kept['source_id']}").json()
    [sheet] = detail["reading"]["dataset"]["sheets"]
    assert (sheet["header_row"], sheet["rows"]) == (1, 3)
    phone = sheet["columns"][4]
    assert (phone["header"], phone["personal"], set(phone["sample"])) == (
        "Telefon",
        "PHONE",
        {"•••"},
    )
    # A document has no dataset.
    text = upload(lead, client, "a.md", b"# Fakt").json()
    assert (
        lead.get(f"{API}/clients/{client}/sources/{text['source_id']}").json()["reading"]["dataset"]
        is None
    )


def test_reading_a_source_again_answers_it_as_read_now(lead: TestClient, world: Any) -> None:
    client = world.client_id("primary")
    kept = upload(lead, client, "a.csv", b"a;b\n1;2\n").json()
    again = lead.post(f"{API}/clients/{client}/sources/{kept['source_id']}/reading")
    assert again.status_code == 200
    assert (again.json()["reader"], again.json()["reading"]["outcome"]) == ("csv/1", "READ")
    other = world.client_id("other")
    assert (
        lead.post(f"{API}/clients/{other}/sources/{kept['source_id']}/reading").status_code == 404
    )


# ---- a document item carries its file (client-workspace C7a) ---------------------------


def propose(c: TestClient, client_id: str, kind: str, content: dict[str, Any]) -> Any:
    return c.post(
        f"{API}/clients/{client_id}/knowledge/proposals",
        json={"kind": kind, "title": "Zadání výzkumu", "content": content},
    )


def test_a_document_item_names_its_clients_source_and_keeps_it_through_an_edit(
    lead: TestClient, world: Any
) -> None:
    client = world.client_id("primary")
    kept = upload(lead, client, "Zadání.md", b"# Zadani\n\nFakt.").json()
    added = propose(lead, client, "DOCUMENT", {"source_id": kept["source_id"]})
    assert added.status_code == 201, added.text
    assert added.json()["source_id"] == kept["source_id"]
    item_id = added.json()["item_id"]
    edited = lead.post(
        f"{API}/clients/{client}/knowledge/proposals",
        json={
            "kind": "DOCUMENT",
            "title": "Zadání výzkumu, verze 2",
            "content": {"source_id": kept["source_id"]},
            "item_id": item_id,
            "base_revision": 1,
        },
    )
    assert edited.status_code == 201, edited.text
    item = next(
        i for i in lead.get(f"{API}/clients/{client}/knowledge").json() if i["item_id"] == item_id
    )
    assert (item["revision"], item["content"]) == (2, {"source_id": kept["source_id"]})


def test_another_clients_source_cannot_be_named(
    lead: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    kept = upload(lead, world.client_id("primary"), "a.txt", b"Fakt.").json()
    got = propose(
        other_client_lead, world.client_id("other"), "DOCUMENT", {"source_id": kept["source_id"]}
    )
    assert got.status_code == 422 and got.json()["code"] == "unknown_source"
    # An id no source has is the same answer.
    got = propose(
        lead, world.client_id("primary"), "DOCUMENT", {"source_id": "SRC-0000000000000000"}
    )
    assert got.status_code == 422 and got.json()["code"] == "unknown_source"


def test_only_the_material_kinds_carry_a_source_and_only_by_its_id(
    lead: TestClient, world: Any
) -> None:
    client = world.client_id("primary")
    kept = upload(lead, client, "a.txt", b"Fakt.").json()
    for kind, content in (
        ("FACT", {"source_id": kept["source_id"]}),
        ("DOCUMENT", {"source_id": "../../etc"}),
        ("DOCUMENT", {"source_id": 7}),
    ):
        got = propose(lead, client, kind, content)
        assert got.status_code == 422 and got.json()["code"] == "invalid_proposal", (kind, content)


def test_a_studys_proposal_does_not_attach_a_clients_source(lead: TestClient, world: Any) -> None:
    kept = upload(lead, world.client_id("primary"), "a.txt", b"Fakt.").json()
    got = lead.post(
        f"{API}/studies/{world.study_id('primary')}/knowledge-proposals",
        json={"kind": "DOCUMENT", "title": "Zadání", "content": {"source_id": kept["source_id"]}},
    )
    assert got.status_code == 422 and got.json()["code"] == "invalid_proposal"


# ------------------------------------------------- AI proposals from a source (K2d4)

DOCUMENT = (
    "Fiktivní pivovar Lupínek vaří od roku 1998.\n\nZnačku zná 41 % dospělých v kraji.\n"
).encode()


def _fail_run(app: Any, run_id: str) -> None:
    """End a run without a result, as a refused step would."""
    from aia_core.domain.workflow import WorkflowRunStatus
    from aia_core.infrastructure.db import create_session_factory
    from aia_core.infrastructure.tables import WorkflowRunRow

    with create_session_factory(app.state.engine)() as session:
        run = session.get(WorkflowRunRow, run_id)
        assert run is not None
        run.status = WorkflowRunStatus.FAILED.value
        session.commit()


def test_proposals_are_queued_once_per_reading_as_the_clients_own_work(
    lead: TestClient, world: Any, app: Any
) -> None:
    client = world.client_id("primary")
    source = upload(lead, client, "lupinek.txt", DOCUMENT).json()["source_id"]
    url = f"{API}/clients/{client}/sources/{source}/proposals"
    assert lead.get(url).json() is None  # nobody has asked

    first = lead.post(url)
    assert first.status_code == 202, first.text
    body = first.json()
    assert (body["source_id"], body["created"], body["current"]) == (source, True, True)
    assert (body["status"], body["step_status"]) == ("RUNNING", "RUNNABLE")
    assert body["reason"] is None and body["output"] == {}

    # Asked again: the same run, nothing queued (and nothing paid) twice.
    again = lead.post(url)
    assert again.status_code == 200 and again.json()["run_id"] == body["run_id"]
    assert again.json()["created"] is False
    assert lead.get(url).json()["run_id"] == body["run_id"]

    # After a run ends without a result, asking again starts another.
    _fail_run(app, body["run_id"])
    retried = lead.post(url)
    assert retried.status_code == 202 and retried.json()["run_id"] != body["run_id"]
    assert lead.get(url).json()["run_id"] == retried.json()["run_id"]

    # The run is the client's: it names no study.
    from aia_core.infrastructure.db import create_session_factory
    from aia_core.infrastructure.tables import WorkflowRunRow

    with create_session_factory(app.state.engine)() as session:
        run = session.get(WorkflowRunRow, retried.json()["run_id"])
        assert run is not None and (run.client_id, run.study_id) == (client, None)


def test_a_source_it_does_not_extract_is_refused_by_name_and_nothing_is_queued(
    lead: TestClient, world: Any
) -> None:
    client = world.client_id("primary")
    table = upload(lead, client, "znalost.csv", "značka;znalost\nLupínek;41\n".encode()).json()
    url = f"{API}/clients/{client}/sources/{table['source_id']}/proposals"
    refused = lead.post(url)
    assert refused.status_code == 422 and refused.json()["code"] == "dataset_not_extracted"
    assert lead.get(url).json() is None


def test_another_clients_source_has_no_proposals_here(
    lead: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    source = upload(lead, world.client_id("primary"), "a.txt", DOCUMENT).json()["source_id"]
    other = world.client_id("other")
    url = f"{API}/clients/{other}/sources/{source}/proposals"
    assert other_client_lead.post(url).status_code == 404
    assert other_client_lead.get(url).status_code == 404


def test_an_ai_proposal_shows_its_quote_and_where_it_stands_for_review(
    lead: TestClient, world: Any, app: Any
) -> None:
    """What the step filed reaches Ke schválení with the words it rests on."""
    from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
    from aia_core.domain.knowledge import KnowledgeKind, ProposalDraft
    from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository
    from aia_core.infrastructure.db import create_session_factory

    client = world.client_id("primary")
    source = upload(lead, client, "lupinek.txt", DOCUMENT).json()["source_id"]
    run_id = lead.post(f"{API}/clients/{client}/sources/{source}/proposals").json()["run_id"]
    with create_session_factory(app.state.engine)() as session:
        principal = AuthenticatedPrincipal(
            user_id=world.users["lead"], organization_id=world.organization_id
        )
        work = ScopeResolver(session).client_work_context(principal, client_id=client)
        ClientKnowledgeRepository(session).propose_from_client_work(
            work,
            run_id=run_id,
            drafts=[
                ProposalDraft(
                    kind=KnowledgeKind.FINDING,
                    title="Znalost značky 41 %",
                    summary="",
                    content={"quote": "Značku zná 41 %", "locator": {"line": 3}},
                    provenance={"source_id": source, "segment": 1},
                )
            ],
        )
        session.commit()
    pending = lead.get(f"{API}/clients/{client}/knowledge/proposals?status=PROPOSED").json()
    ai = next(p for p in pending if p["title"] == "Znalost značky 41 %")
    assert ai["from_source"] == {
        "source_id": source,
        "run_id": run_id,
        "quote": "Značku zná 41 %",
        "locator": {"line": 3},
    }
    assert ai["study_id"] is None and ai["source_id"] is None
