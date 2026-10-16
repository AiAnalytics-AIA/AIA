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


def _selection(**over: Any) -> dict[str, Any]:
    return {
        "dimensions": ["media", "finance"],
        "dimensions_unmatched": [],
        "dimensions_applied": False,
        "dimensions_reason": "dimensions_await_population_draw",
        "audience_filters": {"kraj": ["Praha"]},
        "filters_applied": False,
        "filters_reason": "filters_await_population_draw",
        **over,
    }


def test_a_panel_run_says_its_respondents_are_modelled_from_the_population_it_read() -> None:
    words = _words(
        {"persona_source": "panel", "population": POPULATION, "selection": _selection()},
        DataOrigin.MODELLED_AI_PANEL,
    )
    assert "AI respondenti" in words and "modelováno" in words
    assert "Běh zaznamenal populaci v17.4. Respondenti byli vybráni z ní." in words
    # Settled as the run screen settles it: a drawn run applied what awaited the draw.
    assert "Dimenze vybrané v návrhu (media, finance) se uplatnily na respondenty." in words
    assert "Filtry cílové skupiny vybrané v návrhu (kraj) se uplatnily na respondenty." in words


def test_a_fictional_run_says_it_used_invented_people_and_applied_no_filters() -> None:
    words = _words(
        {
            "fieldwork_source": "synthetic_fixture",
            "persona_source": "fictional_roster",
            "population": {**POPULATION, "read_by_fieldwork": False},
            "selection": _selection(
                dimensions_reason="dimensions_need_population_draw",
                filters_reason="filters_need_population_draw",
            ),
        },
        DataOrigin.SYNTHETIC_FIXTURE,
    )
    assert "smyšlení respondenti" in words
    assert "Respondenti z ní nepocházejí" in words
    assert "(media, finance) neuplatnily se: určují témata profilu jen respondentům" in words
    assert "(kraj) neuplatnily se: platí jen pro respondenty vybrané z populace" in words


def test_a_run_that_recorded_no_selection_says_so_and_claims_nothing_stored() -> None:
    """F2: the chapter said filters and dimensions were "stored with the run" whatever the run
    recorded; the Fio run's results page said it recorded none."""
    words = _words(
        {"persona_source": "fictional_roster", "population": POPULATION},
        DataOrigin.SYNTHETIC_AI_FICTIONAL,
    )
    assert "Běh nezaznamenal, které dimenze a filtry cílové skupiny návrh vybral" in words
    assert "uložené" not in words


