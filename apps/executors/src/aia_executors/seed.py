"""``python -m aia_executors.seed [--reset]``: the idempotent develop seed.

Reads ``DATABASE_URL`` and ``AIA_SEED_OWNER_EMAIL``. Runs inside the worker image
on the develop host (``deploy/develop/README.md`` § Seed / reset) and from a
developer checkout with the same variables. Prints ids, never secrets.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from aia_core.application.develop_seed import reset_develop_seed, seed_develop

from ._db import engine_from_env

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="remove the seeded organization first")
    parser.add_argument(
        "--owner-email",
        default=os.environ.get("AIA_SEED_OWNER_EMAIL", ""),
        help="defaults to AIA_SEED_OWNER_EMAIL",
    )
    args = parser.parse_args(argv)
    if not args.owner_email:
        print("AIA_SEED_OWNER_EMAIL (or --owner-email) is required", file=sys.stderr)
        return 2

    engine, sessions = engine_from_env()
    try:
        if args.reset:
            with sessions() as session:
                removed = reset_develop_seed(session)
                session.commit()
            print(json.dumps({"reset": removed}))
        with sessions() as session:
            result = seed_develop(session, owner_email=args.owner_email)
            session.commit()
        print(
            json.dumps(
                {
                    "organization_id": result.organization_id,
                    "owner_user_id": result.owner_user_id,
                    "owner_email": result.owner_email,
                    "smoke_organization_id": result.smoke_organization_id,
                    "smoke_owner_user_id": result.smoke_owner_user_id,
                    "client_id": result.client_id,
                    "study_id": result.study_id,
                    "project_id": result.project_id,
                    "run_id": result.run_id,
                    "created": result.created,
                    "workspaces": result.workspaces,
                },
                indent=2,
            )
        )
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
