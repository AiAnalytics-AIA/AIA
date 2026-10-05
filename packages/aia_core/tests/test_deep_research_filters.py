"""Code filters: duplicates collapsed, languages told apart, candidates ranked -- measured.

The measured half runs every filter over a hand-labelled fictional corpus
(``fixtures/deep_research_filters/corpus.json``: 44 documents, four questions) and pins
what it found. A change to the filters that moves a number moves it here, visibly.
"""

from __future__ import annotations

import itertools
import json
import os
import random
import subprocess
import sys
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.deep_research.filters import (
    DEFAULT_LANGUAGES,
    FILTERS_VERSION,
    MIN_LANGUAGE_TOKENS,
    DuplicateKind,
    FilterCandidate,
    Language,
    NearDuplicateConfig,
    RemovalReason,
    bm25_scores,
    content_key,
    detect_language,
    exact_duplicate_clusters,
    filter_candidates,
    fold_text,
    minhash_signature,
    near_duplicate_clusters,
    relevance_terms,
    shingles,
    stem,
)

CORPUS_PATH = Path(__file__).parent / "fixtures" / "deep_research_filters" / "corpus.json"


@cache
def _corpus() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    return data


def _documents() -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = _corpus()["documents"]
    return documents


def _candidates() -> list[FilterCandidate]:
    return [FilterCandidate(d["id"], d["text"]) for d in _documents()]


def _questions() -> dict[str, str]:
    return {q["id"]: q["text"] for q in _corpus()["questions"]}


LONG_CS = (
    "Trh rostlinných nápojů v Česku loni vzrostl o čtrnáct procent a podle smyšlené agentury "
    "bude růst i letos, protože je kupuje stále více domácností ve velkých městech."
)


# --- text and exact duplicates ------------------------------------------------------


def test_the_version_is_named() -> None:
    assert FILTERS_VERSION == "aia-dr-filters-1"


def test_folding_ignores_case_diacritics_spacing_and_typographic_forms() -> None:
    assert (
        fold_text("  Spotřeba\u00a0\u201eRostlinných\u201c  NÁPOJŮ ")
        == 'spotreba "rostlinnych" napoju'
    )


def test_the_exact_key_ignores_case_diacritics_spacing_and_punctuation_only() -> None:
    base = content_key("Trh rostlinných nápojů vzrostl o 14 %.")
    assert content_key("TRH  rostlinnych napoju\nvzrostl o 14 % !") == base
    assert content_key("Trh rostlinných nápojů vzrostl o 15 %.") != base
    assert content_key("Trh nápojů rostlinných vzrostl o 14 %.") != base


def test_exact_clusters_keep_the_best_priority_and_put_unknown_last() -> None:
    clusters = exact_duplicate_clusters(
        [
            FilterCandidate("a", "Stejný text.", priority=None),
            FilterCandidate("b", "STEJNÝ text", priority=3),
            FilterCandidate("c", "stejny text", priority=2),
            FilterCandidate("d", "Jiný text."),
        ]
    )
    assert len(clusters) == 1
    (cluster,) = clusters
    assert cluster.kind is DuplicateKind.EXACT
    assert cluster.members == ("a", "b", "c")
    assert cluster.representative == "c"  # tier 2 beats tier 3; unknown is never best


def test_without_priorities_the_lowest_id_represents() -> None:
    (cluster,) = exact_duplicate_clusters(
        [FilterCandidate("z", "Stejný text."), FilterCandidate("m", "Stejný text.")]
    )
    assert cluster.representative == "m"


# --- shingles, MinHash, near duplicates -----------------------------------------------


def test_shingles_of_short_and_empty_texts() -> None:
    assert len(shingles("jedna dvě tři", k=5)) == 1
    assert shingles(" .,; ", k=5) == frozenset()
    assert len(shingles("a b c d e f g", k=5)) == 3


def test_a_signature_is_fixed_by_its_seed_and_refuses_no_shingles() -> None:
    values = shingles(LONG_CS)
    first = minhash_signature(values, 64)
    assert first == minhash_signature(sorted(values, reverse=True), 64)
    assert len(first) == 64
    with pytest.raises(ValueError, match="at least one shingle"):
        minhash_signature([], 64)


