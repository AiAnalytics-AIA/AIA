"""Raw open answers stay inside AIA (artifact-results RES5; the product owner, Q52 a, 2026-10-21).

The aggregate stores an open question's answers as ``verbatimy``; Výsledky shows up to five of
them, labelled as data, not admitted evidence. Nothing else may read them: no analysis prompt,
no report (internal or client), no export. This guard fails the moment a second Python module
names the key, so a new reader is a decision made in review, not an accident.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCES = (
    ROOT / "packages" / "aia_core" / "src",
    ROOT / "apps" / "api" / "src",
    ROOT / "apps" / "worker" / "src",
    ROOT / "apps" / "executors" / "src",
)
WRITER = ROOT / "packages" / "aia_core" / "src" / "aia_core" / "domain" / "research_aggregate.py"


def test_only_the_aggregate_names_the_raw_open_answers() -> None:
    naming = sorted(
        path.relative_to(ROOT).as_posix()
        for source in SOURCES
        for path in source.rglob("*.py")
        if "verbatimy" in path.read_text(encoding="utf-8")
    )
    assert naming == [WRITER.relative_to(ROOT).as_posix()]
