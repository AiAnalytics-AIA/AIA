"""Project memory's search: one client's past studies, matched on their designs (M1b).

``search_client_studies`` answers which studies of one client say what a person searched for,
and why. Scope comes first, from the one issuer:

- the client is the one the route names, resolved through ``ScopeResolver.client_context``.
  A client the person cannot see is ``ScopeDenied``, which the route answers as a 404.
- every study searched is one of that client's (``ClientContext.study_ids``), and its design
  is read only under its own ``StudyContext`` from ``ScopeResolver.study_context``. So a
  sibling client's study is never read, let alone returned.

What a study is searched on (owner, 2026-10-12):

- its latest Design Revision (``design``, with the revision number);
- else, for a study with no Design Revision, its working content (``draft``), which is never
  called a design;
- else its name alone (``name``).

The client's own dimension titles come from its knowledge, read once under the
``ClientContext``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy.orm import Session

from ..domain.knowledge import KnowledgeKind
from ..domain.project_memory import FieldMatch, match, query_words, study_text
from ..domain.scope import ScopeDenied, StudyKind, StudyStatus
from ..infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from ..infrastructure.scope_repository import ScopeRepository
from ..infrastructure.study_design_repository import StudyDesignRepository
from ..infrastructure.study_workspace_repository import StudyWorkspaceRepository
from .scope import AuthenticatedPrincipal, ScopeResolver

__all__ = [
    "MIN_QUERY_LENGTH",
    "MemoryHit",
    "MemorySource",
    "search_client_studies",
]

#: A shorter query matches almost everything and says nothing.
MIN_QUERY_LENGTH = 2


class MemorySource(StrEnum):
    """What a study was searched on."""

    #: Its latest Design Revision.
    DESIGN = "design"
    #: Its working content: the study has no Design Revision yet. Never a design.
    DRAFT = "draft"
    #: Its name alone: neither a design nor working content.
    NAME = "name"


@dataclass(frozen=True, slots=True)
class MemoryHit:
    """One past study of the client that says what was searched for."""

    study_id: str
    name: str
    kind: StudyKind
    status: StudyStatus
    modified_at: datetime | None
    source: MemorySource
    #: The Design Revision searched, for ``source == DESIGN``; otherwise ``None``.
    design_revision: int | None
    matches: tuple[FieldMatch, ...]


def search_client_studies(
    session: Session,
    resolver: ScopeResolver,
    principal: AuthenticatedPrincipal,
    *,
    client_id: str,
    query: str,
) -> list[MemoryHit]:
    """The studies of ``client_id`` matching ``query``, newest first.

    Raises ``ScopeDenied`` for a client the principal cannot see, and ``ValueError`` for a
    query with fewer than :data:`MIN_QUERY_LENGTH` characters.
    """
    if len(query.strip()) < MIN_QUERY_LENGTH:
        raise ValueError(f"a search needs at least {MIN_QUERY_LENGTH} characters")
    words = query_words(query)
    client = resolver.client_context(principal, client_id=client_id)
    dimension_titles = {
        item.item_id: item.title
        for item in ClientKnowledgeRepository(session).items(
            client, kinds=(KnowledgeKind.DIMENSION,)
        )
    }
    workspaces = StudyWorkspaceRepository(session)
    hits: list[MemoryHit] = []
    for study in ScopeRepository(session).studies_in_client(client):
        try:
            scope = resolver.study_context(principal, study_id=study.study_id)
        except ScopeDenied:
            continue  # gone or closed since the client was resolved: not this person's to read
        if scope.client_id != client.client_id:  # pragma: no cover - the study row names it
            continue
        source, revision, content = MemorySource.NAME, None, None
        latest = StudyDesignRepository(session, scope).latest()
        if latest is not None:
            source, revision = MemorySource.DESIGN, latest.revision
            content = StudyDesignRepository(session, scope).content(latest.revision_id)
        else:
            working = workspaces.content(scope)
            if working.content:
                source, content = MemorySource.DRAFT, working.content
        found = match(
            words, study_text(study.name, content, client_dimension_titles=dimension_titles)
        )
        if found is None:
            continue
        hits.append(
            MemoryHit(
                study_id=study.study_id,
                name=study.name,
                kind=study.kind,
                status=study.status,
                modified_at=study.modified_at,
                source=source,
                design_revision=revision,
                matches=found,
            )
        )
    return hits
