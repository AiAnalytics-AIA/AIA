"""Deep Research runs (ADR 0017, plan decisions I-8 and I-9): frozen, scoped, idempotent.

What is pinned here: a run freezes its request at enqueue and a later approval does
not reach it; the request holds only the Study's own client's knowledge; starting is
idempotent per request; a run, its bundle and its snapshots are found only through
the Study's own design and the run's type; there is no default depth; and nothing
here registers the workflow type.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aia_core.application.deep_research import (
    BundleNotReady,
    DeepResearchRunNotFound,
    DeepResearchRunNotRetryable,
    DeepResearchRuns,
    NothingToResearch,
    ResearchTargetInvalid,
    ResearchTargetNotFound,
    RunNotGoverned,
    RunSpecCorrupt,
    governed_record,
)
from aia_core.application.research import ResearchRuns
from aia_core.domain.deep_research.contracts import Channel, SubjectKind
from aia_core.domain.deep_research.integration import (
    RUN_SPEC_CONTRACT,
    DesignLineage,
    DesignRevisionTarget,
    PurposeSource,
    ResultQuestionTarget,
)
from aia_core.domain.deep_research.planning import UnknownPreset
from aia_core.domain.deep_research.workflow import (
    DEEP_RESEARCH,
    DEEP_RESEARCH_KINDS,
    NODE_ORDER,
    deep_research_steps,
)
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.knowledge import KnowledgeKind
from aia_core.domain.scope import ClientContext, ScopeDenied, StudyStatus
from aia_core.domain.workflow import StepRunStatus, WorkflowRunStatus
from aia_core.domain.workflow_templates import WORKFLOW_TYPES
from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import (
    DesignRevisionNotFound,
    StudyDesignRepository,
)
from aia_core.infrastructure.workflow_repository import WorkflowRepository

DESIGN: dict[str, Any] = {
    "title": "Rostlinné nápoje",
    "goal": "Zjistit, kdo v Česku pije rostlinné nápoje a proč.",
    "briefing": "Značka zvažuje uvedení ovesného nápoje.",
    "research_plan": {
        "research_questions": [
            "Jak roste trh rostlinných nápojů v Česku?",
            "Proč lidé přecházejí na rostlinné nápoje?",
        ]
    },
    "sections": [
        {
            "type": "questions",
            "questions": [
                {
                    "id": "q1",
                    "text": "Kupujete rostlinné nápoje?",
                    "kategorie": ["Ano", "Ne"],
                }
            ],
        },
        {
            "type": "object_battery",
            "objects": ["Ovesný nápoj", "Mandlový nápoj"],
            "object_question": "Jak hodnotíte {object}?",
        },
    ],
}


@pytest.fixture
def runs(session: Any, scoped: Any) -> Any:
    """``runs(user=…, study=…)``: the Deep Research runs of a user's scope on a study."""
    return lambda **kw: DeepResearchRuns(session, scoped.scope(**kw))


@pytest.fixture
def design(session: Any, scoped: Any) -> Any:
    """``design(content, study=…)``: submit a design as the lead, return its revision id."""

    def submit(content: dict[str, Any] = DESIGN, *, study: str = "primary") -> str:
        user = "other_lead" if study == "other_client" else "lead"
        repo = StudyDesignRepository(session, scoped.scope(user=user, study=study))
        revision, _ = repo.submit(content=content, source_stage="brief")
        return revision.revision_id

    return submit


def _client(scoped: Any, user: str, client: str = "primary") -> ClientContext:
    return scoped.resolver.client_context(  # type: ignore[no-any-return]
        scoped.principal(scoped.users[user]), client_id=scoped.clients[client].client_id
    )


@pytest.fixture
def approve(session: Any, scoped: Any) -> Any:
    """``approve(kind, title, text, client=…)``: an approved knowledge item of a client."""

    def add(kind: KnowledgeKind, title: str, text: str = "", *, client: str = "primary") -> str:
        repo = ClientKnowledgeRepository(session)
        proposer, approver = (
            ("researcher", "reviewer")
            if client == "primary"
            else (
                "other_lead",
                "owner",
            )
        )
        if client != "primary":
            scoped.scope_repo.set_self_approval(
                scoped.admin_context, allowed=True, client_id=scoped.clients[client].client_id
            )
        proposal = repo.propose(
            _client(scoped, proposer, client),
            kind=kind,
            title=title,
            content={"text": text} if text else {},
        )
        decided = repo.decide(
            _client(scoped, proposer if client != "primary" else approver, client),
            proposal_id=proposal.proposal_id,
            approve=True,
        )
        assert decided.item_id is not None
        return decided.item_id

    return add


# --------------------------------------------------------------------------- start


