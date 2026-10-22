"""Q69 (a), the owner, 2026-10-22: the Lead's study notes stay out of the draft report.

The import contract "no report path reads the Lead's notes (Q69)" keeps the Lead's repositories
out of every report module; this keeps the Lead's tables out of them too, by name, since a module
may import ``tables`` for its own rows and query another's.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "packages/aia_core/src/aia_core"

#: Every module that composes, stores, renders or approves a report.
REPORT_MODULES = (
    *sorted((CORE / "application").glob("*report*.py")),
    *sorted((CORE / "domain/report").rglob("*.py")),
    *sorted((CORE / "infrastructure/report_docx").rglob("*.py")),
    ROOT / "apps/executors/src/aia_executors/report.py",
)
#: The Lead's turns, its files and notes, and their tables.
LEAD_NAMES = re.compile(
    r"\b(StudyLeadTurnRow|ResearcherLeadRow|ResearcherLeadRevisionRow|ResearcherLeadMemoryRow"
    r"|study_lead_turns|researcher_leads|researcher_lead_revisions|researcher_lead_memories)\b"
)


def test_no_report_module_names_the_leads_notes() -> None:
    assert len(REPORT_MODULES) > 20  # the list found the report's modules, not none
    named = {
        str(path.relative_to(ROOT)): sorted(set(LEAD_NAMES.findall(path.read_text())))
        for path in REPORT_MODULES
        if LEAD_NAMES.search(path.read_text())
    }
    assert named == {}
