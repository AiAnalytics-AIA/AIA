"""Measures: a claim's number must mean what it means in the source, not only read the same.

Plan ``deep-research-web-search.md`` § 8.1, chunk 7, and the finding in its § 15.
"""

from __future__ import annotations

import pytest

from aia_core.domain.deep_research.contracts import Measure, QuarantineReason
from aia_core.domain.deep_research.grounding import (
    GROUNDING_VERSION,
    GroundableSource,
    Grounding,
    ground,
    normalise_text,
)
from aia_core.domain.deep_research.measures import (
    CONTEXT_MAX_CHARS,
    MEASURES_VERSION,
    Attribute,
    check_measures,
    claim_measures,
    context_window,
    fold,
    stated_numbers,
)


def _ground(source: str, quote: str, claim: str) -> Grounding:
    text = normalise_text(source)
    return ground(
        source_ref="S1",
        quote=quote,
        claim=claim,
        sources={"S1": GroundableSource("S1", text, ())},
    )


def _quarantined(verdict: Grounding, *needles: str) -> None:
    assert verdict.failure is QuarantineReason.MEASURE_NOT_IN_SOURCE, verdict
    # The quote is in the source: the finding keeps its span, the claim is what fails.
    assert verdict.span is not None
    for needle in needles:
        assert needle in verdict.detail, verdict.detail


# --------------------------------------------------------------------------- the finding


def test_a_household_share_claimed_as_a_share_of_adults_is_quarantined() -> None:
    """The reproduction in the plan's § 15: accepted on develop @ 757154e."""
    verdict = _ground(
        "Podle průzkumu kupuje rostlinné nápoje 45 % domácností v Česku.",
        quote="kupuje rostlinné nápoje 45 % domácností",
        claim="Rostlinné nápoje kupuje 45 % všech dospělých lidí v Česku.",
    )
    _quarantined(verdict, "45", "'dospělých'", "ADULTS")
    assert verdict.span == (15, 54)


def test_a_population_named_elsewhere_in_the_context_does_not_rescue_the_number() -> None:
    # "lidí" is in the sentence, but the source gives the 45 % to households.
    verdict = _ground(
        "Rostlinné nápoje kupuje 45 % domácností, tedy asi 1,9 milionu lidí.",
        quote="Rostlinné nápoje kupuje 45 % domácností",
        claim="Rostlinné nápoje kupuje 45 % lidí.",
    )
    _quarantined(verdict, "'lidí'", "PERSONS", "HOUSEHOLDS")


def test_a_value_in_thousands_claimed_as_units_is_quarantined() -> None:
    source = "Rostlinné nápoje pravidelně kupuje 450 tis. domácností."
    quote = "pravidelně kupuje 450 tis. domácností"
    _quarantined(
        _ground(source, quote, "Rostlinné nápoje pravidelně kupuje 450 domácností."),
        "450",
        "no scale word",
        "'tis.'",
    )
    # A scale the source does not write is as wrong as one it writes and the claim drops.
    _quarantined(
        _ground(
            "Rostlinné nápoje pravidelně kupuje 450 domácností z panelu.",
            "pravidelně kupuje 450 domácností z panelu",
            "Rostlinné nápoje pravidelně kupuje 450 tisíc domácností.",
        ),
        "'tisíc'",
    )
    # The same scale in other words is the same number.
    assert _ground(source, quote, "Pravidelně je kupuje 450 tisíc domácností.").grounded


def test_a_scale_written_as_a_header_of_the_figure_is_accepted() -> None:
    verdict = _ground(
        "Počet domácností (v tis.): 450 v roce 2025.",
        quote="Počet domácností (v tis.): 450 v roce 2025",
        claim="V roce 2025 to bylo 450 tis. domácností.",
    )
    assert verdict.grounded, verdict


