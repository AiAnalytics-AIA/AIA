"""Source scoring from declared tables; the agent's own score is never an input."""

from __future__ import annotations

import hashlib
import json
from datetime import date

import pytest

from aia_core.domain.deep_research.sources import (
    ACCEPT_THRESHOLD,
    SOURCE_TABLE_V1,
    SOURCE_TABLE_VERSION,
    SourceClass,
    SourceTable,
    SourceTier,
    host_geography,
    is_excluded,
    is_excluded_url,
    score_knowledge_source,
    score_web_source,
    tier_of,
    web_tier,
    worse_tier,
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


# --- the production table, pinned ------------------------------------------------

#: SOURCE_TABLE_V1 as data: hosts, path rules, suffixes and base scores. Tiers were
#: added beside it (plan deep-research-web-search chunk 8) without changing any of it.
_V1_SHA256 = "defc5d30d69fe48b43e0cea6932fd175275e382ba827a70fe1a992e7b14586e2"


def test_the_production_table_is_unchanged() -> None:
    table = SOURCE_TABLE_V1
    data = json.dumps(
        {
            "hosts": sorted((h, c.value) for h, c in table.hosts.items()),
            "paths": [[h, p, c.value] for h, p, c in table.paths],
            "suffixes": [[s, c.value] for s, c in table.suffixes],
            "scores": sorted((c.value, v) for c, v in table.base_scores.items()),
        },
        sort_keys=True,
    )
    assert hashlib.sha256(data.encode()).hexdigest() == _V1_SHA256
    assert table.version == SOURCE_TABLE_VERSION == "aia-source-table-1"
    assert dict(table.base_scores) == {
        SourceClass.OFFICIAL_STATISTICS: 0.95,
        SourceClass.GOVERNMENT_OR_REGULATOR: 0.9,
        SourceClass.PEER_REVIEWED: 0.9,
        SourceClass.ACADEMIC_INSTITUTION: 0.75,
        SourceClass.CLIENT_KNOWLEDGE: 0.85,
        SourceClass.INDUSTRY_RESEARCH: 0.7,
        SourceClass.MEDIA: 0.6,
        SourceClass.PREPRINT: 0.55,
        SourceClass.FORUM_OR_SOCIAL: 0.3,
        SourceClass.UNKNOWN: 0.2,
    }


# --- tiers ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cls", "tier"),
    [
        (SourceClass.OFFICIAL_STATISTICS, SourceTier.T1),
        (SourceClass.GOVERNMENT_OR_REGULATOR, SourceTier.T1),
        (SourceClass.PEER_REVIEWED, SourceTier.T2),
        (SourceClass.ACADEMIC_INSTITUTION, SourceTier.T2),
        (SourceClass.INDUSTRY_RESEARCH, SourceTier.T3),
        (SourceClass.MEDIA, SourceTier.T4),
        (SourceClass.PREPRINT, SourceTier.T5),
        (SourceClass.UNKNOWN, SourceTier.T5),
        (SourceClass.FORUM_OR_SOCIAL, SourceTier.EXCLUDED),
        (SourceClass.CLIENT_KNOWLEDGE, SourceTier.CLIENT_KNOWLEDGE),
    ],
)
def test_every_class_has_its_tier(cls: SourceClass, tier: SourceTier) -> None:
    assert tier_of(cls) is tier


def test_every_class_is_tiered() -> None:
    assert {tier_of(cls) for cls in SourceClass} == set(SourceTier)


@pytest.mark.parametrize(
    "url",
    [
        "https://unheard-of-blog.example/post",
        "https://czso.cz.example.com/a",
        "https://notczso.cz/a",
        "not a url",
        "",
    ],
)
def test_an_unknown_host_is_never_above_t5(url: str) -> None:
    assert web_tier(url, SOURCE_TABLE_V1) is SourceTier.T5


def test_a_known_host_takes_its_class_tier() -> None:
    assert web_tier("https://vdb.czso.cz/a", SOURCE_TABLE_V1) is SourceTier.T1
    assert web_tier("https://www.idnes.cz/a", SOURCE_TABLE_V1) is SourceTier.T4
    assert web_tier("https://ec.europa.eu/eurostat/a", SOURCE_TABLE_V1) is SourceTier.T1


def test_forums_and_social_platforms_are_excluded() -> None:
    assert is_excluded(SourceClass.FORUM_OR_SOCIAL)
    assert [cls for cls in SourceClass if is_excluded(cls)] == [SourceClass.FORUM_OR_SOCIAL]
    assert is_excluded_url("https://www.reddit.com/r/czech", SOURCE_TABLE_V1)
    assert not is_excluded_url("https://www.czso.cz/a", SOURCE_TABLE_V1)
    assert not is_excluded_url("https://unheard-of-blog.example/a", SOURCE_TABLE_V1)
    assert web_tier("https://m.facebook.com/a", SOURCE_TABLE_V1) is SourceTier.EXCLUDED


def test_an_excluded_host_is_quarantined_today() -> None:
    """Exclusion agrees with merge's quarantine: every excluded host scores under the bar."""
    excluded = [h for h, cls in SOURCE_TABLE_V1.hosts.items() if is_excluded(cls)]
    assert excluded
    for host in excluded:
        score = score_web_source(
            f"https://{host}/a", published=TODAY, retrieved=TODAY, table=SOURCE_TABLE_V1
        )
        assert not score.acceptable, host


def test_the_worse_tier_wins_and_knowledge_is_not_ranked() -> None:
    assert worse_tier(SourceTier.T1, SourceTier.T2) is SourceTier.T2
    assert worse_tier(SourceTier.T5, SourceTier.T3) is SourceTier.T5
    assert worse_tier(SourceTier.T4, SourceTier.EXCLUDED) is SourceTier.EXCLUDED
    assert worse_tier(SourceTier.T1, SourceTier.T1) is SourceTier.T1
    with pytest.raises(ValueError, match="Client Knowledge"):
        worse_tier(SourceTier.CLIENT_KNOWLEDGE, SourceTier.T5)


def test_a_table_that_classes_a_page_as_knowledge_has_no_web_tier() -> None:
    broken = SOURCE_TABLE_V1.extended("broken-1", {"kb.example": SourceClass.CLIENT_KNOWLEDGE})
    with pytest.raises(ValueError, match="Client Knowledge"):
        web_tier("https://kb.example/a", broken)
