"""The experimental Sociomapping's internal draft report (plan sociomapping-engine I2).

One INTERNAL, unapproved document per run: what the method is and is not, each tracked set's
map with its fit, the objects with their positions, heights and per-point fit, the declared
relationship matrix as measured, every limitation, and the provenance -- fingerprints,
versions, parameters and evidence-register rule ids.

The numbers printed here are **properties of the computation** (positions, rank fit, the
correlations the layout was fitted to, the average answers that set the heights), printed as
the stored artifact holds them. None of them is an admitted survey claim: the ledger is empty,
and the report says so. That is why it is INTERNAL and why nothing here can produce a client
report: :func:`compose_sociomapping_report` refuses any kind but INTERNAL.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from aia_core.domain.evidence import ClaimSurface
from aia_core.domain.report.evidence import EvidenceLedger
from aia_core.domain.report.model import (
    AuditBlock,
    BulletList,
    Callout,
    CalloutKind,
    Classification,
    Column,
    ListItem,
    Paragraph,
    ReportDocument,
    ReportKind,
    ReportMeta,
    Section,
    SociomapFigure,
    Table,
    TableRow,
    TextCell,
    text,
)
from aia_core.domain.report.numbers import number
from aia_core.domain.report.validation import require_valid

__all__ = [
    "SOCIOMAPPING_REPORT_ARTIFACT_TYPE",
    "SOCIOMAPPING_REPORT_CONTRACT",
    "SociomappingReportRefused",
    "compose_sociomapping_report",
    "limitation_text",
]

SOCIOMAPPING_REPORT_ARTIFACT_TYPE: Final = "research_sociomapping_docx"
SOCIOMAPPING_REPORT_CONTRACT: Final = "aia-sociomapping-report-1"

#: The limitation codes the artifact carries -> what the report prints. A code without
#: wording prints its stored English detail, never nothing.
_LIMITATIONS: Final[dict[str, str]] = {
    "EXPERIMENTAL_METHOD": (
        "Rozmístění počítá experimentální H-Model AIA (aia_hmodel_candidate_v1). Cílová "
        "funkce SOMECS není zdokumentovaná; nejde o ověřenou rekonstrukci SOMECS."
    ),
    "NO_RESPONDENT_PLACEMENT": (
        "Respondenti na mapě nejsou: umístění respondentů (STORM) v SOMECS není zdokumentované."
    ),
    "NO_HEIGHT_SURFACE": (
        "Výška je zobrazena jen u objektů; plocha mezi nimi se nedopočítává (interpolace "
        "WIND v SOMECS není zdokumentovaná)."
    ),
    "UNWEIGHTED": "Vztahy i výšky jsou nevážené: žádný zdroj Sociomapu neváží.",
    "ADEQUACY_NOT_ASSESSED": (
        "Zda podpora stačí, aby korelace nebo mapa něco znamenaly, posouzeno není; "
        "spočitatelné není totéž co dostatečné."
    ),
    "NO_SIGNIFICANCE": "Shoda mapy není testována proti náhodným maticím stejné velikosti.",
    "COMPLETE_RESPONDENTS_ONLY": (
        "Ve vztazích a výškách jsou jen respondenti, kteří odpověděli na všechny objekty sady."
    ),
    "NEGATIVE_CORRELATIONS_KEPT": (
        "Některé dvojice objektů korelují záporně. Korelace zůstávají se znaménkem a mapa je "
        "rozmisťuje podle pořadí; matice vztahů 0-1 ani soudržnosti pro tuto sadu nevznikly, "
        "dokud není rozhodnuto, jak RTS zápornou korelaci převádí."
    ),
    "UNPLACED_OBJECTS": "Některé objekty na mapě nejsou, protože nemají žádný definovaný vztah.",
    "FEW_OBJECTS": (
        "Na mapě je málo objektů: s několika dvojicemi je přesnost blízká 1 snadno dosažitelná "
        "a o struktuře vypovídá málo."
    ),
}


def objects_word(n: int) -> str:
    """'1 objekt', '3 objekty', '5 objektů': Czech agreement with the count."""
    if n == 1:
        return f"{n} objekt"
    return f"{n} objekty" if 2 <= n <= 4 else f"{n} objektů"


class SociomappingReportRefused(ValueError):
    """The stored result cannot be reported as asked."""


def limitation_text(item: Mapping[str, Any]) -> str:
    """One limitation in the report's words, with the open question it waits on."""
    words = _LIMITATIONS.get(str(item.get("code")), str(item.get("detail", "")))
    if item.get("code") in {"COMPLETE_RESPONDENTS_ONLY", "UNPLACED_OBJECTS", "FEW_OBJECTS"}:
        words = f"{words} ({item.get('detail')})"
    question = item.get("question")
    return f"{words} Otevřená otázka {question}." if question else words


