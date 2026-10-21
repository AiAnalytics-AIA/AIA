"""The migrations have exactly one head.

Two pull requests that each add a migration on the same parent merge cleanly as files and leave
``alembic upgrade head`` failing on develop, with acceptance and the deploy behind it
(lead-orchestration LO1's review of #544, P1-a). This fails the second of them in its own CI run,
before the merge, instead of after it.
"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

REPO = Path(__file__).resolve().parents[3]


def test_the_migrations_have_exactly_one_head() -> None:
    config = Config(str(REPO / "alembic.ini"))
    config.set_main_option("script_location", str(REPO / "migrations"))
    heads = ScriptDirectory.from_config(config).get_heads()
    assert len(heads) == 1, f"migration heads {sorted(heads)}: re-point one down_revision"
