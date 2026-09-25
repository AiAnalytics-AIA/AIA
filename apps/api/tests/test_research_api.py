"""Research execution over HTTP (ADR 0016): Design Revisions, then the runs that execute them.

Every route is under the Study and resolves it first. The browser supplies the
design's content and nothing else: a revision or run of another Study, or of
another client, is a 404; a missing permission inside a visible Study is a 403.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

API = "/api/v1"

DESIGN = {
    "title": "Ranní nápoj",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
    "sections": [{"type": "questions", "questions": [{"id": "q1", "typ": "skala"}]}],
    "n": 450,
}


def submit(c: TestClient, world: Any, content: Any = None, study: str = "primary") -> Any:
    return c.post(
        f"{API}/studies/{world.study_id(study)}/design/revisions",
        json={"content": DESIGN if content is None else content, "source_stage": "run"},
    )


# --------------------------------------------------------------------------- #
# Design Revisions
# --------------------------------------------------------------------------- #


def test_a_design_becomes_an_immutable_revision_and_resubmitting_it_changes_nothing(
    researcher: TestClient, viewer: TestClient, world: Any
) -> None:
    first = submit(researcher, world)
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["created"] is True and body["revision"] == 1
    assert body["study_id"] == world.study_id() and body["revision_id"].startswith("REV-")
    same = submit(researcher, world)
    assert same.status_code == 200 and same.json()["revision_id"] == body["revision_id"]
    edited = submit(researcher, world, {**DESIGN, "n": 500})
    assert edited.status_code == 201 and edited.json()["parent_revision"] == 1
    # Anyone who can see the Study reads its revisions; the content is exactly what ran.
    got = viewer.get(f"{API}/studies/{world.study_id()}/design/revisions/{body['revision_id']}")
    assert got.status_code == 200 and got.json()["content"] == DESIGN
    listed = viewer.get(f"{API}/studies/{world.study_id()}/design/revisions").json()["items"]
    assert [r["revision"] for r in listed] == [2, 1]


def test_submitting_needs_edit_rights_and_says_why_it_refuses(
    viewer: TestClient, reviewer: TestClient, lead: TestClient, world: Any
) -> None:
    for c in (viewer, reviewer):
        refused = submit(c, world)
        assert refused.status_code == 403 and refused.json()["code"] == "insufficient_role"
    bad = submit(lead, world, {**DESIGN, "client_id": world.client_id("other")})
    assert bad.status_code == 422 and bad.json()["code"] == "design_carries_scope"
    assert submit(lead, world, []).status_code == 422
    extra = lead.post(
        f"{API}/studies/{world.study_id()}/design/revisions",
        json={"content": DESIGN, "source_stage": "run", "client_id": world.client_id()},
    )
    assert extra.status_code == 422


def test_a_design_never_crosses_studies_or_clients(
    lead: TestClient, other_client_lead: TestClient, outsider: TestClient, world: Any
) -> None:
    acme = submit(lead, world).json()["revision_id"]
    # Each study has a design of its own, so only the Study filter can refuse Acme's id.
    assert submit(other_client_lead, world, study="other_client").status_code == 201
    assert submit(lead, world, {**DESIGN, "n": 1}, study="sibling").status_code == 201
    # Another client's lead: Acme's study is invisible; Acme's revision id means nothing in theirs.
    assert submit(other_client_lead, world).status_code == 404
    assert (
        other_client_lead.get(f"{API}/studies/{world.study_id()}/design/revisions").status_code
        == 404
    )
    assert (
        other_client_lead.get(
            f"{API}/studies/{world.study_id('other_client')}/design/revisions/{acme}"
        ).status_code
        == 404
    )
    # The sibling study of the same client does not have it either.
    assert (
        lead.get(f"{API}/studies/{world.study_id('sibling')}/design/revisions/{acme}").status_code
        == 404
    )
    assert outsider.get(f"{API}/studies/{world.study_id()}/design/revisions").status_code == 404
    # A malformed id is refused before any lookup.
    assert lead.get(f"{API}/studies/{world.study_id()}/design/revisions/PRJ-1").status_code == 422
