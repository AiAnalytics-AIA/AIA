"""Completeness guard for the reference module inventory.

The prototype being migrated has 191 Python modules. The parity matrix names the
significant ones in prose, which is how 85 of them ended up with no recorded
disposition at all -- including the modules that implement the epistemic and
budget rules the product documentation claims AIA enforces (``factual_layer``,
``tier_gate``, ``holdout_registry``, ``uncertainty``, ``budget_guard``).

``docs/migration/module-dispositions.json`` records an explicit disposition for
every module, so a module can no longer be forgotten by omission.

**These checks run without the reference checkout**, which is the point: the
reference is deliberately not committed, so a guard that needed it would skip in
CI and enforce nothing. The expected module set is derived instead from
``docs/migration/reference-manifest.json`` -- the committed SHA256 manifest of
the prototype's 1,324 canonical files. The live-reference test at the bottom is
an additional cross-check that the committed manifest still matches the tree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

DOCS = Path(__file__).resolve().parents[3] / "docs" / "migration"
INVENTORY = DOCS / "module-dispositions.json"
MANIFEST = DOCS / "reference-manifest.json"

# Not part of the migration surface: the prototype's own test suite, build
# caches, and the bundled demo payloads (data, not behaviour).
EXCLUDED_DIRS = frozenset({"tests", "__pycache__", "node_modules", ".venv", "demo_library", ".git"})

VALID_DISPOSITIONS = frozenset({"port", "data-pipeline", "dev-tool", "drop"})
VALID_STATES = frozenset({"done", "partial", "not-started", "n/a"})


def _is_migration_module(path: str) -> bool:
    return path.endswith(".py") and not EXCLUDED_DIRS & set(path.split("/"))


@pytest.fixture(scope="module")
def inventory() -> dict[str, dict[str, Any]]:
    """The recorded disposition of every reference module, keyed by path."""
    data = json.loads(INVENTORY.read_text(encoding="utf-8"))
    return {str(entry["module"]): entry for entry in data["modules"]}


@pytest.fixture(scope="module")
def manifest_modules() -> set[str]:
    """Migration-relevant modules according to the committed reference manifest."""
    files = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    return {path for path in files if _is_migration_module(path)}


def test_every_reference_module_has_a_disposition(
    manifest_modules: set[str], inventory: dict[str, dict[str, Any]]
) -> None:
    """No module may be dropped by omission -- the failure mode this guards."""
    unclassified = sorted(manifest_modules - inventory.keys())
    assert not unclassified, (
        f"{len(unclassified)} reference module(s) have no recorded disposition. "
        "Add an entry to docs/migration/module-dispositions.json -- a module with "
        "no disposition is one nobody decided to keep or drop:\n  " + "\n  ".join(unclassified)
    )


def test_inventory_has_no_stale_entries(
    manifest_modules: set[str], inventory: dict[str, dict[str, Any]]
) -> None:
    """An entry for a module absent from the manifest means the map drifted."""
    stale = sorted(inventory.keys() - manifest_modules)
    assert not stale, (
        f"{len(stale)} inventory entr(ies) name a module that is not in the "
        f"reference manifest:\n  " + "\n  ".join(stale)
    )


def test_dispositions_are_well_formed(inventory: dict[str, dict[str, Any]]) -> None:
    """Each entry carries a known disposition, a context and a reason."""
    for module, entry in sorted(inventory.items()):
        assert entry["disposition"] in VALID_DISPOSITIONS, (
            f"{module}: unknown disposition {entry['disposition']!r}"
        )
        assert entry["state"] in VALID_STATES, f"{module}: unknown state {entry['state']!r}"
        assert entry["context"], f"{module}: no bounded context recorded"
        assert entry["note"], f"{module}: no reason recorded for its disposition"


def test_ported_modules_name_an_owning_phase(inventory: dict[str, dict[str, Any]]) -> None:
    """A port with no phase is work nobody scheduled."""
    for module, entry in sorted(inventory.items()):
        if entry["disposition"] == "port":
            phase = entry["phase"]
            assert isinstance(phase, int) and 2 <= phase <= 10, (
                f"{module}: ported modules need a migration phase, got {phase!r}"
            )
        else:
            assert entry["phase"] is None, (
                f"{module}: only ports carry a phase, got {entry['phase']!r}"
            )
            assert entry["state"] == "n/a", (
                f"{module}: a module that is not ported has no progress state"
            )


def test_only_ported_modules_claim_progress(inventory: dict[str, dict[str, Any]]) -> None:
    """`done` must mean a production replacement exists, not merely a decision."""
    done = {m for m, e in inventory.items() if e["state"] in {"done", "partial"}}
    assert done == {
        "project_pipeline.py",
        "project_store.py",
        "provider_runtime.py",
        "artifact_store.py",
        "job_store.py",
        "workflow_engine.py",
        "cost_controller.py",
        "ui_server.py",
        # Deterministic halves only; behavioural tests in test_simulation_*.py.
        "full_simulation.py",
        "scenario_compiler.py",
        # PR C chunk 5: aggregation, exact against captures of the unit
        # (test_research_aggregate.py); bounds within its seed spread (OI-62).
        "uncertainty.py",
        "fidelity.py",
        # PR C chunk 6: derive_relation_matrix, exact against a capture of the unit
        # (test_research_sociomap.py).
        "sociomap.py",
        # Agent Runtime Foundation: the respondent response process and factual layer,
        # against captures of the unit's own functions (test_respondent_behavior.py)
        # and its module itself (test_respondent_facts.py).
        "behavior.py",
        "styly.py",
        "factual_layer.py",
        # Deep Research: the leakage screen and merge, exact against captures of the
        # unit's own research_context.py (test_deep_research_legacy.py).
        "research_context.py",
    }, (
        "The set of modules claiming progress changed. Update this assertion "
        "deliberately, with the parity or behavioural evidence for the new entry."
    )


@pytest.mark.parity
def test_committed_manifest_still_matches_the_reference_tree(
    legacy_root: Path, manifest_modules: set[str]
) -> None:
    """Cross-check: the offline manifest is only trustworthy while it is current."""
    actual = {
        str(path.relative_to(legacy_root))
        for path in legacy_root.rglob("*.py")
        if _is_migration_module(str(path.relative_to(legacy_root)))
    }
    assert actual == manifest_modules, (
        "docs/migration/reference-manifest.json has drifted from the extracted "
        "reference tree.\n\n"
        "Do NOT regenerate from the tree. The tree is mutable -- running the "
        "reference rewrites its data/*.sqlite state -- and a tree-derived write "
        "cannot supply the archive hash, the reference-repository identity or "
        "the migration module list, so it would silently downgrade the manifest "
        "schema. The tool refuses it for that reason.\n\n"
        "Regenerate from the authoritative archive instead:\n"
        "    python tools/reference_manifest.py write --archive <reference>.zip\n\n"
        "AiAnalytics-AIA/AIA-reference is authoritative for obtaining it; see "
        "docs/migration/reference-source.md.\n\n"
        "A difference here usually means the TREE has drifted, not the manifest: "
        "the manifest is derived from the immutable archive, so a checkout that "
        "disagrees with it is the thing to investigate first.\n"
        f"  only in tree:     {sorted(actual - manifest_modules)}\n"
        f"  only in manifest: {sorted(manifest_modules - actual)}"
    )
