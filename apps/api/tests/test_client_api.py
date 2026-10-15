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


def test_the_directory_lists_every_client_to_every_member(
    lead: TestClient,
    other_client_lead: TestClient,
    outsider: TestClient,
    owner: TestClient,
    world: Any,
) -> None:
    """ADR 0019 decision 2: membership of the organization is the access to every client."""
    both = {world.client_id("primary"), world.client_id("other")}
    for c in (lead, other_client_lead, outsider, owner):
        listed = c.get(f"{API}/workspace/clients").json()
        assert {x["client_id"] for x in listed} == both
        assert {x["your_role"] for x in listed} == {"RESEARCHER"}
    primary = next(
        x
        for x in lead.get(f"{API}/workspace/clients").json()
        if x["client_id"] == world.client_id("primary")
    )
    assert primary["active_count"] == 2


def test_a_researcher_starts_a_client_and_every_member_can_open_it(
    owner: TestClient, lead: TestClient, outsider: TestClient, world: Any
) -> None:
    """Starting a client needs no administration (ADR 0019; the owner, 2026-10-05)."""
    me = owner.get(f"{API}/workspace/me").json()
    assert me["may_administer"] is True and me["organization_role"] == "OWNER"
    assert lead.get(f"{API}/workspace/me").json()["may_administer"] is False
    made = lead.post(f"{API}/workspace/clients", json={"name": "Nový klient s. r. o."})
    assert made.status_code == 201 and made.json()["your_role"] == "RESEARCHER"
    assert made.json()["slug"].startswith("novy-klient-s-r-o-")
    assert made.json()["client_id"] in {
        c["client_id"] for c in owner.get(f"{API}/workspace/clients").json()
    }
    audit = owner.get(f"{API}/access-audit").json()
    # Starting a client is audited as its creation, with the researcher who started it;
    # no self-grant is written (ADR 0019).
    mine = [a for a in audit if a["client_id"] == made.json()["client_id"]]
    assert [a["action"] for a in mine] == ["CLIENT_CREATED"]
    assert mine[0]["actor_id"] == world.users["lead"]
    # The new client is the organization's: every member opens it, no grant needed.
    opened = outsider.get(f"{API}/clients/{made.json()['client_id']}")
    assert opened.status_code == 200 and opened.json()["your_role"] == "RESEARCHER"


def test_a_researcher_creates_a_client_by_the_api_but_its_status_stays_with_administration(
    owner: TestClient, lead: TestClient
) -> None:
    """``POST /clients`` is open to any member; ``PUT /clients/{id}/status`` is not."""
    made = lead.post(f"{API}/clients", json={"slug": "lead-made", "name": "Lead made"})
    assert made.status_code == 201, made.text
    client_id = made.json()["client_id"]
    archive = {"status": "ARCHIVED"}
    assert lead.put(f"{API}/clients/{client_id}/status", json=archive).status_code == 403
    assert owner.put(f"{API}/clients/{client_id}/status", json=archive).status_code == 200


def test_a_client_workspace_opens_for_every_member_and_an_unknown_one_is_404(
    lead: TestClient, other_client_lead: TestClient, outsider: TestClient, world: Any
) -> None:
    for c in (lead, other_client_lead, outsider):
        ok = c.get(f"{API}/clients/{world.client_id()}")
        assert ok.status_code == 200 and ok.json()["your_role"] == "RESEARCHER"
        for path in ("/studies", "/overview", "/knowledge", "/knowledge/proposals"):
            r = c.get(f"{API}/clients/{world.client_id()}{path}")
            assert r.status_code == 200, (path, r.text)
    assert lead.get(f"{API}/clients/CLI-0000000000").status_code == 404
    assert lead.get(f"{API}/clients/not-a-client").status_code == 422


