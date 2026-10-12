"""What a reused design carries from its source (plans/project-memory-reuse.md M3a).

A past study's design may start a new study of the same client. The new design cites its
source, and the source's labels go with it: a design whose runs answered fictional
respondents, or whose report was never approved, stays labelled that way where it is reused.

The labels are derived by one conservative rule, never picked: over every run executed of the
source Design Revision, the union of what they carry. They are recorded with the run and report
artifact ids they were derived from, so a later run of the source cannot change what was cited.
Unknown is never good: a run whose fieldwork produced data with no origin stamped is not
"measured", it is ``unlabelled_data``. Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Final

from pydantic import BaseModel, ConfigDict

from .fieldwork import NON_EVIDENCE_ORIGINS, FieldworkSource

__all__ = [
    "REUSE_SOURCE_STAGE",
    "DesignSource",
    "SourceLabels",
    "SourceRun",
    "derive_source_labels",
]

#: The ``source_stage`` of a Design Revision made by reusing a past design.
REUSE_SOURCE_STAGE: Final = "memory"

#: Every origin AIA stamps today is fictional and never evidence (``NON_EVIDENCE_ORIGINS``).
_FICTIONAL_ORIGINS: Final = frozenset(o.value for o in NON_EVIDENCE_ORIGINS)


class SourceRun(BaseModel):
    """What one run of the source revision says about its data and its report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    #: The run's fieldwork source, as it recorded it (``synthetic_fixture``, ``ai_runtime``).
    fieldwork_source: str | None
    #: The data origins its steps stamped; empty when no step produced data.
    data_origins: tuple[str, ...] = ()
    #: Whether its fieldwork step produced a dataset at all.
    produced_data: bool = False
    #: Its internal report artifact, when one was made, and whether a person approved it.
    report_artifact_id: str | None = None
    report_approved: bool = False


class SourceLabels(BaseModel):
    """The labels a reused design carries, and what they were derived from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Some run of the source answered fictional respondents: never evidence.
    synthetic: bool
    #: Some run's report is a draft no person approved.
    draft: bool
    #: The source revision was never run: nothing it found exists.
    never_run: bool
    #: Some run produced data with no origin stamped: not known to be anything.
    unlabelled_data: bool
    #: The runs and report artifacts the labels were derived from, in the order given.
    run_ids: tuple[str, ...]
    report_artifact_ids: tuple[str, ...]


def derive_source_labels(runs: Iterable[SourceRun]) -> SourceLabels:
    """The union of what every run of the source revision carries."""
    seen = list(runs)
    synthetic = any(
        r.fieldwork_source == FieldworkSource.SYNTHETIC_FIXTURE.value
        or any(o in _FICTIONAL_ORIGINS for o in r.data_origins)
        for r in seen
    )
    unlabelled = any(r.produced_data and not r.data_origins for r in seen) or any(
        o not in _FICTIONAL_ORIGINS for r in seen for o in r.data_origins
    )
    return SourceLabels(
        synthetic=synthetic,
        draft=any(r.report_artifact_id is not None and not r.report_approved for r in seen),
        never_run=not seen,
        unlabelled_data=unlabelled,
        run_ids=tuple(r.run_id for r in seen),
        report_artifact_ids=tuple(r.report_artifact_id for r in seen if r.report_artifact_id),
    )


class DesignSource(BaseModel):
    """Where a Study's design came from: its citation, recorded once when it was reused."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    study_id: str
    #: The Study's first Design Revision: the reused design itself.
    revision_id: str
    source_study_id: str
    source_revision_id: str
    source_revision: int
    source_content_sha256: str
    labels: SourceLabels
    created_by: str
    created_at: datetime
