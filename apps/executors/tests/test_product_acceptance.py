"""Product acceptance: what a researcher meets, over HTTP, the real worker and the stored report.

Each test walks one product scenario (plan productization-coherence PC11) through the calls the
browser makes -- the API app over the same database and artifact store as the worker -- and holds
one invariant across every surface that shows it. Component suites prove each surface; these
prove the surfaces agree. Fictional designs, fictional respondents and a scripted Bedrock
(``scripted_bedrock``): nothing leaves the process and nothing is paid.

1-2. A research question the design measures and one it does not read the same at readiness, at
     the start, on the run, on Results and in the report.
4.   After the design changes, a run, its Results and its report stay its own revision's; the new
     revision gets a run of its own, never the old one's.
5.   A provider throttles one analysis module: the run reads as waiting, nothing offers a person an
     action that would pay again, and once the provider's reset passes the same run finishes its
     report with every call paid once.
6.   A delivered study: reading, downloading and approving what it holds still work; every new
     piece of work is refused under one code, ``study_closed``; reopening it restores them.

Scenario 3 (a report with literature: the review chosen, the draft, its DOCX and its PDF name one
variant) is the composed chain in ``test_analysis_executor.py``
(``test_native_ai_study_connects_a_populated_map_to_admitted_report_inputs``, its deep-research
case) and the routes in ``apps/api/tests/test_report_variant_api.py``; it is not walked again here.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from aia_api.config import Environment, Settings
from aia_api.main import create_app
from aia_core.domain.ai_contracts import UsageOutcome
from aia_core.domain.analysis import AnalysisModuleId
from aia_core.domain.analysis.steps import analysis_node_key
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.infrastructure.ai_usage_repository import AIUsageRepository
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.model_adapters.transport import HttpResponse
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.workflow_repository import WorkQueue
from aia_executors.ai_runtime import AIRuntimeSettings, build_ai_fieldwork, build_gateway
from aia_executors.analysis import AnalysisConfig, analysis_registry
from aia_executors.registry import registry_for
from aia_executors.workbench import workbench_registry_for
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from fastapi.testclient import TestClient
from scripted_bedrock import ScriptedModels, Signer, runtime_env

API = "/api/v1"
RQ_MEASURED = "Jak často lidé ráno pijí kávu?"
RQ_UNMEASURED = "Proč lidé ráno nepijí čaj?"
REASON = "Fiktivní akceptační běh: otázku o čaji vědomě necháváme bez měření."
#: One analysis call as ScriptedModels reports it, at runtime_env's test prices.
ANALYSIS_CALL_USD = (2400 * 3 + 380 * 15) / 1_000_000


def _design(*, n: int = 200, tea_measured: bool = False) -> dict[str, Any]:
    """Two research questions; q1 says it measures the first. With ``tea_measured`` q2 says it
    measures the second; without, nothing does."""
    q2: dict[str, Any] = {
        "id": "q2",
        "text": "Co si ráno koupíte?",
        "typ": "vyber",
        "kategorie": ["Kávu", "Čaj", "Nic"],
    }
    if tea_measured:
        q2["research_questions"] = [RQ_UNMEASURED]
    return {
        "title": "Fiktivní ranní nápoj",
        "goal": "Zjistit, co fiktivní lidé ráno pijí a proč.",
        "n": n,
        "research_plan": {"research_questions": [RQ_MEASURED, RQ_UNMEASURED]},
        "sections": [
            {
                "type": "questions",
                "questions": [
                    {
                        "id": "q1",
                        "text": "Jak často pijete kávu?",
                        "typ": "skala",
                        "skala": [1, 5],
                        "research_questions": [RQ_MEASURED],
                    },
                    q2,
                ],
            }
        ],
    }


GAPPED = _design()
REVISED = _design(tea_measured=True)
#: The same design at another size: a revision of its own, for a run whose analysis is refused.
REFUSED = _design(n=210, tea_measured=True)
#: Every design a worker here may send to the scripted model: classified, as the operator would.
CLASSIFIED = (GAPPED, REVISED, REFUSED)


# --------------------------------------------------------------------------- #
# harness: the API the browser calls, the worker beside it
# --------------------------------------------------------------------------- #


@pytest.fixture
def api(world: Any, database_url: str, store: InMemoryArtifactStore) -> Iterator[TestClient]:
    """The API app over the worker's database and store, signed in as the study's lead.

    The answerability gate is on (owner decision D-2 recommends it for develop), so a design
    that cannot answer a research question starts only on a person's recorded decision.
    """
    app = create_app(
        Settings(
            env=Environment.TEST,
            database_url=database_url,
            identity_provider="test",
            log_level="WARNING",
            log_format="console",
            ai_analysis_enabled=True,
            research_answerability_gate=True,
            ai_fieldwork_reservation_usd=0.25,
            ai_analysis_reservation_usd=1.0,
        )
    )
    with TestClient(app) as client:
        app.state.artifact_store = store
        app.state.identity_provider.register(
            "token-lead",
            subject="lead@art-chain.io",
            email="lead@art-chain.io",
            display_name="Lead",
        )
        client.headers["Authorization"] = "Bearer token-lead"
        yield client


def _fieldwork(api: TestClient, source: FieldworkSource) -> None:
    """Who answers the runs this API starts: the deployment's setting, never the request's."""
    settings = api.app.state.settings  # type: ignore[attr-defined]
    api.app.state.settings = settings.model_copy(update={"research_fieldwork_source": source})  # type: ignore[attr-defined]


@pytest.fixture
def worker_for(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: BuildIdentity
) -> Callable[..., Worker]:
    """A worker running the real executors, its model calls answered by ``models``."""

    def make(models: ScriptedModels, *, ai_fieldwork: bool = False) -> Worker:
        settings = AIRuntimeSettings.from_env(runtime_env(world.client_id, CLASSIFIED))
        assert settings is not None
        upstream = (
            registry_for(
                store=store,
                build=build,
                ai_runtime=build_ai_fieldwork(
                    settings, build=build, transport=models, signer=Signer()
                ),
            )
            if ai_fieldwork
            else workbench_registry_for(store=store, build=build)
        )
        return Worker(
            session_factory=world.sessions,
            executors={
                **upstream,
                **analysis_registry(
                    store=store,
                    build=build,
                    gateway=build_gateway(settings, transport=models, signer=Signer()),
                    config=AnalysisConfig.from_settings(
                        settings, max_output_tokens=4096, reservation_usd=1.0
                    ),
                ),
            },
            settings=WorkerSettings(
                database_url=database_url,
                executors="aia_executors.registry:build_registry",
                worker_id="acceptance-worker",
                lease_seconds=30,
                heartbeat_seconds=0.1,
                poll_seconds=0.05,
                maintenance_seconds=0.2,
            ),
        )

    return make


def _drain(worker: Worker) -> list[str]:
    endings: list[str] = []
    while (result := worker.run_once()) is not None:
        endings.append(result.ending)
    return endings


def _study(world: Any) -> str:
    return f"{API}/studies/{world.study_id}"


def _run_url(world: Any, run_id: str) -> str:
    return f"{_study(world)}/research/runs/{run_id}"


def _submit(api: TestClient, world: Any, design: dict[str, Any]) -> str:
    """The design as the browser submits it (ADR 0026 decision 5): the working copy is saved
    as it first, and the design names that working revision."""
    now = api.get(f"{_study(world)}/workspace/content").json()
    saved = api.put(
        f"{_study(world)}/workspace/content",
        json={"content": design, "base_revision": now.get("revision")},
    )
    assert saved.status_code == 200, saved.text
    made = api.post(
        f"{_study(world)}/design/revisions",
        json={
            "content": design,
            "source_stage": "run",
            "workspace_revision": saved.json()["revision"],
        },
    )
    assert made.status_code in (200, 201), made.text
    return str(made.json()["revision_id"])


def _readiness(api: TestClient, world: Any, revision_id: str) -> dict[str, Any]:
    got = api.get(f"{_study(world)}/research/readiness?design_revision_id={revision_id}")
    assert got.status_code == 200, got.text
    return dict(got.json())


def _start(api: TestClient, world: Any, revision_id: str) -> dict[str, Any]:
    """Start as the Run stage does: with the person's decision when readiness asks for one."""
    answer = _readiness(api, world, revision_id)["answerability"]
    body: dict[str, Any] = {"design_revision_id": revision_id}
    if answer["acknowledgement_required"]:
        body["acknowledge_research_questions"] = {"digest": answer["digest"], "reason": REASON}
    started = api.post(f"{_study(world)}/research/runs", json=body)
    assert started.status_code in (200, 201), started.text
    return dict(started.json())


