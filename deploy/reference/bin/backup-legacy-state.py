"""Stream consistent SQLite copies as a ZIP; run inside the legacy container.

The host feeds this source to the running image, including an older image during
pre-deploy backup. No code or credentials are installed in the reference tree.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import BinaryIO


def write_backup(data_dir: Path, output: BinaryIO) -> list[str]:
    """Back up live databases with SQLite's API, including committed WAL data."""
    if not (data_dir / "project_store.sqlite").is_file():
        raise FileNotFoundError("legacy working project database is missing")
    databases = sorted(data_dir.glob("*.sqlite"))
    with tempfile.TemporaryDirectory(prefix="aia-state-backup-") as temporary:
        folder = Path(temporary)
        archive = folder / "state.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in databases:
                copy = folder / path.name
                source = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
                destination = sqlite3.connect(copy)
                try:
                    source.backup(destination)
                finally:
                    destination.close()
                    source.close()
                bundle.write(copy, arcname=path.name)
        with archive.open("rb") as stream:
            shutil.copyfileobj(stream, output)
    return [p.name for p in databases]


if __name__ == "__main__":
    write_backup(Path("/app/data"), sys.stdout.buffer)
