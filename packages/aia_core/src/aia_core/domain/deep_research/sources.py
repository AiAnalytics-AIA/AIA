"""Source scoring from declared tables. The agent's own quality score decides nothing.

ADR 0017 decision 4. 18.6.6 accepted a finding on ``source_quality``, a number the
researching agent wrote about its own source (``research_context.py:345``, 0.55):
*unknown scored as good* (CLAUDE.md §8). Here a source's class comes from what
code can see -- the host of the page it fetched, or that an item is approved
Client Knowledge -- through tables declared below and versioned with
:data:`SOURCE_TABLE_VERSION`. A host no table names is ``UNKNOWN`` and scores
lowest, never neutral.

Recency comes from the date the fetcher read out of the page's own metadata,
never from the model; an undated source does not get the benefit of the doubt.
Geography is recorded (from the host's country-code domain) and not scored: which
markets a study is about is a methodology declaration nobody has made yet.

The numbers are a **proposal** for the methodology owner, like the depth presets
(DR-5): they are data, so changing them changes the version and every fingerprint
that used them, and nothing else.

Every class also has a **tier** (plan ``deep-research-web-search`` § 8.7): T1 official
statistics and government, T2 peer-reviewed and academic, T3 industry, T4 media, T5
preprints and anything unidentified, and EXCLUDED for forums and social platforms.
The tier is an annotation beside the score; it changes no score and no decision
here. An unknown host is ``UNKNOWN`` and so T5 -- never above it. Approved Client
Knowledge is not a publisher at all: its tier is its own, ``CLIENT_KNOWLEDGE``, so
no consumer can rank it against a host by accident.

Pure: stdlib only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Final
from urllib.parse import urlsplit

__all__ = [
    "ACCEPT_THRESHOLD",
    "SOURCE_TABLE_V1",
    "SOURCE_TABLE_VERSION",
    "SourceClass",
    "SourceScore",
    "SourceTable",
    "SourceTier",
    "host_geography",
    "is_excluded",
    "is_excluded_url",
    "score_knowledge_source",
    "score_web_source",
    "tier_of",
    "web_tier",
    "worse_tier",
]

SOURCE_TABLE_VERSION: Final = "aia-source-table-1"

#: The unit's acceptance threshold, kept; what it is compared with is not the unit's.
ACCEPT_THRESHOLD: Final = 0.55


class SourceClass(StrEnum):
    OFFICIAL_STATISTICS = "OFFICIAL_STATISTICS"
    GOVERNMENT_OR_REGULATOR = "GOVERNMENT_OR_REGULATOR"
    PEER_REVIEWED = "PEER_REVIEWED"
    ACADEMIC_INSTITUTION = "ACADEMIC_INSTITUTION"
    PREPRINT = "PREPRINT"
    INDUSTRY_RESEARCH = "INDUSTRY_RESEARCH"
    MEDIA = "MEDIA"
    FORUM_OR_SOCIAL = "FORUM_OR_SOCIAL"
    #: Approved by a person into the client's knowledge (ADR 0015).
    CLIENT_KNOWLEDGE = "CLIENT_KNOWLEDGE"
    UNKNOWN = "UNKNOWN"


class SourceTier(StrEnum):
    """Where a source's publisher stands (plan § 8.7). T1 is the most authoritative."""

    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    T4 = "T4"
    T5 = "T5"
    #: Forums and social platforms: quarantined, whatever they say.
    EXCLUDED = "EXCLUDED"
    #: Approved by a person into the client's knowledge: no publisher to rank.
    CLIENT_KNOWLEDGE = "CLIENT_KNOWLEDGE"


#: The web tiers from best to worst. CLIENT_KNOWLEDGE is deliberately absent.
_WEB_TIER_ORDER: Final[tuple[SourceTier, ...]] = (
    SourceTier.T1,
    SourceTier.T2,
    SourceTier.T3,
    SourceTier.T4,
    SourceTier.T5,
    SourceTier.EXCLUDED,
)


