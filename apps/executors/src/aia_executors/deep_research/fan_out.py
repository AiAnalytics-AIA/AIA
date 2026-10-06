"""What a fanned-out ``investigate`` hands to a track's own step, and the run's shared cache.

Plan ``deep-research-web-search.md`` chunk 21; ``docs/architecture/deep-research-fan-out.md``
§ 2. With ``DeepResearchConfig.fan_out`` the join (``InvestigateExecutor``) returns every
track that would make a call as a child step of the run (``Deferred``), and runs again once
they all succeeded; the child (``InvestigateTrackExecutor``) researches its one track with
the code the sequential step uses. This module holds the two things they share:

* :class:`TrackStepPayload` -- the child's input: the track, and for a lead-planned task
  its brief and budget. Written by the join under its lease; the child re-checks it
  against the run's plan before anything is sent.
* :class:`StoredRunSnapshotCache` -- the run's snapshot cache (chunk 5: a URL captured
  once in a run is not fetched again) across the run's track steps: a kept page is
  indexed in the store under its canonical URL, and another track step asking for it is
  answered from the stored snapshot. Not a lock: two steps asking at one instant may both
  fetch, and the duplicate capture dedupes by content address.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aia_core.application.web_retrieval import RunSnapshotCache
from aia_core.domain.deep_research.contracts import ResearchTrack, digest
from aia_core.domain.deep_research.investigator import Allowance
from aia_core.domain.deep_research.legacy import canonical_url
from aia_core.domain.deep_research.steps import (
    PlannedTrack,
    SnapshotArtifact,
    UrlCaptureRecord,
    run_scoped,
)
from aia_core.domain.deep_research.workflow import (
    ARTIFACT_TYPES,
    INVESTIGATE_TRACK_KIND,
    track_step_key,
)
from aia_core.infrastructure.web_retrieval import FetchedPage
from aia_worker.executor import ChildStep, StepContext, StepInput
from pydantic import BaseModel, ConfigDict

from .lead import LeadTask

if TYPE_CHECKING:
    from ._shared import _Step

__all__ = ["LeadTaskPayload", "StoredRunSnapshotCache", "TrackStepPayload", "track_child"]

#: A track's step may retry a transient failure, as the ``investigate`` step it came from.
_TRACK_ATTEMPTS = 3


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LeadTaskPayload(_Closed):
    """A lead-planned task's brief and budget, as its track step receives them."""

    planned: PlannedTrack
    turns: int
    searches: int
    opens: int
    assignment: dict[str, Any]

    @classmethod
    def of(cls, task: LeadTask) -> LeadTaskPayload:
        return cls(
            planned=task.planned,
            turns=task.allowance.turns,
            searches=task.allowance.searches,
            opens=task.allowance.opens,
            assignment=dict(task.assignment),
        )

    def task(self) -> LeadTask:
        return LeadTask(
            planned=self.planned,
            allowance=Allowance(turns=self.turns, searches=self.searches, opens=self.opens),
            assignment=dict(self.assignment),
        )


class TrackStepPayload(_Closed):
    """One track handed out to a step of its own."""

    track: ResearchTrack
    lead: LeadTaskPayload | None = None


def track_child(step: StepInput, track: ResearchTrack, lead: LeadTask | None) -> ChildStep:
    """The child step ``track`` is handed out as: keyed by its id, fingerprinted by it."""
    return ChildStep(
        node_key=track_step_key(track.track_id),
        kind=INVESTIGATE_TRACK_KIND,
        payload=TrackStepPayload(
            track=track, lead=LeadTaskPayload.of(lead) if lead is not None else None
        ).model_dump(mode="json"),
        input_fingerprint=track.fingerprint,
        stage_type=step.stage_type,
        artifact_target=ARTIFACT_TYPES["track"],
        max_attempts=_TRACK_ATTEMPTS,
    )


class StoredRunSnapshotCache(RunSnapshotCache):
    """The run's cache, held in this process and indexed in the store for its other steps.

    ``get`` asks this process first, then the run's index; ``put`` keeps the page here and
    indexes its requested and final URL. Both run on the step's thread (the gate begins
    and finishes every fetch there), each in a short fenced transaction.
    """

    def __init__(self, executor: _Step, context: StepContext, step: StepInput) -> None:
        super().__init__()
        self._executor = executor
        self._context = context
        self._step = step

    def _index_key(self, url: str) -> str:
        return run_scoped(self._step.run_id, digest(["url_capture", canonical_url(url) or url]))

    def get(self, url: str) -> FetchedPage | None:
        held = super().get(url)
        if held is not None:
            return held
        executor, step = self._executor, self._step
        with self._context.transaction() as (session, _workflow):
            repo = executor._repo(session, self._context)
            index = executor._find(repo, step, "url_capture", self._index_key(url))
            if index is None:
                return None
            record = executor._read(repo, index.artifact_id, UrlCaptureRecord)
            snapshot = executor._find(repo, step, "snapshot", record.snapshot_id)
            if snapshot is None:
                # Indexed by a step that has not stored the page yet: fetched here.
                return None
            stored = executor._read(repo, snapshot.artifact_id, SnapshotArtifact)
        page = FetchedPage(snapshot=stored.snapshot, published=stored.published)
        super().put(url, page)
        return page

    def put(self, url: str, page: FetchedPage) -> None:
        super().put(url, page)
        executor, step = self._executor, self._step
        with self._context.transaction() as (session, _workflow):
            repo = executor._repo(session, self._context)
            for each in dict.fromkeys((url, page.snapshot.final_url)):
                executor._put(
                    repo,
                    step,
                    payload=UrlCaptureRecord(
                        kind="deep_research_url_capture",
                        url=each,
                        snapshot_id=page.snapshot.snapshot_id,
                    ),
                    kind="url_capture",
                    key=self._index_key(each),
                )