def _answers(api: TestClient, world: Any, run_id: str) -> list[dict[str, Any]]:
    """Every answer to a research question Results shows for the run, across its modules."""
    shown = api.get(f"{_run_url(world, run_id)}/analysis")
    assert shown.status_code == 200, shown.text
    return [a for m in shown.json()["modules"].values() for a in m["research_question_answers"]]


def _report(api: TestClient, world: Any, run_id: str) -> tuple[dict[str, Any], str, bytes]:
    """The report card's status, and the document its download serves, with its text."""
    status = api.get(f"{_run_url(world, run_id)}/report")
    assert status.status_code == 200, status.text
    download = api.get(f"{_run_url(world, run_id)}/report/download")
    assert download.status_code == 200, download.text
    # The draft the card shows is the one downloaded (approval reads this header).
    assert download.headers["X-AIA-Artifact-Id"] == status.json()["artifact_id"]
    body = zipfile.ZipFile(io.BytesIO(download.content)).read("word/document.xml").decode()
    return dict(status.json()), body, download.content


# --------------------------------------------------------------------------- #
# Scenarios 1-2: a research question measured, one not
# --------------------------------------------------------------------------- #


def test_a_measured_and_an_unmeasured_research_question_read_the_same_from_readiness_to_report(
    api: TestClient, world: Any, worker_for: Callable[..., Worker]
) -> None:
    """One truth about which research question the run can answer, from readiness to report.

    Each surface was built and tested on its own: readiness's trace, the start's gate, the run's
    record, Results' answers (PC2) and the report's chapter. Nothing held them to one another.
    """
    _fieldwork(api, FieldworkSource.AI_RUNTIME)
    revision = _submit(api, world, GAPPED)

    # Readiness: the design runs, and it says which question it cannot answer, and why.
    ready = _readiness(api, world, revision)
    assert ready["ready"] is True
    answer = ready["answerability"]
    assert answer["capable"] is False and answer["acknowledgement_required"] is True
    assert [(g["research_question"], g["reasons"]) for g in answer["gaps"]] == [
        (RQ_UNMEASURED, ["unmeasured"])
    ]
    traced = {q["text"]: q for q in ready["research_trace"]["questions"]}
    assert (traced[RQ_MEASURED]["measures"], traced[RQ_MEASURED]["verdict"]) == (
        ["q1"],
        "ANSWERABLE",
    )
    assert (traced[RQ_UNMEASURED]["measures"], traced[RQ_UNMEASURED]["verdict"]) == (
        [],
        "UNANSWERABLE",
    )

    # The start: refused without a decision, naming the same gap under the same digest...
    url = f"{_study(world)}/research/runs"
    refused = api.post(url, json={"design_revision_id": revision})
    assert (
        refused.status_code == 409 and refused.json()["code"] == "research_questions_unanswerable"
    )
    assert refused.json()["details"]["gaps"] == answer["gaps"]
    assert refused.json()["details"]["digest"] == answer["digest"]
    # ...and started with it: the run records what readiness said, and the decision.
    run = _start(api, world, revision)
    assert run["created"] is True
    recorded = run["answerability"]
    assert (recorded["digest"], recorded["gaps"]) == (answer["digest"], answer["gaps"])
    assert recorded["acknowledgement"]["reason"] == REASON

    models = ScriptedModels()
    endings = _drain(worker_for(models, ai_fieldwork=True))
    assert endings and set(endings) == {"completed"}, endings
    finished = api.get(_run_url(world, run["run_id"])).json()
    assert finished["status"] == "COMPLETED"
    assert finished["answerability"] == recorded, "the record is frozen at start"

    # Results: an answer to the unmeasured question says so; one to the measured one does not.
    answers = _answers(api, world, run["run_id"])
    assert {a["question"] for a in answers} == {RQ_MEASURED, RQ_UNMEASURED}
    gapped = [a for a in answers if a["question"] == RQ_UNMEASURED]
    assert gapped and all(a["gap"] for a in gapped)
    assert all(a["gap"] is None for a in answers if a["question"] == RQ_MEASURED)

    # The report: the same question, the same words, once; the decision that let it run.
    report, body, _ = _report(api, world, run["run_id"])
    assert report["state"] == "READY" and report["review_state"] == "DRAFT_UNAPPROVED"
    assert body.count("Bez doložené odpovědi") == 1
    assert all(a["gap"] in body for a in gapped)
    assert REASON in body
    assert RQ_MEASURED in body and "běh na ni mohl odpovědět" in body


