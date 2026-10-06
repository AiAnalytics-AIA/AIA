"""Code filters: the funnel's Filter stage, from many candidates to a ranked few.

``.planning/plans/deep-research-web-search.md`` § 5.1 (Filter) and § 8.5 (independence
is by publisher *after* near-duplicate collapse), chunk 19. Nothing here reads a page,
calls a model or decides what is true; it decides which captured candidates are worth a
reader's time, and it says why each of the others was set aside.

:func:`filter_candidates` applies, in order:

1. **Empty text** -- a candidate with no word in it is removed (``empty_text``).
2. **Exact duplicates** -- :func:`content_key`, a SHA-256 over :func:`fold_text`'s
   words: case, diacritics, punctuation and spacing are ignored, so a copy re-typed
   without háčky or with other quotation marks is the same text. One survives per
   key; the rest are ``exact_duplicate`` of it.
3. **Near-duplicates** -- word ``k``-shingles (default 5), MinHash over a fixed,
   seeded hash family (``blake2b`` keyed with :data:`_SEED`, never Python's
   per-process ``hash()``), banded LSH for candidate pairs, then the *exact* Jaccard
   of each candidate pair against the threshold (default 0.8). Clusters are the
   connected components of the pairs that pass (single linkage: A~B and B~C put A
   and C together even when A and C alone would not). MinHash only proposes pairs;
   it never decides one, so a false LSH match costs a set comparison, never a
   wrong collapse. Removed: ``near_duplicate`` of the cluster's representative.
4. **Language** -- :func:`detect_language` (``cs``, ``sk``, ``en``, ``other``,
   ``unknown``); a language outside the allowed set is removed (``language``).
5. **Relevance** -- :func:`bm25_scores` of each survivor against the sub-question;
   the top ``max_keep`` are kept, ties broken by id; the rest are ``below_cutoff``.
   A score of 0 (no shared term) is ranked, not removed: a Czech question shares no
   word with a relevant English page, and the cut-off, not a zero, decides.

**The representative** of a duplicate group is the member with the lowest
``priority`` (a source tier: 1 is best), then the lowest id. A candidate without a
priority sorts after every candidate with one: unknown is never ranked as good.

**Deterministic and order-independent.** Candidates are processed sorted by id; every
hash is keyed and fixed; floating-point sums run in a fixed order. The same input in
any order, in any process, gives the same result.

**Limits, stated plainly.**

* The language heuristic counts function words and characteristic letters. Under
  :data:`MIN_LANGUAGE_TOKENS` words it says ``unknown``; it cannot separate Czech from
  Slovak in a text that uses only the words they share; a Polish page reads ``other``
  by its letters, but a Slovene or Croatian one may read ``unknown`` or even ``cs``;
  a page mixing two languages gets the one with more function words. Its thresholds
  were set on the fictional corpus it is measured on
  (``tests/fixtures/deep_research_filters``), so that corpus's 100 % is an upper bound.
* The stemmer is a light, fixed-rule normaliser, not a morphological analyser: it
  conflates words that share their first eight letters after an ending is cut, and misses
  inflections that change the stem (``pes``/``psa``, ``prodej``/``prodává``).
* BM25 is lexical: synonyms and translations score nothing. Relevance across
  languages needs the question phrased in each language the caller allows.
* Near-duplicate detection compares word shingles; on a short text a single edited
  word removes up to ``k`` shingles, so the threshold is harsh below ~100 words, and
  a heavy rewrite of the same press release is not a near-duplicate here. On the
  fictional corpus, syndicated copies of 55-105 words with a dateline, a credit line
  or two edited words sit at Jaccard 0.71-0.88: the default 0.8 finds under half of
  the labelled pairs, 0.7 every one but the rewrite, both with no false pair (the
  test pins both). The default stays 0.8 until a decision lowers it.
* Exact-duplicate keys ignore punctuation, so ``12,5`` and ``12.5`` fold alike.

Pure: stdlib only.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from .grounding import normalise_text

__all__ = [
    "BM25_B",
    "BM25_K1",
    "DEFAULT_LANGUAGES",
    "FILTERS_VERSION",
    "MIN_LANGUAGE_TOKENS",
    "DuplicateCluster",
    "DuplicateKind",
    "FilterCandidate",
    "FilterResult",
    "KeptCandidate",
    "Language",
    "LanguageGuess",
    "NearDuplicateConfig",
    "RemovalReason",
    "Removed",
    "bm25_scores",
    "content_key",
    "detect_language",
    "exact_duplicate_clusters",
    "filter_candidates",
    "fold_text",
    "minhash_signature",
    "near_duplicate_clusters",
    "relevance_terms",
    "shingles",
    "stem",
    "words",
]

#: The filters' version; part of any fingerprint that depends on what they kept.
FILTERS_VERSION: Final = "aia-dr-filters-1"

# --- text -----------------------------------------------------------------------

_WORD: Final = re.compile(r"\w+")
_LETTERS: Final = re.compile(r"[^\W\d_]+")


def fold_text(text: str) -> str:
    """``normalise_text``, then case-folded and stripped of diacritics.

    The form duplicates and relevance are compared in: ``Spotřeba`` and ``spotreba``
    are one word here. (A quote is still matched verbatim, by :mod:`.grounding`.)
    """
    decomposed = unicodedata.normalize("NFD", normalise_text(text).casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def words(text: str) -> list[str]:
    """The folded words of ``text`` (letters and digits; punctuation dropped)."""
    return _WORD.findall(fold_text(text))


def content_key(text: str) -> str:
    """The exact-duplicate key: SHA-256 of the folded words joined by one space."""
    return hashlib.sha256(" ".join(words(text)).encode("utf-8")).hexdigest()


# --- candidates and results -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FilterCandidate:
    """One captured candidate: a stable id, its text, and an optional priority.

    ``priority`` orders the choice of a duplicate group's representative (a source
    tier: lower is better). ``None`` is unknown and sorts after every known value.
    """

    id: str
    text: str
    priority: int | None = None


def _representative_key(candidate: FilterCandidate) -> tuple[int, int, str]:
    if candidate.priority is None:
        return (1, 0, candidate.id)
    return (0, candidate.priority, candidate.id)


class DuplicateKind(StrEnum):
    EXACT = "exact"
    NEAR = "near"


@dataclass(frozen=True, slots=True)
class DuplicateCluster:
    """Candidates that are one text: the representative kept, every member listed.

    ``min_similarity`` is the lowest Jaccard of the pairs that linked the cluster
    (1.0 for an exact cluster).
    """

    kind: DuplicateKind
    representative: str
    members: tuple[str, ...]
    min_similarity: float


class RemovalReason(StrEnum):
    EMPTY_TEXT = "empty_text"
    EXACT_DUPLICATE = "exact_duplicate"
    NEAR_DUPLICATE = "near_duplicate"
    LANGUAGE = "language"
    BELOW_CUTOFF = "below_cutoff"


@dataclass(frozen=True, slots=True)
class Removed:
    """A candidate set aside, and why. ``duplicate_of`` names the survivor it folded
    into (duplicates only); ``language`` is set for a language removal; ``score``
    for a cut-off."""

    id: str
    reason: RemovalReason
    duplicate_of: str | None = None
    language: Language | None = None
    score: float | None = None


# --- exact and near duplicates ------------------------------------------------------


def exact_duplicate_clusters(candidates: Sequence[FilterCandidate]) -> tuple[DuplicateCluster, ...]:
    """Groups of two or more candidates with the same :func:`content_key`."""
    groups: dict[str, list[FilterCandidate]] = defaultdict(list)
    for candidate in sorted(candidates, key=lambda c: c.id):
        groups[content_key(candidate.text)].append(candidate)
    clusters = [
        DuplicateCluster(
            kind=DuplicateKind.EXACT,
            representative=min(group, key=_representative_key).id,
            members=tuple(c.id for c in group),
            min_similarity=1.0,
        )
        for group in groups.values()
        if len(group) > 1
    ]
    return tuple(sorted(clusters, key=lambda c: c.representative))


@dataclass(frozen=True, slots=True)
class NearDuplicateConfig:
    """Shingle length, MinHash size, LSH banding and the Jaccard threshold.

    With the defaults (64 hashes in 16 bands of 4 rows) a pair at Jaccard 0.8
    becomes an LSH candidate with probability 1 - (1 - 0.8**4)**16 ≈ 0.9998; at
    0.5, ≈ 0.64 -- false candidates cost only an exact comparison.
    """

    shingle_words: int = 5
    num_hashes: int = 64
    bands: int = 16
    threshold: float = 0.8

    def __post_init__(self) -> None:
        if self.shingle_words < 1:
            raise ValueError("shingle_words must be at least 1")
        if self.bands < 1 or self.num_hashes % self.bands != 0:
            raise ValueError("num_hashes must be a positive multiple of bands")
        if not 0.0 < self.threshold <= 1.0:
            raise ValueError("threshold must be in (0, 1]")

    @property
    def rows(self) -> int:
        return self.num_hashes // self.bands


#: The fixed key of every hash here. Changing it changes every signature: bump
#: :data:`FILTERS_VERSION` with it.
_SEED: Final = b"aia-dr-filters-minhash-1"
_PRIME: Final = (1 << 61) - 1  # a Mersenne prime above every 61-bit residue


def _hash64(value: str, salt: str = "") -> int:
    digest = hashlib.blake2b(
        value.encode("utf-8"), digest_size=8, key=_SEED, salt=salt.encode("ascii")[:16]
    ).digest()
    return int.from_bytes(digest, "big")


_PERMUTATIONS: dict[int, tuple[tuple[int, int], ...]] = {}


def _permutations(count: int) -> tuple[tuple[int, int], ...]:
    """``count`` universal-hash parameters ``(a, b)``, derived from the seed only."""
    cached = _PERMUTATIONS.get(count)
    if cached is None:
        cached = tuple(
            (
                _hash64(str(i), salt="a") % (_PRIME - 1) + 1,
                _hash64(str(i), salt="b") % _PRIME,
            )
            for i in range(count)
        )
        _PERMUTATIONS[count] = cached
    return cached


def shingles(text: str, k: int = 5) -> frozenset[int]:
    """The 64-bit hashes of ``text``'s folded ``k``-word shingles.

    A text shorter than ``k`` words is one shingle; a text with no word has none.
    (Two different shingles colliding in 64 bits is negligible at any corpus size
    this stage sees.)
    """
    tokens = words(text)
    if not tokens:
        return frozenset()
    if len(tokens) <= k:
        return frozenset({_hash64(" ".join(tokens))})
    return frozenset(_hash64(" ".join(tokens[i : i + k])) for i in range(len(tokens) - k + 1))


def minhash_signature(shingle_hashes: Iterable[int], num_hashes: int = 64) -> tuple[int, ...]:
    """The MinHash signature: per permutation ``(a*x + b) mod p``, its minimum."""
    values = sorted({x % _PRIME for x in shingle_hashes})
    if not values:
        raise ValueError("a signature needs at least one shingle")
    return tuple(min((a * x + b) % _PRIME for x in values) for a, b in _permutations(num_hashes))


def _jaccard(left: frozenset[int], right: frozenset[int]) -> float:
    union = len(left | right)
    return len(left & right) / union if union else 0.0


def near_duplicate_clusters(
    candidates: Sequence[FilterCandidate], config: NearDuplicateConfig | None = None
) -> tuple[DuplicateCluster, ...]:
    """Clusters of near-duplicates: LSH proposes, exact Jaccard >= threshold decides."""
    config = config or NearDuplicateConfig()
    ordered = sorted(candidates, key=lambda c: c.id)
    by_id = {c.id: c for c in ordered}
    if len(by_id) != len(ordered):
        raise ValueError("candidate ids must be unique")
    sets = {c.id: shingles(c.text, config.shingle_words) for c in ordered}
    buckets: dict[tuple[int, tuple[int, ...]], list[str]] = defaultdict(list)
    for cid, shingle_set in sets.items():
        if not shingle_set:
            continue
        signature = minhash_signature(shingle_set, config.num_hashes)
        for band in range(config.bands):
            rows = signature[band * config.rows : (band + 1) * config.rows]
            buckets[(band, rows)].append(cid)
    pairs: set[tuple[str, str]] = set()
    for ids in buckets.values():
        for i, left in enumerate(ids):
            for right in ids[i + 1 :]:
                pairs.add((left, right))

    parent = {cid: cid for cid in by_id}

    def find(cid: str) -> str:
        while parent[cid] != cid:
            parent[cid] = parent[parent[cid]]
            cid = parent[cid]
        return cid

    linked: list[tuple[str, str, float]] = []
    for left, right in sorted(pairs):
        similarity = _jaccard(sets[left], sets[right])
        if similarity >= config.threshold:
            linked.append((left, right, similarity))
            root_left, root_right = find(left), find(right)
            if root_left != root_right:
                low, high = sorted((root_left, root_right))
                parent[high] = low

    components: dict[str, list[str]] = defaultdict(list)
    for cid in by_id:
        components[find(cid)].append(cid)
    floor: dict[str, float] = {}
    for left, _right, similarity in linked:
        root = find(left)
        floor[root] = min(floor.get(root, 1.0), similarity)
    clusters = [
        DuplicateCluster(
            kind=DuplicateKind.NEAR,
            representative=min((by_id[m] for m in members), key=_representative_key).id,
            members=tuple(sorted(members)),
            min_similarity=round(floor[root], 6),
        )
        for root, members in components.items()
        if len(members) > 1
    ]
    return tuple(sorted(clusters, key=lambda c: c.representative))


# --- language ---------------------------------------------------------------------


class Language(StrEnum):
    CS = "cs"
    SK = "sk"
    EN = "en"
    #: Enough words, but too few function words of cs, sk or en.
    OTHER = "other"
    #: Too short, or Slavic without telling Czech from Slovak.
    UNKNOWN = "unknown"


#: Fewer words than this and the guess is ``unknown``: a headline is not evidence.
MIN_LANGUAGE_TOKENS: Final = 8
#: English needs this share of English function words, else ``other``. (A German
#: page carries a few: ``in``, ``also``.)
_MIN_ENGLISH_SHARE: Final = 0.10
#: Czech or Slovak needs this share of their function words, else ``other``. Lower
#: than English's: Czech and Slovak drop articles, so news prose carries fewer.
_MIN_SLAVIC_SHARE: Final = 0.06
#: The Czech/Slovak decision needs this share of their combined evidence.
_MIN_CS_SK_MARGIN: Final = 0.7


def _wordset(text: str) -> frozenset[str]:
    return frozenset(text.split())


_EN_WORDS: Final = _wordset(
    "a an the and or but of to in on at for with by from as is are was were be been being "
    "it its this that these those has have had not no will would can could should may "
    "which who whom what their they them there than then more most also about into over "
    "after before per said says we our you your he she his her i if so such other while "
    "between under up out all any each both because during"
)
_CS_SK_SHARED: Final = _wordset(
    "a v na je z do o s k že ale tak to po od za by i ten ani už však aby kde má bude jej "
    "tom až tento roku jeho oproti"
)
_CS_ONLY: Final = _wordset(
    "se jsou jsem jsme jste být byl byla bylo byli byly který která které kteří nebo jako "
    "pro podle mezi také než při ve ze jejich této tyto tato jen když co jak proto ještě "
    "více roce mají budou není pouze již"
)
_SK_ONLY: Final = _wordset(
    "sa sú som sme ste byť bol bola bolo boli ktorý ktorá ktoré ktorí alebo ako pre podľa "
    "medzi tiež pri vo zo ich táto tieto tejto len keď čo preto ešte viac majú budú nie "
    "iba aj"
)
#: Letters one language writes and the other does not.
_CS_LETTERS: Final = frozenset("řůě")
_SK_LETTERS: Final = frozenset("äôĺľŕ")
#: Letters neither Czech, Slovak nor English writes (Polish, German, Hungarian).
_FOREIGN_LETTERS: Final = frozenset("ąęłśźżńćßöüőű")

_SLAVIC: Final = _CS_SK_SHARED | _CS_ONLY | _SK_ONLY
#: A word in both the English and the Slavic lists (``a``, ``to``, ``by``, ``on`` …)
#: says nothing about which it is, and is not counted for either.
_EN_SCORED: Final = _EN_WORDS - _SLAVIC
_SLAVIC_SCORED: Final = _SLAVIC - _EN_WORDS


@dataclass(frozen=True, slots=True)
class LanguageGuess:
    """The guess, its confidence in [0, 1], and the counts it was made from."""

    language: Language
    confidence: float
    tokens: int
    english_words: int = 0
    slavic_words: int = 0
    czech_evidence: int = 0
    slovak_evidence: int = 0
    foreign_letters: int = 0


def detect_language(text: str) -> LanguageGuess:
    """Czech, Slovak, English, other or unknown, from function words and letters.

    1. Fewer than :data:`MIN_LANGUAGE_TOKENS` words: ``unknown``.
    2. English vs Czech/Slovak by which family has more function words (a word in
       both lists counts for neither). The winner below its minimum share
       (:data:`_MIN_ENGLISH_SHARE`, :data:`_MIN_SLAVIC_SHARE`), or no function word
       at all: ``other``. A tie: ``unknown``.
    3. A Slavic text with more letters Czech and Slovak never write (ł ą ę ż …) than
       Czech-or-Slovak evidence is ``other`` (Polish, mostly).
    4. Czech vs Slovak by evidence: words only one of them writes (``jsou``/``sú``,
       ``nebo``/``alebo``) plus letters only one of them writes (ř ů ě vs ä ô ĺ ľ ŕ).
       The winner needs :data:`_MIN_CS_SK_MARGIN` of the evidence, else ``unknown``.

    Confidence is the winning family's share of the function words times, for cs/sk,
    the winner's share of the evidence; rounded to three places. It is 0 for
    ``other`` and for a text too short to judge.
    """
    lowered = unicodedata.normalize("NFC", normalise_text(text).casefold())
    tokens = _LETTERS.findall(lowered)
    n = len(tokens)
    if n < MIN_LANGUAGE_TOKENS:
        return LanguageGuess(Language.UNKNOWN, 0.0, n)
    english = sum(1 for t in tokens if t in _EN_SCORED)
    slavic = sum(1 for t in tokens if t in _SLAVIC_SCORED)
    czech = sum(1 for t in tokens if t in _CS_ONLY)
    czech += sum(1 for ch in lowered if ch in _CS_LETTERS)
    slovak = sum(1 for t in tokens if t in _SK_ONLY)
    slovak += sum(1 for ch in lowered if ch in _SK_LETTERS)
    foreign = sum(1 for ch in lowered if ch in _FOREIGN_LETTERS)

    def guess(language: Language, confidence: float = 0.0) -> LanguageGuess:
        return LanguageGuess(
            language, round(confidence, 3), n, english, slavic, czech, slovak, foreign
        )

    if english == slavic:
        return guess(Language.OTHER if english == 0 else Language.UNKNOWN)
    family = max(english, slavic) / (english + slavic)
    if english > slavic:
        return (
            guess(Language.EN, family)
            if english / n >= _MIN_ENGLISH_SHARE
            else guess(Language.OTHER)
        )
    if slavic / n < _MIN_SLAVIC_SHARE or foreign > czech + slovak:
        return guess(Language.OTHER)
    if czech + slovak == 0:
        return guess(Language.UNKNOWN)
    share = max(czech, slovak) / (czech + slovak)
    if share < _MIN_CS_SK_MARGIN:
        return guess(Language.UNKNOWN, family * share)
    return guess(Language.CS if czech > slovak else Language.SK, family * share)


#: The languages a run keeps by default: Czech, Slovak, English, and a text too
#: short to tell (dropping it would decide on no evidence). ``other`` is removed.
DEFAULT_LANGUAGES: Final = frozenset({Language.CS, Language.SK, Language.EN, Language.UNKNOWN})


# --- relevance --------------------------------------------------------------------

#: BM25's term-frequency saturation and length normalisation (the usual values).
BM25_K1: Final = 1.2
BM25_B: Final = 0.75
#: A stem is at most this many characters: a fixed-length prefix after suffixes.
_STEM_LENGTH: Final = 8
_MIN_STEM: Final = 3
#: Endings stripped once, longest first (folded: no diacritics). Czech case and
#: number endings, and the English plural; then one trailing vowel.
_SUFFIXES: Final = tuple(
    sorted(
        _wordset("atech ami ach ech ich ych ymi eho emu ova ove ovi ovy ou em am um im ym es s"),
        key=lambda s: (-len(s), s),
    )
)
_VOWELS: Final = frozenset("aeiouy")


def _fold_word(word: str) -> str:
    decomposed = unicodedata.normalize("NFD", word.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


#: Folded, ``být`` becomes ``byt`` (a flat): a content word of the housing market, so
#: it is not a stopword for relevance.
_STOPWORDS: Final = frozenset(_fold_word(w) for w in _EN_WORDS | _SLAVIC) - {"byt"}


def stem(word: str) -> str:
    """A light, fixed-rule stem of one folded word.

    Strip the longest listed ending that leaves at least three characters, then one
    trailing vowel on the same condition, then keep the first eight characters. Digits
    are kept whole. ``trhu``, ``trhy`` -> ``trh``; ``ceny``, ``cenou`` -> ``cen``;
    ``prices``, ``price`` -> ``pric``.
    """
    if word.isdigit():
        return word
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= _MIN_STEM:
            word = word[: -len(suffix)]
            break
    if len(word) > _MIN_STEM and word[-1] in _VOWELS:
        word = word[:-1]
    return word[:_STEM_LENGTH]


def relevance_terms(text: str) -> list[str]:
    """The stemmed, stopword-free terms BM25 compares (in text order)."""
    return [stem(w) for w in words(text) if w not in _STOPWORDS and len(w) > 1]


def bm25_scores(question: str, documents: Mapping[str, str]) -> dict[str, float]:
    """Okapi BM25 of every document against ``question``, over this set's statistics.

    ``idf = ln(1 + (N - df + 0.5) / (df + 0.5))`` (never negative); each distinct
    question term counts once; terms are summed in sorted order, so the float result
    does not depend on the order anything was given in.
    """
    if not documents:
        return {}
    terms = {doc_id: Counter(relevance_terms(text)) for doc_id, text in sorted(documents.items())}
    lengths = {doc_id: sum(counts.values()) for doc_id, counts in terms.items()}
    average = sum(lengths.values()) / len(lengths) or 1.0
    query = sorted(set(relevance_terms(question)))
    n = len(terms)
    df = {term: sum(1 for counts in terms.values() if term in counts) for term in query}
    idf = {term: math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5)) for term in query}
    scores: dict[str, float] = {}
    for doc_id, counts in terms.items():
        norm = BM25_K1 * (1 - BM25_B + BM25_B * lengths[doc_id] / average)
        score = 0.0
        for term in query:
            tf = counts.get(term, 0)
            if tf:
                score += idf[term] * tf * (BM25_K1 + 1) / (tf + norm)
        scores[doc_id] = score
    return scores


# --- the stage ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class KeptCandidate:
    """A survivor: its rank (1 is first), score, language, and every id folded into it."""

    id: str
    rank: int
    score: float
    language: LanguageGuess
    absorbed: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FilterResult:
    """What the Filter stage kept, in rank order, and what it removed and why."""

    version: str
    question: str
    received: int
    kept: tuple[KeptCandidate, ...]
    removed: tuple[Removed, ...]
    clusters: tuple[DuplicateCluster, ...] = ()

    def removed_ids(self, reason: RemovalReason) -> tuple[str, ...]:
        return tuple(r.id for r in self.removed if r.reason is reason)

    def counts(self) -> dict[str, int]:
        """Per reason, how many were removed; and how many were kept."""
        tally = {reason.value: 0 for reason in RemovalReason}
        for removal in self.removed:
            tally[removal.reason.value] += 1
        tally["kept"] = len(self.kept)
        return tally


def filter_candidates(
    candidates: Sequence[FilterCandidate],
    question: str,
    *,
    max_keep: int,
    languages: frozenset[Language] = DEFAULT_LANGUAGES,
    near: NearDuplicateConfig | None = None,
) -> FilterResult:
    """Empty -> exact duplicates -> near-duplicates -> language -> rank -> top ``max_keep``."""
    if max_keep < 0:
        raise ValueError("max_keep must not be negative")
    ordered = sorted(candidates, key=lambda c: c.id)
    if len({c.id for c in ordered}) != len(ordered):
        raise ValueError("candidate ids must be unique")
    removed: list[Removed] = []
    absorbed: dict[str, list[str]] = defaultdict(list)

    live = []
    for candidate in ordered:
        if words(candidate.text):
            live.append(candidate)
        else:
            removed.append(Removed(candidate.id, RemovalReason.EMPTY_TEXT))

    exact = exact_duplicate_clusters(live)
    for cluster in exact:
        for member in cluster.members:
            if member != cluster.representative:
                removed.append(
                    Removed(member, RemovalReason.EXACT_DUPLICATE, cluster.representative)
                )
                absorbed[cluster.representative].append(member)
    gone = {r.id for r in removed}
    live = [c for c in live if c.id not in gone]

    near_clusters = near_duplicate_clusters(live, near)
    for cluster in near_clusters:
        for member in cluster.members:
            if member != cluster.representative:
                removed.append(
                    Removed(member, RemovalReason.NEAR_DUPLICATE, cluster.representative)
                )
                absorbed[cluster.representative].extend([member, *absorbed.pop(member, [])])
    gone = {r.id for r in removed}
    live = [c for c in live if c.id not in gone]

    guesses: dict[str, LanguageGuess] = {}
    in_language = []
    for candidate in live:
        guess = detect_language(candidate.text)
        if guess.language in languages:
            guesses[candidate.id] = guess
            in_language.append(candidate)
        else:
            removed.append(Removed(candidate.id, RemovalReason.LANGUAGE, language=guess.language))

    scores = bm25_scores(question, {c.id: c.text for c in in_language})
    ranking = sorted(in_language, key=lambda c: (-scores[c.id], c.id))
    kept = tuple(
        KeptCandidate(
            id=c.id,
            rank=i + 1,
            score=round(scores[c.id], 6),
            language=guesses[c.id],
            absorbed=tuple(sorted(absorbed.get(c.id, []))),
        )
        for i, c in enumerate(ranking[:max_keep])
    )
    removed.extend(
        Removed(c.id, RemovalReason.BELOW_CUTOFF, score=round(scores[c.id], 6))
        for c in ranking[max_keep:]
    )
    return FilterResult(
        version=FILTERS_VERSION,
        question=question,
        received=len(ordered),
        kept=kept,
        removed=tuple(removed),
        clusters=exact + near_clusters,
    )
