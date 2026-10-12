"""Keep each population version's audience factor catalogue with it

panel-grounded-respondents 6b. The audience step's factor editor draws from a catalogue of
the dimensions a study may filter by: each factor's kind, range or most frequent values, and
the field policy's answer. 18.6.6 computed it from the loaded panel on every request; AIA
computes it once per version (``population_ops record-catalogue``) and keeps it here,
insert-once, so the API serves it without reading a respondent row. Nothing existing
changes; a version has no row until the command stores it.

Revision ID: a2c4e6f8b0d3
Revises: f0b2d4e6a8c1
Created: 2026-10-12 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "a2c4e6f8b0d3"
down_revision: str | None = "f0b2d4e6a8c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "population_version_audience_catalogues",
        sa.Column("version_id", sa.String(length=128), nullable=False),
        sa.Column("catalogue_version", sa.String(length=128), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["population_dataset_versions.version_id"],
            name=op.f(
                "fk_population_version_audience_catalogues_version_id_population_dataset_versions"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "version_id",
            "catalogue_version",
            name=op.f("pk_population_version_audience_catalogues"),
        ),
    )


def downgrade() -> None:
    op.drop_table("population_version_audience_catalogues")
