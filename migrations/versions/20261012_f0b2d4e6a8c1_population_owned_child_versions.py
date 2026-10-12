"""Let a population version belong to one organization, as a materialized child

Population-operations P4c. A materialized dimension becomes an owned child
``DatasetVersion`` (P4a): its base plus the added fields, belonging to the organization
and client it was materialized for. ``population_dataset_versions`` gains the owner and
the hash of the contract extension declaring the added fields, all set or all NULL, and
an owned version always has a parent. ``population_contract_extensions`` keeps each
extension, insert-once.

The two whole-table unique keys become partial: the same bytes and the same label stay
unique among the shared versions and within one owner's, so two clients' identical
children are two versions (their ids differ by an owner digest, ``owned_version_id``).
Every existing row is shared: it gets NULL owner columns and keeps both guarantees.

Revision ID: f0b2d4e6a8c1
Revises: e8a0c2e4f6b8
Created: 2026-10-12 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f0b2d4e6a8c1"
down_revision: str | None = "e8a0c2e4f6b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "population_contract_extensions",
        sa.Column("extension_sha256", sa.String(length=64), nullable=False),
        sa.Column("contract", sa.String(length=64), nullable=False),
        sa.Column(
            "payload", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("extension_sha256", name=op.f("pk_population_contract_extensions")),
    )
    op.add_column(
        "population_dataset_versions",
        sa.Column("owner_organization_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "population_dataset_versions",
        sa.Column("owner_client_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "population_dataset_versions",
        sa.Column("extension_sha256", sa.String(length=64), nullable=True),
    )
    op.drop_constraint(
        op.f("population_version_label"), "population_dataset_versions", type_="unique"
    )
    op.drop_constraint(
        op.f("uq_population_dataset_versions_content_sha256"),
        "population_dataset_versions",
        type_="unique",
    )
    op.create_index(
        "ix_population_versions_owner",
        "population_dataset_versions",
        ["owner_organization_id", "dataset_id"],
        unique=False,
    )
    op.create_index(
        "uq_population_version_owned_content",
        "population_dataset_versions",
        ["owner_client_id", "content_sha256"],
        unique=True,
        postgresql_where=sa.text("owner_client_id IS NOT NULL"),
        sqlite_where=sa.text("owner_client_id IS NOT NULL"),
    )
    op.create_index(
        "uq_population_version_owned_label",
        "population_dataset_versions",
        ["owner_client_id", "dataset_id", "label"],
        unique=True,
        postgresql_where=sa.text("owner_client_id IS NOT NULL"),
        sqlite_where=sa.text("owner_client_id IS NOT NULL"),
    )
    op.create_index(
        "uq_population_version_shared_content",
        "population_dataset_versions",
        ["content_sha256"],
        unique=True,
        postgresql_where=sa.text("owner_client_id IS NULL"),
        sqlite_where=sa.text("owner_client_id IS NULL"),
    )
    op.create_index(
        "uq_population_version_shared_label",
        "population_dataset_versions",
        ["dataset_id", "label"],
        unique=True,
        postgresql_where=sa.text("owner_client_id IS NULL"),
        sqlite_where=sa.text("owner_client_id IS NULL"),
    )
    op.create_foreign_key(
        op.f("fk_population_dataset_versions_owner_organization_id_organizations"),
        "population_dataset_versions",
        "organizations",
        ["owner_organization_id"],
        ["organization_id"],
    )
    op.create_foreign_key(
        op.f("fk_population_dataset_versions_owner_client_id_clients"),
        "population_dataset_versions",
        "clients",
        ["owner_client_id"],
        ["client_id"],
    )
    op.create_foreign_key(
        op.f("fk_population_dataset_versions_extension_sha256_population_contract_extensions"),
        "population_dataset_versions",
        "population_contract_extensions",
        ["extension_sha256"],
        ["extension_sha256"],
    )
    op.create_check_constraint(
        op.f("ck_population_dataset_versions_population_version_owned_child"),
        "population_dataset_versions",
        "(owner_organization_id IS NULL AND owner_client_id IS NULL"
        " AND extension_sha256 IS NULL)"
        " OR (owner_organization_id IS NOT NULL AND owner_client_id IS NOT NULL"
        " AND extension_sha256 IS NOT NULL AND parent_version_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_population_dataset_versions_population_version_owned_child"),
        "population_dataset_versions",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_population_dataset_versions_extension_sha256_population_contract_extensions"),
        "population_dataset_versions",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_population_dataset_versions_owner_client_id_clients"),
        "population_dataset_versions",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_population_dataset_versions_owner_organization_id_organizations"),
        "population_dataset_versions",
        type_="foreignkey",
    )
    op.drop_index(
        "uq_population_version_shared_label",
        table_name="population_dataset_versions",
        postgresql_where=sa.text("owner_client_id IS NULL"),
        sqlite_where=sa.text("owner_client_id IS NULL"),
    )
    op.drop_index(
        "uq_population_version_shared_content",
        table_name="population_dataset_versions",
        postgresql_where=sa.text("owner_client_id IS NULL"),
        sqlite_where=sa.text("owner_client_id IS NULL"),
    )
    op.drop_index(
        "uq_population_version_owned_label",
        table_name="population_dataset_versions",
        postgresql_where=sa.text("owner_client_id IS NOT NULL"),
        sqlite_where=sa.text("owner_client_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_population_version_owned_content",
        table_name="population_dataset_versions",
        postgresql_where=sa.text("owner_client_id IS NOT NULL"),
        sqlite_where=sa.text("owner_client_id IS NOT NULL"),
    )
    op.drop_index("ix_population_versions_owner", table_name="population_dataset_versions")
    op.create_unique_constraint(
        op.f("uq_population_dataset_versions_content_sha256"),
        "population_dataset_versions",
        ["content_sha256"],
        postgresql_nulls_not_distinct=False,
    )
    op.create_unique_constraint(
        op.f("population_version_label"),
        "population_dataset_versions",
        ["dataset_id", "label"],
        postgresql_nulls_not_distinct=False,
    )
    op.drop_column("population_dataset_versions", "extension_sha256")
    op.drop_column("population_dataset_versions", "owner_client_id")
    op.drop_column("population_dataset_versions", "owner_organization_id")
    op.drop_table("population_contract_extensions")
