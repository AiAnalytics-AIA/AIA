"""Project memory's search, scoped to one client (plans/project-memory-reuse.md M1b).

Over the two-client world in ``conftest.py``: the primary client's study with a Design
Revision is found on that design, a study with only working content is found and labelled
a draft, a client dimension is found by its knowledge title, the sibling client's study
saying the same words is absent, and another organization's client is refused.
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.application.project_memory import (
    MemorySource,
    search_client_studies,
)
from aia_core.domain.knowledge import KnowledgeKind
from aia_core.domain.research_template import research_template
from aia_core.domain.scope import ScopeDenied
from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository


def _design(title: str, *, dimensions: tuple[str, ...] = ()) -> dict[str, Any]:
    content = research_template()
    content.update(title=title, goal="Zjistit, zda nový nápoj dává smysl dojíždějícím.")
    content["research_plan"]["research_questions"] = ["Kdo pije kávu ráno?"]
    content["persona_dimensions"] = {"approved": list(dimensions)}
    return content


@pytest.fixture
def world(session: Any, scoped: Any) -> Any:
    """Primary: a designed study and a draft-only one. Other client: the same words."""
    lead = scoped.principal(scoped.users["lead"])
    client = scoped.resolver.client_context(lead, client_id=scoped.clients["primary"].client_id)
    ClientKnowledgeRepository(session).add(
        client, kind=KnowledgeKind.DIMENSION, title="Ranní rituály", summary="fictional"
    )
    own = ClientKnowledgeRepository(session).items(client, kinds=(KnowledgeKind.DIMENSION,))
    own_id = own[0].item_id
    StudyDesignRepository(session, scoped.scope(study="primary")).submit_as_working_copy(
        content=_design("Ranní káva", dimensions=("zdravi", own_id)), source_stage="run"
    )
    StudyWorkspaceRepository(session).save(
        scoped.scope(study="sibling"), content=_design("Kávové ceny"), base_revision=None
    )
    StudyDesignRepository(
        session, scoped.scope(user="other_lead", study="other_client")
    ).submit_as_working_copy(content=_design("Ranní káva u Globexu"), source_stage="run")
    session.flush()
    return scoped


def _search(world: Any, session: Any, query: str, *, client: str = "primary") -> list[Any]:
    return search_client_studies(
        session,
        world.resolver,
        world.principal(world.users["lead"]),
        client_id=world.clients[client].client_id,
        query=query,
    )


def test_a_designed_study_is_found_on_its_design(world: Any, session: Any) -> None:
    hits = _search(world, session, "ranní káva")
    by_id = {h.study_id: h for h in hits}
    primary = by_id[world.studies["primary"].study_id]
    assert (primary.source, primary.design_revision) == (MemorySource.DESIGN, 1)
    assert [m.field for m in primary.matches][:2] == ["title", "research_questions"]


def test_a_study_with_only_working_content_is_found_as_a_draft(world: Any, session: Any) -> None:
    hits = {h.study_id: h for h in _search(world, session, "kávové ceny")}
    sibling = hits[world.studies["sibling"].study_id]
    assert (sibling.source, sibling.design_revision) == (MemorySource.DRAFT, None)


def test_a_dimension_is_found_by_its_czech_title_and_by_the_clients_own(
    world: Any, session: Any
) -> None:
    primary = world.studies["primary"].study_id
    for query in ("zdravi", "Zdraví", "rituály"):
        hits = _search(world, session, query)
        assert [h.study_id for h in hits] == [primary], query
        assert hits[0].matches[-1].field == "dimensions"


def test_the_sibling_clients_study_saying_the_same_is_never_returned(
    world: Any, session: Any
) -> None:
    other = world.studies["other_client"].study_id
    found = {h.study_id for h in _search(world, session, "ranní káva")}
    assert other not in found
    assert world.studies["primary"].study_id in found
    # From the other client's side, its own study is the one found, and nothing of primary.
    theirs = {h.study_id for h in _search(world, session, "ranní káva", client="other")}
    assert theirs == {other}


def test_a_study_with_nothing_but_its_name_is_found_by_name(world: Any, session: Any) -> None:
    other = world.studies["other_client"]
    hits = _search(world, session, "Globex brand", client="other")
    assert [(h.study_id, h.source) for h in hits] == [(other.study_id, MemorySource.DESIGN)]
    pricing = _search(world, session, "Acme pricing")
    assert [h.study_id for h in pricing] == [world.studies["sibling"].study_id]


def test_another_organizations_client_is_refused(world: Any, session: Any) -> None:
    org, owner = world.scope_repo.create_organization(
        slug="elsewhere", name="Elsewhere", owner_email="owner@elsewhere.test", owner_name="O"
    )
    from aia_core.application.scope import AuthenticatedPrincipal

    admin = world.resolver.organization_context(
        AuthenticatedPrincipal(user_id=owner.user_id, organization_id=org.organization_id)
    )
    theirs = world.scope_repo.create_client(admin, slug="theirs", name="Their client")
    session.flush()
    with pytest.raises(ScopeDenied):
        search_client_studies(
            session,
            world.resolver,
            world.principal(world.users["lead"]),
            client_id=theirs.client_id,
            query="káva",
        )


def test_a_query_under_two_characters_is_refused(world: Any, session: Any) -> None:
    with pytest.raises(ValueError, match="at least 2"):
        _search(world, session, " k ")
