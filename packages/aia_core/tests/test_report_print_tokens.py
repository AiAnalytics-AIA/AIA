"""The report's print register, generated from the design tokens.

`apps/web/scripts/build-tokens.mjs` writes `domain/report/print_tokens.py` from
`apps/web/src/design/tokens.json`, and `npm run tokens:check` fails CI when the two
drift. These tests pin what the DOCX renderer relies on.
"""

from __future__ import annotations

import re
import subprocess
import sys

from aia_core.domain.report import print_tokens as pt

#: Styles the renderer maps onto Word styles. Removing one from tokens.json breaks it.
REQUIRED = {
    "doc-title",
    "doc-subtitle",
    "doc-kicker",
    "doc-h1",
    "doc-h2",
    "doc-h3",
    "doc-lede",
    "doc-body",
    "doc-caption",
    "doc-footnote",
    "doc-meta",
    "doc-running",
    "doc-table",
    "doc-table-head",
    "doc-kpi",
    "doc-quote",
    "doc-mono",
}


def test_every_required_style_is_present() -> None:
    assert set(pt.STYLES) >= REQUIRED


def test_every_style_resolves_to_an_embeddable_font() -> None:
    for style in pt.STYLES.values():
        assert style.font in pt.FONTS, style.name


def test_no_print_text_falls_below_the_legibility_floor() -> None:
    # 7.5 pt is the floor for running heads and fingerprints; body text is 10.5 pt.
    for style in pt.STYLES.values():
        assert style.size_pt >= 7.5, style.name
        assert style.leading_pt >= style.size_pt, style.name
    assert pt.STYLES["doc-body"].size_pt == 10.5
    assert pt.STYLES["doc-body"].leading_pt == 16.8


def test_headings_are_semibold_faces_not_synthetic_bold() -> None:
    # Weight 600 has its own face; Word's synthetic bold would thicken Regular.
    for name in ("doc-h1", "doc-h2", "doc-h3", "doc-title"):
        assert not pt.STYLES[name].bold, name
        assert "Semibold" in pt.STYLES[name].font or "SmBld" in pt.STYLES[name].font


def test_colours_are_resolved_hex_from_the_light_theme() -> None:
    for name, value in pt.COLORS.items():
        assert re.fullmatch(r"#[0-9a-f]{6}", value), name
    assert pt.COLORS["doc-paper"] == "#fffdfa"
    assert pt.COLORS["doc-ink"] == "#0f1216"
    assert set(pt.COLORS) >= {f"viz-cat-{i}" for i in range(1, 7)}


def test_page_is_a4_with_room_for_running_heads() -> None:
    assert (pt.PAGE.width_mm, pt.PAGE.height_mm) == (210.0, 297.0)
    assert pt.PAGE.header_mm < pt.PAGE.margin_top_mm
    assert pt.PAGE.footer_mm < pt.PAGE.margin_bottom_mm


def test_the_module_needs_nothing_but_the_stdlib() -> None:
    # The domain layer must stay importable with nothing installed but Pydantic;
    # the print register needs even less.
    code = (
        "import sys; import aia_core.domain.report.print_tokens; "
        "bad = [m for m in sys.modules if m.split('.')[0] in "
        "{'docx', 'matplotlib', 'lxml', 'numpy', 'sqlalchemy'}]; "
        "assert not bad, bad"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
