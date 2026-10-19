"""A source a researcher checked, added to the client's knowledge from a Deep Research run.

Plan ``inline-decisions`` chunk 1 (the product owner, 2026-10-19). Deep Research captures sources
and models propose findings from them; neither ever writes knowledge (ADR 0017, ADR 0019). A
researcher who opened a captured source and checked it adds it with one click, "Ověřeno, přidat
zdroj": that click is a person's write, so the source is knowledge at once (ADR 0019 decision 3)
through :meth:`ClientKnowledgeRepository.add_source_once`.

Nothing the browser sends becomes the item. The run is found through the Study, its sealed
bundle read and verified (:meth:`DeepResearchRuns.bundle`), and the snapshot and the accepted
finding citing it must both be in that bundle; the URL, title, quote and hash are the bundle's.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

from sqlalchemy.orm import Session

from ..domain.scope import ClientContext, Permission, ScopeDenied, StudyContext
from ..infrastructure.client_knowledge_repository import ClientKnowledgeRepository, SourceAdded
from ..infrastructure.storage import ArtifactStore
from .deep_research import DeepResearchRuns

__all__ = ["SourceAdded", "SourceNotInRun", "add_verified_source"]

#: The item's title is bounded by its column.
_TITLE_MAX: Final = 255


class SourceNotInRun(LookupError):
    """The run's sealed bundle holds no such snapshot, or no accepted finding citing it."""

    reason = "source_not_in_run"


@dataclass(frozen=True, slots=True)
class VerifiedSource:
    """What the click did (:class:`SourceAdded`), with the URL and title it was for."""

    added: SourceAdded
    url: str
    title: str


def add_verified_source(
    session: Session,
    study: StudyContext,
    client: ClientContext,
    *,
    run_id: str,
    snapshot_id: str,
    evidence_id: str,
    store: ArtifactStore,
) -> VerifiedSource:
    """Add the source ``snapshot_id`` of the Study's Deep Research run ``run_id`` to the
    Study's client's knowledge, as the person in ``client`` who checked it.

    Needs ``EDIT_STUDY`` on the Study (to read the run's evidence) and the client's knowledge
    permissions (to write). ``client`` must be the Study's own client. The click is made on
    the Study, so the Study's self-approval rule holds as well as the client's: where either
    turns it off, the source is filed as a proposal another person decides. Raises
    :class:`SourceNotInRun` when the snapshot is not in the run's sealed bundle, or no accepted
    finding with ``evidence_id`` cites it; a run of another Study is not found.
    """
    study.require(Permission.EDIT_STUDY)
    if (client.organization_id, client.client_id) != (study.organization_id, study.client_id):
        raise ScopeDenied("the source goes to the study's own client", reason="forged_scope")
    bundle = DeepResearchRuns(session, study).bundle(run_id, store=store)
    snapshot = next((s for s in bundle.snapshots if s.snapshot_id == snapshot_id), None)
    finding = next(
        (
            a.evidence
            for a in bundle.accepted
            if a.evidence.evidence_id == evidence_id and a.evidence.source_ref == snapshot_id
        ),
        None,
    )
    if snapshot is None or finding is None or not snapshot.url:
        raise SourceNotInRun(snapshot_id)
    title = (snapshot.title.strip() or snapshot.url)[:_TITLE_MAX]
    if not study.self_approval.allowed:
        # Narrowed, never widened: the client's context carries its own rule, which a Study
        # that turned self-approval off must not be able to get around from its own screen.
        client = replace(client, self_approval=study.self_approval)
    added = ClientKnowledgeRepository(session).add_source_once(
        client,
        url=snapshot.url,
        title=title,
        summary=finding.quote,
        content={
            "final_url": snapshot.final_url,
            "title": snapshot.title,
            "quote": finding.quote,
            "snapshot_id": snapshot.snapshot_id,
            "text_sha256": snapshot.text_sha256,
            "retrieved_at": snapshot.retrieved_at.isoformat(),
        },
        provenance={
            "deep_research_run_id": run_id,
            "evidence_id": finding.evidence_id,
            "snapshot_id": snapshot.snapshot_id,
            "study_id": study.study_id,
            "added_by": client.actor_id,
            "verified_by_person": True,
            "note": f"added by {client.actor_id} after checking",
        },
    )
    return VerifiedSource(added=added, url=snapshot.url, title=title)
