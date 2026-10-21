"""The harness itself: the stack tier A runs on, its recorded providers and its boundaries.

These hold what every criterion in ``test_mvp_acceptance.py`` relies on (plan
``mvp-acceptance-harness`` chunks 1, 3 and 4): the tree drives the product only over HTTP and
through the declared operator bootstrap; the API and the worker are processes of their own; a
research run's model calls are answered by recordings behind the real gateway, and say so; and
the USD 25 allocation the live tier will spend under is whole and sums within the study's budget.
They prove no acceptance criterion and are listed under none.
"""

from __future__ import annotations

import ast
import json
import os
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.acceptance

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
#: What this tree may never import: everything it drives, and every way to a table.
FORBIDDEN_IMPORTS = (
    "aia_core.application",
    "aia_core.infrastructure",
    "aia_api",
    "aia_worker",
    "aia_executors",
    "sqlalchemy",
    "psycopg",
    "alembic",
)
RQ = "Které z fiktivních služeb knihovny by lidé využili?"
DESIGN: dict[str, Any] = {
    "title": "Fiktivní služby knihovny",
    "goal": "Ověřit harness: běh odpovídají zaznamenané modely za bránou.",
    "n": 200,
    "research_plan": {"research_questions": [RQ]},
    "sections": [
        {
            "type": "questions",
            "questions": [
                {
                    "id": "q1",
                    "text": "Jak často byste využili prodloužení otevírací doby?",
                    "typ": "skala",
                    "skala": [1, 5],
                    "research_questions": [RQ],
                },
                {
                    "id": "q2",
                    "text": "Kterou službu byste využili nejdříve?",
                    "typ": "vyber",
                    "kategorie": ["Prodloužení", "Výdejní box", "Žádnou"],
                    "research_questions": [RQ],
                },
            ],
        }
    ],
}
#: One call of each kind as the recorded wire reports its usage, at the harness's test prices
#: (USD 3 / 15 per million input / output tokens; conftest.WORKER_ENV).
RESPONDENT_CALL_USD = (900 * 3 + 120 * 15) / 1_000_000
ANALYSIS_CALL_USD = (2400 * 3 + 380 * 15) / 1_000_000
#: Long enough for a cold worker on a CI runner (CLAUDE.md §7: size timing generously).
RUN_SECONDS = 300.0


ALLOCATION = HERE / "allocation.json"
PLAN = REPO / ".planning" / "plans" / "mvp-acceptance-harness.md"
#: The categories chunk 1 of the plan says the allocation covers, each a line of its own.
ALLOCATED_CATEGORIES = frozenset(
    {
        "fieldwork",
        "analysis_and_repairs",
        "lead_turns",
        "design_workers",
        "report_writer_and_map_interpreter",
        "deep_research_design_models",
        "deep_research_interpretation_models",
        "deep_research_tools_and_search",
        "retry_round",
    }
)
_PLAN_ROW = re.compile(r"^\| (A\d\d|E\d\d) \| `([a-z_]+)` \| ([0-9.,-]+|unknown) \|", re.M)


# --------------------------------------------------------------------------- #
# the tier B allocation (plan chunk 1)
# --------------------------------------------------------------------------- #


def test_the_tier_b_allocation_is_whole_and_within_the_study_budget() -> None:
    """Every category has a ceiling of its own; the ceilings sum to the study's budget and no
    more; nothing outside the budget is counted in it; and until the owner approves it, it says
    so. Summed here, before any recorded or live run."""
    allocation = json.loads(ALLOCATION.read_text("utf-8"))
    lines = allocation["lines"]
    ids = [line["id"] for line in lines]
    assert len(ids) == len(set(ids)), ids
    categories = {line["category"] for line in lines}
    assert categories >= ALLOCATED_CATEGORIES, ALLOCATED_CATEGORIES - categories
    assert all(line["ceiling_usd"] > 0 for line in lines), "a zero ceiling is a guess"
    total = round(sum(line["ceiling_usd"] for line in lines), 2)
    assert total == allocation["budget_usd"] == 25.0, total
    if allocation["approved_by"] is None:
        assert allocation["status"].endswith("awaiting owner approval"), allocation["status"]
        assert allocation["approved_at"] is None
    else:
        assert allocation["status"].startswith("APPROVED") and allocation["approved_at"]
    for line in allocation["outside_budget"]:
        estimate = line["estimate_usd"]
        # Unknown is said, never read as zero (CLAUDE.md §8).
        assert estimate is None or 0 < estimate[0] <= estimate[1], line["id"]
        if estimate is None:
            assert "unknown" in line["basis"], line["id"]


