"""A cited work's DOI and standing; a finding on a retracted work quarantined (chunk 46a)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest

from aia_core.domain.deep_research.contracts import (
    Channel,
    EvidenceItem,
    EvidenceType,
    QuarantineReason,
    RecommendedUse,
    RetrievalMode,
    SourceKind,
    evidence_id,
)
from aia_core.domain.deep_research.merge import (
    MERGE_RULES_VERSION,
    SourceFacts,
    TrackEvidence,
    merge_evidence,
)
from aia_core.domain.deep_research.sources import SOURCE_TABLE_V1
from aia_core.domain.deep_research.steps import SourceFactsRecord
from aia_core.domain.deep_research.works import (
    WORKS_VERSION,
    WorkNotice,
    WorkStatus,
    normalise_doi,
    resolve_status,
)
from aia_core.domain.residency import DataClass
from aia_core.infrastructure.web_retrieval import page_snapshot

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
DOI = "10.5555/fikt.2025.7"


@pytest.mark.parametrize(
    ("raw", "doi"),
    [
        ("10.5555/FIKT.2025.7", DOI),
        ("https://doi.org/10.5555/fikt.2025.7", DOI),
        ("http://dx.doi.org/10.5555/fikt.2025.7.", DOI),
        ("doi: 10.5555/fikt.2025.7", DOI),
        ("info:doi/10.5555/fikt.2025.7", DOI),
        ("ISBN 978-80-000", None),
        ("10.12/too-short-registrant", None),
        ("", None),
    ],
)
def test_a_doi_is_read_whatever_way_it_is_written_and_nothing_else_is(
    raw: str, doi: str | None
) -> None:
    assert normalise_doi(raw) == doi


def _notice(status: WorkStatus, source: str = "retraction-watch") -> WorkNotice:
    return WorkNotice(status=status, notice_doi="10.5555/notice.1", source=source)


def test_unknown_is_never_not_retracted() -> None:
    record = resolve_status(DOI, {"crossref-works-1": None}, checked_at=NOW)
    assert (record.status, record.quarantines, record.checked_by) == (
        WorkStatus.UNKNOWN,
        False,
        (),
    )


def test_an_index_that_lists_nothing_says_none_recorded() -> None:
    record = resolve_status(DOI, {"crossref-works-1": ()}, checked_at=NOW)
    assert record.status is WorkStatus.NONE_RECORDED and not record.quarantines


def test_the_most_severe_notice_any_index_states_stands() -> None:
    record = resolve_status(
        DOI,
        {"crossref-works-1": (_notice(WorkStatus.CORRECTED, "publisher"),)},
        retracted_flags={"openalex-works-1": True},
        checked_at=NOW,
    )
    assert record.status is WorkStatus.RETRACTED and record.quarantines
    assert record.checked_by == ("crossref-works-1", "openalex-works-1")
    # A correction alone is shown, not quarantined.
    corrected = resolve_status(
        DOI, {"crossref-works-1": (_notice(WorkStatus.CORRECTED),)}, checked_at=NOW
    )
    assert corrected.status is WorkStatus.CORRECTED and not corrected.quarantines
    concern = resolve_status(
        DOI, {"x": (_notice(WorkStatus.EXPRESSION_OF_CONCERN),)}, checked_at=NOW
    )
    assert not concern.quarantines
    withdrawn = resolve_status(DOI, {"x": (_notice(WorkStatus.WITHDRAWN),)}, checked_at=NOW)
    assert withdrawn.quarantines


def test_a_page_names_its_own_doi_from_its_metadata() -> None:
    body = (
        '<html><head><meta name="citation_doi" content="doi:10.5555/FIKT.2025.7">'
        '<meta name="dc.identifier" content="10.9999/other.1"></head>'
        "<body><p>Spotřeba rostlinných nápojů v Česku vzrostla.</p>"
        '<a href="https://doi.org/10.1234/cited.9">a work it cites</a></body></html>'
    ).encode()
    snap = _snapshot(body).snapshot
    assert snap.doi == DOI
    stored = snap.model_dump(mode="json")
    assert stored["doi"] == DOI
    # A page that names no DOI stores exactly what it stored before the field existed;
    # a DOI it merely links to is a work it cites, not the work it is.
    plain = _snapshot(b'<p>No metadata. <a href="https://doi.org/10.1234/x.1">x</a></p>')
    assert plain.snapshot.doi is None and "doi" not in plain.snapshot.model_dump(mode="json")


def _snapshot(body: bytes) -> Any:
    return page_snapshot(
        url="https://journal.example/clanek/7",
        final_url="https://journal.example/clanek/7",
        redirects=(),
        http_status=200,
        content_type="text/html; charset=utf-8",
        body=body,
        request_id=None,
        adapter_id="test-fetch",
        retrieval_mode=RetrievalMode.RECORDED,
        retrieved_at=NOW,
    )


def _item(url: str) -> EvidenceItem:
    ref = "SNP-" + "a" * 24
    claim = "Spotřeba rostlinných nápojů v Česku vzrostla o 12,5 %."
    return EvidenceItem.model_validate(
        {
            "evidence_id": evidence_id("f" * 64, ref, claim, claim),
            "track_id": "T1",
            "subject_key": "q-000000000001",
            "channel": Channel.WEB,
            "source_kind": SourceKind.WEB_PAGE,
            "source_ref": ref,
            "source_url": url,
            "source_title": "t",
            "claim": claim,
            "quote": claim,
            "quote_span": (0, len(claim)),
            "evidence_type": EvidenceType.PEER_REVIEWED,
            "source_date": None,
            "geography": "",
            "population": "",
            "topics": (),
            "data_class": DataClass.CLASS_C_INTERNAL,
            "agent_outcome_overlap": False,
            "agent_recommended_use": RecommendedUse.CONTEXT_ONLY,
            "agent_source_quality": 1.0,
        }
    )


def _merge(status: Any) -> Any:
    # An official host scores well above acceptance: only the work's standing can stop it.
    item = _item("https://www.czso.cz/csu/czso/studie-7")
    facts = SourceFacts(
        ref=item.source_ref,
        kind=SourceKind.WEB_PAGE,
        url=item.source_url,
        published=date(2025, 6, 1),
        retrieved=date(2026, 10, 8),
        work_status=status,
    )
    track = TrackEvidence(track_id="T1", evidence=(item,), sources={item.source_ref: facts})
    return merge_evidence([track], questionnaire=(), table=SOURCE_TABLE_V1)


def test_a_finding_on_a_retracted_work_is_quarantined_however_well_its_host_scores() -> None:
    assert len(_merge(None).candidates) == 1
    retracted = resolve_status(
        DOI, {"crossref-works-1": (_notice(WorkStatus.RETRACTED),)}, checked_at=NOW
    )
    result = _merge(retracted)
    assert result.candidates == ()
    (q,) = result.quarantined
    assert q.reason is QuarantineReason.RETRACTED_SOURCE
    assert DOI in q.detail and "10.5555/notice.1" in q.detail and "crossref-works-1" in q.detail


@pytest.mark.parametrize(
    "status", [WorkStatus.UNKNOWN, WorkStatus.NONE_RECORDED, WorkStatus.CORRECTED]
)
def test_a_work_that_stands_or_is_unknown_changes_nothing(status: WorkStatus) -> None:
    answers: dict[str, tuple[WorkNotice, ...] | None] = {
        WorkStatus.UNKNOWN: {"c": None},
        WorkStatus.NONE_RECORDED: {"c": ()},
        WorkStatus.CORRECTED: {"c": (_notice(WorkStatus.CORRECTED),)},
    }[status]  # type: ignore[assignment]
    record = resolve_status(DOI, answers, checked_at=NOW)
    assert record.status is status
    assert len(_merge(record).candidates) == 1


def test_a_source_nobody_asked_about_stores_what_it_stored_before() -> None:
    record = SourceFactsRecord(
        ref="SNP-" + "a" * 24,
        kind=SourceKind.WEB_PAGE,
        url="https://x.example/",
        published=None,
        retrieved=None,
    )
    assert "work_status" not in record.model_dump(mode="json")
    asked = record.model_copy(
        update={"work_status": resolve_status(DOI, {"c": ()}, checked_at=NOW)}
    )
    stored = asked.model_dump(mode="json")
    assert stored["work_status"]["status"] == "none_recorded"
    assert SourceFactsRecord.model_validate(stored) == asked
    assert asked.facts().work_status == asked.work_status


def test_the_works_rule_moves_the_merge_rules() -> None:
    assert WORKS_VERSION in MERGE_RULES_VERSION
