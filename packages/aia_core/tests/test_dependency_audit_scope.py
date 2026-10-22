"""CI's dependency audit reads every third-party distribution the images ship.

The security job installs AIA's packages and audits what pip resolved
(``.github/workflows/ci.yml``, "Audit Python dependencies"). The images install
``aia_core`` with a set of extras (``deploy/docker/python.Dockerfile``); an extra the
image installs and the audit does not is shipped unaudited. ``errors`` (sentry-sdk,
the error reporter in the API and the worker) was exactly that: in the image since
error tracking landed, never in the audit. Both files are read as text, as
``test_acceptance_wiring.py`` reads the workflow.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CI = REPO / ".github" / "workflows" / "ci.yml"
DOCKERFILE = REPO / "deploy" / "docker" / "python.Dockerfile"


def _extras(text: str, where: str) -> set[str]:
    found = re.findall(r"packages/aia_core\[([a-z0-9_,]+)\]", text)
    assert len(found) == 1, f"{len(found)} aia_core installs with extras in {where}"
    return set(found[0].split(","))


def _audit_step() -> str:
    steps = re.split(r"\n\s+- (?=name:|uses:|run:)", CI.read_text(encoding="utf-8"))
    found = [step for step in steps if step.startswith("name: Audit Python dependencies")]
    assert len(found) == 1, f"{len(found)} audit steps"
    return found[0]


def test_the_audit_installs_every_extra_the_images_ship() -> None:
    shipped = _extras(DOCKERFILE.read_text(encoding="utf-8"), "the Dockerfile")
    audited = _extras(_audit_step(), "the audit step")
    assert shipped <= audited, f"shipped but never audited: {sorted(shipped - audited)}"
