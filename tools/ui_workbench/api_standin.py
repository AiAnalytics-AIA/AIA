"""The workbench's AIA API: the real application, on SQLite, with local identity.

    python tools/ui_workbench/api_standin.py --port 8766

The client-first screens (ADR 0015) read ``/api/v1``, so the workbench runs the
real ``aia_api`` application -- not a double -- in the ``local`` environment,
where the development identity provider trusts the bearer credential as the
caller's e-mail (``aia_api.identity.testing``; it refuses to exist anywhere
else). The schema is created on a scratch SQLite file under ``tmp/ui-workbench``
and the develop seed provisions its world for ``WORKBENCH_EMAIL``: the synthetic
client and the two fictional clients with their studies and knowledge. Nothing
here reaches a provider: no model is configured.

Research runs (ADR 0016) are executed by a separate worker process on the same
SQLite file and the same filesystem artifact store (``--artifacts``). The API
records each run's fieldwork source from ``--fieldwork``: ``ai_runtime``, the
production answer, parks every run at fieldwork; ``synthetic_fixture`` -- legal
only because this is the ``local`` environment -- gives the workbench worker
(``aia_executors.workbench``) fictional respondents to finish the chain with.

``--panel-origin`` also switches on the legacy-panel gate (ADR 0012) for that
origin, for the develop routing proof (tools/develop_routing_proof.py), where
Caddy asks it before every gated path.

Needs the repository's own Python environment (``make setup``), not the
workbench venv, which holds the 18.6.6 unit's requirements.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOME = REPO / "tmp" / "ui-workbench"
DB = HOME / "aia.sqlite"
WORKBENCH_EMAIL = "workbench@example.invalid"


def build(
    db: Path,
    panel_origin: str = "",
    *,
    artifacts: Path | None = None,
    fieldwork: str = "ai_runtime",
) -> object:
    from aia_api.config import Environment, Settings
    from aia_api.main import create_app
    from aia_core.application.develop_seed import seed_develop
    from aia_core.infrastructure.tables import Base
    from sqlalchemy.orm import Session

    settings = Settings(
        env=Environment.LOCAL,
        database_url=f"sqlite+pysqlite:///{db}",
        identity_provider="development",
        log_level="WARNING",
        log_format="console",
        legacy_panel_enabled=bool(panel_origin),
        legacy_panel_origin=panel_origin,
        storage_backend="filesystem",
        storage_root=str(artifacts or db.parent / "artifacts"),
        research_fieldwork_source=fieldwork,
    )
    app = create_app(settings)
    return app, Base, seed_develop, Session


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--fresh", action="store_true", help="start from an empty database")
    ap.add_argument("--db", default=str(DB), help="the SQLite file")
    ap.add_argument("--panel-origin", default="", help="switch the legacy-panel gate on")
    ap.add_argument("--artifacts", default="", help="the artifact directory the worker shares")
    ap.add_argument(
        "--fieldwork",
        default="ai_runtime",
        choices=("ai_runtime", "synthetic_fixture"),
        help="the fieldwork source recorded on research runs",
    )
    args = ap.parse_args(argv)

    import uvicorn
    from fastapi.testclient import TestClient

    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    artifacts = Path(args.artifacts) if args.artifacts else None
    if args.fresh:
        db.unlink(missing_ok=True)
        shutil.rmtree(artifacts or db.parent / "artifacts", ignore_errors=True)
    app, base, seed_develop, session_cls = build(
        db,
        args.panel_origin,
        artifacts=artifacts,
        fieldwork=args.fieldwork,
    )
    # Startup builds the engine; create the schema and seed through it once.
    with TestClient(app):  # type: ignore[arg-type]
        engine = app.state.engine  # type: ignore[attr-defined]
        base.metadata.create_all(engine)  # type: ignore[attr-defined]
        with session_cls(engine) as session:  # type: ignore[operator]
            result = seed_develop(session, owner_email=WORKBENCH_EMAIL)
            session.commit()
    print(f"api: seeded for {WORKBENCH_EMAIL}: {sorted(result.workspaces)}", file=sys.stderr)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