def test_the_client_counts_its_open_studies_and_its_knowledge_for_the_tabs(
    owner: TestClient, researcher: TestClient, world: Any
) -> None:
    """The tabs' counts: open studies by kind, proposals waiting, datasets; this client only."""
    url = f"{API}/clients/{world.client_id()}"
    assert researcher.get(url).json()["counts"] == {
        "research": 2,
        "simulations": 0,
        "pending_proposals": 0,
        "datasets": 0,
    }
    start(researcher, world, "Cenové scénáře", kind="SIMULATION")
    start(researcher, world, "Jinde", client="other")
    researcher.post(
        f"{API}/studies/{world.study_id()}/knowledge-proposals",
        json={"kind": "FINDING", "title": "Mladší kupci řeší cenu"},
    )
    researcher.post(
        f"{url}/knowledge/proposals", json={"kind": "DATASET", "title": "Klientská báze 2026"}
    )
    archived = owner.put(
        f"{API}/studies/{world.study_id('sibling')}/status", json={"status": "ARCHIVED"}
    )
    assert archived.status_code == 200, archived.text
    assert researcher.get(url).json()["counts"] == {
        "research": 1,
        "simulations": 1,
        "pending_proposals": 1,
        "datasets": 1,
    }
    other = researcher.get(f"{API}/clients/{world.client_id('other')}").json()["counts"]
    assert other == {"research": 2, "simulations": 0, "pending_proposals": 0, "datasets": 0}


def test_the_studies_list_says_what_each_study_brought_into_the_clients_knowledge(
    researcher: TestClient, lead: TestClient, world: Any
) -> None:
    base = f"{API}/clients/{world.client_id()}/knowledge/proposals"
    for title in ("Mladší kupci řeší cenu", "Starší kupci řeší servis"):
        researcher.post(
            f"{API}/studies/{world.study_id()}/knowledge-proposals",
            json={"kind": "FINDING", "title": title},
        )
    waiting = lead.get(base, params={"status": "PROPOSED"}).json()
    lead.post(f"{base}/{waiting[0]['proposal_id']}/decision", json={"approve": True})
    # A person's own addition counts against no study.
    researcher.post(base, json={"kind": "TERM", "title": "Flotilový zákazník"})

    listed = {
        s["study_id"]: s["knowledge"]
        for s in researcher.get(f"{API}/clients/{world.client_id()}/studies").json()
    }
    assert listed[world.study_id()] == {"approved": 1, "proposed": 1, "rejected": 0}
    assert listed[world.study_id("sibling")] == {"approved": 0, "proposed": 0, "rejected": 0}
    # Another client's list knows nothing of it.
    theirs = researcher.get(f"{API}/clients/{world.client_id('other')}/studies").json()
    assert all(s["knowledge"] == {"approved": 0, "proposed": 0, "rejected": 0} for s in theirs)


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
    # A client's studies list is that client's alone, whoever asks (ADR 0019: any member may ask).
    theirs = other_client_lead.get(f"{API}/clients/{world.client_id('other')}/studies").json()
    assert {s["client_id"] for s in theirs} == {world.client_id("other")}
    assert research.json()["study_id"] not in {s["study_id"] for s in theirs}
    # Another client's lead may start work under this client too; it belongs to this client.
    theirs_here = start(other_client_lead, world, "Od druhého vedoucího")
    assert theirs_here.status_code == 201
    assert theirs_here.json()["client_id"] == world.client_id()


def test_every_member_may_start_work_with_or_without_a_grant(
    viewer: TestClient, reviewer: TestClient, outsider: TestClient, world: Any
) -> None:
    """ADR 0019: the old labels, and a member never granted the client, all hold the one role."""
    for c, name in (
        (viewer, "Od prohlížeče"),
        (reviewer, "Od recenzenta"),
        (outsider, "Bez přidělení"),
    ):
        r = start(c, world, name)
        assert r.status_code == 201, r.text
        assert r.json()["client_id"] == world.client_id()


