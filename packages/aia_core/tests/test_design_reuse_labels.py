"""The labels a reused design carries (plans/project-memory-reuse.md M3a).

One conservative rule over every run of the source revision: any fictional source or origin
makes it synthetic, any unapproved report makes it draft, no run makes it never run, and data
with no origin stamped is unlabelled -- never "measured".
"""

from __future__ import annotations

from aia_core.domain.design_reuse import SourceRun, derive_source_labels


def test_a_never_run_source_says_so_and_nothing_else() -> None:
    labels = derive_source_labels([])
    assert (labels.never_run, labels.synthetic, labels.draft, labels.unlabelled_data) == (
        True,
        False,
        False,
        False,
    )
    assert (labels.run_ids, labels.report_artifact_ids) == ((), ())


def test_any_fictional_run_makes_the_source_synthetic() -> None:
    fixture = SourceRun(run_id="RUN-1", fieldwork_source="synthetic_fixture")
    ai = SourceRun(
        run_id="RUN-2",
        fieldwork_source="ai_runtime",
        data_origins=("SYNTHETIC_AI_FICTIONAL",),
        produced_data=True,
    )
    parked = SourceRun(run_id="RUN-3", fieldwork_source="ai_runtime")
    assert derive_source_labels([fixture]).synthetic
    assert derive_source_labels([parked, ai]).synthetic
    assert not derive_source_labels([parked]).synthetic


def test_any_unapproved_report_makes_it_draft_and_every_report_is_recorded() -> None:
    approved = SourceRun(
        run_id="RUN-1",
        fieldwork_source="ai_runtime",
        report_artifact_id="ART-a",
        report_approved=True,
    )
    draft = SourceRun(run_id="RUN-2", fieldwork_source="ai_runtime", report_artifact_id="ART-b")
    assert not derive_source_labels([approved]).draft
    labels = derive_source_labels([approved, draft])
    assert labels.draft
    assert labels.run_ids == ("RUN-1", "RUN-2")
    assert labels.report_artifact_ids == ("ART-a", "ART-b")


def test_data_without_an_origin_is_unlabelled_never_measured() -> None:
    blank = SourceRun(run_id="RUN-1", fieldwork_source="ai_runtime", produced_data=True)
    odd = SourceRun(
        run_id="RUN-2", fieldwork_source="ai_runtime", data_origins=("PANEL",), produced_data=True
    )
    assert derive_source_labels([blank]).unlabelled_data
    assert derive_source_labels([odd]).unlabelled_data
    assert not derive_source_labels([blank]).synthetic
