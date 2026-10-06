"""The reputation register: exact name and host lookups, tiers never raised, shipped off."""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from aia_core.domain.deep_research.reputation import (
    REPUTATION_REGISTER_V1,
    REPUTATION_REGISTER_VERSION,
    REPUTATION_SOURCE_TABLE_VERSION,
    SOURCE_TABLE_REPUTATION_1,
    Publisher,
    RegisterStatus,
    ReputationRegister,
    normalise_name,
)
from aia_core.domain.deep_research.sources import (
    SOURCE_TABLE_V1,
    SourceClass,
    SourceTable,
    SourceTier,
    tier_of,
    worse_tier,
)
from aia_core.domain.deep_research.web import check_url

REGISTER = REPUTATION_REGISTER_V1
NAMES = [(p, name) for p in REGISTER.publishers for name in p.all_names]
HOSTS = [(p, host) for p in REGISTER.publishers for host in p.hosts]


def _ascii(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# --- versions and status -----------------------------------------------------------


def test_the_register_and_its_table_have_stable_versions() -> None:
    assert REPUTATION_REGISTER_VERSION == "aia-reputation-register-1 (proposed)"
    assert REGISTER.version == REPUTATION_REGISTER_VERSION
    assert REPUTATION_SOURCE_TABLE_VERSION == "aia-source-table-1+reputation-1 (proposed)"
    assert SOURCE_TABLE_REPUTATION_1.version == REPUTATION_SOURCE_TABLE_VERSION


def test_the_whole_register_is_proposed() -> None:
    assert REGISTER.status is RegisterStatus.PROPOSED
    assert {p.status for p in REGISTER.publishers} == {RegisterStatus.PROPOSED}


_PY_APPS = ("api", "worker", "executors")


def test_no_composition_uses_the_proposed_table() -> None:
    """Shipped off: only this module and its tests name the extended table."""
    root = Path(__file__).resolve().parents[3]
    named = [
        path.relative_to(root).as_posix()
        for tree in ("packages/aia_core/src", *(f"apps/{app}/src" for app in _PY_APPS))
        for path in (root / tree).rglob("*.py")
        if "SOURCE_TABLE_REPUTATION_1" in path.read_text(encoding="utf-8")
    ]
    assert named == ["packages/aia_core/src/aia_core/domain/deep_research/reputation.py"]


# --- names -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("publisher", "name"), NAMES, ids=[f"{p.canonical_name}|{n}" for p, n in NAMES]
)
def test_every_name_variant_resolves_to_its_publisher(publisher: Publisher, name: str) -> None:
    for form in (name, name.upper(), name.lower(), _ascii(name), f"  {_ascii(name).upper()} "):
        assert REGISTER.resolve_publisher(form) is publisher, form


@pytest.mark.parametrize(
    ("name", "canonical"),
    [
        ("ČSÚ", "Český statistický úřad"),
        ("csu", "Český statistický úřad"),
        ("Cesky statisticky urad", "Český statistický úřad"),
        ("czech statistical office", "Český statistický úřad"),
        ("CZSO", "Český statistický úřad"),
        ("Eurostat", "Evropská komise"),
        ("ČNB", "Česká národní banka"),
        ("Organisation for Economic Co-operation and Development", "OECD"),
        ("svetova banka", "World Bank"),
        ("iDNES.cz", "iDNES.cz"),
        ("idnes cz", "iDNES.cz"),
    ],
)
def test_names_resolve_whatever_their_case_and_diacritics(name: str, canonical: str) -> None:
    publisher = REGISTER.resolve_publisher(name)
    assert publisher is not None and publisher.canonical_name == canonical


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        "Český statistický",
        "Czech Statistics Office",
        "Statistický úřad",
        "Novinky",
        "Deník",
        "Aktuálně",
        "Ministry of Agriculture",
        "ČSÚ 2024",
        "Slovenský štatistický úrad",
    ],
)
def test_an_undeclared_name_is_none_never_a_guess(name: str) -> None:
    assert REGISTER.resolve_publisher(name) is None