@pytest.mark.parametrize(
    ("source", "quote", "claim", "needle"),
    [
        (
            "Ve školním roce 2023/24 kupovalo rostlinné nápoje 45 % domácností.",
            "2023/24 kupovalo rostlinné nápoje 45 % domácností",
            "V roce 2023 kupovalo rostlinné nápoje 45 % domácností.",
            "'2023' (Y2023)",
        ),
        (
            "V lednu 2025 kupovalo rostlinné nápoje 45 % domácností.",
            "kupovalo rostlinné nápoje 45 % domácností",
            "V březnu kupovalo rostlinné nápoje 45 % domácností.",
            "'březnu' (M03)",
        ),
        (
            "V Q1 kupovalo rostlinné nápoje 45 % domácností.",
            "kupovalo rostlinné nápoje 45 % domácností",
            "Ve třetím čtvrtletí kupovalo rostlinné nápoje 45 % domácností.",
            "(Q3)",
        ),
    ],
)
def test_a_period_absent_from_the_context_is_quarantined(
    source: str, quote: str, claim: str, needle: str
) -> None:
    _quarantined(_ground(source, quote, claim), needle)


def test_a_year_absent_from_the_quote_is_refused_by_the_number_check_first() -> None:
    # "v roce 2023" when the source says 2025: a written year is a number, so the
    # check that runs first refuses it; the measure check never sees it.
    verdict = _ground(
        "V roce 2025 kupovalo rostlinné nápoje 45 % domácností.",
        quote="kupovalo rostlinné nápoje 45 % domácností",
        claim="V roce 2023 kupovalo rostlinné nápoje 45 % domácností.",
    )
    assert verdict.failure is QuarantineReason.NUMBER_NOT_IN_QUOTE


def test_a_unit_or_denominator_the_source_does_not_give_is_quarantined() -> None:
    source = "Rostlinné nápoje zdražily o 3 p. b. a průměrná cena byla 42 Kč za litr."
    _quarantined(
        _ground(source, "Rostlinné nápoje zdražily o 3 p. b.", "Rostlinné nápoje zdražily o 3 %."),
        "'%'",
        "'p. b.'",
    )
    _quarantined(
        _ground(
            source,
            "průměrná cena byla 42 Kč za litr",
            "Průměrná cena byla 42 Kč za kilogram.",
        ),
        "'kilogram'",
    )
    _quarantined(
        _ground(source, "průměrná cena byla 42 Kč za litr", "Průměrná cena byla 42 EUR za litr."),
        "'EUR'",
    )
    assert _ground(
        source, "průměrná cena byla 42 Kč za litr", "Litr stál v průměru 42 korun za litr."
    ).grounded


def test_a_place_other_than_the_one_the_context_names_is_quarantined() -> None:
    _quarantined(
        _ground(
            "Rostlinné nápoje kupuje v Praze 45 % domácností.",
            "kupuje v Praze 45 % domácností",
            "Rostlinné nápoje kupuje 45 % domácností v Česku.",
        ),
        "'Česku' (CZ)",
        "CZ-PR",
    )
    # A page that names no place leaves the claim's place to the verifier.
    assert _ground(
        "Rostlinné nápoje kupuje 45 % domácností.",
        "Rostlinné nápoje kupuje 45 % domácností",
        "Rostlinné nápoje kupuje 45 % domácností v Česku.",
    ).grounded


# --------------------------------------------------------------------------- what passes


def test_a_correct_claim_with_population_unit_and_period_is_accepted() -> None:
    verdict = _ground(
        "Spotřeba rostlinných nápojů v Česku vzrostla v roce 2025 o 12,5 % na 41 milionů "
        "litrů. Nejrychleji rostly ovesné nápoje. V březnu 2025 kupovalo rostlinné nápoje "
        "45 % domácností.",
        quote="V březnu 2025 kupovalo rostlinné nápoje 45 % domácností.",
        claim="V Česku v březnu 2025 kupovalo rostlinné nápoje 45 procent domácností.",
    )
    assert verdict.grounded, verdict
    assert _ground(
        "Spotřeba rostlinných nápojů v Česku vzrostla v roce 2025 o 12,5 % na 41 milionů litrů.",
        "vzrostla v roce 2025 o 12,5 % na 41 milionů litrů",
        "V Česku se v roce 2025 vypilo 41 mil. l rostlinných nápojů, o 12,5 % víc.",
    ).grounded
    assert _ground(
        "Tržby za rostlinné nápoje dosáhly v roce 2025 celkem 2,1 miliardy korun.",
        "Tržby za rostlinné nápoje dosáhly v roce 2025 celkem 2,1 miliardy korun.",
        "V roce 2025 utržily rostlinné nápoje 2,1 mld. Kč.",
    ).grounded


