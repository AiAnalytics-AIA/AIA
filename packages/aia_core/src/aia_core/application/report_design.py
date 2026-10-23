"""The study's design in the internal report (complete-study-report B1b).

A reader of the complete report needs to know what was asked before reading what came
back: the brief's goal and what the decision is for, the comparable sets the run measured,
its sample size and audience as the design stated them, and the whole questionnaire as an
appendix. The goal and decision use are the run's own Design Revision's words (F19); the rest
is words from the run's own compiled specification -- the one its evidence was computed
from -- so nothing here can describe a design the run did not execute. No result is printed:
the numbers here are the design's own sizes (the sample the design asked for, a scale's end
points) and whatever the person wrote into the goal or decision use, design facts all.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from aia_core.application.analysis_results import Brief
from aia_core.domain.report.control_tags import source_tag
from aia_core.domain.report.model import (
    Block,
    BulletList,
    Heading,
    ListItem,
    Paragraph,
    Section,
    Text,
    text,
)
from aia_core.domain.report.numbers import counted
from aia_core.domain.report.printable import xml_text
from aia_core.domain.research_design import (
    ResearchSpecification,
    SpecBattery,
    SpecQuestion,
    labelled_points,
)

_TYPE = {
    "vyber": "jedna odpověď",
    "multi": "více odpovědí",
    "skala": "škála",
    "otevrena": "otevřená odpověď",
}


@dataclass(frozen=True, slots=True)
class DesignSections:
    """The design chapter (after the introduction) and the questionnaire appendix."""

    chapter: Section
    appendix: Section


def scale_wording(scale: tuple[int, int], labels: Sequence[str]) -> str:
    """A labelled scale's points as the report prints them, beside its values: the two ends
    or every point, low to high (``1 = vůbec, 10 = zcela``); empty for no labels."""
    return ", ".join(f"{value} = {label}" for value, label in labelled_points(scale, labels))


def _ends(battery: SpecBattery) -> tuple[str, str]:
    """A set's two ends as the report names them: as develop read them for a set labelled at
    its ends (the report a stored design always had), the first and last point's for one
    labelled point by point."""
    return battery.told_ends if len(battery.scale_labels) == 2 else battery.end_labels


def _question_line(q: SpecQuestion) -> ListItem:
    kind = _TYPE.get(q.typ, q.typ)
    if q.typ in ("vyber", "multi"):
        detail = f"{kind}: {', '.join(q.options)}"
    elif q.typ == "skala" and q.scale is not None:
        detail = f"{kind} {q.scale[0]}\u2013{q.scale[1]}"
        if q.scale_labels:
            detail += f" ({scale_wording(q.scale, q.scale_labels)})"
    else:
        detail = kind
    if q.has_filter:
        detail += "; jen pro část respondentů (filtr)"
    return ListItem((Text(q.text, "strong"), Text(f" — {detail}")))


_STRATEGY = {
    "population": "Cílovou skupinou je celá populace.",
    "filters": "Cílovou skupinu návrh zúžil podle faktorů populace",
    "discover": ("Návrh nejdřív měří širokou populaci a ideální skupinu hledá až ve výsledcích."),
}


def _filter_value(value: object) -> str:
    if isinstance(value, dict):
        low, high = value.get("min"), value.get("max")
        return f"{'' if low is None else low}\u2013{'' if high is None else high}"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value)


def _rated_items(n: int) -> str:
    """'1 položka hodnocená', '3 položky hodnocené', '5 položek hodnocených'."""
    return counted(n, "položka hodnocená", "položky hodnocené", "položek hodnocených")


def _audience_sentence(spec: ResearchSpecification) -> str:
    """The audience as the design stated it: its description and built-in subpanel when the
    design gave them, then the strategy and, when it narrowed, by what."""
    stated = ""
    if description := spec.audience.get("description"):
        stated += f"Cílová skupina podle návrhu: {description}. "
    population = spec.audience.get("source_mode") == "population"
    if population and (subpanel := spec.audience.get("builtin_subpanel")):
        stated += f"Vycházela z vestavěného podpanelu {subpanel}. "
    return stated + _audience_rule(spec)


def _audience_rule(spec: ResearchSpecification) -> str:
    """The strategy and, when it narrowed, by what."""
    strategy = str(spec.audience.get("strategy") or "population")
    if spec.audience.get("source_mode") != "population":
        return "Návrh počítal s vlastním souborem respondentů mimo populaci AIA."
    if strategy != "filters":
        return _STRATEGY.get(strategy, f"Strategie cílové skupiny: {strategy}.")
    filters = spec.selection.audience_filters if spec.selection is not None else {}
    if not filters:
        return _STRATEGY["filters"] + ", ale žádný faktor neuvedl."
    named = "; ".join(f"{k}: {_filter_value(v)}" for k, v in filters.items())
    return f"{_STRATEGY['filters']} ({named})."


#: Said, in code's words, where the person stated nothing: never a template's placeholder.
NOT_STATED = "V zadání neuvedeno."


def _paragraphs(written: str | None) -> list[Block]:
    """A person's text as they wrote it, a paragraph for each part a blank line separates (Word's
    line break a line); what XML cannot hold left out (``printable.xml_text``), so a field of
    nothing else is said not stated, never printed empty."""
    clean = xml_text((written or "").replace("\x0b", "\n"))
    parts = [part.strip() for part in re.split(r"\n\s*\n", clean) if part.strip()]
    return [Paragraph(text(part)) for part in parts] or [Paragraph(text(NOT_STATED))]


def compose_design_sections(
    spec: ResearchSpecification,
    research_questions: Sequence[str],
    *,
    brief: Brief | None = None,
) -> DesignSections:
    """The design as the run executed it: the brief's goal and what the decision is for (with
    ``brief``; each said not stated when empty), then questions, sets, sample and audience; then
    every question of the questionnaire in its order.

    A block that prints a number code wrote from the specification (a scale's ends, a count, the
    planned n, an audience bound) prints locked under ``design:<fingerprint>`` (RPT8a, part 3,
    P10); what the person wrote around it (a set's title, the wording) is locked with it. The
    questionnaire appendix is the questionnaire as it was asked, a record, so its question lists
    are locked whole; the chapter's own research questions and items, which print no number,
    stay as they are."""
    # The fingerprint's first 16 hex characters: Word keeps a content control's tag to 64; the
    # section's manifest pins the specification whole.
    control = source_tag("design", spec.fingerprint()[:16])
    blocks: list[Block] = [
        Paragraph(
            text(
                "Tato kapitola popisuje návrh, podle kterého běh proběhl: co měl výzkum "
                "zjistit, co porovnával a koho se ptal. Pochází z revize návrhu, ze které "
                "byl běh sestaven; pozdější úpravy návrhu se do ní nepromítají."
            )
        )
    ]
    # What the person asked for, before how it was measured (F19): both always, so an empty field
    # reads as not stated, never as a report that leaves it out.
    if brief is not None:
        blocks.append(Heading("Cíl studie", 2))
        blocks.extend(_paragraphs(brief.goal))
        blocks.append(Heading("Rozhodnutí, které má výzkum podpořit", 2))
        blocks.extend(_paragraphs(brief.decision_use))
    if research_questions:
        blocks.append(Heading("Výzkumné otázky", 2))
        blocks.append(BulletList(tuple(ListItem(text(q)) for q in research_questions)))
    if spec.batteries:
        blocks.append(Heading("Porovnávané sady", 2))
        for battery in spec.batteries:
            low, high = _ends(battery)
            blocks.append(
                Paragraph(
                    (
                        Text(battery.title, "strong"),
                        Text(
                            # Agreeing with the count: "3 položky hodnocené", "5 položek
                            # hodnocených" (cross-review: "3 položek").
                            f" — {_rated_items(len(battery.objects))} otázkou "
                            f"„{battery.question_template.replace('{object}', '…')}“ na škále "
                            f"{battery.scale[0]} ({low}) až {battery.scale[1]} ({high})"
                            + (
                                "; před hodnocením se ověřuje znalost položky"
                                if battery.familiarity_required
                                else ""
                            )
                            + "."
                        ),
                    ),
                    control=control,
                )
            )
            blocks.append(BulletList(tuple(ListItem(text(o.label)) for o in battery.objects)))
    blocks.append(Heading("Vzorek a cílová skupina", 2))
    blocks.append(
        Paragraph(
            text(
                (
                    f"Návrh počítal s {spec.n} respondenty. "
                    if spec.n is not None
                    else "Návrh neuvádí velikost vzorku. "
                )
                + _audience_sentence(spec)
                + " Jak byli respondenti v běhu skutečně vybráni, uvádí kapitola o metodice."
            ),
            control=control,
        )
    )
    chapter = Section("Návrh studie", tuple(blocks), id="ch-design")

    questionnaire: list[Block] = [
        Paragraph(
            text(
                "Dotazník tak, jak byl položen, v pořadí otázek. U hodnocených sad je "
                "uvedena společná otázka; každá položka sady byla jednou otázkou."
            )
        )
    ]
    sections: dict[str, list[SpecQuestion]] = {}
    for q in spec.questions:
        sections.setdefault(q.section_id, []).append(q)
    for index, questions in enumerate(sections.values(), start=1):
        questionnaire.append(Heading(f"Blok {index}", 2))
        questionnaire.append(
            BulletList(tuple(_question_line(q) for q in questions), control=control)
        )
    for battery in spec.batteries:
        low, high = _ends(battery)
        scale = (
            f"{battery.scale[0]} ({low}) až {battery.scale[1]} ({high})"
            if len(battery.scale_labels) == 2
            else (
                f"{battery.scale[0]}\u2013{battery.scale[1]} "
                f"({scale_wording(battery.scale, battery.scale_labels)})"
            )
        )
        questionnaire.append(Heading(f"Sada: {battery.title}", 2))
        questionnaire.append(
            Paragraph(
                text(
                    f"„{battery.question_template.replace('{object}', '…')}“ — škála "
                    f"{scale}, položky: {', '.join(o.label for o in battery.objects)}."
                ),
                control=control,
            )
        )
    appendix = Section("Dotazník", tuple(questionnaire), id="app-questionnaire", appendix=True)
    return DesignSections(chapter, appendix)
