"""Deleting a client over HTTP (settings-backends SB5)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

API = "/api/v1"


def _delete(client: TestClient, client_id: str, token: str) -> Any:
    return client.request("DELETE", f"{API}/clients/{client_id}", json={"confirm_token": token})


def test_preview_then_delete_then_already_deleted(owner: TestClient, world: Any) -> None:
    client_id = world.client_id("other")
    preview = owner.post(f"{API}/clients/{client_id}/deletion")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["name"] == "Globex Inc" and body["deleted"]["studies"] == 1
    assert set(body["kept"]) == {"usage_rows", "approval_rows", "audit_rows"}
    # Said, never shown as deleted: what stays until the stores can delete it (SDL2).
    assert body["remains_until_sdl2"] == {
        "population_children": 0,
        "replaced_source_readings": None,
    }
    # Nothing of the client is running: nothing holds the deletion back.
    assert body["active_run_ids"] == []
    done = _delete(owner, client_id, body["confirm_token"])
    assert done.status_code == 200, done.text
    assert done.json()["already_deleted"] is False and done.json()["deleted"]["studies"] == 1
    assert done.json()["objects_failed"] == 0
    again = _delete(owner, client_id, body["confirm_token"])
    assert again.status_code == 200 and again.json()["already_deleted"] is True
    # Gone from the listing and from reading; another client is untouched.
    listed = [c["client_id"] for c in owner.get(f"{API}/clients").json()]
    assert client_id not in listed and world.client_id("primary") in listed
    assert owner.post(f"{API}/clients/{client_id}/deletion").status_code == 404


def test_a_confirmation_must_be_this_persons_for_this_client(
    owner: TestClient, as_user: Any, world: Any
) -> None:
    other = world.client_id("other")
    token = owner.post(f"{API}/clients/{other}/deletion").json()["confirm_token"]
    wrong_client = _delete(owner, world.client_id("primary"), token)
    assert wrong_client.status_code == 409
    assert wrong_client.json()["code"] == "confirmation_invalid"
    owner.post(f"{API}/members", json={"email": "lead@art-chain.io", "role": "ADMIN"})
    admin: TestClient = as_user("lead")
    assert _delete(admin, other, token).status_code == 409
    assert _delete(owner, other, "forged").json()["code"] == "confirmation_invalid"


def test_only_an_administrator_deletes_or_reads_what_is_kept(
    researcher: TestClient, world: Any
) -> None:
    assert researcher.post(f"{API}/clients/{world.client_id()}/deletion").status_code == 403
    assert researcher.get(f"{API}/settings/kept-records").status_code == 403
    assert _delete(researcher, world.client_id(), "x").status_code == 403


def test_kept_records_list_what_a_deletion_keeps(owner: TestClient) -> None:
    rows = owner.get(f"{API}/settings/kept-records").json()
    assert [r["record"] for r in rows] == [
        "usage_rows",
        "budget_holds",
        "approval_rows",
        "audit_rows",
        "deleted_clients",
    ]
    assert {r["kept_for"] for r in rows} == {"indefinite"}


DESIGN = {
    "title": "Ranní nápoj",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
    "n": 60,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]}
            ],
        }
    ],
}


def test_the_preview_names_the_runs_that_hold_the_deletion_back(
    owner: TestClient, world: Any
) -> None:
    """A run of the client that has not ended is named in the preview, before the person
    confirms (settings-redesign F22), and the deletion itself still refuses while it runs."""
    made = world.design(owner, DESIGN)
    assert made.status_code in (200, 201), made.text
    started = owner.post(
        f"{API}/studies/{world.study_id()}/research/runs",
        json={"design_revision_id": made.json()["revision_id"]},
    )
    assert started.status_code == 201, started.text
    run_id = str(started.json()["run_id"])
    client_id = world.client_id("primary")
    body = owner.post(f"{API}/clients/{client_id}/deletion").json()
    assert body["active_run_ids"] == [run_id]
    refused = _delete(owner, client_id, body["confirm_token"])
    assert refused.status_code == 409
    assert refused.json()["code"] == "client_has_active_work"
    assert refused.json()["details"]["run_ids"] == [run_id]
    # Another client's preview names none of it.
    other = owner.post(f"{API}/clients/{world.client_id('other')}/deletion").json()
    assert other["active_run_ids"] == []


def test_the_preview_is_a_post_it_issues_a_confirmation(owner: TestClient, world: Any) -> None:
    assert owner.get(f"{API}/clients/{world.client_id('other')}/deletion").status_code == 405
