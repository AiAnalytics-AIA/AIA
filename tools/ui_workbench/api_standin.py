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

The audience step's catalogue and preview read a fictional LIVE population built from
the sampler's fixture rows (``fictional_population.py``), unless ``--no-audience-population``;
research runs still record the Czech LIVE, which the workbench never establishes.

``--population-double`` composes the population double instead (RQC10, local and test only):
runs record its LIVE, the panel is offered and the default, and readiness draws the run's own
sample from it, so Vzorek shows the sample by quota cell (run-qc-and-checkpoint RQC6d). It needs
``--fieldwork ai_runtime``; no model is configured, so a run started there parks at fieldwork.

Needs the repository's own Python environment (``make setup``), not the
workbench venv, which holds the 18.6.6 unit's requirements.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOME = REPO / "tmp" / "ui-workbench"
DB = HOME / "aia.sqlite"
WORKBENCH_EMAIL = "workbench@example.invalid"


def build(
    db: Path,
    *,
    artifacts: Path | None = None,
    fieldwork: str = "ai_runtime",
    population_double: bool = False,
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
        storage_backend="filesystem",
        storage_root=str(artifacts or db.parent / "artifacts"),
        research_fieldwork_source=fieldwork,
        # The experimental Sociomapping (plan sociomapping-engine I1-I5) runs here: no model,
        # fictional fieldwork, and every result marked EXPERIMENTAL_AIA.
        sociomapping_experimental_enabled=True,
        # The Research Lead (ADR 0026): the workbench's worker answers each turn by a script,
        # without a model (aia_executors.workbench), and every reply says so.
        ai_research_lead_enabled=True,
        # The eight analysis modules and the internal draft report (plan
        # artifact-chain-to-draft-report CHN7): the worker answers them from recordings behind
        # the real gateway, priced at zero (aia_executors.workbench.recorded_analysis).
        ai_analysis_enabled=True,
        # Priced at zero, so a nominal hold: eight modules stay inside a fixture study's budget.
        ai_analysis_reservation_usd=0.01,
        # A design job's ceiling (lead-orchestration LO15): its recorded answer costs nothing,
        # and a nominal hold keeps the spend gate a real one (aia_executors.workbench).
        ai_research_reservation_usd=0.01,
        population_double=population_double,
        ai_population_personas_enabled=population_double,
        # The object map's kernels compiled after start, as on develop, when asked for
        # (AIA_SOCIOMAP_WARMUP_ENABLED=true in the environment): off by default here.
        sociomap_warmup_enabled=os.environ.get("AIA_SOCIOMAP_WARMUP_ENABLED") == "true",
    )
    app = create_app(settings)
    return app, Base, seed_develop, Session


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--fresh", action="store_true", help="start from an empty database")
    ap.add_argument("--db", default=str(DB), help="the SQLite file")
    ap.add_argument("--artifacts", default="", help="the artifact directory the worker shares")
    ap.add_argument(
        "--fieldwork",
        default="ai_runtime",
        choices=("ai_runtime", "synthetic_fixture"),
        help="the fieldwork source recorded on research runs",
    )
    ap.add_argument(
        "--no-audience-population",
        action="store_true",
        help="leave the audience step without a population (it says so, as on a fresh develop)",
    )
    ap.add_argument(
        "--population-double",
        action="store_true",
        help="compose the fictional population double and offer the panel (needs ai_runtime)",
    )
    args = ap.parse_args(argv)
    if args.population_double and args.fieldwork != "ai_runtime":
        ap.error("--population-double offers the panel, which only ai_runtime fieldwork answers")

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
        artifacts=artifacts,
        fieldwork=args.fieldwork,
        population_double=args.population_double,
    )
    # Startup builds the engine; create the schema and seed through it once.
    with TestClient(app):  # type: ignore[arg-type]
        engine = app.state.engine  # type: ignore[attr-defined]
        base.metadata.create_all(engine)  # type: ignore[attr-defined]
        with session_cls(engine) as session:  # type: ignore[operator]
            result = seed_develop(session, owner_email=WORKBENCH_EMAIL)
            session.commit()
            if not (args.no_audience_population or args.population_double):
                import fictional_population

                contract, source = fictional_population.build(session)
                fictional_population.install(app, contract, source)
    print(f"api: seeded for {WORKBENCH_EMAIL}: {sorted(result.workspaces)}", file=sys.stderr)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
