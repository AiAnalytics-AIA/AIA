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


def test_the_preview_is_a_post_it_issues_a_confirmation(owner: TestClient, world: Any) -> None:
    assert owner.get(f"{API}/clients/{world.client_id('other')}/deletion").status_code == 405
