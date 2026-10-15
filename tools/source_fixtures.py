# ruff: noqa: E501, RUF001  -- the fictional documents below are content, kept as written
"""Fictional documents for the client-source readers' tests (lifecycle K2b).

    python tools/source_fixtures.py write [name …]  # write and convert (needs soffice); all if none
    python tools/source_fixtures.py verify   # the files on disk match index.json

The content is invented: a fictional brief about a morning drink, with Czech text (so a
reader that drops accents fails), a heading, a table and a hyperlink (a field in a Word
97 file, whose code a reader must not show as text). LibreOffice converts one flat
OpenDocument text into ``.doc``, ``.odt`` and ``.docx``, and one flat presentation into
``.pptx``; each output is pinned by its SHA-256 in ``index.json``. A converter of another
version writes other bytes, so ``write`` is run by hand and the new hashes are committed
with the files: a fixture never changes silently.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "packages/aia_core/tests/fixtures/client_sources"

TEXT = """<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:xlink="http://www.w3.org/1999/xlink"
 office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.text">
 <office:body><office:text>
  <text:h text:outline-level="1">Zadání výzkumu: fiktivní ranní nápoj</text:h>
  <text:p>Cílová skupina: lidé 18–65 let, kteří pijí kávu alespoň třikrát týdně.</text:p>
  <text:p/>
  <text:p>Plain ASCII paragraph for the compressed path.</text:p>
  <table:table table:name="Podily">
   <table:table-column table:number-columns-repeated="2"/>
   <table:table-row>
    <table:table-cell><text:p>Značka</text:p></table:table-cell>
    <table:table-cell><text:p>Podíl</text:p></table:table-cell>
   </table:table-row>
   <table:table-row>
    <table:table-cell><text:p>Ranní Ň</text:p></table:table-cell>
    <table:table-cell><text:p>12 %</text:p></table:table-cell>
   </table:table-row>
  </table:table>
  <text:p>Zdroj: <text:a xlink:type="simple" xlink:href="https://example.org/zdroj">fiktivní studie</text:a> z roku 2026.</text:p>
 </office:text></office:body>
</office:document>
"""

SLIDES = """<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
 xmlns:presentation="urn:oasis:names:tc:opendocument:xmlns:presentation:1.0"
 office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.presentation">
 <office:body><office:presentation>
  <draw:page draw:name="Úvod">
   <draw:frame svg:x="1cm" svg:y="1cm" svg:width="20cm" svg:height="3cm">
    <draw:text-box><text:p>Fiktivní ranní nápoj</text:p></draw:text-box>
   </draw:frame>
   <draw:frame svg:x="1cm" svg:y="5cm" svg:width="20cm" svg:height="6cm">
    <draw:text-box><text:p>Cíl: porozumět ranním návykům.</text:p><text:p>Metoda: online panel.</text:p></draw:text-box>
   </draw:frame>
  </draw:page>
  <draw:page draw:name="Prázdný"/>
  <draw:page draw:name="Závěr">
   <draw:frame svg:x="1cm" svg:y="1cm" svg:width="20cm" svg:height="3cm">
    <draw:text-box><text:p>Doporučení: testovat dvě příchutě.</text:p></draw:text-box>
   </draw:frame>
  </draw:page>
 </office:presentation></office:body>
</office:document>
"""

# A fictional survey export: typed numbers and dates, a column of fictional e-mails (the
# personal-data detector must flag and mask it), and a second sheet of notes.
SHEET = """<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:number="urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0"
 office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.spreadsheet">
 <office:automatic-styles>
  <number:date-style style:name="Ndate">
   <number:year number:style="long"/><number:text>-</number:text>
   <number:month number:style="long"/><number:text>-</number:text>
   <number:day number:style="long"/>
  </number:date-style>
  <style:style style:name="Cdate" style:family="table-cell" style:data-style-name="Ndate"/>
 </office:automatic-styles>
 <office:body><office:spreadsheet>
  <table:table table:name="Odpovědi">
   <table:table-row>
    <table:table-cell office:value-type="string"><text:p>ID</text:p></table:table-cell>
    <table:table-cell office:value-type="string"><text:p>Věk</text:p></table:table-cell>
    <table:table-cell office:value-type="string"><text:p>Kraj</text:p></table:table-cell>
    <table:table-cell office:value-type="string"><text:p>Spokojenost</text:p></table:table-cell>
    <table:table-cell office:value-type="string"><text:p>Datum</text:p></table:table-cell>
    <table:table-cell office:value-type="string"><text:p>E-mail</text:p></table:table-cell>
   </table:table-row>