@pytest.mark.parametrize(
    ("source_phrase", "claim_phrase"),
    [
        ("45 % domácností", "45 % domácností"),
        ("45 % domácností", "45 % všem domácnostem"),
        ("45 % osob", "45 % osoby"),
        ("45 % osob", "45 % obyvatelům"),  # one class: persons
        ("45 % obyvatel", "45 % lidí"),
        ("45 % dotázaných", "45 % respondentů"),  # one class: respondents
    ],
)
def test_czech_inflections_and_synonyms_of_one_population_match(
    source_phrase: str, claim_phrase: str
) -> None:
    verdict = _ground(
        f"Rostlinné nápoje kupuje {source_phrase} v Česku.",
        quote=f"Rostlinné nápoje kupuje {source_phrase}",
        claim=f"Rostlinné nápoje kupuje {claim_phrase}.",
    )
    assert verdict.grounded, verdict


def test_matching_ignores_diacritics_and_case() -> None:
    assert fold("DOMÁCNOSTÍ Česku Kč") == "domacnosti cesku kc"
    verdict = _ground(
        "Rostlinne napoje kupuje 45 % DOMACNOSTI v CR.",
        quote="Rostlinne napoje kupuje 45 % DOMACNOSTI",
        claim="Rostlinné nápoje kupuje 45 % domácností v ČR.",
    )
    assert verdict.grounded, verdict


def test_a_claim_that_omits_the_population_is_accepted() -> None:
    verdict = _ground(
        "Podle průzkumu kupuje rostlinné nápoje 45 % domácností v Česku.",
        quote="kupuje rostlinné nápoje 45 % domácností",
        claim="Rostlinné nápoje kupuje 45 %.",
    )
    assert verdict.grounded, verdict


def test_a_number_free_claim_and_a_claim_with_only_a_year_are_not_read() -> None:
    source = "V roce 2025 se o rostlinné nápoje zajímaly hlavně domácnosti ve městech."
    assert _ground(
        source, "o rostlinné nápoje zajímaly hlavně domácnosti", "Lidé je kupují."
    ).grounded
    assert _ground(
        source,
        "V roce 2025 se o rostlinné nápoje zajímaly",
        "V roce 2025 se o ně zajímali dospělí lidé.",
    ).grounded
    assert check_measures("Zájem o rostlinné nápoje roste.", "") is None


def test_a_word_far_from_the_number_is_not_attached_to_it() -> None:
    # "Lidé" opens the clause seven tokens before the figure: it is the sentence's
    # subject, not the figure's population, and the source's "Tržby" is not required.
    verdict = _ground(
        "Tržby za rostlinné nápoje dosáhly 2,1 miliardy korun.",
        quote="Tržby za rostlinné nápoje dosáhly 2,1 miliardy korun.",
        claim="Lidé utratili v obchodech za rostlinné nápoje celkem 2,1 miliardy korun.",
    )
    assert verdict.grounded, verdict
    # "a" joins two figures in one clause; each keeps its own population.
    (first, second) = stated_numbers("Kupuje je 45 % domácností a 30 % firem.")
    assert [p.key for p in first.populations] == ["HOUSEHOLDS"]
    assert [p.key for p in second.populations] == ["FIRMS"]


