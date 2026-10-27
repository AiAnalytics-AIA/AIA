"""``python -m aia_executors.status_report [--days N]``: the deployment's state as one line,
``aia-status {json}`` (plan ops-status-report).

Run by ``deploy/develop/bin/deploy.sh`` after the smoke and by ``bin/backup.sh`` after the nightly
dump, both into the deploy log the CloudWatch agent ships, so an operator (or an agent with log
read and no shell) can see what the database holds: runs and steps by status, every failed or
parked step with its reason code, model calls and their cost, open holds, Deep Research approvals.

The worker's switches come from an allowlist of its own environment (:data:`SWITCHES`); a key not
on it is never printed, and no secret is on it. Everything from the database comes through
``infrastructure/operations_status.py``: codes, counts and opaque ids only.

Acts as no one (as ``smoke_record`` and the seed do). Exit 0 with the line; exit 1 with
``aia-status-error <class>`` when the database cannot be read. Its callers never let it fail them.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from aia_core.infrastructure.build_identity import parse_build_sha
from aia_core.infrastructure.operations_status import code_or_uncoded, read_status

from ._db import engine_from_env

__all__ = ["SWITCHES", "main", "switches"]

#: The worker environment keys the report prints, each a switch, a model id or a route name.
#: Never a key, a token, a secret, a DSN or a URL: a test refuses a name that looks like one.
SWITCHES = (
    "AIA_ENV",
    "AIA_DATA_CLASS_GATES",
    "AIA_AI_RUNTIME_ENABLED",
    "AIA_AI_ROUTE_ID",
    "AIA_AI_ROUTE_APPROVED_FOR",
    "AIA_BEDROCK_MODEL_ID",
    "AIA_BEDROCK_STRUCTURED_OUTPUT",
    "AIA_BEDROCK_THINKING",
    "AIA_AI_POLICY_VERSION",
    "AIA_AI_RESEARCH_AGENTS_ENABLED",
    "AIA_AI_RESEARCH_LEAD_ENABLED",
    "AIA_AI_RESEARCH_LEAD_MODEL_ID",
    "AIA_AI_ANALYSIS_ENABLED",
    "AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED",
    "AIA_AI_POPULATION_PERSONAS_ENABLED",
    "AIA_AI_FIELDWORK_CHECKPOINT",
    "AIA_AI_FIELDWORK_HEARTBEAT",
    "AIA_AI_FIELDWORK_QUOTA_FILL",
    "AIA_AI_STEP_EVENTS",
    "AIA_AI_SCALE_LABELS_IN_PROMPT",
    "AIA_REPORT_PDF_ENABLED",
    "AIA_DEEP_RESEARCH_ENABLED",
    "AIA_DEEP_RESEARCH_WEB_SEARCH",
    "AIA_DEEP_RESEARCH_AGENT_DIRECTED",
    "AIA_DEEP_RESEARCH_LEAD",
    "AIA_DEEP_RESEARCH_FAN_OUT",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL",
    "AIA_SOCIOMAPPING_EXPERIMENTAL_ENABLED",
)


def switches(env: Mapping[str, str]) -> dict[str, str | None]:
    """Each allowlisted key's value when it is a code (a comma list of codes included), None
    when unset, ``uncoded`` otherwise."""
    shown: dict[str, str | None] = {}
    for key in SWITCHES:
        value = env.get(key, "").strip()
        if not value:
            shown[key] = None
        elif all(
            code_or_uncoded(part.strip()) not in (None, "uncoded") for part in value.split(",")
        ):
            shown[key] = value
        else:
            shown[key] = "uncoded"
    return shown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aia_executors.status_report")
    parser.add_argument("--days", type=int, default=7, help="the window, in days (1-90)")
    args = parser.parse_args(argv)
    if not 1 <= args.days <= 90:
        print("aia-status-error days_out_of_range")
        return 1
    now = datetime.now(UTC)
    report: dict[str, Any] = {
        "build": parse_build_sha(os.environ.get("AIA_BUILD_SHA", "")),
        "generated_at": now.isoformat(timespec="seconds"),
        "window_days": args.days,
        "switches": switches(os.environ),
    }
    try:
        engine, sessions = engine_from_env()
    except SystemExit:
        print("aia-status-error no_database_url")
        return 1
    try:
        with sessions() as session:
            report.update(read_status(session, since=now - timedelta(days=args.days)).as_json())
    except Exception as exc:
        print(f"aia-status-error {type(exc).__name__}")
        return 1
    finally:
        engine.dispose()
    print("aia-status " + json.dumps(report, sort_keys=True, separators=(",", ":")))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
