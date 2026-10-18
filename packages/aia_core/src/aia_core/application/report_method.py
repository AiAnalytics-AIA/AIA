"""Who answered, and how the run was computed, in the internal report (complete-study-report B1c).

A reader needs to know before any number who the respondents were: fictional people for a
test, or AI respondents drawn from a recorded population. The run's own records say it --
the origin its dataset carries, the persona source it pinned at start, the population it
bound and whether fieldwork read it, and the methods it pinned -- and this chapter repeats
them in words. A fact the run did not record is said to be unrecorded, never filled in
from a default.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aia_core.domain.answerability import read_answerability_note
from aia_core.domain.fieldwork import (
    MODELLED_DISCLOSURE,
    DataOrigin,
    OriginKind,
    origin_kind,
    persona_source_of,
)
from aia_core.domain.methodology.pins import run_methods
from aia_core.domain.report.model import (
    Block,
    Callout,
    CalloutKind,
    Column,
    Heading,
    Paragraph,
    Section,
    Table,
    TableRow,
    TextCell,
    text,
)
from aia_core.domain.research_design import settle_selection

_WHO: dict[OriginKind, str] = {
    OriginKind.SIMULATED: (
        "Odpovídali smyšlení respondenti vytvoření pro vývoj a testy. Nejde o lidi ani o "
        "respondenty sestavené z populace; výsledky popisují chování simulace."
    ),
    OriginKind.MODELLED: (
        f"Odpovídali AI respondenti ({MODELLED_DISCLOSURE}). Každý vychází z osoby vybrané "
        "z populace běhu: model odhadl, jak by odpověděla, a odpověď z toho vylosoval kód. "
        "Fakta o osobě (věk, kraj a podobně) nevymýšlí model, odpovídá je kód z populace."
    ),
    OriginKind.UNKNOWN: (
        "Původ odpovědí běh nezaznamenal ve tvaru, který AIA umí přečíst. Výsledky proto "
        "nelze číst jako měření ani jako modelovaný odhad."
    ),
}

_MODULE = {
    "sociomap": "Sociomapa",
    "support": "Podpora (kdy je číslo dost podložené)",
    "aggregation": "Agregace odpovědí",
    "response": "Proces odpovědi AI respondenta",
}


#: A research question's state at start, as the run recorded it (Verdict).
#: A gap's verdict where no column says what it is about: under an answer, "předem nešlo ověřit"
#: alone left out what could not be verified (review 3).
_GAP_VERDICT = {
    "UNANSWERABLE": "běh na ni odpovědět nemohl",
    "UNKNOWN": "předem nešlo ověřit, že na ni běh odpoví",
}
_VERDICT = {
    "ANSWERABLE": "běh na ni mohl odpovědět",
    "AT_RISK": "běh na ni mohl odpovědět jen s rizikem (slabá podpora nebo otevřená otázka)",
    "UNKNOWN": "předem nešlo ověřit",
    "UNANSWERABLE": "běh na ni odpovědět nemohl",
}
#: Why it was so (GapReason and the trace's reasons), for one research question and for several
#: (grouped: "ji" is "it", "je" is "them"). Closed: test_report_method checks totality.
_REASON: dict[str, tuple[str, str]] = {
    "unlinked_design": (
        "žádná otázka dotazníku neuvádí, na kterou výzkumnou otázku odpovídá",
        "žádná otázka dotazníku neuvádí, na kterou výzkumnou otázku odpovídá",
    ),
    "unmeasured": ("žádná otázka dotazníku ji neměří", "žádná otázka dotazníku je neměří"),
    "comparison_needs_tracked_set": (
        "pořadí vyžaduje sledovanou sadu, žádná ji neměří",
        "pořadí vyžaduje sledovanou sadu, žádná je neměří",
    ),
    "comparison_needs_concept_set": (
        "test A/B vyžaduje sadu testu konceptů",
        "test A/B vyžaduje sadu testu konceptů",
    ),
    "comparison_set_unanswerable": (
        "sadu, která by objekty seřadila nebo koncepty porovnala, běh celou nezodpoví",
        "sadu, která by objekty seřadila nebo koncepty porovnala, běh celou nezodpoví",
    ),
    "segments_unavailable": (
        "srovnání segmentů AIA zatím neumí",
        "srovnání segmentů AIA zatím neumí",
    ),
    "comparison_unknown": ("neznámý způsob srovnání", "neznámý způsob srovnání"),
    "measures_unanswerable": (
        "měří ji jen otázky, na které běh neodpoví",
        "měří je jen otázky, na které běh neodpoví",
    ),
    "no_citable_measure": (
        "měří ji jen otevřené otázky nebo položky, jejichž čísla se necitují",
        "měří je jen otevřené otázky nebo položky, jejichž čísla se necitují",
    ),
}
_REASON_UNKNOWN = ("důvod uvedený v záznamu běhu", "důvod uvedený v záznamu běhu")


def _items(n: int) -> str:
    """'1 položka', '3 položky', '5 položek'."""
    word = "položka" if n == 1 else "položky" if 2 <= n <= 4 else "položek"
    return f"{n} {word}"


def _why(reasons: Any, *, plural: bool) -> str:
    worded = [_REASON.get(str(r), _REASON_UNKNOWN)[1 if plural else 0] for r in reasons or ()]
    return ", ".join(dict.fromkeys(worded))


def _gap_lines(gaps: list[Mapping[str, Any]]) -> str:
    """Gaps in words: the research questions, and why, never a code. Questions with the same
    reasons share one statement of them, in the plural when there are several: the rendered
    Fio-like report repeated one reason after every question, right below the table that had
    just given it (research-integrity-report 4)."""
    groups: dict[tuple[str, ...], list[str]] = {}
    for gap in gaps:
        key = tuple(dict.fromkeys(str(r) for r in gap.get("reasons") or ()))
        groups.setdefault(key, []).append(str(gap.get("research_question")))
    lines = []
    for reasons, questions in groups.items():
        why = _why(reasons, plural=len(questions) > 1)
        lines.append(_quoted(questions) + (f" ({why})" if why else ""))
    return "; ".join(lines)


def _quoted(questions: list[str]) -> str:
    """„A“, „B“ a „C“: a research question ends in its own question mark, so a separator after
    it read "Česku?; Proč" in the rendered report."""
    marked = [f"„{q}“" for q in questions]
    return marked[0] if len(marked) == 1 else ", ".join(marked[:-1]) + " a " + marked[-1]


def research_question_gaps(meta: Mapping[str, Any]) -> dict[str, str]:
    """Each research question the run recorded as a gap at start, in words (its verdict and why),
    keyed by its text with whitespace folded: for the chapter that answers the research
    questions, which must not read as if those answers rest on a measure (review, 2026-10-16:
    the gaps were said chapters later, under answers given with confidence)."""
    note = read_answerability_note(meta)
    if note is None:
        return {}
    gaps: dict[str, str] = {}
    for gap in note["gaps"]:
        if not isinstance(gap, Mapping) or not gap.get("research_question"):
            continue
        why = _why(gap.get("reasons"), plural=False)
        words = _GAP_VERDICT.get(str(gap.get("verdict")), "stav nelze přečíst")
        gaps[" ".join(str(gap["research_question"]).split())] = words + (f" ({why})" if why else "")
    return gaps


def research_question_gap(gaps: Mapping[str, str], question: str) -> str | None:
    """What the run recorded at start about ``question`` (:func:`research_question_gaps`), or
    ``None`` when it recorded no gap for it: matched as the report matches it, whitespace
    folded, so every surface that shows an answer to it says the same (PC2)."""
    return gaps.get(" ".join(question.split()))


def _answerability_blocks(meta: Mapping[str, Any], *, client: bool = False) -> list[Block]:
    """What the run recorded at start about answering its research questions: each one with
    its measures and state, and the decision that let it start with gaps. From the run's frozen
    record only; a run that recorded none says so and is never read as capable.

    ``client``: the client report gives question-level results and no written answers to the
    research questions, so it says what the questionnaire could measure for each, never what an
    analysis or an answers chapter (which it does not contain) would show; who decided, their
    reason, run ids and how AIA was configured stay internal."""
    note = read_answerability_note(meta)
    blocks: list[Block] = [Heading("Výzkumné otázky před spuštěním běhu", 2)]
    if note is None:
        recorded = "answerability" in meta
        blocks.append(
            Paragraph(
                text(
                    (
                        "Záznam běhu o tom, zda dotazník měří každou výzkumnou otázku, AIA "
                        "nedokáže přečíst; nic se z něj neusuzuje."
                        if recorded
                        else "Běh nezaznamenal, zda dotazník měří každou výzkumnou otázku; "
                        "byl spuštěn před zavedením této kontroly."
                    )
                    + (
                        ""
                        if client
                        else " Zda zpráva odpovídá na všechny otázky, posuďte podle kapitoly "
                        "s odpověďmi a podle dotazníku v příloze."
                    )
                )
            )
        )
        return blocks
    # A research question that is a gap reads by its gap (records whose verdict was the
    # trace's: its best over every measure, an open question's included).
    gap_of = {
        str(g.get("research_question")): g
        for g in note["gaps"]
        if isinstance(g, Mapping) and g.get("research_question")
    }
    linked = note.get("linked") is not False
    rows = []
    for traced in note["research_questions"]:
        if not isinstance(traced, Mapping):
            continue
        gap = gap_of.get(str(traced.get("text")), {})
        q = {**traced, **{k: gap[k] for k in ("verdict", "reasons") if k in gap}}
        why = _why(q.get("reasons"), plural=False)
        measures = q.get("measures") or []
        rows.append(
            TableRow(
                (
                    TextCell(str(q.get("text") or "")),
                    # Unlinked: the design declares no links, which says nothing of what the
                    # questionnaire measures -- never "nothing".
                    TextCell(
                        _items(len(measures)) if measures else "nic" if linked else "neuvedeno"
                    ),
                    TextCell(
                        _VERDICT.get(str(q.get("verdict")), "stav nelze přečíst")
                        + (f" ({why})" if why else "")
                    ),
                )
            )
        )
    pending = [str(p) for p in note.get("pending") or []]
    if rows:
        blocks.append(
            Table(
                id="tab-run-answerability",
                title="Co dotazník měřil pro každou výzkumnou otázku",
                columns=(
                    Column("Výzkumná otázka", width_weight=4),
                    Column("Měřeno", width_weight=1),
                    Column("Stav při spuštění", width_weight=3),
                ),
                rows=tuple(rows),
                source="Záznam běhu (kontrola výzkumných otázek při jeho spuštění)",
                notes=(
                    "Stav vychází z návrhu a pravidel podpory platných při spuštění, nikoli "
                    "z výsledků." + ("" if client else " O odpovědi rozhoduje až analýza."),
                    *(
                        ()
                        if linked
                        else (
                            "„Neuvedeno“: návrh u žádné otázky dotazníku neuvádí, kterou "
                            "výzkumnou otázku měří; co dotazník skutečně měří, záznam neříká.",
                        )
                    ),
                ),
            )
        )
    gaps = [g for g in note["gaps"] if isinstance(g, Mapping) and g.get("research_question")]
    none_stated = any(
        isinstance(g, Mapping) and g.get("kind") == "no_research_questions" for g in note["gaps"]
    )
    unanswerable = [g for g in gaps if g.get("verdict") == "UNANSWERABLE"]
    unverified = [g for g in gaps if g.get("verdict") != "UNANSWERABLE"]
    pending_sentence = (
        "Zda data stačí, rozhodla až podpora zjištěná při sběru u "
        + ("této výzkumné otázky: " if len(pending) == 1 else "těchto výzkumných otázek: ")
        + _quoted(pending)
        + "."
        if pending
        else ""
    )
    if not gaps and not none_stated:
        blocks.append(
            Paragraph(
                text(
                    # The client wording claims what the record holds: a measure the run
                    # collected answers to, never that it could answer the research question
                    # (a pending one's support was unknown at start; review 3).
                    (
                        "Podle záznamu ze spuštění měřila každou výzkumnou otázku alespoň "
                        "jedna otázka dotazníku, na kterou běh sbíral odpovědi."
                        if client
                        else "Při spuštění měla každá výzkumná otázka alespoň jedno měření, "
                        "jehož čísla může analýza citovat."
                    )
                    + (f" {pending_sentence}" if pending_sentence else "")
                )
            )
        )
        return blocks
    parts: list[str] = []
    if none_stated:
        parts.append(
            "Návrh neuváděl žádnou výzkumnou otázku."
            if client
            else "Návrh neuváděl žádnou výzkumnou otázku, takže analýza neměla na co odpovědět."
        )
    if unanswerable:
        parts.append(
            "Běh nemohl odpovědět na "
            + ("tuto výzkumnou otázku: " if len(unanswerable) == 1 else "tyto výzkumné otázky: ")
            + _gap_lines(unanswerable)
            + "."
        )
    if unverified:
        parts.append(
            "Předem nešlo ověřit, že běh zodpoví "
            + ("tuto výzkumnou otázku: " if len(unverified) == 1 else "tyto výzkumné otázky: ")
            + _gap_lines(unverified)
            + "."
        )
    if gaps:
        # Said by what the record holds, never by the measure: a comparison gap's measures
        # were linked and answered, only the comparison was not shown (review 3).
        one = len(gaps) == 1
        parts.append(
            "Tato zpráva uvádí výsledky jednotlivých otázek dotazníku, nikoli odpovědi na "
            "výzkumné otázky; že z nich vyplývá odpověď na "
            + ("tuto výzkumnou otázku" if one else "tyto výzkumné otázky")
            + ", běh při spuštění nedoložil."
            if client
            else (
                "Odpověď, kterou na ni zpráva přesto uvádí, čtěte jako nedoloženou: běh při "
                "spuštění nedoložil, že na ni odpoví."
                if one
                else "Odpovědi, které na ně zpráva přesto uvádí, čtěte jako nedoložené: běh "
                "při spuštění nedoložil, že na ně odpoví."
            )
        )
    if pending_sentence:
        parts.append(pending_sentence)
    held = note.get("acknowledgement")
    if not client:
        if isinstance(held, Mapping):
            # The choice by the name the Run screen gave it (D1, 2026-10-17); the record is the
            # acknowledgement it always was.
            inherited = held.get("inherited_from")
            parts.append(
                "Výzkumník zvolil Pokračovat s omezeními s odůvodněním: "
                f"„{held.get('reason')}“"
                + (f" (volba převzata z běhu {inherited})." if inherited else ".")
                + " Kdo volbu udělal, je v záznamu schválení."
            )
        elif note.get("exempt") == "analysis_retry":
            parts.append(
                "Tento běh opakoval jen analýzu nad již sebranými daty, a proto se potvrzení "
                "nevyžadovalo."
            )
        elif note.get("enforced") is False:
            parts.append("Při spuštění to nikdo nepotvrdil: AIA potvrzení tehdy nevyžadovala.")
    blocks.append(
        Callout(
            CalloutKind.LIMITATION,
            text(" ".join(parts)),
            title="Výzkumné otázky, na které běh nemusel odpovědět",
        )
    )
    return blocks


#: How a part of a run's selection reached its respondents, by the reason it recorded; the
#: sentence reads "{part} vybrané v návrhu (…) {reason}." with the clitic in second position.
_SELECTION_REASON = {
    "dimensions_need_population_draw": (
        "se neuplatnily: určují témata profilu jen respondentům vybraným z populace"
    ),
    "dimensions_await_population_draw": "se uplatní, až běh vybere respondenty z populace",
    "dimensions_not_persona_topics": "se neuplatnily: žádná z nich není tématem profilu",
    "dimensions_not_read_by_personas": "se neuplatnily: AIA je tehdy respondentům nepředávala",
    "filters_need_population_draw": (
        "se neuplatnily: platí jen pro respondenty vybrané z populace"
    ),
    "filters_await_population_draw": "se uplatní, až běh vybere respondenty z populace",
    "population_draw_not_completed": (
        "se neuplatnily: běh skončil dřív, než vybral respondenty z populace"
    ),
}


def _selection_blocks(meta: Mapping[str, Any], *, drawn: bool) -> list[Block]:
    """What the design selected and what reached the respondents, from the run's own record
    (``metadata.selection``) settled as the run screen settles it (``settle_selection``). A run
    that recorded none says so; nothing is filled in from today's design."""
    raw = meta.get("selection")
    if not isinstance(raw, Mapping):
        return [
            Paragraph(
                text(
                    "Běh nezaznamenal, které dimenze a filtry cílové skupiny návrh vybral "
                    "(byl spuštěn dříve, než to AIA evidovala)."
                )
            )
        ]
    selection = settle_selection(raw, drawn=drawn, ended=True)
    sentences: list[str] = []
    dimensions = [str(d) for d in selection.get("dimensions") or []]
    filters = selection.get("audience_filters") or {}
    if not dimensions and not filters:
        return [Paragraph(text("Návrh nevybral žádné dimenze ani filtry cílové skupiny."))]
    unmatched = [str(d) for d in selection.get("dimensions_unmatched") or []]
    # An unmatched dimension never reached anyone: never named among the applied ones.
    matched = [d for d in dimensions if d not in unmatched]
    for label, chosen, part in (
        ("Dimenze", dimensions, "dimensions"),
        ("Filtry cílové skupiny", [str(k) for k in filters], "filters"),
    ):
        if not chosen:
            continue
        if selection.get(f"{part}_applied") is True:
            if part == "dimensions" and not matched:
                continue
            shown = matched if part == "dimensions" else chosen
            sentences.append(
                f"{label} vybrané v návrhu ({', '.join(shown)}) se uplatnily na respondenty."
            )
        else:
            reason = _SELECTION_REASON.get(
                str(selection.get(f"{part}_reason")), "se neuplatnily (důvod v záznamu běhu)"
            )
            sentences.append(f"{label} vybrané v návrhu ({', '.join(chosen)}) {reason}.")
    # Said once: a selection whose every dimension is no topic already says so above.
    if unmatched and selection.get("dimensions_reason") != "dimensions_not_persona_topics":
        sentences.append(
            "Tyto dimenze nejsou tématem profilu respondenta a k respondentům se nedostaly: "
            + ", ".join(unmatched)
            + "."
        )
    return [Paragraph(text(" ".join(sentences)))]


