"""Document types (D4): a student thesis is named by declared rules, and nothing else is.

Every address and title here is synthetic, in the shape a rule declares; no real thesis,
student or supervisor is named.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from aia_core.domain.deep_research.document_types import (
    DOCUMENT_RULES_VERSION,
    THESIS_TITLES,
    DocumentType,
    declared_rules,
    document_rules_of,
    document_type,
    title_segments,
)

THESIS = DocumentType.STUDENT_THESIS
UNDETERMINED = DocumentType.UNDETERMINED


@pytest.mark.parametrize(
    ("url", "signal"),
    [
        ("https://theses.cz/id/fiktivni1/", "host:theses.cz"),
        ("https://www.theses.cz/id/fiktivni2/", "host:theses.cz"),
        ("https://vskp.vse.cz/00000_fiktivni-prace", "host:vskp.vse.cz"),
    ],
)
def test_every_page_of_a_thesis_register_is_a_thesis(url: str, signal: str) -> None:
    typed = document_type(url, "Fiktivní záznam")
    assert (typed.type, typed.signal) == (THESIS, signal)
    assert typed.words == f"celý web {signal.removeprefix('host:')} je registr kvalifikačních prací"


@pytest.mark.parametrize(
    ("url", "signal"),
    [
        ("https://is.vse.cz/zp/000001", "path:vse.cz/zp/"),
        ("https://insis.vse.cz/zp/000002/fiktivni.pdf", "path:vse.cz/zp/"),
        ("https://www.vse.cz/zp/000003", "path:vse.cz/zp/"),
        ("https://is.muni.cz/th/fikt1/", "path:is.muni.cz/th/"),
        ("https://IS.MUNI.CZ/TH/fikt2/", "path:is.muni.cz/th/"),
        ("https://is.cuni.cz/webapps/zzp/detail/000004/", "path:is.cuni.cz/webapps/zzp/"),
        (
            "https://www.vutbr.cz/studenti/zav-prace/detail/000005",
            "path:vutbr.cz/studenti/zav-prace/",
        ),
    ],
)
def test_a_thesis_archive_on_a_declared_university_host_is_a_thesis(url: str, signal: str) -> None:
    typed = document_type(url, "")
    assert (typed.type, typed.signal) == (THESIS, signal)
    assert signal.removeprefix("path:") in typed.words


@pytest.mark.parametrize(
    "url",
    [
        # /th/ is a thesis archive on is.muni.cz alone: elsewhere it is, for one, Thai.
        "https://example.com/th/fiktivni-clanek",
        "https://www.muni.cz/th/fiktivni",
        "https://is.cuni.cz/th/fiktivni",
        "https://is.vse.cz/th/fiktivni",
        # A prefix is a whole leading path: /zp/ is not /zpravy/ and needs its host.
        "https://www.vse.cz/zpravy/fiktivni",
        "https://example.cz/zp/000001",
        # A journal on a university host is the host's class, not a thesis.
        "https://polek.vse.cz/fiktivni-clanek",
        "https://www.vutbr.cz/studenti/fiktivni",
    ],
)
def test_an_archive_prefix_counts_only_on_its_declared_host(url: str) -> None:
    assert document_type(url, "Fiktivní článek").type is UNDETERMINED


@pytest.mark.parametrize(
    ("url", "segment"),
    [
        ("https://example.org/x/zaverecne-prace/y", "zaverecne-prace"),
        ("https://example.org/Diplomova-Prace/1", "diplomova-prace"),
        ("https://example.org/archiv/z%C3%A1v%C4%9Bre%C4%8Dn%C3%A1-pr%C3%A1ce", "zaverecna-prace"),
        ("https://example.org/kvalifikacni-prace/", "kvalifikacni-prace"),
        ("https://example.org/a/bakalarska-prace/b", "bakalarska-prace"),
        ("https://example.org/disertacni-prace/1", "disertacni-prace"),
        ("https://example.org/dizertacni-prace/1", "dizertacni-prace"),
    ],
)
def test_a_path_segment_that_names_the_genre_is_a_thesis(url: str, segment: str) -> None:
    typed = document_type(url, "")
    assert (typed.type, typed.signal) == (THESIS, f"segment:{segment}")
    assert typed.words == f"adresa obsahuje část „{segment}“"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.org/blog/diplomova-prace-o-bankach",
        "https://example.org/jak-napsat-bakalarska-prace",
        "https://example.org/files/diplomova-prace.pdf",
        "https://example.org/zaverecneprace/1",
    ],
)
def test_a_slug_containing_a_thesis_word_is_not_a_thesis(url: str) -> None:
    # Segment equality, never a substring: a blog post about writing a thesis is no thesis.
    assert document_type(url, "Fiktivní článek").type is UNDETERMINED


@pytest.mark.parametrize(
    ("title", "phrase"),
    [
        ("Důvěra v banky \u2013 Bakalářská práce", "bakalářská práce"),
        ("DIPLOMOVÁ PRÁCE: Spoření mladých domácností", "diplomová práce"),
        ("Spoření v Česku | Master\u2019s thesis", "master's thesis"),
        ("Bachelor's Thesis / Fiktivní univerzita", "bachelor's thesis"),
        ("Finanční gramotnost - Dizertační práce", "dizertační práce"),
        ("Bankové služby \u2014 bakalárska práca", "bakalárska práca"),
        ("(Rigorózní práce)", "rigorózní práce"),
        ("Dissertation", "dissertation"),
    ],
)
def test_a_title_segment_that_names_the_genre_is_a_thesis(title: str, phrase: str) -> None:
    typed = document_type("https://example.org/a", title)
    assert (typed.type, typed.signal) == (THESIS, f"title:{phrase}")
    assert typed.words == f"název zdroje uvádí „{phrase}“"


@pytest.mark.parametrize(
    "title",
    [
        "Studentka obhájila diplomovou práci o bankách",
        "Bakalářská práce o důvěře v banky",
        "Jak napsat diplomovou práci",
        "Zpráva o trhu \u2013 diplomová",
        "Dissertation abstracts",
        "Spoření e-diplomová práce",
        "",
    ],
)
def test_a_title_names_its_genre_only_as_a_whole_segment(title: str) -> None:
    # A miss is never a false refusal: a title that only mentions a thesis is not one.
    assert document_type("https://example.org/a", title).type is UNDETERMINED


def test_every_declared_title_phrase_is_recognised_as_written() -> None:
    folded = {title_segments(p) for p in THESIS_TITLES}
    assert len(folded) == len(THESIS_TITLES)  # no two phrases fold alike
    for phrase in THESIS_TITLES:
        typed = document_type(None, f"Fiktivní téma \u2013 {phrase}")
        assert (typed.type, typed.signal) == (THESIS, f"title:{phrase}")


def test_the_first_rule_that_fires_names_the_signal() -> None:
    # Register before archive before segment before title.
    assert document_type("https://theses.cz/zp/diplomova-prace", "Bakalářská práce").signal == (
        "host:theses.cz"
    )
    assert document_type("https://is.vse.cz/zp/diplomova-prace", "Bakalářská práce").signal == (
        "path:vse.cz/zp/"
    )
    assert document_type("https://example.org/diplomova-prace", "Bakalářská práce").signal == (
        "segment:diplomova-prace"
    )


@pytest.mark.parametrize(
    ("url", "title"),
    [
        ("https://www.czso.cz/fiktivni", "Spotřeba rostlinných nápojů"),
        (None, None),
        ("", ""),
        ("http://[::1", "Fiktivní článek"),  # an address that does not parse types by title only
        ("not a url", "Fiktivní článek"),
    ],
)
def test_no_rule_is_undetermined_and_says_nothing(url: str | None, title: str | None) -> None:
    typed = document_type(url, title)
    assert (typed.type, typed.signal, typed.words) == (UNDETERMINED, "", "")


def test_an_address_that_does_not_parse_is_still_typed_by_its_title() -> None:
    assert document_type("http://[::1", "Fiktivní téma: Diplomová práce").type is THESIS


@pytest.mark.parametrize(
    "url",
    [
        "https://dspace.cuni.cz/handle/20.500.11956/000000",
        "https://dspace.vutbr.cz/handle/11012/000000",
        "https://repository.example.edu/thesis/000000",
        "https://example.cz/fiktivni-prace.pdf",
    ],
)
def test_the_coverage_limits_stay_undetermined(url: str) -> None:
    """Said plainly in the module and the plan: a repository no rule declares, whose title
    does not name its genre, is not recognised."""
    assert document_type(url, "Fiktivní práce o spoření").type is UNDETERMINED


@pytest.mark.parametrize(
    ("url", "title"),
    [
        # The live route's hits: the article's title alone, then the captured page's.
        ("https://cs.wikipedia.org/wiki/Diplomov%C3%A1_pr%C3%A1ce", "Diplomová práce"),
        (
            "https://cs.wikipedia.org/wiki/Diplomov%C3%A1_pr%C3%A1ce",
            "Diplomová práce \u2013 Wikipedie",
        ),
        (
            "https://cs.wikipedia.org/wiki/Bakal%C3%A1%C5%99sk%C3%A1_pr%C3%A1ce",
            "Bakalářská práce \u2013 Wikipedie",
        ),
        ("https://en.wikipedia.org/wiki/Thesis", "Master's thesis - Wikipedia"),
        ("https://cs.wikipedia.org/wiki/zaverecne-prace", "Fiktivní heslo"),
    ],
)
def test_an_encyclopedia_article_on_the_genre_is_not_a_thesis(url: str, title: str) -> None:
    """An encyclopedia's article about a genre is titled with the genre's name and is no
    thesis: no rule types a page on a declared encyclopedia."""
    typed = document_type(url, title)
    assert (typed.type, typed.signal, typed.words) == (UNDETERMINED, "", "")
    # A host that only ends in the same letters is not the encyclopedia.
    assert document_type("https://notwikipedia.org/a", "Diplomová práce").type is THESIS


def test_a_merge_version_names_the_document_rules_it_applied() -> None:
    assert document_rules_of("aia-merge-3/aia-works-1/x/aia-document-types-1") == (
        "aia-document-types-1"
    )
    # Any later version too: never read as "nobody typed".
    assert document_rules_of("aia-merge-9/aia-document-types-4/y") == "aia-document-types-4"
    assert document_rules_of("aia-merge-1") is None
    assert document_rules_of("aia-merge-2/aia-works-1") is None
    assert document_rules_of("") is None


def test_the_declared_rules_are_the_version_they_name() -> None:
    # A changed rule is a changed version: change DOCUMENT_RULES_VERSION with it, then this pin.
    data = json.dumps(
        {"version": DOCUMENT_RULES_VERSION, "rules": declared_rules()},
        ensure_ascii=False,
        sort_keys=True,
    ).encode()
    assert (DOCUMENT_RULES_VERSION, hashlib.sha256(data).hexdigest()) == (
        "aia-document-types-1",
        "6d9014682eacd97889b835807f84b5e098c36e555379933b3cff4604c8ff98c7",
    )
