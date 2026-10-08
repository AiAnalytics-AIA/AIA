"""The cited works' standing, asked by the merge step (plan chunk 46).

Every web source a track kept names its own DOI when its page's metadata does
(``SourceFactsRecord.doi``). Before it merges, the merge step asks the scholarly indexes
the composition gave (Crossref, OpenAlex) about each distinct DOI once per run, through
the gate -- classified, journaled, metered like every other call -- and stores each answer
as it returns (``WorkStandingRecord``), so a merge that runs again reads what it asked
and never asks twice. A lookup an earlier attempt left in flight is not sent again: that
DOI's standing is unknown.

Asked outside any transaction, a lookup at a time: the merge's own transaction opens only
after the last one returned.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Final

from aia_core.application.web_retrieval import RetrievalGate
from aia_core.domain.deep_research.contracts import digest
from aia_core.domain.deep_research.datasets import DatasetQuery
from aia_core.domain.deep_research.steps import PlanRecord, WorkStandingRecord, run_scoped
from aia_core.domain.deep_research.works import WorkNotice, WorkStatusRecord, resolve_status
from aia_core.domain.residency import DataClass
from aia_core.infrastructure.artifact_repository import ArtifactRepository
from aia_core.infrastructure.dataset_crossref import CROSSREF_CONNECTOR_ID, crossref_notices
from aia_core.infrastructure.dataset_openalex import OPENALEX_CONNECTOR_ID, openalex_retracted
from aia_worker.executor import StepContext, StepInput
from sqlalchemy.orm import Session

from ._shared import _class_a_texts
from .runtime import DeepResearchRuntime, StepToolMeter

__all__ = ["MAX_WORK_LOOKUPS", "STANDING_CONNECTORS", "work_standings"]

#: The indexes a standing is asked of, in the order they are asked.
STANDING_CONNECTORS: Final = (CROSSREF_CONNECTOR_ID, OPENALEX_CONNECTOR_ID)
#: Distinct DOIs one run asks about, at most; the rest stay unasked (``None``), in order.
MAX_WORK_LOOKUPS: Final = 40

_Repo = Callable[[Session], ArtifactRepository]


def _journal_id(doi: str) -> str:
    """The id a DOI's lookups are journaled under: one per DOI, short, stable."""
    return "WRK-" + hashlib.sha256(doi.encode("utf-8")).hexdigest()[:20]


def work_standings(
    *,
    context: StepContext,
    step: StepInput,
    runtime: DeepResearchRuntime,
    plan: PlanRecord,
    dois: Sequence[str],
    repo: _Repo,
    put: Callable[[ArtifactRepository, WorkStandingRecord, str], None],
    find: Callable[[ArtifactRepository, str], WorkStandingRecord | None],
    clock: Callable[[], datetime],
) -> dict[str, WorkStatusRecord]:
    """Each DOI's standing, asked once per run of the indexes the composition gave.

    ``{}`` when the composition gave none of them (nobody was asked, and nothing is said).
    """
    if runtime.retrieval is None:
        return {}
    asked_of = [
        c
        for c in STANDING_CONNECTORS
        if any(d.connector.connector_id == c for d in runtime.datasets)
    ]
    if not asked_of:
        return {}
    meter = StepToolMeter.resuming(context, clock=runtime.clock)
    gate = RetrievalGate(
        retrieval=runtime.retrieval,
        scope=context.scope,
        meter=meter,
        client_terms=plan.request.client_terms,
        class_a_texts=_class_a_texts(plan.request),
        clock=runtime.clock,
        datasets=runtime.datasets,
    )
    standings: dict[str, WorkStatusRecord] = {}
    for doi in sorted(set(dois))[:MAX_WORK_LOOKUPS]:
        key = run_scoped(step.run_id, digest({"kind": "work_standing", "doi": doi}))
        with context.transaction() as (session, _workflow):
            stored = find(repo(session), key)
        if stored is not None:
            standings[doi] = stored.standing
            continue
        journal = _journal_id(doi)
        answers: dict[str, tuple[WorkNotice, ...] | None] = {}
        flags: dict[str, bool | None] = {}
        in_flight = bool(meter.dispatched_earlier(journal))
        for connector in asked_of:
            if in_flight:
                # An earlier attempt sent a lookup with no answer on record: it may have
                # been served, so nothing is sent again and the standing stays unknown.
                answers[connector] = None
                continue
            outcome = gate.dataset(
                DatasetQuery(connector_id=connector, dataset_id=f"doi:{doi}"),
                context_class=DataClass.CLASS_C_INTERNAL,
                track_id=journal,
            )
            table = (
                outcome.snapshot.dataset
                if outcome.snapshot is not None and not outcome.uncertain
                else None
            )
            if connector == CROSSREF_CONNECTOR_ID:
                answers[connector] = crossref_notices(table) if table is not None else None
            else:
                flags[connector] = openalex_retracted(table) if table is not None else None
        standing = resolve_status(doi, answers, retracted_flags=flags, checked_at=clock())
        record = WorkStandingRecord(kind="deep_research_work_standing", doi=doi, standing=standing)
        with context.transaction() as (session, _workflow):
            put(repo(session), record, key)
        standings[doi] = standing
    return standings
