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
from aia_core.domain.report.numbers import counted, effective_n, number
from aia_core.domain.sociomap import read_object_maps
from aia_core.domain.sociomap.models_v3 import MapCredibility
from aia_core.domain.sociomap.pairs import PairRelations
from aia_core.domain.sociomap.relations import PairStatus
from aia_core.domain.sociomap.terrain import EnvelopeTerrain
from aia_core.domain.sociomap_register import MethodologyStatus, recorded_statuses

#: A pair's status in words (audit F3; the web's ``objectMap.state``): the table printed the
#: code ("reliable") in English (cross-review).
PAIR_STATUS: dict[PairStatus, str] = {
    PairStatus.RELIABLE: "spolehlivý",
    PairStatus.WEAK: "slabý",
    PairStatus.UNKNOWN: "neznámý",
}
#: The basis under which a pair's state reads the effective n of its common raters' weights,
#: not their count (``PairRelations.basis``; ``aia-sociomap-3``'s, AIA Q6 (c)).
_EFFECTIVE_N_BASIS = "kish_effective_n"
_ANSWERS = ("společná odpověď", "společné odpovědi", "společných odpovědí")


def pair_status_means(relations: PairRelations) -> dict[PairStatus, str]:
    """What each state says, as ``relations.pair_status`` decided it for this map: on the n
    its recorded basis names, at its ``n_min``; nothing more.

    The count of common raters decides it under ``respondent_count`` and for a relation
    stored before the evidence policy (no basis). Under the effective-n basis it is the
    effective n of those raters' weights, which the count can far exceed, so the words name
    that n and never the count (cross-review: "málo společných odpovědí" beside 60 of them
    at n_min 30, the effective n 6.2).
    """
    if relations.basis == _EFFECTIVE_N_BASIS:
        enough = f"efektivní n aspoň {relations.n_min}"
        short = f"efektivní n pod {relations.n_min}"
    else:
        enough = f"aspoň {counted(relations.n_min, *_ANSWERS)}"
        short = f"méně než {counted(relations.n_min, *_ANSWERS)}"
    return {
        PairStatus.RELIABLE: f"{enough} a interval korelace nezahrnuje nulu",
        # The interval includes zero, so the correlation is not told apart from zero: never "od
        # žádného", which Czech reads as "from any relation" (cross-review).
        PairStatus.WEAK: (
            f"{enough}, ale interval korelace zahrnuje nulu, takže korelaci nelze odlišit od nuly"
        ),
        PairStatus.UNKNOWN: f"{short}, nebo korelaci nelze spočítat",
    }


#: The signed-off layout's methods (``layout.method``), which compute no Stress-1.
POSITION_METHOD = {
    "soft_rank_spearman_coulomb": "Spearman měkkých pořadí s Coulombovým odpuzováním",
    "interval_mds": "Interval MDS",
}


