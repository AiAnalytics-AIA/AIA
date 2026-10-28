"""The recorded doubles behind the gateway and the retrieval gate, over HTTP on the stack
(``docs/migration/mvp-acceptance.md`` §2, tier A; plan ``mvp-acceptance-harness`` chunk 4).

The harness's worker (``aia_executors.acceptance_recorded``) answers every model call from the
shared recorded wire and, with Deep Research on, every search and fetch from ``recordings/``:
``web.json`` (the representative study's one public page, ``inputs/web-page.html``, served at
its URL) and ``agents.json`` (the five agents' script). These tests drive a client document's
knowledge proposals and a Design Research run the way the web client does, and read back that
every answer was a recording. They prove no acceptance criterion and are listed under none.
"""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

pytestmark = pytest.mark.acceptance

HERE = Path(__file__).resolve().parent
INPUTS = HERE / "inputs"
RECORDINGS = HERE / "recordings"
#: Generous: a cold worker imports the whole composition (CLAUDE.md §7).
RUN_SECONDS = 240.0
#: The recorded extraction's usage (2,000 in, 300 out) at the stack's test prices (USD 3 / 15
#: per million tokens): what one batch costs the client.
SOURCE_BATCH_USD = (2000 * 3 + 300 * 15) / 1_000_000
#: A recorded Deep Research agent's usage (1,500 in, 250 out) at the same prices.
DEEP_RESEARCH_CALL_USD = (1500 * 3 + 250 * 15) / 1_000_000
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}


def _index() -> dict[str, Any]:
    entries: dict[str, Any] = json.loads((INPUTS / "index.json").read_text("utf-8"))["inputs"]
    return entries


