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
    return owner.post(
        f"{PROMPTS}/{prompt}/versions",
        json={"text": text, "note": "test", "declares_no_client_data": True},
    )


# ------------------------------------------------------------------ who may


def test_unauthenticated_is_refused(client: TestClient) -> None:
    assert client.get(PROMPTS).status_code == 401


@pytest.mark.parametrize("who", ["lead", "researcher", "reviewer", "viewer", "outsider"])
def test_a_member_cannot_read_or_change_prompts(who: str, as_user: Any) -> None:
    member: TestClient = as_user(who)
    assert member.get(PROMPTS).status_code == 403
    assert member.get(f"{PROMPTS}/{CRITIQUE}").status_code == 403
    valid = {"text": "x", "declares_no_client_data": True}  # so the role, not the body, decides
    assert member.post(f"{PROMPTS}/{CRITIQUE}/versions", json=valid).status_code == 403
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
            # The Research Lead (ADR 0026): its own task wording, the same rails.
            "lead",
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


def _revision(client: TestClient, world: Any) -> str:
    return str(
        world.design(
            client, {"title": "Fictional", "goal": "Test concept"}, source_stage="brief"
        ).json()["revision_id"]
    )


def _start(client: TestClient, world: Any, rev: str, **extra: Any) -> Any:
    return client.post(
        f"{API}/studies/{world.study_id()}/research/agent-jobs",
        json={"design_revision_id": rev, "action": "critique_design", **extra},
    )


def test_a_job_runs_the_active_prompt_and_asking_for_a_version_is_refused(
    owner: TestClient, researcher: TestClient, world: Any, app: Any
) -> None:
    """D-15 (system-prompts-settings 14): no job runs a draft. A start naming a prompt version
    is refused by the request's shape (422), administrator or not, fictional client or not:
    no paid start outside the Lead stays reachable over HTTP."""
    _save(owner)
    rev = _revision(researcher, world)
    app.state.settings = app.state.settings.model_copy(
        update={"ai_fictional_client_ids": world.client_id("primary")}
    )
    for who in (owner, researcher):
        refused = _start(who, world, rev, prompt_version=1)
        assert refused.status_code == 422, refused.text
    # An ordinary job records that the code's wording ran: the stored draft was never activated.
    ordinary = _start(researcher, world, rev)
    assert ordinary.status_code == 201, ordinary.text
    assert (ordinary.json()["prompt_version"], ordinary.json()["prompt_origin"]) == (
        "2",
        "baseline",
    )


def test_the_detail_offers_no_draft_test_and_says_what_to_classify(
    owner: TestClient, world: Any, app: Any
) -> None:
    saved = _save(owner, "Zkritizuj návrh.").json()
    app.state.settings = app.state.settings.model_copy(
        update={"ai_fictional_client_ids": "CLI-b, CLI-a"}
    )
    detail = owner.get(f"{PROMPTS}/{CRITIQUE}").json()
    assert "draft_test_client_ids" not in detail  # D-15: nowhere a draft may be tried
    # The hash an operator lists to classify this exact text; it is not the text's plain hash.
    from aia_core.domain.ai_material import material_sha256

    version = detail["versions"][0]
    assert version["material_sha256"] == material_sha256("Zkritizuj návrh.")
    assert version["material_sha256"] != saved["text_sha256"]


# ------------------------------------------------------------------ the author's declaration


def test_saving_records_who_declared_the_text_holds_no_client_data(owner: TestClient) -> None:
    saved = _save(owner).json()
    assert saved["declared_class"] == "CLASS_C_INTERNAL"
    assert saved["declared_by"] and saved["declared_at"]
    listed = owner.get(f"{PROMPTS}/{CRITIQUE}").json()["versions"][0]
    assert (listed["declared_class"], listed["declared_by"]) == (
        "CLASS_C_INTERNAL",
        saved["declared_by"],
    )


def test_a_save_that_does_not_declare_is_refused(owner: TestClient) -> None:
    said_no = owner.post(
        f"{PROMPTS}/{CRITIQUE}/versions", json={"text": "Moje.", "declares_no_client_data": False}
    )
    assert said_no.status_code == 422 and said_no.json()["code"] == "declaration_required"
    # Omitting the field is not a quiet default for "yes": the request is invalid.
    omitted = owner.post(f"{PROMPTS}/{CRITIQUE}/versions", json={"text": "Moje."})
    assert omitted.status_code == 422
    assert owner.get(f"{PROMPTS}/{CRITIQUE}").json()["versions"] == []