def test_the_overview_shows_active_work_and_the_knowledge_state(
    lead: TestClient, researcher: TestClient, world: Any
) -> None:
    started = start(researcher, world, "Brand perception").json()
    # A person's own addition is knowledge at once; only a study's finding waits.
    researcher.post(
        f"{API}/clients/{world.client_id()}/knowledge/proposals",
        json={"kind": "TERM", "title": "Flotilový zákazník"},
    )
    researcher.post(
        f"{API}/studies/{world.study_id()}/knowledge-proposals",
        json={"kind": "FINDING", "title": "Mladší kupci řeší cenu"},
    )
    body = lead.get(f"{API}/clients/{world.client_id()}/overview").json()
    assert started["study_id"] in [s["study_id"] for s in body["active"]]
    assert body["client"]["name"] == world.clients["primary"].name
    assert body["knowledge"]["items_by_kind"] == {"TERM": 1}
    assert body["knowledge"]["pending_proposals"] == 1
    assert [p["title"] for p in body["pending"]] == ["Mladší kupci řeší cenu"]
    # What wants attention: the new term is in no folder and was changed today.
    assert body["knowledge"]["unfiled_items"] == 1 and body["knowledge"]["stale_items"] == 0
    # What changed: the term a person wrote; the study's finding still waits, so it is not here.
    assert [(c["title"], c["origin"], c["revision"]) for c in body["recent_changes"]] == [
        ("Flotilový zákazník", "PERSON", 1)
    ]


# --------------------------------------------------------------------------- #
# Client knowledge
# --------------------------------------------------------------------------- #


def test_knowledge_is_proposed_approved_and_never_seen_by_another_client(
    owner: TestClient,
    researcher: TestClient,
    reviewer: TestClient,
    other_client_lead: TestClient,
    world: Any,
) -> None:
    # ADR 0019 made self-approval the default; this client asks for independent review.
    forbid = owner.put(
        f"{API}/self-approval", json={"allowed": False, "client_id": world.client_id()}
    )
    assert forbid.status_code == 200, forbid.text
    base = f"{API}/clients/{world.client_id()}/knowledge"
    proposal = researcher.post(
        f"{base}/proposals",
        json={"kind": "FACT", "title": "134 dealerů", "summary": "Výroční zpráva"},
    ).json()
    assert researcher.get(base).json() == []
    # With independent review asked for, the proposer does not approve their own update.
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

    # Client B's workspace: nothing, and direct attempts through it fail closed. Knowledge belongs
    # to the client whose path it is read under; Globex's lead may open Acme's workspace too
    # (ADR 0019) and sees Acme's knowledge there, never under Globex.
    assert other_client_lead.get(f"{API}/clients/{world.client_id('other')}/knowledge").json() == []
    via_acme = other_client_lead.get(base, params={"section": "knowledge"})
    assert via_acme.status_code == 200 and [i["item_id"] for i in via_acme.json()] == [
        item["item_id"]
    ]
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


