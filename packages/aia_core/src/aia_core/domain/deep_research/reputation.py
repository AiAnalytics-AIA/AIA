"""The reputation register: publishers, their names, hosts, tiers and data interfaces.

Plan ``deep-research-web-search`` § 8.7 and chunk 8. A source table says what class a
*host* is; the register says who the *publisher* is: the names a page or a model may
cite it by ("ČSÚ", "Český statistický úřad", "Czech Statistical Office"), the hosts it
publishes on (``csu.gov.cz``, ``czso.cz``), its tier, and the data interfaces a
connector could query (``datastat``). Later chunks use it to chase a cited
publisher to its own site (ladder rungs 3 and 4) and to annotate a finding's tier.

Two lookups, both exact:

* :meth:`ReputationRegister.resolve_publisher` -- a name, normalised (case,
  diacritics, punctuation and spacing) and then matched exactly against a declared
  variant. No fuzzy matching: a name nobody declared is ``None``, never a guess.
* :meth:`ReputationRegister.publisher_for_host` -- a host matches a declared host
  or one of its subdomains (``vdb.czso.cz``), never a look-alike
  (``czso.cz.example.com``, ``notczso.cz``).

A publisher's tier may be *lower* than its class's tier (the plan puts the OECD and
the World Bank at T2 while their statistics class is T1), never higher, and a URL's
tier is the worse of the register's and the table's: an unknown host stays T5.

The register is data, versioned, and **proposed**: the data owner has not approved
it. :data:`SOURCE_TABLE_REPUTATION_1` is the source table extended with its hosts,
under its own version, and nothing uses it: no composition names it and
:data:`~.sources.SOURCE_TABLE_V1` is unchanged. Approving it is a change of
``status`` and version, made by a person.

Hosts are listed only where they are known to be the publisher's own registrable
domain; a doubtful one is left out rather than guessed.

Pure: stdlib only.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final
from urllib.parse import urlsplit

from .sources import (
    SOURCE_TABLE_V1,
    SourceClass,
    SourceTable,
    SourceTier,
    tier_of,
    web_tier,
    worse_tier,
)

__all__ = [
    "REPUTATION_REGISTER_V1",
    "REPUTATION_REGISTER_VERSION",
    "REPUTATION_SOURCE_TABLE_VERSION",
    "SOURCE_TABLE_REPUTATION_1",
    "Publisher",
    "RegisterStatus",
    "ReputationRegister",
    "normalise_name",
]

REPUTATION_REGISTER_VERSION: Final = "aia-reputation-register-1 (proposed)"
REPUTATION_SOURCE_TABLE_VERSION: Final = "aia-source-table-1+reputation-1 (proposed)"

#: A registrable domain or a subdomain of one, lower case, without ``www.``.
_LABEL: Final = r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
_HOST: Final = re.compile(rf"^(?!www\.){_LABEL}(?:\.{_LABEL})+$")
_NOT_NAME: Final = re.compile(r"[^0-9a-z]+")
#: An interface is named, not located: ``datastat``, ``eurostat_api``.
_INTERFACE: Final = re.compile(r"^[a-z][a-z0-9_]*$")


class RegisterStatus(StrEnum):
    """Whether the data owner approved an entry. Only a person moves it to APPROVED."""

    PROPOSED = "proposed"
    APPROVED = "approved"


def normalise_name(name: str) -> str:
    """A name as the register compares it: no diacritics, case-folded, words only.

    ``"Český statistický úřad"`` and ``"CESKY  statisticky-urad"`` are the same name;
    nothing else is done to it.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _NOT_NAME.sub(" ", stripped.casefold()).strip()


def _normalise_host(host: str) -> str | None:
    candidate = host.strip().lower().rstrip(".").removeprefix("www.")
    return candidate if _HOST.match(candidate) else None


def _within(host: str, declared: str) -> bool:
    return host == declared or host.endswith("." + declared)