def test_a_word_that_only_looks_like_a_population_is_not_one() -> None:
    # "může" folds to "muze": not "muže" (men), whose stem is matched only by its forms.
    (n,) = stated_numbers("Až 30 % zákazníků může přejít.")
    assert [p.key for p in n.populations] == ["CUSTOMERS"]
    (n,) = stated_numbers("Trh dospěl k 30 % podílu.")
    assert n.populations == ()


# --------------------------------------------------------------------------- the window


def test_the_context_window_is_the_quotes_sentence_and_one_either_side() -> None:
    text = "První věta. Druhá věta je tady. Třetí věta s citací 45 %. Čtvrtá věta. Pátá věta."
    at = text.index("citací")
    lo, hi = context_window(text, (at, at + len("citací 45 %")))
    assert text[lo:hi].strip() == "Druhá věta je tady. Třetí věta s citací 45 %. Čtvrtá věta."
    # A quote across two sentences takes both, and one either side of them.
    at = text.index("je tady")
    lo, hi = context_window(text, (at, text.index("citací")))
    assert (
        text[lo:hi].strip()
        == "První věta. Druhá věta je tady. Třetí věta s citací 45 %. Čtvrtá věta."
    )


def test_an_abbreviation_does_not_end_a_sentence() -> None:
    text = "Trh dosáhl 2,1 mld. Kč a 450 tis. Domácnosti platí víc. Jiné."
    at = text.index("Kč")
    lo, hi = context_window(text, (at, at + 2))
    assert text[lo:hi].strip() == text[: text.index(" Jiné")] + " Jiné."
    assert text[lo:hi].startswith("Trh dosáhl 2,1 mld. Kč")


def test_the_context_window_is_capped_and_never_cuts_a_word() -> None:
    long_tail = " ".join(["slovo"] * 400)
    text = f"Začátek {long_tail} kupuje 45 % domácností {long_tail} konec."
    at = text.index("kupuje")
    end = text.index("domácností") + len("domácností")
    lo, hi = context_window(text, (at, end))
    assert at - lo <= CONTEXT_MAX_CHARS
    assert hi - end <= CONTEXT_MAX_CHARS
    assert text[lo - 1] == " " and text[lo:].startswith("slovo")
    assert text[hi] == " " and text[:hi].endswith("slovo")


def test_a_figure_in_the_neighbouring_sentence_is_inside_the_window() -> None:
    # The population was named in the sentence before: "z nich" carries it.
    verdict = _ground(
        "Průzkum se týkal domácností s dětmi. Rostlinné nápoje kupuje 45 % z nich.",
        quote="Rostlinné nápoje kupuje 45 % z nich.",
        claim="Rostlinné nápoje kupuje 45 % domácností s dětmi.",
    )
    assert verdict.grounded, verdict
    # Two sentences away is outside it.
    verdict = _ground(
        "Průzkum se týkal domácností. Byl dlouhý. Rostlinné nápoje kupuje 45 % z dotázaných.",
        quote="Rostlinné nápoje kupuje 45 % z dotázaných.",
        claim="Rostlinné nápoje kupuje 45 % domácností.",
    )
    _quarantined(verdict, "HOUSEHOLDS")


# --------------------------------------------------------------------------- the measure


def test_a_claims_measures_are_read_into_the_contract() -> None:
    # The quarter is placed in its year (aia-measures-1 read "Q3" and dropped the 2025).
    assert claim_measures("Ve 3. čtvrtletí 2025 kupovalo v Praze 45 % domácností.") == (
        Measure(value=45, unit="%", period="2025-Q3", geography="CZ-PR", population="HOUSEHOLDS"),
    )
    assert claim_measures("Tržby dosáhly 2,1 mld. Kč, cena 42 Kč/l.") == (
        Measure(value=2.1, unit="CZK", scale=1_000_000_000),
        Measure(value=42, unit="CZK", denominator="l"),
    )
    assert claim_measures("V sezóně 2024/25 roste zájem.") == ()
    # "na 45 %" is a new value, not a denominator; "na osobu" and "na 1000 obyvatel" are.
    assert claim_measures("Podíl vzrostl o 3 p. b. na 45 %.") == (
        Measure(value=3, unit="pp"),
        Measure(value=45, unit="%"),
    )
    (per_person,) = claim_measures("Spotřeba byla 12 l na osobu.")
    assert per_person == Measure(value=12, unit="l", denominator="PERSONS")
    per_thousand, _ = claim_measures("Spotřeba byla 5 kg na 1000 obyvatel.")
    assert per_thousand == Measure(value=5, unit="kg", denominator="PERSONS")


