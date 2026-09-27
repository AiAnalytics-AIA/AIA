"""The query classifier: a query is at least as confidential as what it was written from.

Adversarial on purpose. Each case is a way a client term, or confidential text,
gets past a literal check: case, diacritics, transliteration, spacing, punctuation,
and a paraphrase with every keyword removed.
"""

from __future__ import annotations

import pytest

from aia_core.domain.deep_research.classification import (
    NGRAM,
    classify_query,
    fold,
    most_restrictive,
    term_variants,
)
from aia_core.domain.deep_research.contracts import ClientTerm
from aia_core.domain.residency import DataClass

A = DataClass.CLASS_A_CLIENT_CONFIDENTIAL
B = DataClass.CLASS_B_DERIVED_CLIENT
C = DataClass.CLASS_C_INTERNAL

TERMS = (
    ClientTerm(term="Pivovar Kotelna", source="client.name"),
    ClientTerm(term="Müller Nápoje", source="knowledge:KNW-00000000000001@1"),
    ClientTerm(term="ACME", source="client.slug"),
    ClientTerm(term="Projekt Jasan", source="study.name"),
)
CONFIDENTIAL = (
    "Klient plánuje v třetím čtvrtletí zvýšit ceny prémiové řady o dvanáct procent "
    "a stáhnout plechovky z diskontů.",
)


def _classify(text: str, context: DataClass = C) -> tuple[DataClass, tuple[str, ...]]:
    result = classify_query(
        text, context_class=context, client_terms=TERMS, class_a_texts=CONFIDENTIAL
    )
    return result.data_class, result.reasons


def test_a_public_query_from_a_public_context_is_class_c() -> None:
    cls, reasons = _classify("spotřeba rostlinných nápojů Česko 2025 statistika")
    assert cls is C and reasons == ("context:CLASS_C_INTERNAL",)


@pytest.mark.parametrize(
    "query",
    [
        "Pivovar Kotelna tržní podíl",
        "PIVOVAR KOTELNA",
        "pivovar kotelna",
        "Pívovar Kotélna",  # diacritics added
        "pivovar-kotelna.cz recenze",
        "P i v o v a r  K o t e l n a",  # spacing
        "Mueller Napoje Brno",  # German transliteration of Müller Nápoje
        "müller nápoje",
        "acme corp výsledky",
        "a.c.m.e dodavatelé",
        "projekt jasan cenová strategie",
    ],
)
def test_a_client_term_makes_a_query_class_b_however_it_is_written(query: str) -> None:
    cls, reasons = _classify(query)
    assert cls is B, query
    assert any(r.startswith("client_term:") for r in reasons)


def test_a_short_term_matches_whole_words_only() -> None:
    terms = (ClientTerm(term="AB", source="client.slug"),)
    assert (
        classify_query(
            "about the market", context_class=C, client_terms=terms, class_a_texts=()
        ).data_class
        is C
    )
    assert (
        classify_query(
            "AB market share", context_class=C, client_terms=terms, class_a_texts=()
        ).data_class
        is B
    )


def test_a_query_sharing_a_run_of_words_with_class_a_text_is_class_a() -> None:
    cls, reasons = _classify("zvýšit ceny prémiové řady o dvanáct procent konkurence")
    assert cls is A and "class_a_overlap" in reasons
    # Four shared words in a row are not a run of five.
    assert NGRAM == 5
    assert _classify("zvýšit ceny prémiové řady")[0] is C


def test_removing_every_keyword_does_not_downgrade_a_confidential_derivation() -> None:
    # A paraphrase of the client's plan, with no client term and no shared run of
    # words: its class is the class of the context it was written from.
    paraphrase = "prémiové pivo zdražení podzim diskontní řetězce plechovky"
    assert _classify(paraphrase, context=C)[0] is C
    assert _classify(paraphrase, context=A)[0] is A
    assert _classify(paraphrase, context=B)[0] is B


def test_nothing_lowers_a_class_and_a_class_of_nothing_is_refused() -> None:
    assert most_restrictive([C, A, B]) is A
    assert most_restrictive([C, B]) is B
    with pytest.raises(ValueError):
        most_restrictive([])


def test_folding_and_variants() -> None:
    assert fold("Žluťoučký kůň, Straße!") == "zlutoucky kun strasse"
    assert term_variants("Müller") == frozenset({"muller", "mueller"})
    assert term_variants("   ") == frozenset()
