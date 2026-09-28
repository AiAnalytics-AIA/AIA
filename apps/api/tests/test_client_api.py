"""The client workspace API (ADR 0015): clients, their studies, the bridge, knowledge.

Every route resolves scope first. These tests cross the client boundary on
purpose: a client's studies, workspace and knowledge must never appear under
another client, and a direct attempt across it must fail closed (404).
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any

import pytest
from fastapi.testclient import TestClient

API = "/api/v1"


def start(
    c: TestClient, world: Any, name: str, kind: str = "RESEARCH", client: str = "primary"
) -> Any:
    return c.post(
        f"{API}/clients/{world.client_id(client)}/studies", json={"name": name, "kind": kind}
    )


# --------------------------------------------------------------------------- #
# The directory and one client
# --------------------------------------------------------------------------- #


def test_the_directory_lists_only_the_clients_you_work_for(
    lead: TestClient,
    other_client_lead: TestClient,
    outsider: TestClient,
    owner: TestClient,
    world: Any,
) -> None:
    mine = lead.get(f"{API}/workspace/clients").json()
    assert [c["client_id"] for c in mine] == [world.client_id("primary")]
    assert mine[0]["your_role"] == "LEAD" and mine[0]["active_count"] == 2
    assert [c["client_id"] for c in other_client_lead.get(f"{API}/workspace/clients").json()] == [
        world.client_id("other")
    ]
    assert outsider.get(f"{API}/workspace/clients").json() == []
    # An owner administers the organization; opening a client's work needs a grant (ADR 0004).
    assert owner.get(f"{API}/workspace/clients").json() == []


def test_an_administrator_starts_a_client_and_can_open_it_members_cannot(
    owner: TestClient, lead: TestClient, world: Any
) -> None:
    me = owner.get(f"{API}/workspace/me").json()
    assert me["may_administer"] is True and me["organization_role"] == "OWNER"
    assert lead.get(f"{API}/workspace/me").json()["may_administer"] is False
    made = owner.post(f"{API}/workspace/clients", json={"name": "Nový klient s. r. o."})
    assert made.status_code == 201 and made.json()["your_role"] == "LEAD"
    assert made.json()["slug"].startswith("novy-klient-s-r-o-")
    assert [c["client_id"] for c in owner.get(f"{API}/workspace/clients").json()] == [
        made.json()["client_id"]
    ]
    audit = owner.get(f"{API}/access-audit").json()
    assert any(
        a["action"] == "CLIENT_SELF_GRANT" and a["client_id"] == made.json()["client_id"]
        for a in audit
    )
    assert lead.post(f"{API}/workspace/clients", json={"name": "Nope"}).status_code == 403
    # The new client is invisible to people without a grant on it.
    assert lead.get(f"{API}/clients/{made.json()['client_id']}").status_code == 404


def test_a_client_workspace_cannot_be_opened_outside_your_scope(
    lead: TestClient, other_client_lead: TestClient, outsider: TestClient, world: Any
) -> None:
    ok = lead.get(f"{API}/clients/{world.client_id()}")
    assert ok.status_code == 200 and ok.json()["your_role"] == "LEAD"
    for c in (other_client_lead, outsider):
        for path in ("", "/studies", "/overview", "/knowledge", "/knowledge/proposals"):
            r = c.get(f"{API}/clients/{world.client_id()}{path}")
            assert r.status_code == 404, (path, r.text)
    assert lead.get(f"{API}/clients/CLI-0000000000").status_code == 404
    assert lead.get(f"{API}/clients/not-a-client").status_code == 422


def test_research_and_simulation_belong_to_the_selected_client(
    researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    research = start(researcher, world, "Vnímání značky 2026")
    sim = start(researcher, world, "Cenové scénáře", kind="SIMULATION")
    assert research.status_code == 201 and sim.status_code == 201
    assert (
        research.json()["client_id"] == world.client_id() and research.json()["kind"] == "RESEARCH"
    )
    assert research.json()["slug"].startswith("vnimani-znacky-2026-")
    listed = researcher.get(
        f"{API}/clients/{world.client_id()}/studies", params={"kind": "SIMULATION"}
    ).json()
    assert [s["study_id"] for s in listed] == [sim.json()["study_id"]]
    # Another client's lead neither sees them nor starts work under this client.
    theirs = other_client_lead.get(f"{API}/clients/{world.client_id('other')}/studies").json()
    assert {s["client_id"] for s in theirs} == {world.client_id("other")}
    assert research.json()["study_id"] not in {s["study_id"] for s in theirs}
    assert start(other_client_lead, world, "Hijack").status_code == 404


def test_starting_work_needs_a_role_that_may(
    viewer: TestClient, reviewer: TestClient, world: Any
) -> None:
    for c in (viewer, reviewer):
        r = start(c, world, "Nope")
        assert r.status_code == 403 and r.json()["code"] == "insufficient_role"


def test_the_overview_shows_active_work_and_the_knowledge_state(
    lead: TestClient, researcher: TestClient, world: Any
) -> None:
    started = start(researcher, world, "Brand perception").json()
    researcher.post(
        f"{API}/clients/{world.client_id()}/knowledge/proposals",
        json={"kind": "TERM", "title": "Flotilový zákazník"},
    )
    body = lead.get(f"{API}/clients/{world.client_id()}/overview").json()
    assert started["study_id"] in [s["study_id"] for s in body["active"]]
    assert body["client"]["name"] == world.clients["primary"].name
    assert body["knowledge"]["pending_proposals"] == 1
    assert [p["title"] for p in body["pending"]] == ["Flotilový zákazník"]


# --------------------------------------------------------------------------- #
# Client knowledge
# --------------------------------------------------------------------------- #


def test_knowledge_is_proposed_approved_and_never_seen_by_another_client(
    researcher: TestClient, reviewer: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    base = f"{API}/clients/{world.client_id()}/knowledge"
    proposal = researcher.post(
        f"{base}/proposals",
        json={"kind": "FACT", "title": "134 dealerů", "summary": "Výroční zpráva"},
    ).json()
    assert researcher.get(base).json() == []
    # The proposer does not approve their own update.
    assert (
        researcher.post(
            f"{base}/proposals/{proposal['proposal_id']}/decision", json={"approve": True}
        ).status_code
        == 403
    )
    decided = reviewer.post(
        f"{base}/proposals/{proposal['proposal_id']}/decision", json={"approve": True}
    )
    assert decided.status_code == 200 and decided.json()["status"] == "APPROVED"
    assert (
        reviewer.post(
            f"{base}/proposals/{proposal['proposal_id']}/decision", json={"approve": False}
        ).status_code
        == 409
    )
    [item] = researcher.get(base, params={"section": "knowledge"}).json()
    assert item["title"] == "134 dealerů"
    history = researcher.get(f"{base}/items/{item['item_id']}/revisions").json()
    assert history[0]["provenance"]["origin"] == "CLIENT"

    # Client B: nothing, and direct attempts fail closed.
    assert other_client_lead.get(f"{API}/clients/{world.client_id('other')}/knowledge").json() == []
    assert other_client_lead.get(base).status_code == 404
    assert other_client_lead.get(f"{base}/items/{item['item_id']}/revisions").status_code == 404
    theirs = f"{API}/clients/{world.client_id('other')}/knowledge"
    assert other_client_lead.get(f"{theirs}/items/{item['item_id']}/revisions").status_code == 404
    assert (
        other_client_lead.post(
            f"{theirs}/proposals/{proposal['proposal_id']}/decision", json={"approve": False}
        ).status_code
        == 404
    )
    assert (
        other_client_lead.post(
            f"{theirs}/proposals", json={"kind": "FACT", "title": "x", "item_id": item["item_id"]}
        ).status_code
        == 404
    )


def test_a_study_proposes_and_consumes_but_never_writes_client_knowledge(
    researcher: TestClient, reviewer: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    study = f"{API}/studies/{world.study_id()}"
    proposed = researcher.post(
        f"{study}/knowledge-proposals", json={"kind": "FINDING", "title": "Mladší kupci řeší cenu"}
    )
    assert proposed.status_code == 201 and proposed.json()["origin"] == "STUDY"
    assert researcher.get(f"{study}/context").json()["client"] == []
    pending = reviewer.get(
        f"{API}/clients/{world.client_id()}/knowledge/proposals", params={"status": "PROPOSED"}
    ).json()
    assert pending[0]["study_name"] == world.studies["primary"].name
    reviewer.post(
        f"{API}/clients/{world.client_id()}/knowledge/proposals/{proposed.json()['proposal_id']}/decision",
        json={"approve": True},
    )
    assert [i["title"] for i in researcher.get(f"{study}/context").json()["client"]] == [
        "Mladší kupci řeší cenu"
    ]
    other = other_client_lead.get(f"{API}/studies/{world.study_id('other_client')}/context").json()
    assert other["client"] == [] and other["client_id"] == world.client_id("other")
    assert other_client_lead.get(f"{study}/context").status_code == 404


def test_a_study_only_grantee_sees_the_study_but_not_the_clients_knowledge(
    lead: TestClient, outsider: TestClient, world: Any
) -> None:
    granted = lead.post(
        f"{API}/studies/{world.study_id()}/grants",
        json={"user_id": world.users["outsider"], "role": "RESEARCHER"},
    )
    assert granted.status_code == 204
    ws = outsider.get(f"{API}/clients/{world.client_id()}")
    assert ws.status_code == 200 and ws.json()["your_role"] is None
    assert [
        s["study_id"] for s in outsider.get(f"{API}/clients/{world.client_id()}/studies").json()
    ] == [world.study_id()]
    assert outsider.get(f"{API}/clients/{world.client_id()}/knowledge").status_code == 403
    assert outsider.get(f"{API}/clients/{world.client_id()}/overview").json()["knowledge"] is None


# --------------------------------------------------------------------------- #
# A study's working content, in AIA (ADR 0018, OI-58)
# --------------------------------------------------------------------------- #

BRIEF = {"title": "Vnímání značky", "goal": "Co lidé o značce vědí", "sections": []}


def test_a_new_study_starts_empty_with_the_template_and_its_first_save_is_revision_one(
    lead: TestClient, viewer: TestClient, world: Any
) -> None:
    url = f"{API}/studies/{world.study_id()}/workspace"
    frame = lead.get(url).json()
    assert frame["content_state"] == "EMPTY" and frame["can_edit"] is True
    assert frame["client_name"] == world.clients["primary"].name
    assert "unit_project_id" not in frame
    empty = lead.get(f"{url}/content").json()
    assert (empty["state"], empty["revision"], empty["content"]) == ("EMPTY", None, None)
    assert empty["template"]["title"] == "Nový výzkum" and empty["can_edit"] is True

    assert viewer.put(f"{url}/content", json={"content": BRIEF}).status_code == 403
    saved = lead.put(f"{url}/content", json={"content": BRIEF, "reason": "autosave"})
    assert saved.status_code == 200
    assert saved.json() | {"revision_id": "x"} == {
        "study_id": world.study_id(),
        "state": "NATIVE",
        "revision": 1,
        "revision_id": "x",
        "deduplicated": False,
    }
    loaded = viewer.get(f"{url}/content").json()
    assert (loaded["state"], loaded["revision"], loaded["content"]) == ("NATIVE", 1, BRIEF)
    assert loaded["can_edit"] is False

    again = lead.put(
        f"{url}/content", json={"content": BRIEF, "analysis": {"x": 1}, "base_revision": 1}
    )
    assert again.json()["revision"] == 2
    history = lead.get(f"{url}/revisions").json()["items"]
    assert [r["revision"] for r in history] == [2, 1]

    assert lead.put(f"{url}/stage", json={"stage": "questionnaire"}).status_code == 204
    listed = lead.get(f"{API}/clients/{world.client_id()}/studies").json()
    row = next(s for s in listed if s["study_id"] == world.study_id())
    assert (row["last_stage"], row["has_working_content"], row["content_state"]) == (
        "questionnaire",
        True,
        "NATIVE",
    )


def test_a_save_from_a_stale_revision_is_a_conflict_that_names_the_current_one(
    lead: TestClient, researcher: TestClient, world: Any
) -> None:
    url = f"{API}/studies/{world.study_id()}/workspace/content"
    lead.put(url, json={"content": BRIEF})
    researcher.put(url, json={"content": {**BRIEF, "goal": "B"}, "base_revision": 1})
    stale = lead.put(url, json={"content": {**BRIEF, "goal": "A"}, "base_revision": 1})
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_revision"
    assert stale.json()["details"] == {"current_revision": 2}
    blind = lead.put(url, json={"content": BRIEF})
    assert blind.status_code == 409


def test_content_is_validated_before_it_is_saved(lead: TestClient, world: Any) -> None:
    url = f"{API}/studies/{world.study_id()}/workspace/content"
    posing = lead.put(url, json={"content": {"title": "x", "study_id": "STU-other"}})
    assert posing.status_code == 422 and posing.json()["code"] == "content_carries_scope"
    assert lead.put(url, json={"content": {}}).json()["code"] == "content_empty"
    assert lead.put(url, json={"content": BRIEF, "reason": "Bad Reason"}).status_code == 422
    assert lead.put(url, json={"content": BRIEF, "base_revision": 0}).status_code == 422
    assert lead.get(url).json()["state"] == "EMPTY"


def test_the_workspace_of_another_clients_study_is_not_found(
    lead: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    lead.put(f"{API}/studies/{world.study_id()}/workspace/content", json={"content": BRIEF})
    for method, path in (
        ("get", ""),
        ("get", "/content"),
        ("put", "/content"),
        ("get", "/revisions"),
    ):
        r = getattr(other_client_lead, method)(
            f"{API}/studies/{world.study_id()}/workspace{path}",
            **({"json": {"content": BRIEF}} if method == "put" else {}),
        )
        assert r.status_code == 404, (method, path)
    # The other client's own study is untouched and empty.
    theirs = other_client_lead.get(
        f"{API}/studies/{world.study_id('other_client')}/workspace/content"
    ).json()
    assert theirs["state"] == "EMPTY"


def test_the_unit_binding_route_is_gone(lead: TestClient, world: Any) -> None:
    """ADR 0018: nothing binds a study to an 18.6.6 project any more."""
    r = lead.put(f"{API}/studies/{world.study_id()}/workspace", json={"unit_project_id": "PRJ-1"})
    assert r.status_code == 405


# --------------------------------------------------------------------------- #
# The brief's attachments (ADR 0018): AIA's storage, served only through the study
# --------------------------------------------------------------------------- #


def test_a_file_is_attached_in_aia_and_downloaded_only_through_its_study(
    lead: TestClient, viewer: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    url = f"{API}/studies/{world.study_id()}/workspace"
    body = {
        "filename": "Zadání.txt",
        "data_b64": base64.b64encode("Fiktivní zadání".encode()).decode(),
    }
    unsaved = lead.post(f"{url}/attachments", json=body)
    assert unsaved.status_code == 409 and unsaved.json()["code"] == "not_saved"

    lead.put(f"{url}/content", json={"content": BRIEF})
    assert viewer.post(f"{url}/attachments", json=body).status_code == 403
    created = lead.post(f"{url}/attachments", json=body)
    assert created.status_code == 201
    record = created.json()
    assert record == {
        "kind": "file",
        "attachment_id": record["attachment_id"],
        "filename": "Zad_n_.txt",
        "extension": ".txt",
        "content_type": "text/plain",
        "size_bytes": len("Fiktivní zadání".encode()),
        "sha256": hashlib.sha256("Fiktivní zadání".encode()).hexdigest(),
        "text_extracted": True,
        "context_excerpt": "Fiktivní zadání",
    }
    # Attaching changes nothing in the brief: the stage adds the record and saves.
    assert lead.get(f"{url}/content").json()["revision"] == 1

    download = viewer.get(f"{url}/attachments/{record['attachment_id']}")
    assert download.status_code == 200
    assert download.content == "Fiktivní zadání".encode()
    assert download.headers["content-type"] == "application/octet-stream"
    assert download.headers["content-disposition"] == 'attachment; filename="Zad_n_.txt"'
    assert download.headers["x-content-type-options"] == "nosniff"

    assert other_client_lead.get(f"{url}/attachments/{record['attachment_id']}").status_code == 404
    assert other_client_lead.post(f"{url}/attachments", json=body).status_code == 404
    assert lead.get(f"{url}/attachments/ART-0123456789abcdef").status_code == 404


@pytest.mark.parametrize("damage", ["tampered", "missing"])
def test_a_damaged_attachment_stays_marked_corrupt_after_the_409(
    lead: TestClient,
    viewer: TestClient,
    world: Any,
    damage_artifact: Any,
    artifact_status: Any,
    damage: str,
) -> None:
    """Regression: the attachment's CORRUPT mark was rolled back with the 409 that reported it.

    The download reads the bytes through ``ArtifactRepository.read``, which flushes
    the mark into the request's session and raises. The route answered 409 without
    committing, so ``get_session`` rolled the mark back and the file read VALID
    again, as #84 found for the run and research artifact routes.
    """
    url = f"{API}/studies/{world.study_id()}/workspace"
    lead.put(f"{url}/content", json={"content": BRIEF})
    body = {"filename": "zadani.txt", "data_b64": base64.b64encode(b"Fiktivni zadani").decode()}
    attachment_id = lead.post(f"{url}/attachments", json=body).json()["attachment_id"]
    damage_artifact(attachment_id, damage)

    refused = viewer.get(f"{url}/attachments/{attachment_id}")
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "artifact_corrupt"
    assert artifact_status(attachment_id) == "CORRUPT"
    assert viewer.get(f"{url}/attachments/{attachment_id}").status_code == 409


def test_an_attachment_is_checked_before_it_is_stored(lead: TestClient, world: Any) -> None:
    url = f"{API}/studies/{world.study_id()}/workspace"
    lead.put(f"{url}/content", json={"content": BRIEF})
    not_b64 = lead.post(f"{url}/attachments", json={"filename": "a.txt", "data_b64": "***"})
    assert not_b64.status_code == 422 and not_b64.json()["code"] == "not_base64"
    empty = lead.post(f"{url}/attachments", json={"filename": "a.txt", "data_b64": "="})
    assert empty.status_code == 422
    assert lead.post(f"{url}/attachments", json={"data_b64": "YQ=="}).status_code == 422
    assert lead.get(f"{url}/attachments/not-an-artifact").status_code == 422


# --------------------------------------------------------------------------- #
# The questionnaire import (ADR 0018): read in AIA, stored by the stage's save
# --------------------------------------------------------------------------- #

QUESTIONNAIRE_CSV = (
    "id,otazka,typ,moznosti,blok\nQ1,Souhlasíte?,vyber,Ano|Ne,Úvod\n"
    "S1,Jak vnímáte {object}?,objektova_sada,A|B|C|D,Značky\n"
)


def test_a_questionnaire_file_is_read_in_aia_and_nothing_is_stored(
    lead: TestClient, viewer: TestClient, world: Any
) -> None:
    url = f"{API}/studies/{world.study_id()}/workspace"
    body = {
        "filename": "dotaznik.csv",
        "data_b64": base64.b64encode(QUESTIONNAIRE_CSV.encode()).decode(),
    }
    assert viewer.post(f"{url}/questionnaire-import", json=body).status_code == 403
    imported = lead.post(f"{url}/questionnaire-import", json=body)
    assert imported.status_code == 200
    got = imported.json()
    assert got["summary"] == {"question_count": 1, "tracked_sets": 1, "sections": 2}
    assert [s["id"] for s in got["sections"]] == ["sec_import_1", "s1"]
    assert got["sections"][0]["questions"][0]["id"] == "q1"
    assert got["filename"] == "dotaznik.csv"
    # Reading a file is not a save: the study is still empty.
    assert lead.get(f"{url}/content").json()["state"] == "EMPTY"

    refused = lead.post(
        f"{url}/questionnaire-import",
        json={"filename": "d.csv", "data_b64": base64.b64encode(b"id,otazka\n").decode()},
    )
    assert refused.status_code == 422
    assert (refused.json()["code"], refused.json()["message"]) == (
        "missing_columns",
        "Chybí povinné sloupce: typ",
    )
    unreadable = lead.post(
        f"{url}/questionnaire-import",
        json={"filename": "d.xlsx", "data_b64": base64.b64encode(b"not a zip").decode()},
    )
    assert unreadable.status_code == 422 and unreadable.json()["code"] == "unreadable"


def test_the_questionnaire_template_is_aias_workbook_for_any_reader_of_the_study(
    viewer: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    url = f"{API}/studies/{world.study_id()}/workspace/questionnaire-template"
    template = viewer.get(url)
    assert template.status_code == 200
    assert template.content.startswith(b"PK")
    assert (
        template.headers["content-disposition"]
        == 'attachment; filename="AIA_dotaznik_sablona.xlsx"'
    )
    assert other_client_lead.get(url).status_code == 404