# --------------------------------------------------------------------------- #
# Scenario 4: the design changes after a run
# --------------------------------------------------------------------------- #


def test_a_runs_results_and_report_stay_its_revisions_when_the_design_changes(
    api: TestClient, world: Any, worker_for: Callable[..., Worker]
) -> None:
    """A run is its revision's for good; a new revision is never answered with an old run."""
    _fieldwork(api, FieldworkSource.SYNTHETIC_FIXTURE)
    worker = worker_for(ScriptedModels())
    first_revision = _submit(api, world, GAPPED)
    first = _start(api, world, first_revision)
    assert set(_drain(worker)) == {"completed"}
    first_report, first_body, first_bytes = _report(api, world, first["run_id"])
    assert first_body.count("Bez doložené odpovědi") == 1

    # The design changes: q2 now measures the question the first run could not answer.
    second_revision = _submit(api, world, REVISED)
    assert second_revision != first_revision
    listed = api.get(f"{_study(world)}/design/revisions").json()["items"]
    assert [r["revision_id"] for r in listed][:2] in (
        [second_revision, first_revision],
        [first_revision, second_revision],
    )

    # The first run is still the first revision's, read from its own record, never re-judged
    # against today's design: its gap stays, on the run, on Results and in its report.
    again = api.get(_run_url(world, first["run_id"])).json()
    assert (again["design_revision_id"], again["design_revision"]) == (first_revision, 1)
    assert [g["research_question"] for g in again["answerability"]["gaps"]] == [RQ_UNMEASURED]
    assert any(
        a["gap"] for a in _answers(api, world, first["run_id"]) if a["question"] == RQ_UNMEASURED
    )
    still, _, still_bytes = _report(api, world, first["run_id"])
    assert (still["artifact_id"], still_bytes) == (first_report["artifact_id"], first_bytes)

    # The new revision is judged on its own: nothing unanswered, and its start is a new run.
    assert _readiness(api, world, second_revision)["answerability"]["gaps"] == []
    second = _start(api, world, second_revision)
    assert second["created"] is True and second["run_id"] != first["run_id"]
    assert (second["design_revision_id"], second["design_revision"]) == (second_revision, 2)
    assert second["answerability"]["gaps"] == []
    assert set(_drain(worker)) == {"completed"}
    assert not any(a["gap"] for a in _answers(api, world, second["run_id"]))
    second_report, second_body, _ = _report(api, world, second["run_id"])
    assert second_report["artifact_id"] != first_report["artifact_id"]
    assert "Bez doložené odpovědi" not in second_body

    # The run list names each run's revision, newest first; the old report is unchanged.
    runs = api.get(f"{_study(world)}/research/runs").json()["items"]
    assert [(r["run_id"], r["design_revision"]) for r in runs] == [
        (second["run_id"], 2),
        (first["run_id"], 1),
    ]
    assert _report(api, world, first["run_id"])[2] == first_bytes