def test_grounding_carries_the_measures_version() -> None:
    assert MEASURES_VERSION in GROUNDING_VERSION
    assert GROUNDING_VERSION != "aia-grounding-1"
    assert {a.value for a in Attribute} == {
        "unit",
        "scale",
        "period",
        "population",
        "denominator",
        "geography",
    }


# --------------------------------------------------------------------------- dates and periods


def test_a_dates_day_and_month_are_not_measures() -> None:
    """Reported against aia-measures-1: three measures, the 31 and the 12 among them."""
    claim = "Česko mělo k 31. 12. 2091 celkem 10 450 tis. obyvatel."
    assert claim_measures(claim) == (
        Measure(
            value=10450,
            scale=1000,
            period="2091-12-31",
            geography="CZ",
            population="PERSONS",
        ),
    )
    day, month, year, figure = stated_numbers(claim)
    assert [n.is_period for n in (day, month, year, figure)] == [True, True, True, False]
    assert [t.key for t in figure.periods] == ["2091-12-31"]


@pytest.mark.parametrize(
    "date",
    [
        "31. 12. 2091",
        "31.12.2091",
        "2091-12-31",
        "31. prosince 2091",
        "31. prosinci 2091",
        "31. prosince roku 2091",
        "31.prosince 2091",
    ],
)
def test_every_written_form_of_a_date_is_one_period(date: str) -> None:
    (measure,) = claim_measures(f"Česko mělo k {date} celkem 10 450 tis. obyvatel.")
    assert measure.value == 10450 and measure.period == "2091-12-31"


@pytest.mark.parametrize(
    ("phrase", "key"),
    [
        ("od 1. ledna", "M01-01"),
        ("do 2. února", "M02-02"),
        ("k 15. březnu", "M03-15"),
        ("s 1. dubnem", "M04-01"),
        ("od 1. května", "M05-01"),
        ("do 30. června", "M06-30"),
        ("od 1. července", "M07-01"),
        ("do 31. srpna", "M08-31"),
        ("od 1. září", "M09-01"),
        ("do 28. října", "M10-28"),
        ("od 17. listopadu", "M11-17"),
        ("k 31. prosinci", "M12-31"),
        ("od 1. ledna 2025", "2025-01-01"),
        ("od 29. února 2024", "2024-02-29"),
    ],
)
def test_a_day_before_a_month_name_in_any_case_is_part_of_a_date(phrase: str, key: str) -> None:
    (n,) = (n for n in stated_numbers(f"Platí {phrase} pro 45 % domácností.") if not n.is_period)
    assert n.value == 45
    assert [t.key for t in n.periods] == [key]


def test_a_date_with_no_year_is_not_placed_in_one() -> None:
    (measure,) = claim_measures("Od 1. ledna kupuje rostlinné nápoje 45 % domácností.")
    assert measure.period is None
    # An impossible day is no date: its numbers stay numbers.
    assert [n.value for n in stated_numbers("Mezi 31. 2. 2025 a dneškem 45 %.") if not n.is_period][
        :2
    ] == [31, 2]


def test_a_number_at_a_sentence_end_is_still_a_number() -> None:
    # A full stop after a number ends the sentence when a capital follows: no date.
    (first, second) = claim_measures("Prodej vzrostl o 12. Poté klesl o 3 %.")
    assert first == Measure(value=12) and second == Measure(value=3, unit="%")
    # A capitalised month name after "12." starts the next sentence.
    assert [m.value for m in claim_measures("Počet vzrostl o 12. Prosinec byl slabší.")] == [12]
    # A numeric day and month need their year: "12. 12 obchodů" is two numbers.
    assert [m.value for m in claim_measures("Přibylo jich 12. 12 obchodů zavřelo.")] == [12, 12]
    # At the very end of the text.
    assert [m.value for m in claim_measures("Počet domácností vzrostl o 12.")] == [12]


