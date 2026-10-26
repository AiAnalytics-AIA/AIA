"""The hatch's pure half (lead-identity LI1): its input, its closed answer and ADR 0030 decision
3's check of a personal file."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aia_core.domain.lead_hatch import (
    BRIEF_MAX_BYTES,
    NAME_MAX_BYTES,
    HatchInput,
    HatchOutput,
    hatch_refusals,
    personal_text_refusal,
)
from aia_core.domain.research_lead import SOUL_MAX_BYTES

TRAITS = {"tone": "vecny", "answers": "strucne", "initiative": "ceka", "numbers": "vzdy_nejistota"}


def test_the_input_is_trimmed_and_closed() -> None:
    hatch = HatchInput(name="  Ada ", traits=TRAITS, brief=" Buď stručná. ")
    assert (hatch.name, hatch.brief, hatch.about) == ("Ada", "Buď stručná.", "")
    with pytest.raises(ValidationError):
        HatchInput(name="Ada", traits=TRAITS, model="x")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        HatchInput(name="Ada", traits={**TRAITS, "tone": "drsny"})
    with pytest.raises(ValidationError):
        HatchInput(name="   ", traits=TRAITS)


def test_the_input_is_bounded_in_bytes_not_only_characters() -> None:
    # 1,001 three-byte characters are within the brief's characters and over its bytes.
    with pytest.raises(ValidationError, match="bytes"):
        HatchInput(name="Ada", traits=TRAITS, brief="\u20ac" * (BRIEF_MAX_BYTES // 3 + 1))
    # Forty four-byte characters are 160 bytes: the name's byte bound holds at its characters.
    assert NAME_MAX_BYTES == 4 * 40


def test_the_answer_is_closed_and_bounded_like_a_lead_file() -> None:
    ok = HatchOutput(soul="# Ada\n- Mluvím věcně.", user="", greeting="Ahoj, jsem Ada.")
    assert ok.user == ""
    with pytest.raises(ValidationError, match="bytes"):
        HatchOutput(soul="ř" * (SOUL_MAX_BYTES // 2 + 1), greeting="Ahoj.")
    with pytest.raises(ValidationError):
        HatchOutput(soul="# Ada", greeting="Ahoj.", reply="x")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        HatchOutput(soul="", greeting="Ahoj.")


@pytest.mark.parametrize(
    "text",
    [
        "Pro Pivovar Zlatá Hora píšu stručně.",
        "pro PIVOVAR ZLATA HORA píšu stručně.",  # accents and case folded
        "Dotazník do 10 minut.",
        "Čísla vždy s intervalem 95 %.",
    ],
)
def test_a_personal_text_naming_a_client_or_a_number_is_refused(text: str) -> None:
    refused = personal_text_refusal(text, ["Pivovar Zlatá Hora", "Delta"])
    assert refused == "client_fact_in_personal_file"


@pytest.mark.parametrize(
    "text",
    [
        "Mluvím věcně a rozlišuji doložené, domněnku a návrh.",
        "Deltoid není klient: jméno se hledá celé.",  # "Delta" only as a whole word
        "Otázky jako Q3 jsou id, ne čísla.",
    ],
)
def test_working_style_alone_passes(text: str) -> None:
    assert personal_text_refusal(text, ["Pivovar Zlatá Hora", "Delta"]) is None


def test_every_file_of_the_answer_is_checked_and_named() -> None:
    output = HatchOutput(
        soul="# Ada\n- Pracuji pro Delta.",
        user="Píše otázky jako otázky.",
        greeting="Mám 2 nápady.",
    )
    assert hatch_refusals(output, ["Delta"]) == {
        "soul": "client_fact_in_personal_file",
        "greeting": "client_fact_in_personal_file",
    }
    assert hatch_refusals(HatchOutput(soul="# Ada", greeting="Ahoj."), ["Delta"]) == {}


def test_the_chosen_name_is_checked_with_the_files() -> None:
    clean = HatchOutput(soul="# Ada", greeting="Ahoj.")
    assert hatch_refusals(clean, ["Delta"], name="Delta") == {
        "name": "client_fact_in_personal_file"
    }
    assert hatch_refusals(clean, ["Delta"], name="Ada") == {}