def test_a_run_freezes_its_request_and_enqueues_the_six_steps(
    runs: Any, design: Any, approve: Any
) -> None:
    approve(KnowledgeKind.FACT, "Ovesné nápoje tvoří polovinu prodejů", "Podle panelu 2025.")
    revision_id = design()
    started = runs().start(design_revision_id=revision_id, preset_name="QUICK")
    run = started.run

    assert started.created and started.workflow_type == DEEP_RESEARCH
    assert [s["node_key"] for s in run["steps"]] == list(NODE_ORDER)
    assert [s["kind"] for s in run["steps"]] == [DEEP_RESEARCH_KINDS[n] for n in NODE_ORDER]
    assert [s["status"] for s in run["steps"]] == [StepRunStatus.RUNNABLE] + [
        StepRunStatus.BLOCKED
    ] * 5
    assert all(s["stage_type"] == "DEEP_RESEARCH" for s in run["steps"])

    request = runs().freeze(design_revision_id=revision_id, preset_name="QUICK")
    assert run["metadata"]["request_fingerprint"] == request.fingerprint()
    assert run["metadata"]["design_revision_id"] == revision_id
    assert run["metadata"]["knowledge_items"] == 1
    kinds = [s.kind for s in request.subjects]
    assert kinds == [SubjectKind.QUESTION] * 2 + [SubjectKind.OBJECT] * 2
    assert [q.id for q in request.questionnaire] == ["q1", "section_2_obj_1", "section_2_obj_2"]
    terms = {(t.source, t.term) for t in request.client_terms}
    assert {
        ("client.name", "Acme Corp"),
        ("client.slug", "acme"),
        ("study.name", "Acme brand"),
        ("study.slug", "brand-2026"),
    } <= terms


def test_the_type_is_not_registered_here() -> None:
    """``deep_research`` is created from the domain's own step graph, not a template.

    Its executors are in the worker's default registry and its route in the API; the
    type is still not a ``WORKFLOW_TYPES`` template (the service builds the graph)."""
    assert DEEP_RESEARCH not in WORKFLOW_TYPES


def test_starting_twice_is_one_run_and_an_approval_in_between_is_a_new_one(
    runs: Any, design: Any, approve: Any
) -> None:
    revision_id = design()
    first = runs().start(design_revision_id=revision_id, preset_name="QUICK")
    again = runs().start(design_revision_id=revision_id, preset_name="QUICK")
    assert not again.created and again.run_id == first.run_id

    approve(KnowledgeKind.FACT, "Rostlinné nápoje rostou", "Meziročně o 12,5 %.")
    after = runs().start(design_revision_id=revision_id, preset_name="QUICK")
    assert after.created and after.run_id != first.run_id
    # The queued job did not change: it holds what it froze.
    assert runs().get(first.run_id)["metadata"]["knowledge_items"] == 0
    assert runs().get(after.run_id)["metadata"]["knowledge_items"] == 1

    other_depth = runs().start(design_revision_id=revision_id, preset_name="STANDARD")
    assert other_depth.created and other_depth.run_id not in {first.run_id, after.run_id}
    web_only = runs().start(
        design_revision_id=revision_id, preset_name="QUICK", channels=(Channel.WEB,)
    )
    assert web_only.created and web_only.run["metadata"]["channels"] == ["WEB"]


def test_the_request_holds_only_the_studys_own_clients_knowledge(
    runs: Any, design: Any, approve: Any
) -> None:
    approve(KnowledgeKind.FACT, "Acme: ovesné nápoje", "Vlastní data klienta.")
    approve(KnowledgeKind.FACT, "Globex: mandlové nápoje", "Data jiného klienta.", client="other")
    request = runs().freeze(design_revision_id=design(), preset_name="QUICK")
    assert [k.title for k in request.knowledge.items] == ["Acme: ovesné nápoje"]
    assert "Globex" not in request.model_dump_json()


def test_there_is_no_default_depth_and_an_empty_design_has_nothing_to_research(
    runs: Any, design: Any
) -> None:
    revision_id = design()
    with pytest.raises(UnknownPreset):
        runs().start(design_revision_id=revision_id, preset_name="")
    with pytest.raises(NothingToResearch):
        runs().start(design_revision_id=design({"title": "", "goal": ""}), preset_name="QUICK")


def test_another_studys_revision_is_not_this_studys_to_research(runs: Any, design: Any) -> None:
    sibling_revision = design(study="sibling")
    with pytest.raises(DesignRevisionNotFound):
        runs().start(design_revision_id=sibling_revision, preset_name="QUICK")
    with pytest.raises(DesignRevisionNotFound):
        runs().start(design_revision_id=design(study="other_client"), preset_name="QUICK")