def test_normalisation_drops_only_case_diacritics_and_punctuation() -> None:
    assert normalise_name("Český  statistický-úřad") == "cesky statisticky urad"
    assert normalise_name("MF ČR") == "mf cr"
    assert normalise_name("MFČR") == "mfcr"


def test_every_normalised_name_belongs_to_one_publisher() -> None:
    owners: dict[str, str] = {}
    for publisher, name in NAMES:
        key = normalise_name(name)
        assert owners.setdefault(key, publisher.canonical_name) == publisher.canonical_name


# --- hosts -------------------------------------------------------------------------


@pytest.mark.parametrize(("publisher", "host"), HOSTS, ids=[h for _, h in HOSTS])
def test_every_host_is_fetchable_and_resolves_with_its_subdomains(
    publisher: Publisher, host: str
) -> None:
    assert check_url(f"https://{host}/") == host
    assert check_url(f"https://www.{host}/a") == f"www.{host}"
    for form in (host, f"www.{host}", f"data.{host}", host.upper(), f"{host}."):
        assert REGISTER.publisher_for_host(form) is publisher, form


@pytest.mark.parametrize(
    ("host", "canonical"),
    [
        ("www.czso.cz", "Český statistický úřad"),
        ("vdb.czso.cz", "Český statistický úřad"),
        ("csu.gov.cz", "Český statistický úřad"),
        ("ct24.ceskatelevize.cz", "Česká televize"),
        ("ec.europa.eu", "Evropská komise"),
        ("ecb.europa.eu", "Evropská centrální banka"),
    ],
)
def test_a_host_and_its_subdomains_name_the_publisher(host: str, canonical: str) -> None:
    publisher = REGISTER.publisher_for_host(host)
    assert publisher is not None and publisher.canonical_name == canonical


@pytest.mark.parametrize(
    "host",
    [
        "czso.cz.example.com",
        "notczso.cz",
        "czso.cz-evil.com",
        "evil-csu.gov.cz",
        "csu.gov.cz.attacker.com",
        "europa.eu",
        "gov.cz",
        "cz",
        "",
        "https://czso.cz/",
        "czso.cz/a",
        "czso.cz:443",
        "user@czso.cz",
        "unheard-of-blog.example",
    ],
)
def test_a_look_alike_or_malformed_host_names_no_publisher(host: str) -> None:
    assert REGISTER.publisher_for_host(host) is None


def test_no_host_is_declared_twice_or_inside_another() -> None:
    hosts = [host for _, host in HOSTS]
    assert len(hosts) == len(set(hosts))
    for a in hosts:
        for b in hosts:
            assert a == b or not a.endswith("." + b), (a, b)


# --- tiers -------------------------------------------------------------------------


@pytest.mark.parametrize("publisher", REGISTER.publishers, ids=lambda p: p.canonical_name)
def test_a_publisher_never_stands_above_its_class(publisher: Publisher) -> None:
    assert worse_tier(publisher.tier, tier_of(publisher.source_class)) is publisher.tier


def test_the_register_counts_per_tier() -> None:
    counts: dict[SourceTier, int] = {}
    for publisher in REGISTER.publishers:
        counts[publisher.tier] = counts.get(publisher.tier, 0) + 1
    assert counts == {
        SourceTier.T1: 14,
        SourceTier.T2: 2,
        SourceTier.T3: 4,
        SourceTier.T4: 12,
    }


@pytest.mark.parametrize(
    ("url", "table", "tier"),
    [
        ("https://www.czso.cz/a", SOURCE_TABLE_V1, SourceTier.T1),
        ("https://www.oecd.org/a", SOURCE_TABLE_V1, SourceTier.T2),
        ("https://data.worldbank.org/a", SOURCE_TABLE_REPUTATION_1, SourceTier.T2),
        ("https://www.foodnet.cz/a", SOURCE_TABLE_REPUTATION_1, SourceTier.T3),
        # The production table does not know hn.cz: the register cannot raise it.
        ("https://hn.cz/a", SOURCE_TABLE_V1, SourceTier.T5),
        ("https://hn.cz/a", SOURCE_TABLE_REPUTATION_1, SourceTier.T4),
        ("https://unheard-of-blog.example/a", SOURCE_TABLE_REPUTATION_1, SourceTier.T5),
        ("https://czso.cz.example.com/a", SOURCE_TABLE_REPUTATION_1, SourceTier.T5),
        ("https://www.reddit.com/a", SOURCE_TABLE_REPUTATION_1, SourceTier.EXCLUDED),
    ],
)
def test_a_pages_tier_is_the_worse_of_register_and_table(
    url: str, table: SourceTable, tier: SourceTier
) -> None:
    assert REGISTER.tier_for_url(url, table) is tier