def _n(value: float | None, decimals: int = 3) -> str:
    return "nedefinováno" if value is None else number(round(value, decimals), decimals)


def _fit_caption(layout: Mapping[str, Any]) -> str:
    accuracy = layout["accuracy"]
    return (
        f"přesnost (Spearman, {accuracy['evaluator']}) = {_n(accuracy['overall'])}; "
        f"průměr shody bodů = {_n(accuracy['mean_per_point'])}"
    )


def _battery_sections(
    index: int,
    battery: Mapping[str, Any],
    image_png: bytes | None,
    source: str,
) -> Section:
    labels = {o["id"]: o["label"] for o in battery["objects"]}
    support = battery["support"]
    blocks: list[Any] = [
        Paragraph(
            text(
                f"Sada „{battery['title']}“: {objects_word(len(battery['objects']))} na škále "
                f"{battery['rating_scale'][0]}-{battery['rating_scale'][1]}; ve výpočtu "
                f"{support['respondents_complete']} z {support['respondents_total']} "
                "respondentů (ti, kdo odpověděli na všechny objekty sady), nevážené."
            )
        )
    ]
    layout = battery.get("layout")
    if battery["status"] != "MAPPED" or layout is None:
        blocks.append(
            Callout(
                CalloutKind.LIMITATION,
                text(f"Mapa nevznikla: {battery['reason']}"),
                title="Mapa nevznikla",
            )
        )
    else:
        ids = layout["element_ids"]
        heights = dict(
            zip([o["id"] for o in battery["objects"]], battery["heights"]["on_scale"], strict=True)
        )
        if image_png is not None:
            blocks.append(
                SociomapFigure(
                    id=f"fig-sociomapping-{index}",
                    title=f"Experimentální mapa: {battery['title']}",
                    image_png=image_png,
                    methodology_status="EXPERIMENTAL_AIA",
                    stress_1=None,
                    fit_caption=_fit_caption(layout),
                    source=source,
                    alt=(
                        f"Mapa {len(ids)} objektů sady {battery['title']}: body podle "
                        "rozmístění experimentálního H-Modelu, barva podle průměrné odpovědi."
                    ),
                )
            )
        per_point = layout["accuracy"]["per_point"]
        blocks.append(
            Table(
                id=f"tab-sociomapping-objects-{index}",
                title=f"Objekty na mapě: {battery['title']}",
                columns=(
                    Column("Objekt"),
                    Column("x"),
                    Column("y"),
                    Column("Výška (průměrná odpověď)"),
                    Column("Shoda bodu (Spearman)"),
                ),
                rows=tuple(
                    TableRow(
                        (
                            TextCell(labels.get(oid, oid)),
                            TextCell(_n(x)),
                            TextCell(_n(y)),
                            TextCell(_n(heights[oid], 2)),
                            TextCell(_n(fit)),
                        )
                    )
                    for oid, (x, y), fit in zip(ids, layout["positions"], per_point, strict=True)
                ),
                source=source,
                notes=tuple(
                    f"Mimo mapu: {labels.get(u['element_id'], u['element_id'])} ({u['reason']})."
                    for u in layout["unplaced"]
                ),
            )
        )
    order = [o["id"] for o in battery["objects"]]
    relations = battery.get("relations")
    if relations is not None:
        blocks.append(
            Table(
                id=f"tab-sociomapping-relations-{index}",
                title=(
                    "Deklarovaná matice vztahů (Pearsonova korelace se znaménkem): "
                    f"{battery['title']}"
                ),
                columns=(Column(""), *(Column(labels[o]) for o in order)),
                rows=tuple(
                    TableRow(
                        (
                            TextCell(labels[order[r]]),
                            *(
                                TextCell("—" if r == s else _n(relations["matrix"][r][s], 2))
                                for s in range(len(order))
                            ),
                        )
                    )
                    for r in range(len(order))
                ),
                source=source,
                notes=(
                    f"Podpora: {relations['support']} respondentů. Záporné hodnoty jsou zachovány; "
                    "„nedefinováno“ znamená, že objekt dostal od všech stejnou odpověď.",
                ),
            )
        )
    if layout is not None:
        starts = layout["starts"]
        blocks.append(
            Table(
                id=f"tab-sociomapping-fit-{index}",
                title=f"Diagnostika shody: {battery['title']}",
                columns=(Column("Ukazatel"), Column("Hodnota")),
                rows=(
                    TableRow(
                        (
                            TextCell("Celková přesnost (Spearman)"),
                            TextCell(_n(layout["accuracy"]["overall"])),
                        )
                    ),
                    TableRow(
                        (
                            TextCell("Průměr shody bodů"),
                            TextCell(_n(layout["accuracy"]["mean_per_point"])),
                        )
                    ),
                    TableRow(
                        (
                            TextCell("Uspořádaných párů ve výpočtu"),
                            TextCell(str(layout["accuracy"]["ordered_pairs"])),
                        )
                    ),
                    TableRow(
                        (
                            TextCell("Nedefinovaných párů (mimo výpočet)"),
                            TextCell(str(layout["accuracy"]["undefined_pairs"])),
                        )
                    ),
                    TableRow(
                        (
                            TextCell("Výchozí klasické MDS (srovnávací základ)"),
                            TextCell(_n(layout["baseline_classical_mds"])),
                        )
                    ),
                    *(
                        TableRow(
                            (
                                TextCell(f"Start {k + 1} ({s['label']}), větev {s['branch']}"),
                                TextCell(_n(s["final_accuracy"])),
                            ),
                            emphasis=k == layout["chosen_start"],
                        )
                        for k, s in enumerate(starts)
                    ),
                ),
                source=source,
                notes=("Zvýrazněný start byl zvolen. Rozptyl mezi starty ukazuje lokální optima.",),
            )
        )
    coherence = battery.get("coherences") or {}
    if coherence.get("available"):
        blocks.append(
            Paragraph(
                text(
                    f"Soudržnosti (alfa-řezy): {coherence['written']}. Pravidla: "
                    f"{', '.join(coherence['rules'])}."
                )
            )
        )
    elif coherence:
        blocks.append(
            Paragraph(
                text(
                    "Soudržnosti nevznikly: pro tuto sadu neexistuje matice vztahů 0-1 (záporné "
                    "nebo nedefinované korelace; otevřená otázka M12). Záznam výpočtu: "
                    f"{coherence['reason']}"
                )
            )
        )
    return Section(f"Mapa: {battery['title']}", tuple(blocks), id=f"ch-sociomapping-{index}")


