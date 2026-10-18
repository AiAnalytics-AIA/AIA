"""The report templates: every sample renders, in its section order, and the client
variants carry no internals.

With ``AIA_REPORT_SAMPLES_DIR`` set, the samples are also written there as DOCX
(``tools/report_preview.py --samples`` uses this), and ``AIA_REPORT_STRESS``
lengthens their prose (``--stress``, +35 % by default).
"""

from __future__ import annotations

import io
import os
import re
import zipfile
from pathlib import Path
from typing import Any

import pytest
import report_samples
from lxml import etree

from aia_core.domain.report.model import EvidenceAppendix, ReportKind
from aia_core.domain.report.templates import client_report
from aia_core.domain.report.validation import validate
from aia_core.infrastructure.report_docx.lint import lint_docx
from aia_core.infrastructure.report_docx.renderer import DocxRenderer

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: Words and ids no client may see (legacy tests/test_release_core.py:22, plus the
#: identifiers and audit values the internal samples carry).
INTERNAL = re.compile(
    r"quality gate|provider|prompt|claude|anthropic|bedrock|openai|run-7f3a2c|STU-2026-014|"
    r"pop-v17|\bQA\b|Audit",
    re.IGNORECASE,
)


def _all_text(data: bytes) -> str:
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if name.endswith(".xml") and (name.startswith("word/") or name.startswith("docProps/")):
                root = etree.fromstring(z.read(name))
                out.append(" ".join(t.text or "" for t in root.iter(f"{W}t")))
                out.append(" ".join(e.text or "" for e in root.iter() if not len(e)))
    return "\n".join(out)


@pytest.mark.parametrize("kind", report_samples.KINDS)
def test_every_template_renders_a_valid_clean_report(kind: str, report_ledger: Any) -> None:
    stress = float(os.environ.get("AIA_REPORT_STRESS", "1.0"))
    doc = report_samples.build(kind, report_ledger, stress=stress)
    assert validate(doc) == ()
    data = DocxRenderer().render(doc)
    assert lint_docx(data) == []
    out = os.environ.get("AIA_REPORT_SAMPLES_DIR")
    if out:
        suffix = "-stress" if stress != 1.0 else ""
        Path(out).mkdir(parents=True, exist_ok=True)
        (Path(out) / f"{kind}{suffix}.docx").write_bytes(data)


#: Word sections per sample: cover, front matter, body, then one per change of
#: orientation (the landscape evidence appendix, and the portrait page after it).
SECTIONS = {"internal": 5, "client": 4, "final": 4, "documentation": 5}


@pytest.mark.parametrize("kind", report_samples.KINDS)
def test_a_section_opens_only_where_the_page_changes(kind: str, report_ledger: Any) -> None:
    # Was one more for each sample with a portrait appendix, which opened a section,
    # and so a page, of its own. Chapters and appendices now flow
    # (research-integrity-report D5).
    doc = report_samples.build(kind, report_ledger)
    wide = [
        s.appendix and any(isinstance(b, EvidenceAppendix) for b in s.blocks) for s in doc.sections
    ]
    turns = sum(before != after for before, after in zip([False, *wide], wide, strict=False))
    with zipfile.ZipFile(io.BytesIO(DocxRenderer().render(doc))) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    sections = list(root.iter(f"{W}sectPr"))
    assert len(sections) == 3 + turns == SECTIONS[kind]
    landscape = [s.find(f"{W}pgSz").get(f"{W}orient") == "landscape" for s in sections[2:]]
    assert landscape == [i % 2 == 1 for i in range(len(landscape))]  # body portrait, then turns


def test_the_client_report_follows_the_legacy_section_order(report_ledger: Any) -> None:
    doc = report_samples.build("client", report_ledger)
    assert [s.title for s in doc.sections] == [
        "Shrnutí pro vedení",
        "Odpověď pro rozhodnutí",
        "Výzkumné otázky",
        "Co jsme zjistili",
        "Doporučení",
        "Jak výsledky zapadají do dostupné externí evidence",
        "Jistota závěrů",
        "Metodika",
        "Limity",
        "Závěr",
        "Dotazník",
        "Evidenční příloha",
    ]


def test_the_final_report_adds_triangulation_and_support(report_ledger: Any) -> None:
    titles = [s.title for s in report_samples.build("final", report_ledger).sections]
    at = titles.index("Jak výsledky zapadají do dostupné externí evidence")
    assert titles[at + 1 : at + 3] == ["Externí kontext a triangulace", "Efektivní podpora vzorku"]


@pytest.mark.parametrize("kind", ["client", "final"])
def test_a_client_variant_carries_no_internal_strings(kind: str, report_ledger: Any) -> None:
    data = DocxRenderer().render(report_samples.build(kind, report_ledger))
    hits = sorted({m.group(0) for m in INTERNAL.finditer(_all_text(data))})
    assert hits == []


def test_the_internal_report_carries_the_audit_and_identifiers(report_ledger: Any) -> None:
    doc = report_samples.build("internal", report_ledger)
    assert doc.sections[-1].title == "Audit" and doc.sections[-1].appendix
    text = _all_text(DocxRenderer().render(doc))
    for value in ("run-7f3a2c", "STU-2026-014", "anthropic.claude (Bedrock EU)"):
        assert value in text


def test_a_template_refuses_the_wrong_report_kind(report_ledger: Any) -> None:
    with pytest.raises(ValueError, match="makes a client report"):
        client_report(
            report_samples.meta(ReportKind.FINAL),
            report_samples.content(report_samples.stretch(1.0)),
            report_ledger(),
        )


def test_stress_lengthens_prose_by_the_factor() -> None:
    grow = report_samples.stretch(1.35)
    original = "Kampaň začněte v Praze, kde je důvěra nejvyšší."
    assert len(grow(original)) >= int(len(original) * 1.35)
    assert grow(original).startswith("Kampaň začněte v Praze")