def _credibility_note(credibility: MapCredibility) -> str:
    """The signed-off methodology's split-half check and uncertainty radius, for internal
    readers."""
    agreement = (
        " Shodu polovin vzorku nelze spočítat; mapa je slabě určená, právě když žádný vztah "
        f"není spolehlivý (spolehlivých vztahů: {credibility.reliable_pairs})."
        if credibility.split_half is None
        else " Dvě poloviny vzorku se shodnou v "
        f"{number(round(100 * credibility.split_half), 0)} % srovnání „co je blíž“ (50 % = "
        f"náhoda; pod {number(round(100 * credibility.threshold), 0)} % je mapa slabě určená)."
    )
    verdict = (
        " Mapa je slabě určená." if credibility.weakly_determined else (" Mapa slabě určená není.")
    )
    radius = credibility.uncertainty_radius
    return (
        agreement
        + verdict
        + (
            " Poloměr nejistoty polohy nelze spočítat."
            if radius is None
            else f" Poloměr nejistoty polohy je {number(round(radius, 2), 2)}násobek střední "
            "kvadratické vzdálenosti objektů."
        )
    )


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
            credibility = artifact.credibility
            if credibility is not None and credibility.weakly_determined:
                # The signed-off methodology shows this instead of reading positions as structure.
                blocks.append(
                    Callout(
                        CalloutKind.LIMITATION,
                        text(
                            (
                                "Žádný vztah mezi objekty se neliší od náhody. "
                                if credibility.split_half is None
                                else "Dvě poloviny vzorku se shodnou jen v "
                                f"{number(round(100 * credibility.split_half), 0)} % srovnání "
                                "„co je blíž“ (50 % = náhoda). "
                            )
                            + "Pozice na mapě nečtěte jako skupiny ani vzdálenosti."
                        ),
                        title="Slabě určená mapa",
                    )
                )
            if not client:
                # Support counts and the fit, as numbers outside the ledger: internal only.
                blocks.append(
                    Paragraph(
                        text(
                            f"Metoda {method} zahrnuje "
                            f"{counted(len(artifact.object_ids), 'objekt', 'objekty', 'objektů')}. "
                            "Vztahy vycházejí "
                            f"z {support.placed} použitelných profilů hodnocení z celkem "
                            f"{support.respondents} odpovědních profilů; počet nezávislých "
                            f"donorů je {support.donors}."
                            + (
                                f" Stress-1 je {number(round(layout.stress_1, 3), 3)} (uložená "
                                f"kvalita: {QUALITY.get(layout.quality, layout.quality)}). Nižší "
                                "Stress-1 znamená menší nesoulad mezi cílovými vztahy "
                                "a vzdálenostmi na mapě. Shoda uspořádání není testem "
                                "statistické významnosti vztahů."
                                if layout.stress_1 is not None and layout.quality is not None
                                else ""
                            )
                            + ("" if credibility is None else _credibility_note(credibility))
                        )
                    )
                )
            # The framed envelope draws relative heights and reaches every cell.
            relative = (
                isinstance(artifact.terrain, EnvelopeTerrain)
                and artifact.terrain.method == "framed_relative_envelope"
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
                        fit_caption=None
                        if layout.stress_1 is not None or layout.method is None
                        else f"rozložení {POSITION_METHOD.get(layout.method, layout.method)}; "
                        "Stress-1 se nepočítá",
                        source=source,
                        alt=f"{view_title} uložené mapy {battery['title']}. Číslované objekty "
                        "odpovídají legendě; barva a výška ukazují "
                        + (
                            "průměr hodnocení vůči ostatním objektům sady."
                            if relative
                            else "průměr hodnocení na škále 0\u20131."
                        ),
                    )
                )
            if isinstance(artifact.terrain, EnvelopeTerrain):
                blocks.append(
                    Paragraph(
                        text(
                            "Prostorový pohled zobrazuje uloženou obálku objektových výšek. "
                            "Povrch mezi body je vizualizační konstrukce, nikoli další naměřená "
                            "odpověď. "
                            + (
                                "Daleko od objektů klesá povrch k nule, což neznamená "
                                "nulové hodnocení. "
                                if relative
                                else "Prázdné oblasti nemají povrch a neznamenají "
                                "nulové hodnocení. "
                            )
                            + "Perspektiva mění zdánlivou vzdálenost; polohy proto porovnávejte "
                            "v pohledu shora."
                        )
                    )
                )
            drawn += 1
            if client:
                continue  # the pair table prints r and n outside the ledger: internal only
            labels = {o["id"]: o["label"] for o in battery["objects"]}
            pairs = artifact.relations
            means = pair_status_means(pairs)
            # Under the effective-n basis the state reads that n, so the table prints it
            # beside the count, rounded down: never more support than there is.
            effective = pairs.n_effective
            rows: list[TableRow] = []
            for i, first in enumerate(artifact.object_ids):
                for j in range(i + 1, len(artifact.object_ids)):
                    second = artifact.object_ids[j]
                    r = pairs.r[i][j]
                    status = pairs.status[i][j]
                    cells = [
                        TextCell(f"{labels[first]} \u00d7 {labels[second]}"),
                        TextCell("nedefinováno" if r is None else number(round(r, 3), 3)),
                        TextCell(str(pairs.n[i][j])),
                    ]
                    if effective is not None:
                        n_eff = effective[i][j]
                        cells.append(TextCell("neuvedeno" if n_eff is None else effective_n(n_eff)))
                    cells.append(TextCell("neuvedeno" if status is None else PAIR_STATUS[status]))
                    rows.append(TableRow(tuple(cells)))
            columns = [
                Column("Dvojice objektů", width_weight=3),
                Column("Korelace r", align=Align.RIGHT),
                Column("Společné odpovědi", align=Align.RIGHT, width_weight=1.5),
            ]
            basis_note = ""
            if effective is not None:
                columns.append(Column("Efektivní n", align=Align.RIGHT, width_weight=1.5))
                basis_note = (
                    "Efektivní n vychází z vah respondentů, kteří hodnotili oba objekty; stav "
                    "vztahu se řídí jím, nikoli počtem společných odpovědí. "
                )
            columns.append(Column("Stav vztahu"))
            blocks.append(
                Table(
                    id=f"tab-native-map-pairs-{index}-{ordinal}",
                    title="Směr a podpora vztahů",
                    columns=tuple(columns),
                    rows=tuple(rows),
                    source=source,
                    notes=(
                        "Kladné r značí souhlasný vztah, záporné opačný. "
                        + basis_note
                        + "Stav vztahu: "
                        + "; ".join(f"{PAIR_STATUS[s]}: {means[s]}" for s in PairStatus)
                        + ". Hodnoty jsou vlastnosti výpočtu, nikoli schválená populační "
                        "tvrzení.",
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