_PROBE = """
import json, sys
from aia_core.domain.deep_research.filters import (
    FilterCandidate, filter_candidates, minhash_signature, shingles)
text, docs, question = json.loads(sys.stdin.read())
result = filter_candidates(
    [FilterCandidate(i, t) for i, t in docs], question, max_keep=5)
print(json.dumps([list(minhash_signature(shingles(text))), repr(result)]))
"""


def test_signatures_and_results_are_the_same_in_every_process() -> None:
    docs = [(d["id"], d["text"]) for d in _documents()]
    question = _questions()["q1"]
    expected = [
        list(minhash_signature(shingles(LONG_CS))),
        repr(filter_candidates([FilterCandidate(i, t) for i, t in docs], question, max_keep=5)),
    ]
    for seed in ("0", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": os.pathsep.join(sys.path)}
        completed = subprocess.run(
            [sys.executable, "-c", _PROBE],
            input=json.dumps([LONG_CS, docs, question]),
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        assert json.loads(completed.stdout) == expected


def test_near_duplicate_config_is_validated() -> None:
    with pytest.raises(ValueError, match="multiple of bands"):
        NearDuplicateConfig(num_hashes=64, bands=10)
    with pytest.raises(ValueError, match="threshold"):
        NearDuplicateConfig(threshold=0.0)
    with pytest.raises(ValueError, match="shingle_words"):
        NearDuplicateConfig(shingle_words=0)
    assert NearDuplicateConfig().rows == 4


def test_a_near_copy_collapses_and_a_different_text_does_not() -> None:
    copy = "Praha (Zpravodaj) \u2013 " + LONG_CS
    other = (
        "Ceny domácích kávovarů letos klesly v průměru o osm procent, ukazuje srovnání "
        "smyšleného portálu, protože výrobci uvedli na trh nové modely."
    )
    clusters = near_duplicate_clusters(
        [
            FilterCandidate("b", copy, priority=1),
            FilterCandidate("a", LONG_CS),
            FilterCandidate("c", other),
        ],
        NearDuplicateConfig(threshold=0.7),
    )
    assert len(clusters) == 1
    assert clusters[0].kind is DuplicateKind.NEAR
    assert clusters[0].members == ("a", "b")
    assert clusters[0].representative == "b"  # a known tier beats a lower id
    assert 0.7 <= clusters[0].min_similarity < 1.0


def test_near_duplicate_ids_must_be_unique() -> None:
    with pytest.raises(ValueError, match="unique"):
        near_duplicate_clusters([FilterCandidate("a", "x"), FilterCandidate("a", "y")])


# --- language -------------------------------------------------------------------------


def test_a_text_too_short_is_unknown() -> None:
    guess = detect_language("Trh rostlinných nápojů v Česku roste")
    assert guess.tokens < MIN_LANGUAGE_TOKENS
    assert guess.language is Language.UNKNOWN
    assert guess.confidence == 0.0


@pytest.mark.parametrize(
    ("text", "language"),
    [
        (LONG_CS, Language.CS),
        (
            "Trh rastlinných nápojov na Slovensku vlani vzrástol, podľa agentúry sú "
            "najobľúbenejšie ovsené nápoje, ktoré si kupuje štvrtina domácností.",
            Language.SK,
        ),
        (
            "The market for plant-based drinks grew last year, and the agency expects that "
            "it will keep growing in large cities.",
            Language.EN,
        ),
        (
            "Der Markt für pflanzliche Getränke ist im letzten Jahr gewachsen und die meisten "
            "Käufer leben in großen Städten.",
            Language.OTHER,
        ),
        (
            "Sprzedaż rowerów elektrycznych w polskich miastach wzrosła w zeszłym roku o "
            "jedną piątą, najwięcej w Warszawie.",
            Language.OTHER,
        ),
        # Only words Czech and Slovak share: the heuristic cannot tell, and says so.
        ("A to je tak, že na to v tom kde po od za tom až.", Language.UNKNOWN),
    ],
)
def test_languages_are_told_apart(text: str, language: Language) -> None:
    assert detect_language(text).language is language


def test_confidence_is_a_share_and_names_its_evidence() -> None:
    guess = detect_language(LONG_CS)
    assert 0.0 < guess.confidence <= 1.0
    assert guess.czech_evidence > 0
    assert guess.slovak_evidence == 0
    assert guess.english_words == 0


# --- relevance ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("trhu", "trh"),
        ("trhy", "trh"),
        ("trh", "trh"),
        ("ceny", "cen"),
        ("cenou", "cen"),
        ("cena", "cen"),
        ("prices", "pric"),
        ("price", "pric"),
        ("elektrokola", "elektrok"),
        ("2025", "2025"),
    ],
)
def test_the_light_stemmer(word: str, expected: str) -> None:
    assert stem(word) == expected