def test_by_default_what_a_person_adds_to_a_client_takes_effect_at_once(
    researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    """ADR 0019 decision 3: no approval between people; a source a person adds is knowledge."""
    base = f"{API}/clients/{world.client_id()}/knowledge"
    added = researcher.post(
        f"{base}/proposals", json={"kind": "SOURCE", "title": "Starbucks annual report"}
    )
    assert added.status_code == 201, added.text
    record = added.json()
    assert record["status"] == "APPROVED" and record["revision"] == 1
    assert researcher.get(f"{base}/proposals", params={"status": "PROPOSED"}).json() == []
    [item] = researcher.get(base, params={"section": "sources"}).json()
    assert item["title"] == "Starbucks annual report"
    history = researcher.get(f"{base}/items/{item['item_id']}/revisions").json()
    assert history[0]["provenance"]["authored"] == "person"
    # Never across clients.
    assert other_client_lead.get(f"{API}/clients/{world.client_id('other')}/knowledge").json() == []
    assert (
        other_client_lead.post(
            f"{API}/clients/{world.client_id('other')}/knowledge/proposals/"
            f"{record['proposal_id']}/decision",
            json={"approve": True},
        ).status_code
        == 404
    )


def test_by_default_the_proposer_may_approve_their_own_studys_finding(
    researcher: TestClient, world: Any
) -> None:
    """What a study offers is the AI's side of the gate, and one person may accept it."""
    proposed = researcher.post(
        f"{API}/studies/{world.study_id()}/knowledge-proposals",
        json={"kind": "FINDING", "title": "Mladší kupci řeší cenu"},
    ).json()
    assert proposed["status"] == "PROPOSED" and proposed["yours"] is True
    base = f"{API}/clients/{world.client_id()}/knowledge"
    decided = researcher.post(
        f"{base}/proposals/{proposed['proposal_id']}/decision", json={"approve": True}
    )
    assert decided.status_code == 200 and decided.json()["status"] == "APPROVED"
    assert [i["title"] for i in researcher.get(base, params={"section": "knowledge"}).json()] == [
        "Mladší kupci řeší cenu"
    ]


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
    # A study's context is its own client's alone. Another client's lead may open this study
    # (ADR 0019) and gets this study's client context, never their own client's.
    here = other_client_lead.get(f"{study}/context")
    assert here.status_code == 200 and here.json()["client_id"] == world.client_id()


def test_an_edit_written_from_an_older_revision_is_a_409_until_the_reviewer_names_the_current(
    researcher: TestClient, reviewer: TestClient, world: Any
) -> None:
    """F-K1: approving a study's older edit no longer replaces a newer correction."""
    base = f"{API}/clients/{world.client_id()}/knowledge"
    first = researcher.post(f"{base}/proposals", json={"kind": "FACT", "title": "Dealers: 120"})
    item_id = first.json()["item_id"]
    edit = researcher.post(
        f"{API}/studies/{world.study_id()}/knowledge-proposals",
        json={"kind": "FACT", "title": "Dealers: 125", "item_id": item_id},
    ).json()
    assert edit["base_revision"] == 1
    corrected = researcher.post(
        f"{base}/proposals",
        json={"kind": "FACT", "title": "Dealers: 134", "item_id": item_id, "base_revision": 1},
    )
    assert corrected.status_code == 201 and corrected.json()["revision"] == 2

    # A person's save from the screen that still showed revision 1 is refused too.
    again = researcher.post(
        f"{base}/proposals",
        json={"kind": "FACT", "title": "Dealers: 99", "item_id": item_id, "base_revision": 1},
    )
    assert again.status_code == 409
    assert again.json()["code"] == "knowledge_proposal_stale"

    decision = f"{base}/proposals/{edit['proposal_id']}/decision"
    refused = reviewer.post(decision, json={"approve": True})
    assert refused.status_code == 409, refused.text
    error = refused.json()
    assert error["code"] == "knowledge_proposal_stale"
    assert error["details"] == {"item_id": item_id, "base_revision": 1, "current_revision": 2}
    [item] = researcher.get(base, params={"section": "knowledge"}).json()
    assert (item["title"], item["revision"]) == ("Dealers: 134", 2)

    accepted = reviewer.post(decision, json={"approve": True, "reviewed_revision": 2})
    assert accepted.status_code == 200 and accepted.json()["revision"] == 3
    [item] = researcher.get(base, params={"section": "knowledge"}).json()
    assert item["title"] == "Dealers: 125"


def test_any_member_sees_the_whole_client_and_its_knowledge(
    outsider: TestClient, world: Any
) -> None:
    """ADR 0019: the study-only grantee, who saw one study and no knowledge, is gone."""
    client = f"{API}/clients/{world.client_id()}"
    ws = outsider.get(client)
    assert ws.status_code == 200 and ws.json()["your_role"] == "RESEARCHER"
    studies = [s["study_id"] for s in outsider.get(f"{client}/studies").json()]
    assert len(studies) == 2  # the client's two studies, with nothing granted
    assert outsider.get(f"{client}/knowledge").status_code == 200
    assert outsider.get(f"{client}/overview").json()["knowledge"] is not None


# --------------------------------------------------------------------------- #
# A study's working content, in AIA (ADR 0018, OI-58)
# --------------------------------------------------------------------------- #

BRIEF = {"title": "Vnímání značky", "goal": "Co lidé o značce vědí", "sections": []}


def test_a_new_study_starts_empty_with_the_template_and_its_first_save_is_revision_one(
    lead: TestClient, viewer: TestClient, outsider: TestClient, world: Any
) -> None:
    url = f"{API}/studies/{world.study_id()}/workspace"
    frame = lead.get(url).json()
    assert frame["content_state"] == "EMPTY" and frame["can_edit"] is True
    assert frame["client_name"] == world.clients["primary"].name
    assert "unit_project_id" not in frame
    empty = lead.get(f"{url}/content").json()
    assert (empty["state"], empty["revision"], empty["content"]) == ("EMPTY", None, None)
    assert empty["template"]["title"] == "Nový výzkum" and empty["can_edit"] is True

    # ADR 0019: a member who was never granted the study opens it like anyone else.
    opened = outsider.get(f"{url}/content").json()
    assert opened["state"] == "EMPTY" and opened["can_edit"] is True
    assert lead.get(f"{url}/content").json()["state"] == "EMPTY"
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
    assert loaded["can_edit"] is True

    again = lead.put(
        f"{url}/content", json={"content": BRIEF, "analysis": {"x": 1}, "base_revision": 1}
    )
    assert again.json()["revision"] == 2
    history = lead.get(f"{url}/revisions").json()["items"]
    assert [r["revision"] for r in history] == [2, 1]

    by_viewer = viewer.put(
        f"{url}/content", json={"content": {**BRIEF, "goal": "G"}, "base_revision": 2}
    )
    assert by_viewer.status_code == 200 and by_viewer.json()["revision"] == 3

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


def test_a_studys_workspace_is_that_studys_alone_whoever_opens_it(
    lead: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    """ADR 0019: another client's lead may open and edit this study; its content stays its own."""
    url = f"{API}/studies/{world.study_id()}/workspace"
    lead.put(f"{url}/content", json={"content": BRIEF})
    for method, path in (("get", ""), ("get", "/content"), ("get", "/revisions")):
        r = getattr(other_client_lead, method)(f"{url}{path}")
        assert r.status_code == 200, (method, path)
    seen = other_client_lead.get(f"{url}/content").json()
    assert (seen["state"], seen["content"]) == ("NATIVE", BRIEF)
    edited = other_client_lead.put(
        f"{url}/content", json={"content": {**BRIEF, "goal": "G"}, "base_revision": 1}
    )
    assert edited.status_code == 200 and edited.json()["revision"] == 2
    # Their own client's study is untouched and empty: content never moves between studies.
    theirs = other_client_lead.get(
        f"{API}/studies/{world.study_id('other_client')}/workspace/content"
    ).json()
    assert theirs["state"] == "EMPTY"
    sibling = lead.get(f"{API}/studies/{world.study_id('sibling')}/workspace/content").json()
    assert sibling["state"] == "EMPTY"


def test_the_unit_binding_route_is_gone(lead: TestClient, world: Any) -> None:
    """ADR 0018: nothing binds a study to an 18.6.6 project any more."""
    r = lead.put(f"{API}/studies/{world.study_id()}/workspace", json={"unit_project_id": "PRJ-1"})
    assert r.status_code == 405


# --------------------------------------------------------------------------- #
# The brief's attachments (ADR 0018): AIA's storage, served only through the study
# --------------------------------------------------------------------------- #


def test_a_file_is_attached_in_aia_and_downloaded_only_through_its_study(
    lead: TestClient,
    viewer: TestClient,
    outsider: TestClient,
    other_client_lead: TestClient,
    world: Any,
) -> None:
    url = f"{API}/studies/{world.study_id()}/workspace"
    body = {
        "filename": "Zadání.txt",
        "data_b64": base64.b64encode("Fiktivní zadání".encode()).decode(),
    }
    unsaved = lead.post(f"{url}/attachments", json=body)
    assert unsaved.status_code == 409 and unsaved.json()["code"] == "not_saved"

    lead.put(f"{url}/content", json={"content": BRIEF})
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
    # ADR 0019: a member who was never granted the study downloads it like anyone else.
    assert outsider.get(f"{url}/attachments/{record['attachment_id']}").status_code == 200
    by_viewer = viewer.post(
        f"{url}/attachments",
        json={"filename": "Doplněk.txt", "data_b64": base64.b64encode(b"Dalsi soubor").decode()},
    )
    assert by_viewer.status_code == 201
    assert by_viewer.json()["attachment_id"] != record["attachment_id"]

    # Served only through its own study: the same attachment id under a sibling study's path,
    # whoever asks, is not found.
    sibling = f"{API}/studies/{world.study_id('sibling')}/workspace"
    assert lead.get(f"{sibling}/attachments/{record['attachment_id']}").status_code == 404
    assert (
        other_client_lead.get(f"{sibling}/attachments/{record['attachment_id']}").status_code == 404
    )
    # Another client's lead may open this study (ADR 0019) and attach to it.
    assert other_client_lead.post(f"{url}/attachments", json=body).status_code == 201
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
    lead: TestClient, viewer: TestClient, outsider: TestClient, world: Any
) -> None:
    url = f"{API}/studies/{world.study_id()}/workspace"
    body = {
        "filename": "dotaznik.csv",
        "data_b64": base64.b64encode(QUESTIONNAIRE_CSV.encode()).decode(),
    }
    # ADR 0019: the "viewer" label and a member who was never granted the study may import.
    assert outsider.post(f"{url}/questionnaire-import", json=body).status_code == 200
    assert viewer.post(f"{url}/questionnaire-import", json=body).status_code == 200
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
    # Any member reads it, another client's lead included (ADR 0019).
    assert other_client_lead.get(url).status_code == 200


# --------------------------------------------------------------------------- #
# Folders and labels (client-workspace C3)
# --------------------------------------------------------------------------- #


def test_a_person_files_the_clients_knowledge_in_folders_and_labels(
    researcher: TestClient, world: Any
) -> None:
    base = f"{API}/clients/{world.client_id()}/knowledge"
    for title in ("Výroční zpráva 2025", "Hlavní konkurenti"):
        researcher.post(f"{base}/proposals", json={"kind": "SOURCE", "title": title})
    items = researcher.get(base).json()
    assert all(i["folder_id"] is None and i["label_ids"] == [] for i in items)
    a, b = sorted(i["item_id"] for i in items)

    folder = researcher.post(f"{base}/folders", json={"name": " Minulé  výzkumy "})
    assert folder.status_code == 201, folder.text
    folder_id = folder.json()["folder_id"]
    assert folder.json() == {"folder_id": folder_id, "name": "Minulé výzkumy", "item_count": 0}
    taken = researcher.post(f"{base}/folders", json={"name": "minulé výzkumy"})
    assert taken.status_code == 409 and taken.json()["code"] == "name_taken"
    label = researcher.post(f"{base}/labels", json={"name": "2025", "colour": "BLUE"}).json()
    assert researcher.post(f"{base}/labels", json={"name": "x", "colour": "RED"}).status_code == 422

    placed = researcher.put(
        f"{base}/placement",
        json={"item_ids": [a, b], "folder_id": folder_id, "add_labels": [label["label_id"]]},
    )
    assert placed.status_code == 200, placed.text
    assert {(i["folder_id"], tuple(i["label_ids"])) for i in placed.json()} == {
        (folder_id, (label["label_id"],))
    }
    # Filing is not a change to the knowledge: no new revision.
    assert len(researcher.get(f"{base}/items/{a}/revisions").json()) == 1
    assert researcher.get(f"{base}/folders").json()[0]["item_count"] == 2

    # Left out, the folder is kept; null takes the item out of it.
    researcher.put(
        f"{base}/placement", json={"item_ids": [a], "remove_labels": [label["label_id"]]}
    )
    researcher.put(f"{base}/placement", json={"item_ids": [b], "folder_id": None})
    by_folder = researcher.get(base, params={"folder": folder_id}).json()
    assert [i["item_id"] for i in by_folder] == [a]
    assert [i["item_id"] for i in researcher.get(base, params={"folder": "unfiled"}).json()] == [b]
    labelled = researcher.get(base, params={"label": label["label_id"]}).json()
    assert [i["item_id"] for i in labelled] == [b]

    renamed = researcher.put(f"{base}/folders/{folder_id}", json={"name": "Archiv"})
    assert renamed.status_code == 200 and renamed.json()["name"] == "Archiv"
    recoloured = researcher.put(
        f"{base}/labels/{label['label_id']}", json={"colour": "TEAL"}
    ).json()
    assert recoloured["colour"] == "TEAL" and recoloured["name"] == "2025"
    assert researcher.delete(f"{base}/folders/{folder_id}").status_code == 204
    assert researcher.delete(f"{base}/labels/{label['label_id']}").status_code == 204
    assert all(i["folder_id"] is None and i["label_ids"] == [] for i in researcher.get(base).json())
    assert researcher.delete(f"{base}/folders/{folder_id}").status_code == 404


def test_filing_never_crosses_clients_and_is_all_or_nothing(
    researcher: TestClient, world: Any
) -> None:
    mine = f"{API}/clients/{world.client_id()}/knowledge"
    theirs = f"{API}/clients/{world.client_id('other')}/knowledge"
    researcher.post(f"{mine}/proposals", json={"kind": "FACT", "title": "Acme"})
    researcher.post(f"{theirs}/proposals", json={"kind": "FACT", "title": "Globex"})
    [a] = researcher.get(mine).json()
    [g] = researcher.get(theirs).json()
    my_folder = researcher.post(f"{mine}/folders", json={"name": "Moje"}).json()["folder_id"]
    their_folder = researcher.post(f"{theirs}/folders", json={"name": "Moje"}).json()["folder_id"]

    for body in (
        {"item_ids": [a["item_id"], g["item_id"]], "folder_id": my_folder},
        {"item_ids": [a["item_id"]], "folder_id": their_folder},
    ):
        assert researcher.put(f"{mine}/placement", json=body).status_code == 404
    assert researcher.get(mine).json()[0]["folder_id"] is None
    # Another client's folder is not found under this client's path.
    assert researcher.put(f"{mine}/folders/{their_folder}", json={"name": "x"}).status_code == 404
    assert researcher.get(mine, params={"folder": their_folder}).json() == []
    assert [f["folder_id"] for f in researcher.get(f"{theirs}/folders").json()] == [their_folder]
    # Shape is checked before anything is read.
    assert researcher.put(f"{mine}/placement", json={"item_ids": []}).status_code == 422
    assert researcher.put(f"{mine}/placement", json={"item_ids": ["nope"]}).status_code == 422


# --------------------------------------------------------------------------- #
# The client's profile and contacts (client-workspace C5)
# --------------------------------------------------------------------------- #


def test_a_member_fills_in_the_clients_profile_and_its_history_says_what_changed(
    researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    url = f"{API}/clients/{world.client_id()}/profile"
    empty = researcher.get(url).json()
    assert {k: empty[k] for k in ("short_code", "industry", "market", "description")} == {
        "short_code": "",
        "industry": "",
        "market": "",
        "description": "",
    }
    assert empty["contacts"] == [] and empty["history"] == []
    saved = researcher.put(
        url, json={"short_code": " AC ", "industry": "Automotive", "market": "Česko"}
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert (body["short_code"], body["industry"], body["description"]) == ("AC", "Automotive", "")
    assert body["history"][0]["action"] == "CLIENT_PROFILE_CHANGED"
    assert set(body["history"][0]["fields"]) == {"short_code", "industry", "market"}
    too_long = researcher.put(url, json={"short_code": "x" * 30})
    assert too_long.status_code == 422 and too_long.json()["code"] == "invalid_profile"
    # Another client's profile is its own.
    theirs = other_client_lead.get(f"{API}/clients/{world.client_id('other')}/profile").json()
    assert theirs["industry"] == ""


def test_a_member_sets_the_clients_own_budget_and_the_directory_does_not_carry_it(
    researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    """client-budget CB1: work on the client itself has a budget of its own, 0 until set."""
    url = f"{API}/clients/{world.client_id()}/budget"
    assert researcher.get(url).json() == {
        "budget_usd": 0.0,
        "spent_usd": 0.0,
        "reserved_usd": 0.0,
        "available_usd": 0.0,
    }
    saved = researcher.put(url, json={"budget_usd": 12.5})
    assert saved.status_code == 200, saved.text
    assert saved.json()["available_usd"] == 12.5
    for bad in ({"budget_usd": -1}, {"budget_usd": 2_000_000}, {"budget_usd": 5, "spent_usd": 1}):
        assert researcher.put(url, json=bad).status_code == 422
    # Costs stay behind their own route: the client's detail does not carry them.
    detail = researcher.get(f"{API}/clients/{world.client_id()}").json()
    assert "budget_usd" not in detail and "spent_usd" not in detail
    # Another client's budget is its own, and a client that does not exist is not found.
    theirs = other_client_lead.get(f"{API}/clients/{world.client_id('other')}/budget").json()
    assert theirs["budget_usd"] == 0.0
    assert researcher.get(f"{API}/clients/CLI-0000000000ffff/budget").status_code == 404


def test_contacts_are_kept_per_client_and_checked(researcher: TestClient, world: Any) -> None:
    base = f"{API}/clients/{world.client_id()}/contacts"
    added = researcher.post(
        base, json={"name": "Jana Nová", "email": "jana@klient.cz", "receives_reports": True}
    )
    assert added.status_code == 201, added.text
    contact = added.json()
    assert researcher.post(base, json={"name": "x", "email": "nope"}).status_code == 422
    changed = researcher.put(
        f"{base}/{contact['contact_id']}", json={"name": "Jana Nová", "role": "Insights"}
    ).json()
    assert (changed["role"], changed["email"], changed["receives_reports"]) == (
        "Insights",
        "",
        False,
    )
    other = f"{API}/clients/{world.client_id('other')}/contacts/{contact['contact_id']}"
    assert researcher.delete(other).status_code == 404
    profile = researcher.get(f"{API}/clients/{world.client_id()}/profile").json()
    assert [c["name"] for c in profile["contacts"]] == ["Jana Nová"]
    assert "jana@klient.cz" not in str(profile["history"])
    assert researcher.delete(f"{base}/{contact['contact_id']}").status_code == 204
    assert researcher.get(f"{API}/clients/{world.client_id()}/profile").json()["contacts"] == []


def test_the_client_says_whether_a_proposer_may_accept_their_own_proposal(
    owner: TestClient, researcher: TestClient, world: Any
) -> None:
    url = f"{API}/clients/{world.client_id()}"
    before = researcher.get(url).json()
    assert before["self_approval_allowed"] is True and before["self_approval_source"] == "default"
    owner.put(f"{API}/self-approval", json={"allowed": False, "client_id": world.client_id()})
    after = researcher.get(url).json()
    assert after["self_approval_allowed"] is False and after["self_approval_source"] == "client"
