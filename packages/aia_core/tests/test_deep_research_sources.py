"""Source scoring from declared tables; the agent's own score is never an input."""

from __future__ import annotations

from datetime import date

import pytest

from aia_core.domain.deep_research.sources import (
    ACCEPT_THRESHOLD,
    SOURCE_TABLE_V1,
    SOURCE_TABLE_VERSION,
    SourceClass,
    SourceTable,
    host_geography,
    score_knowledge_source,
    score_web_source,
)

TODAY = date(2026, 9, 27)


@pytest.mark.parametrize(
    ("url", "cls"),
    [
        ("https://www.czso.cz/csu/czso/spotreba", SourceClass.OFFICIAL_STATISTICS),
        ("https://ec.europa.eu/eurostat/web/main", SourceClass.OFFICIAL_STATISTICS),
        ("https://ec.europa.eu/info/law", SourceClass.GOVERNMENT_OR_REGULATOR),
        ("https://data.europa.eu/set/1", SourceClass.OFFICIAL_STATISTICS),
        ("https://www.mzp.gov.cz/cz/obaly", SourceClass.GOVERNMENT_OR_REGULATOR),
        ("https://doi.org/10.1000/xyz", SourceClass.PEER_REVIEWED),
        ("https://arxiv.org/abs/2601.00001", SourceClass.PREPRINT),
        ("https://www.nielseniq.com/report", SourceClass.INDUSTRY_RESEARCH),
        ("https://www.irozhlas.cz/zpravy", SourceClass.MEDIA),
        ("https://www.reddit.com/r/czech", SourceClass.FORUM_OR_SOCIAL),
        ("https://stanford.edu/paper", SourceClass.ACADEMIC_INSTITUTION),
        ("https://unheard-of-blog.example/post", SourceClass.UNKNOWN),
        ("not a url", SourceClass.UNKNOWN),
    ],
)
def test_the_host_decides_the_class(url: str, cls: SourceClass) -> None:
    assert SOURCE_TABLE_V1.classify(url) is cls


def test_an_unknown_source_scores_lowest_and_is_not_acceptable() -> None:
    unknown = score_web_source(
        "https://x.example/a", published=TODAY, retrieved=TODAY, table=SOURCE_TABLE_V1
    )
    assert unknown.source_class is SourceClass.UNKNOWN
    assert unknown.score == min(SOURCE_TABLE_V1.base_scores.values())
    assert not unknown.acceptable


def test_an_undated_source_does_not_get_the_benefit_of_the_doubt() -> None:
    url = "https://www.czso.cz/a"
    dated = score_web_source(
        url, published=date(2025, 1, 1), retrieved=TODAY, table=SOURCE_TABLE_V1
    )
    undated = score_web_source(url, published=None, retrieved=TODAY, table=SOURCE_TABLE_V1)
    future = score_web_source(
        url, published=date(2027, 1, 1), retrieved=TODAY, table=SOURCE_TABLE_V1
    )
    old = score_web_source(url, published=date(2010, 1, 1), retrieved=TODAY, table=SOURCE_TABLE_V1)
    assert dated.age == "recent" and undated.age == "undated" and future.age == "undated"
    assert dated.score > undated.score > old.score
    assert dated.table_version == SOURCE_TABLE_VERSION


def test_media_passes_and_forums_do_not() -> None:
    media = score_web_source(
        "https://www.idnes.cz/a", published=TODAY, retrieved=TODAY, table=SOURCE_TABLE_V1
    )
    forum = score_web_source(
        "https://www.reddit.com/a", published=TODAY, retrieved=TODAY, table=SOURCE_TABLE_V1
    )
    assert media.acceptable and media.score >= ACCEPT_THRESHOLD
    assert not forum.acceptable


def test_approved_knowledge_is_its_own_class() -> None:
    score = score_knowledge_source(SOURCE_TABLE_V1)
    assert score.source_class is SourceClass.CLIENT_KNOWLEDGE and score.acceptable


def test_an_extended_table_is_a_new_version_and_the_production_table_is_unchanged() -> None:
    fixture = SOURCE_TABLE_V1.extended(
        "recorded-fixture-1", {"statistika.example": SourceClass.OFFICIAL_STATISTICS}
    )
    assert fixture.classify("https://statistika.example/a") is SourceClass.OFFICIAL_STATISTICS
    assert SOURCE_TABLE_V1.classify("https://statistika.example/a") is SourceClass.UNKNOWN
    with pytest.raises(ValueError, match="own version"):
        SOURCE_TABLE_V1.extended(SOURCE_TABLE_VERSION, {})


def test_a_table_must_score_every_class() -> None:
    with pytest.raises(ValueError, match="scores no"):
        SourceTable(version="broken", hosts={}, base_scores={SourceClass.UNKNOWN: 0.2})


@pytest.mark.parametrize(
    ("url", "geo"),
    [
        ("https://www.idnes.cz/a", "CZ"),
        ("https://ec.europa.eu/a", "EU"),
        ("https://median.eu/a", "EU"),
        ("https://reuters.com/a", ""),
        ("https://localhost/a", ""),
    ],
)
def test_geography_is_read_from_the_domain_only(url: str, geo: str) -> None:
    assert host_geography(url) == geo