def test_the_plan_states_the_allocation_this_file_holds() -> None:
    """The plan's table (what the owner reads and approves) and this file (what is summed and
    what tier B checks) are one allocation."""
    allocation = json.loads(ALLOCATION.read_text("utf-8"))
    stated = {(m[0], m[1], m[2]) for m in _PLAN_ROW.findall(PLAN.read_text("utf-8"))}
    held = {
        (line["id"], line["category"], f"{line['ceiling_usd']:.2f}") for line in allocation["lines"]
    }
    held |= {
        (
            line["id"],
            line["category"],
            "unknown"
            if line["estimate_usd"] is None
            else "-".join(f"{v:,.2f}" for v in line["estimate_usd"]),
        )
        for line in allocation["outside_budget"]
    }
    assert stated == held, {"plan only": stated - held, "file only": held - stated}
    assert "PROPOSAL" in PLAN.read_text("utf-8")


# --------------------------------------------------------------------------- #
# boundaries
# --------------------------------------------------------------------------- #


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module)
    return names


def test_the_tree_imports_nothing_it_drives() -> None:
    """Over HTTP and through the bootstrap, never by import (mvp-acceptance.md §2: no back door).

    import-linter cannot hold this: ``tests/acceptance`` is not a package. Every import form
    but a dynamic one is read here from the syntax tree; a dynamic one would be visible in
    review as exactly what it is.
    """
    offenders = [
        (path.relative_to(REPO).as_posix(), name)
        for path in sorted(HERE.rglob("*.py"))
        for name in _imports(path)
        if any(name == f or name.startswith(f + ".") for f in FORBIDDEN_IMPORTS)
    ]
    assert not offenders, offenders
    dynamic = [
        path.name
        for path in HERE.rglob("*.py")
        if re.search(r"\b(importlib|__import__)\b", path.read_text("utf-8"))
        and path.name != Path(__file__).name
    ]
    assert not dynamic, dynamic


