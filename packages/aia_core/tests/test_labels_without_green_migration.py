"""Migration 5cc62edde24e: green leaves the label palette, every green label becomes teal, the
change is audited once per client, and the downgrade puts back exactly those labels
(client-pages-redesign CPR16; the product owner's Q2, 2026-10-27)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

REPO = Path(__file__).resolve().parents[3]
MIGRATION = REPO / "migrations/versions/20261029_5cc62edde24e_labels_without_green.py"

_AUDIT = sa.table(
    "access_audit",
    sa.column("event_id"),
    sa.column("organization_id"),
    sa.column("client_id"),
    sa.column("actor_id"),
    sa.column("action"),
    sa.column("reason"),
    sa.column("payload", sa.JSON),
    sa.column("created_at", sa.DateTime(timezone=True)),
)


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("labels_without_green", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema() -> sa.Engine:
    engine = create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table(
        "client_knowledge_labels",
        metadata,
        sa.Column("label_id", sa.String, primary_key=True),
        sa.Column("organization_id", sa.String, nullable=False),
        sa.Column("client_id", sa.String, nullable=False),
        sa.Column("colour", sa.String, nullable=False),
        sa.CheckConstraint(
            "colour in ('BLUE','TEAL','GREEN','ORANGE','VIOLET','SLATE')",
            name="ck_client_knowledge_labels_knowledge_label_colour_known",
        ),
    )
    sa.Table(
        "access_audit",
        metadata,
        sa.Column("event_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.String, nullable=False),
        sa.Column("client_id", sa.String),
        sa.Column("actor_id", sa.String),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("reason", sa.String, nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO client_knowledge_labels VALUES "
                "('KNL-1', 'ORG-1', 'CLI-a', 'GREEN'), ('KNL-2', 'ORG-1', 'CLI-a', 'BLUE'), "
                "('KNL-3', 'ORG-1', 'CLI-b', 'GREEN'), ('KNL-4', 'ORG-1', 'CLI-a', 'TEAL'), "
                "('KNL-5', 'ORG-2', 'CLI-c', 'GREEN')"
            )
        )
    return engine


def _run(engine: sa.Engine, step: str) -> None:
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        getattr(_migration(), step)()


def _colours(engine: sa.Engine) -> dict[str, str]:
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT label_id, colour FROM client_knowledge_labels"))
        return {str(label_id): str(colour) for label_id, colour in rows}


def _recoloured(engine: sa.Engine) -> list[tuple[object, ...]]:
    with engine.connect() as connection:
        rows = connection.execute(
            sa.select(
                _AUDIT.c.organization_id,
                _AUDIT.c.client_id,
                _AUDIT.c.actor_id,
                _AUDIT.c.reason,
                _AUDIT.c.payload,
            )
            .where(_AUDIT.c.action == "CLIENT_KNOWLEDGE_LABELS_RECOLOURED")
            .order_by(_AUDIT.c.event_id)
        )
        return [tuple(r) for r in rows]


def _recolour(label_ids: list[str]) -> dict[str, object]:
    return {"from": "GREEN", "to": "TEAL", "label_ids": label_ids}


def test_every_green_label_turns_teal_audited_once_per_client_and_green_is_refused() -> None:
    engine = _schema()
    _run(engine, "upgrade")
    assert _colours(engine) == {
        "KNL-1": "TEAL",
        "KNL-2": "BLUE",
        "KNL-3": "TEAL",
        "KNL-4": "TEAL",
        "KNL-5": "TEAL",
    }
    # A system change: no actor and no reason, each client named as its label audits are.
    assert _recoloured(engine) == [
        ("ORG-1", "CLI-a", None, "", _recolour(["KNL-1"])),
        ("ORG-1", "CLI-b", None, "", _recolour(["KNL-3"])),
        ("ORG-2", "CLI-c", None, "", _recolour(["KNL-5"])),
    ]
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as connection:
        connection.execute(
            text("INSERT INTO client_knowledge_labels VALUES ('KNL-9', 'ORG-1', 'CLI-a', 'GREEN')")
        )


def test_the_downgrade_puts_back_only_what_it_recoloured_and_no_person_changed_since() -> None:
    engine = _schema()
    _run(engine, "upgrade")
    # A person changes KNL-3 after the recolouring (keeping teal): their choice stands.
    with engine.begin() as connection:
        connection.execute(
            _AUDIT.insert().values(
                organization_id="ORG-1",
                client_id="CLI-b",
                action="CLIENT_KNOWLEDGE_LABEL_CHANGED",
                reason="",
                payload={"label_id": "KNL-3", "from": {"colour": "TEAL"}, "to": {"colour": "TEAL"}},
                created_at=sa.func.current_timestamp(),
            )
        )
    _run(engine, "downgrade")
    # KNL-4 was teal before the migration and stays teal.
    assert _colours(engine) == {
        "KNL-1": "GREEN",
        "KNL-2": "BLUE",
        "KNL-3": "TEAL",
        "KNL-4": "TEAL",
        "KNL-5": "GREEN",
    }
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO client_knowledge_labels VALUES ('KNL-9', 'ORG-1', 'CLI-a', 'GREEN')")
        )


def test_a_second_cycle_undoes_only_its_own_upgrade() -> None:
    engine = _schema()
    _run(engine, "upgrade")
    _run(engine, "downgrade")
    # Between the cycles KNL-1 is made blue: the second upgrade does not recolour it.
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE client_knowledge_labels SET colour = 'BLUE' WHERE label_id = 'KNL-1'")
        )
    _run(engine, "upgrade")
    # Made teal by hand after the second upgrade; the first cycle's row still names it.
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE client_knowledge_labels SET colour = 'TEAL' WHERE label_id = 'KNL-1'")
        )
    _run(engine, "downgrade")
    assert _colours(engine)["KNL-1"] == "TEAL"
    assert _colours(engine)["KNL-5"] == "GREEN"
