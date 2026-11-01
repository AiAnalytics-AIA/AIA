"""a person's message to the Lead carries files (lead-orchestration LO18a)

Revision ID: 2bec066f109f
Revises: c3e5a7b9d1f2
Created: 2026-10-28

``study_lead_turns.files``: nullable, set on insert and never after. Each entry names a client's
source a person attached to their message, by its id and the SHA-256 of its bytes and of its
reading as attached; the file itself is the client's source. Only a person's message carries files.
No row before carries any, so nothing is backfilled. The downgrade refuses while a turn carries
files, rather than forget what a message was sent with.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2bec066f109f"
down_revision: str | None = "c3e5a7b9d1f2"
branch_labels = None
depends_on = None

_CHECK = "ck_study_lead_turns_study_lead_turn_files_are_a_messages"


def upgrade() -> None:
    with op.batch_alter_table("study_lead_turns") as batch:
        batch.add_column(
            sa.Column(
                "files", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True
            )
        )
        batch.create_check_constraint(
            op.f(_CHECK), "files IS NULL OR (actor = 'person' AND kind = 'message')"
        )


def downgrade() -> None:
    carried = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM study_lead_turns WHERE files IS NOT NULL")
    )
    if carried:
        raise RuntimeError(f"{carried} Lead message(s) carry files; refusing to drop them")
    with op.batch_alter_table("study_lead_turns") as batch:
        batch.drop_constraint(op.f(_CHECK), type_="check")
        batch.drop_column("files")
