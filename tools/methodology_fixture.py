"""Write the Metodika tab's web fixture: what GET /api/v1/methodology/* serves, as one file.

The web client's tests render every formula of every registered method module from this
file (a malformed formula fails there, not on a page). ``apps/api/tests/test_methodology_api.py``
fails when the file is not what the API serves, and names this command::

    python tools/methodology_fixture.py          # rewrite the fixture
    python tools/methodology_fixture.py --check  # exit 1 if it is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "apps/web/src/lib/fixtures/methodology.json"


def document() -> dict[str, Any]:
    """Every module's summary and detail, each module's presets as the versions route serves
    them (what an edit starts from), and the field policy's tables, exactly as the routes
    serialise them."""
    from aia_api.routers.methodology import (
        _presets,
        _summary,
        field_policy_tables,
        read_module_detail,
    )
    from aia_core.domain.methodology import MODULES

    return {
        "modules": [_summary(m).model_dump(mode="json") for m in MODULES],
        "details": {
            m.id: {
                preset: read_module_detail(m.id, preset).model_dump(mode="json")
                for preset in [p.name for p in m.presets] or [None]
            }
            for m in MODULES
        },
        "presets": {m.id: _presets(m.id) for m in MODULES},
        "field_policy": field_policy_tables().model_dump(mode="json"),
    }


def render() -> str:
    return json.dumps(document(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the fixture is stale")
    args = parser.parse_args()
    text = render()
    if args.check:
        if not FIXTURE.exists() or FIXTURE.read_text(encoding="utf-8") != text:
            print(f"{FIXTURE.relative_to(REPO)} is stale: run python tools/methodology_fixture.py")
            return 1
        return 0
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(text, encoding="utf-8")
    print(f"wrote {FIXTURE.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