@pytest.mark.parametrize(
    ("phrase", "period"),
    [
        ("ve 2. čtvrtletí 2025", "2025-Q2"),
        ("ve druhém čtvrtletí 2025", "2025-Q2"),
        ("ve 2. čtvrtletí roku 2025", "2025-Q2"),
        ("v Q2 2025", "2025-Q2"),
        ("v Q2/2025", "2025-Q2"),
        ("v 1. pololetí 2025", "2025-H1"),
        ("v březnu 2025", "2025-03"),
        ("v březnu roku 2025", "2025-03"),
        ("v prosinci 2024", "2024-12"),
        # No year next to it: not placed, and not guessed from one written elsewhere.
        ("ve 2. čtvrtletí", None),
        ("v březnu", None),
        ("v roce 2025 ve 2. čtvrtletí", "Y2025"),
        # A season's year is not a quarter's year.
        ("v Q1 2023/24", "Y2023/2024"),
    ],
)
def test_a_sub_year_period_is_placed_in_the_year_written_next_to_it(
    phrase: str, period: str | None
) -> None:
    (measure,) = claim_measures(f"Rostlinné nápoje kupovalo {phrase} 45 % domácností.")
    assert measure.period == period


def test_a_quarter_of_another_year_is_quarantined() -> None:
    # aia-measures-1 read "Q2" and "Y2025" apart, and both were in the window.
    # The quote carries every number the claim states (the number check runs first).
    source = "Ve 2. čtvrtletí 2024 kupovalo rostlinné nápoje 45 % domácností, v roce 2025 víc."
    quote = "Ve 2. čtvrtletí 2024 kupovalo rostlinné nápoje 45 % domácností, v roce 2025"
    _quarantined(
        _ground(source, quote, "Ve 2. čtvrtletí 2025 kupovalo rostlinné nápoje 45 % domácností."),
        "(2025-Q2)",
    )
    # The source's own phrase, a yearless quarter under its year, and the year alone pass.
    same = "Ve 2. čtvrtletí 2025 kupovalo rostlinné nápoje 45 % domácností."
    assert _ground(same, same, "Ve 2. čtvrtletí 2025 to bylo 45 % domácností.").grounded
    under = "V roce 2025: ve 2. čtvrtletí kupovalo rostlinné nápoje 45 % domácností."
    assert _ground(
        under, under, "Ve 2. čtvrtletí 2025 kupovalo rostlinné nápoje 45 % domácností."
    ).grounded
    assert _ground(same, same, "V roce 2025 to bylo 45 % domácností.").grounded


def test_a_date_is_checked_as_one_period() -> None:
    source = "Česko mělo k 31. 12. 2091 celkem 10 450 tis. obyvatel."
    quote = "k 31. 12. 2091 celkem 10 450 tis. obyvatel"
    # The same date in another form, and the date's year alone, are in the source.
    assert _ground(source, quote, "K 31. prosinci 2091 mělo Česko 10 450 tis. obyvatel.").grounded
    assert _ground(source, quote, "V roce 2091 mělo Česko 10 450 tis. obyvatel.").grounded
    # Another day is not.
    _quarantined(
        _ground(
            "Česko mělo k 31. 12. 2091 celkem 10 450 tis. obyvatel, k 1. 1. 2090 méně.",
            "k 31. 12. 2091 celkem 10 450 tis. obyvatel, k 1. 1. 2090",
            "K 1. lednu 2091 mělo Česko 10 450 tis. obyvatel.",
        ),
        "(2091-01-01)",
    )
    # Its day and month are not measures demanded of the source.
    assert check_measures("K 31. 12. 2091 mělo Česko 10 450 tis. obyvatel.", source) is None
