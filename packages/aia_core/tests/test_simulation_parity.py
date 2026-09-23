"""Simulation parity scaffold for fixture F13 (``REF-GAP-SIMULATION-WORLD-MODEL``).

F13 is the provider-produced fixture the reference repository specifies but has
not captured: a real ``build_world_model()`` output, frozen, then driven through
the reference ``inoculate_population``. Until it exists, these tests skip, and the
skip is reported rather than counted as a pass (``ARCHITECTURE.md`` §8).

What they assert when F13 is present is deliberately limited to the **EXACT**
items of the reference contract -- seed derivation, world identity, the
epistemic marker, the fixture's own declared tolerance and dataset. The
**NUMERICAL** comparison of ``FS_*`` columns is not written: production's
inoculation formula (``fs-inoculation-v1``) is production-defined because the
reference formula bodies are in the withheld archive, so a numeric comparison
today would fail by construction and prove nothing. It is written when the
reference source is readable; see
``docs/architecture/simulation-deterministic-engine.md`` §6.

The fixture is read from the AIA-reference checkout through the shared
``reference_repo`` fixture (``AIA_REFERENCE_REPO``, see
``docs/migration/reference-source.md``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.simulation import (
    DEFAULT_SPEC_SEED,
    FS_EPISTEMIC_STATUS,
    world_id,
    world_seed,
)

pytestmark = pytest.mark.parity

F13 = "F13_simulation_world_inoculation.json"


@pytest.fixture(scope="module")
def f13(reference_repo: Path) -> dict[str, Any]:
    path = reference_repo / "golden-fixtures" / F13
    if not path.is_file():
        pytest.skip(f"{F13} not captured yet (REF-GAP-SIMULATION-WORLD-MODEL is open)")
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def test_f13_declares_the_contracted_parity(f13: dict[str, Any]) -> None:
    assert f13["parity_type"] == "NUMERICAL"
    assert f13["tolerance"] == 1e-9
    assert str(f13["dataset_version"]).startswith("v17_4_0")


def test_f13_uses_the_reference_seed(f13: dict[str, Any]) -> None:
    assert f13["seed"] == DEFAULT_SPEC_SEED


def test_f13_world_identity_matches_the_ported_derivation(f13: dict[str, Any]) -> None:
    """EXACT: world_001 carries seed + 104729 and the experimental marker."""
    columns = f13["expected_output"]["fs_columns"]
    assert set(columns["FS_WORLD_ID"]) == {world_id(0)}
    assert set(columns["FS_WORLD_SEED"]) == {world_seed(DEFAULT_SPEC_SEED, 0)}
    assert set(columns["FS_EPISTEMIC_STATUS"]) == {FS_EPISTEMIC_STATUS}