def compose_method_section(
    meta: Mapping[str, Any], origin: DataOrigin | None, *, client: bool = False
) -> Section:
    """The chapter "Respondenti a výpočet", from the run's metadata and its dataset's origin.

    ``client``: the client report's version -- the same facts, without who acknowledged what,
    their reasons or run ids."""
    kind = origin_kind(origin)
    blocks: list[Block] = [Paragraph(text(_WHO[kind]))]

    try:
        persona = persona_source_of(meta)
    except ValueError:
        persona = None
    population = meta.get("population") if isinstance(meta.get("population"), Mapping) else None
    if population is None:
        blocks.append(Paragraph(text("Běh nezaznamenal, nad jakou populací byl spuštěn.")))
    else:
        label = population.get("version_label") or population.get("version_id") or "neuvedená"
        read = population.get("read_by_fieldwork") is True
        blocks.append(
            Paragraph(
                text(
                    f"Běh zaznamenal populaci {label}. "
                    + (
                        "Respondenti byli vybráni z ní."
                        if read
                        else "Respondenti z ní nepocházejí; běh ji pouze eviduje."
                    )
                )
            )
        )
    if persona is None:
        blocks.append(
            Callout(
                CalloutKind.LIMITATION,
                text("Zdroj respondentů, který běh zaznamenal, AIA nezná; neuvádí se žádný."),
            )
        )
    blocks.extend(_selection_blocks(meta, drawn=kind is OriginKind.MODELLED))

    methods = run_methods(meta)
    rows = tuple(
        TableRow(
            (
                TextCell(_MODULE[module]),
                TextCell(method.name or "záznam nelze přečíst"),
                TextCell(
                    "uložená verze z karty Metodika" if method.stored else "výchozí, z kódu AIA"
                ),
            )
        )
        for module, method in methods.items()
        if module in _MODULE
    )
    blocks.append(
        Table(
            id="tab-run-methods",
            title="Metody, podle kterých běh počítal",
            columns=(
                Column("Část výpočtu", width_weight=2),
                Column("Metoda", width_weight=2),
                Column("Původ", width_weight=2),
            ),
            rows=rows,
            source="Záznam běhu (metody připnuté při jeho spuštění)",
            notes=(
                "Běh počítá metodami, které si připnul při spuštění; pozdější změna "
                "metodiky jej nemění.",
            ),
        )
    )
    blocks.extend(_answerability_blocks(meta, client=client))
    return Section("Respondenti a výpočet", tuple(blocks), id="ch-method")
