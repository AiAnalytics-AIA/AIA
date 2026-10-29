"""lead-orchestration LO2 (ADR 0028 decision 3): a run start cannot be confirmed but by a person.

The confirmation was a bare ``confirm_cost_usd`` on every run start, so anything able to reach the
start could confirm its own spend. It is now a ``SpendConfirmation`` issued by ``confirm_spend``
alone. This holds the three things that make that true: no run start takes a bare figure; the
import contract "nothing the worker runs reaches the confirming start" keeps the worker and the
executors from importing the issuer; and neither names it by any other road.
"""

from __future__ import annotations

import inspect
import re
import tomllib
from pathlib import Path

import pytest

from aia_core.application.analysis_results import retry_failed_modules
from aia_core.application.research import ResearchRuns
from aia_core.application.spend_confirmation import SpendConfirmation

ROOT = Path(__file__).resolve().parents[3]
ISSUER = "aia_core.application.spend_confirmation"
#: What the worker runs: its loop and every executor.
WORKER_TREES = (ROOT / "apps/worker/src/aia_worker", ROOT / "apps/executors/src/aia_executors")
NAMES_THE_ISSUER = re.compile(r"\b(confirm_spend|spend_confirmation|_CONFIRMATION_ISSUER)\b")

RUN_STARTS = (
    ResearchRuns.start,
    ResearchRuns.start_run,
    ResearchRuns.retry,
    ResearchRuns.retry_analysis,
    retry_failed_modules,
)


@pytest.mark.parametrize("start", RUN_STARTS, ids=lambda f: f.__qualname__)
def test_no_run_start_takes_a_bare_confirmation(start: object) -> None:
    """A start reaches the confirming path only through a person's issued yes."""
    parameters = inspect.signature(start).parameters  # type: ignore[arg-type]
    assert "confirm_cost_usd" not in parameters
    assert parameters["confirmation"].annotation in (
        "SpendConfirmation | None",
        SpendConfirmation | None,
    )


def test_the_import_contract_keeps_the_issuer_from_the_worker() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    (contract,) = (
        c
        for c in config["tool"]["importlinter"]["contracts"]
        if c["name"].startswith("nothing the worker runs reaches the confirming start")
    )
    assert contract["type"] == "forbidden"
    assert {"aia_worker", "aia_executors"} <= set(contract["source_modules"])
    assert contract["forbidden_modules"] == [ISSUER]


def test_nothing_the_worker_runs_names_the_issuer() -> None:
    """What the contract's direct imports cannot see: the issuer reached through a module that
    imports it, or named in a string."""
    files = [p for tree in WORKER_TREES for p in sorted(tree.rglob("*.py"))]
    assert len(files) > 20  # the trees were found, not none
    named = {str(p.relative_to(ROOT)) for p in files if NAMES_THE_ISSUER.search(p.read_text())}
    assert named == set()
