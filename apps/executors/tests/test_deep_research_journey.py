"""Deep Research end to end, recorded: the real worker, gateway, adapter and retrieval gate.

The acceptance journey of the recorded/offline core (``.planning/plans/deep-research.md``,
chunk h). Nothing leaves the process: Bedrock's side is :class:`RecordedAgents`, one
recorded answer per agent keyed by what the agent is shown, and the web's side is
``fixtures/deep_research/web.json`` through the recorded composition. Everything
between is production code: the worker loop and its leases, ``StepModelCaller`` and
the governed gateway with the Bedrock adapter, the retrieval gate and the fetcher,
the executors, the artifacts, the application service.

The world is a fictional client (its designs are Class C). Its approved knowledge is
one FACT (Class B) and one DOCUMENT (Class A, whose text a planner query reproduces).
The test route is approved for Class B, so the internal channel can be exercised on
recorded exchanges; no deployed route is (D6), and the production-shaped test below
uses a Class C route, as develop has.
"""

from __future__ import annotations

import functools
import json
import re
import sys
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from aia_core.application.deep_research import DeepResearchRuns
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.application.web_retrieval import RetrievalGate
from aia_core.domain.deep_research.agents import AgentRole
from aia_core.domain.deep_research.bundle import EvidenceBundle
from aia_core.domain.deep_research.contracts import (
    HARNESS_VERSION,
    Channel,
    ClientTerm,
    EvidenceOrigin,
    QualityStatus,
    QuarantineReason,
    QueryDecision,
    RetrievalMode,
    SourceKind,
    StopReason,
    SubjectKind,
    TrackStatus,
    subject_key,
    track_id,
)
from aia_core.domain.deep_research.grounding import locate_quote, normalise_text
from aia_core.domain.deep_research.merge import RespondentUse
from aia_core.domain.deep_research.quarantine import (
    RecordedEvidenceRefused,
    require_live_evidence,
    respondent_context,
)
from aia_core.domain.deep_research.request_limits import (
    RESEARCH_KINDS,
    ModelPrices,
    RequestLimits,
    kind_budgets,
    kind_of,
)
from aia_core.domain.deep_research.synthesis import SynthesisStatus
from aia_core.domain.deep_research.tooling import TOOL_EVENT_KINDS, ToolOutcome
from aia_core.domain.deep_research.workflow import DEEP_RESEARCH, deep_research_steps
from aia_core.domain.knowledge import KnowledgeKind
from aia_core.domain.residency import DataClass
from aia_core.domain.scope import StudyContext, StudyStatus
from aia_core.domain.workflow import StepRunStatus, WorkflowRunStatus
from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import StepAttemptRow
from aia_core.infrastructure.web_retrieval import RecordedSearch
from aia_core.infrastructure.workflow_repository import WorkflowRepository, WorkQueue
from aia_executors.ai_runtime import AIRuntimeConfigError, build_gateway
from aia_executors.deep_research import (
    DeepResearchConfig,
    DeepResearchRuntime,
    StepToolMeter,
    deep_research_registry,
)
from aia_executors.deep_research import runtime as deep_research_runtime_module
from aia_executors.deep_research_recorded import recorded_retrieval, recorded_runtime
from aia_executors.deep_research_runtime import deep_research_runtime
from aia_worker.executor import CancellationRequested
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from deep_research_fixtures import (
    ALMOND,
    ANSWERS,
    DESIGN,
    DESIGN_2,
    DEVELOP_ROUTE,
    FACT,
    OATS,
    PLAN_A,
    Q1,
    Q2,
    REASONING,
    SOY,
    WEB,
    RecordedAgents,
    Signer,
    ai_settings,
    recorded,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker


def tid(kind: SubjectKind, text: str, channel: Channel) -> str:
    return track_id(subject_key(kind, text), channel)


IN, WEB_ = Channel.INTERNAL, Channel.WEB
QS, OS = SubjectKind.QUESTION, SubjectKind.OBJECT


# --------------------------------------------------------------------------- #
# Bedrock's side, recorded
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# The world and the compositions
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ResearchWorld:
    """A fictional client with an ACTIVE study, a lead and a reviewer; another client too."""

    organization_id: str
    client_id: str
    study_id: str
    lead_id: str
    reviewer_id: str
    other_study_id: str
    other_lead_id: str
    sessions: sessionmaker[Session]

    def _principal(self, user_id: str) -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(user_id=user_id, organization_id=self.organization_id)

    def lead_scope(self, session: Session) -> StudyContext:
        return ScopeResolver(session).study_context(
            self._principal(self.lead_id), study_id=self.study_id
        )

    def other_scope(self, session: Session) -> StudyContext:
        return ScopeResolver(session).study_context(
            self._principal(self.other_lead_id), study_id=self.other_study_id
        )

    def approve(self, kind: KnowledgeKind, title: str, text: str) -> None:
        """Knowledge the lead proposes and the reviewer approves (ADR 0015)."""
        with self.sessions() as session:
            resolver, repo = ScopeResolver(session), ClientKnowledgeRepository(session)
            proposal = repo.propose(
                resolver.client_context(self._principal(self.lead_id), client_id=self.client_id),
                kind=kind,
                title=title,
                content={"text": text},
            )
            repo.decide(
                resolver.client_context(
                    self._principal(self.reviewer_id), client_id=self.client_id
                ),
                proposal_id=proposal.proposal_id,
                approve=True,
            )
            session.commit()


@pytest.fixture
def research(sessions: sessionmaker[Session]) -> ResearchWorld:
    return make_research_world(sessions)


def make_research_world(sessions: sessionmaker[Session]) -> ResearchWorld:
    """The journey's world in an empty database (the ``research`` fixture's)."""
    with sessions() as session:
        repo, resolver = ScopeRepository(session), ScopeResolver(session)
        org, owner = repo.create_organization(
            slug="aia", name="AIA", owner_email="owner@art-chain.io"
        )
        admin = resolver.organization_context(
            AuthenticatedPrincipal(user_id=owner.user_id, organization_id=org.organization_id)
        )
        client = repo.create_client(admin, slug="acme", name="Acme")
        other = repo.create_client(admin, slug="globex", name="Globex")
        study = repo.create_study(
            admin,
            client_id=client.client_id,
            slug="projekt-zelena",
            name="Projekt Zelená",
            budget_usd=25.0,
        )
        other_study = repo.create_study(
            admin,
            client_id=other.client_id,
            slug="projekt-modra",
            name="Projekt Modrá",
            budget_usd=25.0,
        )
        users = {}
        for label in ("lead", "reviewer", "other"):
            member = repo.add_member(admin, email=f"{label}@art-chain.io")
            users[label] = member.user_id
        session.flush()
        for user, study_id in (
            (users["lead"], study.study_id),
            (users["other"], other_study.study_id),
        ):
            scope = resolver.study_context(
                AuthenticatedPrincipal(user_id=user, organization_id=org.organization_id),
                study_id=study_id,
            )
            repo.set_study_status(scope, StudyStatus.ACTIVE)
        session.commit()
        return ResearchWorld(
            organization_id=org.organization_id,
            client_id=client.client_id,
            study_id=study.study_id,
            lead_id=users["lead"],
            reviewer_id=users["reviewer"],
            other_study_id=other_study.study_id,
            other_lead_id=users["other"],
            sessions=sessions,
        )


def worker(
    world: ResearchWorld,
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    runtime: DeepResearchRuntime | None,
) -> Worker:
    return Worker(
        session_factory=world.sessions,
        executors=deep_research_registry(store=store, build=build, runtime=runtime),
        settings=WorkerSettings(
            database_url=database_url,
            worker_id="deep-research-test",
            executors="aia_executors.registry:build_registry",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


def drain(w: Worker, *, limit: int = 20) -> int:
    """Run the worker until nothing is claimable; the number of attempts it made."""
    for n in range(limit):
        if w.run_once() is None:
            return n
    raise AssertionError("the worker kept finding work")


def start(world: ResearchWorld, content: dict[str, Any] = DESIGN, **kwargs: Any) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
            content=content, source_stage="brief"
        )
        run = DeepResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id, preset_name=kwargs.get("preset", "QUICK")
        )
        session.commit()
        return run.run_id


def read(
    world: ResearchWorld, run_id: str, store: InMemoryArtifactStore
) -> tuple[dict[str, Any], EvidenceBundle]:
    with world.sessions() as session:
        runs = DeepResearchRuns(session, world.lead_scope(session))
        return runs.get(run_id), runs.bundle(run_id, store=store)


def tool_events(world: ResearchWorld, run_id: str) -> list[dict[str, Any]]:
    with world.sessions() as session:
        events = DeepResearchRuns(session, world.lead_scope(session)).events(run_id, limit=2000)
    kinds = set(TOOL_EVENT_KINDS.values())
    return [e for e in events if e["message"] in kinds]


def approve_knowledge(world: ResearchWorld) -> None:
    world.approve(KnowledgeKind.FACT, OATS, FACT)
    world.approve(KnowledgeKind.DOCUMENT, "Interní plán uvedení", PLAN_A)


@dataclass(frozen=True)
class Journey:
    world: ResearchWorld
    agents: RecordedAgents
    worker: Worker
    runtime: DeepResearchRuntime
    run_id: str

    def web_calls(self) -> tuple[int, int]:
        """(searches, page requests) that reached the recorded web's transports."""
        retrieval = self.runtime.retrieval
        assert retrieval is not None and isinstance(retrieval.search, RecordedSearch)
        return len(retrieval.search.calls), len(retrieval.fetcher._transport.calls)  # type: ignore[attr-defined]


@pytest.fixture
def pass_one(
    research: ResearchWorld, database_url: str, store: InMemoryArtifactStore, build: Any
) -> Iterator[Journey]:
    approve_knowledge(research)
    agents = RecordedAgents(ANSWERS)
    runtime = recorded(research, agents)
    w = worker(research, database_url, store, build, runtime)
    run_id = start(research)
    assert drain(w) == 6
    yield Journey(world=research, agents=agents, worker=w, runtime=runtime, run_id=run_id)


# --------------------------------------------------------------------------- #
# Pass 1: every phase, a grounded bundle
# --------------------------------------------------------------------------- #


def test_pass_one_runs_every_phase_to_a_sealed_grounded_bundle(
    pass_one: Journey, store: InMemoryArtifactStore
) -> None:
    world, agents, run_id = pass_one.world, pass_one.agents, pass_one.run_id
    run, bundle = read(world, run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED
    assert [s["status"] for s in run["steps"]] == [StepRunStatus.SUCCEEDED] * 6
    assert bundle.verify() and bundle.request_fingerprint == run["metadata"]["request_fingerprint"]
    assert bundle.quality_status is QualityStatus.PARTIAL  # some tracks were blocked, and say why
    assert bundle.origins == (EvidenceOrigin.CLIENT_KNOWLEDGE, EvidenceOrigin.RECORDED_FIXTURE)
    assert bundle.fictional_client and bundle.client_facing is False

    tracks = {t.track_id: t for t in bundle.tracks}
    assert {k: (t.status, t.stop_reason) for k, t in tracks.items()} == {
        tid(QS, Q1, IN): (TrackStatus.COMPLETED, StopReason.SINGLE_PASS),
        tid(QS, Q1, WEB_): (TrackStatus.COMPLETED, StopReason.DEPTH_TARGET_MET),
        # Q2 matches only the Class A plan: the gateway refuses it before any request.
        tid(QS, Q2, IN): (TrackStatus.BLOCKED, StopReason.MODEL_ROUTE_REFUSED),
        tid(QS, Q2, WEB_): (TrackStatus.COMPLETED, StopReason.QUERIES_EXHAUSTED),
        tid(OS, OATS, IN): (TrackStatus.COMPLETED, StopReason.SINGLE_PASS),
        tid(OS, OATS, WEB_): (TrackStatus.COMPLETED, StopReason.QUERIES_EXHAUSTED),
        tid(OS, ALMOND, IN): (TrackStatus.COMPLETED, StopReason.SINGLE_PASS),
        # A known failure, then a search whose answer never came: stopped, not retried.
        tid(OS, ALMOND, WEB_): (TrackStatus.INCOMPLETE, StopReason.TOOL_OUTCOME_UNCERTAIN),
    }
    assert tracks[tid(QS, Q2, IN)].detail.startswith("model_route: ")
    assert not any(t.reused for t in bundle.tracks)

    # The queries code refused: the client's name (Class B) and the client's plan (Class A).
    refused = {
        q.text: (q.data_class, q.refusal)
        for t in bundle.tracks
        for q in t.queries
        if q.decision is QueryDecision.REFUSED
    }
    assert refused == {
        "Acme ovesný nápoj": (
            DataClass.CLASS_B_DERIVED_CLIENT,
            "egress_route_not_approved_for_class",
        ),
        "uvedení ovesného nápoje v květnu 2027 cena": (
            DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
            "class_a_query",
        ),
    }

    accepted = {a.evidence.claim: a for a in bundle.accepted}
    assert set(accepted) == {
        FACT,
        "Spotřeba rostlinných nápojů v Česku vzrostla v roce 2025 o 12,5 % na 41 milionů litrů.",
        "Rostlinné nápoje kupuje 45 % domácností.",
        "Tržby za rostlinné nápoje dosáhly v roce 2025 celkem 2,1 miliardy korun.",
        "Nejčastějším důvodem přechodu na rostlinné nápoje je podle 37 % respondentů zdraví",
        "U 22 % je důvodem ohled na životní prostředí.",
        "Průměrná cena ovesného nápoje byla v roce 2025 42 Kč za litr.",
    }
    # The same approved fact, found by three tracks, is one finding that remembers the others.
    assert len(accepted[FACT].merged_ids) == 2
    # Survey answers stay as alignment evidence and never reach respondents.
    excluded = {
        c: a.respondent_exclusion
        for c, a in accepted.items()
        if a.respondent_use is RespondentUse.EXCLUDED
    }
    assert excluded == {
        "Rostlinné nápoje kupuje 45 % domácností.": QuarantineReason.DETERMINISTIC_TARGET_OVERLAP,
        "U 22 % je důvodem ohled na životní prostředí.": QuarantineReason.TARGET_OUTCOME_OVERLAP,
    }

    assert Counter(q.reason for q in bundle.quarantined) == Counter(
        {
            QuarantineReason.NUMBER_NOT_IN_QUOTE: 1,
            QuarantineReason.UNGROUNDED_EXCERPT: 1,
            QuarantineReason.CITATION_OUTSIDE_TRACK: 1,
            QuarantineReason.SOURCE_CONTAINS_INSTRUCTIONS: 1,
            QuarantineReason.LOW_SOURCE_QUALITY: 1,
            QuarantineReason.OVERSTATED_BY_VERIFIER: 1,
        }
    )

    # The brief: what cites accepted evidence with its own numbers is kept; the rest is not.
    assert bundle.synthesis is not None
    check = bundle.synthesis.check
    assert check.status is SynthesisStatus.PARTIAL
    assert sorted(e.reason for e in check.excluded) == [
        "citation_not_accepted",
        "number_not_in_cited_evidence",
    ]
    assert all(
        set(f.evidence_ids) <= {a.evidence.evidence_id for a in bundle.accepted}
        for f in check.findings
    )

    # What it did, measured: by the transport, and by the run's own counts.
    assert agents.roles() == Counter(
        planner=1, internal_investigator=3, web_investigator=4, verifier=4, synthesizer=1
    )
    assert bundle.counts["model_requests"] == len(agents.requests) == 13
    assert bundle.counts["search_calls"] == 6 and bundle.counts["fetches"] == 8
    assert bundle.counts["queries_refused"] == 2 and bundle.counts["tracks_reused"] == 0
    assert bundle.spend_usd["tool_usd"] == 0.0  # recorded routes have no price
    # 13 requests of 1000 input and 200 output tokens at the test route's $3 / $15 per Mtok.
    assert bundle.spend_usd["model_usd"] == pytest.approx(0.078)
    # The private address was refused at resolution: dispatched, never requested.
    assert pass_one.web_calls() == (6, 7)


def test_every_accepted_finding_quotes_a_snapshot_the_run_captured(
    pass_one: Journey, store: InMemoryArtifactStore
) -> None:
    world, run_id = pass_one.world, pass_one.run_id
    _run, bundle = read(world, run_id, store)
    refs = {s.snapshot_id: s for s in bundle.snapshots}
    with world.sessions() as session:
        runs = DeepResearchRuns(session, world.lead_scope(session))
        for accepted in bundle.accepted:
            item = accepted.evidence
            if item.source_kind is SourceKind.CLIENT_KNOWLEDGE:
                assert (
                    item.source_ref.endswith("@1")
                    and item.data_class is DataClass.CLASS_B_DERIVED_CLIENT
                )
                continue
            snapshot = runs.snapshot(run_id, item.source_ref, store=store)
            assert snapshot.retrieval_mode is RetrievalMode.RECORDED
            assert snapshot.snapshot_id == item.source_ref and item.source_ref in refs
            assert locate_quote(snapshot.text, normalise_text(item.quote)) == item.quote_span
            assert snapshot.url == item.source_url or snapshot.final_url == item.source_url
            # Captured when it was recorded, not when it was replayed.
            assert snapshot.retrieved_at.isoformat() == "2026-09-01T09:00:00+00:00"
    injected = [s for s in bundle.snapshots if s.instructions_detected]
    assert [s.final_url for s in injected] == ["https://zpravy.example/pokyny"]
    assert set(injected[0].instructions_detected) == {"ignore_instructions", "verdict_override"}


def test_a_recorded_bundle_is_never_client_evidence_nor_respondent_context(
    pass_one: Journey, store: InMemoryArtifactStore
) -> None:
    world, run_id = pass_one.world, pass_one.run_id
    _run, bundle = read(world, run_id, store)
    with pytest.raises(RecordedEvidenceRefused):
        require_live_evidence(bundle)
    with world.sessions() as session:
        questionnaire = (
            DeepResearchRuns(session, world.lead_scope(session))
            .freeze(design_revision_id=bundle.design_revision_id, preset_name="QUICK")
            .questionnaire
        )
    with pytest.raises(RecordedEvidenceRefused):
        respondent_context(bundle, questionnaire)
    context = respondent_context(bundle, questionnaire, allow_recorded=True)
    texts = " ".join(b.text for b in context.blocks)
    assert "45 %" not in texts and "22 %" not in texts  # the survey's own answers
    assert "12,5 %" in texts


def test_every_tool_call_is_journaled_before_it_leaves_and_names_no_query(
    pass_one: Journey, store: InMemoryArtifactStore
) -> None:
    world, run_id = pass_one.world, pass_one.run_id
    events = tool_events(world, run_id)
    outcomes = Counter(e["payload"]["outcome"] for e in events)
    assert outcomes == Counter(
        {
            ToolOutcome.DISPATCHED.value: 14,  # 6 searches and 8 fetches
            ToolOutcome.SUCCEEDED.value: 11,
            ToolOutcome.FAILED.value: 2,  # a provider error; a private address after dispatch
            ToolOutcome.UNCERTAIN.value: 1,
            ToolOutcome.REFUSED.value: 2,
        }
    )
    first: dict[str, int] = {}
    for e in events:
        call = e["payload"]["call_id"]
        if e["payload"]["outcome"] == ToolOutcome.DISPATCHED.value:
            first[call] = e["event_id"]
        elif e["payload"]["outcome"] != ToolOutcome.REFUSED.value:
            assert first[call] < e["event_id"]  # the dispatch is on record before the outcome
    journal = json.dumps([e["payload"] for e in events], ensure_ascii=False)
    assert "Acme" not in journal and "ovesný" not in journal  # fingerprints, never the text


# --------------------------------------------------------------------------- #
# Pass 2: reuse what did not change, research what did
# --------------------------------------------------------------------------- #


def test_a_second_pass_reuses_unchanged_tracks_and_measures_what_it_bought(
    pass_one: Journey, store: InMemoryArtifactStore
) -> None:
    world, agents, w, first_run = pass_one.world, pass_one.agents, pass_one.worker, pass_one.run_id
    searched, fetched = pass_one.web_calls()
    _run, first = read(world, first_run, store)
    before = len(agents.requests)

    second_run = start(world, DESIGN_2)
    assert drain(w) == 6
    run, second = read(world, second_run, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED and second.verify()

    tracks = {t.track_id: t for t in second.tracks}
    reused = {k for k, t in tracks.items() if t.reused}
    assert reused == {
        tid(QS, Q1, IN),
        tid(QS, Q1, WEB_),
        tid(QS, Q2, WEB_),
        tid(OS, OATS, IN),
        tid(OS, OATS, WEB_),
        tid(OS, ALMOND, IN),
    }
    for k in reused:  # the same stored result, not a new one
        assert tracks[k].artifact_id == {t.track_id: t for t in first.tracks}[k].artifact_id
    # A blocked or cut-short track is never reused: the gate may have opened.
    assert (
        tracks[tid(QS, Q2, IN)].status is TrackStatus.BLOCKED and not tracks[tid(QS, Q2, IN)].reused
    )
    assert tracks[tid(OS, ALMOND, WEB_)].status is TrackStatus.INCOMPLETE
    assert tracks[tid(OS, SOY, IN)].status is TrackStatus.COMPLETED
    assert tracks[tid(OS, SOY, WEB_)].status is TrackStatus.COMPLETED

    # Exactly what the new object and the unfinished track cost, and nothing else.
    bought = Counter(RecordedAgents._role(r) for r in agents.requests[before:])
    assert bought == Counter(
        planner=1, internal_investigator=1, web_investigator=1, verifier=1, synthesizer=1
    )
    assert second.counts["model_requests"] == 5
    assert second.counts["tracks_reused"] == 6 and second.counts["tracks_researched"] == 4
    assert second.counts["search_calls"] == 3 and second.counts["fetches"] == 2
    assert second.counts["verification_batches"] == 5
    assert second.counts["verification_batches_reused"] == 4
    assert second.counts["accepted"] == 8 and second.counts["quarantined"] == 6
    # Both pages were requested; the redirect's second hop, to the metadata service, never was.
    assert pass_one.web_calls() == (searched + 3, fetched + 2)

    soy = [a for a in second.accepted if a.evidence.track_id == tid(OS, SOY, WEB_)]
    assert [a.evidence.claim for a in soy] == [
        "Sójové nápoje tvořily v roce 2025 celkem 18 % spotřeby rostlinných nápojů."
    ]
    assert {a.evidence.evidence_id for a in first.accepted} <= {
        a.evidence.evidence_id for a in second.accepted
    }
    # The redirect to the metadata service was refused on its second hop.
    soy_web = tracks[tid(OS, SOY, WEB_)]
    assert soy_web.fetches == 2 and len(soy_web.snapshot_ids) == 1


# --------------------------------------------------------------------------- #
# Extended thinking (AIA_DEEP_RESEARCH_THINKING_BUDGET_TOKENS)
# --------------------------------------------------------------------------- #


def _stored_text(world: ResearchWorld, run_id: str, store: InMemoryArtifactStore) -> str:
    """Every artifact the store holds and every event of the run, as one text."""
    with world.sessions() as session:
        events = DeepResearchRuns(session, world.lead_scope(session)).events(run_id, limit=2000)
    blobs = [store.get(key).decode("utf-8", "replace") for key in store.keys]
    return "\n".join([*blobs, json.dumps(events, default=str, ensure_ascii=False)])


def test_without_the_thinking_key_no_request_thinks_and_the_tool_is_forced(
    pass_one: Journey,
) -> None:
    for request in pass_one.agents.requests:
        assert "additionalModelRequestFields" not in request.body
        name = request.body["toolConfig"]["tools"][0]["toolSpec"]["name"]
        assert request.body["toolConfig"]["toolChoice"] == {"tool": {"name": name}}
        assert len(request.body["system"]) == 1
        assert "Answer only by calling the tool" not in request.body["system"][0]["text"]
    assert "thinking_budget_tokens" not in pass_one.runtime.versions()


def test_a_recorded_run_thinks_when_configured_and_keeps_none_of_the_reasoning(
    research: ResearchWorld, database_url: str, store: InMemoryArtifactStore, build: Any
) -> None:
    approve_knowledge(research)
    agents = RecordedAgents(ANSWERS, thinking=True)
    runtime = recorded(research, agents, thinking=2048)
    run_id = start(research)
    assert drain(worker(research, database_url, store, build, runtime)) == 6
    run, bundle = read(research, run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED and bundle.verify()
    assert len(bundle.accepted) == 7  # what pass one accepts without thinking

    assert agents.roles() == Counter(
        planner=1, internal_investigator=3, web_investigator=4, verifier=4, synthesizer=1
    )
    for request in agents.requests:
        body = request.body
        assert body["additionalModelRequestFields"] == {
            "thinking": {"type": "enabled", "budget_tokens": 2048}
        }
        # No sampling setting; each kind's answer limit with the thinking budget on top,
        # never beyond the research limit (request_limits).
        kind = kind_of(AgentRole(RecordedAgents._role(request)))
        assert body["inferenceConfig"] == {"maxTokens": runtime.config.budget(kind).output_tokens}
        assert body["toolConfig"]["toolChoice"] == {"auto": {}}
        name = body["toolConfig"]["tools"][0]["toolSpec"]["name"]
        assert f"Answer only by calling the tool {name}" in body["system"][0]["text"]
    # The research limit for the few, the answer limit and the thinking for the many.
    assert {
        RecordedAgents._role(r): r.body["inferenceConfig"]["maxTokens"] for r in agents.requests
    } == {
        "planner": 8192,
        "internal_investigator": 6144 + 2048,
        "web_investigator": 6144 + 2048,
        "verifier": 4096 + 2048,
        "synthesizer": 8192,
    }
    assert runtime.versions()["thinking_budget_tokens"] == "2048"
    assert REASONING not in _stored_text(research, run_id, store)


def test_an_answer_in_text_with_thinking_on_is_one_counted_repair(
    research: ResearchWorld, database_url: str, store: InMemoryArtifactStore, build: Any
) -> None:
    approve_knowledge(research)
    agents = RecordedAgents(ANSWERS, thinking=True, in_text={"planner"})
    run_id = start(research)
    assert (
        drain(
            worker(research, database_url, store, build, recorded(research, agents, thinking=2048))
        )
        == 6
    )
    run, bundle = read(research, run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED
    # The planner answered in text, was told to use its tool, and did: two calls, one
    # logical request, both billed.
    assert agents.roles()["planner"] == 2
    repair = agents.requests[1].body
    assert repair["messages"][-1]["content"][0]["text"].startswith(
        "Your previous answer did not satisfy the required output schema:\n"
        "- answered in text, not through the output tool"
    )
    assert bundle.counts["model_requests"] == 13 and len(agents.requests) == 14
    assert bundle.spend_usd["model_usd"] == pytest.approx(0.078 + 0.006)


def test_a_thinking_pass_reuses_no_track_a_pass_without_thinking_researched(
    pass_one: Journey, database_url: str, store: InMemoryArtifactStore, build: Any
) -> None:
    # The second pass of the reuse test above, which reuses six tracks without thinking.
    world = pass_one.world
    agents = RecordedAgents(ANSWERS, thinking=True)
    run_id = start(world, DESIGN_2)
    assert (
        drain(worker(world, database_url, store, build, recorded(world, agents, thinking=2048)))
        == 6
    )
    _run, bundle = read(world, run_id, store)
    assert bundle.counts["tracks_reused"] == 0
    assert not any(t.reused for t in bundle.tracks)


# --------------------------------------------------------------------------- #
# Harness 2: per-kind request limits are a method change (chunk 23)
# --------------------------------------------------------------------------- #

HARNESS_ONE = "aia-deep-research-harness-1"


def _as_harness_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """The engine as it was before per-kind request limits: harness 1 in every module that
    names the harness, and every kind of request at the model's window and the whole
    research output limit."""
    for module in list(sys.modules.values()):
        if (module.__name__ or "").startswith(("aia_core", "aia_executors")) and getattr(
            module, "HARNESS_VERSION", None
        ) == HARNESS_VERSION:
            monkeypatch.setattr(module, "HARNESS_VERSION", HARNESS_ONE)
    whole = {kind: RequestLimits(window_tokens=None, answer_tokens=None) for kind in RESEARCH_KINDS}
    monkeypatch.setattr(
        deep_research_runtime_module, "kind_budgets", functools.partial(kind_budgets, limits=whole)
    )


def test_an_identical_run_under_the_new_limits_reuses_nothing_made_under_the_old(
    research: ResearchWorld,
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approve_knowledge(research)
    _as_harness_one(monkeypatch)
    old_agents = RecordedAgents(ANSWERS)
    old_run = start(research)
    assert drain(worker(research, database_url, store, build, recorded(research, old_agents))) == 6
    _run, old = read(research, old_run, store)
    assert {r.body["inferenceConfig"]["maxTokens"] for r in old_agents.requests} == {8192}
    monkeypatch.undo()

    new_agents = RecordedAgents(ANSWERS)
    new_run = start(research)  # the same design, preset and knowledge
    assert new_run != old_run
    assert drain(worker(research, database_url, store, build, recorded(research, new_agents))) == 6
    _run, new = read(research, new_run, store)
    assert new.request_fingerprint != old.request_fingerprint
    # Nothing method-dependent crosses: every track, verification and the brief again.
    assert new.counts["tracks_reused"] == 0 and not any(t.reused for t in new.tracks)
    assert new.counts["verification_batches_reused"] == 0
    assert new_agents.roles() == old_agents.roles()
    assert {t.artifact_id for t in new.tracks}.isdisjoint({t.artifact_id for t in old.tracks})
    assert {r.body["inferenceConfig"]["maxTokens"] for r in new_agents.requests} == {
        8192,
        6144,
        4096,
    }


def test_a_request_frozen_under_harness_one_is_never_executed_under_harness_two(
    research: ResearchWorld,
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approve_knowledge(research)
    _as_harness_one(monkeypatch)
    run_id = start(research)  # frozen, not yet planned, when the method moved
    monkeypatch.undo()

    agents = RecordedAgents(ANSWERS)
    w = worker(research, database_url, store, build, recorded(research, agents))
    result = w.run_once()
    assert result is not None and result.ending == "failed"
    with research.sessions() as session:
        run = DeepResearchRuns(session, research.lead_scope(session)).get(run_id)
    assert run["metadata"]["harness_version"] == HARNESS_ONE
    [plan] = [s for s in run["steps"] if s["status"] is StepRunStatus.FAILED]
    assert plan["attempts"][0]["error"]["reason"] == "harness_changed"
    assert agents.requests == [], "nothing was asked for a request of another method"


def test_a_run_whose_settings_pin_was_altered_is_never_executed(
    research: ResearchWorld,
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    """ADR 0022 decision 4 (chunk 43): a run runs under the settings it pinned at enqueue,
    and a pin that does not hash to itself fails the run closed before anything is asked."""
    from aia_core.infrastructure.tables import StepRunRow
    from sqlalchemy import select

    approve_knowledge(research)
    run_id = start(research)
    with research.sessions() as session:
        plan_row = session.scalars(
            select(StepRunRow).where(StepRunRow.run_id == run_id, StepRunRow.node_key == "plan")
        ).one()
        pinned = dict(plan_row.input_json["settings"])
        pinned["method_digest"] = "0" * 64
        plan_row.input_json = {**plan_row.input_json, "settings": pinned}
        session.commit()

    agents = RecordedAgents(ANSWERS)
    w = worker(research, database_url, store, build, recorded(research, agents))
    result = w.run_once()
    assert result is not None and result.ending == "failed"
    with research.sessions() as session:
        run = DeepResearchRuns(session, research.lead_scope(session)).get(run_id)
    [plan] = [s for s in run["steps"] if s["status"] is StepRunStatus.FAILED]
    assert plan["attempts"][0]["error"]["reason"] == "settings_pin_altered"
    assert agents.requests == [], "nothing was asked under settings the run cannot prove"


def test_a_run_whose_pin_is_not_its_requests_method_is_never_executed(
    research: ResearchWorld,
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    """Harness 3: the request's method digest and the pin's must agree. A pin that proves
    itself but records other approved method settings than the request was frozen under
    fails the run before anything is asked."""
    from datetime import UTC, datetime

    from aia_core.domain.deep_research.settings import ApprovedValue, effective, pin
    from aia_core.infrastructure.tables import StepRunRow
    from sqlalchemy import select

    approve_knowledge(research)
    run_id = start(research)
    other = effective(
        {
            "budgets.allowance.exhaustive.crawl_pages": ApprovedValue(
                value=300, version=1, approved_by="someone", approved_at=datetime.now(UTC)
            )
        }
    )
    with research.sessions() as session:
        plan_row = session.scalars(
            select(StepRunRow).where(StepRunRow.run_id == run_id, StepRunRow.node_key == "plan")
        ).one()
        plan_row.input_json = {**plan_row.input_json, "settings": pin(other)}
        session.commit()

    agents = RecordedAgents(ANSWERS)
    w = worker(research, database_url, store, build, recorded(research, agents))
    result = w.run_once()
    assert result is not None and result.ending == "failed"
    with research.sessions() as session:
        run = DeepResearchRuns(session, research.lead_scope(session)).get(run_id)
    [plan] = [s for s in run["steps"] if s["status"] is StepRunStatus.FAILED]
    assert plan["attempts"][0]["error"]["reason"] == "settings_mismatch"
    assert agents.requests == []


@pytest.mark.parametrize(
    ("value", "problem"),
    [
        ("lots", "AIA_DEEP_RESEARCH_THINKING_BUDGET_TOKENS='lots' is not an integer"),
        ("1.5", "AIA_DEEP_RESEARCH_THINKING_BUDGET_TOKENS='1.5' is not an integer"),
        ("1023", "AIA_DEEP_RESEARCH_THINKING_BUDGET_TOKENS=1023 is below the smallest budget"),
        ("-2048", "AIA_DEEP_RESEARCH_THINKING_BUDGET_TOKENS=-2048 is below the smallest budget"),
        ("8192", "AIA_DEEP_RESEARCH_THINKING_BUDGET_TOKENS=8192 must be below"),
    ],
)
def test_an_invalid_thinking_budget_stops_the_configuration_and_names_its_key(
    research: ResearchWorld, value: str, problem: str
) -> None:
    settings = ai_settings(research.client_id, approved_for=DEVELOP_ROUTE)
    env = {"AIA_DEEP_RESEARCH_ENABLED": "true", "AIA_DEEP_RESEARCH_THINKING_BUDGET_TOKENS": value}
    with pytest.raises(AIRuntimeConfigError, match=re.escape(problem)):
        deep_research_runtime(settings, env=env, transport=RecordedAgents(ANSWERS), signer=Signer())


def test_the_thinking_budget_needs_deep_research_and_is_off_when_unset(
    research: ResearchWorld,
) -> None:
    with pytest.raises(AIRuntimeConfigError, match="needs AIA_DEEP_RESEARCH_ENABLED"):
        deep_research_runtime(None, env={"AIA_DEEP_RESEARCH_THINKING_BUDGET_TOKENS": "2048"})
    settings = ai_settings(research.client_id, approved_for=DEVELOP_ROUTE)
    for env in (
        {"AIA_DEEP_RESEARCH_ENABLED": "true"},
        {"AIA_DEEP_RESEARCH_ENABLED": "true", "AIA_DEEP_RESEARCH_THINKING_BUDGET_TOKENS": " "},
    ):
        runtime = deep_research_runtime(
            settings, env=env, transport=RecordedAgents(ANSWERS), signer=Signer()
        )
        assert runtime is not None and runtime.config.thinking_budget_tokens is None
        assert runtime.inputs().thinking_budget_tokens is None
    runtime = deep_research_runtime(
        settings,
        env={
            "AIA_DEEP_RESEARCH_ENABLED": "true",
            "AIA_DEEP_RESEARCH_THINKING_BUDGET_TOKENS": "4096",
        },
        transport=RecordedAgents(ANSWERS),
        signer=Signer(),
    )
    assert runtime is not None and runtime.config.thinking_budget_tokens == 4096
    assert runtime.inputs().thinking_budget_tokens == 4096
    # A composition built by hand is held to the same rule.
    with pytest.raises(ValueError, match="below the output limit"):
        recorded(research, RecordedAgents(ANSWERS), thinking=8192)


# --------------------------------------------------------------------------- #
# Disabled and public-route production compositions
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("fictional", [True, False])
def test_the_production_shape_blocks_every_track_and_sends_nothing(
    research: ResearchWorld,
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    fictional: bool,
) -> None:
    approve_knowledge(research)
    agents = RecordedAgents(ANSWERS)
    settings = ai_settings(research.client_id if fictional else "", approved_for=DEVELOP_ROUTE)
    runtime = deep_research_runtime(
        settings, env={"AIA_DEEP_RESEARCH_ENABLED": "true"}, transport=agents, signer=Signer()
    )
    assert runtime is not None and runtime.retrieval is None
    run_id = start(research)
    assert drain(worker(research, database_url, store, build, runtime)) == 6
    run, bundle = read(research, run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED
    assert agents.requests == []  # no model was asked anything
    web = [t for t in bundle.tracks if t.channel is WEB_]
    internal = [t for t in bundle.tracks if t.channel is IN]
    assert {(t.status, t.stop_reason) for t in web} == {
        (TrackStatus.BLOCKED, StopReason.WEB_RETRIEVAL_UNAVAILABLE)
    }
    # Client Knowledge is Class B or A; develop's route carries Class C only.
    assert {(t.status, t.stop_reason) for t in internal} == {
        (TrackStatus.BLOCKED, StopReason.MODEL_ROUTE_REFUSED)
    }
    assert bundle.quality_status is QualityStatus.PARTIAL and bundle.accepted == ()
    assert bundle.synthesis is not None
    assert bundle.synthesis.check.status is SynthesisStatus.EMPTY
    assert bundle.counts["model_requests"] == 0 and bundle.counts["search_calls"] == 0


def test_unconfigured_parks_the_run_before_anything_is_read(
    research: ResearchWorld, database_url: str, store: InMemoryArtifactStore, build: Any
) -> None:
    assert deep_research_runtime(None, env={}) is None
    run_id = start(research)
    assert drain(worker(research, database_url, store, build, None)) == 1
    with research.sessions() as session:
        run = DeepResearchRuns(session, research.lead_scope(session)).get(run_id)
    assert run["status"] is WorkflowRunStatus.WAITING_PROVIDER
    [attempt] = run["steps"][0]["attempts"]
    assert attempt["error"]["reason"] == "deep_research_unconfigured"
    assert [s["status"] for s in run["steps"][1:]] == [StepRunStatus.BLOCKED] * 5


def test_enabling_it_without_research_agents_refuses_to_start(research: ResearchWorld) -> None:
    with pytest.raises(AIRuntimeConfigError, match="AIA_AI_RESEARCH_AGENTS_ENABLED"):
        deep_research_runtime(None, env={"AIA_DEEP_RESEARCH_ENABLED": "true"})
    with pytest.raises(AIRuntimeConfigError, match="not true or false"):
        deep_research_runtime(None, env={"AIA_DEEP_RESEARCH_ENABLED": "maybe"})
    with pytest.raises(AIRuntimeConfigError, match="needs AIA_DEEP_RESEARCH_ENABLED"):
        deep_research_runtime(None, env={"AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED": "true"})


def test_public_wikipedia_route_is_live_fee_free_and_class_c_only(research: ResearchWorld) -> None:
    settings = ai_settings(research.client_id, approved_for=DEVELOP_ROUTE)
    runtime = deep_research_runtime(
        settings,
        env={
            "AIA_DEEP_RESEARCH_ENABLED": "true",
            "AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED": "true",
        },
        transport=RecordedAgents(ANSWERS),
        signer=Signer(),
    )
    assert runtime is not None and runtime.retrieval is not None
    assert runtime.retrieval.search_route.price_usd_per_call == 0
    assert runtime.retrieval.fetch_route.price_usd_per_call == 0
    assert runtime.retrieval.search_route.retrieval_mode is RetrievalMode.LIVE
    assert runtime.retrieval.fetch_route.route.approved_for == frozenset(
        {DataClass.CLASS_C_INTERNAL}
    )


def test_the_recorded_composition_refuses_outside_local_and_test(
    research: ResearchWorld,
) -> None:
    agents = RecordedAgents(ANSWERS)
    settings = ai_settings("", approved_for=DEVELOP_ROUTE)
    for env in ({"AIA_ENV": "production"}, {"AIA_ENV": "develop"}, {}):
        with pytest.raises(RuntimeError, match="refuses AIA_ENV"):
            recorded_runtime(
                gateway=build_gateway(settings, transport=agents, signer=Signer()),
                config=DeepResearchConfig(
                    policy_version="p",
                    max_output_tokens=1,
                    context_window_tokens=1,
                    prices=ModelPrices(3.0, 15.0),
                    fictional_client_ids=frozenset(),
                ),
                fixture=WEB,
                env=env,
            )


# --------------------------------------------------------------------------- #
# Confidential material, scope and tampering
# --------------------------------------------------------------------------- #


def test_a_real_clients_design_writes_no_query_and_sends_nothing(
    research: ResearchWorld, database_url: str, store: InMemoryArtifactStore, build: Any
) -> None:
    """Not a fictional client: the design is Class A, so no query written from it may leave."""
    approve_knowledge(research)
    agents = RecordedAgents(ANSWERS)
    runtime = recorded(research, agents, fictional=False)
    run_id = start(research)
    assert drain(worker(research, database_url, store, build, runtime)) == 6
    _run, bundle = read(research, run_id, store)
    web = [t for t in bundle.tracks if t.channel is WEB_]
    assert {(t.status, t.stop_reason) for t in web} == {
        (TrackStatus.BLOCKED, StopReason.SEARCH_ROUTE_REFUSED)
    }
    assert all("class_a_query" in t.detail for t in web)
    assert agents.requests == []  # no planner was paid to write queries that cannot leave
    assert bundle.counts["search_calls"] == 0 and tool_events(research, run_id) == []
    assert not bundle.fictional_client


def _enqueue(world: ResearchWorld, request: Any, *, fingerprint: str) -> str:
    """A run created around the application service, as a forged or altered payload would be."""
    with world.sessions() as session:
        scope = world.lead_scope(session)
        designs = StudyDesignRepository(session, scope)
        if designs.project_id() is None:
            designs.submit(content=DESIGN, source_stage="brief")
        project_id = designs.project_id()
        assert project_id is not None
        steps = deep_research_steps()
        run_id = WorkflowRepository(session, scope).create_run(
            project_id=project_id,
            project_revision=request.design_revision,
            workflow_type=DEEP_RESEARCH,
            steps=steps,
            idempotency_key=f"forged:{fingerprint}",
            fingerprints={s.node_key: fingerprint for s in steps},
            step_inputs={"plan": {"request": request.model_dump(mode="json")}},
        )
        session.commit()
        return run_id


def test_a_run_cannot_research_another_clients_design(
    research: ResearchWorld, database_url: str, store: InMemoryArtifactStore, build: Any
) -> None:
    with research.sessions() as session:
        other = research.other_scope(session)
        revision, _ = StudyDesignRepository(session, other).submit(
            content=DESIGN, source_stage="brief"
        )
        foreign = DeepResearchRuns(session, other).freeze(
            design_revision_id=revision.revision_id, preset_name="QUICK"
        )
        session.commit()
    run_id = _enqueue(research, foreign, fingerprint=foreign.fingerprint())
    agents = RecordedAgents(ANSWERS)
    drain(worker(research, database_url, store, build, recorded(research, agents)))
    with research.sessions() as session:
        run = WorkflowRepository(session, research.lead_scope(session)).get_run(run_id)
    assert run["status"] is WorkflowRunStatus.FAILED
    assert run["steps"][0]["attempts"][0]["error"]["reason"] == "design_not_in_scope"
    assert agents.requests == [] and tool_events(research, run_id) == []


def test_an_altered_request_is_refused(
    research: ResearchWorld, database_url: str, store: InMemoryArtifactStore, build: Any
) -> None:
    with research.sessions() as session:
        scope = research.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
            content=DESIGN, source_stage="brief"
        )
        request = DeepResearchRuns(session, scope).freeze(
            design_revision_id=revision.revision_id, preset_name="QUICK"
        )
        session.commit()
    # The client terms removed after the fingerprint was taken: queries would be less safe.
    altered = request.model_copy(update={"client_terms": ()})
    run_id = _enqueue(research, altered, fingerprint=request.fingerprint())
    agents = RecordedAgents(ANSWERS)
    drain(worker(research, database_url, store, build, recorded(research, agents)))
    with research.sessions() as session:
        run = WorkflowRepository(session, research.lead_scope(session)).get_run(run_id)
    assert run["steps"][0]["attempts"][0]["error"]["reason"] == "request_altered"
    assert agents.requests == []


# --------------------------------------------------------------------------- #
# Stopping, recovery and a changed composition
# --------------------------------------------------------------------------- #


def test_cancelling_between_steps_sends_nothing_more(
    research: ResearchWorld, database_url: str, store: InMemoryArtifactStore, build: Any
) -> None:
    approve_knowledge(research)
    agents = RecordedAgents(ANSWERS)
    w = worker(research, database_url, store, build, recorded(research, agents))
    run_id = start(research)
    assert w.run_once() is not None  # the plan, with its one planner request
    with research.sessions() as session:
        DeepResearchRuns(session, research.lead_scope(session)).cancel(run_id)
        session.commit()
    drain(w)
    with research.sessions() as session:
        run = DeepResearchRuns(session, research.lead_scope(session)).get(run_id)
    assert run["status"] is WorkflowRunStatus.CANCELLED
    assert agents.roles() == Counter(planner=1)
    assert tool_events(research, run_id) == []


class _Cancelled:
    """A step context that has been cancelled: what the worker's context says once asked."""

    def __init__(self, scope: StudyContext) -> None:
        self.scope = scope
        self.journal: list[str] = []

    def checkpoint(self) -> None:
        raise CancellationRequested("run")

    def progress(self, message: str, **payload: Any) -> None:
        self.journal.append(message)


def test_a_cancelled_step_stops_before_its_tool_call_leaves(research: ResearchWorld) -> None:
    retrieval, _table = recorded_retrieval(WEB)
    with research.sessions() as session:
        context = _Cancelled(research.lead_scope(session))
    meter = StepToolMeter(context)  # type: ignore[arg-type]
    gate = RetrievalGate(
        retrieval=retrieval,
        scope=context.scope,
        meter=meter,
        client_terms=(ClientTerm(term="Acme", source="client.name"),),
        class_a_texts=(),
    )
    with pytest.raises(CancellationRequested):
        gate.search(
            "trh rostlinných nápojů česko",
            context_class=DataClass.CLASS_C_INTERNAL,
            track_id="T",
            max_results=2,
        )
    assert isinstance(retrieval.search, RecordedSearch) and retrieval.search.calls == []
    assert meter.events() == () and context.journal == []


class _Running(_Cancelled):
    """A step context that lets the work go on."""

    def checkpoint(self) -> None:
        return None


def test_a_meter_that_never_took_over_its_step_s_journal_sends_nothing(
    research: ResearchWorld,
) -> None:
    retrieval, _table = recorded_retrieval(WEB)
    with research.sessions() as session:
        context = _Running(research.lead_scope(session))
    meter = StepToolMeter(context)  # type: ignore[arg-type]  # not StepToolMeter.resuming
    gate = RetrievalGate(
        retrieval=retrieval, scope=context.scope, meter=meter, client_terms=(), class_a_texts=()
    )
    with pytest.raises(RuntimeError, match=r"StepToolMeter\.resuming"):
        gate.search(
            "trh rostlinných nápojů česko",
            context_class=DataClass.CLASS_C_INTERNAL,
            track_id="T",
            max_results=2,
        )
    assert isinstance(retrieval.search, RecordedSearch) and retrieval.search.calls == []
    assert meter.events() == () and context.journal == []


def test_a_lost_model_answer_waits_for_recovery_and_is_not_bought_again(
    research: ResearchWorld, database_url: str, store: InMemoryArtifactStore, build: Any
) -> None:
    approve_knowledge(research)
    agents = RecordedAgents(ANSWERS, lose={"web_investigator"})
    w = worker(research, database_url, store, build, recorded(research, agents))
    run_id = start(research)
    drain(w)
    drain(w)  # nothing more is claimable: an uncertain call is never retried automatically
    with research.sessions() as session:
        run = DeepResearchRuns(session, research.lead_scope(session)).get(run_id)
    assert run["status"] is WorkflowRunStatus.RECOVERY_REQUIRED
    assert run["steps"][1]["status"] is StepRunStatus.RECOVERY_REQUIRED
    assert agents.roles()["web_investigator"] == 1
    # The internal track that finished before it is stored, and a later run reuses it.
    with research.sessions() as session:
        runs = DeepResearchRuns(session, research.lead_scope(session))
        events = runs.events(run_id, limit=2000)
    done = [e for e in events if e["message"] == "deep_research_track"]
    assert [e["payload"]["track_id"] for e in done] == [tid(QS, Q1, IN)]


def test_a_changed_composition_is_refused_mid_run(
    research: ResearchWorld, database_url: str, store: InMemoryArtifactStore, build: Any
) -> None:
    approve_knowledge(research)
    agents = RecordedAgents(ANSWERS)
    run_id = start(research)
    assert worker(research, database_url, store, build, recorded(research, agents)).run_once()
    changed = recorded(research, agents, policy="another-policy-v2")
    drain(worker(research, database_url, store, build, changed))
    with research.sessions() as session:
        run = DeepResearchRuns(session, research.lead_scope(session)).get(run_id)
    assert run["steps"][1]["attempts"][0]["error"]["reason"] == "composition_changed"
    assert agents.roles() == Counter(planner=1)


# --------------------------------------------------------------------------- #
# A call whose outcome is unknown is the last thing its track sends
# --------------------------------------------------------------------------- #


def _recorded_web_with(tmp_path: Path, pages: dict[str, dict[str, Any]]) -> Path:
    """The recorded web with some pages replaced, where a runtime can be pointed at it."""
    web = json.loads(WEB.read_text(encoding="utf-8"))
    web["pages"].update(pages)
    path = tmp_path / "web.json"
    path.write_text(json.dumps(web, ensure_ascii=False), encoding="utf-8")
    return path


def _investigated_urls(agents: RecordedAgents) -> list[str]:
    """Every page URL a web investigator request carried."""
    return [
        source["url"]
        for r in agents.requests
        if RecordedAgents._role(r) == "web_investigator"
        for source in json.loads(r.body["messages"][0]["content"][0]["text"])["sources"]
    ]


def _take_the_lease(world: ResearchWorld) -> None:
    """Another worker takes the running attempt: the one in flight can record nothing more."""
    with world.sessions() as session:
        attempt = session.scalar(
            select(StepAttemptRow).where(StepAttemptRow.status.in_(("CLAIMED", "EXECUTING")))
        )
        assert attempt is not None
        attempt.worker_id = "another-worker"
        session.commit()


def test_a_fetch_that_may_have_been_served_ends_its_track_before_a_model_sees_its_round(
    research: ResearchWorld,
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    tmp_path: Path,
) -> None:
    # "ovesný nápoj spotřeba" returns two hits: the first page is captured, the
    # second fetch gets no answer and may have been served.
    web = _recorded_web_with(tmp_path, {"https://zpravy.example/pokyny": {"fail": "uncertain"}})
    approve_knowledge(research)
    agents = RecordedAgents(ANSWERS)
    run_id = start(research)
    runtime = recorded(research, agents, fixture=web)
    assert drain(worker(research, database_url, store, build, runtime)) == 6
    run, bundle = read(research, run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED and bundle.verify()

    oats = {t.track_id: t for t in bundle.tracks}[tid(OS, OATS, WEB_)]
    assert oats.status is TrackStatus.INCOMPLETE
    assert oats.stop_reason is StopReason.TOOL_OUTCOME_UNCERTAIN
    # Nothing more is sent -- not even the investigator request over the page the
    # round did capture before its next fetch went unanswered.
    assert "https://trh.example/ovesne-napoje" not in _investigated_urls(agents)
    assert agents.roles()["web_investigator"] == 3  # the questions' rounds (2 + 1); oats sent none


def test_a_search_left_in_flight_by_a_lost_attempt_is_closed_uncertain_and_never_sent_again(
    research: ResearchWorld,
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approve_knowledge(research)
    agents = RecordedAgents(ANSWERS)
    runtime = recorded(research, agents)
    w = worker(research, database_url, store, build, runtime)
    run_id = start(research)
    lost = "ovesný nápoj spotřeba"
    served = RecordedSearch.search

    def search(self: RecordedSearch, query: str, *, max_results: int) -> Any:
        if query == lost and lost not in self.calls:
            _take_the_lease(research)  # the dispatch is on record; its outcome will not be
        return served(self, query, max_results=max_results)

    monkeypatch.setattr(RecordedSearch, "search", search)
    drain(w)  # the plan, then the investigation until its lease goes mid-search
    with research.sessions() as session:  # the reconciler, once the lapsed lease is due
        WorkQueue(session).recover_expired_attempts(now=datetime.now(UTC) + timedelta(hours=1))
        session.commit()
    drain(w)

    run, bundle = read(research, run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED and bundle.verify()
    assert [a["status"].value for a in run["steps"][1]["attempts"]] == ["EXPIRED", "SUCCEEDED"]
    retrieval = runtime.retrieval
    assert retrieval is not None and isinstance(retrieval.search, RecordedSearch)
    assert retrieval.search.calls.count(lost) == 1, (
        "a search that may have been served is not sent again"
    )
    oats = {t.track_id: t for t in bundle.tracks}[tid(OS, OATS, WEB_)]
    assert oats.status is TrackStatus.INCOMPLETE
    assert oats.stop_reason is StopReason.TOOL_OUTCOME_UNCERTAIN
    # The journal closes the lost call exactly once, from the attempt that took over.
    entries = [
        e for e in tool_events(research, run_id) if e["payload"]["track_id"] == oats.track_id
    ]
    dispatched = [e for e in entries if e["message"] == TOOL_EVENT_KINDS[ToolOutcome.DISPATCHED]]
    closed = [e for e in entries if e["message"] == TOOL_EVENT_KINDS[ToolOutcome.UNCERTAIN]]
    assert len(dispatched) == 1 and len(closed) == 1
    assert closed[0]["payload"]["call_id"] == dispatched[0]["payload"]["call_id"]
    assert closed[0]["attempt_id"] != dispatched[0]["attempt_id"]
