"""a report version approved before approving froze is frozen

Revision ID: bd44c92f1fb7
Revises: d2f4a6c8e0b3
Created: 2026-10-18

Approving a run's report now freezes the version (``application.report_approval``; plan
``research-integrity-report`` chunk 13, D2), so ``invalidate_stage`` and ``delete``, which spare
only a frozen artifact, can no longer remove a signed version. A report approved by the previous
release is approved and not frozen. This freezes every one of them: the internal report, the
report with literature and the client report, the three types a person approves.

Data only. Downgrade leaves the rows frozen: freezing is one-way
(``ArtifactRepository.freeze``), and a downgrade cannot tell a version this froze from one an
approval froze.
"""

from __future__ import annotations

from alembic import op

revision: str = "bd44c92f1fb7"
down_revision: str | None = "d2f4a6c8e0b3"
branch_labels = None
depends_on = None

# report_approval.REPORT_ARTIFACT_TYPES as of this revision, written out: a migration never
# imports application code, whose names may change after it.
_REPORTS = (
    "('research_internal_docx','research_internal_docx_with_research','research_client_docx')"
)


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE project_artifacts
           SET is_frozen = true
         WHERE is_approved
           AND NOT is_frozen
           AND artifact_type IN {_REPORTS}
        """
    )


def downgrade() -> None:
    pass