def test_relevance_terms_drop_stopwords_of_all_three_languages() -> None:
    assert relevance_terms("Trh je v Česku a the market is in Czechia") == [
        "trh",
        "cesk",
        "market",
        "czechi",
    ]
    # "být" folds to "byt" (a flat), which stays a word.
    assert relevance_terms("ceny bytů a byt") == ["cen", "byt", "byt"]


def test_bm25_scores_nothing_without_a_shared_term_and_ties_by_id() -> None:
    scores = bm25_scores(
        "kávovary", {"b": "Kávovary zlevnily.", "a": "Kávovary zlevnily.", "c": "Počasí."}
    )
    assert scores["a"] == scores["b"] > 0.0
    assert scores["c"] == 0.0
    assert bm25_scores("cokoli", {}) == {}
    result = filter_candidates(
        [
            FilterCandidate("b", "Kávovary zlevnily o osm procent podle srovnání cen v obchodech."),
            FilterCandidate("a", "Kávovary zlevnily o osm procent podle srovnání cen na webu."),
        ],
        "kávovary",
        max_keep=2,
    )
    assert [k.id for k in result.kept] == ["a", "b"]


# --- the stage ------------------------------------------------------------------------


def test_the_stage_says_what_it_removed_and_why() -> None:
    result = filter_candidates(_candidates(), _questions()["q1"], max_keep=10)
    assert result.version == FILTERS_VERSION
    assert result.received == 44
    assert result.counts() == {
        "empty_text": 1,
        "exact_duplicate": 3,
        "near_duplicate": 4,
        "language": 2,
        "below_cutoff": 24,
        "kept": 10,
    }
    assert result.removed_ids(RemovalReason.EMPTY_TEXT) == ("x11",)
    assert set(result.removed_ids(RemovalReason.EXACT_DUPLICATE)) == {"c02", "p02", "p03"}
    assert result.removed_ids(RemovalReason.NEAR_DUPLICATE) == ("c03", "e02", "g02", "p04")
    assert set(result.removed_ids(RemovalReason.LANGUAGE)) == {"x07", "x08"}
    near = next(r for r in result.removed if r.id == "p04")
    assert near.duplicate_of == "p01"
    german = next(r for r in result.removed if r.id == "x07")
    assert german.language is Language.OTHER
    kept = {k.id: k for k in result.kept}
    assert kept["p01"].absorbed == ("p02", "p03", "p04")
    assert [k.rank for k in result.kept] == list(range(1, 11))
    cut = [r for r in result.removed if r.reason is RemovalReason.BELOW_CUTOFF]
    assert all(r.score is not None and r.score <= result.kept[-1].score for r in cut)
    assert {c.kind for c in result.clusters} == {DuplicateKind.EXACT, DuplicateKind.NEAR}


def test_the_stage_is_independent_of_input_order() -> None:
    candidates = _candidates()
    question = _questions()["q2"]
    expected = filter_candidates(candidates, question, max_keep=12)
    shuffled = list(candidates)
    random.Random(7).shuffle(shuffled)
    assert filter_candidates(shuffled, question, max_keep=12) == expected


def test_the_stage_refuses_a_negative_cutoff_and_repeated_ids() -> None:
    with pytest.raises(ValueError, match="max_keep"):
        filter_candidates([], "q", max_keep=-1)
    with pytest.raises(ValueError, match="unique"):
        filter_candidates([FilterCandidate("a", "x"), FilterCandidate("a", "y")], "q", max_keep=1)