ROWS
  </table:table>
  <table:table table:name="Poznámky">
   <table:table-row>
    <table:table-cell office:value-type="string"><text:p>Fiktivní export, jen pro testy.</text:p></table:table-cell>
   </table:table-row>
  </table:table>
 </office:spreadsheet></office:body>
</office:document>
"""
RESPONDENTS = [
    (1, 34, "Praha", 4.5, "2026-09-01", "jana.fikt@example.test"),
    (2, 51, "Jihomoravský", 3, "2026-09-02", "petr.fikt@example.test"),
    (3, 27, "Praha", 5, "2026-09-02", "eva.fikt@example.test"),
    (4, 63, "Olomoucký", 2.5, "2026-09-03", "adam.fikt@example.test"),
]


def _sheet() -> str:
    cell = "    <table:table-cell office:value-type=\"{kind}\" {attr}><text:p>{shown}</text:p></table:table-cell>"
    rows = []
    for rid, age, region, score, day, mail in RESPONDENTS:
        cells = [
            cell.format(kind="float", attr=f'office:value="{rid}"', shown=rid),
            cell.format(kind="float", attr=f'office:value="{age}"', shown=age),
            cell.format(kind="string", attr="", shown=region),
            cell.format(kind="float", attr=f'office:value="{score}"', shown=score),
            cell.format(
                kind="date", attr=f'table:style-name="Cdate" office:date-value="{day}"', shown=day
            ),
            cell.format(kind="string", attr="", shown=mail),
        ]
        rows.append("   <table:table-row>\n" + "\n".join(cells) + "\n   </table:table-row>")
    return SHEET.replace("ROWS", "\n".join(rows))


# A Czech export as a spreadsheet writes it: UTF-8 with a byte-order mark, semicolons, a
# decimal comma, and a phone column of fictional numbers.
CSV = (
    "\ufeffID;Věk;Kraj;Útrata;Telefon\r\n"
    "1;34;Praha;1 250,50;+420 600 000 001\r\n"
    "2;51;Jihomoravský;980;+420 600 000 002\r\n"
    "3;27;Praha;2 310,00;+420 600 000 003\r\n"
)

OUTPUTS = {
    "zadani.doc": "doc",
    "zadani.odt": "odt",
    "zadani.docx": "docx",
    "prezentace.pptx": "pptx",
    "odpovedi.ods": "ods",
    "odpovedi.xlsx": "xlsx",
    "odpovedi.xls": "xls",
    "utrata.csv": "csv",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _convert(source: Path, fmt: str, target: Path) -> None:
    with tempfile.TemporaryDirectory() as work:
        subprocess.run(
            [
                "soffice",
                f"-env:UserInstallation=file://{work}/profile",
                "--headless",
                "--convert-to",
                fmt,
                "--outdir",
                work,
                str(source),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
        shutil.move(str(Path(work) / f"{source.stem}.{fmt}"), target)


def write(names: list[str]) -> None:
    """Write the named outputs (all, if none are named) and pin their new hashes.

    A converter run gives new bytes, so naming only the new fixtures leaves the pinned
    ones as they were.
    """
    unknown = sorted(set(names) - set(OUTPUTS))
    if unknown:
        sys.exit(f"unknown fixtures: {unknown}")
    wanted = names or sorted(OUTPUTS)
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as work:
        text = Path(work) / "zadani.fodt"
        text.write_text(TEXT, encoding="utf-8")
        slides = Path(work) / "prezentace.fodp"
        slides.write_text(SLIDES, encoding="utf-8")
        sheet = Path(work) / "odpovedi.fods"
        sheet.write_text(_sheet(), encoding="utf-8")
        for name in wanted:
            fmt = OUTPUTS[name]
            if fmt == "csv":
                (OUT / name).write_bytes(CSV.encode("utf-8"))
                continue
            source = {"pptx": slides, "ods": sheet, "xlsx": sheet, "xls": sheet}.get(fmt, text)
            _convert(source, fmt, OUT / name)
    index_path = OUT / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    index.update({name: _sha(OUT / name) for name in wanted})
    index = dict(sorted(index.items()))
    (OUT / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(index, indent=2))


def verify() -> int:
    index = json.loads((OUT / "index.json").read_text(encoding="utf-8"))
    bad = [name for name, sha in index.items() if _sha(OUT / name) != sha]
    for name in bad:
        print(f"changed: {name}")
    return 1 if bad else 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "write":
        write(sys.argv[2:])
    elif command == "verify":
        sys.exit(verify())
    else:
        sys.exit(__doc__)
