"""Q69 (a), the owner, 2026-10-22: the Lead's study notes stay out of the draft report.

The import contract "no report path reads the Lead's notes (Q69)" (root ``pyproject.toml``) keeps
the Lead's modules out of every report module. This holds the contract's list to every module that
composes, stores, renders or approves a report, and refuses in them by name what an import contract
cannot see: the Lead's tables (a module may import ``tables`` for its own rows) and the Lead's turn
artifact on the design project (every report module can list artifacts).
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "packages/aia_core/src/aia_core"
EXECUTORS = ROOT / "apps/executors/src/aia_executors"

#: Every module that composes, stores, renders or approves a report.
REPORT_FILES = (
    *sorted((CORE / "application").glob("*report*.py")),
    *sorted((CORE / "domain/report").rglob("*.py")),
    *sorted((CORE / "infrastructure/report_docx").rglob("*.py")),
    CORE / "infrastructure/report_pdf.py",
    *sorted(EXECUTORS.glob("*report*.py")),
)
#: The Lead's turns, files and notes: their tables, rows and repositories, and its turn artifact.
LEAD_NAMES = re.compile(
    r"\b(StudyLeadTurnRow|ResearcherLeadRow|ResearcherLeadRevisionRow|ResearcherLeadMemoryRow"
    r"|study_lead_turns|researcher_leads|researcher_lead_revisions|researcher_lead_memories"
    r"|StudyLeadRepository|ResearcherLeadRepository|RESEARCH_LEAD_TURN|research_lead_turn)\b"
)


def _module(path: Path) -> str:
    base = CORE.parent if path.is_relative_to(CORE) else EXECUTORS.parent
    return ".".join(path.relative_to(base).with_suffix("").parts).removesuffix(".__init__")


def _contract_sources() -> list[str]:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    (contract,) = (c for c in config["tool"]["importlinter"]["contracts"] if "(Q69)" in c["name"])
    return list(contract["source_modules"])


def test_the_import_contract_covers_every_report_module() -> None:
    sources = _contract_sources()
    uncovered = [
        m
        for m in map(_module, REPORT_FILES)
        if not any(m == s or m.startswith(s + ".") for s in sources)
    ]
    assert uncovered == []


def test_no_report_module_names_the_leads_notes() -> None:
    assert len(REPORT_FILES) > 20  # the list found the report's modules, not none
    named = {
        str(path.relative_to(ROOT)): sorted(set(found))
        for path in REPORT_FILES
        if (found := LEAD_NAMES.findall(path.read_text()))
    }
    assert named == {}
