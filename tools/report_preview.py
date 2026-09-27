#!/usr/bin/env python3
"""Look at a report the way a reader will: DOCX -> PDF -> PNG, through LibreOffice.

A structural test cannot see a cropped chart, a heading orphaned at the foot of
a page or a table column too narrow for Czech. This renders any DOCX (or the
four template samples) to pages and a contact sheet, and lints the package on
the way. It is a verification tool, never a runtime dependency.

    python tools/report_preview.py report.docx               # one file
    python tools/report_preview.py --samples                 # the four templates
    python tools/report_preview.py --samples --stress        # prose +35 %
    python tools/report_preview.py --samples --grey          # greyscale pages too

Needs LibreOffice **Writer** (``libreoffice-writer``, not only its core) and
``pdftoppm`` (``poppler-utils``); see AGENTS.md § DOCX. Output goes to
``tmp/report-preview/`` unless ``--out`` says otherwise: per document the PDF,
one PNG per page (``-grey`` twins with ``--grey``) and ``<name>-sheet.png``.
Exits 1 when a package fails the lint or a conversion fails.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "packages" / "aia_core"
STRESS_DEFAULT = 1.35


def _need(tool: str) -> str:
    path = shutil.which(tool)
    if path is None:
        sys.exit(f"report_preview: {tool!r} is not installed (see AGENTS.md § DOCX)")
    return path


def write_samples(out: Path, stress: float | None) -> list[Path]:
    """Render the four template samples through their own test, into ``out``."""
    env = dict(os.environ, AIA_REPORT_SAMPLES_DIR=str(out))
    if stress is not None:
        env["AIA_REPORT_STRESS"] = str(stress)
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        str(CORE / "tests" / "test_report_templates.py"),
        "-k",
        "every_template_renders",
    ]
    result = subprocess.run(cmd, cwd=CORE, env=env, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"report_preview: the sample tests failed\n{result.stdout}{result.stderr}")
    suffix = "-stress" if stress is not None else ""
    return (
        sorted(out.glob(f"*{suffix}.docx"))
        if suffix
        else sorted(p for p in out.glob("*.docx") if not p.stem.endswith("-stress"))
    )


def lint(docx: Path) -> list[str]:
    # aia_core with the report extra: `make deps` installs it in the venv.
    from aia_core.infrastructure.report_docx.lint import lint_docx

    problems: list[str] = lint_docx(docx.read_bytes())
    return problems


def to_pdf(docx: Path, out: Path) -> Path:
    soffice = _need("soffice")
    with tempfile.TemporaryDirectory() as profile:
        # A private profile: a running LibreOffice or a stale lock never blocks this.
        subprocess.run(
            [
                soffice,
                f"-env:UserInstallation=file://{profile}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out),
                str(docx),
            ],
            check=True,
            capture_output=True,
            timeout=300,
        )
    pdf = out / f"{docx.stem}.pdf"
    if not pdf.exists():
        raise RuntimeError(f"LibreOffice wrote no PDF for {docx}")
    return pdf


def to_pngs(pdf: Path, out: Path, dpi: int, grey: bool) -> list[Path]:
    pdftoppm = _need("pdftoppm")
    for old in out.glob(f"{pdf.stem}-*.png"):
        old.unlink()
    subprocess.run(
        [pdftoppm, "-r", str(dpi), "-png", str(pdf), str(out / pdf.stem)], check=True, timeout=300
    )
    pages = sorted(
        (p for p in out.glob(f"{pdf.stem}-*.png") if p.stem.rsplit("-", 1)[1].isdigit()),
        key=lambda p: int(p.stem.rsplit("-", 1)[1]),
    )
    if grey:
        from PIL import Image

        greys = []
        for page in pages:
            target = page.with_name(f"{page.stem}-grey.png")
            with Image.open(page) as im:
                im.convert("L").save(target)
            greys.append(target)
        return pages + greys
    return pages


def contact_sheet(pages: list[Path], target: Path, columns: int = 4) -> None:
    from PIL import Image

    images = [Image.open(p).convert("RGB") for p in pages]
    if not images:
        return
    w = max(i.width for i in images)
    h = max(i.height for i in images)
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * (w + 8), rows * (h + 8)), "#8a8a8a")
    for k, image in enumerate(images):
        sheet.paste(image, ((k % columns) * (w + 8), (k // columns) * (h + 8)))
    sheet.save(target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("docx", nargs="*", type=Path, help="DOCX files to preview")
    parser.add_argument("--samples", action="store_true", help="the four template samples")
    parser.add_argument(
        "--stress",
        nargs="?",
        const=STRESS_DEFAULT,
        type=float,
        help=f"lengthen the samples' prose (default factor {STRESS_DEFAULT})",
    )
    parser.add_argument("--grey", action="store_true", help="also write greyscale pages")
    parser.add_argument("--dpi", type=int, default=60)
    parser.add_argument("--out", type=Path, default=REPO / "tmp" / "report-preview")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    files = list(args.docx)
    if args.samples:
        files += write_samples(args.out, args.stress)
    if not files:
        parser.error("name a DOCX file or pass --samples")

    failed = False
    for docx in files:
        problems = lint(docx)
        for problem in problems:
            print(f"LINT {docx.name}: {problem}")
        failed |= bool(problems)
        try:
            pdf = to_pdf(docx, args.out)
            pages = to_pngs(pdf, args.out, args.dpi, args.grey)
        except (subprocess.SubprocessError, RuntimeError) as exc:
            print(f"FAIL {docx.name}: {exc}")
            failed = True
            continue
        colour = [p for p in pages if not p.stem.endswith("-grey")]
        contact_sheet(colour, args.out / f"{docx.stem}-sheet.png")
        if args.grey:
            greys = [p for p in pages if p.stem.endswith("-grey")]
            contact_sheet(greys, args.out / f"{docx.stem}-sheet-grey.png")
        print(f"ok   {docx.name}: {len(colour)} pages -> {args.out / (docx.stem + '-sheet.png')}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
