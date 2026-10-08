"""Where each kind of evidence is usually found: hints for the investigator (plan chunk 49).

A researcher who knows the field goes to the office that publishes a number before the
article that repeats it, to the register before the press release, to the study before
its summary. The investigator is told the same, as hints rendered into its prompt from
the reputation register (:mod:`.reputation`): for each kind of evidence a track may need
(:class:`EvidenceNeed`), the publishers the register lists for it, by name.

**A hint is not a route.** It names publishers and kinds of document, never a host, a
URL or a query: the investigator still finds a page by searching or by a link the app
captured, and code still decides what may leave (class, egress, robots.txt, budget). A
name that looks like an address ("iDNES.cz") is left out of the hints rather than shown,
and the press is named as a kind, never by title: it is where a number is repeated, so
the hint is to follow it to its origin. Tested: no hint carries a host or a URL.

The register is **proposed** (its status), so the hints are too; they change with it,
under :data:`PLAYBOOK_VERSION` and the investigator's prompt version.

Pure: stdlib only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from .reputation import Publisher, ReputationRegister
from .sources import SourceClass, SourceTier

__all__ = ["PLAYBOOKS", "PLAYBOOK_VERSION", "EvidenceNeed", "Playbook", "render_playbooks"]

PLAYBOOK_VERSION: Final = "aia-playbooks-1"

#: A name that reads as an address: never shown in a hint.
_ADDRESS_LIKE: Final = re.compile(r"\.[a-z]{2,}\b|/|@|https?:", re.IGNORECASE)
#: At most this many publishers named per kind of evidence.
_PER_NEED: Final = 16


class EvidenceNeed(StrEnum):
    """What a track may need, by where it is usually found."""

    OFFICIAL_STATISTICS = "official_statistics"
    REGULATORS = "regulators"
    REGISTERS = "registers"
    SCHOLARSHIP = "scholarship"
    INDUSTRY = "industry"
    PRESS = "press"


@dataclass(frozen=True, slots=True)
class Playbook:
    """One kind of evidence: what it is, where it is usually found, and how to use it."""

    need: EvidenceNeed
    #: The Czech label the prompt shows.
    label: str
    #: The register's publishers of these classes are named for it (none: a kind only).
    classes: tuple[SourceClass, ...]
    #: Only publishers at this tier or better are named.
    best_tier: SourceTier
    #: What to look for and how, in Czech; names kinds of documents, never an address.
    advice: str
    #: Name the register's publishers for this kind of evidence.
    name_publishers: bool = True


_TIER_ORDER: Final = (SourceTier.T1, SourceTier.T2, SourceTier.T3, SourceTier.T4, SourceTier.T5)

PLAYBOOKS: Final[tuple[Playbook, ...]] = (
    Playbook(
        EvidenceNeed.OFFICIAL_STATISTICS,
        "oficiální statistika",
        (SourceClass.OFFICIAL_STATISTICS,),
        SourceTier.T2,
        "číslo hledej u statistického úřadu, který ho vydává, v jeho tabulce a s metodickou "
        "poznámkou; zahraniční srovnání u mezinárodních statistik, označené jako zahraniční",
    ),
    Playbook(
        EvidenceNeed.REGULATORS,
        "ministerstva, regulátoři a centrální banky",
        (SourceClass.GOVERNMENT_OR_REGULATOR,),
        SourceTier.T1,
        "výroční a tematické zprávy, statistiky trhu, rozhodnutí a jejich odůvodnění",
    ),
    Playbook(
        EvidenceNeed.REGISTERS,
        "veřejné rejstříky",
        (),
        SourceTier.T1,
        "údaje o firmách z obchodního rejstříku a ARES, smlouvy z registru smluv, zakázky z "
        "věstníku veřejných zakázek, datové sady z katalogu otevřených dat; rejstřík říká, "
        "co je zapsáno, ne jak se firmě daří",
        name_publishers=False,
    ),
    Playbook(
        EvidenceNeed.SCHOLARSHIP,
        "odborná literatura",
        (SourceClass.PEER_REVIEWED, SourceClass.ACADEMIC_INSTITUTION),
        SourceTier.T2,
        "recenzované studie a zprávy výzkumných institucí; uveď DOI, znáš-li ho, aby aplikace "
        "ověřila, zda práce nebyla stažena; preprint není recenzovaná studie",
    ),
    Playbook(
        EvidenceNeed.INDUSTRY,
        "oborové svazy a komory",
        (SourceClass.INDUSTRY_RESEARCH,),
        SourceTier.T3,
        "průzkumy a ročenky oboru; uveď, kdo průzkum dělal, na kom a kdy, a ber je jako "
        "pohled oboru, ne jako statistiku",
    ),
    Playbook(
        EvidenceNeed.PRESS,
        "zpravodajství",
        (SourceClass.MEDIA,),
        SourceTier.T4,
        "zprávy číslo obvykle jen opakují -- zjisti z nich, kdo ho vydal, a jdi k němu (odkaz na "
        "zdroj otevři, jinak použij 'ladder'); samotná zpráva je až poslední možnost",
        name_publishers=False,
    ),
)


def _shown_name(publisher: Publisher) -> str | None:
    """The publisher as the hint names it: canonical name, with a short variant if any."""
    if _ADDRESS_LIKE.search(publisher.canonical_name):
        return None
    short = next(
        (n for n in publisher.names if len(n) <= 6 and n.isupper() and not _ADDRESS_LIKE.search(n)),
        None,
    )
    return f"{publisher.canonical_name} ({short})" if short else publisher.canonical_name


def _named(playbook: Playbook, register: ReputationRegister) -> list[str]:
    if not playbook.name_publishers:
        return []
    allowed = set(_TIER_ORDER[: _TIER_ORDER.index(playbook.best_tier) + 1])
    names = []
    for publisher in register.publishers:
        if publisher.source_class in playbook.classes and publisher.tier in allowed:
            shown = _shown_name(publisher)
            if shown is not None:
                names.append(shown)
    return names[:_PER_NEED]


def render_playbooks(register: ReputationRegister) -> str:
    """The hints, in Czech, one line per kind of evidence."""
    lines = [
        "KDE SE DŮKAZY OBVYKLE NACHÁZEJÍ (nápověda, ne pravidlo; co smí opustit aplikaci, "
        "rozhoduje aplikace, a adresy z nápovědy nepiš, hledej je):"
    ]
    for playbook in PLAYBOOKS:
        named = _named(playbook, register)
        where = f" -- např. {', '.join(named)}" if named else ""
        lines.append(f"- {playbook.label}{where}: {playbook.advice}.")
    return "\n".join(lines) + "\n"
