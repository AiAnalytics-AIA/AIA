"""The internal report's chapter on who answered and how (complete-study-report B1c)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from aia_core.application.report_method import compose_method_section, research_question_gaps
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
    # The clitic in second position (review, 2026-10-16: "… neuplatnily se").
    assert "(media, finance) se neuplatnily: určují témata profilu jen respondentům" in words
    assert "(kraj) se neuplatnily: platí jen pro respondenty vybrané z populace" in words


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
    assert "Předem nešlo ověřit, že běh zodpoví tuto výzkumnou otázku: " in words
    assert f"„{_RQ}“ (žádná otázka dotazníku neuvádí, na kterou výzkumnou otázku odpovídá)" in words
    # The choice by its name on the Run screen, quoted (research-integrity-report 14, D1); the
    # reason ends the sentence it ends, never "„….“." (cross-review).
    assert (
        "Výzkumník zvolil „Pokračovat s omezeními“ s odůvodněním „Test postupu.“ "
        "Kdo volbu udělal, je v záznamu schválení."
    ) in words
    assert "“." not in words
    unended = {"answerability": _note(acknowledgement={"reason": "Test postupu", "by": "u1"})}
    assert "s odůvodněním „Test postupu“. Kdo volbu udělal" in _words(
        unended, DataOrigin.SYNTHETIC_AI_FICTIONAL
    )
    assert "nemohl" not in words  # UNKNOWN is not UNANSWERABLE
    inherited = _note(
        acknowledgement={"reason": "Test postupu.", "by": "u1", "inherited_from": "RUN-1"}
    )
    assert (
        "Výzkumník zvolil „Pokračovat s omezeními“ (volba převzata z běhu RUN-1) s odůvodněním "
        "„Test postupu.“ Kdo"
    ) in _words({"answerability": inherited}, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    section = compose_method_section(meta, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    # The gap titled as chapter 3 titles it, not "na které běh nemusel odpovědět" (read as "was
    # not required to answer"; cross-review).
    assert [b.title for b in section.blocks if isinstance(b, Callout)] == [
        "Výzkumné otázky bez doložené odpovědi"
    ]
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
        f"odpovídá); „{third}“ (měří ji jen otevřené otázky nebo položky, jejichž čísla se "
        "necitují)"
    ) in words
    assert words.count("žádná otázka dotazníku neuvádí") == 1  # prose only: once, not per question


def test_a_gap_reads_by_its_gap_in_the_table_too() -> None:
    # The trace said "at risk" (an open question beside one the run will not answer); the gap,
    # and so the table, says the run could not answer it.
    note = _note()
    note["research_questions"] = [
        {"text": _RQ, "verdict": "AT_RISK", "reasons": [], "measures": ["q3", "q4"]}
    ]
    note["gaps"] = [
        {
            "kind": "not_answerable",
            "research_question": _RQ,
            "verdict": "UNANSWERABLE",
            "reasons": ["measures_unanswerable"],
            "measures": ["q3", "q4"],
        }
    ]
    section = compose_method_section({"answerability": note}, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    table = next(
        b for b in section.blocks if isinstance(b, Table) and b.id == "tab-run-answerability"
    )
    (row,) = table.rows
    assert isinstance(row.cells[2], TextCell)
    assert row.cells[2].text.startswith("běh na ni odpovědět nemohl")
    assert "měří ji jen otázky, na které běh neodpoví" in row.cells[2].text


def test_an_unenforced_gap_says_nobody_made_the_choice() -> None:
    # The same act is "volba" in every branch (cross-review: "potvrzení" here and on retry).
    words = _words({"answerability": _note(enforced=False)}, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    assert (
        "Volbu „Pokračovat s omezeními“ AIA tehdy nevyžadovala a při spuštění ji nikdo neudělal."
    ) in words
    assert "potvrz" not in words


def test_the_run_screen_says_what_the_report_then_records_in_its_words() -> None:
    # The Run screen's notice for a deployment that does not ask for the choice
    # (answerability.notRequired) says what the report will record: the choice by the same
    # name, the gap by the callout's title, nobody making the choice by the same verb.
    cs = (Path(__file__).resolve().parents[3] / "apps/web/src/i18n/cs.ts").read_text("utf-8")
    found = re.search(r'notRequired: "([^"]*)"', cs)
    assert found is not None
    screen = found.group(1)
    words = _words({"answerability": _note(enforced=False)}, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    section = compose_method_section(
        {"answerability": _note(enforced=False)}, DataOrigin.SYNTHETIC_AI_FICTIONAL
    )
    (title,) = [b.title for b in section.blocks if isinstance(b, Callout)]
    assert "volbu „Pokračovat s omezeními“" in screen and "„Pokračovat s omezeními“" in words
    assert title is not None and title.removeprefix("Výzkumné otázky ") in screen
    assert "volbu při spuštění nikdo neudělal" in screen and "ji nikdo neudělal" in words


def test_an_analysis_retry_says_it_was_exempt_not_that_nothing_was_enforced() -> None:
    words = _words(
        {"answerability": _note(exempt="analysis_retry")}, DataOrigin.SYNTHETIC_AI_FICTIONAL
    )
    assert (
        "Tento běh opakoval jen analýzu nad již sebranými daty, a proto se u něj volba "
        "„Pokračovat s omezeními“ neprováděla."
    ) in words
    assert "nevyžadovala" not in words and "potvrz" not in words


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
    # Quoted, so the question's own mark is not followed by "." (review, 2026-10-16).
    assert f"až podpora zjištěná při sběru u této výzkumné otázky: „{_RQ}“." in words
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


# Review of the branch, 2026-10-16: what the method chapter says must be what the record shows.


def _decided(content: dict[str, Any]) -> dict[str, Any]:
    """The note a start records for ``content``, through the domain's own rule."""
    from aia_core.domain.answerability import answerability, answerability_note
    from aia_core.domain.question_outlook import question_outlook
    from aia_core.domain.research_design import compile_design
    from aia_core.domain.research_trace import comparisons_of, trace_research

    spec, problems = compile_design(content)
    assert spec is not None, problems
    items = question_outlook(spec, None)
    trace = trace_research(
        spec, content["research_plan"]["research_questions"], items, comparisons_of(content)
    )
    return answerability_note(trace, answerability(trace, items, design_revision_id="REV-1"))


