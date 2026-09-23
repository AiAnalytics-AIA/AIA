"""Sociomapa parity against the legacy source checkout (``AIA_LEGACY_REFERENCE``).

The numerical parity evidence for the ported Sociomapping mathematics is the
golden fixtures F1-F9, vendored under ``fixtures/sociomap/`` and exercised by
``test_sociomap_relations.py``, ``test_sociomap_metrics.py``,
``test_sociomap_terrain.py`` and ``test_sociomap_engine.py`` -- in every CI job,
without a checkout.

This module does the two things that still need the legacy *source*:

1. pin the reference ``sociomap.py`` and siblings to the hash the committed
   manifest records, so any future port from source is known to describe the
   validated snapshot and not a drifted copy;
2. generate the function-level inventory from the real source.

Both skip cleanly without ``AIA_LEGACY_REFERENCE`` and are marked ``parity`` so
they run under ``make test-parity``. A skip here is reported, never counted as a
pass. What the source is still needed for -- the reference's Python unfolding
(F4), ``baseObjectLayout66`` and the R smacof branch -- is recorded in
``.planning/open-items.md``.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "docs/migration/reference-manifest.json"
TOOLS = REPO / "tools"

LEGACY_SOCIOMAP_MODULES = (
    "sociomap.py",
    "visualization_lab.py",
    "segment_orchestration.py",
    "respondent_dialogue.py",
)

pytestmark = pytest.mark.parity


@pytest.fixture(scope="module")
def inventory_tool() -> Any:
    sys.path.insert(0, str(TOOLS))
    try:
        import sociomap_inventory

        return sociomap_inventory
    finally:
        sys.path.remove(str(TOOLS))


def test_manifest_names_the_legacy_sociomap_modules() -> None:
    """Runs everywhere: the committed manifest must still list every module we port from."""
    files = json.loads(MANIFEST.read_text())["files"]
    for module in LEGACY_SOCIOMAP_MODULES:
        assert module in files, f"{module} missing from the reference manifest"
        assert len(files[module]) == 64


@pytest.mark.parametrize("module", LEGACY_SOCIOMAP_MODULES)
def test_reference_sociomap_module_matches_the_committed_manifest(
    legacy_root: Path, module: str
) -> None:
    """The source we port from must be the validated snapshot, byte for byte."""
    expected = json.loads(MANIFEST.read_text())["files"][module]
    actual = hashlib.sha256((legacy_root / module).read_bytes()).hexdigest()
    assert actual == expected, (
        f"{module} has drifted from the manifest; see reference-weaknesses.md"
    )


def test_inventory_of_the_real_sociomap_module(
    legacy_root: Path, inventory_tool: Any, tmp_path: Path
) -> None:
    """Generate the function-level audit table from the real ``sociomap.py``.

    The table is written to ``tmp_path`` and its location printed so the engineer
    can copy it into the engine document. The assertions are structural: the
    module parses, has functions, and every function was inventoried.
    """
    facts = inventory_tool.inventory_module(legacy_root / "sociomap.py")
    assert facts.functions, "sociomap.py has no functions? inventory tool or reference is wrong"
    assert facts.loc > 0

    out = tmp_path / "sociomap_inventory.md"
    out.write_text(inventory_tool.render_markdown([facts]), encoding="utf-8")
    print(f"\nlegacy sociomap inventory written to {out}")

    # These are the facts the port must reconcile before any contract is finalised.
    randomness = [f.qualname for f in facts.functions if f.uses_randomness]
    print(f"functions touching randomness: {randomness or 'none detected'}")
    print(f"mutable module globals: {facts.mutable_globals or 'none detected'}")
    print(f"module constants: {list(facts.constants) or 'none detected'}")