def tier_of(cls: SourceClass) -> SourceTier:
    """The tier a source class stands at. Exhaustive: a new class must choose one."""
    match cls:
        case SourceClass.OFFICIAL_STATISTICS | SourceClass.GOVERNMENT_OR_REGULATOR:
            return SourceTier.T1
        case SourceClass.PEER_REVIEWED | SourceClass.ACADEMIC_INSTITUTION:
            return SourceTier.T2
        case SourceClass.INDUSTRY_RESEARCH:
            return SourceTier.T3
        case SourceClass.MEDIA:
            return SourceTier.T4
        case SourceClass.PREPRINT | SourceClass.UNKNOWN:
            return SourceTier.T5
        case SourceClass.FORUM_OR_SOCIAL:
            return SourceTier.EXCLUDED
        case SourceClass.CLIENT_KNOWLEDGE:
            return SourceTier.CLIENT_KNOWLEDGE


def worse_tier(a: SourceTier, b: SourceTier) -> SourceTier:
    """The lower-standing of two web tiers. Client Knowledge is not ranked against hosts."""
    if SourceTier.CLIENT_KNOWLEDGE in (a, b):
        raise ValueError("Client Knowledge has no web tier to compare")
    return max(a, b, key=_WEB_TIER_ORDER.index)


def is_excluded(cls: SourceClass) -> bool:
    """Whether a class is excluded outright. Its base score is under the threshold too."""
    return tier_of(cls) is SourceTier.EXCLUDED


