# ruff: noqa: E501, RUF001  -- the fictional documents below are content, kept as written
"""Fictional documents for the client-source readers' tests (lifecycle K2b).

    python tools/source_fixtures.py write    # write the inputs and convert them (needs soffice)
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

OUTPUTS = {
    "zadani.doc": "doc",
    "zadani.odt": "odt",
    "zadani.docx": "docx",
    "prezentace.pptx": "pptx",
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


def write() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as work:
        text = Path(work) / "zadani.fodt"
        text.write_text(TEXT, encoding="utf-8")
        slides = Path(work) / "prezentace.fodp"
        slides.write_text(SLIDES, encoding="utf-8")
        for name, fmt in OUTPUTS.items():
            _convert(slides if fmt == "pptx" else text, fmt, OUT / name)
    index = {name: _sha(OUT / name) for name in sorted(OUTPUTS)}
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
        write()
    elif command == "verify":
        sys.exit(verify())
    else:
        sys.exit(__doc__)
