"""A plan's status is its own front-matter, and the index is printed, never kept.

``tools/progress.py`` replaced a hand-edited ``PROGRESS.md`` that every feature
PR edited, which made each merge conflict with every other open PR
(CLAUDE.md §1, §4). These tests pin what ``--check`` accepts and refuses. They
use synthetic plans only: the tool must not turn the real plan files into a CI
gate.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

TOOL_PATH = Path(__file__).resolve().parents[3] / "tools" / "progress.py"

GOOD = """---
status: in-progress        # planned | in-progress | done
chunks:
  - "[x] 1. What landed"
  - "[ ] 2. What is next"
  - "[-] 3. Superseded by another plan"
---
# A feature

Body.
"""


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    """Import the tool by path -- `tools/` is a script directory, not a package."""
    spec = importlib.util.spec_from_file_location("progress_tool", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["progress_tool"] = module
    spec.loader.exec_module(module)
    return module


def _plans(tmp_path: Path, **files: str) -> Path:
    (tmp_path / "done").mkdir()
    (tmp_path / "README.md").write_text("# not a plan\n", encoding="utf-8")
    for name, text in files.items():
        (tmp_path / name.replace("__", "/")).write_text(text, encoding="utf-8")
    return tmp_path


def test_a_well_formed_plan_parses(tool: ModuleType, tmp_path: Path) -> None:
    plan = tool.parse(_plans(tmp_path, **{"a.md": GOOD}) / "a.md")
    assert plan.errors == []
    assert (plan.status, plan.title, plan.done, plan.counted) == ("in-progress", "A feature", 1, 2)
    assert plan.next_chunk == "2. What is next"


def test_plans_in_done_are_read_and_the_readme_is_not(tool: ModuleType, tmp_path: Path) -> None:
    root = _plans(tmp_path, **{"a.md": GOOD, "done__b.md": GOOD})
    assert [p.name for p in tool.plan_files(root)] == ["a.md", "b.md"]


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("# no front-matter\n", "no front-matter"),
        ("---\nstatus: done\nchunks:\n", "never closes"),
        ('---\nchunks:\n  - "[x] 1. a"\n---\n', "missing status:"),
        ("---\nstatus: done\n---\n", "missing chunks:"),
        ("---\nstatus: done\nchunks:\n---\n", "chunks: lists nothing"),
        ('---\nstatus: paused\nchunks:\n  - "[x] 1. a"\n---\n', "status must be one of"),
        ('---\nstatus: planned\nchunks:\n  - "[y] 1. a"\n---\n', "a chunk must read"),
        ("---\nstatus: planned\nchunks:\n  - [ ] 1. unquoted\n---\n", "a chunk must read"),
        ('---\nstatus: done\nchunks:\n  - "[ ] 1. open"\n---\n', "status is done but"),
        ('---\nstatus: done\nowner: x\nchunks:\n  - "[x] 1. a"\n---\n', "unknown key 'owner'"),
    ],
)
def test_check_refuses_malformed_front_matter(
    tool: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str], text: str, error: str
) -> None:
    root = _plans(tmp_path, **{"a.md": GOOD, "b.md": text})
    assert tool.main(["--check", "--plans", str(root)]) == 1
    captured = capsys.readouterr()
    assert error in captured.err
    assert "1 of 2 plans well-formed" in captured.out


def test_check_passes_and_the_table_orders_in_progress_first(
    tool: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    done = GOOD.replace("status: in-progress", "status: done").replace('"[ ] 2', '"[x] 2')
    root = _plans(tmp_path, **{"a.md": done, "b.md": GOOD})
    assert tool.main(["--check", "--plans", str(root)]) == 0
    assert tool.main(["--plans", str(root)]) == 0
    lines = capsys.readouterr().out.splitlines()
    statuses = [line.split(" | ")[0] for line in lines if line.startswith(("| in", "| done"))]
    assert statuses == ["| in-progress", "| done"]
