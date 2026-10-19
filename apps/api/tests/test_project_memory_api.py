"""``GET /clients/{client_id}/memory/search``: one client's past studies (project memory M1c).

Through the real API over the two-client world: a designed study is found on its design, a
draft-only one says draft, a dimension is found by its Czech title, the sibling client's study
saying the same words is absent, and another organization's client -- and an unknown one --
is a 404. Nobody unauthenticated searches.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.scope_repository import ScopeRepository
from fastapi import FastAPI

API = "/api/v1"

#: A fictional design in the research document's shape.
DESIGN: dict[str, Any] = {
    "title": "",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
    "n": 450,
    "research_plan": {"research_questions": ["Kdo pije kávu ráno?"]},
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]}
            ],
        }
    ],
}


def submit(c: Any, world: Any, content: Any, study: str = "primary") -> Any:
    return world.design(c, content, study=study)


def _design(title: str, dimensions: list[str] | None = None) -> dict[str, Any]:
    content = copy.deepcopy(DESIGN)
    content["title"] = title
    content["persona_dimensions"] = {"approved": dimensions or []}
    return content


def _search(c: Any, world: Any, q: str, client: str = "primary") -> Any:
    return c.get(f"{API}/clients/{world.client_id(client)}/memory/search", params={"q": q})


@pytest.fixture
def memory(world: Any, lead: Any, other_client_lead: Any) -> Any:
    assert submit(lead, world, _design("Ranní káva", ["zdravi"])).status_code == 201
    draft = {"content": _design("Kávové ceny"), "base_revision": None}
    saved = lead.put(f"{API}/studies/{world.study_id('sibling')}/workspace/content", json=draft)
    assert saved.status_code == 200, saved.text
    theirs = submit(other_client_lead, world, _design("Ranní káva u Globexu"), study="other_client")
    assert theirs.status_code == 201
    return world


def test_a_designed_study_is_found_on_its_design(memory: Any, lead: Any) -> None:
    response = _search(lead, memory, "ranní káva")
    assert response.status_code == 200
    by_id = {h["study_id"]: h for h in response.json()}
    primary = by_id[memory.study_id("primary")]
    assert (primary["source"], primary["design_revision"]) == ("design", 1)
    assert primary["matches"][0] == {"field": "title", "texts": ["Ranní káva"]}


def test_a_draft_says_draft(memory: Any, lead: Any) -> None:
    by_id = {h["study_id"]: h for h in _search(lead, memory, "kávové ceny").json()}
    assert by_id[memory.study_id("sibling")]["source"] == "draft"


def test_a_dimension_is_found_by_its_czech_title(memory: Any, lead: Any) -> None:
    hits = _search(lead, memory, "Zdraví").json()
    assert [h["study_id"] for h in hits] == [memory.study_id("primary")]
    assert hits[0]["matches"][-1] == {"field": "dimensions", "texts": ["Zdraví"]}


def test_the_sibling_clients_matching_study_is_absent(memory: Any, lead: Any) -> None:
    found = {h["study_id"] for h in _search(lead, memory, "ranní káva").json()}
    assert memory.study_id("primary") in found
    assert memory.study_id("other_client") not in found


def test_another_organizations_client_is_404(app: FastAPI, memory: Any, lead: Any) -> None:
    with create_session_factory(app.state.engine)() as session:
        repo = ScopeRepository(session)
        org, owner = repo.create_organization(
            slug="elsewhere", name="Elsewhere", owner_email="owner@elsewhere.test", owner_name="O"
        )
        admin = ScopeResolver(session).organization_context(
            AuthenticatedPrincipal(user_id=owner.user_id, organization_id=org.organization_id)
        )
        theirs = repo.create_client(admin, slug="theirs", name="Their client")
        session.commit()
    response = lead.get(f"{API}/clients/{theirs.client_id}/memory/search", params={"q": "káva"})
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    unknown = lead.get(f"{API}/clients/CLI-0000000000/memory/search", params={"q": "káva"})
    assert unknown.status_code == 404


def test_a_short_query_is_refused_and_nobody_unauthenticated_searches(
    memory: Any, lead: Any, client: Any
) -> None:
    assert _search(lead, memory, "k").status_code == 422
    assert _search(client, memory, "káva").status_code == 401
