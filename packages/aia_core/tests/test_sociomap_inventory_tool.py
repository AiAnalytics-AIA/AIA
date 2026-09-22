"""Tests for the legacy Sociomapping inventory tool.

The tool exists so the function-level audit of ``sociomap.py`` is generated from
the real source rather than written from memory. It is tested against a
synthetic module, so it needs no reference checkout; the one test that touches
the real reference is in ``test_sociomap_parity.py`` and skips without it.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

TOOLS = Path(__file__).resolve().parents[3] / "tools"

SYNTHETIC = textwrap.dedent(
    '''
    """A stand-in for a legacy module with the smells the audit must surface."""
    import math
    import random
    import numpy as np
    from collections import defaultdict

    DEFAULT_ITERATIONS = 500
    TOLERANCE = 1e-6
    WEIGHTS = {"a": 0.4, "b": 0.6}
    _cache = {}
    registry = defaultdict(list)

    def relation_matrix(rows, weights=None, min_overlap=3):
        """Derive the relation matrix from pairwise rows."""
        w = weights or WEIGHTS
        return [[abs(x - y) * w["a"] for y in rows] for x in rows]

    def layout(matrix, iterations=DEFAULT_ITERATIONS, seed=None, tol=TOLERANCE):
        """Unfold a matrix into 2-D."""
        rng = random.Random(seed)
        pts = [(rng.random(), rng.random()) for _ in matrix]
        if len(matrix) > 50:
            iterations = iterations // 2
        _cache["last"] = pts
        return pts

    def height(values, clip=0.95):
        return [min(v, clip) for v in values]

    class Mapper:
        def run(self, matrix):
            """Run everything."""
            global registry
            registry["runs"].append(1)
            return layout(matrix)

        async def stream(self):
            return np.random.normal()
    '''
)


@pytest.fixture(scope="module")
def tool() -> Any:
    sys.path.insert(0, str(TOOLS))
    try:
        import sociomap_inventory

        return sociomap_inventory
    finally:
        sys.path.remove(str(TOOLS))


@pytest.fixture
def fake_reference(tmp_path: Path) -> Path:
    root = tmp_path / "npc-panel-reference"
    root.mkdir()
    (root / "project_pipeline.py").write_text("STAGES = []\n")
    (root / "sociomap.py").write_text(SYNTHETIC)
    return root


def test_inventory_lists_every_function_and_method(tool: Any, fake_reference: Path) -> None:
    facts = tool.inventory_module(fake_reference / "sociomap.py")
    assert [f.qualname for f in facts.functions] == [
        "relation_matrix",
        "layout",
        "height",
        "Mapper.run",
        "Mapper.stream",
    ]
    assert facts.loc > 20
    assert len(facts.sha256) == 64
    assert "random" in facts.imports and "numpy" in facts.imports


def test_inventory_surfaces_hidden_defaults_and_thresholds(tool: Any, fake_reference: Path) -> None:
    facts = tool.inventory_module(fake_reference / "sociomap.py")
    assert facts.constants["DEFAULT_ITERATIONS"] == "500"
    assert facts.constants["TOLERANCE"] == "1e-06"
    assert facts.constants["WEIGHTS"] == "{'a': 0.4, 'b': 0.6}"
    by_name = {f.qualname: f for f in facts.functions}
    assert by_name["relation_matrix"].numeric_defaults == {"min_overlap": "3"}
    assert by_name["height"].numeric_defaults == {"clip": "0.95"}
    # An inline threshold that is not a parameter is a hidden methodology decision.
    assert "50" in by_name["layout"].numeric_literals


def test_inventory_flags_randomness_and_mutable_state(tool: Any, fake_reference: Path) -> None:
    facts = tool.inventory_module(fake_reference / "sociomap.py")
    by_name = {f.qualname: f for f in facts.functions}
    assert by_name["layout"].uses_randomness
    assert any("random" in c for c in by_name["layout"].random_calls)
    assert by_name["Mapper.stream"].uses_randomness
    assert not by_name["height"].uses_randomness
    assert set(facts.mutable_globals) == {"WEIGHTS", "_cache", "registry"}
    assert "WEIGHTS" in by_name["relation_matrix"].reads_globals
    assert "_cache" in by_name["layout"].reads_globals
    assert by_name["Mapper.run"].writes_globals == ["registry"]


def test_inventory_never_imports_the_module(tool: Any, tmp_path: Path) -> None:
    """Importing would execute the reference; a side effect here proves it did not."""
    marker = tmp_path / "executed"
    module = tmp_path / "sociomap.py"
    module.write_text(
        f"import pathlib\npathlib.Path({str(marker)!r}).write_text('ran')\ndef f():\n    return 1\n"
    )
    facts = tool.inventory_module(module)
    assert [f.qualname for f in facts.functions] == ["f"]
    assert not marker.exists()


def test_markdown_has_the_audit_columns(tool: Any, fake_reference: Path) -> None:
    text = tool.render_markdown([tool.inventory_module(fake_reference / "sociomap.py")])
    header = next(line for line in text.splitlines() if line.startswith("| Legacy function/module"))
    for column in (
        "Responsibility",
        "Inputs",
        "Outputs",
        "Deterministic / semantic / presentation",
        "Production destination",
        "Parity requirement",
        "Randomness",
    ):
        assert column in header
    assert "`sociomap.py:layout`" in text
    assert "random.Random" in text
    assert "DEFAULT_ITERATIONS = 500" in text


def test_json_output_round_trips(tool: Any, fake_reference: Path) -> None:
    data = json.loads(tool.render_json([tool.inventory_module(fake_reference / "sociomap.py")]))
    assert data[0]["path"] == "sociomap.py"
    assert {f["qualname"] for f in data[0]["functions"]} >= {"layout", "relation_matrix"}


def test_cli_uses_the_configured_reference(
    tool: Any, fake_reference: Path, tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    monkeypatch.setenv("AIA_LEGACY_REFERENCE", str(fake_reference))
    out = tmp_path / "inventory.md"
    assert tool.main(["--module", "sociomap.py", "--output", str(out)]) == 0
    assert "| `sociomap.py:relation_matrix`" in out.read_text()


def test_cli_refuses_to_run_without_the_reference(
    tool: Any, tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    """A missing checkout must be reported in the agreed words, never as an empty inventory."""
    monkeypatch.setenv("AIA_LEGACY_REFERENCE", str(tmp_path / "nowhere"))
    assert tool.main([]) == 2
    assert tool.REFERENCE_UNAVAILABLE in capsys.readouterr().err
    assert (
        tool.REFERENCE_UNAVAILABLE
        == "parity suite not run because the reference checkout is unavailable"
    )


def test_cli_reports_a_missing_module_rather_than_skipping_it(
    tool: Any, fake_reference: Path, monkeypatch: Any, capsys: Any
) -> None:
    monkeypatch.setenv("AIA_LEGACY_REFERENCE", str(fake_reference))
    assert tool.main(["--module", "visualization_lab.py"]) == 2
    assert "missing in reference: visualization_lab.py" in capsys.readouterr().err
