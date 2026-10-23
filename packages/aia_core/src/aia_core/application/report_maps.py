"""Readable internal map chapters from a run's frozen object-map artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from aia_core.domain.report.control_tags import source_tag
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
from aia_core.domain.sociomap import SociomapArtifactV3, read_object_maps
from aia_core.domain.sociomap.models_v3 import MapCredibility, RespondentMap
from aia_core.domain.sociomap.pairs import PairRelations
from aia_core.domain.sociomap.relations import PairStatus
from aia_core.domain.sociomap.specification import RelationEstimator
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


def _height_sentence(maps: list[tuple[str, SociomapArtifactV3]]) -> str:
    """What height and colour show on the printed ``maps``: the 0-1 means under the earlier
    methods; under the signed-off one the means on the set's declared scale, relative to the
    set's other objects."""
    signed = [(m, a) for m, a in maps if _is_signed_off(a)]
    earlier = "Výška a barva ukazují průměrné hodnocení převedené na škálu od nuly do jedné. "
    if not signed:
        return earlier
    method, artifact = signed[0]
    ends = {(i.scale_min, i.scale_max) for i in artifact.items}
    scale = (
        "na škále {}\u2013{}".format(
            *(number(v, 0 if float(v).is_integer() else 1) for v in next(iter(ends)))
        )
        if len(ends) == 1
        else "na deklarované škále každého objektu"
    )
    floor = artifact.spec.terrain.relative_height_floor if artifact.spec.terrain else None
    relative = (
        f"Výška a barva ukazují průměrné hodnocení {scale} vůči ostatním objektům sady: "
        "nejvýše hodnocený objekt má plnou výšku"
        + (
            f", nejníže hodnocený {number(round(100 * floor), 0)} % výšky. "
            if floor is not None
            else ". "
        )
    )
    if len(signed) == len(maps):
        return relative
    return earlier + f"U metody {method}: " + relative[:1].lower() + relative[1:]


def _respondent_reading(artifact: SociomapArtifactV3, resp: RespondentMap) -> str:
    """How to read the respondent figure: the dots, the faint ones, the height and the colours."""
    rules = artifact.spec.segments
    seg = resp.segments
    out = (
        "Mapa respondentů ukazuje každého umístěného respondenta jako bod: leží směrem "
        "k objektům, které hodnotí nad svým průměrem, a čím jasnější je jeho směr, tím dál od "
        "středu. Světlé body jsou umístěné slabě (jejich směr nelze odlišit od náhody) a do "
        "výšky se nepočítají. Výška ukazuje hustotu jasně umístěných respondentů. "
    )
    if seg is not None and seg.decision == "SEGMENTS":
        membership = round(100 * (rules.colour_membership if rules else 0.8))
        out += (
            "Barva bodu ukazuje chuťový segment, je-li respondent jasně umístěný a do segmentu "
            f"patří s pravděpodobností alespoň {membership} %; šedé body nejsou jasně v jednom "
            "segmentu."
        )
    elif seg is not None and seg.decision == "BORDERLINE":
        out += "Body nejsou obarvené: rozdělení na chuťové segmenty není jisté."
    elif seg is not None and seg.reason == "TOO_FEW_OBJECTS":
        n = rules.min_ratings if rules else 5
        out += (
            f"Chuťové segmenty se nehledají: sada má méně než {n} objektů a chuť člověka se "
            f"určuje z alespoň {n} hodnocení."
        )
    elif seg is not None and seg.reason == "TOO_FEW_RESPONDENTS":
        out += "Chuťové segmenty se nehledají: na ně je v sadě příliš málo respondentů."
    elif seg is not None:
        out += "Data žádné skupiny chutí silnější než náhoda neukazují."
    placing = artifact.spec.respondent_map
    if placing is not None and len(artifact.object_ids) < placing.min_ratings:
        # As the figure says it: nobody has the ratings a position needs.
        out = (
            "Sada má méně objektů, než kolik hodnocení potřebuje poloha respondenta "
            f"({placing.min_ratings}): respondenty nelze umístit."
        )
    elif not resp.informative:
        out += f" Sada má méně než {resp.min_objects} objektů: mapa respondentů je jen orientační."
    return out


def map_control(battery: Mapping[str, Any], method: str) -> str:
    """The tag of the locked controls text written from one stored map prints in."""
    return source_tag("map", f"{battery['battery_id']}/{method}")


def _is_signed_off(artifact: SociomapArtifactV3) -> bool:
    return (
        artifact.spec.relation.estimator == RelationEstimator.BASELINE_CORRECTED_PEARSON
        and isinstance(artifact.terrain, EnvelopeTerrain)
    )


