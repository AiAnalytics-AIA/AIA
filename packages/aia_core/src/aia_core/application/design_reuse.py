"""Reuse a past study's design in a new or empty study of the same client (project memory M3c).

A person on the past-research page chooses one Design Revision of a past research study and
starts a study from it. Scope comes first, from the one issuer, for both studies:

- the client is the one the route names (``ScopeResolver.client_context``);
- the source is read only under its own ``StudyContext``, and must be of that client: a study
  of another client, or another organization's, is not found, exactly like an unknown one;
- the target is a new research study of the client (``create_study_in_client``) or one of its
  existing research studies under its own ``StudyContext``.

The target must be empty -- no working content and no Design Revision (owner, 2026-10-12):
nothing anyone has written is replaced. Then, in the caller's one transaction, the source's
content (its SHA-256 checked against the revision) becomes the target's working content, its
first Design Revision (``source_stage = memory``), and its citation, with the labels derived
from every run of the source revision. Nothing of the source is written and none of its data
is copied: a reused design is design input only, never evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..domain.design import DesignRevision
from ..domain.design_reuse import (
    REUSE_SOURCE_STAGE,
    DesignSource,
    SourceRun,
    derive_source_labels,
)
from ..domain.pipeline import fingerprint
from ..domain.scope import ScopeDenied, Study, StudyContext, StudyKind
from ..domain.workflow import StepRunStatus
from ..infrastructure.artifact_repository import ArtifactNotFound
from ..infrastructure.scope_repository import ScopeRepository
from ..infrastructure.storage import ArtifactStore
from ..infrastructure.study_design_repository import StudyDesignRepository
from ..infrastructure.study_workspace_repository import StudyWorkspaceRepository
from .research import ResearchRuns, research_artifacts
from .scope import AuthenticatedPrincipal, ScopeResolver

__all__ = ["ReuseRefused", "ReusedDesign", "reuse_design", "source_runs"]

#: The working-content save reason of a reused design.
REUSE_SAVE_REASON = "reuse"

#: Every run of the source revision is read; a revision is run a handful of times.
_RUN_LIMIT = 100


class ReuseRefused(Exception):
    """The design cannot be reused into that study; ``reason`` names why."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class ReusedDesign:
    """The study a design now starts, its first Design Revision and its citation."""

    study_id: str
    created_study: bool
    revision: DesignRevision
    source: DesignSource


def _not_found() -> ScopeDenied:
    return ScopeDenied("not found", reason="unknown_study")


def source_runs(
    session: Session, scope: StudyContext, store: ArtifactStore, revision_id: str
) -> list[SourceRun]:
    """What every run of one of the Study's Design Revisions says, oldest first.

    Read through the Study's own runs and its research artifacts, the only readers of
    either. A report that cannot be read is a report no person approved.
    """
    runs = ResearchRuns(session, scope)
    artifacts = research_artifacts(session, scope, store)
    found: list[SourceRun] = []
    for summary in reversed(runs.runs(limit=_RUN_LIMIT)):
        if (summary.get("metadata") or {}).get("design_revision_id") != revision_id:
            continue
        run = runs.get(str(summary["run_id"]))
        meta = run.get("metadata") or {}
        origins: list[str] = []
        produced = False
        report_id: str | None = None
        approved = False
        for step in run["steps"]:
            output: dict[str, Any] = step.get("output") or {}
            origin = output.get("data_origin")
            if origin and str(origin) not in origins:
                origins.append(str(origin))
            if step["node_key"] == "run" and output.get("artifact_id"):
                produced = True
            if (
                step["node_key"] == "report"
                and step["status"] is StepRunStatus.SUCCEEDED
                and output.get("artifact_id")
            ):
                report_id = str(output["artifact_id"])
                try:
                    approved = artifacts.get(report_id).is_approved
                except ArtifactNotFound:
                    approved = False
        found.append(
            SourceRun(
                run_id=str(run["run_id"]),
                fieldwork_source=str(meta["fieldwork_source"])
                if meta.get("fieldwork_source")
                else None,
                data_origins=tuple(origins),
                produced_data=produced,
                report_artifact_id=report_id,
                report_approved=approved,
            )
        )
    return found


def reuse_design(
    session: Session,
    resolver: ScopeResolver,
    principal: AuthenticatedPrincipal,
    store: ArtifactStore,
    *,
    client_id: str,
    source_study_id: str,
    source_revision_id: str,
    target_study_id: str | None = None,
    new_study: tuple[str, str] | None = None,
) -> ReusedDesign:
    """Start ``target_study_id``, or a new study ``new_study = (slug, name)``, from a past design.

    Raises ``ScopeDenied`` for anything outside the client the person can see,
    ``DesignRevisionNotFound`` for a revision that is not the source's, and
    :class:`ReuseRefused` for a target that is not an empty research study. The caller commits.
    """
    if (target_study_id is None) == (new_study is None):
        raise ValueError("name either an existing target study or a new one, not both")
    client = resolver.client_context(principal, client_id=client_id)

    source_scope = resolver.study_context(principal, study_id=source_study_id)
    if source_scope.client_id != client.client_id:
        raise _not_found()
    source_designs = StudyDesignRepository(session, source_scope)
    revision = source_designs.get(source_revision_id)
    content = source_designs.content(revision.revision_id)
    if fingerprint(content) != revision.content_sha256:  # pragma: no cover - immutable rows
        raise ReuseRefused("the source revision does not match its hash", reason="source_corrupt")
    labels = derive_source_labels(source_runs(session, source_scope, store, revision.revision_id))

    created = False
    if new_study is not None:
        slug, name = new_study
        study: Study = ScopeRepository(session).create_study_in_client(
            client, slug=slug, name=name, kind=StudyKind.RESEARCH
        )
        session.flush()
        target_study_id = study.study_id
        created = True
    assert target_study_id is not None
    if target_study_id == source_study_id:
        raise ReuseRefused("a study cannot start from its own design", reason="target_is_source")
    target = resolver.study_context(principal, study_id=target_study_id)
    if target.client_id != client.client_id:
        raise _not_found()

    if ScopeRepository(session).get_study(target).kind is not StudyKind.RESEARCH:
        raise ReuseRefused("only a research study has a research design", reason="not_research")
    target_designs = StudyDesignRepository(session, target)
    workspaces = StudyWorkspaceRepository(session)
    state = workspaces.state(target)
    if state.has_content or not state.editable or target_designs.latest() is not None:
        raise ReuseRefused(
            "the study already has a design or working content", reason="target_not_empty"
        )

    workspaces.save(target, content=content, base_revision=None, reason=REUSE_SAVE_REASON)
    first, _ = target_designs.submit(content=content, source_stage=REUSE_SOURCE_STAGE)
    cited = target_designs.record_source(
        revision_id=first.revision_id,
        source_study_id=source_scope.study_id,
        source_revision_id=revision.revision_id,
        source_revision=revision.revision,
        source_content_sha256=revision.content_sha256,
        labels=labels,
    )
    return ReusedDesign(
        study_id=target.study_id, created_study=created, revision=first, source=cited
    )