def _marks_module_acceptance(path: Path) -> bool:
    """Whether the module says ``pytestmark = pytest.mark.acceptance`` at its top level."""
    for node in ast.parse(path.read_text("utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets
        ):
            return ast.unparse(node.value) == "pytest.mark.acceptance"
    return False


def test_every_test_module_here_is_marked_acceptance() -> None:
    """The marker selects tier A (CI runs ``-m acceptance``): an unmarked module would be
    deselected there without a word, so every module carries it."""
    modules = sorted(HERE.glob("test_*.py"))
    assert {p.name for p in modules} >= {"test_mvp_acceptance.py", Path(__file__).name}
    unmarked = [p.name for p in modules if not _marks_module_acceptance(p)]
    assert not unmarked, unmarked


def test_the_stack_is_separate_processes_after_one_declared_bootstrap(stack: Any) -> None:
    """The bootstrap is the only step that is not HTTP, and it is named; the API serves from a
    process of its own, never from this one."""
    assert [step["argv"] for step in stack.bootstrap] == [
        ["-m", "alembic", "upgrade", "head"],
        ["-m", "aia_executors.seed", "--owner-email", "researcher@acceptance.invalid"],
    ]
    assert all(step["exit"] == 0 for step in stack.bootstrap)
    assert stack.seeded["organization_id"] != stack.seeded["smoke_organization_id"]
    assert stack.api.alive() and stack.api.popen.pid != os.getpid()
    health = stack.http.get("/health", as_user=None)
    assert health.status == 200, health.text


# --------------------------------------------------------------------------- #
# the recorded providers, behind the gateway
# --------------------------------------------------------------------------- #


def _wait_for_run(stack: Any, path: str, who: str) -> dict[str, Any]:
    deadline = time.monotonic() + RUN_SECONDS
    seen: dict[str, Any] = {}
    while time.monotonic() < deadline:
        reply = stack.http.get(path, as_user=who)
        assert reply.status == 200, reply.text
        seen = dict(reply.json())
        if seen["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
            return seen
        if any(not w.alive() for w in stack.workers):
            break
        time.sleep(0.5)
    raise AssertionError(f"the run did not finish: {json.dumps(seen)[:2000]}\n{stack.logs()}")


def test_a_run_is_answered_by_recorded_models_behind_the_gateway(
    stack: Any, people: Any, signed_in: Callable[[str], None], unique: Callable[[str], str]
) -> None:
    """Fieldwork and analysis through the production composition: every model request reaches
    the recorded wire through the gateway, its ledger row says it was recorded, and the run
    finishes with a report. Nothing leaves the process and nothing is paid."""
    http, who = stack.http, people.researcher
    signed_in(who)
    client = http.post(
        "/clients", {"slug": unique("harness-client"), "name": "Harness (fiktivní)"}, as_user=who
    )
    assert client.status == 201, client.text
    study = http.post(
        "/studies",
        {
            "client_id": client.json()["client_id"],
            "slug": unique("harness-run"),
            "name": "Harness run (fiktivní)",
            "budget_usd": 25,
        },
        as_user=who,
    )
    assert study.status == 201, study.text
    base = f"/studies/{study.json()['study_id']}"

    now = http.get(f"{base}/workspace/content", as_user=who)
    assert now.status == 200, now.text
    saved = http.put(
        f"{base}/workspace/content",
        {"content": DESIGN, "base_revision": now.json().get("revision")},
        as_user=who,
    )
    assert saved.status == 200, saved.text
    revision = http.post(
        f"{base}/design/revisions",
        {
            "content": DESIGN,
            "source_stage": "run",
            "workspace_revision": saved.json()["revision"],
        },
        as_user=who,
    )
    assert revision.status in (200, 201), revision.text
    started = http.post(
        f"{base}/research/runs", {"design_revision_id": revision.json()["revision_id"]}, as_user=who
    )
    assert started.status in (200, 201), started.text
    run_path = f"{base}/research/runs/{started.json()['run_id']}"

    with stack.worker("recorded"):
        run = _wait_for_run(stack, run_path, who)
    assert run["status"] == "COMPLETED", f"{_unfinished(run)}\n{stack.logs()}"

    analysis = http.get(f"{run_path}/analysis", as_user=who)
    assert analysis.status == 200, analysis.text
    modules = analysis.json()["modules"]
    assert modules, "the analysis modules answered"
    report = http.get(f"{run_path}/report", as_user=who)
    assert report.status == 200, report.text

    # The analysis modules keep each call's provider request id: every one is a recording.
    calls = _recorded_calls(stack, run, run_path, who)
    analysis_ids = {str(c["provider_request_id"]) for c in calls}
    assert analysis_ids, "the analysis modules' artifacts list their model calls"
    assert all(i.startswith("recorded-analysis-") for i in analysis_ids), sorted(analysis_ids)[:3]
    # The respondents' calls are not served over HTTP (the dataset never is, ADR 0016), so
    # the ledger is read through the study's spend: each call metered by the gateway at the
    # recording's usage and the test prices -- 200 respondents x one block, and the analysis
    # calls above. A call that went anywhere but the recorded wire would not add up.
    spent = http.get(base, as_user=who).json()["spent_usd"]
    expected = 200 * RESPONDENT_CALL_USD + len(analysis_ids) * ANALYSIS_CALL_USD
    assert spent == pytest.approx(expected, abs=1e-4), (spent, expected, len(analysis_ids))
    fieldwork = next(step for step in run["steps"] if step["kind"] == "research_fieldwork")
    assert fieldwork["data_origin"] == "SYNTHETIC_AI_FICTIONAL"


def _unfinished(run: dict[str, Any]) -> str:
    """The steps that did not succeed, each with its reason: what a failed run's message needs."""
    return json.dumps(
        [
            {k: step.get(k) for k in ("node_key", "status", "failure_class", "error_message")}
            for step in run.get("steps", [])
            if step.get("status") != "SUCCEEDED"
        ],
        ensure_ascii=False,
    )


def _recorded_calls(stack: Any, run: dict[str, Any], run_path: str, who: str) -> list[Any]:
    """Every model call a stored artifact of the run records, read through the run's routes."""
    calls: list[Any] = []
    for step in run.get("steps", []):
        for artifact_id in _artifact_ids(step):
            reply = stack.http.get(f"{run_path}/artifacts/{artifact_id}", as_user=who)
            assert reply.status == 200, reply.text
            calls.extend(_calls_in(reply.json()))
    return calls


def _artifact_ids(step: dict[str, Any]) -> list[str]:
    found = step.get("artifact_ids") or []
    if step.get("artifact_id"):
        found = [*found, step["artifact_id"]]
    return [str(a) for a in found]


def _calls_in(node: Any) -> list[Any]:
    """Each dict that names a provider request, wherever the artifact keeps it."""
    if isinstance(node, dict):
        own = [node] if "provider_request_id" in node else []
        return own + [c for v in node.values() for c in _calls_in(v)]
    if isinstance(node, list):
        return [c for v in node for c in _calls_in(v)]
    return []
