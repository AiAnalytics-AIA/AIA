"""Every legacy route the ledger calls PORTING or PORTED names a route this API actually serves.

The route ledger (``docs/migration/legacy-route-ledger.json``) is the strangler's
record of which of the 18.6.6 HTTP routes AIA already serves. A row that names an
AIA route which is not in the OpenAPI document would be a claim with nothing
behind it -- the same failure as a CI contract assertion outliving its contract
(ARCHITECTURE.md §6 A3), in the other direction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aia_api.config import Environment, Settings
from aia_api.main import create_app

REPO = Path(__file__).resolve().parents[3]
LEDGER = json.loads((REPO / "docs" / "migration" / "legacy-route-ledger.json").read_text("utf-8"))
CLAIMED = [r for r in LEDGER["routes"] if r["status"] in {"PORTING", "PORTED"}]


@pytest.fixture(scope="module")
def served() -> set[tuple[str, str]]:
    spec = create_app(Settings(env=Environment.LOCAL)).openapi()
    return {
        (method.upper(), path)
        for path, operations in spec["paths"].items()
        for method in operations
        if method.lower() in {"get", "post", "put", "patch", "delete"}
    }


def test_the_ledger_claims_at_least_the_project_routes() -> None:
    assert len(CLAIMED) >= 10, "the ledger stopped recording the routes AIA already serves"


@pytest.mark.parametrize("row", CLAIMED, ids=[r["route"] for r in CLAIMED])
def test_a_claimed_aia_route_is_in_the_openapi_document(
    row: dict[str, Any], served: set[tuple[str, str]]
) -> None:
    verb, path = row["aia_route"].split(" ", 1)
    assert (verb, path) in served, (
        f"{row['route']} claims {row['aia_route']}, which this API does not serve"
    )


def test_study_scoped_claims_carry_the_study_in_the_path() -> None:
    for row in CLAIMED:
        if row["scope"] == "study":
            assert "/api/v1/studies/{study_id}/" in row["aia_route"], row["route"]
