"""``GET /population``: the registry, read-only (plan ``population-operations.md`` P2).

Any member reads it; nobody unauthenticated does. Each version says where it stands,
derived from the populations and their history (never stored): the STATIC reference,
LIVE now, superseded, or only registered. Nothing about the response can write.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from aia_core.domain.population import PopulationKind
from aia_core.domain.population.czech import CZ_SYNTHETIC_V17
from aia_core.domain.population.versions import (
    DatasetVersion,
    Population,
    PromotionRecord,
    dataset_version_id,
)
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.population_repository import PopulationRegistryRepository
from fastapi import FastAPI

DATASET = CZ_SYNTHETIC_V17.dataset_id
AT = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _version(label: str, parent: str | None, minutes: int) -> DatasetVersion:
    sha = _sha(label)
    return DatasetVersion(
        version_id=dataset_version_id(DATASET, sha),
        dataset_id=DATASET,
        label=label,
        content_sha256=sha,
        byte_size=100,
        row_count=6,
        column_count=4,
        contract_id=CZ_SYNTHETIC_V17.contract_id,
        dictionary_sha256=_sha("dictionary"),
        field_names_sha256=_sha("fields"),
        parent_version_id=parent,
        storage_location=f"panels/{label}.csv.gz",
        dictionary_location="dictionary.csv",
        provenance="fictional registry rows for this test",
        imported_at=AT + timedelta(minutes=minutes),
        imported_by="USR-operator",
    )


@pytest.fixture
def registry(app: FastAPI) -> dict[str, str]:
    """Four fictional versions: a root, STATIC, a superseded LIVE, LIVE now."""
    base = _version("v_BASE", None, 0)
    static = _version("v_1", base.version_id, 1)
    old = _version("v_4", static.version_id, 2)
    live = _version("v_5", old.version_id, 3)
    with create_session_factory(app.state.engine)() as session:
        repo = PopulationRegistryRepository(session)
        for v in (base, static, old, live):
            repo.insert_version(v, validation={})
        for pid, kind, version in (
            ("CZ_STATIC_REFERENCE", PopulationKind.STATIC, static),
            ("CZ_LIVE", PopulationKind.LIVE, old),
        ):
            repo.insert_population(
                Population(pid, DATASET, kind, version.version_id, AT, "USR-operator"),
                PromotionRecord(
                    f"PRM-{pid}", pid, None, version.version_id, "USR-operator", "establish", AT
                ),
            )
        repo.apply_promotion(
            Population(
                "CZ_LIVE", DATASET, PopulationKind.LIVE, live.version_id, AT, "USR-operator"
            ),
            PromotionRecord(
                "PRM-move", "CZ_LIVE", old.version_id, live.version_id, "USR-operator",
                "the newer version", AT + timedelta(minutes=5),
            ),
        )  # fmt: skip
        session.commit()
    return {"base": base.version_id, "static": static.version_id, "old": old.version_id,
            "live": live.version_id}  # fmt: skip


def test_an_empty_registry_reads_as_empty(lead: Any, api_prefix: str) -> None:
    body = lead.get(f"{api_prefix}/population").json()
    assert body["dataset_id"] == DATASET
    assert body["versions"] == [] and body["populations"] == [] and body["history"] == []


def test_every_version_says_where_it_stands(
    registry: dict[str, str], viewer: Any, api_prefix: str
) -> None:
    response = viewer.get(f"{api_prefix}/population")
    assert response.status_code == 200
    body = response.json()
    by_id = {v["version_id"]: v for v in body["versions"]}
    assert [v["label"] for v in body["versions"]] == ["v_BASE", "v_1", "v_4", "v_5"]
    assert {k: (by_id[v]["status"], by_id[v]["runtime_eligible"]) for k, v in registry.items()} == {
        "base": ("REGISTERED", False),
        "static": ("STATIC_REFERENCE", True),
        "old": ("SUPERSEDED", True),
        "live": ("LIVE_CURRENT", True),
    }
    assert by_id[registry["live"]]["parent_version_id"] == registry["old"]
    assert {p["population_id"]: p["current_version_id"] for p in body["populations"]} == {
        "CZ_STATIC_REFERENCE": registry["static"],
        "CZ_LIVE": registry["live"],
    }
    moves = [(h["from_version_id"], h["to_version_id"], h["reason"]) for h in body["history"]]
    assert (registry["old"], registry["live"], "the newer version") in moves


def test_any_member_reads_it_and_nobody_unauthenticated(
    registry: dict[str, str], outsider: Any, client: Any, api_prefix: str
) -> None:
    assert outsider.get(f"{api_prefix}/population").status_code == 200
    assert client.get(f"{api_prefix}/population").status_code == 401


def test_the_registry_offers_no_write(lead: Any, api_prefix: str) -> None:
    for method in ("post", "put", "patch", "delete"):
        assert getattr(lead, method)(f"{api_prefix}/population").status_code == 405
