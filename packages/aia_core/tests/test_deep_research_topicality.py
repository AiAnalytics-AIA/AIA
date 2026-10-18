"""Does a grounded finding support the topic it was searched for (D4, evaluation finding F1).

Everything here is fictional: Banka Lípa is no bank, its thesis no thesis, and the corpus is the
filters' own invented one. What is pinned:

* **F1's shape** -- a current-account topic, three grounded quotes from a mortgage thesis whose
  title names the mortgage, sharing bank, trust and client words: R4 sets them aside on the
  title, whatever the investigator's claim says; findings that name the account stay;
* **each rule** -- an object finding names its object in the quote or title by its
  distinguishing phrase, never by one word of a longer name (R1); a question finding shares one
  topic word once the client's names, question words, a subject's framing and digits are out
  (R3); nothing to judge by is undetermined, never on topic;
* **the concept table** -- every entry by its inflected forms, longest phrase first, a mortgage
  a kind of loan, pinned to its version; the run's tracked objects a family of their own;
* **the declared rules** -- word lists, framings and the fold, pinned to the rules' version;
* **every topic a run can hold** -- each interpretation target kind's mission and a design's
  crosses profile into something the rules can judge;
* **the measured screen** on the filters' corpus, first sentence as the claim.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.analysis.modules import AnalysisModuleId
from aia_core.domain.deep_research.contracts import (
    HARNESS_VERSION,
    Channel,
    ClientTerm,
    DeepResearchRequest,
    FrozenKnowledge,
    ResearchSubject,
    SubjectKind,
    subject_key,
)
from aia_core.domain.deep_research.filters import FILTERS_VERSION
from aia_core.domain.deep_research.integration import (
    AnalysisModuleTarget,
    ResearchTargetRef,
    ResultBatteryObjectTarget,
    ResultQuestionTarget,
    SociomapObjectTarget,
    SociomapRelationshipTarget,
    SociomapTarget,
)
from aia_core.domain.deep_research.interpretation import (
    MODULE_FRAMING,
    RESEARCH_QUESTION_FRAMING,
    RESULT_FRAMING,
    interpretation_mission,
)
from aia_core.domain.deep_research.planning import (
    brief_digest,
    extract_subjects,
    preset,
    screen_questions,
    track_slots,
)
from aia_core.domain.deep_research.topicality import (
    CONCEPT_FAMILIES,
    CONCEPTS_VERSION,
    TOPICALITY_VERSION,
    TRACKED_OBJECTS,
    ConceptFamily,
    TopicRule,
    TopicScreen,
    TopicVerdict,
    concept_table,
    declared_rules,
    topic_screen,
)
from aia_core.domain.research_design import compile_design

CORPUS = Path(__file__).parent / "fixtures" / "deep_research_filters" / "corpus.json"

CLIENT = (
    ClientTerm(term="Banka Lípa", source="client.name"),
    ClientTerm(term="banka-lipa", source="client.slug"),
    ClientTerm(term="Digitální účet", source="study.name"),
)
TRUST = "Do jaké míry klienti důvěřují založení běžného účtu online?"
#: A fictional thesis on a credible academic host; its title names the mortgage.
THESIS = "Faktory výběru poskytovatele hypotečního úvěru"
OATS, ALMOND, SOY = "Ovesný nápoj", "Mandlový nápoj", "Sójový nápoj"
FACT = "Ovesný nápoj tvořil v roce 2025 polovinu prodejů rostlinných nápojů v síti klienta."


def _subject(kind: SubjectKind, text: str, **fields: Any) -> ResearchSubject:
    return ResearchSubject(key=subject_key(kind, text), kind=kind, text=text, origin="t", **fields)


def _q(text: str) -> ResearchSubject:
    return _subject(SubjectKind.QUESTION, text)


def _o(text: str) -> ResearchSubject:
    return _subject(SubjectKind.OBJECT, text)


def _screen(*subjects: ResearchSubject, client: tuple[ClientTerm, ...] = CLIENT) -> TopicScreen:
    return topic_screen(subjects, client_terms=client)


def _judge(
    screen: TopicScreen,
    subject: ResearchSubject,
    quote: str,
    *,
    title: str = "",
    claim: str | None = None,
) -> Any:
    return screen.judge_text(
        subject.key, claim=quote if claim is None else claim, quote=quote, source_title=title
    )


# --------------------------------------------------------------------------- F1


def test_a_mortgage_thesis_does_not_support_a_current_account_topic() -> None:
    topic = _q(TRUST)
    framed = _q(RESEARCH_QUESTION_FRAMING.format(question=TRUST))
    screen = _screen(topic, framed)
    # Grounded quotes sharing the bank, trust and client words, and a claim that even names
    # the account: the investigator's paraphrase never decides R4.
    mortgage = [
        ("Důvěra v banku je pro klienty při výběru poskytovatele druhým faktorem.", None),
        ("Klienti, kteří bance důvěřují, se k ní při dalším rozhodování vracejí.", None),
        (
            "Klienti, kteří u banky již mají účet, si u ní častěji sjednají další produkt.",
            "Klienti s běžným účtem u Banky Lípa si častěji sjednají další produkt.",
        ),
    ]
    for subject in (topic, framed):
        for quote, claim in mortgage:
            judgement = _judge(screen, subject, quote, title=THESIS, claim=claim)
            assert judgement.verdict is TopicVerdict.OFF_TOPIC
            assert judgement.rule is TopicRule.CONCEPT_SWAP
            assert judgement.detail == "téma: „běžný účet“; zdroj jmenuje: „hypotéka“"
        # What names the account stays, in the quote or in the title.
        on = _judge(
            screen,
            subject,
            "Podíl klientů, kteří si běžný účet založili online, loni vzrostl.",
            title="Digitální bankovnictví v Česku",
        )
        assert on.verdict is TopicVerdict.ON_TOPIC and on.rule is None
        both = _judge(screen, subject, "Klienti mají běžný účet i hypotéku u jedné banky.")
        assert both.verdict is TopicVerdict.ON_TOPIC


def test_a_topic_naming_no_concept_is_not_judged_by_its_family() -> None:
    # A known limit, said: R4 needs the topic to name a concept of the family.
    topic = _q("Jak klienti vnímají bezpečnost mobilního bankovnictví?")
    judgement = _judge(
        _screen(topic), topic, "Důvěra v banku je pro klienty druhým faktorem.", title=THESIS
    )
    assert judgement.verdict is TopicVerdict.ON_TOPIC


# --------------------------------------------------------------------------- R1


def test_an_object_finding_names_its_object_in_the_quote_or_the_title() -> None:
    oats, almond, soy = _o(OATS), _o(ALMOND), _o(SOY)
    screen = _screen(oats, almond, soy)
    assert _judge(screen, oats, FACT).verdict is TopicVerdict.ON_TOPIC
    off = _judge(screen, almond, FACT)
    assert (off.verdict, off.rule) == (TopicVerdict.OFF_TOPIC, TopicRule.OBJECT_NAMED)
    assert off.detail == "objekt: „Mandlový nápoj“; citace ani název zdroje ho nejmenuje"
    # The title names it: enough. The claim alone names it: not enough.
    plain = "Prodej rostlinných nápojů loni vzrostl o desetinu."
    assert _judge(screen, almond, plain, title="Mandlové nápoje v Česku").verdict is (
        TopicVerdict.ON_TOPIC
    )
    assert _judge(screen, almond, plain, claim="Mandlový nápoj roste.").verdict is (
        TopicVerdict.OFF_TOPIC
    )


def test_a_word_another_tracked_object_shares_names_no_object() -> None:
    fio, air, cs = _o("Fio banka"), _o("Air Bank"), _o("Česká spořitelna")
    screen = _screen(fio, air, cs, client=())
    assert screen.profiles[fio.key].object_name == ("fio",)
    assert screen.profiles[air.key].object_name == ("air",)
    assert screen.profiles[cs.key].object_name == ("cesk", "sporitel")
    # "bank" names neither of the two that share it.
    assert _judge(screen, fio, "Air Bank má 1,2 milionu klientů.").verdict is (
        TopicVerdict.OFF_TOPIC
    )
    assert _judge(screen, air, "Air Bank má 1,2 milionu klientů.").verdict is (
        TopicVerdict.ON_TOPIC
    )
    # One word of a longer name never names it: "České republice" is not the bank.
    off = _judge(screen, cs, "Banky v České republice zvýšily poplatky.")
    assert (off.verdict, off.rule) == (TopicVerdict.OFF_TOPIC, TopicRule.OBJECT_NAMED)
    assert off.detail == "objekt: „Česká spořitelna“; citace ani název zdroje ho nejmenuje"
    assert _judge(screen, cs, "České spořitelně loni přibyli klienti.").verdict is (
        TopicVerdict.ON_TOPIC
    )
    assert _judge(screen, cs, "Poplatky zvýšila.", title="Česká spořitelna: ceník").verdict is (
        TopicVerdict.ON_TOPIC
    )
    # Every word shared: the whole label names it. A single object: its whole label, so
    # "banky" alone does not name a lone "Fio banka".
    twin = _screen(_o("Spořicí konto"), _o("Konto spořicí plus"), client=())
    assert {p.object_name for p in twin.profiles.values()} >= {("sporic", "kont")}
    alone = _screen(fio, client=())
    assert alone.profiles[fio.key].object_name == ("fio", "bank")
    assert _judge(alone, fio, "Banky zvýšily poplatky.").rule is TopicRule.OBJECT_NAMED
    assert _judge(alone, fio, "Fio banka zvýšila poplatky.").verdict is TopicVerdict.ON_TOPIC


# --------------------------------------------------------------------------- R4: objects


def test_the_runs_tracked_objects_are_one_family() -> None:
    fio, air = _o("Fio banka"), _o("Air Bank")
    about_air = _q("Proč klienti volí Air Bank?")
    screen = _screen(fio, air, about_air, client=())
    swap = _judge(screen, about_air, "Fio banka loni získala nejvíce nových klientů.")
    assert (swap.verdict, swap.rule) == (TopicVerdict.OFF_TOPIC, TopicRule.CONCEPT_SWAP)
    assert swap.detail == "téma: „Air Bank“; zdroj jmenuje: „Fio banka“"
    assert _judge(screen, about_air, "Air Bank i Fio banka získaly klienty.").verdict is (
        TopicVerdict.ON_TOPIC
    )
    # A topic naming no tracked object is not judged by the family.
    general = _q("Proč klienti mění banku?")
    assert _judge(
        _screen(fio, air, general, client=()), general, "Fio banka získala klienty."
    ).verdict is (TopicVerdict.ON_TOPIC)
    assert TRACKED_OBJECTS not in {f.family_id for f in _screen(fio, client=()).families}


def test_a_word_of_a_longer_name_names_no_tracked_object() -> None:
    # "Česku" shares its stem with "Česká spořitelna"; neither the topic nor the source
    # names the bank by it.
    fio, air, cs = _o("Fio banka"), _o("Air Bank"), _o("Česká spořitelna")
    banks = _q("Jak lidé v Česku vnímají banky?")
    about_fio = _q("Jak klienti vnímají Fio banku?")
    screen = _screen(fio, air, cs, banks, about_fio, client=())
    assert screen.profiles[banks.key].concepts == frozenset()
    fio_fact = "Fio banka má mezi bankami nejvíce spokojených klientů."
    assert _judge(screen, banks, fio_fact).verdict is TopicVerdict.ON_TOPIC
    general = "Klienti v Česku nejvíce oceňují nízké poplatky."
    assert _judge(screen, about_fio, general).verdict is TopicVerdict.ON_TOPIC
    # The whole name still names it, in any case.
    swap = _judge(screen, about_fio, "Klienti České spořitelny nejvíce oceňují pobočky.")
    assert (swap.rule, swap.detail) == (
        TopicRule.CONCEPT_SWAP,
        "téma: „Fio banka“; zdroj jmenuje: „Česká spořitelna“",
    )


# --------------------------------------------------------------------------- R3


def test_a_question_finding_shares_one_word_of_its_topic() -> None:
    topic = _q("Proč lidé přecházejí na rostlinné nápoje?")
    screen = _screen(topic, client=())
    off = _judge(screen, topic, "Výkupní ceny kravského mléka loni klesly.")
    assert (off.verdict, off.rule) == (TopicVerdict.OFF_TOPIC, TopicRule.TOPIC_WORDS)
    assert off.detail == (
        "téma: „Proč lidé přecházejí na rostlinné nápoje?“; tvrzení, citace ani název zdroje "
        "nesdílí žádné z jeho slov („lidé“, „přecházejí“, „rostlinné“, „nápoje“)"
    )
    # One word, anywhere -- the claim counts here, and only here.
    assert _judge(screen, topic, "Ceny klesly.", claim="Nápoje zdražily.").verdict is (
        TopicVerdict.ON_TOPIC
    )
    assert _judge(screen, topic, "Ceny klesly.", title="Rostlinné nápoje").verdict is (
        TopicVerdict.ON_TOPIC
    )


def test_question_words_framings_and_digits_are_not_topic_words() -> None:
    topic = _q("Proč a kolik lidí kupovalo kávu v roce 2025?")
    framed = _q(RESULT_FRAMING.format(question="Kolik lidí kupovalo kávu v roce 2025?"))
    screen = _screen(topic, framed, client=())
    assert [w for _, w in screen.profiles[topic.key].topic_terms] == ["lidí", "kupovalo", "kávu"]
    # A framed question has its core's words, not the framing's.
    assert screen.profiles[framed.key].topic_terms == screen.profiles[topic.key].topic_terms
    for subject in (topic, framed):
        for quote in (
            "Proč v roce 2025 klesla cena elektřiny?",
            "Srovnatelná měření z veřejných zdrojů ukazují vývoj v čase.",
        ):
            assert _judge(screen, subject, quote).verdict is TopicVerdict.OFF_TOPIC


def test_a_subject_loses_its_own_framings_words_and_no_other() -> None:
    # A design question is never framed: no framing's word leaves it.
    audience = _q("Kdo je cílová skupina?")
    segments = _q("Jaké jsou hlavní segmenty cílové skupiny?")
    screen = _screen(audience, segments, client=())
    assert [w for _, w in screen.profiles[audience.key].topic_terms] == ["cílová", "skupina"]
    assert [w for _, w in screen.profiles[segments.key].topic_terms] == [
        "hlavní",
        "segmenty",
        "cílové",
        "skupiny",
    ]
    quote = "Cílovou skupinu tvoří především lidé ve věku 25 až 34 let."
    for subject in (audience, segments):
        judgement = _judge(screen, subject, quote, title="Cílová skupina rostlinných nápojů")
        assert judgement.verdict is TopicVerdict.ON_TOPIC
    # A module's subject keeps what fills its slots -- the module, the goal -- and loses
    # the framing's own words.
    module = _q(MODULE_FRAMING.format(module="Cílová skupina", goal="Trh rostlinných nápojů"))
    assert [w for _, w in _screen(module, client=()).profiles[module.key].topic_terms] == [
        "Cílová",
        "skupina",
        "Trh",
        "rostlinných",
        "nápojů",
    ]
    # Cut at its bound, a framed subject still loses only its framing's words.
    framed = RESULT_FRAMING.format(question=" ".join(["Kolik domácností kupuje kávu"] * 49))
    cut = _q(framed[:1499].rstrip() + "…")
    assert "srovnatelná" in cut.text and not cut.text.endswith("zdrojů")
    assert [w for _, w in _screen(cut, client=()).profiles[cut.key].topic_terms] == [
        "domácností",
        "kupuje",
        "kávu",
    ]


def test_the_clients_own_names_are_not_topic_words() -> None:
    topic = _q("Jak klienti Banky Lípa hodnotí digitální účet?")
    screen = _screen(topic)
    terms = [w for _, w in screen.profiles[topic.key].topic_terms]
    assert "Banky" not in terms and "Lípa" not in terms
    assert _judge(screen, topic, "Banka Lípa otevřela pobočku v Brně.").verdict is (
        TopicVerdict.OFF_TOPIC
    )
    # The study's name is not the client: a study named after its topic keeps its words.
    assert "digitální" in terms
    assert _judge(screen, topic, "Digitální kanály používá většina lidí.").verdict is (
        TopicVerdict.ON_TOPIC
    )


# --------------------------------------------------------------------------- unknown


def test_nothing_to_judge_by_is_undetermined_never_on_topic() -> None:
    bare = _q("Proč a kdy?")
    named = _q("Banka Lípa")
    screen = _screen(bare, named)
    for subject in (bare, named):
        judgement = _judge(screen, subject, "Banka Lípa: proč a kdy změnit účet.")
        assert (judgement.verdict, judgement.rule) == (
            TopicVerdict.UNDETERMINED,
            TopicRule.NO_TERMS,
        )
    missing = screen.judge_text("q-ffffffffffff", claim="x", quote="x", source_title="x")
    assert (missing.verdict, missing.rule) == (TopicVerdict.UNDETERMINED, TopicRule.NO_PROFILE)
    # A cross whose question the run does not hold has no words to judge it by.
    obj = _o(OATS)
    orphan = _subject(
        SubjectKind.CROSS,
        f"Kdo kupuje? — {OATS}",
        question_key="q-000000000000",
        object_key=obj.key,
    )
    cross = topic_screen((obj, orphan), client_terms=())
    assert _judge(cross, orphan, FACT).verdict is TopicVerdict.UNDETERMINED


def test_a_detail_is_in_words_as_written_never_stems() -> None:
    topic = _q(TRUST)
    screen = _screen(topic)
    detail = _judge(screen, topic, "Výkupní ceny mléka klesly.").detail
    assert "„důvěřují“" in detail and "„běžného“" in detail
    for stem in ("duveruj", "bezn", "uct", "klient"):
        assert stem not in detail.split("„")[-1]
    assert "„klienti“" in detail


# ------------------------------------------------------------------ every topic a run holds

DESIGN: dict[str, Any] = {
    "title": "Rostlinné nápoje",
    "goal": "Porozumět trhu rostlinných nápojů před uvedením nového nápoje.",
    "research_plan": {
        "research_questions": [
            "Proč lidé přecházejí na rostlinné nápoje?",
            "Kdo kupuje mandlový nápoj?",
        ]
    },
    "sections": [
        {
            "type": "questions",
            "questions": [
                {
                    "id": "q1",
                    "text": "Jaký podíl domácností kupuje rostlinné nápoje?",
                    "kategorie": ["Ano", "Ne"],
                }
            ],
        },
        {
            "type": "object_battery",
            "id": "napoje",
            "title": "Nápoje",
            "object_family": "rostlinné nápoje",
            "objects": [OATS, ALMOND, SOY],
            "object_question": "Jak hodnotíte {object}?",
        },
    ],
}
RUN = "RUN-00000000000000a1"


def _targets(battery: str, a: str, b: str) -> list[ResearchTargetRef]:
    run: dict[str, Any] = {"research_run_id": RUN}
    agg = {**run, "aggregate_artifact_id": "ART-00000000000000a3"}
    soc = {**run, "sociomap_artifact_id": "ART-00000000000000a4", "battery_id": battery}
    targets: list[ResearchTargetRef] = [
        ResultQuestionTarget(kind="RESULT_QUESTION", question_id="q1", **agg),
        ResultBatteryObjectTarget(
            kind="RESULT_BATTERY_OBJECT", battery_id=battery, object_id=a, **agg
        ),
        SociomapTarget(kind="SOCIOMAP", **soc),
        SociomapObjectTarget(kind="SOCIOMAP_OBJECT", object_id=b, **soc),
        SociomapRelationshipTarget(
            kind="SOCIOMAP_RELATIONSHIP", source_object_id=a, target_object_id=b, **soc
        ),
    ]
    targets += [
        AnalysisModuleTarget(
            kind="ANALYSIS_MODULE",
            analysis_artifact_id="ART-00000000000000a5",
            module_id=module,
            **run,
        )
        for module in AnalysisModuleId
    ]
    return targets


def _judgeable(screen: TopicScreen) -> None:
    for profile in screen.profiles.values():
        if profile.kind in (SubjectKind.OBJECT, SubjectKind.CROSS):
            assert profile.object_name, profile.text
        if profile.kind in (SubjectKind.QUESTION, SubjectKind.CROSS):
            assert profile.topic_terms, profile.text


def test_every_interpretation_target_kinds_mission_can_be_judged() -> None:
    spec, problems = compile_design(DESIGN)
    assert spec is not None, problems
    (battery,) = spec.batteries
    a, b = (o.id for o in battery.objects[:2])
    kinds = set()
    for target in _targets(battery.id, a, b):
        subjects = interpretation_mission(
            target, specification=spec.model_dump(mode="json"), design=DESIGN
        )
        assert subjects, target.kind
        kinds.add(target.kind)
        screen = topic_screen(subjects, client_terms=CLIENT)
        assert set(screen.profiles) == {s.key for s in subjects}
        _judgeable(screen)
    assert kinds == {
        "RESULT_QUESTION",
        "RESULT_BATTERY_OBJECT",
        "ANALYSIS_MODULE",
        "SOCIOMAP",
        "SOCIOMAP_OBJECT",
        "SOCIOMAP_RELATIONSHIP",
    }


def test_a_designs_crosses_are_their_question_about_their_object() -> None:
    knowledge = FrozenKnowledge(items=(), omitted_ids=(), retrieval_limit=200)
    request = DeepResearchRequest(
        harness_version=HARNESS_VERSION,
        design_revision_id="REV-1",
        design_revision=1,
        preset="DEEP",
        channels=(Channel.WEB,),
        brief=brief_digest(DESIGN),
        subjects=extract_subjects(DESIGN, knowledge),
        questionnaire=screen_questions(DESIGN),
        knowledge=knowledge,
        client_terms=CLIENT,
    )
    subjects = tuple(dict.fromkeys(s for s, _ in track_slots(request, preset("DEEP"))))
    crosses = [s for s in subjects if s.kind is SubjectKind.CROSS]
    assert len(crosses) == 6
    screen = topic_screen(subjects, client_terms=request.client_terms)
    _judgeable(screen)
    cross = next(c for c in crosses if c.text.endswith(ALMOND) and "Proč" in c.text)
    profile = screen.profiles[cross.key]
    assert profile.object_label == ALMOND
    assert [w for _, w in profile.topic_terms] == ["lidé", "přecházejí", "rostlinné", "nápoje"]
    # R1 for the object, R3 for the question.
    assert _judge(screen, cross, FACT).rule is TopicRule.OBJECT_NAMED
    assert _judge(screen, cross, "Lidé kupují mandlový nápoj kvůli chuti.").verdict is (
        TopicVerdict.ON_TOPIC
    )
    assert _judge(screen, cross, "Mandlové mléko zdražilo.").rule is TopicRule.TOPIC_WORDS


# --------------------------------------------------------------------------- the concept table

RETAIL = {f.family_id: f for f in CONCEPT_FAMILIES}["retail_banking_products"]


@pytest.mark.parametrize(
    ("concept", "texts"),
    [
        (
            "běžný účet",
            [
                "Běžný účet založíte online.",
                "Poplatek za vedení běžného účtu klesl.",
                "Klienti s běžným účtem platí kartou.",
                "Banky nabízejí běžné účty zdarma.",
                "Srovnání běžných účtů.",
                "Platební účet se základními funkcemi.",
                "The current account market.",
            ],
        ),
        (
            "spořicí účet",
            [
                "Spořicí účet úročí vklady.",
                "Úrok spořicího účtu vzrostl.",
                "Na spořicích účtech mají lidé víc peněz.",
                "Savings accounts pay more.",
            ],
        ),
        (
            "hypotéka",
            [
                "Hypotéka zdražila.",
                "Zájem o hypotéky roste.",
                "Klienti splácejí hypotéku déle.",
                "Sazby hypoték klesly.",
                "Poskytovatel hypotečního úvěru.",
                "Úvěr na bydlení je dražší.",
                "Mortgage rates fell.",
            ],
        ),
        (
            "úvěr",
            [
                "Spotřebitelský úvěr je drahý.",
                "Splátky úvěrů rostou.",
                "Půjčka od banky.",
                "Počet půjček klesl.",
                "Loans grew.",
            ],
        ),
        (
            "kreditní karta",
            [
                "Kreditní karta s odměnami.",
                "Platby kreditní kartou.",
                "Počet kreditních karet roste.",
                "Credit cards are popular.",
            ],
        ),
        (
            "pojištění",
            [
                "Pojištění domácnosti zdražilo.",
                "Cestovní pojistka.",
                "Lidé ruší pojistky.",
                "Insurance premiums rose.",
            ],
        ),
        (
            "investice",
            [
                "Podílový fond pro začátečníky.",
                "Investiční fondy rostou.",
                "Zájem o investování roste.",
                "Mutual funds charge fees.",
            ],
        ),
        (
            "penzijní spoření",
            [
                "Doplňkové penzijní spoření.",
                "Účastníci penzijního spoření.",
                "Penzijní připojištění.",
                "Penzijní fondy zhodnotily úspory.",
                "Pension funds grew.",
            ],
        ),
        (
            "stavební spoření",
            [
                "Stavební spoření s podporou státu.",
                "Smlouvy stavebního spoření.",
                "Building savings schemes.",
            ],
        ),
    ],
)
def test_each_concept_is_named_in_the_forms_a_text_writes_it_in(
    concept: str, texts: list[str]
) -> None:
    for text in texts:
        assert RETAIL.named(text) == {concept}, text


def test_the_longest_phrase_names_the_concept_and_neutral_phrases_name_none() -> None:
    assert RETAIL.named("Hypoteční úvěr na nový byt.") == {"hypotéka"}
    assert RETAIL.named("Vklady jsou chráněny pojištěním vkladů.") == frozenset()
    # A bare account names no concept: a savings account is one too.
    assert RETAIL.named("Klienti si účet založí za deset minut.") == frozenset()
    # Phrases do not run across a quote and its title: each is read on its own.
    assert RETAIL.named("běžný") == RETAIL.named("účet") == frozenset()


def test_a_kind_of_the_topics_concept_is_no_swap() -> None:
    # A mortgage is a loan: a loan topic keeps a mortgage source, never the other way round.
    loans, mortgages = _q("Jak klienti vnímají úvěry?"), _q("Jak klienti vnímají hypotéky?")
    screen = _screen(loans, mortgages, client=())
    quote = "Objem nově poskytnutých hypotečních úvěrů vzrostl o 20 %."
    assert _judge(screen, loans, quote, title="Hypoteční trh 2025").verdict is (
        TopicVerdict.ON_TOPIC
    )
    swap = _judge(screen, mortgages, "Splátky spotřebitelských úvěrů rostou.")
    assert (swap.rule, swap.detail) == (
        TopicRule.CONCEPT_SWAP,
        "téma: „hypotéka“; zdroj jmenuje: „úvěr“",
    )
    assert RETAIL.broader({"hypotéka"}) == {"hypotéka", "úvěr"}
    assert RETAIL.broader({"běžný účet"}) == {"běžný účet"}
    # A kind names concepts of its own family, or the table does not load.
    with pytest.raises(ValueError, match="kinds name no concept"):
        ConceptFamily.declare("f", [("a", ())], kinds=[("a", "b")])


def test_no_phrase_names_two_concepts() -> None:
    families: list[ConceptFamily] = list(CONCEPT_FAMILIES)
    for family in families:
        owners: dict[tuple[str, ...], str] = {}
        for concept in family.concepts:
            for marker in concept.markers:
                assert owners.setdefault(marker, concept.name) == concept.name, marker
            assert concept.markers
        assert not set(owners) & set(family.neutral)


def test_the_concept_table_is_the_version_it_names() -> None:
    # A changed phrase is a changed table: change CONCEPTS_VERSION with it, then this pin.
    table = json.dumps(concept_table(), ensure_ascii=False, sort_keys=True).encode()
    assert (CONCEPTS_VERSION, hashlib.sha256(table).hexdigest()) == (
        "aia-dr-concepts-1",
        "2a0e154df8290a128760dc0847b7359b285a77be8fbd84c24e1f0091e9ac6951",
    )


def test_the_declared_rules_are_the_version_they_name() -> None:
    # A changed word list, framing or fold is a changed version: change TOPICALITY_VERSION
    # with it, then this pin.
    data = json.dumps(
        {"version": TOPICALITY_VERSION, "rules": declared_rules()},
        ensure_ascii=False,
        sort_keys=True,
    ).encode()
    assert (TOPICALITY_VERSION, hashlib.sha256(data).hexdigest()) == (
        "aia-dr-topicality-1/aia-dr-filters-1/aia-dr-concepts-1",
        "907e5ccdc59772caef804799e8f4c084b3052c232624614b089a37ff775e2f3d",
    )


def test_the_rules_version_carries_the_term_rules_and_the_table() -> None:
    assert TOPICALITY_VERSION.startswith("aia-dr-topicality-")
    assert FILTERS_VERSION in TOPICALITY_VERSION and CONCEPTS_VERSION in TOPICALITY_VERSION


# --------------------------------------------------------------------------- measured

_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def test_measured_topicality() -> None:
    """The screen on the filters' fictional corpus: 4 questions x 44 documents, each
    document's first sentence as the claim and the quote, no title. The labels are the
    corpus's ``relevant_to``. Its topics are questions that name no declared concept, so the
    whole screen comes down to R3 here. Set on no data here: the numbers are what the rules do,
    recorded, and a rule or label change moves them in the same commit."""
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    subjects = {q["id"]: _q(q["text"]) for q in corpus["questions"]}
    screen = topic_screen(tuple(subjects.values()), client_terms=())
    tally = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for question_id, subject in subjects.items():
        for document in corpus["documents"]:
            sentence = _SENTENCE.split(document["text"].strip())[0]
            on = _judge(screen, subject, sentence).verdict is TopicVerdict.ON_TOPIC
            relevant = question_id in document["relevant_to"]
            tally[("t" if on == relevant else "f") + ("p" if on else "n")] += 1
    # 176 pairs, 27 relevant. Kept: 25 of 27 relevant (missed: a German sentence and "Sdílená
    # kola" under e-bikes). Set aside: 120 of 149 irrelevant; the 29 kept share one generic
    # word with their question -- "trh", "Česku", "ceny" -- which is all R3 asks.
    assert tally == {"tp": 25, "fp": 29, "fn": 2, "tn": 120}