@dataclass(frozen=True, slots=True)
class Publisher:
    """One publisher: what it is called, where it publishes, and where it stands."""

    canonical_name: str
    #: Other names it is cited by, Czech and English, abbreviations included.
    names: tuple[str, ...]
    #: Registrable domains (or a declared subdomain); subdomains of each match too.
    hosts: tuple[str, ...]
    source_class: SourceClass
    tier: SourceTier
    #: Data interfaces a connector could query, by name only.
    data_interfaces: tuple[str, ...] = ()
    status: RegisterStatus = RegisterStatus.PROPOSED

    def __post_init__(self) -> None:
        who = self.canonical_name
        if not normalise_name(who):
            raise ValueError("a publisher needs a canonical name")
        if any(not normalise_name(name) for name in self.names):
            raise ValueError(f"{who}: a name variant is empty once normalised")
        if not self.hosts:
            raise ValueError(f"{who}: a publisher needs at least one host")
        for host in self.hosts:
            if _normalise_host(host) != host:
                raise ValueError(f"{who}: {host!r} is not a lower-case host without www.")
        if len(set(self.hosts)) != len(self.hosts):
            raise ValueError(f"{who}: a host is listed twice")
        if self.source_class in (SourceClass.CLIENT_KNOWLEDGE, SourceClass.UNKNOWN):
            raise ValueError(f"{who}: a publisher is not {self.source_class.value}")
        if self.tier is SourceTier.CLIENT_KNOWLEDGE:
            raise ValueError(f"{who}: a publisher has a web tier")
        if worse_tier(self.tier, tier_of(self.source_class)) is not self.tier:
            raise ValueError(
                f"{who}: tier {self.tier.value} is above its class's "
                f"{tier_of(self.source_class).value}; a register may only lower a tier"
            )
        for interface in self.data_interfaces:
            if not _INTERFACE.match(interface):
                raise ValueError(f"{who}: interface {interface!r} is not a plain name")

    @property
    def all_names(self) -> tuple[str, ...]:
        return (self.canonical_name, *self.names)


@dataclass(frozen=True, slots=True)
class ReputationRegister:
    """Publishers as versioned data. Every name and every host belongs to one publisher."""

    version: str
    status: RegisterStatus
    publishers: tuple[Publisher, ...]
    _by_name: dict[str, Publisher] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        by_name: dict[str, Publisher] = {}
        hosts: dict[str, Publisher] = {}
        for publisher in self.publishers:
            if self.status is RegisterStatus.APPROVED and (
                publisher.status is not RegisterStatus.APPROVED
            ):
                raise ValueError(
                    f"register {self.version} is approved but {publisher.canonical_name} is not"
                )
            for name in publisher.all_names:
                key = normalise_name(name)
                other = by_name.get(key)
                if other is not None and other is not publisher:
                    raise ValueError(
                        f"{name!r} names both {other.canonical_name} and {publisher.canonical_name}"
                    )
                by_name[key] = publisher
            for host in publisher.hosts:
                for known, other in hosts.items():
                    if _within(host, known) or _within(known, host):
                        raise ValueError(
                            f"{host} ({publisher.canonical_name}) overlaps {known} "
                            f"({other.canonical_name})"
                        )
                hosts[host] = publisher
        object.__setattr__(self, "_by_name", by_name)

    def resolve_publisher(self, name: str) -> Publisher | None:
        """The publisher a declared name variant names, or ``None``. Never a guess."""
        key = normalise_name(name)
        return self._by_name.get(key) if key else None

    def publisher_for_host(self, host: str) -> Publisher | None:
        """The publisher whose declared host is ``host`` or a parent domain of it."""
        normalised = _normalise_host(host)
        if normalised is None:
            return None
        for publisher in self.publishers:
            if any(_within(normalised, declared) for declared in publisher.hosts):
                return publisher
        return None

    def tier_for_url(self, url: str, table: SourceTable) -> SourceTier:
        """A page's tier: the worse of its publisher's and its host's class in ``table``.

        An unknown host is T5 (or EXCLUDED); the register can lower a tier, never raise
        one above what the table says of the host.
        """
        tier = web_tier(url, table)
        publisher = self.publisher_for_host(urlsplit(url).hostname or "")
        return tier if publisher is None else worse_tier(tier, publisher.tier)

    def host_classes(self) -> dict[str, SourceClass]:
        """Every declared host and its publisher's class, for a source table."""
        return {host: p.source_class for p in self.publishers for host in p.hosts}


_P: Final = RegisterStatus.PROPOSED
_OFFICIAL: Final = SourceClass.OFFICIAL_STATISTICS
_GOV: Final = SourceClass.GOVERNMENT_OR_REGULATOR
_INDUSTRY: Final = SourceClass.INDUSTRY_RESEARCH
_MEDIA: Final = SourceClass.MEDIA
_T1: Final = SourceTier.T1
_T2: Final = SourceTier.T2
_T3: Final = SourceTier.T3
_T4: Final = SourceTier.T4