# --------------------------------------------------------------------------- #
# Scenario 5: a provider throttles, then recovers
# --------------------------------------------------------------------------- #


def _throttled() -> HttpResponse:
    return HttpResponse(
        status=429,
        headers={
            "x-amzn-requestid": "req-throttled",
            "x-amzn-errortype": "ThrottlingException",
            "retry-after": "60",
        },
        body={"message": "ThrottlingException"},
    )


def test_a_throttled_module_waits_visibly_and_the_same_run_finishes_paying_each_call_once(
    api: TestClient, world: Any, worker_for: Callable[..., Worker]
) -> None:
    """The run, its report and the actions offered agree while a provider wait clears itself."""
    _fieldwork(api, FieldworkSource.SYNTHETIC_FIXTURE)
    executive = analysis_node_key(AnalysisModuleId.EXECUTIVE)
    models = ScriptedModels(failures={("executive", 1): _throttled()})
    worker = worker_for(models)
    run_id = _start(api, world, _submit(api, world, REVISED))["run_id"]
    _drain(worker)

    # While it waits: the step says why, the run is waiting (not failed, not finished), and its
    # report waits behind the module -- never failed, never stored.
    run = api.get(_run_url(world, run_id)).json()
    steps = {s["node_key"]: s for s in run["steps"]}
    assert (steps[executive]["status"], steps[executive]["failure_class"]) == (
        "WAITING_PROVIDER",
        "QUOTA",
    )
    assert (run["phase"], run["is_terminal"], run["retryable"]) == ("WAITING", False, False)
    assert steps["report"]["status"] == "BLOCKED"
    assert api.get(f"{_run_url(world, run_id)}/report").json()["state"] == "BLOCKED"
    # Nothing a person could press pays again: no resume (it is no runtime park), no retry.
    resume = api.post(f"{_run_url(world, run_id)}/resume")
    assert resume.status_code == 409 and resume.json()["code"] == "runtime_park_not_resumable"
    retry = api.post(f"{_run_url(world, run_id)}/retry")
    assert retry.status_code == 409 and retry.json()["code"] == "run_not_retryable"

    # The provider's reset passes: the worker's own sweep offers the step again.
    with world.sessions() as session:
        resumed = WorkQueue(session).resume_waiting_steps(
            now=datetime.now(UTC) + timedelta(seconds=61)
        )
        session.commit()
    assert resumed == [steps[executive]["step_id"]]
    assert set(_drain(worker)) == {"completed"}

    done = api.get(_run_url(world, run_id)).json()
    assert (done["status"], done["run_id"]) == ("COMPLETED", run_id), "the same run, not a retry"
    assert api.get(f"{_run_url(world, run_id)}/report").json()["state"] == "READY"
    # Every call paid once: the throttled one charged nothing, the module asked once more.
    assert models.calls("executive") == [1, 2]
    assert all(models.calls(m.value) == [1] for m in AnalysisModuleId if m.value != "executive")
    with world.sessions() as session:
        ledger = AIUsageRepository(session, world.lead_scope(session)).events(run_id=run_id)
    executive_step = steps[executive]["step_id"]
    assert [e.outcome for e in ledger if e.step_id == executive_step] == [
        UsageOutcome.DISPATCHED,
        UsageOutcome.FAILED,
        UsageOutcome.DISPATCHED,
        UsageOutcome.SUCCEEDED,
    ]
    assert done["actual_cost_usd"] == pytest.approx(len(AnalysisModuleId) * ANALYSIS_CALL_USD)