def compose_sociomapping_report(
    result: Mapping[str, Any],
    meta: ReportMeta,
    images: Mapping[str, bytes],
    audit: tuple[tuple[str, str], ...],
) -> ReportDocument:
    """The internal draft. ``images`` maps a battery id to its drawn map (PNG)."""
    if meta.kind is not ReportKind.INTERNAL or meta.classification is not Classification.INTERNAL:
        raise SociomappingReportRefused("an experimental Sociomapping is reported internally only")
    if meta.approvals:
        raise SociomappingReportRefused("an experimental Sociomapping report is never approved")
    if (
        result.get("client_facing") is not False
        or result.get("method_status") != "EXPERIMENTAL_AIA"
    ):
        raise SociomappingReportRefused("the stored result does not say it is experimental")
    method = result["method"]
    origin = result.get("data_origin") or "neuvedeno"
    source = f"AIA, {method['name']} ({method['status']}); data: {origin}"
    about: list[Any] = [
        Callout(
            CalloutKind.PROVISIONAL,
            text(
                "Experimentální metoda AIA. Mapa, její shoda i čísla v této zprávě jsou "
                "výstupem experimentálního H-Modelu AIA, nikoli ověřené rekonstrukce SOMECS "
                "ani schválené metodiky. Zpráva je interní koncept a nepředává se klientovi."
            ),
        ),
        Callout(CalloutKind.METHOD, ()),
        Paragraph(
            text(
                f"Metoda {method['name']} hledá rozmístění objektů v rovině tak, aby pořadí "
                "vzdáleností co nejlépe odpovídalo pořadí vztahů mezi objekty. Shodu měří "
                f"evaluátor {method['evaluator']}: Spearmanova korelace mezi vztahy a zápornými "
                "vzdálenostmi přes všechny definované uspořádané dvojice. Vztahy jsou "
                "Pearsonovy korelace odpovědí respondentů mezi objekty, se znaménkem, bez úprav."
            )
        ),
    ]
    if result.get("synthetic_data"):
        about.append(
            Callout(
                CalloutKind.NOTE,
                text(
                    f"Data jsou fiktivní ({origin}): nejde o pozorované odpovědi skutečných lidí "
                    "a z výsledků nelze vyvozovat zjištění."
                ),
                title="Fiktivní data",
            )
        )
    about.append(
        Paragraph(
            text(
                "Čísla v této zprávě jsou vlastnosti výpočtu, vytištěná tak, jak je uložil "
                "artefakt běhu. Neprošla důkazní bránou AIA a nejsou tvrzeními o populaci."
            )
        )
    )
    sections = [Section("Co tato zpráva je", tuple(about), id="ch-about")]
    batteries = result.get("batteries", [])
    for i, battery in enumerate(batteries, start=1):
        sections.append(_battery_sections(i, battery, images.get(battery["battery_id"]), source))
    if not batteries:
        sections.append(
            Section("Mapy", (Paragraph(text(result.get("note") or "Žádná sada.")),), id="ch-none")
        )
    seen: list[str] = []
    for battery in batteries:
        for item in battery.get("limitations", []):
            line = limitation_text(item)
            if line not in seen:
                seen.append(line)
    sections.append(
        Section(
            "Omezení",
            (BulletList(tuple(ListItem(text(line)) for line in seen)),)
            if seen
            else (Paragraph(text("Žádná sada nevznikla.")),),
            id="ch-limitations",
        )
    )
    provenance_rows = [
        ("Verze výsledku", str(result["sociomapping_version"])),
        ("Metoda", f"{method['name']} ({method['status']})"),
        ("Evaluátor shody", str(method["evaluator"])),
        (
            "Parametry",
            ", ".join(f"{k}={v}" for k, v in sorted(method["parameters"].items())),
        ),
        ("Původ dat", origin),
    ]
    inputs = result.get("inputs") or {}
    for key, label in (
        ("specification_fingerprint", "Otisk specifikace"),
        ("dataset_sha256", "SHA-256 datasetu"),
    ):
        if key in inputs:
            provenance_rows.append((label, str(inputs[key])))
    for battery in batteries:
        if battery.get("relations"):
            provenance_rows.append(
                (f"Otisk matice vztahů: {battery['title']}", battery["relations"]["fingerprint"])
            )
        if battery.get("rules"):
            provenance_rows.append(
                (f"Pravidla registru: {battery['title']}", ", ".join(battery["rules"]))
            )
    sections.append(
        Section(
            "Původ a reprodukovatelnost",
            (
                Table(
                    id="tab-sociomapping-provenance",
                    title="Původ výpočtu",
                    columns=(Column("Položka"), Column("Hodnota")),
                    rows=tuple(TableRow((TextCell(k), TextCell(v))) for k, v in provenance_rows),
                    source=source,
                    notes=(
                        "Pravidla odkazují na docs/migration/sociomapping-evidence-register.json.",
                    ),
                ),
            ),
            id="ch-provenance",
        )
    )
    sections.append(Section("Audit", (AuditBlock(audit),), id="app-audit", appendix=True))
    document = ReportDocument(
        meta,
        tuple(sections),
        EvidenceLedger.from_claims([], surface=ClaimSurface.INTERNAL),
        list_of_tables=False,
    )
    require_valid(document)
    return document