_BASE_SCORES: Final[dict[SourceClass, float]] = {
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

# Age of a source relative to when it was retrieved, in years -> adjustment.
_RECENT_YEARS: Final = 3
_OLD_YEARS: Final = 8
_AGE_ADJUSTMENT: Final = {"recent": 0.0, "dated": -0.05, "old": -0.15, "undated": -0.05}


@dataclass(frozen=True, slots=True)
class SourceTable:
    """Host -> class, as declared data. A host matches itself and its subdomains."""

    version: str
    hosts: Mapping[str, SourceClass]
    #: (host, path prefix, class): a class for part of a host (Eurostat on europa.eu).
    paths: tuple[tuple[str, str, SourceClass], ...] = ()
    #: (domain suffix, class), consulted when no host matches.
    suffixes: tuple[tuple[str, SourceClass], ...] = ()
    base_scores: Mapping[SourceClass, float] = field(default_factory=lambda: dict(_BASE_SCORES))

    def __post_init__(self) -> None:
        missing = set(SourceClass) - set(self.base_scores)
        if missing:
            raise ValueError(f"source table {self.version} scores no {sorted(missing)}")

    def classify(self, url: str) -> SourceClass:
        """The class of the page at ``url``: path rule, host, suffix, else UNKNOWN."""
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().removeprefix("www.")
        if not host:
            return SourceClass.UNKNOWN
        path = parts.path or "/"
        for rule_host, prefix, cls in self.paths:
            if _host_matches(host, rule_host) and path.startswith(prefix):
                return cls
        best: tuple[int, SourceClass] | None = None
        for rule_host, cls in self.hosts.items():
            if _host_matches(host, rule_host) and (best is None or len(rule_host) > best[0]):
                best = (len(rule_host), cls)
        if best is not None:
            return best[1]
        for suffix, cls in self.suffixes:
            if host.endswith(suffix):
                return cls
        return SourceClass.UNKNOWN

    def extended(self, version: str, hosts: Mapping[str, SourceClass]) -> SourceTable:
        """This table with more hosts, under a new version (the recorded fixtures' hosts)."""
        if version == self.version:
            raise ValueError("an extended table is a different table; give it its own version")
        return SourceTable(
            version=version,
            hosts={**self.hosts, **hosts},
            paths=self.paths,
            suffixes=self.suffixes,
            base_scores=self.base_scores,
        )


def _host_matches(host: str, rule: str) -> bool:
    return host == rule or host.endswith("." + rule)


def web_tier(url: str, table: SourceTable) -> SourceTier:
    """The tier of a fetched page from its host's declared class; unknown hosts are T5."""
    tier = tier_of(table.classify(url))
    if tier is SourceTier.CLIENT_KNOWLEDGE:
        raise ValueError(f"source table {table.version} classes a web page as Client Knowledge")
    return tier


def is_excluded_url(url: str, table: SourceTable) -> bool:
    """Whether the page at ``url`` is excluded (a forum or social platform) by ``table``."""
    return is_excluded(table.classify(url))


def host_geography(url: str) -> str:
    """The country a host's domain names ("CZ"), "EU", or "" when it names none."""
    host = (urlsplit(url).hostname or "").lower()
    if host == "europa.eu" or host.endswith(".europa.eu"):
        return "EU"
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if tld == "eu":
        return "EU"
    return tld.upper() if len(tld) == 2 and tld.isalpha() else ""


@dataclass(frozen=True, slots=True)
class SourceScore:
    """A source's score and every term of it, for the reviewer."""

    source_class: SourceClass
    base: float
    age: str
    age_adjustment: float
    score: float
    geography: str
    table_version: str

    @property
    def acceptable(self) -> bool:
        return self.score >= ACCEPT_THRESHOLD


def _age(published: date | None, retrieved: date) -> str:
    if published is None or published > retrieved:
        # A date after retrieval is not a date anyone can rely on.
        return "undated"
    years = (retrieved - published).days / 365.25
    if years <= _RECENT_YEARS:
        return "recent"
    return "dated" if years <= _OLD_YEARS else "old"


def score_web_source(
    url: str, *, published: date | None, retrieved: date, table: SourceTable
) -> SourceScore:
    """Score a fetched page from its host's declared class and its own publication date."""
    cls = table.classify(url)
    base = table.base_scores[cls]
    age = _age(published, retrieved)
    adjustment = _AGE_ADJUSTMENT[age]
    return SourceScore(
        source_class=cls,
        base=base,
        age=age,
        age_adjustment=adjustment,
        score=round(max(0.0, min(1.0, base + adjustment)), 4),
        geography=host_geography(url),
        table_version=table.version,
    )


def score_knowledge_source(table: SourceTable) -> SourceScore:
    """An approved Client Knowledge item: a person already vouched for it."""
    base = table.base_scores[SourceClass.CLIENT_KNOWLEDGE]
    return SourceScore(
        source_class=SourceClass.CLIENT_KNOWLEDGE,
        base=base,
        age="approved",
        age_adjustment=0.0,
        score=base,
        geography="",
        table_version=table.version,
    )


_OFFICIAL: Final = SourceClass.OFFICIAL_STATISTICS
_GOV: Final = SourceClass.GOVERNMENT_OR_REGULATOR
_PEER: Final = SourceClass.PEER_REVIEWED
_ACADEMIC: Final = SourceClass.ACADEMIC_INSTITUTION
_PREPRINT: Final = SourceClass.PREPRINT
_INDUSTRY: Final = SourceClass.INDUSTRY_RESEARCH
_MEDIA: Final = SourceClass.MEDIA
_FORUM: Final = SourceClass.FORUM_OR_SOCIAL

#: The production table. Czech sources first, then European and international ones.
SOURCE_TABLE_V1: Final = SourceTable(
    version=SOURCE_TABLE_VERSION,
    hosts={
        # official statistics
        "czso.cz": _OFFICIAL,
        "statistics.sk": _OFFICIAL,
        "destatis.de": _OFFICIAL,
        "stat.gov.pl": _OFFICIAL,
        "ons.gov.uk": _OFFICIAL,
        "data.europa.eu": _OFFICIAL,
        "oecd.org": _OFFICIAL,
        "worldbank.org": _OFFICIAL,
        "imf.org": _OFFICIAL,
        "who.int": _OFFICIAL,
        "un.org": _OFFICIAL,
        # government and regulators
        "europa.eu": _GOV,
        "cnb.cz": _GOV,
        "ctu.cz": _GOV,
        "uohs.cz": _GOV,
        "mzcr.cz": _GOV,
        "szu.cz": _GOV,
        "mpsv.cz": _GOV,
        "msmt.cz": _GOV,
        "psp.cz": _GOV,
        "senat.cz": _GOV,
        "zakonyprolidi.cz": _GOV,
        # peer-reviewed publishers and indexes
        "doi.org": _PEER,
        "pubmed.ncbi.nlm.nih.gov": _PEER,
        "ncbi.nlm.nih.gov": _PEER,
        "sciencedirect.com": _PEER,
        "link.springer.com": _PEER,
        "onlinelibrary.wiley.com": _PEER,
        "tandfonline.com": _PEER,
        "journals.sagepub.com": _PEER,
        "jstor.org": _PEER,
        "nature.com": _PEER,
        "science.org": _PEER,
        "thelancet.com": _PEER,
        "bmj.com": _PEER,
        "journals.plos.org": _PEER,
        "frontiersin.org": _PEER,
        "academic.oup.com": _PEER,
        "cambridge.org": _PEER,
        # academic institutions
        "cuni.cz": _ACADEMIC,
        "muni.cz": _ACADEMIC,
        "vse.cz": _ACADEMIC,
        "cvut.cz": _ACADEMIC,
        "vutbr.cz": _ACADEMIC,
        "upol.cz": _ACADEMIC,
        "mendelu.cz": _ACADEMIC,
        "soc.cas.cz": _ACADEMIC,
        # preprints
        "arxiv.org": _PREPRINT,
        "ssrn.com": _PREPRINT,
        "osf.io": _PREPRINT,
        "researchgate.net": _PREPRINT,
        # industry research
        "nielseniq.com": _INDUSTRY,
        "kantar.com": _INDUSTRY,
        "ipsos.com": _INDUSTRY,
        "gfk.com": _INDUSTRY,
        "euromonitor.com": _INDUSTRY,
        "mintel.com": _INDUSTRY,
        "statista.com": _INDUSTRY,
        "mckinsey.com": _INDUSTRY,
        "deloitte.com": _INDUSTRY,
        "pwc.com": _INDUSTRY,
        "kpmg.com": _INDUSTRY,
        "bcg.com": _INDUSTRY,
        "ey.com": _INDUSTRY,
        "stem.cz": _INDUSTRY,
        "median.eu": _INDUSTRY,
        "nms.cz": _INDUSTRY,
        # media
        "reuters.com": _MEDIA,
        "apnews.com": _MEDIA,
        "bbc.co.uk": _MEDIA,
        "bbc.com": _MEDIA,
        "ft.com": _MEDIA,
        "economist.com": _MEDIA,
        "theguardian.com": _MEDIA,
        "nytimes.com": _MEDIA,
        "irozhlas.cz": _MEDIA,
        "ceskatelevize.cz": _MEDIA,
        "idnes.cz": _MEDIA,
        "lidovky.cz": _MEDIA,
        "aktualne.cz": _MEDIA,
        "seznamzpravy.cz": _MEDIA,
        "novinky.cz": _MEDIA,
        "ihned.cz": _MEDIA,
        "e15.cz": _MEDIA,
        "denik.cz": _MEDIA,
        "forbes.cz": _MEDIA,
        "respekt.cz": _MEDIA,
        # forums and social platforms
        "reddit.com": _FORUM,
        "quora.com": _FORUM,
        "modrykonik.cz": _FORUM,
        "facebook.com": _FORUM,
        "x.com": _FORUM,
        "twitter.com": _FORUM,
        "tiktok.com": _FORUM,
        "youtube.com": _FORUM,
        "medium.com": _FORUM,
        "blogspot.com": _FORUM,
        "wordpress.com": _FORUM,
    },
    paths=(("ec.europa.eu", "/eurostat", _OFFICIAL),),
    suffixes=(
        (".gov", _GOV),
        (".gov.cz", _GOV),
        (".gov.sk", _GOV),
        (".gov.uk", _GOV),
        (".gv.at", _GOV),
        (".bund.de", _GOV),
        (".edu", _ACADEMIC),
        (".ac.uk", _ACADEMIC),
    ),
)
