"""The report as data: Czech formatting, print grades, the ledger, and validation.

A report holds no numbers of its own: every value is a reference into a ledger
built from admitted claims. These tests pin the rules the renderer relies on the
validator to have enforced.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from aia_core.domain.evidence import ClaimBasis, ClaimSurface, Interval, MetricUnit
from aia_core.domain.evidence.validation import METHOD_STATUS_PENDING
from aia_core.domain.report import numbers
from aia_core.domain.report.evidence import PrintGrade, UnknownEvidence, grade_of
from aia_core.domain.report.model import (
    AuditBlock,
    BulletList,
    Callout,
    CalloutKind,
    Chart,
    ChartKind,
    Classification,
    Column,
    CrossRef,
    Figure,
    Heading,
    Kpi,
    KpiRow,
    ListItem,
    NumberCell,
    Paragraph,
    Quote,
    ReportDocument,
    ReportKind,
    ReportMeta,
    Section,
    Series,
    SociomapFigure,
    Table,
    TableRow,
    Text,
    TextCell,
    text,
)
from aia_core.domain.report.validation import ProblemCode, ReportInvalid, require_valid, validate

NB = numbers.NBSP


# --- Czech formatting -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "decimals", "out"),
    [
        (42.5, 1, "42,5"),
        (1204.0, 0, f"1{NB}204"),
        (1234567.25, 2, f"1{NB}234{NB}567,25"),
        (0.0, 1, "0,0"),
        (-3.2, 1, "\u22123,2"),
    ],
)
def test_numbers_print_in_czech_without_re_rounding(value: float, decimals: int, out: str) -> None:
    assert numbers.number(value, decimals) == out


def test_a_number_the_evidence_did_not_round_is_refused() -> None:
    with pytest.raises(ValueError, match="not rounded"):
        numbers.number(42.54, 1)
    with pytest.raises(ValueError, match="non-finite"):
        numbers.number(float("nan"), 1)


def test_units_intervals_and_base_n() -> None:
    assert numbers.with_unit(42.5, 1, MetricUnit.PERCENT) == f"42,5{NB}%"
    assert numbers.with_unit(3.8, 1, MetricUnit.SCALE_MEAN) == "3,8"
    iv = Interval(38.1, 46.9, 0.95)
    assert numbers.interval(iv, 1, MetricUnit.PERCENT) == f"(38,1\u201346,9{NB}%)"
    assert numbers.base_n(480.9) == f"n{NB}={NB}480"  # rounded down, never up


def test_czech_dates_use_the_genitive_month() -> None:
    assert numbers.czech_date(date(2026, 9, 25)) == f"25.{NB}září{NB}2026"


# --- grades ------------------------------------------------------------------------------


def test_modelled_basis_always_prints_modelled(evidence_row: Any) -> None:
    row = evidence_row(basis=ClaimBasis.MODELED, fields=("deal_seeking_1_10",))
    assert grade_of(row, {"deal_seeking_1_10": PrintGrade.MEASURED}) is PrintGrade.MODELLED


def test_a_field_without_a_grade_prints_unknown_never_measured(evidence_row: Any) -> None:
    assert grade_of(evidence_row()) is PrintGrade.UNKNOWN
    assert grade_of(evidence_row(), {"vek": PrintGrade.MEASURED}) is PrintGrade.MEASURED


def test_a_claim_prints_the_weakest_grade_of_its_fields(evidence_row: Any) -> None:
    row = evidence_row(fields=("vek", "vzdelani"), joint=True)
    grades = {"vek": PrintGrade.MEASURED, "vzdelani": PrintGrade.CALIBRATED}
    assert grade_of(row, grades) is PrintGrade.CALIBRATED


def test_several_fields_not_jointly_measured_never_print_measured(evidence_row: Any) -> None:
    row = evidence_row(fields=("vek", "vzdelani"), joint=False)
    grades = {"vek": PrintGrade.MEASURED, "vzdelani": PrintGrade.MEASURED}
    assert grade_of(row, grades) is PrintGrade.UNKNOWN


# --- the ledger ---------------------------------------------------------------------------


def test_the_ledger_holds_admitted_rows_and_names_the_suppressed(report_ledger: Any) -> None:
    ledger = report_ledger()
    assert ledger.row("trust_total").value == 42.5
    assert ledger.is_suppressed("trust_zlin")
    with pytest.raises(UnknownEvidence, match="suppressed"):
        ledger.row("trust_zlin")
    with pytest.raises(UnknownEvidence, match="does not hold"):
        ledger.row("nowhere")
    assert ledger.is_indicative("trust_ostrava")
    assert ledger.grade("trust_total") is PrintGrade.MEASURED
    assert ledger.grade("switch_modelled") is PrintGrade.MODELLED


def test_an_internal_claim_is_refused_in_a_client_ledger(
    evidence_row: Any, field_book: Any, joint_status: Any
) -> None:
    from aia_core.domain.evidence import EvidenceTable, NumericClaim, admit_numeric_claims
    from aia_core.domain.report.evidence import EvidenceLedger

    table = EvidenceTable.build([evidence_row("E1")])
    claim = NumericClaim("c1", "E1", "top2box_pct", 42.5, "%")
    admission = admit_numeric_claims(
        [claim], table, book=field_book, joint_status=joint_status, surface=ClaimSurface.INTERNAL
    )
    assert admission.decision.allowed
    with pytest.raises(ValueError, match="admitted for INTERNAL"):
        EvidenceLedger.from_claims(admission.admitted, surface=ClaimSurface.CLIENT_FACING)


# --- validation --------------------------------------------------------------------------


def meta(kind: ReportKind = ReportKind.CLIENT, **kw: Any) -> ReportMeta:
    args: dict[str, Any] = {
        "kind": kind,
        "title": "Důvěra v digitální bankovnictví 2026",
        "subtitle": "Závěrečná zpráva",
        "client_name": "Banka Horizont",
        "study_name": "Důvěra 2026",
        "study_id": "STU-0a1b01",
        "issued_on": date(2026, 9, 25),
        "revision": 1,
        "method_status": METHOD_STATUS_PENDING,
        "classification": Classification.CLIENT_CONFIDENTIAL
        if kind in (ReportKind.CLIENT, ReportKind.FINAL)
        else Classification.INTERNAL,
    }
    args.update(kw)
    return ReportMeta(**args)


METHOD = Callout(CalloutKind.METHOD, text("Syntetický výzkum."))


def figure(**kw: Any) -> Figure:
    args: dict[str, Any] = {
        "id": "fig-trust",
        "title": "Důvěra podle regionu",
        "chart": Chart(
            ChartKind.BAR,
            ("Praha", "Brno", "Ostrava"),
            (Series("Důvěra", ("trust_praha", "trust_brno", "trust_ostrava")),),
            "Podíl (%)",
        ),
        "source": "AIA, syntetický panel",
        "alt": "Sloupcový graf důvěry podle regionu.",
        "base_ref": "n_total",
    }
    args.update(kw)
    return Figure(**args)


def table(**kw: Any) -> Table:
    args: dict[str, Any] = {
        "id": "tab-trust",
        "title": "Důvěra podle regionu",
        "columns": (Column("Region"), Column("Podíl", unit="%")),
        "rows": (
            TableRow((TextCell("Praha"), NumberCell("trust_praha", with_interval=True))),
            TableRow((TextCell("Zlín"), NumberCell("trust_zlin"))),  # suppressed: removed
        ),
        "source": "AIA, syntetický panel",
        "base_ref": "n_total",
    }
    args.update(kw)
    return Table(**args)


def doc(ledger: Any, *blocks: Any, kind: ReportKind = ReportKind.CLIENT, **kw: Any) -> Any:
    return ReportDocument(
        meta(kind, **kw),
        (Section("Hlavní zjištění", (METHOD, *blocks), id="ch-findings"),),
        ledger,
    )


def codes(document: Any) -> set[ProblemCode]:
    return {p.code for p in validate(document)}


def test_a_complete_client_report_is_valid(report_ledger: Any) -> None:
    ledger = report_ledger()
    d = doc(
        ledger,
        Paragraph((Text("Důvěra je "), CrossRef("fig-trust"), Text("."))),
        KpiRow((Kpi("Důvěřuje", "trust_total"),)),
        figure(),
        table(),
        Heading("Regiony", 2),
        Heading("Praha", 3),
        Quote("„Bankám věřím.“", "respondentka, 34 let", synthetic=True),
    )
    assert validate(d) == ()
    assert require_valid(d) is d


def test_every_cited_ref_must_be_in_the_ledger(report_ledger: Any) -> None:
    d = doc(report_ledger(), KpiRow((Kpi("?", "nowhere"),)))
    assert ProblemCode.UNKNOWN_REF in codes(d)


def test_a_suppressed_ref_may_be_omitted_from_data_but_never_printed(report_ledger: Any) -> None:
    ledger = report_ledger()
    assert codes(doc(ledger, table())) == set()  # a suppressed table row is removed
    assert ProblemCode.SUPPRESSED_CITED in codes(doc(ledger, KpiRow((Kpi("Zlín", "trust_zlin"),))))


def test_a_client_report_prints_the_method_status_on_the_page(report_ledger: Any) -> None:
    d = ReportDocument(meta(), (Section("Shrnutí", (Paragraph(text("Text.")),)),), report_ledger())
    assert ProblemCode.METHOD_STATUS in codes(d)


def test_a_client_report_needs_client_facing_claims(report_ledger: Any) -> None:
    d = doc(report_ledger(ClaimSurface.INTERNAL))
    assert ProblemCode.WRONG_SURFACE in codes(d)


def test_internals_never_reach_a_client(report_ledger: Any) -> None:
    ledger = report_ledger()
    assert ProblemCode.INTERNAL_BLOCK in codes(doc(ledger, AuditBlock((("run", "R-1"),))))
    assert ProblemCode.INTERNAL_BLOCK in codes(doc(ledger, identifiers=(("run", "R-1"),)))
    leak = Paragraph(text("Výsledek prošel quality gate u providera."))
    assert ProblemCode.INTERNAL_LEAK in codes(doc(ledger, leak))


def test_an_internal_report_may_carry_the_audit(report_ledger: Any) -> None:
    d = doc(
        report_ledger(ClaimSurface.INTERNAL),
        AuditBlock((("provider", "claude_code"),)),
        kind=ReportKind.INTERNAL,
        identifiers=(("run", "R-1"),),
    )
    assert validate(d) == ()


def test_classification_follows_the_kind(report_ledger: Any) -> None:
    d = doc(report_ledger(), classification=Classification.INTERNAL)
    assert ProblemCode.CLASSIFICATION in codes(d)


def test_a_figure_needs_title_source_and_alt_text(report_ledger: Any) -> None:
    assert ProblemCode.FIGURE_INCOMPLETE in codes(doc(report_ledger(), figure(alt=" ")))
    assert ProblemCode.TABLE_INCOMPLETE in codes(doc(report_ledger(), table(source="")))


def test_chart_rules(report_ledger: Any) -> None:
    ledger = report_ledger()
    short = Chart(ChartKind.BAR, ("Praha", "Brno"), (Series("x", ("trust_praha",)),), "%")
    assert ProblemCode.SERIES_SHAPE in codes(doc(ledger, figure(chart=short)))
    mixed = Chart(ChartKind.BAR, ("a", "b"), (Series("x", ("trust_praha", "n_total")),), "?")
    assert ProblemCode.MIXED_UNITS in codes(doc(ledger, figure(chart=mixed)))
    many = Chart(
        ChartKind.GROUPED_BAR,
        ("a",),
        tuple(Series(f"s{i}", ("trust_praha",)) for i in range(7)),
        "%",
    )
    assert ProblemCode.TOO_MANY_SERIES in codes(doc(ledger, figure(chart=many)))


def test_hatching_must_match_the_grade(report_ledger: Any) -> None:
    ledger = report_ledger()
    unhatched = Chart(ChartKind.BAR, ("a",), (Series("x", ("switch_modelled",)),), "%")
    assert ProblemCode.MODELLED_MISMATCH in codes(doc(ledger, figure(chart=unhatched)))
    hatched = Chart(ChartKind.BAR, ("a",), (Series("x", ("switch_modelled",), modelled=True),), "%")
    assert ProblemCode.MODELLED_MISMATCH not in codes(doc(ledger, figure(chart=hatched)))


def test_table_rows_match_their_columns(report_ledger: Any) -> None:
    bad = table(rows=(TableRow((TextCell("Praha"),)),))
    assert ProblemCode.TABLE_SHAPE in codes(doc(report_ledger(), bad))


def test_ids_are_unique_and_crossrefs_resolve(report_ledger: Any) -> None:
    ledger = report_ledger()
    assert ProblemCode.DUPLICATE_ID in codes(doc(ledger, figure(), figure()))
    dangling = Paragraph((Text("viz "), CrossRef("fig-missing")))
    assert ProblemCode.DANGLING_CROSSREF in codes(doc(ledger, dangling))


def test_structure_rules(report_ledger: Any) -> None:
    ledger = report_ledger()
    assert ProblemCode.HEADING_SKIP in codes(doc(ledger, Heading("Hluboko", 3)))
    deep = BulletList((ListItem(text("a"), (ListItem(text("b"), (ListItem(text("c")),)),)),))
    assert ProblemCode.LIST_DEPTH in codes(doc(ledger, deep))
    assert ProblemCode.QUOTE_UNATTRIBUTED in codes(doc(ledger, Quote("„…“", " ", True)))


def test_an_unapproved_sociomap_never_reaches_a_client(report_ledger: Any) -> None:
    sociomap = SociomapFigure(
        "map-1", "Sociomapa", b"\x89PNG", "INTERNAL_ONLY", 0.12, "AIA", "Mapa vztahů."
    )
    ledger = report_ledger()
    assert ProblemCode.SOCIOMAP_NOT_APPROVED in codes(doc(ledger, sociomap))
    approved = replace(sociomap, methodology_status="CLIENT_FACING")
    assert ProblemCode.SOCIOMAP_NOT_APPROVED not in codes(doc(ledger, approved))


def test_require_valid_lists_every_problem(report_ledger: Any) -> None:
    d = doc(report_ledger(), figure(alt=""), KpiRow((Kpi("?", "nowhere"),)))
    with pytest.raises(ReportInvalid) as caught:
        require_valid(d)
    assert {p.code for p in caught.value.problems} >= {
        ProblemCode.FIGURE_INCOMPLETE,
        ProblemCode.UNKNOWN_REF,
    }
