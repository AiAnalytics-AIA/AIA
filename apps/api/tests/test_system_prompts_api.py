"""System prompts over HTTP: an administrator's act, audited, never a member's (ADR 0020)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

API = "/api/v1"
PROMPTS = f"{API}/system-prompts"
CRITIQUE = "aia.research.critique_design"
BUILD = "aia.research.build_questionnaire"


def _save(owner: TestClient, text: str = "Zkritizuj návrh.", prompt: str = CRITIQUE) -> Any:
    return owner.post(f"{PROMPTS}/{prompt}/versions", json={"text": text, "note": "test"})


# ------------------------------------------------------------------ who may


def test_unauthenticated_is_refused(client: TestClient) -> None:
    assert client.get(PROMPTS).status_code == 401


@pytest.mark.parametrize("who", ["lead", "researcher", "reviewer", "viewer", "outsider"])
def test_a_member_cannot_read_or_change_prompts(who: str, as_user: Any) -> None:
    member: TestClient = as_user(who)
    assert member.get(PROMPTS).status_code == 403
    assert member.get(f"{PROMPTS}/{CRITIQUE}").status_code == 403
    assert member.post(f"{PROMPTS}/{CRITIQUE}/versions", json={"text": "x"}).status_code == 403
    assert (
        member.put(f"{PROMPTS}/{CRITIQUE}/active", json={"version_number": None}).status_code == 403
    )


# ------------------------------------------------------------------ reading


def test_the_list_names_every_prompt_and_which_ones_an_edit_reaches(owner: TestClient) -> None:
    rows = owner.get(PROMPTS).json()
    by_id = {r["prompt_id"]: r for r in rows}
    wired = sorted(i for i, r in by_id.items() if r["wired"])
    assert wired == sorted(
        f"aia.research.{a}"
        for a in (
            "analyze_brief",
            "build_questionnaire",
            "optimize_questionnaire",
            "propose_audience",
            "suggest_dimensions",
            "critique_design",
            "design_copilot",
            "answer_memory",
        )
    )
    for row in rows:
        assert row["active"]["origin"] == "baseline"
        assert row["version_count"] == 0 and row["latest_number"] is None
    respondent = by_id["aia.respondent.block"]
    assert not respondent["wired"] and respondent["unwired_reason"] == "feeds_a_reuse_fingerprint"
    assert "baseline_text" not in respondent  # the list stays light; text is in the detail


def test_the_detail_shows_the_frame_the_code_adds_and_the_limit(owner: TestClient) -> None:
    detail = owner.get(f"{PROMPTS}/{BUILD}").json()
    assert detail["fixed_prefix"].startswith("Jsi výzkumný pracovník AIA")
    assert "{object}" in detail["baseline_text"]
    assert detail["required_literals"] == ["{object}"]
    assert detail["max_chars"] == 12000
    assert detail["versions"] == [] and detail["history"] == []


def test_an_unknown_prompt_is_not_found(owner: TestClient) -> None:
    assert owner.get(f"{PROMPTS}/aia.nope").status_code == 404
    assert _save(owner, prompt="aia.nope").status_code == 404


# ------------------------------------------------------------------ writing


def test_saving_makes_a_version_that_does_not_run(owner: TestClient) -> None:
    saved = _save(owner, "  Moje kritika.  ")
    assert saved.status_code == 201
    body = saved.json()
    assert (body["version_number"], body["label"], body["text"]) == (1, "e1", "Moje kritika.")
    assert len(body["text_sha256"]) == 64
    row = next(r for r in owner.get(PROMPTS).json() if r["prompt_id"] == CRITIQUE)
    assert row["version_count"] == 1 and row["active"]["origin"] == "baseline"


@pytest.mark.parametrize(
    ("prompt", "text", "code", "status"),
    [
        pytest.param(CRITIQUE, "   ", "empty", 422, id="empty"),
        pytest.param(CRITIQUE, "x" * 12001, "too_long", 422, id="too_long"),
        pytest.param(BUILD, "Bez zástupného znaku.", "missing_required_text", 422, id="no_object"),
        pytest.param("aia.respondent.block", "Jiný.", "not_editable", 409, id="unwired"),
    ],
)
def test_an_edit_that_cannot_run_is_refused_and_says_why(
    owner: TestClient, prompt: str, text: str, code: str, status: int
) -> None:
    refused = _save(owner, text, prompt)
    assert refused.status_code == status
    assert refused.json()["code"] == code


def test_the_request_is_closed(owner: TestClient) -> None:
    extra = owner.post(f"{PROMPTS}/{CRITIQUE}/versions", json={"text": "x", "client_id": "c"})
    assert extra.status_code == 422


# ------------------------------------------------------------------ activating


def test_by_default_the_author_puts_their_own_version_live(owner: TestClient) -> None:
    """No approval between people (ADR 0019): the default is that the person who wrote it may."""
    _save(owner)
    live = owner.put(
        f"{PROMPTS}/{CRITIQUE}/active", json={"version_number": 1, "reason": "lepší formulace"}
    )
    assert live.status_code == 200
    assert (live.json()["origin"], live.json()["label"], live.json()["reason"]) == (
        "stored",
        "e1",
        "lepší formulace",
    )
    detail = owner.get(f"{PROMPTS}/{CRITIQUE}").json()
    assert detail["active"]["label"] == "e1"
    assert [h["label"] for h in detail["history"]] == ["e1"]


def test_when_the_organization_requires_independent_review_the_author_cannot(
    owner: TestClient,
) -> None:
    assert owner.put(f"{API}/self-approval", json={"allowed": False}).status_code == 200
    _save(owner)
    refused = owner.put(f"{PROMPTS}/{CRITIQUE}/active", json={"version_number": 1})
    assert refused.status_code == 403
    assert refused.json()["code"] == "self_activation_not_allowed"
    assert owner.get(f"{PROMPTS}/{CRITIQUE}").json()["active"]["origin"] == "baseline"

    # Turning review off again is the organization's own act, and then it goes through.
    assert owner.put(f"{API}/self-approval", json={"allowed": True}).status_code == 200
    assert owner.put(f"{PROMPTS}/{CRITIQUE}/active", json={"version_number": 1}).status_code == 200


def test_returning_to_the_codes_wording_is_one_call_and_is_recorded(owner: TestClient) -> None:
    _save(owner)
    owner.put(f"{PROMPTS}/{CRITIQUE}/active", json={"version_number": 1})
    back = owner.put(
        f"{PROMPTS}/{CRITIQUE}/active", json={"version_number": None, "reason": "horší"}
    )
    assert back.status_code == 200 and back.json()["origin"] == "baseline"
    history = owner.get(f"{PROMPTS}/{CRITIQUE}").json()["history"]
    assert [(h["label"], h["reason"]) for h in history] == [(None, "horší"), ("e1", "")]


def test_activating_a_missing_version_is_not_found(owner: TestClient) -> None:
    missing = owner.put(f"{PROMPTS}/{CRITIQUE}/active", json={"version_number": 3})
    assert missing.status_code == 404
    assert missing.json()["code"] == "unknown_version"
    assert owner.put(f"{PROMPTS}/{CRITIQUE}/active", json={"version_number": 0}).status_code == 422


def test_every_change_is_in_the_access_audit(owner: TestClient) -> None:
    _save(owner)
    owner.put(f"{PROMPTS}/{CRITIQUE}/active", json={"version_number": 1, "reason": "proč"})
    owner.put(f"{PROMPTS}/{CRITIQUE}/active", json={"version_number": None})
    actions = [e["action"] for e in owner.get(f"{API}/access-audit").json()]
    for expected in ("PROMPT_VERSION_CREATED", "PROMPT_ACTIVATED", "PROMPT_RESET_TO_BASELINE"):
        assert expected in actions


# ------------------------------------------------------------------ testing a draft


def test_only_an_administrator_may_ask_a_job_to_run_a_draft(
    owner: TestClient, researcher: TestClient, world: Any
) -> None:
    _save(owner)
    rev = researcher.post(
        f"{API}/studies/{world.study_id()}/design/revisions",
        json={"content": {"title": "Fictional", "goal": "Test concept"}, "source_stage": "brief"},
    ).json()["revision_id"]
    refused = researcher.post(
        f"{API}/studies/{world.study_id()}/research/agent-jobs",
        json={"design_revision_id": rev, "action": "critique_design", "prompt_version": 1},
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "prompt_test_requires_administrator"
    # An ordinary job records that the code's wording ran.
    ordinary = researcher.post(
        f"{API}/studies/{world.study_id()}/research/agent-jobs",
        json={"design_revision_id": rev, "action": "critique_design"},
    )
    assert ordinary.status_code == 201, ordinary.text
    assert (ordinary.json()["prompt_version"], ordinary.json()["prompt_origin"]) == (
        "1",
        "baseline",
    )