VIEW_TITLE: Final = {
    "top": "Pohled shora",
    "3d": "Prostorový pohled",
    "respondents": "Mapa respondentů",
}
RESPONDENT_ALT: Final = (
    "Mapa respondentů uložené mapy {title}. Výška ukazuje hustotu jasně umístěných "
    "respondentů, body jednotlivé respondenty (světlé: slabě umístění){segments}; objekty "
    "jsou šedé uzly s popisem."
)


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
        guide_maps = [
            (method, artifact)
            for method, artifact in read_object_maps(battery)
            if not client
            or getattr(approvals.get(method), "status", None) is MethodologyStatus.CLIENT_FACING
        ]
        # The guide's numbers (the scale, the height floor) are the first signed-off map's
        # (_height_sentence): its text prints locked under that map (RPT8a, P8); without one it
        # prints none.
        signed = [method for method, artifact in guide_maps if _is_signed_off(artifact)]
        guide_control = map_control(battery, signed[0]) if signed else None
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
                    "a její podpory v tabulce pod mapami. "
                    + _height_sentence(guide_maps)
                    + "Směr os nemá věcný význam; pro čtení jsou podstatné vzájemné vzdálenosti."
                ),
                control=guide_control,
            ),
        ]
        drawn = 0
        for ordinal, (method, artifact) in enumerate(read_object_maps(battery), start=1):
            approval = approvals.get(method)
            # Text code writes whole from this stored map prints locked under it (RPT8a, P7-P9).
            map_tag = map_control(battery, method)
            map_status = (
                approval.status if approval is not None else MethodologyStatus.INTERNAL_ONLY
            )
            if client and map_status is not MethodologyStatus.CLIENT_FACING:
                continue
            if artifact.layout is None:
                assert artifact.not_mappable is not None
                blocks.append(
                    Paragraph(
                        text(f"Metoda {method}: mapa nevznikla. {artifact.not_mappable.message}"),
                        control=map_tag,
                    )
                )
                continue
            layout = artifact.layout
            support = artifact.support
            blocks.append(
                Callout(CalloutKind.METHOD, text(approval.reader_note), control=map_tag)
                if approval is not None and map_status is MethodologyStatus.CLIENT_FACING
                else Callout(
                    CalloutKind.LIMITATION,
                    text(
                        f"Mapa metodou {method} je interním výstupem: metodika dosud čeká "
                        "na schválení a mapa nesmí do klientské zprávy."
                    ),
                    control=map_tag,
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
                        # As the figure says it: no split-half score means no reliable pair.
                        title="Žádná spolehlivá struktura"
                        if credibility.split_half is None
                        else "Slabě určená mapa",
                        control=map_tag,
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
                        ),
                        control=map_tag,
                    )
                )
            # The framed envelope draws relative heights and reaches every cell.
            relative = (
                isinstance(artifact.terrain, EnvelopeTerrain)
                and artifact.terrain.method == "framed_relative_envelope"
            )
            # A signed-off map is drawn as the AIA panel draws it, labelled on the map, with its
            # respondent map where it is stored.
            panel = _is_signed_off(artifact)
            views: tuple[str, ...] = (
                ("top", "3d") if isinstance(artifact.terrain, EnvelopeTerrain) else ("top",)
            )
            if panel and isinstance(artifact.respondents, RespondentMap):
                views += ("respondents",)
            for view in views:
                key = (battery["battery_id"], method, view)
                if key not in images:
                    raise ValueError(f"missing map snapshot: {key}")
                view_title = VIEW_TITLE[view]
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
                        control=map_tag,
                        alt=RESPONDENT_ALT.format(
                            title=battery["title"],
                            segments=", barva bodu chuťový segment"
                            if isinstance(artifact.respondents, RespondentMap)
                            and artifact.respondents.segments is not None
                            and artifact.respondents.segments.decision == "SEGMENTS"
                            else "",
                        )
                        if view == "respondents"
                        else f"{view_title} uložené mapy {battery['title']}. "
                        + (
                            "Objekty jsou popsané na mapě"
                            if panel
                            else "Číslované objekty odpovídají legendě"
                        )
                        + "; barva a výška ukazují "
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
            if "respondents" in views and isinstance(artifact.respondents, RespondentMap):
                blocks.append(
                    Paragraph(
                        text(_respondent_reading(artifact, artifact.respondents)), control=map_tag
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
                        TextCell(
                            "nedefinováno" if r is None else number(round(r, 3), 3),
                            control=map_tag,
                        ),
                        TextCell(str(pairs.n[i][j]), control=map_tag),
                    ]
                    if effective is not None:
                        n_eff = effective[i][j]
                        cells.append(
                            TextCell(
                                "neuvedeno" if n_eff is None else effective_n(n_eff),
                                control=map_tag,
                            )
                        )
                    cells.append(
                        TextCell(
                            "neuvedeno" if status is None else PAIR_STATUS[status],
                            control=map_tag,
                        )
                    )
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
                    notes_control=map_tag,
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
