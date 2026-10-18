"""Does a grounded finding support the topic it was searched for (D4, evaluation finding F1).

Grounding proves a quote is in its source and the verifier reads the claim against the quote;
neither reads the topic. A grounded quote from a credible host passes both whatever it is about
-- a mortgage thesis filed under trust in a current account (F1). This screen is the merge's
topic gate (``merge_evidence``, after the source score, before dedupe): a small, fixed set of
deterministic rules over the finding's own text, each with its own test. No model is asked.

**What it reads.** A run's topics are its subjects (questions, tracked objects and their
crosses), profiled once per run from the frozen request (:func:`topic_screen`). A finding is
read in what code holds -- its quote and its source's title -- and, for the topic words of a
question only, the investigator's own claim. Terms are :func:`.filters.relevance_terms`:
folded, stopword-free, lightly stemmed -- with one fold of the screen's own: a stem left
ending in ``ov`` is read without it, so the ``-ový`` adjectives an object is named by read
alike in every case (``sójového`` and ``sójových`` are ``sojov``, ``Sójový`` is ``soj``).

**The rules, in order; the first that decides wins** (named as the plan names them,
``research-integrity-report.md`` chunk 10; R2, a study-title rule, was dropped there).

* **R1, object named** (``OBJECT``, ``CROSS``): the quote or the source title names the object
  by its distinguishing phrase -- the label's terms from the first to the last that no other
  tracked object's label shares, in the label's order (the whole label when every term is
  shared, or no other object is tracked). A word of a longer name never names it alone: ``bank``
  names neither ``Fio banka`` nor ``Air Bank`` beside each other, ``nápoj`` none of three plant
  drinks, and ``Česku`` not ``Česká spořitelna``.
* **R4, concept swap** (every kind): the quote or the source title names a sibling concept of a
  declared family and none of the topic's own -- a topic about a current account, a source
  about a mortgage. Families: :data:`CONCEPT_FAMILIES` (versioned, :data:`CONCEPTS_VERSION`),
  each concept by the phrases that name it, longest first, so ``hypoteční úvěr`` names a
  mortgage and not a loan; and the run's tracked objects as one family, each named by its
  distinguishing phrase (R1's). A family may declare one concept a kind of another: a mortgage
  is a loan, so a loan topic keeps a mortgage source, never the other way round. A topic that
  names no concept of a family is not judged by it.
* **R3, topic words** (``QUESTION``, ``CROSS``): the claim, the quote or the source title shares
  at least one of the topic's terms, once the client's own names (:data:`CLIENT_IDENTITY`),
  question words (:data:`QUESTION_WORDS`) and every term with a digit are taken out; an
  interpretation subject is read without its framing (:data:`.interpretation.FRAMINGS`): the
  framing's own words go, the text in its slots stays, and a subject no framing frames keeps
  every word.

R1 and R4 never read the claim: the investigator's paraphrase never decides a rule against
it. A topic with no terms left to judge by is **undetermined**, and so is a finding whose topic
the screen does not hold: unknown is never on topic, and the merge quarantines both.

**Limits, stated plainly.** Shared words are not shared meaning: the screen does not check
population, place, period or what a sentence says about the topic. The stemmer misses
inflections that change the stem (``účet``/``účtu``, ``důvěra``/``důvěřují``), there is no
lexicon across languages, and a synonym shares no word; a concept is named only by the phrases
the table lists, and a topic naming none (``bezpečnost mobilního bankovnictví``) is judged by
R3 alone. An object named only in part (``spořitelna`` for ``Česká spořitelna``) is not
named. R3 asks for one shared word, so it sets aside only a finding with none: on the filters'
fictional corpus (``tests/fixtures/deep_research_filters``, first sentence as the claim) it
keeps 25 of 27 relevant pairs and sets aside 120 of 149 irrelevant ones; the other 29 share a
generic word (``trh``, ``Česku``, ``ceny``)
(``test_deep_research_topicality.py::test_measured_topicality``).

Pure: stdlib, and this package's own text rules and contracts.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from .contracts import ClientTerm, EvidenceItem, ResearchSubject, SubjectKind
from .filters import FILTERS_VERSION, relevance_terms
from .grounding import normalise_text
from .interpretation import FRAMINGS

__all__ = [
    "CLIENT_IDENTITY",
    "CONCEPTS_VERSION",
    "CONCEPT_FAMILIES",
    "QUESTION_WORDS",
    "TOPICALITY_PREFIX",
    "TOPICALITY_VERSION",
    "TRACKED_OBJECTS",
    "Concept",
    "ConceptFamily",
    "TopicJudgement",
    "TopicProfile",
    "TopicRule",
    "TopicScreen",
    "TopicVerdict",
    "concept_table",
    "declared_rules",
    "judged_topic",
    "topic_screen",
]

#: The concept-family table's version: a changed phrase is a changed table
#: (``test_the_concept_table_is_the_version_it_names`` holds them together).
CONCEPTS_VERSION: Final = "aia-dr-concepts-1"
#: Every version of these rules begins so, and a merge version that carries it judged topic.
TOPICALITY_PREFIX: Final = "aia-dr-topicality-"
#: The rules' version, with the term rules and the table they read: a changed word list,
#: framing or fold is a changed version (``test_the_declared_rules_are_the_version_they_name``).
TOPICALITY_VERSION: Final = f"{TOPICALITY_PREFIX}1/{FILTERS_VERSION}/{CONCEPTS_VERSION}"

#: The client terms that are the client itself (``ClientTerm.source``). A study's name and an
#: approved entity stay topic words: a study is routinely named after its topic, and taking
#: its words out would leave the topic nothing to be judged by.
CLIENT_IDENTITY: Final = frozenset({"client.name", "client.slug"})

#: What a question asks with, never what it is about (Czech, then English).
QUESTION_WORDS: Final = (
    "proč jaký jaká jaké jakou jakého jakému jakém jakým jakých jakými kolik kdo koho komu kdy "
    "kde kam čím čeho nakolik zda zdali jestli míra míry míru "
    "how why what which whether who when where extent"
)

#: The family the run's own tracked objects make (R4).
TRACKED_OBJECTS: Final = "tracked_objects"

_PLACEHOLDER: Final = re.compile(r"\{\w+\}")
_WORD: Final = re.compile(r"\w+")
#: How much of a topic's text a detail quotes.
_TOPIC_CHARS: Final = 200
#: How many of a topic's words a detail names.
_TOPIC_WORDS: Final = 8
#: A stem is read without a trailing ``ov`` only when longer than this: ``slov`` stays.
_OV_MIN: Final = 4


def _terms(text: str) -> list[str]:
    """:func:`.filters.relevance_terms`, a trailing ``ov`` folded away (the ``-ový`` cases)."""
    return [t[:-2] if len(t) > _OV_MIN and t.endswith("ov") else t for t in relevance_terms(text)]


def _phrase(text: str) -> tuple[str, ...]:
    return tuple(_terms(text))


_QUESTION_TERMS: Final = frozenset(_terms(QUESTION_WORDS))


def _framing_pattern(framing: str) -> re.Pattern[str]:
    """A framing as a pattern over a whole subject: its own words literal, each slot a group.
    The words after the last slot may be cut where the subject met its bound (``…``)."""
    parts = _PLACEHOLDER.split(framing)
    tail = parts[-1]
    cuts = sorted({tail[:i].rstrip() for i in range(len(tail))}, key=len, reverse=True)
    ending = "|".join(
        [re.escape(tail), *(re.escape(cut) + "…" for cut in cuts)] if tail else ["…?"]
    )
    body = "(.+?)".join(re.escape(part) for part in parts[:-1])
    return re.compile(f"{body}(.+?)(?:{ending})", re.DOTALL)


_FRAMED: Final = tuple(_framing_pattern(framing) for framing in FRAMINGS)


def _unframed(text: str) -> str:
    """What a subject is about: the text in its framing's slots, or the whole text when no
    framing frames it -- a framing's words are never a topic's own, and a subject that was
    never framed loses none of its words."""
    for pattern in _FRAMED:
        match = pattern.fullmatch(text)
        if match is not None:
            return " ".join(match.groups())
    return text


# --------------------------------------------------------------------------- #
# Concepts
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Concept:
    """One concept of a family: its name as written, and every phrase that names it."""

    name: str
    markers: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class ConceptFamily:
    """Concepts that are siblings: a text naming one and not another is about the one.

    ``neutral`` phrases name no concept and hide their words from every concept (``pojištění
    vkladů`` is what keeps a current account's deposits, not an insurance product). ``kinds``
    are (narrower, broader) pairs: a text naming the narrower concept names a kind of the
    broader one (a mortgage is a loan), so it is no swap under a topic naming the broader.
    """

    family_id: str
    concepts: tuple[Concept, ...]
    neutral: tuple[tuple[str, ...], ...] = ()
    kinds: tuple[tuple[str, str], ...] = ()

    @classmethod
    def declare(
        cls,
        family_id: str,
        concepts: Iterable[tuple[str, Sequence[str]]],
        *,
        neutral: Sequence[str] = (),
        kinds: Sequence[tuple[str, str]] = (),
    ) -> ConceptFamily:
        """A family from its concepts' names and surface phrases, each stemmed as text is."""
        family = cls(
            family_id=family_id,
            concepts=tuple(
                Concept(
                    name=name,
                    markers=tuple(dict.fromkeys(p for p in map(_phrase, (name, *forms)) if p)),
                )
                for name, forms in concepts
            ),
            neutral=tuple(p for p in map(_phrase, neutral) if p),
            kinds=tuple(kinds),
        )
        names = {c.name for c in family.concepts}
        unknown = {n for pair in family.kinds for n in pair} - names
        if unknown:
            raise ValueError(f"{family_id}: kinds name no concept of the family: {sorted(unknown)}")
        return family

    def broader(self, named: Iterable[str]) -> frozenset[str]:
        """``named`` and every concept each is a kind of, however many steps up."""
        out = set(named)
        while True:
            more = {broad for narrow, broad in self.kinds if narrow in out} - out
            if not more:
                return frozenset(out)
            out |= more

    def named(self, text: str) -> frozenset[str]:
        """The concepts ``text`` names: phrases matched longest first, each word once."""
        seq = _terms(text)
        phrases = sorted(
            [(m, c.name) for c in self.concepts for m in c.markers]
            + [(m, None) for m in self.neutral],
            key=lambda pair: -len(pair[0]),
        )
        used = [False] * len(seq)
        named: set[str] = set()
        for marker, name in phrases:
            width = len(marker)
            for i in range(len(seq) - width + 1):
                if not any(used[i : i + width]) and tuple(seq[i : i + width]) == marker:
                    used[i : i + width] = [True] * width
                    if name is not None:
                        named.add(name)
        return frozenset(named)


#: Retail-banking products (F1: a current-account topic, a mortgage source). Each concept with
#: the inflections a text commonly writes it in; a form the light stemmer folds to another stem
#: is listed, never guessed. ``úvěr na bydlení`` is a mortgage; a bare ``účet`` names no
#: concept, since a savings account is one too.
_RETAIL_BANKING: Final = (
    (
        "běžný účet",
        (
            "běžného účtu",
            "běžnému účtu",
            "běžném účtu",
            "běžným účtem",
            "běžné účty",
            "běžných účtů",
            "běžným účtům",
            "běžnými účty",
            "osobní účet",
            "osobního účtu",
            "osobním účtu",
            "platební účet",
            "platebního účtu",
            "platebním účtu",
            "current account",
            "current accounts",
            "checking account",
            "checking accounts",
        ),
    ),
    (
        "spořicí účet",
        (
            "spořicího účtu",
            "spořicím účtu",
            "spořicím účtem",
            "spořicí účty",
            "spořicích účtů",
            "spořicími účty",
            "spořící účet",
            "spořícího účtu",
            "savings account",
            "savings accounts",
        ),
    ),
    (
        "hypotéka",
        (
            "hypotéky",
            "hypotéce",
            "hypotéku",
            "hypotékou",
            "hypoték",
            "hypotékám",
            "hypotékách",
            "hypotékami",
            "hypoteční",
            "hypotečního",
            "hypotečních",
            "hypotečním",
            "hypoteční úvěr",
            "hypotečního úvěru",
            "hypoteční úvěry",
            "hypotečních úvěrů",
            "úvěr na bydlení",
            "úvěru na bydlení",
            "úvěry na bydlení",
            "úvěrů na bydlení",
            "mortgage",
            "mortgages",
        ),
    ),
    (
        "úvěr",
        (
            "úvěru",
            "úvěrem",
            "úvěry",
            "úvěrů",
            "úvěrům",
            "úvěrech",
            "půjčka",
            "půjčky",
            "půjčce",
            "půjčku",
            "půjčkou",
            "půjček",
            "půjčkám",
            "půjčkách",
            "půjčkami",
            "loan",
            "loans",
        ),
    ),
    (
        "kreditní karta",
        (
            "kreditní karty",
            "kreditní kartě",
            "kreditní kartu",
            "kreditní kartou",
            "kreditních karet",
            "kreditním kartám",
            "kreditních kartách",
            "kreditními kartami",
            "credit card",
            "credit cards",
        ),
    ),
    (
        "pojištění",
        (
            "pojištěním",
            "pojistka",
            "pojistky",
            "pojistce",
            "pojistku",
            "pojistkou",
            "pojistek",
            "insurance",
        ),
    ),
    (
        "investice",
        (
            "investiční fond",
            "investičního fondu",
            "investiční fondy",
            "investičních fondů",
            "podílový fond",
            "podílového fondu",
            "podílové fondy",
            "podílových fondů",
            "investiční produkt",
            "investiční produkty",
            "investičních produktů",
            "investování",
            "investment fund",
            "investment funds",
            "mutual fund",
            "mutual funds",
        ),
    ),
    (
        "penzijní spoření",
        (
            "penzijního spoření",
            "penzijním spoření",
            "penzijnímu spoření",
            "penzijní připojištění",
            "penzijního připojištění",
            "penzijním připojištění",
            "penzijní fond",
            "penzijního fondu",
            "penzijní fondy",
            "penzijních fondů",
            "pension savings",
            "pension fund",
            "pension funds",
        ),
    ),
    (
        "stavební spoření",
        (
            "stavebního spoření",
            "stavebním spoření",
            "stavebnímu spoření",
            "building savings",
        ),
    ),
)
_RETAIL_BANKING_NEUTRAL: Final = (
    "pojištění vkladů",
    "pojištěním vkladů",
    "pojištění vkladu",
    "deposit insurance",
)

#: (narrower, broader): a mortgage is a loan, so a loan topic keeps a mortgage source.
_RETAIL_BANKING_KINDS: Final = (("hypotéka", "úvěr"),)

#: The declared families (:data:`CONCEPTS_VERSION`). One today, seeded from F1.
CONCEPT_FAMILIES: Final = (
    ConceptFamily.declare(
        "retail_banking_products",
        _RETAIL_BANKING,
        neutral=_RETAIL_BANKING_NEUTRAL,
        kinds=_RETAIL_BANKING_KINDS,
    ),
)


def judged_topic(merge_rules_version: str) -> bool:
    """Whether a merge under ``merge_rules_version`` judged each finding's topic: any version
    of these rules, so a later one never reads as "nobody checked"."""
    return TOPICALITY_PREFIX in merge_rules_version


def concept_table() -> list[list[object]]:
    """The declared table as written, for its pin: family, concept, phrases; neutral phrases;
    which concept is a kind of which."""
    return [
        ["retail_banking_products", [[n, list(f)] for n, f in _RETAIL_BANKING]],
        ["retail_banking_products:neutral", list(_RETAIL_BANKING_NEUTRAL)],
        ["retail_banking_products:kinds", [list(pair) for pair in _RETAIL_BANKING_KINDS]],
    ]


def declared_rules() -> dict[str, object]:
    """Everything besides the code and the table that decides a verdict, for its pin: the
    client names, question words, framings and the ``-ov`` fold."""
    return {
        "client_identity": sorted(CLIENT_IDENTITY),
        "question_words": QUESTION_WORDS,
        "framings": list(FRAMINGS),
        "ov_fold_min": _OV_MIN,
    }


# --------------------------------------------------------------------------- #
# Profiles
# --------------------------------------------------------------------------- #


class TopicVerdict(StrEnum):
    ON_TOPIC = "ON_TOPIC"
    OFF_TOPIC = "OFF_TOPIC"
    #: Nothing to judge by: never read as on topic.
    UNDETERMINED = "UNDETERMINED"


class TopicRule(StrEnum):
    """The rule that decided a verdict other than on topic."""

    NO_PROFILE = "no_profile"
    NO_TERMS = "no_terms"
    OBJECT_NAMED = "object_named"
    CONCEPT_SWAP = "concept_swap"
    TOPIC_WORDS = "topic_words"


@dataclass(frozen=True, slots=True)
class TopicJudgement:
    verdict: TopicVerdict
    #: ``None`` on topic.
    rule: TopicRule | None
    #: Czech words as written, never stems: what the topic is and what the source says.
    detail: str


@dataclass(frozen=True, slots=True)
class TopicProfile:
    """One subject as the rules read it."""

    subject_key: str
    kind: SubjectKind
    #: The subject's text as written.
    text: str
    #: The object's label as written (``OBJECT``, ``CROSS``).
    object_label: str | None
    #: R1's distinguishing phrase, terms in the label's order; empty for a question.
    object_name: tuple[str, ...]
    #: R3's terms, each with the word it was first written as, in text order; empty for
    #: an object.
    topic_terms: tuple[tuple[str, str], ...]
    #: R4: (family id, concept name) for every concept the topic names.
    concepts: frozenset[tuple[str, str]]


def _written(text: str) -> dict[str, str]:
    """Each term of ``text`` with the word it is first written as."""
    out: dict[str, str] = {}
    for word in _WORD.findall(normalise_text(text)):
        for term in _terms(word):
            out.setdefault(term, word)
    return out


def _distinguishing(objects: Sequence[ResearchSubject]) -> dict[str, tuple[str, ...]]:
    """Each object's distinguishing phrase: its label's terms, in order, from the first to the
    last that no other object's label shares; the whole label when every term is shared. A
    single word of a longer name never stands for it: ``Česku`` is not ``Česká spořitelna``."""
    terms = {o.key: tuple(_terms(o.text)) for o in objects}
    out: dict[str, tuple[str, ...]] = {}
    for key, own in terms.items():
        others = frozenset().union(*(t for k, t in terms.items() if k != key))
        own_at = [i for i, term in enumerate(own) if term not in others]
        out[key] = own[own_at[0] : own_at[-1] + 1] if own_at else own
    return out


def _says(text: str, phrase: tuple[str, ...]) -> bool:
    """Whether ``text`` has ``phrase``'s terms one after another."""
    seq, width = _terms(text), len(phrase)
    return any(tuple(seq[i : i + width]) == phrase for i in range(len(seq) - width + 1))


def _tracked_family(
    objects: Sequence[ResearchSubject], distinguishing: Mapping[str, tuple[str, ...]]
) -> ConceptFamily | None:
    """The run's tracked objects as siblings: each named by its distinguishing phrase."""
    if len(objects) < 2:
        return None
    return ConceptFamily(
        family_id=TRACKED_OBJECTS,
        concepts=tuple(
            Concept(name=o.text, markers=(distinguishing[o.key],) if distinguishing[o.key] else ())
            for o in objects
        ),
    )


@dataclass(frozen=True, slots=True)
class TopicScreen:
    """A run's topics, profiled once, and the families R4 reads."""

    profiles: Mapping[str, TopicProfile]
    families: tuple[ConceptFamily, ...]
    version: str = TOPICALITY_VERSION

    def judge(self, item: EvidenceItem) -> TopicJudgement:
        """Whether ``item`` supports the topic it was searched for."""
        return self.judge_text(
            item.subject_key, claim=item.claim, quote=item.quote, source_title=item.source_title
        )

    def judge_text(
        self, subject_key: str, *, claim: str, quote: str, source_title: str
    ) -> TopicJudgement:
        """The rules over a finding's text (:func:`judge` reads an item's)."""
        profile = self.profiles.get(subject_key)
        if profile is None:
            return TopicJudgement(
                TopicVerdict.UNDETERMINED,
                TopicRule.NO_PROFILE,
                "téma hledání není v plánu běhu; souvislost s ním nelze posoudit",
            )
        topic = f"téma: „{_cut(profile.text)}“"
        if profile.kind in (SubjectKind.OBJECT, SubjectKind.CROSS):
            if not profile.object_name:
                return TopicJudgement(
                    TopicVerdict.UNDETERMINED,
                    TopicRule.NO_TERMS,
                    f"objekt „{profile.object_label}“ nemá slovo, podle kterého by ho šlo "
                    "poznat v citaci nebo názvu zdroje",
                )
            if not (_says(quote, profile.object_name) or _says(source_title, profile.object_name)):
                return TopicJudgement(
                    TopicVerdict.OFF_TOPIC,
                    TopicRule.OBJECT_NAMED,
                    f"objekt: „{profile.object_label}“; citace ani název zdroje ho nejmenuje",
                )
        for family in self.families:
            own = {name for fid, name in profile.concepts if fid == family.family_id}
            if not own:
                continue
            named = family.named(quote) | family.named(source_title)
            if named and not family.broader(named) & own:
                return TopicJudgement(
                    TopicVerdict.OFF_TOPIC,
                    TopicRule.CONCEPT_SWAP,
                    f"téma: {_listed(own)}; zdroj jmenuje: {_listed(named)}",
                )
        if profile.kind in (SubjectKind.QUESTION, SubjectKind.CROSS):
            if not profile.topic_terms:
                return TopicJudgement(
                    TopicVerdict.UNDETERMINED,
                    TopicRule.NO_TERMS,
                    f"{topic}; bez jmen klienta, tázacích a rámcových slov nezbývá slovo, "
                    "podle kterého by šlo souvislost posoudit",
                )
            found = {*_terms(quote), *_terms(source_title), *_terms(claim)}
            if not any(term in found for term, _ in profile.topic_terms):
                words = [w for _, w in profile.topic_terms[:_TOPIC_WORDS]]
                return TopicJudgement(
                    TopicVerdict.OFF_TOPIC,
                    TopicRule.TOPIC_WORDS,
                    f"{topic}; tvrzení, citace ani název zdroje nesdílí žádné z jeho slov "
                    f"({_listed(words, ordered=True)})",
                )
        return TopicJudgement(TopicVerdict.ON_TOPIC, None, "")


def _cut(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= _TOPIC_CHARS else text[: _TOPIC_CHARS - 1].rstrip() + "…"


def _listed(words: Iterable[str], *, ordered: bool = False) -> str:
    items = list(words) if ordered else sorted(words)
    return ", ".join(f"„{w}“" for w in items)


def topic_screen(
    subjects: Sequence[ResearchSubject], *, client_terms: Sequence[ClientTerm]
) -> TopicScreen:
    """Every subject of a run profiled for the rules, from its frozen request.

    ``subjects`` are the plan's (the request's and the crosses the preset opened);
    ``client_terms`` the request's, of which the client's own names are not topic words.
    """
    client = frozenset(
        t for c in client_terms if c.source in CLIENT_IDENTITY for t in _terms(c.term)
    )
    removed = client | _QUESTION_TERMS
    by_key = {s.key: s for s in subjects}
    objects = [s for s in subjects if s.kind is SubjectKind.OBJECT]
    distinguishing = _distinguishing(objects)
    tracked = _tracked_family(objects, distinguishing)
    families = (*CONCEPT_FAMILIES, *((tracked,) if tracked is not None else ()))

    def topic_terms(text: str) -> tuple[tuple[str, str], ...]:
        return tuple(
            (term, word)
            for term, word in _written(_unframed(text)).items()
            if term not in removed and not any(ch.isdigit() for ch in term)
        )

    def concepts(text: str) -> frozenset[tuple[str, str]]:
        return frozenset(
            (family.family_id, name) for family in CONCEPT_FAMILIES for name in family.named(text)
        )

    def tracked_named(text: str) -> frozenset[tuple[str, str]]:
        if tracked is None:
            return frozenset()
        return frozenset((TRACKED_OBJECTS, name) for name in tracked.named(text))

    profiles: dict[str, TopicProfile] = {}
    for subject in subjects:
        label: str | None = None
        object_name: tuple[str, ...] = ()
        words: tuple[tuple[str, str], ...] = ()
        own = concepts(subject.text)
        if subject.kind is SubjectKind.OBJECT:
            label, object_name = subject.text, distinguishing[subject.key]
            if tracked is not None:
                own |= {(TRACKED_OBJECTS, subject.text)}
        elif subject.kind is SubjectKind.QUESTION:
            words = topic_terms(subject.text)
            own |= tracked_named(subject.text)
        else:
            # A cross is its question about its object: the object named (R1), the
            # question's words (R3). A part the run does not hold leaves nothing to judge.
            question = by_key.get(subject.question_key or "")
            obj = by_key.get(subject.object_key or "")
            if obj is not None and obj.kind is SubjectKind.OBJECT:
                label, object_name = obj.text, distinguishing[obj.key]
                if tracked is not None:
                    own |= {(TRACKED_OBJECTS, obj.text)}
            if question is not None and question.kind is SubjectKind.QUESTION:
                words = topic_terms(question.text)
                own |= tracked_named(question.text)
        profiles[subject.key] = TopicProfile(
            subject_key=subject.key,
            kind=subject.kind,
            text=subject.text,
            object_label=label,
            object_name=object_name,
            topic_terms=words,
            concepts=own,
        )
    return TopicScreen(profiles=profiles, families=families)
