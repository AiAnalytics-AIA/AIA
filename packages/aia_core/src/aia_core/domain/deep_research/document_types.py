"""What kind of document a web source is, by declared rules (D4, evaluation finding F1).

The source table scores a host (:mod:`.sources`), and a university's host is an academic
institution for every page on it: a student's bachelor thesis in its information system
scored 0.70 undated and was accepted beside the university's journals (``vse.cz``,
``sources.py``). The owner's D4 (2026-10-17) asks the review to tell document types apart,
starting with a small, tested set of rules. This module is that set, and it names one type:
a **student thesis**, any qualification thesis -- bachelor's, master's, rigorous, a graduate
school's, and, in this version, a doctoral dissertation. The merge quarantines a web finding
from one (``QuarantineReason.STUDENT_THESIS``), as it quarantines a retracted work whatever
its host scores; the source table and its approval do not change.

**The rules, in order; the first that fires names the type** (each declared as data below),
on any host but an encyclopedia's (:data:`ENCYCLOPEDIAS`), which is never typed: its article
about a genre is titled with the genre's name (Czech Wikipedia's ``Diplomová práce``), and the
live search route reads Czech and English Wikipedia.

* a **thesis register**: the whole host is a register of qualification theses
  (:data:`THESIS_REGISTERS`); a host matches itself and its subdomains;
* a **thesis archive** on a declared university host: the path begins with the archive's
  prefix (:data:`THESIS_PATHS`). ``vse.cz`` ``/zp/`` covers ``is.vse.cz`` and
  ``insis.vse.cz``; ``/th/`` is declared on ``is.muni.cz`` alone and never elsewhere, where it
  is, for one, a Thai-language path;
* a **path segment** that names the genre, on any host (:data:`THESIS_SEGMENTS`): a whole
  segment equal to it once accents and case are folded, never a part of one, so
  ``diplomova-prace-o-bankach`` is not a thesis by this rule;
* a **title segment** that names the genre (:data:`THESIS_TITLES`): the source's title, its
  accents, case and apostrophes folded, split on an en or em dash, ``|``, ``:``, ``/`` and
  ``" - "``, has a whole segment equal to a declared phrase -- ``Důvěra v banky | Bakalářská
  práce`` is a thesis, ``Studentka obhájila diplomovou práci o bankách`` and ``Bakalářská
  práce o důvěře v banky`` are not (a miss, never a false refusal).

Nothing else decides, and nothing raises a source: no rule firing is ``UNDETERMINED``, which
says only that these rules did not recognise a thesis.

**Coverage, said plainly.** A thesis on a host or path no rule declares, whose title does not
name its genre, is not recognised: repository hosts (``dspace.cuni.cz``, ``dspace.vutbr.cz``),
``.edu`` repositories and every host not declared here stay ``UNDETERMINED``, and so the
report keeps "může jít i o studentskou práci" beside an academic host. A DOI is not a document
type (repositories mint them for theses), and the page's text and metadata are not read: the
snapshot keeps no ``dc.type``, and a snapshot captured once is reused by its address, so a rule
reading them would type a page by when it was first captured. Company pages and news versus
opinion are the next rules, not this version. The declared URL shapes are the agreed design's
(``research-integrity-report.md`` chunk 11); the tests use synthetic addresses of those shapes.

Pure: stdlib only.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Final
from urllib.parse import unquote, urlsplit

__all__ = [
    "DOCUMENT_RULES_PREFIX",
    "DOCUMENT_RULES_VERSION",
    "ENCYCLOPEDIAS",
    "THESIS_PATHS",
    "THESIS_REGISTERS",
    "THESIS_SEGMENTS",
    "THESIS_TITLES",
    "DocumentType",
    "DocumentTyping",
    "declared_rules",
    "document_rules_of",
    "document_type",
    "title_segments",
]

#: Every version of these rules begins so, and a merge version that carries it typed documents.
DOCUMENT_RULES_PREFIX: Final = "aia-document-types-"
#: The rules' version: a changed rule is a changed version
#: (``test_the_declared_rules_are_the_version_they_name`` holds them together).
DOCUMENT_RULES_VERSION: Final = f"{DOCUMENT_RULES_PREFIX}1"

#: Hosts that are, as a whole, encyclopedias: no rule types a page on them (a host matches
#: itself and its subdomains, ``cs.wikipedia.org`` and ``en.wikipedia.org`` among them).
ENCYCLOPEDIAS: Final = ("wikipedia.org",)
#: Hosts that are, as a whole, registers of qualification theses.
THESIS_REGISTERS: Final = ("theses.cz", "vskp.vse.cz")
#: (university host, path prefix): the thesis archive of a university's information system.
#: Prefixes are lower case and end in ``/``; a path is compared case-folded.
THESIS_PATHS: Final = (
    ("vse.cz", "/zp/"),
    ("is.muni.cz", "/th/"),
    ("is.cuni.cz", "/webapps/zzp/"),
    ("vutbr.cz", "/studenti/zav-prace/"),
)
#: Path segments that name the genre, as folded (no accents, lower case).
THESIS_SEGMENTS: Final = (
    "zaverecne-prace",
    "zaverecna-prace",
    "kvalifikacni-prace",
    "bakalarska-prace",
    "diplomova-prace",
    "disertacni-prace",
    "dizertacni-prace",
)
#: Title phrases that name the genre, as written: Czech, English, Slovak. A title matches
#: when one of its segments equals a phrase once both are folded.
THESIS_TITLES: Final = (
    "bakalářská práce",
    "diplomová práce",
    "disertační práce",
    "dizertační práce",
    "rigorózní práce",
    "absolventská práce",
    "závěrečná práce",
    "bachelor thesis",
    "bachelor's thesis",
    "master thesis",
    "master's thesis",
    "diploma thesis",
    "doctoral thesis",
    "dissertation",
    "bakalárska práca",
    "diplomová práca",
)
#: What splits a folded title into segments: a dash, a bar, a colon, a slash, a spaced hyphen.
TITLE_SEPARATORS: Final = "[\u2013\u2014|:/]| - "
#: What a segment is stripped of at its edges before it is compared.
SEGMENT_EDGES: Final = " .,;!?()[]{}\"'„“”«»…*-"

_SEPARATORS: Final = re.compile(TITLE_SEPARATORS)
#: Apostrophes a title may write ``bachelor's`` with, read as one.
_APOSTROPHES: Final = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'", "`": "'"})


class DocumentType(StrEnum):
    #: A qualification thesis: bachelor's, master's, rigorous, a graduate school's, doctoral.
    STUDENT_THESIS = "STUDENT_THESIS"
    #: No rule fired: these rules did not recognise a thesis, which says nothing more.
    UNDETERMINED = "UNDETERMINED"


@dataclass(frozen=True, slots=True)
class DocumentTyping:
    """A source's type and the rule that named it."""

    type: DocumentType
    #: The rule that fired, as ``<rule>:<what it matched, as declared>`` (``host:theses.cz``,
    #: ``path:is.muni.cz/th/``, ``segment:diplomova-prace``, ``title:bakalářská práce``);
    #: empty when none did.
    signal: str = ""
    #: The same in Czech words, for a reader; empty when no rule fired.
    words: str = ""