def _recording(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((RECORDINGS / name).read_text("utf-8"))
    return loaded


def _wait(stack: Any, worker: Any, path: str, who: str) -> dict[str, Any]:
    """Poll until the run ends, or until the worker that drains it is gone."""
    deadline = time.monotonic() + RUN_SECONDS
    seen: dict[str, Any] = {}
    while time.monotonic() < deadline:
        reply = stack.http.get(path, as_user=who)
        assert reply.status == 200, reply.text
        seen = dict(reply.json() or {})
        if seen.get("status") in TERMINAL:
            return seen
        if str(seen.get("status", "")).startswith("WAITING") and seen.get("reason"):
            return seen  # parked by name: it would wait for a person, not finish
        if not worker.alive():
            break
        time.sleep(0.5)
    raise AssertionError(f"the run did not finish: {json.dumps(seen)[:2000]}\n{stack.logs()}")


def _client(http: Any, who: str, unique: Callable[[str], str]) -> str:
    client = http.post(
        "/clients",
        {"slug": unique("acceptance-client"), "name": "Acceptance client (fiktivní)"},
        as_user=who,
    )
    assert client.status == 201, client.text
    return str(client.json()["client_id"])


# --------------------------------------------------------------------------- #
# the recordings, read from the files alone
# --------------------------------------------------------------------------- #


def test_the_recorded_page_is_the_committed_input_page() -> None:
    """The recorded web serves exactly the study's public page at its URL, and every quote the
    agents' script gives is literally on it, so the step's grounding keeps it by its own rule."""
    page = _index()["web_page"]
    html = (INPUTS / page["file"]).read_text("utf-8")
    web = _recording("web.json")
    assert web["pages"] == {
        page["url"]: {
            "status": 200,
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": html,
        }
    }
    assert set(web["hosts"]) == {urlsplit(page["url"]).hostname}
    script = _recording("agents.json")
    for query in script["default_queries"]:
        assert [h["url"] for h in web["search"][query]["hits"]] == [page["url"]]
    quotes = [e["quote"] for e in script["web"][page["url"]]]
    assert quotes and all(q in html for q in quotes), quotes


# --------------------------------------------------------------------------- #
# over HTTP
# --------------------------------------------------------------------------- #


#: The worker's switches for the client's own extraction: on, with its bounds. A client's own
#: document is Class A by rule, so the route carries Class A as the EU route does.
SOURCE_PROPOSALS_ENV = {
    "AIA_AI_ROUTE_APPROVED_FOR": (
        "CLASS_A_CLIENT_CONFIDENTIAL,CLASS_B_DERIVED_CLIENT,CLASS_C_INTERNAL"
    ),
    "AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED": "true",
    "AIA_AI_CLIENT_SOURCE_MAX_OUTPUT_TOKENS": "2048",
    "AIA_AI_CLIENT_SOURCE_RESERVATION_USD": "0.5",
}


def test_a_client_document_s_proposals_are_answered_by_the_recorded_wire(
    stack: Any, people: Any, signed_in: Callable[[str], None], unique: Callable[[str], str]
) -> None:
    """The annual summary's knowledge proposals: every request answered by the recorded
    extraction behind the gateway, every proposal kept by the step's own grounding, and the
    client charged exactly the recordings' usage."""
    http, who = stack.http, people.researcher
    signed_in(who)
    client_id = _client(http, who, unique)
    budget = http.put(f"/clients/{client_id}/budget", {"budget_usd": 1.0}, as_user=who)
    assert budget.status == 200, budget.text
    entry = _index()["client_document"]
    added = http.post(
        f"/clients/{client_id}/sources",
        {
            "filename": entry["file"],
            "data_b64": base64.b64encode((INPUTS / entry["file"]).read_bytes()).decode("ascii"),
        },
        as_user=who,
    )
    assert added.status == 201, added.text
    path = f"/clients/{client_id}/sources/{added.json()['source_id']}/proposals"
    started = http.post(path, {}, as_user=who)
    assert started.status == 202, started.text

    with stack.worker("source-proposals", **SOURCE_PROPOSALS_ENV) as worker:
        run = _wait(stack, worker, path, who)
    assert run["status"] == "COMPLETED", f"{json.dumps(run)}\n{stack.logs()}"
    output = run["output"]
    assert output["proposed"] >= 1, output
    assert not output.get("dropped"), output
    spent = http.get(f"/clients/{client_id}/budget", as_user=who).json()["spent_usd"]
    assert spent == pytest.approx(output["batches"] * SOURCE_BATCH_USD, abs=1e-6), (spent, output)


#: The worker's switches for Deep Research over the harness's recordings. A design is Class B by
#: rule and the recorded routes carry Class C alone (``deep_research_recorded``): the gates run
#: advisory, as develop's do (ADR 0008, Amendment 2026-10-21), so the refusal is a recorded pass.
DEEP_RESEARCH_ENV = {
    "AIA_AI_RESEARCH_AGENTS_ENABLED": "true",
    "AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS": "8192",
    # Two calls at the model's ceilings (the worker refuses less at start).
    "AIA_AI_RESEARCH_RESERVATION_USD": "2",
    "AIA_DEEP_RESEARCH_ENABLED": "true",
    "AIA_ACCEPTANCE_RECORDINGS": str(RECORDINGS),
    "AIA_DATA_CLASS_GATES": "advisory",
}


def _design_revision(http: Any, who: str, study_id: str) -> str:
    """The brief, with one research question, saved and submitted as a Design Revision."""
    path = f"/studies/{study_id}/workspace/content"
    current = http.get(path, as_user=who).json()
    content = json.loads(json.dumps(current["content"] or current["template"]))
    brief = json.loads((INPUTS / _index()["brief"]["file"]).read_text("utf-8"))["content"]
    for key, value in brief.items():
        content[key] = {**content.get(key, {}), **value} if isinstance(value, dict) else value
    content["research_plan"] = {
        **content["research_plan"],
        "research_questions": ["Jak knihovny v malých městech rozšiřují své služby?"],
    }
    saved = http.put(
        path,
        {"content": content, "base_revision": current["revision"], "reason": "acceptance_input"},
        as_user=who,
    )
    assert saved.status == 200, saved.text
    held = http.get(path, as_user=who).json()
    submitted = http.post(
        f"/studies/{study_id}/design/revisions",
        {
            "content": held["content"],
            "source_stage": "brief",
            "workspace_revision": held["revision"],
        },
        as_user=who,
    )
    assert submitted.status == 201, submitted.text
    return str(submitted.json()["revision_id"])


def test_a_design_research_run_is_answered_by_recorded_agents_over_the_recorded_web(
    stack: Any, people: Any, signed_in: Callable[[str], None], unique: Callable[[str], str]
) -> None:
    """A Design Research run through the production composition: the five agents answered by
    the recorded wire behind the gateway, the search and fetch by the recorded web behind the
    retrieval gate. Its sealed bundle accepts the page's quotes and nothing but recordings."""
    http, who = stack.http, people.researcher
    signed_in(who)
    client_id = _client(http, who, unique)
    study = http.post(
        "/studies",
        {
            "client_id": client_id,
            "slug": unique("mvp-acceptance"),
            "name": "MVP acceptance (fiktivní)",
            "budget_usd": 25,
        },
        as_user=who,
    )
    assert study.status == 201, study.text
    study_id = study.json()["study_id"]
    revision_id = _design_revision(http, who, study_id)
    runs = f"/studies/{study_id}/deep-research/runs"
    started = http.post(
        runs, {"design_revision_id": revision_id, "preset_name": "QUICK"}, as_user=who
    )
    assert started.status == 201, started.text
    run_path = f"{runs}/{started.json()['run_id']}"

    with stack.worker("deep-research", **DEEP_RESEARCH_ENV) as worker:
        run = _wait(stack, worker, run_path, who)
    assert run["status"] == "COMPLETED", f"{json.dumps(run)[:3000]}\n{stack.logs()}"

    bundle = http.get(f"{run_path}/bundle", as_user=who)
    assert bundle.status == 200, bundle.text
    sealed = bundle.json()
    page = _index()["web_page"]
    assert sealed["origins"] == ["RECORDED_FIXTURE"], sealed["origins"]
    assert sealed["snapshots"], "the recorded page was captured"
    assert {s["url"] for s in sealed["snapshots"]} == {page["url"]}
    assert all(s["retrieval_mode"] == "RECORDED" for s in sealed["snapshots"])
    quotes = {e["quote"] for e in _recording("agents.json")["web"][page["url"]]}
    accepted = sealed["accepted"]
    assert accepted, "the bundle accepted the page's quotes"
    assert {a["evidence"]["quote"] for a in accepted} <= quotes, accepted
    # Every agent call metered by the gateway at the recording's usage: the run's cost is a
    # whole number of recorded calls, and more than none.
    assert run["actual_cost_usd"] is not None, "a call's outcome is unknown, or costs are hidden"
    calls = run["actual_cost_usd"] / DEEP_RESEARCH_CALL_USD
    assert calls >= 4 and calls == pytest.approx(round(calls), abs=1e-6), run["actual_cost_usd"]
