"""What a readiness draft would change for the organization's studies (plan V1a2).

``Porovnat`` on the readiness area answers one question: which studies of the organization
would the draft limits let start, or stop, compared with the limits in force. It reads every
open research study the person may open, each under its own ``StudyContext`` from
``ScopeResolver.study_context``, never a study of another organization, and checks the content
a check would read next:

- its working content (``draft``), the design the researcher is editing;
- else its latest Design Revision (``design``);
- else nothing: the study is counted, not assessed.

Nothing is started, stopped or written: a study's verdict changes only when the person next
checks it, under the limits then in force.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..domain.research_design import ReadinessSpec, prepare
from ..domain.scope import ScopeDenied, StudyKind
from ..infrastructure.scope_repository import ScopeRepository
from ..infrastructure.study_design_repository import StudyDesignRepository
from ..infrastructure.study_workspace_repository import StudyWorkspaceRepository
from .scope import AuthenticatedPrincipal, ScopeResolver

__all__ = ["CheckMove", "ReadinessImpact", "StudyImpact", "readiness_impact"]


@dataclass(frozen=True, slots=True)
class CheckMove:
    """One readiness check whose status the draft moves; ``None``: the check is not made."""

    check_id: str
    in_force: str | None
    draft: str | None
    #: The check's words under the draft, else under the limits in force.
    message: str


@dataclass(frozen=True, slots=True)
class StudyImpact:
    study_id: str
    client_id: str
    client_name: str
    name: str
    #: ``draft`` (working content) or ``design`` (latest Design Revision).
    source: str
    n: int | None
    ready: tuple[bool, bool]  # [in force, draft]
    moves: tuple[CheckMove, ...]


@dataclass(frozen=True, slots=True)
class ReadinessImpact:
    #: Every assessed study whose verdict or any check the draft moves, verdict changes first.
    studies: tuple[StudyImpact, ...]
    #: Assessed studies the draft changes nothing for.
    unchanged: int
    #: Open research studies with nothing a check can read: no working content and no Design
    #: Revision, or a half-written draft the compiler cannot read.
    not_assessed: int


def _checks(
    content: Mapping[str, Any], limits: ReadinessSpec, pair_n_min: int, routing: bool
) -> Any:
    return prepare(dict(content), pair_n_min=pair_n_min, limits=limits, routing=routing)[1]


def _moves(before: Any, after: Any) -> tuple[CheckMove, ...]:
    old = {c.id: c for c in before.checks}
    new = {c.id: c for c in after.checks}
    moves = []
    for check_id in [*new, *(i for i in old if i not in new)]:
        a, b = old.get(check_id), new.get(check_id)
        status_a = a.status.value if a else None
        status_b = b.status.value if b else None
        if status_a == status_b:
            continue  # the same verdict, perhaps in other words: nothing moves
        shown = b or a
        assert shown is not None
        moves.append(CheckMove(check_id, status_a, status_b, shown.message))
    return tuple(moves)


def readiness_impact(
    session: Session,
    resolver: ScopeResolver,
    principal: AuthenticatedPrincipal,
    *,
    in_force: ReadinessSpec,
    draft: ReadinessSpec,
    pair_n_min: int,
    routing: bool = False,
) -> ReadinessImpact:
    """Every open research study the principal may open, checked under both sets of limits.

    ``pair_n_min`` is the Sociomap's, in force, and ``routing`` the deployment's
    ``AIA_ROUTING_ENABLED``: neither moves a verdict between the two, but the checks are the
    ones Kontrola a spuštění would show."""
    scopes = ScopeRepository(session)
    workspaces = StudyWorkspaceRepository(session)
    impacts: list[StudyImpact] = []
    unchanged = not_assessed = 0
    for client_id in resolver.accessible_clients(principal):
        try:
            client = resolver.client_context(principal, client_id=client_id)
        except ScopeDenied:
            continue
        client_name = scopes.get_client_in_scope(client).name
        for study in scopes.studies_in_client(client, kind=StudyKind.RESEARCH):
            if not study.status.accepts_work:
                continue
            try:
                scope = resolver.study_context(principal, study_id=study.study_id)
            except ScopeDenied:
                continue  # gone or closed since the client was resolved
            source, content = "draft", workspaces.content(scope).content
            if not content:
                designs = StudyDesignRepository(session, scope)
                latest = designs.latest()
                source = "design"
                content = designs.content(latest.revision_id) if latest is not None else None
            if not content:
                not_assessed += 1
                continue
            try:
                before = _checks(content, in_force, pair_n_min, routing)
                after = _checks(content, draft, pair_n_min, routing)
            except (TypeError, ValueError, AttributeError, KeyError):
                # A half-written draft the compiler cannot read: this study cannot be
                # assessed, and one such draft never stops the organization's comparison.
                not_assessed += 1
                continue
            moves = _moves(before, after)
            if not moves and before.ready == after.ready:
                unchanged += 1
                continue
            n = content.get("n")
            impacts.append(
                StudyImpact(
                    study_id=study.study_id,
                    client_id=client.client_id,
                    client_name=client_name,
                    name=study.name,
                    source=source,
                    n=n if isinstance(n, int) and not isinstance(n, bool) else None,
                    ready=(before.ready, after.ready),
                    moves=moves,
                )
            )
    impacts.sort(key=lambda s: (s.ready[0] == s.ready[1], s.client_name, s.name))
    return ReadinessImpact(tuple(impacts), unchanged, not_assessed)