# --------------------------------------------------------------------------- #
# Scenario 6: a delivered study
# --------------------------------------------------------------------------- #


def test_a_delivered_study_keeps_its_results_and_refuses_new_work_under_one_code(
    api: TestClient, world: Any, worker_for: Callable[..., Worker]
) -> None:
    """After delivery, what reads, downloads and approves what the study holds works; anything
    that would change its design or start or continue work is refused as ``study_closed``."""
    _fieldwork(api, FieldworkSource.SYNTHETIC_FIXTURE)
    study = _study(world)
    workspace = f"{study}/workspace"
    saved = api.put(f"{workspace}/content", json={"content": REVISED})
    assert saved.status_code == 200, saved.text
    # Before delivery: a run that finished with its report, and one whose analysis the model
    # could not ground, so it failed -- a run and modules a person could ask again while open.
    run_id = _start(api, world, _submit(api, world, REVISED))["run_id"]
    assert set(_drain(worker_for(ScriptedModels()))) == {"completed"}
    failed_id = _start(api, world, _submit(api, world, REFUSED))["run_id"]
    assert _drain(worker_for(ScriptedModels(invent={"objects"})))[-1] == "failed"
    failed = api.get(_run_url(world, failed_id)).json()
    assert (failed["status"], failed["retryable"]) == ("FAILED", True)
    retryable = api.get(f"{_run_url(world, failed_id)}/analysis/retryable").json()
    assert retryable["modules"] == ["objects"]
    unstarted = _submit(api, world, _design(n=220, tea_measured=True))
    report, _, document = _report(api, world, run_id)

    delivered = api.put(f"{study}/status", json={"status": "DELIVERED"})
    assert delivered.status_code == 200, delivered.text
    frame = api.get(workspace).json()
    assert (frame["can_edit"], frame["can_review"]) == (False, True)
    assert frame["study"]["delivered_at"] is not None

    # What the study holds stays readable, downloadable and approvable.
    for path in ("", "/analysis", "/report"):
        assert api.get(f"{_run_url(world, run_id)}{path}").status_code == 200, path
    assert api.get(f"{study}/research/runs").status_code == 200
    assert _report(api, world, run_id)[2] == document
    approved = api.post(
        f"{_run_url(world, run_id)}/report/approve", json={"artifact_id": report["artifact_id"]}
    )
    assert approved.status_code == 200, approved.text
    # What it learned may still be proposed to its client's knowledge: the client's, not the
    # study's work, and a person decides it there (whether delivery freezes this is D-1's).
    proposed = api.post(
        f"{study}/knowledge-proposals",
        json={"kind": "FINDING", "title": "Fiktivní zjištění", "content": {"text": "Káva."}},
    )
    assert proposed.status_code == 201, proposed.text

    # Every new piece of work is refused, and under one code: never a role the person holds.
    work = {
        "save the working content": ("put", f"{workspace}/content", {"content": GAPPED}),
        "import a questionnaire": (
            "post",
            f"{workspace}/questionnaire-import",
            {"filename": "dotaznik.csv", "data_b64": "c2VrY2U7b3RhemthCkE7Qgo="},
        ),
        "attach a file": (
            "post",
            f"{workspace}/attachments",
            {"filename": "zadani.txt", "data_b64": "RmlrdGl2bsOtIHphZMOhbsOt"},
        ),
        "submit a design": (
            "post",
            f"{study}/design/revisions",
            {"content": GAPPED, "source_stage": "run", "workspace_revision": 1},
        ),
        "start a run": ("post", f"{study}/research/runs", {"design_revision_id": unstarted}),
        "retry the failed run": ("post", f"{_run_url(world, failed_id)}/retry", None),
        "retry its analysis": ("post", f"{_run_url(world, failed_id)}/analysis/retry", None),
        "resume a run": ("post", f"{_run_url(world, run_id)}/resume", None),
        "lift a budget wait": (
            "post",
            f"{_run_url(world, run_id)}/steps/run/budget",
            {"budget_usd": 50},
        ),
        "ask an AI agent": (
            "post",
            f"{study}/research/agent-jobs",
            {"design_revision_id": unstarted, "action": "critique_design"},
        ),
        "start Deep Research": (
            "post",
            f"{study}/deep-research/runs",
            {"design_revision_id": unstarted, "preset_name": "QUICK"},
        ),
    }
    answered = {
        what: getattr(api, method)(url, **({"json": body} if body is not None else {}))
        for what, (method, url, body) in work.items()
    }
    refusals = {what: (r.status_code, r.json().get("code")) for what, r in answered.items()}
    assert refusals == dict.fromkeys(work, (403, "study_closed")), refusals
    # Nothing was made: the same two runs, no agent job, no Deep Research run.
    assert [r["run_id"] for r in api.get(f"{study}/research/runs").json()["items"]] == [
        failed_id,
        run_id,
    ]
    assert api.get(f"{study}/research/agent-jobs").json() == []
    assert api.get(f"{study}/deep-research/runs").json() in ([], {"items": []})

    # Reopened, the same person may work again.
    assert api.put(f"{study}/status", json={"status": "ACTIVE"}).status_code == 200
    assert api.get(workspace).json()["can_edit"] is True
    assert (
        api.post(f"{study}/research/runs", json={"design_revision_id": unstarted}).status_code
        == 201
    )
