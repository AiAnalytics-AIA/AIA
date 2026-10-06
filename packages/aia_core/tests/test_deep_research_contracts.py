"""Deep Research contracts: identities, closed shapes, the graph and the tool-cost contract."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aia_core.domain.deep_research.contracts import (
    HARNESS_VERSION,
    BriefDigest,
    Channel,
    DeepResearchRequest,
    EvidenceItem,
    EvidenceType,
    FrozenKnowledge,
    KnowledgeSource,
    Measure,
    MeasureBasis,
    RecommendedUse,
    ResearchSubject,
    RetrievalMode,
    SourceKind,
    SubjectKind,
    digest,
    evidence_id,
    subject_key,
    track_id,
)
from aia_core.domain.deep_research.tooling import (
    InMemoryToolLedger,
    ToolBudgetExhausted,
    ToolKind,
    ToolOutcome,
    ToolRoute,
    ToolUsageEvent,
    new_tool_call_id,
    new_tool_event_id,
)
from aia_core.domain.deep_research.workflow import (
    ARTIFACT_TYPES,
    DEEP_RESEARCH_KINDS,
    DEEP_RESEARCH_STAGE,
    NODE_ORDER,
    deep_research_steps,
)
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone
from aia_core.domain.workflow import validate_dag

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _brief() -> BriefDigest:
    return BriefDigest(title="t", goal="g", decision_use="d", briefing="b")


def _request(**overrides: object) -> DeepResearchRequest:
    fields: dict[str, object] = {
        "harness_version": HARNESS_VERSION,
        "design_revision_id": "REV-1",
        "design_revision": 1,
        "preset": "QUICK",
        "channels": (Channel.WEB,),
        "brief": _brief(),
        "subjects": (),
        "questionnaire": (),
        "knowledge": FrozenKnowledge(items=(), omitted_ids=(), retrieval_limit=200),
        "client_terms": (),
        **overrides,
    }
    return DeepResearchRequest.model_validate(fields)


# --------------------------------------------------------------------------- identities


def test_a_subject_is_its_kind_and_normalised_text_never_its_position() -> None:
    a = subject_key(SubjectKind.QUESTION, "Proč  lidé KUPUJÍ rostlinné nápoje?")
    b = subject_key(SubjectKind.QUESTION, "proč lidé kupují rostlinné nápoje?")
    assert a == b and a.startswith("q-")
    assert subject_key(SubjectKind.OBJECT, "proč lidé kupují rostlinné nápoje?") != a
    # NFKC: a compatibility character is the same label.
    assert subject_key(SubjectKind.OBJECT, "\ufb01lter") == subject_key(
        SubjectKind.OBJECT, "filter"
    )


def test_track_ids_are_stable_across_passes_and_name_the_channel() -> None:
    key = subject_key(SubjectKind.OBJECT, "Aroma")
    assert track_id(key, Channel.WEB) == f"DRT-W-{key}"
    assert track_id(key, Channel.INTERNAL) == f"DRT-I-{key}"


def test_evidence_ids_are_deterministic_and_bind_the_track_instance() -> None:
    first = evidence_id("a" * 64, "SNP-x", "quote", "claim")
    assert first == evidence_id("a" * 64, "SNP-x", "quote", "claim")
    assert first != evidence_id("b" * 64, "SNP-x", "quote", "claim")
    assert first.startswith("EV-") and len(first) == 19


def test_subjects_refuse_malformed_keys_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ResearchSubject(key="q-XYZ", kind=SubjectKind.QUESTION, text="x", origin="o")
    with pytest.raises(ValidationError):
        ResearchSubject.model_validate(
            {"key": "q-" + "0" * 12, "kind": "QUESTION", "text": "x", "origin": "o", "rank": 1}
        )


# --------------------------------------------------------------------------- the request


def test_a_request_refuses_a_repeated_channel_and_another_harness() -> None:
    with pytest.raises(ValidationError):
        _request(channels=(Channel.WEB, Channel.WEB))
    with pytest.raises(ValidationError):
        _request(harness_version="aia-deep-research-harness-0")
    with pytest.raises(ValidationError):
        _request(channels=())


def test_a_request_fingerprint_is_its_content() -> None:
    assert _request().fingerprint() == _request().fingerprint()
    assert _request().fingerprint() != _request(preset="STANDARD").fingerprint()


def test_frozen_knowledge_identity_changes_with_a_revision_or_its_text() -> None:
    def source(revision: int, text: str) -> KnowledgeSource:
        return KnowledgeSource(
            ref=f"KNW-0123456789abcd@{revision}",
            item_id="KNW-0123456789abcd",
            revision=revision,
            kind="FACT",
            title="t",
            text=text,
            data_class=DataClass.CLASS_B_DERIVED_CLIENT,
            lineage=(),
            truncated=False,
            public=False,
        )

    base = FrozenKnowledge(items=(source(1, "a"),), omitted_ids=(), retrieval_limit=200)
    newer = FrozenKnowledge(items=(source(2, "a"),), omitted_ids=(), retrieval_limit=200)
    edited = FrozenKnowledge(items=(source(1, "b"),), omitted_ids=(), retrieval_limit=200)
    assert len({base.fingerprint(), newer.fingerprint(), edited.fingerprint()}) == 3
    assert base.source("KNW-0123456789abcd@1") is not None
    assert base.source("KNW-0123456789abcd@2") is None


def test_evidence_records_the_agents_quality_within_bounds_only() -> None:
    fields: dict[str, object] = {
        "evidence_id": "EV-0123456789abcdef",
        "track_id": "DRT-W-o-0123456789ab",
        "subject_key": "o-0123456789ab",
        "channel": Channel.WEB,
        "source_kind": SourceKind.WEB_PAGE,
        "source_ref": "SNP-" + "0" * 24,
        "source_url": "https://example.org/a",
        "source_title": "t",
        "claim": "c",
        "quote": "q",
        "quote_span": (0, 1),
        "evidence_type": EvidenceType.OTHER,
        "source_date": None,
        "geography": "",
        "population": "",
        "topics": (),
        "data_class": DataClass.CLASS_C_INTERNAL,
        "agent_outcome_overlap": False,
        "agent_recommended_use": RecommendedUse.CONTEXT_ONLY,
        "agent_source_quality": 0.4,
    }
    assert EvidenceItem.model_validate(fields).agent_source_quality == 0.4
    with pytest.raises(ValidationError):
        EvidenceItem.model_validate({**fields, "agent_source_quality": 1.5})


def _household_item(**extra: object) -> EvidenceItem:
    return EvidenceItem.model_validate(
        {
            "evidence_id": "EV-0123456789abcdef",
            "track_id": "DRT-W-q-0123456789ab",
            "subject_key": "q-0123456789ab",
            "channel": Channel.WEB,
            "source_kind": SourceKind.WEB_PAGE,
            "source_ref": "SNP-0123456789abcdef01234567",
            "source_url": "https://stat.example/rostlinne-napoje-2025",
            "source_title": "Spotřeba rostlinných nápojů 2025",
            "claim": "Rostlinné nápoje kupuje 45 % domácností.",
            "quote": "Rostlinné nápoje kupuje 45 % domácností.",
            "quote_span": (120, 160),
            "evidence_type": EvidenceType.OFFICIAL_REPORT,
            "source_date": "2025-06-30",
            "geography": "CZ",
            "population": "domácnosti",
            "topics": ("trh",),
            "data_class": DataClass.CLASS_C_INTERNAL,
            "agent_outcome_overlap": False,
            "agent_recommended_use": RecommendedUse.CONTEXT_ONLY,
            "agent_source_quality": 0.8,
            **extra,
        }
    )


#: The digest of :func:`_household_item`'s stored form, computed on ``develop`` at
#: 757154e, before ``EvidenceItem`` had measures. A sealed bundle re-dumps its items
#: to verify itself (``bundle.DeepResearchBundle.verify``): if this changes, every
#: bundle stored before measures existed stops verifying.
_DIGEST_BEFORE_MEASURES = "aede70c741fcbffe0a6a0e90e3d26ba918aa7e208c008257791596c6ce4851a4"


def test_an_item_without_measures_stores_and_digests_exactly_as_before_measures() -> None:
    item = _household_item()
    stored = item.model_dump(mode="json")
    assert "measures" not in stored
    assert digest(stored) == _DIGEST_BEFORE_MEASURES
    # A stored item (no "measures" key) reads back and re-dumps to the same bytes.
    again = EvidenceItem.model_validate(stored)
    assert again.measures == ()
    assert again.model_dump(mode="json") == stored
    assert EvidenceItem.model_validate_json(item.model_dump_json()) == item


def test_an_item_with_measures_keeps_them_and_refuses_a_malformed_one() -> None:
    measure = Measure(
        value=45,
        unit="%",
        period="Y2025",
        geography="CZ",
        population="HOUSEHOLDS",
        basis=MeasureBasis.ACTUAL,
    )
    item = _household_item(measures=(measure,))
    stored = item.model_dump(mode="json")
    assert stored["measures"] == [
        {
            "value": 45.0,
            "unit": "%",
            "scale": 1,
            "period": "Y2025",
            "geography": "CZ",
            "population": "HOUSEHOLDS",
            "denominator": None,
            "measure_name": None,
            "basis": "actual",
        }
    ]
    assert digest(stored) != _DIGEST_BEFORE_MEASURES
    assert EvidenceItem.model_validate(stored) == item
    # Not stated is None, never a default; a scale is a positive multiplier.
    assert Measure(value=3).model_dump()["population"] is None
    with pytest.raises(ValidationError):
        Measure(value=3, scale=0)
    with pytest.raises(ValidationError):
        Measure(value=math.inf)
    with pytest.raises(ValidationError):
        Measure.model_validate({"value": 3, "confidence": 0.9})


# --------------------------------------------------------------------------- the graph


def test_the_graph_is_the_planned_chain_under_deep_research() -> None:
    steps = deep_research_steps()
    validate_dag(steps)
    assert (
        [s.node_key for s in steps]
        == list(NODE_ORDER)
        == [
            "plan",
            "investigate",
            "merge",
            "verify",
            "synthesize",
            "publish",
        ]
    )
    assert [s.depends_on for s in steps] == [(), *[(n,) for n in NODE_ORDER[:-1]]]
    assert {s.stage_type for s in steps} == {DEEP_RESEARCH_STAGE}
    assert [s.kind for s in steps] == [DEEP_RESEARCH_KINDS[n] for n in NODE_ORDER]
    assert all(s.artifact_target in ARTIFACT_TYPES.values() for s in steps)


def test_steps_that_buy_one_answer_are_not_retried_and_checkpointed_ones_are() -> None:
    attempts = {s.node_key: s.max_attempts for s in deep_research_steps()}
    assert attempts["plan"] == attempts["synthesize"] == 1
    assert attempts["investigate"] > 1 and attempts["verify"] > 1


# --------------------------------------------------------------------------- tool cost


def _route(**overrides: object) -> ToolRoute:
    fields: dict[str, object] = {
        "route": ProviderRoute(
            route_id="search-recorded",
            provider="recorded",
            zone=ResidencyZone.EU,
            approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
        ),
        "tool": ToolKind.WEB_SEARCH,
        "adapter_id": "recorded-search-v1",
        "retrieval_mode": RetrievalMode.RECORDED,
        "price_usd_per_call": 0.0,
        **overrides,
    }
    return ToolRoute(**fields)  # type: ignore[arg-type]


def test_a_recorded_route_declares_that_it_costs_nothing() -> None:
    assert _route().route_id == "search-recorded"
    with pytest.raises(ValueError, match="no price"):
        _route(price_usd_per_call=0.008)
    assert _route(retrieval_mode=RetrievalMode.LIVE, price_usd_per_call=0.008)
    for bad in (-0.01, math.nan, math.inf):
        with pytest.raises(ValueError, match="finite"):
            _route(retrieval_mode=RetrievalMode.LIVE, price_usd_per_call=bad)
    with pytest.raises(ValueError, match="adapter"):
        _route(adapter_id=" ")


def _event(call: str, outcome: ToolOutcome, **fields: object) -> ToolUsageEvent:
    values: dict[str, object] = {
        "event_id": new_tool_event_id(),
        "call_id": call,
        "tool": ToolKind.WEB_SEARCH,
        "outcome": outcome,
        "route_id": "search-recorded",
        "retrieval_mode": RetrievalMode.RECORDED,
        "data_class": DataClass.CLASS_C_INTERNAL,
        "track_id": "DRT-W-q-0123456789ab",
        "reservation_id": None,
        "request_fingerprint": "f",
        "provider_request_id": None,
        "credits": 0,
        "cost_usd": 0.0,
        "ceiling_usd": 0.0,
        "occurred_at": NOW,
        **fields,
    }
    return ToolUsageEvent.model_validate(values)


def test_the_in_memory_ledger_brackets_every_call_and_never_charges_a_study() -> None:
    ledger = InMemoryToolLedger(budget_usd=0.05)
    assert ledger.charges_study_budget is False
    held = ledger.reserve(tool=ToolKind.WEB_SEARCH, route_id="r", track_id="t", amount_usd=0.03)
    with pytest.raises(ToolBudgetExhausted):
        ledger.reserve(tool=ToolKind.WEB_SEARCH, route_id="r", track_id="t", amount_usd=0.03)

    call = new_tool_call_id()
    reservation = {"reservation_id": held.reservation_id}
    with pytest.raises(ValueError, match="DISPATCHED"):
        ledger.dispatching(_event(call, ToolOutcome.SUCCEEDED, **reservation))
    with pytest.raises(ValueError, match="closes a dispatched call"):
        ledger.outcome(_event(call, ToolOutcome.SUCCEEDED, **reservation))
    ledger.dispatching(_event(call, ToolOutcome.DISPATCHED, **reservation))
    # A lost answer is charged at its ceiling, never as a free call.
    ledger.outcome(_event(call, ToolOutcome.UNCERTAIN, ceiling_usd=0.03, **reservation))
    assert ledger.committed_usd() == pytest.approx(0.03)
    assert [e.outcome for e in ledger.events()] == [ToolOutcome.DISPATCHED, ToolOutcome.UNCERTAIN]
    # The held amount was released when the call closed; what is left is what was not spent.
    ledger.reserve(tool=ToolKind.WEB_SEARCH, route_id="r", track_id="t", amount_usd=0.02)
    with pytest.raises(ToolBudgetExhausted):
        ledger.reserve(tool=ToolKind.WEB_SEARCH, route_id="r", track_id="t", amount_usd=0.001)


def test_a_refusal_is_recorded_without_a_dispatch() -> None:
    ledger = InMemoryToolLedger(budget_usd=0.0)
    ledger.outcome(_event(new_tool_call_id(), ToolOutcome.REFUSED, note="class not approved"))
    assert ledger.committed_usd() == 0.0 and len(ledger.events()) == 1


def test_a_ledger_takes_over_a_journal_and_closes_a_call_left_in_flight() -> None:
    served, refused, lost = new_tool_call_id(), new_tool_call_id(), new_tool_call_id()
    journal = [
        _event(served, ToolOutcome.DISPATCHED, ceiling_usd=0.02),
        _event(served, ToolOutcome.SUCCEEDED, cost_usd=0.02, ceiling_usd=0.02),
        _event(refused, ToolOutcome.REFUSED),
        _event(lost, ToolOutcome.DISPATCHED, ceiling_usd=0.03),  # its process died in flight
    ]
    closed_at = datetime(2026, 9, 27, 23, 50, tzinfo=UTC)
    ledger = InMemoryToolLedger(budget_usd=0.0)
    closures = ledger.adopt([*journal, journal[1]], closed_at=closed_at)  # a repeat is kept once

    assert [(c.call_id, c.outcome, c.occurred_at) for c in closures] == [
        (lost, ToolOutcome.UNCERTAIN, closed_at)
    ]
    assert closures[0].event_id != journal[3].event_id and closures[0].cost_usd == 0.0
    # What was served costs its price; what may have been served, its ceiling.
    assert ledger.committed_usd() == pytest.approx(0.05)
    assert [e.outcome for e in ledger.events()] == [
        ToolOutcome.DISPATCHED,
        ToolOutcome.SUCCEEDED,
        ToolOutcome.REFUSED,
        ToolOutcome.DISPATCHED,
        ToolOutcome.UNCERTAIN,
    ]
    # A later attempt that adopts the closure too has nothing left to close.
    assert (
        InMemoryToolLedger(budget_usd=0.0).adopt([*journal, *closures], closed_at=closed_at) == ()
    )
    # A ledger adopts only before its own first entry: the journal is history.
    with pytest.raises(ValueError, match="before its own first entry"):
        ledger.adopt(journal, closed_at=closed_at)


def test_a_ledger_refuses_an_impossible_budget() -> None:
    for bad in (-1.0, math.nan):
        with pytest.raises(ValueError):
            InMemoryToolLedger(budget_usd=bad)
