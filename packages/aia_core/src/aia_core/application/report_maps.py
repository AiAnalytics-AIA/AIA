"""Readable internal map chapters from a run's frozen object-map artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aia_core.domain.report.model import (
    Align,
    Block,
    Callout,
    CalloutKind,
    Column,
    Paragraph,
    Section,
    SociomapFigure,
    Table,
    TableRow,
    TextCell,
    text,
)
from aia_core.domain.report.numbers import number
from aia_core.domain.sociomap import read_object_maps
from aia_core.domain.sociomap.terrain import EnvelopeTerrain
from aia_core.domain.sociomap_register import MethodologyStatus, recorded_statuses

QUALITY = {
    "good": "dobrá",
    "fair": "přijatelná",
    "weak": "slabá",
    "unreliable": "nespolehlivé zobrazení v rovině",
}


def compose_map_sections(
    result: Mapping[str, Any],
    images: Mapping[tuple[str, str, str], bytes],
    *,
    source: str,
    client: bool = False,
) -> tuple[Section, ...]:
    """Explain each stored corrected map, with labelled snapshots and no new claims.

    Each map's status is the Sociomap register's for the method, at the exact specification,
    the run recorded beside its maps (complete-study-report B4): an approved map prints the
    approval's note, any other is internal and says its methodology awaits approval.

    ``client`` (B5c) keeps only approved maps, and only their figures and reading guide: the
    support counts and the pair table print numbers outside the evidence ledger, which a
    client page never does. Each figure still prints its fit.
    """
    approvals = recorded_statuses(result)
    sections: list[Section] = []
    for index, battery in enumerate(result.get("batteries", []), start=1):
        blocks: list[Block] = [
            Callout(
                CalloutKind.LIMITATION,
                text(
                    "Polohy a povrch map popisují uložený výpočet; neprokazují příčinu "
                    "vztahů ani chování skutečné populace. U každé mapy je uvedeno, zda "
                    "metodiku, kterou byla spočtena, AIA schválila k použití ve zprávách."
                ),
                title="Rámec interpretace map",
            ),
            Paragraph(
                text(
                    "Body představují sledované objekty. Cílové vzdálenosti vycházejí "
                    "z korelace se znaménkem, po přepočtu hodnocení na osobní škálu respondentů. "
                    "Vyšší korelace znamená menší cílovou vzdálenost; silný záporný vztah "
                    "znamená větší cílovou vzdálenost. Rozmístění v rovině tyto vzdálenosti "
                    "přibližuje; konkrétní dvojice proto ověřujte podle korelace "
                    "a její podpory v tabulce pod mapami. Výška a barva "
                    "ukazují průměrné hodnocení převedené na škálu od nuly do jedné. "
                    "Směr os nemá věcný význam; pro čtení jsou podstatné vzájemné vzdálenosti."
                )
            ),
        ]
        drawn = 0
        for ordinal, (method, artifact) in enumerate(read_object_maps(battery), start=1):
            approval = approvals.get(method)
            map_status = (
                approval.status if approval is not None else MethodologyStatus.INTERNAL_ONLY
            )
            if client and map_status is not MethodologyStatus.CLIENT_FACING:
                continue
            if artifact.layout is None:
                assert artifact.not_mappable is not None
                blocks.append(
                    Paragraph(
                        text(f"Metoda {method}: mapa nevznikla. {artifact.not_mappable.message}")
                    )
                )
                continue
            layout = artifact.layout
            support = artifact.support
            blocks.append(
                Callout(CalloutKind.METHOD, text(approval.reader_note))
                if approval is not None and map_status is MethodologyStatus.CLIENT_FACING
                else Callout(
                    CalloutKind.LIMITATION,
                    text(
                        f"Mapa metodou {method} je interním výstupem: metodika dosud čeká "
                        "na schválení a mapa nesmí do klientské zprávy."
                    ),
                )
            )
            if not client:
                # Support counts and the fit, as numbers outside the ledger: internal only.
                blocks.append(
                    Paragraph(
                        text(
                            f"Metoda {method} zahrnuje {len(artifact.object_ids)} objektů. "
                            "Vztahy vycházejí "
                            f"z {support.placed} použitelných profilů hodnocení z celkem "
                            f"{support.respondents} odpovědních profilů; počet nezávislých "
                            f"donorů je {support.donors}. Stress-1 je "
                            f"{number(round(layout.stress_1, 3), 3)} (uložená kvalita: "
                            f"{QUALITY.get(layout.quality, layout.quality)}). Nižší Stress-1 "
                            "znamená menší nesoulad mezi cílovými vztahy a vzdálenostmi na mapě. "
                            "Shoda uspořádání není testem statistické významnosti vztahů."
                        )
                    )
                )
            for view in (
                ("top", "3d") if isinstance(artifact.terrain, EnvelopeTerrain) else ("top",)
            ):
                key = (battery["battery_id"], method, view)
                if key not in images:
                    raise ValueError(f"missing map snapshot: {key}")
                view_title = "Pohled shora" if view == "top" else "Prostorový pohled"
                blocks.append(
                    SociomapFigure(
                        id=f"fig-native-map-{index}-{ordinal}-{view}",
                        title=f"{battery['title']} · {view_title} · {method}",
                        image_png=images[key],
                        methodology_status=map_status.value,
                        stress_1=layout.stress_1,
                        source=source,
                        alt=f"{view_title} uložené mapy {battery['title']}. Číslované objekty "
                        "odpovídají legendě; barva a výška ukazují průměr hodnocení "
                        "na škále 0\u20131.",
                    )
                )
            if isinstance(artifact.terrain, EnvelopeTerrain):
                blocks.append(
                    Paragraph(
                        text(
                            "Prostorový pohled zobrazuje uloženou obálku objektových výšek. "
                            "Povrch mezi body je vizualizační konstrukce, nikoli další naměřená "
                            "odpověď. Prázdné oblasti nemají povrch a neznamenají "
                            "nulové hodnocení. "
                            "Perspektiva mění zdánlivou vzdálenost; polohy proto porovnávejte "
                            "v pohledu shora."
                        )
                    )
                )
            drawn += 1
            if client:
                continue  # the pair table prints r and n outside the ledger: internal only
            labels = {o["id"]: o["label"] for o in battery["objects"]}
            pairs = artifact.relations
            rows: list[TableRow] = []
            for i, first in enumerate(artifact.object_ids):
                for j in range(i + 1, len(artifact.object_ids)):
                    second = artifact.object_ids[j]
                    r = pairs.r[i][j]
                    status = pairs.status[i][j]
                    rows.append(
                        TableRow(
                            (
                                TextCell(f"{labels[first]} \u00d7 {labels[second]}"),
                                TextCell("nedefinováno" if r is None else number(round(r, 3), 3)),
                                TextCell(str(pairs.n[i][j])),
                                TextCell(str(status)),
                            )
                        )
                    )
            blocks.append(
                Table(
                    id=f"tab-native-map-pairs-{index}-{ordinal}",
                    title="Směr a podpora vztahů",
                    columns=(
                        Column("Dvojice objektů", width_weight=3),
                        Column("Korelace r", align=Align.RIGHT),
                        Column("Společné odpovědi", align=Align.RIGHT, width_weight=1.5),
                        Column("Status"),
                    ),
                    rows=tuple(rows),
                    source=source,
                    notes=(
                        "Kladné r značí souhlasný vztah, záporné opačný. RELIABLE: "
                        "vztah splňuje uložené pravidlo podpory a intervalu; WEAK: "
                        "slabší opora; UNKNOWN: nedostatek informací. "
                        "Hodnoty jsou vlastnosti výpočtu, nikoli schválená populační tvrzení.",
                    ),
                )
            )
        if client and not drawn:
            continue  # no approved map of this set: the client report leaves it out
        if not battery.get("maps"):
            blocks.append(
                Paragraph(
                    text(
                        "Tento běh neobsahuje objektovou mapu podle nové metodiky. "
                        "Prostorový snímek nelze vytvořit bez uložených poloh a povrchu."
                    )
                )
            )
        sections.append(
            Section(f"Sociomapy · {battery['title']}", tuple(blocks), id=f"ch-native-map-{index}")
        )
    if client:
        return tuple(sections)  # no approved map at all: the client report has no map chapter
    if not sections:
        sections.append(
            Section(
                "Sociomapy",
                (
                    Paragraph(
                        text(result.get("note") or "Studie nemá sadu objektů vhodnou pro mapování.")
                    ),
                ),
                id="ch-native-map-none",
            )
        )
    return tuple(sections)