# --- the extended table ------------------------------------------------------------


def test_the_extended_table_reclasses_no_host_the_production_table_knows() -> None:
    for host, cls in REGISTER.host_classes().items():
        if host in SOURCE_TABLE_V1.hosts:
            assert SOURCE_TABLE_V1.hosts[host] is cls, host
    for host in SOURCE_TABLE_V1.hosts:
        url = f"https://{host}/a"
        assert SOURCE_TABLE_REPUTATION_1.classify(url) is SOURCE_TABLE_V1.classify(url), host
    for host, prefix, _ in SOURCE_TABLE_V1.paths:
        url = f"https://{host}{prefix}/a"
        assert SOURCE_TABLE_REPUTATION_1.classify(url) is SOURCE_TABLE_V1.classify(url)
    assert dict(SOURCE_TABLE_REPUTATION_1.base_scores) == dict(SOURCE_TABLE_V1.base_scores)


def test_the_extended_table_knows_every_register_host() -> None:
    for publisher, host in HOSTS:
        assert SOURCE_TABLE_REPUTATION_1.classify(f"https://{host}/") is publisher.source_class


# --- validation --------------------------------------------------------------------


def _publisher(**changes: object) -> Publisher:
    values: dict[str, object] = {
        "canonical_name": "Statistika",
        "names": ("STAT",),
        "hosts": ("statistika.example",),
        "source_class": SourceClass.OFFICIAL_STATISTICS,
        "tier": SourceTier.T1,
    }
    values.update(changes)
    return Publisher(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"tier": SourceTier.T1, "source_class": SourceClass.MEDIA}, "above its class"),
        ({"source_class": SourceClass.UNKNOWN, "tier": SourceTier.T5}, "is not UNKNOWN"),
        ({"source_class": SourceClass.CLIENT_KNOWLEDGE}, "is not CLIENT_KNOWLEDGE"),
        ({"tier": SourceTier.CLIENT_KNOWLEDGE}, "web tier"),
        ({"hosts": ()}, "at least one host"),
        ({"hosts": ("www.statistika.example",)}, "without www"),
        ({"hosts": ("Statistika.example",)}, "without www"),
        ({"hosts": ("https://statistika.example",)}, "without www"),
        ({"hosts": ("a.example", "a.example")}, "twice"),
        ({"names": ("--",)}, "empty"),
        ({"canonical_name": " "}, "canonical name"),
        ({"data_interfaces": ("https://api.example",)}, "plain name"),
    ],
)
def test_a_malformed_publisher_is_refused(changes: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _publisher(**changes)


def test_a_lower_tier_than_the_class_is_allowed() -> None:
    assert _publisher(tier=SourceTier.T3).tier is SourceTier.T3


def test_a_register_refuses_a_name_or_host_owned_twice() -> None:
    first = _publisher()
    same_name = _publisher(canonical_name="Jiná", names=("Stat",), hosts=("jina.example",))
    with pytest.raises(ValueError, match="names both"):
        ReputationRegister("t", RegisterStatus.PROPOSED, (first, same_name))
    nested = _publisher(canonical_name="Jiná", names=(), hosts=("vdb.statistika.example",))
    with pytest.raises(ValueError, match="overlaps"):
        ReputationRegister("t", RegisterStatus.PROPOSED, (first, nested))


def test_an_approved_register_holds_only_approved_publishers() -> None:
    with pytest.raises(ValueError, match="is approved"):
        ReputationRegister("t", RegisterStatus.APPROVED, (_publisher(),))
    approved = _publisher(status=RegisterStatus.APPROVED)
    assert ReputationRegister("t", RegisterStatus.APPROVED, (approved,)).publishers == (approved,)