def _fold(text: str) -> str:
    """Accents, case, apostrophes and runs of whitespace folded away."""
    decomposed = unicodedata.normalize("NFKD", text.translate(_APOSTROPHES))
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(plain.casefold().split())


_TITLES: Final = {_fold(phrase): phrase for phrase in THESIS_TITLES}


def title_segments(title: str | None) -> tuple[str, ...]:
    """A title's segments as the title rule compares them: folded, split, edges stripped."""
    if not title:
        return ()
    parts = (part.strip(SEGMENT_EDGES) for part in _SEPARATORS.split(_fold(title)))
    return tuple(part for part in parts if part)


def _on_host(host: str, rule: str) -> bool:
    return host == rule or host.endswith("." + rule)


def _url_parts(url: str | None) -> tuple[str, str]:
    """The host (lower case) and the decoded path; empty for no URL or one that does not
    parse, so only the title can type it."""
    if not url:
        return "", ""
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").rstrip(".")
    except ValueError:
        return "", ""
    return host, unquote(parts.path)


def document_type(url: str | None, title: str | None) -> DocumentTyping:
    """The type of the source at ``url`` titled ``title``: the first rule that fires names it."""
    host, path = _url_parts(url)
    if any(_on_host(host, encyclopedia) for encyclopedia in ENCYCLOPEDIAS):
        return DocumentTyping(DocumentType.UNDETERMINED)
    if host:
        for register in THESIS_REGISTERS:
            if _on_host(host, register):
                return DocumentTyping(
                    DocumentType.STUDENT_THESIS,
                    f"host:{register}",
                    f"celý web {register} je registr kvalifikačních prací",
                )
        folded_path = path.casefold()
        for rule_host, prefix in THESIS_PATHS:
            if _on_host(host, rule_host) and folded_path.startswith(prefix):
                return DocumentTyping(
                    DocumentType.STUDENT_THESIS,
                    f"path:{rule_host}{prefix}",
                    f"adresa vede do archivu kvalifikačních prací {rule_host}{prefix}",
                )
    for segment in (_fold(s) for s in path.split("/")):
        if segment in THESIS_SEGMENTS:
            return DocumentTyping(
                DocumentType.STUDENT_THESIS,
                f"segment:{segment}",
                f"adresa obsahuje část „{segment}“",
            )
    for segment in title_segments(title):
        phrase = _TITLES.get(segment)
        if phrase is not None:
            return DocumentTyping(
                DocumentType.STUDENT_THESIS,
                f"title:{phrase}",
                f"název zdroje uvádí „{phrase}“",
            )
    return DocumentTyping(DocumentType.UNDETERMINED)


def document_rules_of(merge_rules_version: str) -> str | None:
    """The document rules a merge under ``merge_rules_version`` applied, or ``None`` when it
    applied none: any version of them, so a later one never reads as "nobody typed"."""
    return next(
        (part for part in merge_rules_version.split("/") if part.startswith(DOCUMENT_RULES_PREFIX)),
        None,
    )


def declared_rules() -> dict[str, object]:
    """The rules as declared, for their pin: encyclopedias, registers, archives, segments,
    titles, splitting."""
    return {
        "encyclopedias": list(ENCYCLOPEDIAS),
        "registers": list(THESIS_REGISTERS),
        "paths": [list(rule) for rule in THESIS_PATHS],
        "segments": list(THESIS_SEGMENTS),
        "titles": list(THESIS_TITLES),
        "title_separators": TITLE_SEPARATORS,
        "segment_edges": SEGMENT_EDGES,
    }
