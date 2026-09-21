"""Alembic environment.

The database URL always comes from ``DATABASE_URL`` so that credentials are never
committed and so that the same migration set runs against every environment.

``target_metadata`` points at the single declarative base, which makes
``alembic revision --autogenerate`` and the CI drift check work from one source of
truth.
"""

from __future__ import annotations

from logging.config import fileConfig

from aia_core.infrastructure.db import resolve_database_url
from aia_core.infrastructure.tables import Base
from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", resolve_database_url())

target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    """Render our portable JSON column cleanly in generated migrations.

    Alembic's default rendering of ``JSON().with_variant(JSONB(), "postgresql")``
    emits ``postgresql.JSONB(astext_type=Text())`` without importing ``Text``,
    producing a migration that raises ``NameError`` on first run. Rendering the
    variant ourselves keeps JSONB on PostgreSQL and JSON elsewhere, and needs only
    the imports Alembic already adds.
    """
    if type_ == "type" and obj.__class__.__name__ == "JSON":
        autogen_context.imports.add("from sqlalchemy.dialects import postgresql")
        return 'sa.JSON().with_variant(postgresql.JSONB(), "postgresql")'
    return False


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting, for review or manual application."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_item=render_item,
            # Type and default comparison are on so that a drifted column is
            # reported by the CI autogenerate check rather than silently ignored.
            compare_type=True,
            compare_server_default=True,
            # SQLite cannot ALTER most things in place; batch mode rewrites the
            # table instead. Harmless on PostgreSQL.
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
