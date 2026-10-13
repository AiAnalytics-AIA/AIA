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

from aia_core.domain.fieldwork import (
    MODELLED_DISCLOSURE,
    DataOrigin,
    OriginKind,
    PersonaSource,
    origin_kind,
    persona_source_of,
)
from aia_core.domain.methodology.pins import run_methods
from aia_core.domain.report.model import (
    Block,
    Callout,
    CalloutKind,
    Column,
    Paragraph,
    Section,
    Table,
    TableRow,
    TextCell,
    text,
)

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


def compose_method_section(meta: Mapping[str, Any], origin: DataOrigin | None) -> Section:
    """The chapter "Respondenti a výpočet", from the run's metadata and its dataset's origin."""
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
    if persona is PersonaSource.PANEL:
        blocks.append(
            Paragraph(
                text(
                    "Výběr respondentů respektoval filtry cílové skupiny z návrhu. Dimenze "
                    "zvolené v návrhu jsou s během uložené, na respondenty se zatím neuplatňují."
                )
            )
        )
    elif persona is PersonaSource.FICTIONAL_ROSTER:
        blocks.append(
            Paragraph(
                text(
                    "Filtry cílové skupiny a dimenze z návrhu jsou s během uložené, ale tento "
                    "běh je na respondenty neuplatnil: smyšlený soubor se z populace nevybírá."
                )
            )
        )
    else:
        blocks.append(
            Callout(
                CalloutKind.LIMITATION,
                text("Zdroj respondentů, který běh zaznamenal, AIA nezná; neuvádí se žádný."),
            )
        )

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
    return Section("Respondenti a výpočet", tuple(blocks), id="ch-method")
