"""Green leaves the label palette: every stored green label becomes teal

Plan client-pages-redesign CPR16 (Q2, the product owner, 27 Oct 2026): green belongs to the
version in force alone, so a knowledge label may no longer be green. Each green label is
recoloured teal, and the CHECK no longer admits GREEN.

The recolouring is recorded once per client whose labels it changed, as a system change (no
actor, no reason): CLIENT_KNOWLEDGE_LABELS_RECOLOURED, with the labels it changed in the payload,
the client named as every other label audit names it; one upgrade's rows share one created_at. The
downgrade reads the rows of the latest upgrade (the newest created_at) to put back exactly the labels
it recoloured, where they are still teal and no person has changed them since; the audit rows stay, as the audit is append-only. Autogenerate
does not see a CHECK change (AGENTS.md § Alembic), so this is written by hand.

Revision ID: 5cc62edde24e
Revises: 2bec066f109f
Created: 2026-10-29 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5cc62edde24e"
down_revision: str | None = "2bec066f109f"
branch_labels = None
depends_on = None

ACTION = "CLIENT_KNOWLEDGE_LABELS_RECOLOURED"
_CHANGED = "CLIENT_KNOWLEDGE_LABEL_CHANGED"
_CHECK = "ck_client_knowledge_labels_knowledge_label_colour_known"
_WITHOUT_GREEN = "colour in ('BLUE','TEAL','ORANGE','VIOLET','SLATE')"
_WITH_GREEN = "colour in ('BLUE','TEAL','GREEN','ORANGE','VIOLET','SLATE')"

_labels = sa.table(
    "client_knowledge_labels",
    sa.column("label_id", sa.String),
    sa.column("organization_id", sa.String),
    sa.column("client_id", sa.String),
    sa.column("colour", sa.String),
)
_audit = sa.table(
    "access_audit",
    sa.column("event_id", sa.Integer),
    sa.column("organization_id", sa.String),
    sa.column("client_id", sa.String),
    sa.column("action", sa.String),
    sa.column("reason", sa.String),
    sa.column("payload", sa.JSON().with_variant(postgresql.JSONB(), "postgresql")),
    sa.column("created_at", sa.DateTime(timezone=True)),
)


def _check(condition: str) -> None:
    with op.batch_alter_table("client_knowledge_labels") as batch:
        batch.drop_constraint(op.f(_CHECK), type_="check")
        batch.create_check_constraint(op.f(_CHECK), condition)


def upgrade() -> None:
    bind = op.get_bind()
    green = bind.execute(
        sa.select(_labels.c.organization_id, _labels.c.client_id, _labels.c.label_id)
        .where(_labels.c.colour == "GREEN")
        .order_by(_labels.c.organization_id, _labels.c.client_id, _labels.c.label_id)
    ).all()
    by_client: dict[tuple[str, str], list[str]] = defaultdict(list)
    for organization_id, client_id, label_id in green:
        by_client[(organization_id, client_id)].append(label_id)
    now = datetime.now(UTC)
    for (organization_id, client_id), label_ids in by_client.items():
        bind.execute(
            _audit.insert().values(
                organization_id=organization_id,
                client_id=client_id,
                action=ACTION,
                reason="",
                payload={"from": "GREEN", "to": "TEAL", "label_ids": label_ids},
                created_at=now,
            )
        )
    bind.execute(_labels.update().where(_labels.c.colour == "GREEN").values(colour="TEAL"))
    _check(_WITHOUT_GREEN)


def downgrade() -> None:
    _check(_WITH_GREEN)
    bind = op.get_bind()
    # The rows of the upgrade being undone: an earlier cycle's rows are not.
    latest = bind.scalar(
        sa.select(sa.func.max(_audit.c.created_at)).where(_audit.c.action == ACTION)
    )
    rows = bind.execute(
        sa.select(_audit.c.event_id, _audit.c.client_id, _audit.c.payload).where(
            _audit.c.action == ACTION, _audit.c.created_at == latest
        )
    ).all()
    for event_id, client_id, payload in rows:
        label_ids = set((payload or {}).get("label_ids", []))
        # A label a person changed since, teal on purpose or not, keeps what they chose.
        changed = bind.execute(
            sa.select(_audit.c.payload).where(
                _audit.c.action == _CHANGED,
                _audit.c.client_id == client_id,
                _audit.c.event_id > event_id,
            )
        ).all()
        label_ids -= {(p or {}).get("label_id") for (p,) in changed}
        if label_ids:
            bind.execute(
                _labels.update()
                .where(_labels.c.label_id.in_(sorted(label_ids)), _labels.c.colour == "TEAL")
                .values(colour="GREEN")
            )
