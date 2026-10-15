"""``POST /clients/{client_id}/memory/reuse`` and ``GET /studies/{id}/design/source`` (M3d).

Through the real API over the two-client world: a past study's design starts a new study, whose
working content and first revision are the design and whose citation the study reads back; an
empty study of the client takes it; a study with content is a 409; a study of another client, as
target or as source, is a 404; a study that was not reused has no source.
"""

from __future__ import annotations

from typing import Any

API = "/api/v1"

DESIGN: dict[str, Any] = {
    "title": "Ranní káva",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
    "n": 450,
    "sections": [
        {
            "type": "questions",
            "questions": [{"id": "q1", "text": "Jak často?", "typ": "skala", "skala": [1, 5]}],
        }
    ],
}


def _submit(c: Any, world: Any, study: str = "primary") -> str:
    r = c.post(
        f"{API}/studies/{world.study_id(study)}/design/revisions",
        json={"content": DESIGN, "source_stage": "run"},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["revision_id"])


def _reuse(c: Any, world: Any, body: dict[str, Any], client: str = "primary") -> Any:
    return c.post(f"{API}/clients/{world.client_id(client)}/memory/reuse", json=body)


def test_a_past_design_starts_a_new_study_that_cites_it(world: Any, lead: Any) -> None:
    revision = _submit(lead, world)
    r = _reuse(
        lead,
        world,
        {
            "source_study_id": world.study_id("primary"),
            "source_revision_id": revision,
            "new_study_name": "Ranní káva znovu",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    target = body["study_id"]
    assert body["created_study"] and body["revision"]["source_stage"] == "memory"
    assert body["source"]["source_revision_id"] == revision
    assert body["source"]["labels"]["never_run"] is True
    content = lead.get(f"{API}/studies/{target}/workspace/content").json()["content"]
    assert content == DESIGN
    cited = lead.get(f"{API}/studies/{target}/design/source")
    assert cited.status_code == 200 and cited.json() == body["source"]
    assert lead.get(f"{API}/studies/{world.study_id('primary')}/design/source").status_code == 404


def test_an_empty_study_takes_it_and_one_with_content_is_a_409(world: Any, lead: Any) -> None:
    revision = _submit(lead, world)
    body = {
        "source_study_id": world.study_id("primary"),
        "source_revision_id": revision,
        "target_study_id": world.study_id("sibling"),
    }
    first = _reuse(lead, world, body)
    assert first.status_code == 201, first.text
    assert first.json()["created_study"] is False
    again = _reuse(lead, world, body)
    assert again.status_code == 409 and again.json()["code"] == "target_not_empty"


def test_nothing_crosses_the_client(world: Any, lead: Any, other_client_lead: Any) -> None:
    revision = _submit(lead, world)
    theirs = _submit(other_client_lead, world, study="other_client")
    as_target = _reuse(
        lead,
        world,
        {
            "source_study_id": world.study_id("primary"),
            "source_revision_id": revision,
            "target_study_id": world.study_id("other_client"),
        },
    )
    assert as_target.status_code == 404
    as_source = _reuse(
        lead,
        world,
        {
            "source_study_id": world.study_id("other_client"),
            "source_revision_id": theirs,
            "new_study_name": "Cizí",
        },
    )
    assert as_source.status_code == 404
    wrong_revision = _reuse(
        lead,
        world,
        {
            "source_study_id": world.study_id("primary"),
            "source_revision_id": theirs,
            "new_study_name": "Cizí revize",
        },
    )
    assert wrong_revision.status_code == 404


def test_one_target_is_named_and_nobody_unauthenticated_reuses(
    world: Any, lead: Any, client: Any
) -> None:
    revision = _submit(lead, world)
    both = _reuse(
        lead,
        world,
        {
            "source_study_id": world.study_id("primary"),
            "source_revision_id": revision,
            "target_study_id": world.study_id("sibling"),
            "new_study_name": "Obojí",
        },
    )
    assert both.status_code == 422 and both.json()["code"] == "target_required"
    anonymous = _reuse(
        client,
        world,
        {
            "source_study_id": world.study_id("primary"),
            "source_revision_id": revision,
            "new_study_name": "Anonym",
        },
    )
    assert anonymous.status_code == 401