def test_every_person_with_the_study_starts_and_cancels_a_deep_research_run(
    scoped: Any, runs: Any, design: Any
) -> None:
    """ADR 0019: one role holds RUN_WORKFLOW and CANCEL_WORKFLOW.

    The viewer was refused a start and the reviewer a cancel; both are Researchers now. What
    still bounds a run: no grant means no study scope, and a closed study accepts no new work.
    """
    revision_id = design()
    run_id = runs(user="viewer").start(design_revision_id=revision_id, preset_name="QUICK").run_id
    assert runs(user="reviewer").get(run_id)["run_id"] == run_id
    assert runs(user="reviewer").cancel(run_id) is WorkflowRunStatus.CANCELLED
    # A member who was never granted the study is a member (ADR 0019): they read the run too.
    assert runs(user="outsider").get(run_id)["run_id"] == run_id
    scoped.scope_repo.set_study_status(scoped.scope(), status=StudyStatus.DELIVERED)
    with pytest.raises(ScopeDenied) as closed:
        runs(user="viewer").start(design_revision_id=revision_id, preset_name="QUICK")
    assert closed.value.reason == "study_closed"


# --------------------------------------------------------------------------- read


def test_a_run_is_found_only_through_its_own_study_and_type(
    session: Any, scoped: Any, runs: Any, design: Any
) -> None:
    run_id = runs().start(design_revision_id=design(), preset_name="QUICK").run_id
    assert [r["run_id"] for r in runs().runs()] == [run_id]

    design(study="sibling")
    with pytest.raises(DeepResearchRunNotFound):
        runs(study="sibling").get(run_id)
    assert runs(study="sibling").runs() == []
    with pytest.raises(DeepResearchRunNotFound):
        runs(user="other_lead", study="other_client").get(run_id)

    # A research run of the same Study is not a Deep Research run, nor the reverse.
    research = ResearchRuns(session, scoped.scope())
    research_run = research.start(
        design_revision_id=design(
            {**DESIGN, "n": 300, "sections": DESIGN["sections"][:1]}  # a runnable design
        ),
        fieldwork_source=FieldworkSource.AI_RUNTIME,
    )
    with pytest.raises(DeepResearchRunNotFound):
        runs().get(research_run.run_id)
    assert [r["run_id"] for r in runs().runs()] == [run_id]


def test_nothing_is_read_before_the_run_publishes(runs: Any, design: Any) -> None:
    run_id = runs().start(design_revision_id=design(), preset_name="QUICK").run_id
    store = InMemoryArtifactStore()
    with pytest.raises(BundleNotReady):
        runs().bundle(run_id, store=store)
    with pytest.raises(BundleNotReady):
        runs().snapshot(run_id, "SNP-" + "0" * 24, store=store)
    with pytest.raises(DeepResearchRunNotFound):
        runs(study="sibling").bundle(run_id, store=store)


def test_a_failed_or_cancelled_run_is_retried_as_a_new_linked_run(runs: Any, design: Any) -> None:
    run_id = runs().start(design_revision_id=design(), preset_name="QUICK").run_id
    with pytest.raises(DeepResearchRunNotRetryable):
        runs().retry(run_id)  # a pending run resumes; it is not started again
    runs().cancel(run_id)
    retried = runs().retry(run_id)
    assert retried.created and retried.run_id != run_id
    assert retried.run["metadata"]["retry_of"] == run_id
    assert (
        retried.run["metadata"]["request_fingerprint"]
        == runs().get(run_id)["metadata"]["request_fingerprint"]
    )
    assert runs().retry(run_id).run_id == retried.run_id  # a double click is one retry
    # ADR 0019: a retry is not a second role's act; the former viewer's click is the same retry.
    assert runs(user="viewer").retry(run_id).run_id == retried.run_id


# --------------------------------------------------------------------------- ADR 0021


def _legacy_run(session: Any, scoped: Any, revision_id: str) -> str:
    """A run as develop stored one before ADR 0021: its metadata and its key, verbatim."""

    scope = scoped.scope()
    fixture = Path(__file__).parent / "fixtures" / "deep_research_pre_step1"
    metadata = json.loads((fixture / "run_metadata.json").read_text(encoding="utf-8"))
    metadata["design_revision_id"] = revision_id
    steps = deep_research_steps()
    project_id = StudyDesignRepository(session, scope).project_id()
    assert project_id is not None
    return WorkflowRepository(session, scope).create_run(
        project_id=project_id,
        project_revision=1,
        workflow_type=DEEP_RESEARCH,
        steps=steps,
        idempotency_key=f"{DEEP_RESEARCH}:{revision_id}:{metadata['request_fingerprint']}",
        metadata=metadata,
        fingerprints={s.node_key: metadata["request_fingerprint"] for s in steps},
    )


