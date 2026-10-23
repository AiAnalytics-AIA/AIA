"""A client's rules over HTTP (settings-backends SB7)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

API = "/api/v1"


def test_a_member_reads_and_an_owner_sets_the_rules(
    owner: TestClient, researcher: TestClient, world: Any
) -> None:
    url = f"{API}/clients/{world.client_id()}/rules"
    fresh = researcher.get(url)
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["data_posture"] is None
    assert fresh.json()["effective_posture"] == "CLASSIFIED"
    set_ = owner.put(url, json={"data_posture": "OPEN", "wallet_ceiling_usd": 40})
    assert set_.status_code == 200, set_.text
    assert (set_.json()["effective_posture"], set_.json()["wallet_ceiling_usd"]) == ("OPEN", 40.0)
    assert set_.json()["set_by"] is not None and set_.json()["set_at"] is not None
    # Only what is sent changes; null clears.
    cleared = owner.put(url, json={"wallet_ceiling_usd": None}).json()
    assert (cleared["data_posture"], cleared["wallet_ceiling_usd"]) == ("OPEN", None)
    listed = {r["client_id"]: r for r in researcher.get(f"{API}/settings/client-rules").json()}
    assert listed[world.client_id()]["effective_posture"] == "OPEN"
    assert listed[world.client_id("other")]["effective_posture"] == "CLASSIFIED"


def test_a_researcher_cannot_set_them_and_a_wrong_value_is_refused(
    owner: TestClient, researcher: TestClient, world: Any
) -> None:
    url = f"{API}/clients/{world.client_id()}/rules"
    assert researcher.put(url, json={"data_posture": "OPEN"}).status_code == 403
    assert owner.put(url, json={"data_posture": "MAYBE"}).status_code == 422
    assert owner.put(url, json={"wallet_ceiling_usd": -1}).status_code == 422
    assert owner.get(f"{API}/clients/CLI-nobody/rules").status_code == 404
