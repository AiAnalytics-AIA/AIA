"""Migration bd44c92f1fb7 freezes every report version approved before approving froze.

Approving a run's report freezes it since research-integrity-report chunk 13 (D2); one approved
by the previous release stayed deletable by ``invalidate_stage`` and ``delete`` (Codex review on
PR #478). The migration's upgrade runs here against the real ``project_artifacts`` table.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from aia_core.application.report_approval import REPORT_ARTIFACT_TYPES
from aia_core.infrastructure.tables import ProjectArtifactRow

REPO = Path(__file__).resolve().parents[3]
MIGRATION = REPO / "migrations/versions/20261018_bd44c92f1fb7_freeze_approved_reports.py"


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("freeze_approved_reports", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    artifact_id: str, artifact_type: str, *, approved: bool, frozen: bool
) -> ProjectArtifactRow:
    return ProjectArtifactRow(
        artifact_id=artifact_id,
        project_id="PRJ-1",
        revision=1,
        stage_type="REPORT",
        artifact_type=artifact_type,
        storage_key=f"k/{artifact_id}",
        sha256="0" * 64,
        is_approved=approved,
        is_frozen=frozen,
    )


def test_the_migration_names_the_reports_a_person_approves() -> None:
    """Written out in the migration, never imported: it must still be the approvable set."""
    named = _migration()._REPORTS.strip("()").replace("'", "").split(",")
    assert set(named) == set(REPORT_ARTIFACT_TYPES)


def test_an_approved_report_is_frozen_and_nothing_else_moves() -> None:
    engine = create_engine("sqlite://")
    ProjectArtifactRow.metadata.create_all(engine, tables=[ProjectArtifactRow.__table__])
    rows = [
        _row("ART-internal", "research_internal_docx", approved=True, frozen=False),
        _row("ART-literature", "research_internal_docx_with_research", approved=True, frozen=False),
        _row("ART-client", "research_client_docx", approved=True, frozen=False),
        _row("ART-draft", "research_internal_docx", approved=False, frozen=False),
        _row("ART-other", "research_sociomapping_docx", approved=True, frozen=False),
        _row("ART-done", "research_client_docx", approved=True, frozen=True),
    ]
    with Session(engine) as session:
        session.add_all(rows)
        session.commit()
    with (
        engine.begin() as connection,
        Operations.context(MigrationContext.configure(connection)),
    ):
        _migration().upgrade()
    with Session(engine) as session:
        frozen = {
            row.artifact_id: row.is_frozen for row in session.scalars(select(ProjectArtifactRow))
        }
    assert frozen == {
        "ART-internal": True,
        "ART-literature": True,
        "ART-client": True,
        "ART-draft": False,
        "ART-other": False,
        "ART-done": True,
    }