def test_keeping_nothing_cuts_everything_and_languages_are_the_callers() -> None:
    result = filter_candidates(_candidates(), _questions()["q3"], max_keep=0)
    assert result.kept == ()
    assert result.counts()["below_cutoff"] == 44 - 1 - 3 - 4 - 2
    english_only = filter_candidates(
        _candidates(), _questions()["q3"], max_keep=50, languages=frozenset({Language.EN})
    )
    assert {k.language.language for k in english_only.kept} == {Language.EN}
    assert Language.OTHER not in DEFAULT_LANGUAGES
    assert Language.UNKNOWN in DEFAULT_LANGUAGES


# --- measured on the fictional corpus ---------------------------------------------------


def _pairwise(threshold: float) -> tuple[int, int, int]:
    """True positives, false positives and false negatives over every pair of
    non-empty documents: "the same text" (exact or near) predicted vs labelled."""
    candidates = [c for c in _candidates() if c.text.strip()]
    clusters = near_duplicate_clusters(candidates, NearDuplicateConfig(threshold=threshold))
    predicted = {member: c.representative for c in clusters for member in c.members}
    labelled = {d["id"]: d["dup_group"] for d in _documents() if d["dup_group"]}
    tp = fp = fn = 0
    for a, b in itertools.combinations(sorted(c.id for c in candidates), 2):
        same = a in labelled and labelled[a] == labelled.get(b)
        found = a in predicted and predicted[a] == predicted.get(b)
        tp += same and found
        fp += found and not same
        fn += same and not found
    return tp, fp, fn


def test_measured_exact_duplicates() -> None:
    clusters = exact_duplicate_clusters([c for c in _candidates() if c.text.strip()])
    assert [c.members for c in clusters] == [("c01", "c02"), ("p01", "p02", "p03")]


def test_measured_near_duplicates_at_the_default_threshold() -> None:
    # 24 labelled pairs. Precision 11/11 = 1.0, recall 11/24 = 0.458: the default 0.8
    # finds the exact copies, a dateline copy and a two-edit copy, and misses a credit
    # line swapped for the boilerplate, a cut sentence, two edited words, the rewrite.
    assert _pairwise(0.8) == (11, 0, 13)


def test_measured_near_duplicates_at_0_7() -> None:
    # Precision 19/19 = 1.0, recall 19/24 = 0.792; the five misses are all the
    # heavy rewrite (p06), which shares no 5-word shingle with its original.
    assert _pairwise(0.7) == (19, 0, 5)
    # The hard negative shares a 25-word boilerplate paragraph with two others.
    assert all(
        "g07" not in c.members
        for c in near_duplicate_clusters(_candidates(), NearDuplicateConfig(threshold=0.5))
    )


def test_measured_language_accuracy() -> None:
    wrong = [
        (d["id"], d["lang"], detect_language(d["text"]).language.value)
        for d in _documents()
        if detect_language(d["text"]).language.value != d["lang"]
    ]
    # 44 of 44 (cs 25, sk 6, en 7, other 2, unknown 4). Tuned on this corpus: an
    # upper bound, not an estimate.
    assert wrong == []


def _relevance(question_id: str) -> tuple[int, int, int]:
    """Relevant survivors, relevant in the top R (R-precision's numerator), relevant
    in the top 10, under the default languages."""
    relevant = {d["id"] for d in _documents() if question_id in d["relevant_to"]}
    result = filter_candidates(_candidates(), _questions()[question_id], max_keep=100)
    ranked = [k.id for k in result.kept]
    surviving = [i for i in ranked if i in relevant]
    r = len(surviving)
    return (
        r,
        sum(1 for i in ranked[:r] if i in relevant),
        sum(1 for i in ranked[:10] if i in relevant),
    )


@pytest.mark.parametrize(
    ("question_id", "measured"),
    [
        # (relevant survivors, relevant in top R, relevant in top 10)
        ("q1", (5, 5, 5)),  # plant drinks: R-precision 1.0
        ("q2", (5, 4, 5)),  # e-bikes: 0.8 -- the headline "Elektrokola: ceny 2025" ranks below
        ("q3", (4, 4, 4)),  # coffee machines: 1.0
        ("q4", (5, 5, 5)),  # grocery delivery: 1.0
    ],
)
def test_measured_relevance(question_id: str, measured: tuple[int, int, int]) -> None:
    assert _relevance(question_id) == measured