def test_a_run_whose_design_selected_nothing_says_that() -> None:
    empty = _selection(
        dimensions=[], audience_filters={}, dimensions_reason=None, filters_reason=None
    )
    words = _words({"selection": empty}, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    assert "Návrh nevybral žádné dimenze ani filtry cílové skupiny." in words


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


# The answerability a run recorded at start (plan research-integrity-report chunk 1).

_RQ = "Jak klienti důvěřují digitálnímu účtu?"


def _note(**extra: Any) -> dict[str, Any]:
    gap = {
        "kind": "not_answerable",
        "research_question": _RQ,
        "verdict": "UNKNOWN",
        "reasons": ["unlinked_design"],
        "measures": [],
    }
    return {
        "rules": "aia-answerability-1",
        "capable": False,
        "digest": "a" * 64,
        "linked": False,
        "research_questions": [
            {"text": _RQ, "verdict": "UNKNOWN", "reasons": ["unlinked_design"], "measures": []}
        ],
        "gaps": [gap],
        **extra,
    }


def test_a_run_started_before_the_check_says_it_recorded_nothing_never_capable() -> None:
    words = _words({}, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    assert "nezaznamenal, zda dotazník měří každou výzkumnou otázku" in words


def test_an_acknowledged_gap_is_printed_with_the_persons_reason() -> None:
    meta = {"answerability": _note(acknowledgement={"reason": "Test postupu.", "by": "u1"})}
    words = _words(meta, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    assert "Předem nešlo ověřit, že běh zodpoví tyto výzkumné otázky: " in words
    assert f"„{_RQ}“ (žádná otázka dotazníku neuvádí, na kterou výzkumnou otázku odpovídá)" in words
    assert "„Test postupu.“" in words
    assert "nemohl" not in words  # UNKNOWN is not UNANSWERABLE
    section = compose_method_section(meta, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    table = next(
        b for b in section.blocks if isinstance(b, Table) and b.id == "tab-run-answerability"
    )
    (row,) = table.rows
    assert isinstance(row.cells[2], TextCell)
    assert "žádná otázka dotazníku neuvádí" in row.cells[2].text


def test_questions_with_the_same_reason_share_one_statement_of_it() -> None:
    # The rendered report (research-integrity-report 4) repeated one reason after every
    # question, right below the table that gave it; each reason is still said once.
    other = "Proč lidé odcházejí?"
    third = "Co by je udrželo?"
    note = _note()
    note["gaps"] = [
        note["gaps"][0],
        {**note["gaps"][0], "research_question": other},
        {**note["gaps"][0], "research_question": third, "reasons": ["no_citable_measure"]},
    ]
    words = _words({"answerability": note}, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    assert (
        f"„{_RQ}“ a „{other}“ (žádná otázka dotazníku neuvádí, na kterou výzkumnou otázku "
        f"odpovídá); „{third}“ (měří ji jen otevřené otázky nebo položky, které analýza necituje)"
    ) in words
    assert words.count("žádná otázka dotazníku neuvádí") == 1  # prose only: once, not per question


def test_an_unenforced_gap_says_nobody_confirmed_it() -> None:
    words = _words({"answerability": _note(enforced=False)}, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    assert "Při spuštění to nikdo nepotvrdil" in words


def test_an_analysis_retry_says_it_was_exempt_not_that_nothing_was_enforced() -> None:
    words = _words(
        {"answerability": _note(exempt="analysis_retry")}, DataOrigin.SYNTHETIC_AI_FICTIONAL
    )
    assert "opakoval jen analýzu nad již sebranými daty" in words
    assert "nevyžadovala" not in words


def test_the_client_report_says_what_could_not_be_answered_without_internals() -> None:
    meta = {
        "answerability": _note(
            acknowledgement={
                "reason": "Claude: interní test.",
                "by": "u1",
                "inherited_from": "RUN-1",
            }
        )
    }
    section = compose_method_section(meta, DataOrigin.MODELLED_AI_PANEL, client=True)
    words = "\n".join(
        "".join(i.text for i in b.content if isinstance(i, Text))
        for b in section.blocks
        if isinstance(b, (Paragraph, Callout))
    )
    assert _RQ in words and "Předem nešlo ověřit" in words
    assert "RUN-" not in words and "Claude" not in words and "odůvodněním" not in words


def test_a_capable_run_names_the_questions_whose_support_fieldwork_decided() -> None:
    note = _note(capable=True, gaps=[], pending=[_RQ])
    note["research_questions"][0].update(verdict="UNKNOWN", reasons=[], measures=["q1"])
    words = _words({"answerability": note}, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    assert "měření, jehož čísla může analýza citovat" in words
    assert f"až podpora zjištěná při sběru u těchto výzkumných otázek: {_RQ}." in words
    section = compose_method_section({"answerability": note}, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    table = next(
        b for b in section.blocks if isinstance(b, Table) and b.id == "tab-run-answerability"
    )
    (row,) = table.rows
    assert isinstance(row.cells[1], TextCell) and row.cells[1].text == "1 položka"
    assert isinstance(row.cells[2], TextCell) and row.cells[2].text == "předem nešlo ověřit"


def test_every_gap_reason_and_verdict_has_words_and_none_prints_a_code() -> None:
    from aia_core.application.report_method import _REASON, _VERDICT
    from aia_core.domain.answerability import GapReason
    from aia_core.domain.question_outlook import Verdict

    assert set(_REASON) == {r.value for r in GapReason}
    assert set(_VERDICT) == {v.value for v in Verdict}
    note = _note()
    note["gaps"][0]["reasons"] = ["a_reason_from_the_future"]
    words = _words({"answerability": note}, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    assert "a_reason_from_the_future" not in words and "důvod uvedený v záznamu běhu" in words
