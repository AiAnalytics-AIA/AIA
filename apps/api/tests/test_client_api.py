"""The client workspace API (ADR 0015): clients, their studies, the bridge, knowledge.

Every route resolves scope first. These tests cross the client boundary on
purpose: a client's studies, workspace and knowledge must never appear under
another client, and a direct attempt across it must fail closed (404).
"""

from __future__ import annotations

from typing import Any

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
# The unit bridge (OI-58)
# --------------------------------------------------------------------------- #


def test_the_study_workspace_binds_once_under_the_studys_scope(
    lead: TestClient, viewer: TestClient, world: Any
) -> None:
    url = f"{API}/studies/{world.study_id()}/workspace"
    first = lead.get(url).json()
    assert (
        first["unit_project_id"] is None and first["client_name"] == world.clients["primary"].name
    )
    assert viewer.put(url, json={"unit_project_id": "PRJ-viewer"}).status_code == 403
    bound = lead.put(url, json={"unit_project_id": "PRJ-abc"})
    assert bound.status_code == 200 and bound.json()["unit_project_id"] == "PRJ-abc"
    assert lead.put(url, json={"unit_project_id": "PRJ-other"}).status_code == 409
    assert lead.put(url, json={"unit_project_id": "../etc"}).status_code == 422
    assert lead.put(f"{url}/stage", json={"stage": "questionnaire"}).status_code == 204
    listed = lead.get(f"{API}/clients/{world.client_id()}/studies").json()
    row = next(s for s in listed if s["study_id"] == world.study_id())
    assert (row["last_stage"], row["has_working_content"]) == ("questionnaire", True)


def test_the_workspace_of_another_clients_study_is_not_found(
    lead: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    lead.put(f"{API}/studies/{world.study_id()}/workspace", json={"unit_project_id": "PRJ-acme"})
    for method in ("get", "put"):
        r = getattr(other_client_lead, method)(
            f"{API}/studies/{world.study_id()}/workspace",
            **({"json": {"unit_project_id": "PRJ-x"}} if method == "put" else {}),
        )
        assert r.status_code == 404
    # A unit project already bound to one client's study cannot be claimed by another's.
    claimed = other_client_lead.put(
        f"{API}/studies/{world.study_id('other_client')}/workspace",
        json={"unit_project_id": "PRJ-acme"},
    )
    assert claimed.status_code == 409 and claimed.json()["code"] == "unit_project_taken"
