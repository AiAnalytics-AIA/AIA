"""Deep Research settings over HTTP: read by a member, changed by an administrator (ADR 0022)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

API = "/api/v1"
SETTINGS = f"{API}/deep-research/settings"
RETENTION = "retention.snapshots"
CRAWL = "budgets.allowance.exhaustive.crawl_pages"


def _propose(owner: TestClient, key: str, value: Any, **extra: str) -> Any:
    return owner.post(f"{SETTINGS}/{key}/versions", json={"value": value, **extra})


# ------------------------------------------------------------------ who may


def test_unauthenticated_is_refused(client: TestClient) -> None:
    assert client.get(SETTINGS).status_code == 401


@pytest.mark.parametrize("who", ["lead", "researcher", "outsider"])
def test_a_member_reads_but_cannot_change(who: str, as_user: Any) -> None:
    member: TestClient = as_user(who)
    listed = member.get(SETTINGS)
    assert listed.status_code == 200 and listed.json()["may_administer"] is False
    assert member.get(f"{SETTINGS}/{RETENTION}").status_code == 200
    proposed = _propose(member, RETENTION, 90)
    assert proposed.status_code == 403 and proposed.json()["code"] == "insufficient_role"
    approval = member.put(f"{SETTINGS}/{RETENTION}/approval", json={"version_number": None})
    assert approval.status_code == 403


# ------------------------------------------------------------------ reading


def test_the_overview_lists_every_setting_at_its_proposed_default(owner: TestClient) -> None:
    body = owner.get(SETTINGS).json()
    assert body["may_administer"] is True
    assert body["catalogue_version"] == "aia-dr-settings-catalogue-1"
    by_key = {s["key"]: s for s in body["settings"]}
    crawl = by_key[CRAWL]
    assert (crawl["value"], crawl["default"], crawl["origin"]) == (1000, 1000, "proposed_default")
    assert crawl["lower_only"] and crawl["method"] and not crawl["required_for_live"]
    price = by_key["provider.search.price_per_1000"]
    assert price["value"] is None and price["required_for_live"] is True
    assert by_key["extraction.denylist"]["value"] == []
    assert RETENTION in body["missing_for_live"]
    assert not any("key" in k.split(".")[-1] for k in by_key)


def test_an_unknown_setting_is_404(owner: TestClient) -> None:
    assert owner.get(f"{SETTINGS}/provider.search.nothing").status_code == 404
    assert _propose(owner, "provider.search.nothing", 1).status_code == 404


# ------------------------------------------------------------------ changing


def test_propose_then_approve_puts_a_value_in_force_and_withdraw_returns_the_default(
    owner: TestClient,
) -> None:
    made = _propose(owner, RETENTION, 90, source_url="https://example.org/retention")
    assert made.status_code == 201, made.text
    assert made.json()["version_number"] == 1 and made.json()["value"] == 90
    # Proposed is not in force.
    assert owner.get(f"{SETTINGS}/{RETENTION}").json()["origin"] == "proposed_default"

    approved = owner.put(
        f"{SETTINGS}/{RETENTION}/approval", json={"version_number": 1, "reason": "signed off"}
    )
    assert approved.status_code == 200, approved.text
    assert (approved.json()["value"], approved.json()["origin"]) == (90, "approved")
    assert RETENTION not in owner.get(SETTINGS).json()["missing_for_live"]

    withdrawn = owner.put(f"{SETTINGS}/{RETENTION}/approval", json={"version_number": None})
    assert withdrawn.json()["origin"] == "proposed_default"
    detail = owner.get(f"{SETTINGS}/{RETENTION}").json()
    assert [v["version_number"] for v in detail["versions"]] == [1]
    assert [h["version_number"] for h in detail["history"]] == [None, 1]


def test_a_list_round_trips_in_its_normal_form(owner: TestClient) -> None:
    made = _propose(owner, "extraction.denylist", ["Shop.Example", "a.example"])
    assert made.json()["value"] == ["a.example", "shop.example"]


@pytest.mark.parametrize(
    ("key", "value", "extra", "code"),
    [
        (CRAWL, 5000, {}, "setting_invalid"),
        (RETENTION, "ninety", {}, "setting_invalid"),
        (RETENTION, 90, {"source_url": "http://example.org"}, "source_invalid"),
        ("models.light.model_id", "anthropic.claude-haiku", {}, "setting_invalid"),
    ],
)
def test_a_wrong_value_is_422_with_its_reason(
    owner: TestClient, key: str, value: Any, extra: dict[str, str], code: str
) -> None:
    refused = _propose(owner, key, value, **extra)
    assert refused.status_code == 422 and refused.json()["code"] == code


def test_approving_an_unknown_version_is_404(owner: TestClient) -> None:
    refused = owner.put(f"{SETTINGS}/{RETENTION}/approval", json={"version_number": 9})
    assert refused.status_code == 404 and refused.json()["code"] == "unknown_version"
