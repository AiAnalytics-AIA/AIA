"""The coverage ledger of a real recorded run (plan chunk 47).

The journey of ``test_deep_research_journey.py`` -- the real worker, gateway and gate over
recorded exchanges -- read back through ``DeepResearchRuns.coverage``. Every count must
reconcile with the run's sealed bundle and its own tool journal, and a second pass that
reuses tracks counts them once, as reused, with none of their calls.
"""

from __future__ import annotations

from collections import Counter

from aia_core.application.deep_research import DeepResearchRuns
from aia_core.domain.deep_research.contracts import QueryDecision
from aia_core.domain.deep_research.coverage import COVERAGE_VERSION, CoverageLedger
from aia_core.domain.deep_research.tooling import ToolKind, ToolOutcome, ToolUsageEvent
from aia_core.infrastructure.storage import InMemoryArtifactStore
from test_deep_research_journey import (  # type: ignore[import-not-found]
    DESIGN_2,
    Journey,
    ResearchWorld,
    drain,
    pass_one,  # noqa: F401  (a fixture)
    read,
    research,  # noqa: F401  (a fixture)
    start,
    tool_events,
)


def _ledger(world: ResearchWorld, run_id: str, store: InMemoryArtifactStore) -> CoverageLedger:
    with world.sessions() as session:
        return DeepResearchRuns(session, world.lead_scope(session)).coverage(run_id, store=store)


def _journal(world: ResearchWorld, run_id: str) -> list[ToolUsageEvent]:
    return [ToolUsageEvent.model_validate(e["payload"]) for e in tool_events(world, run_id)]


def test_every_count_reconciles_with_the_bundle_and_the_journal(
    pass_one: Journey,  # noqa: F811
    store: InMemoryArtifactStore,
) -> None:
    world, run_id = pass_one.world, pass_one.run_id
    _run, bundle = read(world, run_id, store)
    ledger = _ledger(world, run_id, store)
    assert ledger.version == COVERAGE_VERSION and ledger.bundle_sha256 == bundle.sha256

    # Findings: what the bundle kept and what it set aside, by reason.
    assert ledger.findings_accepted == len(bundle.accepted)
    assert ledger.findings_quarantined == len(bundle.quarantined)
    assert sum(ledger.quarantined_by_reason.values()) == len(bundle.quarantined)
    assert Counter(ledger.quarantined_by_reason) == Counter(
        q.reason.value for q in bundle.quarantined
    )

    # Queries: every proposed query was sent or refused, and the refusals have reasons.
    queries = [q for t in bundle.tracks for q in t.queries]
    assert ledger.queries_proposed == len(queries) == ledger.queries_sent + ledger.queries_refused
    assert ledger.queries_sent == sum(1 for q in queries if q.decision is QueryDecision.SENT)
    assert sum(ledger.queries_refused_by_reason.values()) == ledger.queries_refused
    assert ledger.hits == sum(q.hits for q in queries)
    assert ledger.sources_captured == len(bundle.snapshots)

    # Tools: the journal's own outcomes, one row per kind, every sent call closed.
    journal = _journal(world, run_id)
    tools = {t.tool: t for t in ledger.tools}
    for tool, row in tools.items():
        mine = [e for e in journal if e.tool is tool]
        assert row.sent == sum(1 for e in mine if e.outcome is ToolOutcome.DISPATCHED)
        assert row.refused == sum(1 for e in mine if e.outcome is ToolOutcome.REFUSED)
        assert row.succeeded + row.failed + row.uncertain == row.sent
        assert sum(row.refused_by_reason.values()) == row.refused
    assert tools[ToolKind.WEB_SEARCH].sent == bundle.counts["search_calls"]

    # Per track: the totals are their sums; a blocked track sent nothing.
    assert sum(t.queries_sent for t in ledger.by_track) == ledger.queries_sent
    for t in ledger.by_track:
        if t.status == "BLOCKED":
            assert t.queries_sent == 0 and t.sources_captured == 0
    assert ledger.blocked_tracks == sum(1 for t in bundle.tracks if t.status.value == "BLOCKED")

    # The journey's own exclusions, by name: what a reader is shown was refused and why.
    assert ledger.queries_refused_by_reason == {
        "class_a_query": 1,
        "egress_route_not_approved_for_class": 1,
    }
    assert tools[ToolKind.WEB_FETCH].failed_by_reason == {"address_not_public": 1}
    assert {
        "source_contains_instructions",
        "low_source_quality",
        "ungrounded_excerpt",
        "number_not_in_quote",
    } <= set(ledger.quarantined_by_reason)


def test_a_reused_track_is_counted_once_as_reused_and_none_of_its_calls_are_this_runs(
    pass_one: Journey,  # noqa: F811
    store: InMemoryArtifactStore,
) -> None:
    world, w = pass_one.world, pass_one.worker
    second_run = start(world, DESIGN_2)
    assert drain(w) == 6
    _run, second = read(world, second_run, store)
    ledger = _ledger(world, second_run, store)
    reused = {t.track_id for t in second.tracks if t.reused}
    assert ledger.reused_tracks == len(reused) > 0
    assert {t.track_id for t in ledger.by_track if t.reused} == reused
    # This run's journal holds no call of a track it took as stored.
    assert not {e.track_id for e in _journal(world, second_run)} & reused


def test_the_ledger_is_read_and_never_sealed(
    pass_one: Journey,  # noqa: F811
    store: InMemoryArtifactStore,
) -> None:
    world, run_id = pass_one.world, pass_one.run_id
    _run, before = read(world, run_id, store)
    first, again = _ledger(world, run_id, store), _ledger(world, run_id, store)
    _run, after = read(world, run_id, store)
    assert first == again
    assert before.sha256 == after.sha256 and after.verify()
