"""A research run records the LIVE population and reads nothing (population-operations P3).

The owner's call of 2026-10-10: once LIVE exists, every new run records the binding --
the version, weight and view it would be computed over -- while fieldwork keeps answering
with fictional respondents and says so. Pinned here, over the fictional population in
``conftest.py``: no LIVE records nothing; a new run records LIVE as it stands; a start that
finds its run returns it with what it recorded, never re-resolving; a retry keeps the
original's; and no step reads the population.
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.application.population import PopulationRuntime, live_binding
from aia_core.application.research import ResearchRuns
from aia_core.domain.fieldwork import FieldworkSource, PersonaSource, persona_source_of
from aia_core.domain.pipeline import ProjectType
from aia_core.domain.population import (
    PopulationBindingMissing,
    PopulationKind,
    PopulationView,
    ResolutionMode,
)
from aia_core.domain.workflow_templates import steps_for_workflow
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.workflow_repository import WorkflowRepository

AI = FieldworkSource.AI_RUNTIME
LIVE = "SYN_LIVE"
DESIGN = {
    "title": "Ranní nápoj",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
    "n": 120,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]}
            ],
        }
    ],
}


def _operator() -> Any:
    from aia_core.application.population_authority import (
        PopulationAuthority,
        PopulationOperatorConfig,
    )
    from aia_core.application.scope import AuthenticatedPrincipal

    config = PopulationOperatorConfig.from_names(
        {"operator": ("POPULATION_ESTABLISH", "POPULATION_PROMOTE")}
    )
    return PopulationAuthority(config).operator_context(
        AuthenticatedPrincipal(user_id="operator", organization_id="platform")
    )


@pytest.fixture
def population(session: Any, synthetic_population: Any) -> Any:
    """Import the fictional versions; ``establish()`` then makes STATIC and LIVE."""
    pop = synthetic_population
    runtime = PopulationRuntime(session, contract=pop.contract, source=pop.source)
    ids = {
        label: runtime.import_version(
            label=label,
            panel_location=pop.location(label),
            dictionary_location=pop.dictionary_location,
            provenance="fictional test bundle",
            imported_by="importer",
        ).version_id
        for label in ("v1_BASE", "v1_1", "v1_4")
    }

    def establish() -> str:
        operator = _operator()
        runtime.establish(
            operator=operator,
            population_id="SYN_STATIC",
            kind=PopulationKind.STATIC,
            version_id=ids["v1_1"],
            reason="the anchor",
        )
        runtime.establish(
            operator=operator,
            population_id=LIVE,
            kind=PopulationKind.LIVE,
            version_id=ids["v1_4"],
            reason="first LIVE",
        )
        return ids["v1_4"]

    pop.establish = establish
    return pop


@pytest.fixture
def runs(session: Any, scoped: Any, population: Any) -> Any:
    def build() -> ResearchRuns:
        return ResearchRuns(
            session,
            scoped.scope(user="lead"),
            population_contract=population.contract,
            population_id=LIVE,
        )

    return build


@pytest.fixture
def revision(session: Any, scoped: Any) -> str:
    repo = StudyDesignRepository(session, scoped.scope(user="lead"))
    created, _ = repo.submit_as_working_copy(content=DESIGN, source_stage="run")
    return created.revision_id


def _binding(session: Any, scoped: Any, run_id: str) -> Any:
    workflows = WorkflowRepository(session, scoped.scope(user="lead"))
    try:
        return workflows.population_binding(run_id)
    except PopulationBindingMissing:
        return None


def test_without_live_a_run_records_no_population(
    runs: Any, revision: str, session: Any, scoped: Any
) -> None:
    started = runs().start(design_revision_id=revision, fieldwork_source=AI)
    assert _binding(session, scoped, started.run_id) is None
    assert "population" not in runs().get(started.run_id)["metadata"]


def test_a_new_run_records_live_and_says_fieldwork_did_not_read_it(
    runs: Any, revision: str, population: Any, session: Any, scoped: Any
) -> None:
    live_version = population.establish()
    started = runs().start(design_revision_id=revision, fieldwork_source=AI)
    binding = _binding(session, scoped, started.run_id)
    assert binding is not None
    assert (binding.version_id, binding.population_id) == (live_version, LIVE)
    assert binding.resolution is ResolutionMode.LIVE_CURRENT
    assert binding.view is PopulationView.ANALYSIS
    assert runs().get(started.run_id)["metadata"]["population"] == {
        "population_id": LIVE,
        "version_id": live_version,
        "version_label": "v1_4",
        "read_by_fieldwork": False,
    }


def test_a_start_that_finds_its_run_returns_it_with_what_it_recorded(
    runs: Any, revision: str, population: Any, session: Any, scoped: Any
) -> None:
    before = runs().start(design_revision_id=revision, fieldwork_source=AI)
    population.establish()
    again = runs().start(design_revision_id=revision, fieldwork_source=AI)
    assert again.run_id == before.run_id and not again.created
    assert _binding(session, scoped, again.run_id) is None  # never re-resolved


def test_a_retry_keeps_the_population_its_original_recorded(
    runs: Any, revision: str, population: Any, session: Any, scoped: Any
) -> None:
    original = runs().start(design_revision_id=revision, fieldwork_source=AI).run_id
    runs().cancel(original)
    population.establish()  # LIVE exists now; the retry still names what the original did
    retry = runs().retry(original, fieldwork_source=AI)
    assert retry.created and retry.run_id != original
    assert _binding(session, scoped, retry.run_id) is None


def test_no_research_step_reads_the_population() -> None:
    for analysis in (False, True):
        for sociomapping in (False, True):
            steps = steps_for_workflow(
                "research",
                project_type=ProjectType.RESEARCH,
                analysis_enabled=analysis,
                sociomapping_enabled=sociomapping,
            )
            assert not any(s.consumes_population for s in steps)


def test_live_binding_is_none_until_live_exists_and_reads_no_panel(
    session: Any, population: Any
) -> None:
    assert live_binding(session, contract=population.contract, population_id=LIVE) is None
    population.establish()
    binding = live_binding(session, contract=population.contract, population_id=LIVE)
    assert binding is not None and binding.version_label == "v1_4"


# --- the persona source a run pins (plan panel-grounded-respondents 5c) --------------------

PANEL = PersonaSource.PANEL
ROSTER = PersonaSource.FICTIONAL_ROSTER


def test_a_run_pins_its_persona_source_and_a_run_before_the_pin_reads_as_the_roster(
    runs: Any, revision: str, population: Any
) -> None:
    population.establish()
    roster = runs().start(design_revision_id=revision, fieldwork_source=AI)
    run = runs().get(roster.run_id)
    assert run["metadata"]["persona_source"] == "fictional_roster"
    assert run["metadata"]["population"]["read_by_fieldwork"] is False
    assert persona_source_of({}) is ROSTER  # stored before 5c
    with pytest.raises(ValueError, match="unknown persona source"):
        persona_source_of({"persona_source": "imported_csv"})


def test_a_panel_run_is_its_own_run_reads_its_population_and_needs_one(
    runs: Any, revision: str, population: Any
) -> None:
    from aia_core.application.research import PanelPopulationMissing

    with pytest.raises(PanelPopulationMissing):
        runs().start(design_revision_id=revision, fieldwork_source=AI, persona_source=PANEL)
    population.establish()
    roster = runs().start(design_revision_id=revision, fieldwork_source=AI)
    panel = runs().start(design_revision_id=revision, fieldwork_source=AI, persona_source=PANEL)
    assert panel.created and panel.run_id != roster.run_id  # never the fictional run returned
    again = runs().start(design_revision_id=revision, fieldwork_source=AI, persona_source=PANEL)
    assert again.run_id == panel.run_id and not again.created
    meta = runs().get(panel.run_id)["metadata"]
    assert meta["persona_source"] == "panel"
    assert meta["population"]["read_by_fieldwork"] is True
    with pytest.raises(ValueError, match="ai_runtime"):
        runs().start(
            design_revision_id=revision,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            persona_source=PANEL,
        )


@pytest.mark.parametrize("original", [PANEL, ROSTER])
def test_a_retry_keeps_the_persona_source_its_original_pinned(
    runs: Any, revision: str, population: Any, original: PersonaSource
) -> None:
    """Whatever the deployment now says: the retry is not asked for a source at all."""
    population.establish()
    first = runs().start(design_revision_id=revision, fieldwork_source=AI, persona_source=original)
    runs().cancel(first.run_id)
    retry = runs().retry(first.run_id, fieldwork_source=AI)
    assert retry.created
    assert runs().get(retry.run_id)["metadata"]["persona_source"] == original.value


def test_a_panel_run_with_selected_dimensions_is_its_own_run_and_records_them(
    runs: Any, session: Any, scoped: Any, population: Any
) -> None:
    """Plan run-recovery-and-truth 5c: a panel run's personas read the selected dimensions as
    their topic allowlist, so such a run never shares an identity with a panel run made
    before the allowlist applied; a roster run is unchanged by them."""
    from aia_core.infrastructure.tables import WorkflowRunRow

    population.establish()
    repo = StudyDesignRepository(session, scoped.scope(user="lead"))
    chosen, _ = repo.submit_as_working_copy(
        content={**DESIGN, "persona_dimensions": {"approved": ["media", "nakup"]}},
        source_stage="run",
    )
    panel = runs().start(
        design_revision_id=chosen.revision_id, fieldwork_source=AI, persona_source=PANEL
    )
    roster = runs().start(design_revision_id=chosen.revision_id, fieldwork_source=AI)

    def key(run_id: str) -> str:
        row = session.get(WorkflowRunRow, run_id)
        assert row is not None
        return row.idempotency_key

    assert ":personas:panel:persona-topics:" in key(panel.run_id)
    assert ":persona-topics:" not in key(roster.run_id)
    selection = runs().get(panel.run_id)["metadata"]["selection"]
    assert selection["dimensions"] == ["media", "nakup"]
    assert selection["dimensions_reason"] == "dimensions_await_population_draw"
    assert runs().get(roster.run_id)["metadata"]["selection"]["dimensions_reason"] == (
        "dimensions_need_population_draw"
    )