def _design(*questions: dict[str, Any], rqs: list[str]) -> dict[str, Any]:
    return {
        "title": "Fiktivní",
        "n": 200,
        "research_plan": {"research_questions": rqs},
        "sections": [{"type": "questions", "questions": list(questions)}],
    }


def _rows(meta: dict[str, Any], *, client: bool = False) -> list[list[str]]:
    section = compose_method_section(meta, DataOrigin.SYNTHETIC_AI_FICTIONAL, client=client)
    table = next(
        b for b in section.blocks if isinstance(b, Table) and b.id == "tab-run-answerability"
    )
    return [[c.text for c in r.cells if isinstance(c, TextCell)] for r in table.rows]


def test_a_pending_question_beside_an_open_one_reads_as_left_to_fieldwork() -> None:
    rq = "Jak klienti důvěřují účtu?"
    note = _decided(
        _design(
            {
                "id": "q1",
                "text": "Nakolik?",
                "typ": "skala",
                "skala": [1, 5],
                "research_questions": [rq],
            },
            {"id": "q2", "text": "Proč?", "typ": "otevrena", "research_questions": [rq]},
            rqs=[rq],
        )
    )
    assert note["pending"] == [rq] and note["research_questions"][0]["trace_verdict"] == "AT_RISK"
    (row,) = _rows({"answerability": note})
    assert row[2] == "předem nešlo ověřit"


def test_a_question_only_an_open_question_measures_reads_as_unanswerable() -> None:
    rq = "Co by je přesvědčilo?"
    note = _decided(
        _design(
            {"id": "q1", "text": "Co?", "typ": "otevrena", "research_questions": [rq]}, rqs=[rq]
        )
    )
    (row,) = _rows({"answerability": note})
    assert row[2].startswith("běh na ni odpovědět nemohl")
    assert "mohl odpovědět jen s rizikem" not in row[2]