#: The proposed register: publishers that matter to Czech market research.
REPUTATION_REGISTER_V1: Final = ReputationRegister(
    version=REPUTATION_REGISTER_VERSION,
    status=_P,
    publishers=(
        # --- T1: official statistics, the central bank, ministries, regulators, EU
        Publisher(
            "Český statistický úřad",
            ("ČSÚ", "Czech Statistical Office", "CZSO"),
            ("csu.gov.cz", "czso.cz"),
            _OFFICIAL,
            _T1,
            ("datastat",),
        ),
        Publisher(
            # ec.europa.eu is the whole Commission; a host cannot tell Eurostat from it.
            # The source table's path rule still classes /eurostat as statistics.
            "Evropská komise",
            ("European Commission", "EK", "EC", "Eurostat"),
            ("ec.europa.eu",),
            _GOV,
            _T1,
            ("eurostat_api",),
        ),
        Publisher(
            "Evropská centrální banka",
            ("European Central Bank", "ECB"),
            ("ecb.europa.eu",),
            _GOV,
            _T1,
        ),
        Publisher(
            "Česká národní banka",
            ("ČNB", "Czech National Bank", "CNB"),
            ("cnb.cz",),
            _GOV,
            _T1,
            ("arad",),
        ),
        Publisher(
            "Národní katalog otevřených dat",
            ("NKOD", "National Open Data Catalogue", "National Catalogue of Open Data"),
            ("data.gov.cz",),
            _GOV,
            _T1,
            ("nkod_sparql",),
        ),
        Publisher(
            "Ministerstvo zemědělství",
            (
                "Ministerstvo zemědělství ČR",
                "Ministerstvo zemědělství České republiky",
                "MZe",
                "MZe ČR",
                "Ministry of Agriculture of the Czech Republic",
                "Czech Ministry of Agriculture",
                "eAGRI",
            ),
            ("mze.gov.cz", "eagri.cz"),
            _GOV,
            _T1,
        ),
        Publisher(
            "Ministerstvo průmyslu a obchodu",
            (
                "Ministerstvo průmyslu a obchodu ČR",
                "Ministerstvo průmyslu a obchodu České republiky",
                "MPO",
                "MPO ČR",
                "Ministry of Industry and Trade of the Czech Republic",
                "Czech Ministry of Industry and Trade",
            ),
            ("mpo.gov.cz", "mpo.cz"),
            _GOV,
            _T1,
        ),
        Publisher(
            "Ministerstvo financí",
            (
                "Ministerstvo financí ČR",
                "Ministerstvo financí České republiky",
                "MF ČR",
                "MFČR",
                "Ministry of Finance of the Czech Republic",
                "Czech Ministry of Finance",
            ),
            ("mfcr.cz",),
            _GOV,
            _T1,
        ),
        Publisher(
            "Ministerstvo zdravotnictví",
            (
                "Ministerstvo zdravotnictví ČR",
                "Ministerstvo zdravotnictví České republiky",
                "MZ ČR",
                "MZČR",
                "Ministry of Health of the Czech Republic",
                "Czech Ministry of Health",
            ),
            ("mzcr.cz",),
            _GOV,
            _T1,
        ),
        Publisher(
            "Ministerstvo práce a sociálních věcí",
            (
                "Ministerstvo práce a sociálních věcí ČR",
                "Ministerstvo práce a sociálních věcí České republiky",
                "MPSV",
                "MPSV ČR",
                "Ministry of Labour and Social Affairs of the Czech Republic",
                "Czech Ministry of Labour and Social Affairs",
            ),
            ("mpsv.cz",),
            _GOV,
            _T1,
        ),
        Publisher(
            "Státní zemědělská a potravinářská inspekce",
            ("SZPI", "Czech Agriculture and Food Inspection Authority", "CAFIA"),
            ("szpi.gov.cz",),
            _GOV,
            _T1,
        ),
        Publisher(
            "Český telekomunikační úřad",
            ("ČTÚ", "Czech Telecommunication Office", "CTU"),
            ("ctu.gov.cz", "ctu.cz"),
            _GOV,
            _T1,
        ),
        Publisher(
            "Energetický regulační úřad",
            ("ERÚ", "Energy Regulatory Office", "ERO"),
            ("eru.gov.cz", "eru.cz"),
            _GOV,
            _T1,
        ),
        Publisher(
            "Úřad pro ochranu hospodářské soutěže",
            ("ÚOHS", "Office for the Protection of Competition"),
            ("uohs.gov.cz", "uohs.cz"),
            _GOV,
            _T1,
        ),
        # --- T2: international organisations (statistics class, lowered per § 8.7)
        Publisher(
            "OECD",
            (
                "Organisation for Economic Co-operation and Development",
                "Organization for Economic Cooperation and Development",
                "Organizace pro hospodářskou spolupráci a rozvoj",
            ),
            ("oecd.org",),
            _OFFICIAL,
            _T2,
            ("oecd_sdmx",),
        ),
        Publisher(
            "World Bank",
            ("The World Bank", "World Bank Group", "Světová banka"),
            ("worldbank.org",),
            _OFFICIAL,
            _T2,
            ("worldbank_indicators",),
        ),
        # --- T3: industry bodies and associations
        Publisher(
            "Potravinářská komora České republiky",
            ("Potravinářská komora ČR", "PK ČR", "Food Chamber of the Czech Republic"),
            ("foodnet.cz",),
            _INDUSTRY,
            _T3,
        ),
        Publisher(
            "Svaz obchodu a cestovního ruchu České republiky",
            (
                "Svaz obchodu a cestovního ruchu ČR",
                "SOCR",
                "SOCR ČR",
                "Confederation of Commerce and Tourism of the Czech Republic",
            ),
            ("socr.cz",),
            _INDUSTRY,
            _T3,
        ),
        Publisher(
            "Hospodářská komora České republiky",
            (
                "Hospodářská komora ČR",
                "HK ČR",
                "Economic Chamber of the Czech Republic",
                "Czech Chamber of Commerce",
            ),
            ("komora.cz",),
            _INDUSTRY,
            _T3,
        ),
        Publisher(
            "Svaz průmyslu a dopravy České republiky",
            (
                "Svaz průmyslu a dopravy ČR",
                "SP ČR",
                "Confederation of Industry of the Czech Republic",
            ),
            ("spcr.cz",),
            _INDUSTRY,
            _T3,
        ),
        # --- T4: established national media. Generic words ("Novinky", "Deník",
        # "Aktuálně") are not names on their own: they would resolve ordinary text.
        Publisher(
            "Česká televize",
            ("ČT", "ČT24", "Czech Television"),
            ("ceskatelevize.cz",),
            _MEDIA,
            _T4,
        ),
        Publisher(
            "Český rozhlas",
            ("ČRo", "Czech Radio", "iROZHLAS", "iROZHLAS.cz"),
            ("rozhlas.cz", "irozhlas.cz"),
            _MEDIA,
            _T4,
        ),
        Publisher(
            "Česká tisková kancelář",
            ("ČTK", "Czech News Agency"),
            ("ctk.cz",),
            _MEDIA,
            _T4,
        ),
        Publisher(
            "iDNES.cz",
            ("iDNES", "MF DNES", "Mladá fronta DNES"),
            ("idnes.cz",),
            _MEDIA,
            _T4,
        ),
        Publisher(
            "Lidové noviny",
            ("Lidovky.cz", "Lidovky"),
            ("lidovky.cz",),
            _MEDIA,
            _T4,
        ),
        Publisher(
            "Novinky.cz",
            (),
            ("novinky.cz",),
            _MEDIA,
            _T4,
        ),
        Publisher(
            "Seznam Zprávy",
            ("SeznamZprávy.cz",),
            ("seznamzpravy.cz",),
            _MEDIA,
            _T4,
        ),
        Publisher(
            "Hospodářské noviny",
            ("HN", "iHNed.cz", "iHNed"),
            ("hn.cz", "ihned.cz"),
            _MEDIA,
            _T4,
        ),
        Publisher(
            "E15",
            ("E15.cz", "Deník E15"),
            ("e15.cz",),
            _MEDIA,
            _T4,
        ),
        Publisher(
            "Aktuálně.cz",
            (),
            ("aktualne.cz",),
            _MEDIA,
            _T4,
        ),
        Publisher(
            "Deník.cz",
            (),
            ("denik.cz",),
            _MEDIA,
            _T4,
        ),
        Publisher(
            "Echo24",
            ("Echo24.cz", "Týdeník Echo"),
            ("echo24.cz",),
            _MEDIA,
            _T4,
        ),
    ),
)

#: The production table extended with the register's hosts. Proposed and off: nothing
#: names it until the data owner approves the register (plan chunk 23 wires it).
SOURCE_TABLE_REPUTATION_1: Final = SOURCE_TABLE_V1.extended(
    REPUTATION_SOURCE_TABLE_VERSION, REPUTATION_REGISTER_V1.host_classes()
)