def test_a_governed_run_records_why_what_and_on_which_design(runs: Any, design: Any) -> None:
    revision_id = design()
    started = runs().start(
        design_revision_id=revision_id,
        preset_name="QUICK",
        purpose_source=PurposeSource.LEGACY_DEFAULT,
        title="Kontext trhu",
    )
    metadata = started.run["metadata"]
    spec = runs().freeze_design(design_revision_id=revision_id, preset_name="QUICK")
    assert metadata["integration_contract"] == RUN_SPEC_CONTRACT
    assert metadata["purpose"] == "DESIGN_RESEARCH"
    assert metadata["purpose_source"] == "LEGACY_DEFAULT"
    assert metadata["run_spec_fingerprint"] == spec.fingerprint()
    assert metadata["request_fingerprint"] == spec.engine_request_fingerprint()
    record = governed_record(metadata)
    assert record is not None
    # The durable round trip: what is stored is the spec, exactly.
    assert (record.purpose, record.target, record.lineage) == (
        spec.purpose,
        spec.target,
        spec.lineage,
    )
    assert record.title == "Kontext trhu"
    revision = runs()._designs().get(revision_id)
    assert spec.lineage == DesignLineage(
        kind="DESIGN",
        design_revision_id=revision_id,
        design_revision=revision.revision,
        design_content_sha256=revision.content_sha256,
    )
    # The title is not identity: the same spec untitled is the same run.
    again = runs().start(design_revision_id=revision_id, preset_name="QUICK")
    assert not again.created and again.run_id == started.run_id


def test_running_design_research_writes_no_design(runs: Any, design: Any) -> None:
    """Advisory only: freezing and starting leaves the Study's revisions as they were."""
    revision_id = design()
    before = [r.revision_id for r in runs()._designs().revisions(limit=50)]
    runs().start(design_revision_id=revision_id, preset_name="QUICK")
    runs().freeze_design(design_revision_id=revision_id, preset_name="STANDARD")
    assert [r.revision_id for r in runs()._designs().revisions(limit=50)] == before


def test_a_run_stored_before_adr_0021_reads_honestly_and_is_not_rewritten(
    session: Any, scoped: Any, runs: Any, design: Any
) -> None:
    revision_id = design()
    legacy = _legacy_run(session, scoped, revision_id)
    run = runs().get(legacy)
    assert governed_record(run["metadata"]) is None  # no purpose is made up for it
    assert "purpose" not in run["metadata"]
    assert [r["run_id"] for r in runs().runs()] == [legacy]
    with pytest.raises(RunNotGoverned):
        runs().provenance(legacy, store=InMemoryArtifactStore())
    # A new start over the same revision is a new, governed run: the old key is not reused.
    governed = runs().start(design_revision_id=revision_id, preset_name="QUICK")
    assert governed.created and governed.run_id != legacy
    assert runs().get(legacy)["metadata"] == run["metadata"]  # history untouched
    # Its retry is a new Design Research run through the legacy rule, said so.
    runs().cancel(legacy)
    retried = runs().retry(legacy)
    assert retried.run["metadata"]["purpose"] == "DESIGN_RESEARCH"
    assert retried.run["metadata"]["purpose_source"] == "LEGACY_DEFAULT"
    assert retried.run["metadata"]["retry_of"] == legacy


def test_a_stored_spec_that_no_longer_hashes_is_refused(runs: Any, design: Any) -> None:
    metadata = dict(runs().start(design_revision_id=design(), preset_name="QUICK").run["metadata"])
    metadata["purpose"] = "INTERPRETATION_RESEARCH"
    with pytest.raises(RunSpecCorrupt):
        governed_record(metadata)
    tampered = dict(runs().start(design_revision_id=design(), preset_name="QUICK").run["metadata"])
    tampered["lineage"] = {**tampered["lineage"], "design_content_sha256": "0" * 64}
    with pytest.raises(RunSpecCorrupt):
        governed_record(tampered)


def test_a_design_target_of_another_study_or_client_is_refused(runs: Any, design: Any) -> None:
    with pytest.raises(DesignRevisionNotFound):
        runs().freeze_design(design_revision_id=design(study="sibling"), preset_name="QUICK")
    with pytest.raises(DesignRevisionNotFound):
        runs().freeze_design(design_revision_id=design(study="other_client"), preset_name="QUICK")


def test_interpretation_needs_a_result_of_this_study(runs: Any, design: Any) -> None:
    store = InMemoryArtifactStore()
    revision_id = design()
    with pytest.raises(ResearchTargetInvalid):
        runs().freeze_interpretation(
            target=DesignRevisionTarget(kind="DESIGN_REVISION", design_revision_id=revision_id),
            preset_name="QUICK",
            store=store,
        )
    with pytest.raises(ResearchTargetNotFound):
        runs().freeze_interpretation(
            target=ResultQuestionTarget(
                kind="RESULT_QUESTION",
                research_run_id="RUN-0000000000000000",
                aggregate_artifact_id="ART-0000000000000000",
                question_id="q1",
            ),
            preset_name="QUICK",
            store=store,
        )
