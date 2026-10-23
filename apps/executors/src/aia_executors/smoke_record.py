"""``python -m aia_executors.smoke_record --build <sha> [--public-hostname <host>] < lines``:
keep a deploy's smoke results for Settings → Stav systému (settings-backends SB4).

``deploy/develop/bin/smoke.sh`` feeds it the check lines it printed (its own and
``aia_executors.smoke``'s) after every check ran. Only each check's label and result are kept
(``domain/deploy_smoke.py``): no detail line. A label is also cleaned before it is kept: any
secret shape redacted (``infrastructure/redaction.py``) and any address other than the public
hostname's replaced, so nothing internal is kept even if a label ever named it.

Acts as no one (as the seed does). Exit status 0 when kept, 1 otherwise; ``smoke.sh`` never
lets this fail a deploy.
"""

from __future__ import annotations

import argparse
import re
import sys
import uuid
from datetime import UTC, datetime
from urllib.parse import urlsplit

from aia_core.domain.deploy_smoke import SmokeCheck, parse_smoke_lines
from aia_core.infrastructure.build_identity import parse_build_sha
from aia_core.infrastructure.deploy_smoke_repository import record_smoke_run
from aia_core.infrastructure.redaction import redact_text

from ._db import engine_from_env

__all__ = ["clean_label", "main"]

_URL = re.compile(r"[a-z][a-z0-9+.-]*://[^\s'\"]+", re.IGNORECASE)


def clean_label(label: str, *, public_hostname: str | None) -> str:
    """``label`` with secret shapes redacted and every address but the public hostname's
    replaced by ``<adresa>``."""

    def address(match: re.Match[str]) -> str:
        url = match.group(0)
        host = urlsplit(url).hostname
        if public_hostname and host == public_hostname.lower() and "@" not in url:
            return url
        return "<adresa>"

    return redact_text(_URL.sub(address, label))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aia_executors.smoke_record")
    parser.add_argument("--build", required=True, help="the deployed git SHA")
    parser.add_argument("--public-hostname", default=None)
    args = parser.parse_args(argv)
    build = parse_build_sha(args.build)
    if build is None:
        print("smoke_record: --build is not a git SHA", file=sys.stderr)
        return 1
    checks = [
        SmokeCheck(clean_label(c.label, public_hostname=args.public_hostname), c.status)
        for c in parse_smoke_lines(sys.stdin)
    ]
    if not checks:
        print("smoke_record: no check lines on stdin; nothing kept", file=sys.stderr)
        return 1
    engine, sessions = engine_from_env()
    try:
        with sessions() as session:
            kept = record_smoke_run(
                session,
                run_id=f"SMK-{uuid.uuid4().hex[:16]}",
                build_sha=build,
                checks=checks,
                ran_at=datetime.now(UTC),
            )
            session.commit()
    finally:
        engine.dispose()
    print(f"smoke_record: {kept} checks kept for build {build}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
