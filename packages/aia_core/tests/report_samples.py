"""Sample reports, one per template, for the template tests and the preview tool.

Built on the ``report_ledger`` fixture (evidence admitted through the real gate),
with prose a consultant might write. ``stress`` lengthens every piece of prose by
that factor with Czech filler, so a layout can be checked for text that runs
+35 % longer than the draft (``tools/report_preview.py --stress``).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from aia_core.domain.evidence.claims import ClaimSurface
from aia_core.domain.evidence.validation import METHOD_STATUS_PENDING
from aia_core.domain.report.model import (
    Align,
    Approval,
    Chart,
    ChartKind,
    Classification,
    Column,
    CrossRef,
    Figure,
    Footnote,
    KeyFinding,
    Kpi,
    KpiRow,
    NumberCell,
    Paragraph,
    Quote,
    Recommendation,
    ReportDocument,
    ReportKind,
    ReportMeta,
    RevisionEntry,
    Section,
    Series,
    Table,
    TableRow,
    Text,
    TextCell,
    Value,
)
from aia_core.domain.report.templates import (
    DocumentationContent,
    FinalContent,
    QuestionAnswer,
    ReportContent,
    client_report,
    final_report,
    internal_report,
    study_documentation,
)

_FILLER = (
    "a to v souvislostech, které podrobněji rozebíráme v dalších částech zprávy, "
    "včetně jejich omezení a předpokladů"
)

KINDS = ("client", "final", "internal", "documentation")


def stretch(factor: float) -> Callable[[str], str]:
    """A function that lengthens text to ``factor`` times, with Czech filler."""

    def grow(s: str) -> str:
        if factor <= 1.0 or not s:
            return s
        target = int(len(s) * factor)
        out = s.rstrip(".")
        while len(out) < target:
            out += ", " + _FILLER
        return out + "."

    return grow


def meta(kind: ReportKind, **overrides: Any) -> ReportMeta:
    internal = kind in (ReportKind.INTERNAL, ReportKind.DOCUMENTATION)
    base: dict[str, Any] = {
        "kind": kind,
        "title": "Důvěra v banky 2026",
        "subtitle": "Co rozhoduje o přechodu k jiné bance",
        "client_name": "Klient a.s.",
        "study_name": "Důvěra 2026",
        "study_id": "STU-2026-014",
        "issued_on": date(2026, 9, 25),
        "revision": 2,
        "method_status": METHOD_STATUS_PENDING,
        "classification": Classification.INTERNAL
        if internal
        else Classification.CLIENT_CONFIDENTIAL,
        "history": (
            RevisionEntry(1, date(2026, 9, 18), "První verze k připomínkám"),
            RevisionEntry(2, date(2026, 9, 25), "Zapracované připomínky klienta"),
        ),
        "identifiers": (("Běh", "run-7f3a2c"), ("Populace", "pop-v17-static")) if internal else (),
    }
    base.update(overrides)
    return ReportMeta(**base)


def _regions_figure() -> Figure:
    return Figure(
        "fig-regions",
        "Důvěra v banky podle regionu",
        Chart(
            ChartKind.DOT_INTERVAL,
            ("Praha", "Brno", "Ostrava", "Zlín"),
            (Series("Důvěra", ("trust_praha", "trust_brno", "trust_ostrava", "trust_zlin")),),
            "Podíl důvěřujících (%)",
        ),
        "AIA, syntetický panel 2026",
        "Tečkový graf s intervaly: důvěra je nejvyšší v Praze a nejnižší v Ostravě.",
        base_ref="trust_total",
    )


def _switch_figure() -> Figure:
    return Figure(
        "fig-switch",
        "Modelovaná ochota přejít k jiné bance",
        Chart(
            ChartKind.BAR,
            ("Celkem", "Do 30 let"),
            (Series("Přechod", ("switch_modelled", "switch_modelled_young"), modelled=True),),
            "Podíl (%)",
        ),
        "AIA, behaviorální model 2026",
        "Pruhový graf: modelovaná ochota přejít je vyšší u lidí do 30 let.",
        notes=("Hodnoty jsou modelované z behaviorálního prioru, nikoli změřené.",),
    )


def _regions_table() -> Table:
    pct = Column("Důvěra", Align.RIGHT, unit="%")
    return Table(
        "tab-regions",
        "Důvěra v banky podle regionu",
        (Column("Region"), pct),
        (
            *(
                TableRow((TextCell(name), NumberCell(ref)))
                for name, ref in (
                    ("Praha", "trust_praha"),
                    ("Brno", "trust_brno"),
                    ("Ostrava", "trust_ostrava"),
                    ("Zlín", "trust_zlin"),
                )
            ),
            TableRow((TextCell("Celkem"), NumberCell("trust_total")), emphasis=True),
        ),
        "AIA, syntetický panel 2026",
        base_ref="trust_total",
    )


def _support_table(s: Callable[[str], str]) -> Table:
    return Table(
        "tab-support",
        "Efektivní podpora vzorku",
        (Column("Buňka"), Column("Respondenti", Align.RIGHT), Column("Poznámka")),
        (TableRow((TextCell("Celkem"), NumberCell("n_total"), TextCell(s("Plná podpora.")))),),
        "AIA, výpočet efektivní velikosti vzorku (Kish)",
        base_ref="n_total",
    )


def content(s: Callable[[str], str]) -> ReportContent:
    return ReportContent(
        executive_summary=(
            Text(s("Bankám v Česku důvěřuje ")),
            Value("trust_total"),
            Text(
                s(
                    " dospělých. Nejvíc důvěřují lidé v Praze, nejméně v Ostravě; rozdíl "
                    "je dost velký na to, aby rozhodl o tom, kde začít."
                )
            ),
        ),
        decision_answer=(
            Text(s("Kampaň na udržení klientů začněte v Praze, kde je důvěra nejvyšší (")),
            Value("trust_praha"),
            Text(s("), a v Ostravě ji nejdřív ověřte na větším vzorku.")),
        ),
        decision_refs=("trust_praha",),
        headline_kpis=KpiRow(
            (Kpi("Důvěřuje bankám", "trust_total"), Kpi("Respondentů", "n_total"))
        ),
        question_answers=(
            QuestionAnswer(
                s("Jak moc lidé důvěřují bankám?"),
                s("Necelá polovina dospělých jim důvěřuje."),
                "měřeno",
            ),
            QuestionAnswer(
                s("Kde je důvěra nejvyšší?"), s("V Praze; v Ostravě nejnižší."), "měřeno"
            ),
            QuestionAnswer(
                s("Kdo je ochoten přejít?"),
                s("Spíše mladší lidé; jde o modelovaný odhad."),
                "modelováno",
            ),
        ),
        key_findings=(
            KeyFinding(
                s("Praha důvěřuje bankám nejvíc"),
                s("Důvěra je v Praze vyšší než v ostatních regionech."),
                s("Srovnání regionů na plném vzorku, s intervaly."),
                s("Kampaň na udržení klientů má největší šanci uspět v Praze."),
                "střední",
                refs=("trust_praha",),
            ),
            KeyFinding(
                s("Mladší lidé by přešli spíš"),
                s("Model odhaduje vyšší ochotu přejít u lidí do 30 let."),
                s("Behaviorální model, nikoli měření."),
                s("Nabídku pro mladé testujte dřív, než ji rozšíříte."),
                "nízká",
                refs=("switch_modelled_young",),
            ),
        ),
        exhibits=(
            Paragraph(
                (
                    Text(s("Rozdíly mezi regiony ukazuje ")),
                    CrossRef("fig-regions"),
                    Text(s("; přesné hodnoty jsou v ")),
                    CrossRef("tab-regions"),
                    Text("."),
                    Footnote(s("Region Zlín je potlačen pro nízkou efektivní velikost vzorku.")),
                )
            ),
            _regions_figure(),
            _regions_table(),
            _switch_figure(),
            Quote(
                s("Banku měním, až když mě opravdu naštve."),
                "žena, 34 let, Brno",
                synthetic=True,
            ),
        ),
        implications=(
            Recommendation(
                s("Začněte v Praze"),
                s("Nejvyšší důvěra dává kampani nejlepší výchozí bod."),
                "vysoká",
                refs=("trust_praha",),
            ),
            Recommendation(
                s("Ověřte Ostravu na větším vzorku"),
                s("Výsledek je orientační; rozhodnutí by na něm nemělo stát."),
                "střední",
                refs=("trust_ostrava",),
            ),
        ),
        validation_summary=(
            Text(
                s(
                    "Výsledky odpovídají dostupným veřejným průzkumům důvěry v instituce; "
                    "externí prediktivní validace proti lidskému vzorku zatím neproběhla."
                )
            ),
        ),
        confidence_summary=(
            Text(s("Jistota je nejvyšší u celkové důvěry a u Prahy, nejnižší u Ostravy.")),
        ),
        method_summary=(
            Text(
                s(
                    "Syntetický panel kalibrovaný na populaci ČR 18+, vážený; čísla prošla "
                    "evidenční branou a jsou uvedena s intervaly."
                )
            ),
        ),
        limitations=(
            s("Výsledky jsou syntetické a modelované, nikoli měřené na lidech."),
            s("Region Zlín nemá dostatečnou efektivní velikost vzorku."),
            s("Ochota přejít je modelovaný odhad."),
        ),
        closing=(
            Text(s("Důvěra je dost silná na to, aby se na ní dalo stavět, začněte v Praze.")),
        ),
        appendices=(
            Section(
                "Dotazník",
                (Paragraph((Text(s("Q1. Jak moc důvěřujete bankám? (škála 1-5)")),)),),
                id="app-questionnaire",
                appendix=True,
            ),
        ),
    )


def build(
    kind: str, report_ledger: Any, *, stress: float = 1.0, approved: bool = False
) -> ReportDocument:
    """One sample report of ``kind`` (``KINDS``)."""
    s = stretch(stress)
    approvals = (Approval("J. Nováková", date(2026, 9, 26)),) if approved else ()
    audit = (("Běh", "run-7f3a2c"), ("Model", "anthropic.claude (Bedrock EU)"), ("QA", "passed"))
    if kind == "client":
        return client_report(
            meta(ReportKind.CLIENT, approvals=approvals), content(s), report_ledger()
        )
    if kind == "final":
        final = FinalContent(
            triangulation=(
                Paragraph((Text(s("Srovnání s veřejnými průzkumy: směr i pořadí regionů sedí.")),)),
            ),
            support=_support_table(s),
        )
        return final_report(
            meta(ReportKind.FINAL, approvals=approvals), content(s), final, report_ledger()
        )
    ledger = report_ledger(ClaimSurface.INTERNAL)
    if kind == "internal":
        return internal_report(
            meta(ReportKind.INTERNAL, approvals=approvals), content(s), audit, ledger
        )
    if kind == "documentation":
        doc = DocumentationContent(
            purpose=(
                Text(s("Studie zjišťuje, jak lidé důvěřují bankám a co je vede k přechodu.")),
            ),
            design=(Paragraph((Text(s("Průřezová studie na syntetickém panelu, jedna vlna.")),)),),
            population=(Paragraph((Text(s("Populace ČR 18+, statická verze v17.")),)),),
            support=_support_table(s),
            method=(
                Paragraph((Text(s("Vážení na populaci, Kish efektivní n, evidenční brána.")),)),
            ),
            limitations=(s("Externí validace čeká."),),
        )
        return study_documentation(
            meta(ReportKind.DOCUMENTATION, approvals=approvals), doc, audit, ledger
        )
    raise ValueError(f"no sample for {kind!r}")
