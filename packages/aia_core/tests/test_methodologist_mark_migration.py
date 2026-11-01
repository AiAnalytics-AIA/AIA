"""Migration a1c3e5f7b9d1 adds the Metodik mark and gives it, at ship, only to the product
owner's memberships (the owner's answer, 2026-10-22; settings-backends SB1)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

REPO = Path(__file__).resolve().parents[3]
MIGRATION = REPO / "migrations/versions/20261022_a1c3e5f7b9d1_methodologist_mark.py"


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("methodologist_mark", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_only_the_product_owners_memberships_are_marked() -> None:
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (user_id TEXT PRIMARY KEY, email TEXT)"))
        connection.execute(
            text(
                "CREATE TABLE organization_members "
                "(organization_id TEXT, user_id TEXT, role TEXT, "
                "PRIMARY KEY (organization_id, user_id))"
            )
        )
        connection.execute(
            text(
                "INSERT INTO users VALUES ('USR-n', 'NigelBlount@art-chain.io'), "
                "('USR-o', 'owner@art-chain.io')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO organization_members VALUES ('ORG-1', 'USR-n', 'OWNER'), "
                "('ORG-2', 'USR-n', 'MEMBER'), ('ORG-1', 'USR-o', 'OWNER')"
            )
        )
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        _migration().upgrade()
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT organization_id, user_id, methodologist FROM organization_members")
        ).all()
    assert {(o, u): bool(m) for o, u, m in rows} == {
        ("ORG-1", "USR-n"): True,
        ("ORG-2", "USR-n"): True,
        ("ORG-1", "USR-o"): False,
    }
