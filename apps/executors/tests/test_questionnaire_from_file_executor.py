"""A questionnaire table given to the Lead, through the real worker (lead-orchestration LO18b).

The proposal is built by code before any gateway: the worker answers it with design jobs switched
off, no model call or reservation is ledgered, and the person's accept writes it like any other.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from aia_core.application.research import ResearchAgentJobs
from aia_core.domain.design import DesignRejected
from aia_core.domain.questionnaire_from_file import ImportMode
from aia_core.domain.workflow import WorkflowRunStatus
from aia_core.infrastructure.questionnaire_file import import_questionnaire
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository
from aia_core.infrastructure.tables import AIUsageEventRow, BudgetReservationRow
from aia_executors.registry import registry_for
from aia_executors.research_agents import ResearchAgentExecutor
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy import func, select

TABLE = (
    Path(__file__).resolve().parents[3]
    / "packages/aia_core/tests/fixtures/questionnaire_import/inputs/aia_sablona.xlsx"
)
SOURCE = {"source_id": "SRC-0000000000000001", "sha256": "a" * 64, "filename": "dotaznik.xlsx"}
EXISTING = {
    "id": "mine",
    "type": "questions",
    "title": "Nákupní záměr",
    "questions": [
        {"id": "my_q", "text": "Jak pravděpodobné je, že byste produkt koupil/a?", "typ": "skala"}
    ],
}


def worker(world: Any, database_url: str, store: Any, build: Any) -> Worker:
    """A worker whose design jobs are switched off: no gateway and no configuration."""
    executor = ResearchAgentExecutor(store=store, build=build, gateway=None, config=None)
    return Worker(
        session_factory=world.sessions,
        executors=registry_for(store=store, build=build, research_agent=executor),
        settings=WorkerSettings(
            database_url=database_url,
            worker_id="from-file-test",
            executors="aia_executors.registry:build_registry",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


def _file(world: Any, content: dict[str, Any], mode: ImportMode, key: str = "k") -> str:
    sections = import_questionnaire(TABLE.read_bytes(), "dotaznik.xlsx").sections
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=content, source_stage="questionnaire"
        )
        run_id = (
            ResearchAgentJobs(session, scope)
            .start_import(
                design_revision_id=revision.revision_id,
                key=f"questionnaire_import:{key}",
                sections=sections,
                mode=mode,
                source=SOURCE,
            )
            .run_id
        )
        session.commit()
    return run_id


def _accept(world: Any, store: Any, run_id: str) -> list[dict[str, Any]]:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        jobs = ResearchAgentJobs(session, scope)
        revision = jobs.get(run_id)["metadata"]["design_revision_id"]
        working = StudyWorkspaceRepository(session).content(scope).revision
        assert working is not None
        jobs.accept(
            run_id,
            store=store,
            expected_revision_id=revision,
            expected_workspace_revision=working,
        )
        session.commit()
        return list(StudyWorkspaceRepository(session).content(scope).content["sections"])


def test_a_table_on_an_empty_study_is_built_with_no_model_and_accepted_as_imported(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    run_id = _file(world, {"title": "S", "sections": []}, ImportMode.REPLACE)
    # Design jobs switched off: the worker has no gateway and still answers the table's job.
    assert worker(world, database_url, store, build).run_once()
    with world.sessions() as session:
        scope = world.lead_scope(session)
        run = ResearchAgentJobs(session, scope).get(run_id)
        assert run["status"] is WorkflowRunStatus.COMPLETED
        assert run["metadata"]["origin"] == "file" and run["metadata"]["mode"] == "replace"
        assert session.scalar(select(func.count()).select_from(AIUsageEventRow)) == 0
        assert session.scalar(select(func.count()).select_from(BudgetReservationRow)) == 0
    sections = _accept(world, store, run_id)
    imported = import_questionnaire(TABLE.read_bytes(), "dotaznik.xlsx").sections
    assert [s["title"] for s in sections] == [s["title"] for s in imported]
    assert [q["text"] for s in sections for q in s.get("questions", [])] == [
        q["text"] for s in imported for q in s.get("questions", [])
    ]


def test_doplnit_adds_only_the_questions_not_there(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    run_id = _file(world, {"title": "S", "sections": [EXISTING]}, ImportMode.ADD)
    assert worker(world, database_url, store, build).run_once()
    sections = _accept(world, store, run_id)
    texts = [q["text"] for s in sections for q in s.get("questions", [])]
    assert texts.count("Jak pravděpodobné je, že byste produkt koupil/a?") == 1
    assert sections[0]["id"] == "mine" and [s["title"] for s in sections] == [
        "Nákupní záměr",
        "Bariéry",
        "Média",
    ]


def test_nahradit_replaces_the_questions(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    run_id = _file(world, {"title": "S", "sections": [EXISTING]}, ImportMode.REPLACE)
    assert worker(world, database_url, store, build).run_once()
    sections = _accept(world, store, run_id)
    assert "mine" not in [s["id"] for s in sections]
    assert [s["title"] for s in sections] == ["Nákupní záměr", "Bariéry", "Média"]


def test_the_same_key_files_once_and_a_files_proposal_is_never_rebuilt(world: Any) -> None:
    first = _file(world, {"title": "S", "sections": []}, ImportMode.REPLACE, key="same")
    again = _file(world, {"title": "S", "sections": []}, ImportMode.REPLACE, key="same")
    assert first == again
    with world.sessions() as session:
        scope = world.lead_scope(session)
        latest = StudyDesignRepository(session, scope).latest()
        assert latest is not None
        with pytest.raises(DesignRejected) as refused:
            ResearchAgentJobs(session, scope).rebuild(first, design_revision_id=latest.revision_id)
        assert refused.value.reason == "from_file"
