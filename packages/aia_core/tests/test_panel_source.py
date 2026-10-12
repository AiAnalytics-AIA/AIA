"""The panel persona source (chunk 5b): sample, personas and plans from a run's population.

The population is the sampler's fictional fixture, 3,000 rows on 400 donors with the persona
companions, loaded as the ANALYSIS view a run binds (``conftest.sampled_population``). What
the sampler and the personas compute is tested in their own suites against the unit; here,
that they compose in the contract's order and that each refusal surfaces by name before
anything else is built.
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.ai_respondent import PROMPT_SHA256, dataset_origin
from aia_core.domain.evidence import respondent_system_fingerprint
from aia_core.domain.fieldwork import DataOrigin
from aia_core.domain.panel_persona import PersonaRefused
from aia_core.domain.panel_source import PANEL_SOURCE, panel_plans, respondent_system
from aia_core.domain.population.sampling import SAMPLER_VERSION, SamplingRefused
from aia_core.domain.research_design import ResearchSpecification, compile_design


def _spec(n: int = 200, audience: dict[str, Any] | None = None) -> ResearchSpecification:
    design: dict[str, Any] = {
        "title": "Ranní nápoj",
        "n": n,
        "sections": [
            {
                "type": "questions",
                "questions": [
                    {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                    {
                        "id": "q2",
                        "text": "Co si ráno koupíte?",
                        "typ": "vyber",
                        "kategorie": ["Kávu", "Čaj", "Nic"],
                    },
                ],
            }
        ],
    }
    if audience is not None:
        design["audience"] = {"filters": audience}
    spec, problems = compile_design(design)
    assert spec is not None, problems
    return spec


@pytest.fixture
def population(sampled_population: Any) -> Any:
    return sampled_population().population


def test_a_panel_run_is_sampled_built_and_planned_in_that_order(population: Any) -> None:
    spec = _spec(200)
    built = panel_plans(population, spec, seed=11)
    assert len(built.sample.respondents) == len(built.personas.personas) == len(built.plans) == 200
    ids = population.column("panel_row_id")
    assert [p.persona.persona_id for p in built.plans] == [
        str(ids[r.row]) for r in built.sample.respondents
    ]
    assert all(len(p.profiles) == len(p.blocks) for p in built.plans)
    # Panel-built personas make a modelled dataset, never a fictional one (4b).
    assert dataset_origin([p.persona for p in built.plans]) is DataOrigin.MODELLED_AI_PANEL
    # The run's seed decides it: the same rows, personas and profiles again. (The catalog holds
    # NaN priorities, which never compare equal, so the plans are compared, not the object.)
    again = panel_plans(population, spec, seed=11)
    assert again.sample == built.sample and again.plans == built.plans
    assert panel_plans(population, spec, seed=12).sample != built.sample


def test_panel_personas_are_styled_under_the_runs_response_process(population: Any) -> None:
    """Plan methodology-tab R1b: the same sample, styled under the process the run pinned."""
    from aia_core.domain.respondent_behavior import AIA_RESPONSE_V1

    spec = _spec(60)
    unit = panel_plans(population, spec, seed=11)
    edited = AIA_RESPONSE_V1.model_copy(
        update={"methodology_version": "aia-response-1+e1", "style_noise_floor": 1.0}
    )
    other = panel_plans(population, spec, seed=11, response=edited)
    assert other.sample == unit.sample  # who is drawn does not depend on the process
    assert [p.style for p in other.personas.personas] != [p.style for p in unit.personas.personas]
    # Naming the default process is the default. Compared as the sibling test compares (the
    # catalog's NaN priorities never compare equal, so the whole object cannot be): the
    # sample, every plan, and every persona's style, which is what the process decides.
    same = panel_plans(population, spec, seed=11, response=AIA_RESPONSE_V1)
    assert same.sample == unit.sample and same.plans == unit.plans
    assert [p.style for p in same.personas.personas] == [p.style for p in unit.personas.personas]


def test_the_designs_audience_filters_are_what_the_sample_draws_under(population: Any) -> None:
    """5a decision 4: applied, as 18.6.6 did; recorded in the sample's provenance."""
    spec = _spec(100, audience={"vek": {"min": 60, "max": 89}})
    assert spec.selection is not None and spec.selection.audience_filters
    built = panel_plans(population, spec, seed=3)
    ages = population.column("vek")
    assert all(60 <= int(ages[r.row]) <= 89 for r in built.sample.respondents)
    record = built.provenance(population)
    assert record["sample"]["filters"] == {"vek": {"min": 60, "max": 89}}
    assert record["source"] == PANEL_SOURCE and record["fictional"] is False
    assert record["binding"]["version_id"] == population.binding.version_id
    assert record["personas"]["persona_source"] == "aia-panel-persona-source-1"


def test_a_sampling_refusal_surfaces_by_name_before_any_persona_is_built(
    population: Any,
) -> None:
    with pytest.raises(SamplingRefused) as exceeded:
        panel_plans(population, _spec(population.row_count + 1), seed=1)
    assert exceeded.value.reason == "sampling_n_exceeds_support"
    with pytest.raises(SamplingRefused) as small:
        panel_plans(population, _spec(8), seed=1)
    assert small.value.reason == "sampling_unrepresentative"  # OI-99, the owner's decision
    with pytest.raises(ValueError, match="n"):
        panel_plans(population, _spec(10).model_copy(update={"n": None}), seed=1)


def test_a_persona_refusal_surfaces_by_name(sampled_population: Any) -> None:
    population = sampled_population(omit=("PERSONA_SIGNAL_CATALOG_v17.csv",)).population
    with pytest.raises(PersonaRefused) as missing:
        panel_plans(population, _spec(200), seed=1)
    assert missing.value.reason == "persona_catalog_missing"


def test_the_respondent_system_names_every_component_and_fingerprints(population: Any) -> None:
    system = respondent_system(population, model_binding="aws_bedrock/model-x/bedrock-eu-primary")
    assert system["respondent_prompt_sha256"] == PROMPT_SHA256
    assert system["sampler_version"] == SAMPLER_VERSION
    assert system["population_version"] == population.binding.version_id
    assert system["persona_mode"]
    assert len(respondent_system_fingerprint(system)) == 64
    other = respondent_system(population, model_binding="aws_bedrock/model-y/bedrock-eu-primary")
    assert respondent_system_fingerprint(other) != respondent_system_fingerprint(system)