def test_several_questions_share_a_reason_in_the_plural() -> None:
    note = _note()
    note["linked"] = True
    note["gaps"] = [
        {
            "kind": "not_answerable",
            "research_question": q,
            "verdict": "UNANSWERABLE",
            "reasons": ["unmeasured"],
            "measures": [],
        }
        for q in ("Kolik?", "Proč?")
    ]
    words = _words({"answerability": note}, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    assert "„Kolik?“ a „Proč?“ (žádná otázka dotazníku je neměří)" in words


def test_pending_questions_are_named_beside_gaps_too() -> None:
    note = _note(pending=["Kolik platí?"])
    words = _words({"answerability": note}, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    assert "u této výzkumné otázky: „Kolik platí?“." in words


def test_a_design_with_no_research_question_says_so_once() -> None:
    note = _note(
        research_questions=[],
        gaps=[
            {
                "kind": "no_research_questions",
                "research_question": None,
                "verdict": None,
                "reasons": [],
                "measures": [],
            }
        ],
    )
    words = _words({"answerability": note}, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    assert words.count("Návrh neuváděl žádnou výzkumnou otázku") == 1
    assert "na ně" not in words and "modul" not in words


def test_an_unlinked_design_never_reads_as_measuring_nothing() -> None:
    (row,) = _rows({"answerability": _note()})  # linked: False
    assert row[1] == "neuvedeno"


def test_a_record_that_cannot_be_read_is_never_called_older_than_the_check() -> None:
    words = _words(
        {"answerability": {"rules": "aia-answerability-1"}}, DataOrigin.SYNTHETIC_AI_FICTIONAL
    )
    assert "nedokáže přečíst" in words and "před zavedením" not in words
    # A later rules version is still read as what it recorded.
    later = _note(rules="aia-answerability-2")
    assert "Předem nešlo ověřit" in _words(
        {"answerability": later}, DataOrigin.SYNTHETIC_AI_FICTIONAL
    )


def test_the_client_report_points_to_no_analysis_or_answers_it_does_not_contain() -> None:
    for meta in ({}, {"answerability": _note()}, {"answerability": _note(capable=True, gaps=[])}):
        section = compose_method_section(meta, DataOrigin.MODELLED_AI_PANEL, client=True)
        words = " ".join(
            "".join(i.text for i in b.content if isinstance(i, Text))
            for b in section.blocks
            if isinstance(b, (Paragraph, Callout))
        )
        notes = " ".join(n for b in section.blocks if isinstance(b, Table) for n in b.notes)
        for absent in ("kapitoly s odpověďmi", "analýz", "modul", "Pokud na ně", "Odpovědi, které"):
            assert absent not in words + notes, (meta, absent)


def test_unmatched_dimensions_are_never_named_as_applied() -> None:
    from aia_core.domain.research_design import DRAW_NOT_COMPLETED  # noqa: F401  (settled shape)

    base = {"population": POPULATION, "persona_source": "panel"}
    applied = _words(
        {
            **base,
            "selection": _selection(
                dimensions=["ekologie", "nesmysl"],
                dimensions_unmatched=["nesmysl"],
                dimensions_applied=True,
                dimensions_reason=None,
            ),
        },
        DataOrigin.MODELLED_AI_PANEL,
    )
    assert "(ekologie) se uplatnily" in applied and "nesmysl) se uplatnily" not in applied
    assert "k respondentům se nedostaly: nesmysl." in applied
    none = _words(
        {
            **base,
            "selection": _selection(
                dimensions=["nesmysl"],
                dimensions_unmatched=["nesmysl"],
                dimensions_applied=False,
                dimensions_reason="dimensions_not_persona_topics",
            ),
        },
        DataOrigin.MODELLED_AI_PANEL,
    )
    assert none.count("nesmysl") == 1  # said once


def test_each_recorded_gap_is_worded_for_the_answer_it_qualifies() -> None:
    """Review 2: the gaps were said chapters after answers given as if measured; the chapter that
    answers the research questions takes them, in words, from the run's own record."""
    spaced = {**_note(), "gaps": [{**_note()["gaps"][0], "research_question": f"  {_RQ}\n"}]}
    gaps = research_question_gaps({"answerability": spaced})
    assert gaps == {
        _RQ: "předem nešlo ověřit, že na ni běh odpoví (žádná otázka dotazníku neuvádí, na kterou "
        "výzkumnou otázku "
        "odpovídá)"
    }
    # Nothing recorded, unreadable or capable: no answer is qualified.
    assert research_question_gaps({}) == {}
    assert research_question_gaps({"answerability": {"rules": "aia-answerability-1"}}) == {}
    assert research_question_gaps({"answerability": _note(capable=True, gaps=[])}) == {}


def _segments_gap() -> tuple[str, dict[str, Any]]:
    """A research question asking for a segment comparison, measured by an answered scale item:
    a gap, though its measure was linked and answered (segments_unavailable)."""
    rq = "Liší se důvěra mladších a starších klientů?"
    content = _design(
        {
            "id": "q1",
            "text": "Nakolik?",
            "typ": "skala",
            "skala": [1, 5],
            "research_questions": [rq],
        },
        rqs=[rq],
    )
    content["research_plan"]["research_question_comparisons"] = {rq: "compare_segments"}
    return rq, _decided(content)


def test_a_comparison_gap_is_never_said_to_rest_on_no_measure() -> None:
    """Review 3: every gap read "se neopírá o měření, které by návrh … určil a běh zodpověděl",
    false for a comparison gap whose measure was linked and answered; it is said by what the
    record holds, that the run did not show it would answer."""
    rq, note = _segments_gap()
    (gap,) = note["gaps"]
    assert gap["reasons"] == ["segments_unavailable"] and gap["measures"] == ["q1"]
    for client in (False, True):
        section = compose_method_section(
            {"answerability": note}, DataOrigin.SYNTHETIC_AI_FICTIONAL, client=client
        )
        words = " ".join(
            "".join(i.text for i in b.content if isinstance(i, Text))
            for b in section.blocks
            if isinstance(b, (Paragraph, Callout))
        )
        assert "měření" not in words.split("Běh nemohl")[-1], client
        assert "nedoložil" in words, client
    assert research_question_gaps({"answerability": note}) == {
        rq: "běh na ni odpovědět nemohl (srovnání segmentů AIA zatím neumí)"
    }


def test_one_gap_is_said_in_the_singular_and_an_unverified_one_never_as_a_no() -> None:
    """Review 3: the sentence after the gaps was plural for one research question, and the
    client report said "z nich odpověď nevyplývá" for gaps only unverified (unlinked_design),
    a negative nobody established."""
    internal = _words({"answerability": _note()}, DataOrigin.SYNTHETIC_AI_FICTIONAL)
    assert "Odpověď, kterou na ni zpráva přesto uvádí, čtěte jako nedoloženou" in internal
    assert "na ně" not in internal and "těmto otázkám" not in internal
    section = compose_method_section(
        {"answerability": _note()}, DataOrigin.MODELLED_AI_PANEL, client=True
    )
    client = " ".join(
        "".join(i.text for i in b.content if isinstance(i, Text))
        for b in section.blocks
        if isinstance(b, (Paragraph, Callout))
    )
    assert "nevyplývá" not in client
    assert (
        "že z nich vyplývá odpověď na tuto výzkumnou otázku, běh při spuštění nedoložil" in client
    )


def test_the_client_report_never_calls_a_pending_question_one_the_run_could_answer() -> None:
    """Review 3: a capable run's client chapter said every research question had a measure the
    run "mohl odpovědět", beside a table row reading "předem nešlo ověřit" for a pending one."""
    rq = "Jak klienti důvěřují účtu?"
    note = _decided(
        _design(
            {
                "id": "q1",
                "text": "Nakolik?",
                "typ": "skala",
                "skala": [1, 5],
                "research_questions": [rq],
            },
            rqs=[rq],
        )
    )
    assert note["pending"] == [rq] and note["capable"]
    section = compose_method_section(
        {"answerability": note}, DataOrigin.MODELLED_AI_PANEL, client=True
    )
    words = " ".join(
        "".join(i.text for i in b.content if isinstance(i, Text))
        for b in section.blocks
        if isinstance(b, (Paragraph, Callout))
    )
    assert "mohl odpovědět" not in words
    assert "na kterou běh sbíral odpovědi" in words and "rozhodla až podpora" in words
