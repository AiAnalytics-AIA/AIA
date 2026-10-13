"""The internal report's chapter on who answered and how (complete-study-report B1c)."""

from __future__ import annotations

from typing import Any

from aia_core.application.report_method import compose_method_section
from aia_core.domain.fieldwork import DataOrigin
from aia_core.domain.report.model import Callout, Paragraph, Table, Text, TextCell


def _words(meta: dict[str, Any], origin: DataOrigin | None) -> str:
    section = compose_method_section(meta, origin)
    out = []
    for b in section.blocks:
        if isinstance(b, (Paragraph, Callout)):
            out.append("".join(i.text for i in b.content if isinstance(i, Text)))
    return "\n".join(out)


POPULATION = {"version_id": "v17_4_0", "version_label": "v17.4", "read_by_fieldwork": True}


def test_a_panel_run_says_its_respondents_are_modelled_from_the_population_it_read() -> None:
    words = _words(
        {"persona_source": "panel", "population": POPULATION}, DataOrigin.MODELLED_AI_PANEL
    )
    assert "AI respondenti" in words and "modelováno" in words
    assert "Běh zaznamenal populaci v17.4. Respondenti byli vybráni z ní." in words
    assert "respektoval filtry cílové skupiny" in words


def test_a_fictional_run_says_it_used_invented_people_and_applied_no_filters() -> None:
    words = _words(
        {
            "fieldwork_source": "synthetic_fixture",
            "persona_source": "fictional_roster",
            "population": {**POPULATION, "read_by_fieldwork": False},
        },
        DataOrigin.SYNTHETIC_FIXTURE,
    )
    assert "smyšlení respondenti" in words
    assert "Respondenti z ní nepocházejí" in words
    assert "neuplatnil" in words


def test_what_a_run_did_not_record_is_said_to_be_unrecorded() -> None:
    words = _words({"persona_source": "somebody_else"}, None)
    assert "nezaznamenal, nad jakou populací" in words
    assert "Zdroj respondentů, který běh zaznamenal, AIA nezná" in words
    assert "nelze číst jako měření" in words


def test_the_methods_table_names_each_pinned_method_and_never_guesses_an_unreadable_one() -> None:
    section = compose_method_section({"support": {"not": "a pin"}}, DataOrigin.SYNTHETIC_FIXTURE)
    (table,) = [b for b in section.blocks if isinstance(b, Table)]
    cells = {
        r.cells[0].text: r.cells[1].text
        for r in table.rows
        if isinstance(r.cells[0], TextCell) and isinstance(r.cells[1], TextCell)
    }
    assert cells["Podpora (kdy je číslo dost podložené)"] == "záznam nelze přečíst"
    assert cells["Sociomapa"] not in ("", "záznam nelze přečíst")
