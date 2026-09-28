"""Figures in DOCX: every chart kind, SVG with PNG fallback, alt text, the Sociomap gate.

A chart plots the ledger's values and labels them as the evidence rounded them;
a suppressed point is left out and counted; a modelled series is hatched and
says so; and a Sociomap reaches a client report only when CLIENT_FACING.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import replace
from typing import Any

import pytest
from lxml import etree
from PIL import Image
from test_report_docx_render import _meta

from aia_core.domain.evidence.claims import ClaimSurface
from aia_core.domain.report.model import (
    Callout,
    CalloutKind,
    Chart,
    ChartKind,
    Classification,
    Figure,
    ReportDocument,
    ReportKind,
    Section,
    Series,
    SociomapFigure,
)
from aia_core.domain.report.validation import ReportInvalid
from aia_core.domain.research_sociomap import SociomapNotApproved
from aia_core.infrastructure.report_docx.charts import draw_chart
from aia_core.infrastructure.report_docx.lint import lint_docx
from aia_core.infrastructure.report_docx.renderer import DocxRenderer

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
NB = "\u00a0"

REGIONS = ("Praha", "Brno", "Ostrava", "Zlín")
TRUST = ("trust_praha", "trust_brno", "trust_ostrava", "trust_zlin")


def _png(width: int = 60, height: int = 40) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "#dde6f0").save(out, format="PNG")
    return out.getvalue()


def chart(kind: ChartKind) -> Chart:
    if kind is ChartKind.BAR:
        return Chart(kind, REGIONS, (Series("Důvěra", TRUST),), "Podíl (%)")
    if kind is ChartKind.DOT_INTERVAL:
        return Chart(kind, REGIONS, (Series("Důvěra", TRUST),), "Podíl (%)")
    if kind is ChartKind.LINE:
        return Chart(
            kind,
            ("2024", "2025", "2026"),
            (
                Series("Důvěra", ("trust_brno", "trust_total", "trust_praha")),
                Series("Přechod", ("switch_modelled", None, "switch_modelled_young"), True),
            ),
            "Podíl (%)",
        )
    return Chart(
        kind,
        ("Celkem", "Mladí"),
        (
            Series("Nesouhlas", ("trust_brno", "trust_ostrava")),
            Series("Neutrální", ("trust_total", "trust_praha")),
            Series("Souhlas", ("switch_modelled", "switch_modelled_young"), True),
        ),
        "Podíl (%)",
    )


def figures_document(ledger: Any, **meta: Any) -> ReportDocument:
    kinds = [
        ChartKind.BAR,
        ChartKind.DOT_INTERVAL,
        ChartKind.LINE,
        ChartKind.STACKED_100,
        ChartKind.DIVERGING,
        ChartKind.GROUPED_BAR,
        ChartKind.HEATMAP,
    ]
    figs = tuple(
        Figure(
            f"fig-{k.value}",
            f"Graf druhu {k.value}",
            chart(k),
            "AIA, syntetický panel 2026",
            f"Popis grafu {k.value} pro čtečku obrazovky.",
            base_ref="trust_total",
        )
        for k in kinds
    )
    return ReportDocument(
        _meta(**meta),
        (Section("Grafy", (Callout(CalloutKind.METHOD, ()), *figs)),),
        ledger,
    )


def _parts(doc: ReportDocument) -> dict[str, bytes]:
    data = DocxRenderer().render(doc)
    assert lint_docx(data) == []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist()}


def _t(el: etree._Element) -> str:
    return "".join(t.text or "" for t in el.iter(f"{W}t"))


def test_every_chart_kind_renders_as_svg_with_a_png_fallback(report_ledger: Any) -> None:
    parts = _parts(figures_document(report_ledger()))
    root = etree.fromstring(parts["word/document.xml"])
    alts = [d.get("descr") for d in root.iter(f"{WP}docPr")]
    for kind in ("bar", "dot_interval", "line", "stacked_100", "diverging", "heatmap"):
        assert f"Popis grafu {kind} pro čtečku obrazovky." in alts
    svgs = [n for n in parts if n.endswith(".svg")]
    assert len(svgs) >= 7
    for name in svgs:
        svg = parts[name].decode()
        assert "<text" not in svg  # text is paths: no font needed on the reader's machine
        assert "<dc:date>" not in svg


def test_captions_number_figures_and_state_base_and_suppression(report_ledger: Any) -> None:
    root = etree.fromstring(_parts(figures_document(report_ledger()))["word/document.xml"])
    caps = [
        _t(p)
        for p in root.iter(f"{W}p")
        if (s := p.find(f"{W}pPr/{W}pStyle")) is not None and s.get(f"{W}val") == "Caption"
    ]
    assert caps[0] == f"Graf 1 — Graf druhu bar (n{NB}={NB}480; měřeno)"
    assert caps[2].startswith("Graf 3 — Graf druhu line (n")
    assert "měřeno" not in caps[2]  # a measured and a modelled series: no single grade
    sources = [_t(p) for p in root.iter(f"{W}p") if _t(p).startswith("Zdroj:")]
    assert sources[0].endswith("Potlačeno pro nedostatečnou efektivní velikost vzorku: 1.")
    instr = [(i.text or "").strip() for i in root.iter(f"{W}instrText")]
    assert 'TOC \\h \\z \\c "Graf"' in instr
    assert instr.count("SEQ Graf \\* ARABIC") == 7


def test_a_chart_is_drawn_from_the_ledger_and_is_deterministic(report_ledger: Any) -> None:
    doc = figures_document(report_ledger())
    first = DocxRenderer().render(doc)
    assert first == DocxRenderer().render(doc)


def test_the_bar_chart_leaves_the_suppressed_point_out(report_ledger: Any) -> None:
    from aia_core.infrastructure.report_docx.charts import points

    class Ctx:
        ledger = report_ledger()

    pts, omitted = points(Ctx(), Series("Důvěra", TRUST))  # type: ignore[arg-type]
    assert omitted == 1 and pts[3] is None
    assert [p.label for p in pts if p] == [f"48,2{NB}%", f"39,7{NB}%", f"36,1{NB}%"]
    drawn = draw_chart(Ctx(), chart(ChartKind.BAR))  # type: ignore[arg-type]
    assert drawn.omitted == 1
    assert 0 < drawn.width_mm <= 166.0


def _sociomap(status: str) -> SociomapFigure:
    return SociomapFigure(
        "map-1", "Sociomapa důvěry", _png(), status, 0.1234, "AIA", "Mapa vztahů mezi bankami."
    )


def test_a_client_report_refuses_an_unapproved_sociomap(report_ledger: Any) -> None:
    doc = figures_document(report_ledger())
    section = replace(doc.sections[0], blocks=(*doc.sections[0].blocks, _sociomap("INTERNAL_ONLY")))
    with pytest.raises(ReportInvalid, match="sociomap_not_approved"):
        DocxRenderer().render(replace(doc, sections=(section,)))


def test_the_renderer_checks_the_sociomap_gate_itself(report_ledger: Any, monkeypatch: Any) -> None:
    import aia_core.infrastructure.report_docx.renderer as renderer

    doc = figures_document(report_ledger())
    section = replace(doc.sections[0], blocks=(*doc.sections[0].blocks, _sociomap("INTERNAL_ONLY")))
    monkeypatch.setattr(renderer, "require_valid", lambda d: d)  # as if validation were bypassed
    with pytest.raises(SociomapNotApproved):
        DocxRenderer().render(replace(doc, sections=(section,)))


def test_an_approved_sociomap_prints_its_stress(report_ledger: Any) -> None:
    doc = figures_document(report_ledger())
    section = replace(doc.sections[0], blocks=(*doc.sections[0].blocks, _sociomap("CLIENT_FACING")))
    root = etree.fromstring(_parts(replace(doc, sections=(section,)))["word/document.xml"])
    assert any(_t(p) == "Graf 8 — Sociomapa důvěry (stres 1 = 0,123)" for p in root.iter(f"{W}p"))
    assert "Mapa vztahů mezi bankami." in [d.get("descr") for d in root.iter(f"{WP}docPr")]


def test_an_internal_report_labels_an_internal_sociomap(report_ledger: Any) -> None:
    doc = figures_document(
        report_ledger(ClaimSurface.INTERNAL),
        kind=ReportKind.INTERNAL,
        classification=Classification.INTERNAL,
    )
    section = replace(doc.sections[0], blocks=(*doc.sections[0].blocks, _sociomap("INTERNAL_ONLY")))
    root = etree.fromstring(_parts(replace(doc, sections=(section,)))["word/document.xml"])
    assert any("není schválena pro klienta" in _t(p) for p in root.iter(f"{W}p"))
