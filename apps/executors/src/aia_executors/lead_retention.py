"""``python -m aia_executors.lead_retention [--apply]``: erase sealed Leads past their date.

A deactivated member's Lead is sealed at once and erased after 30 days (ADR 0030, the product
owner's answer of 2026-10-22, plan settings-backends SB2). This is the sweep that erases it,
with its researcher's Lead turns, what those turns sent and got back, and their stored
artifacts (``aia_core.application.membership.erase_sealed_leads``). Dry run by default: it
prints how many Leads are due. The develop deploy runs it with ``--apply`` after each
migration; a failure there never fails the deploy, and the next run picks up what is left.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from aia_core.application.membership import erase_sealed_leads
from aia_core.infrastructure.researcher_lead_repository import LeadSeals
from aia_core.infrastructure.storage_settings import StorageSettings, build_artifact_store

from ._db import engine_from_env

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m aia_executors.lead_retention")
    parser.add_argument("--apply", action="store_true", help="erase; without it, count only")
    args = parser.parse_args(argv)
    now = datetime.now(UTC)
    engine, sessions = engine_from_env()
    try:
        if not args.apply:
            with sessions() as session:
                due = LeadSeals.due(session, now=now)
            print(f"lead retention: {len(due)} sealed Lead(s) past their date (dry run)")
            return 0
        store = build_artifact_store(StorageSettings.from_env())
        erased = erase_sealed_leads(sessions, store, now=now)
        print(f"lead retention: erased {len(erased)} sealed Lead(s)")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
