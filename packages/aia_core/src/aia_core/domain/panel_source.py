"""The panel persona source: a run's respondents drawn from the population it recorded.

Chunk 5b of ``plans/panel-grounded-respondents.md``. Given the population a run's binding
loaded and the specification it compiled, :func:`panel_plans` is everything the fieldwork
executor needs before its first model request, in the order the contract fixes (5a, decision 3):

1. the sample -- :func:`~.population.sampling.draw_panel_sample` under the design's recorded
   audience filters (``spec.selection``), its ``n`` and the run's seed;
2. the personas -- :func:`~.panel_persona.panel_personas` for exactly those rows;
3. the plans -- :meth:`~.panel_persona.PanelPersonas.plan` per respondent, each block shown the
   profile of its own topics.

Every refusal is the one its step raises, by name (``SamplingRefused``, ``PersonaRefused``),
before anything is sent or paid for; nothing here draws a smaller sample or builds a narrower
persona than asked.

:func:`respondent_system` names what a modelled validation is earned on (ADR 0024 §4) for a run
built here, and :meth:`PanelPlans.provenance` what the dataset artifact records about how its
respondents came to be.

Pure: stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from .ai_respondent import PROMPT_SHA256, RespondentPlan
from .fieldwork import PersonaSource
from .panel_persona import PANEL_PERSONA_VERSION, PanelPersonas, panel_personas
from .persona_profile import PERSONA_MODE, PROFILE_VERSION
from .population.runtime import RuntimePopulation
from .population.sampling import SAMPLER_VERSION, PanelSample, draw_panel_sample
from .research_design import ResearchSpecification
from .respondent_behavior import BEHAVIOR_VERSION
from .respondent_facts import FACT_LAYER_VERSION

__all__ = [
    "PANEL_SOURCE",
    "PanelPlans",
    "panel_plans",
    "respondent_system",
]

#: The persona source a run pins when its respondents are drawn from its population
#: (5a, decision 1); the other is ``fictional_roster``.
PANEL_SOURCE: Final = PersonaSource.PANEL.value


@dataclass(frozen=True, slots=True)
class PanelPlans:
    """One run's sample, its personas and a plan per respondent, in sample order."""

    sample: PanelSample
    personas: PanelPersonas
    plans: tuple[RespondentPlan, ...]

    def provenance(self, population: RuntimePopulation) -> dict[str, Any]:
        """What the fieldwork dataset records about where its respondents came from."""
        binding = population.binding
        return {
            "source": PANEL_SOURCE,
            "binding": {
                "version_id": binding.version_id,
                "version_label": binding.version_label,
                "content_sha256": binding.content_sha256,
                "weight_role": binding.weight_role,
            },
            "sample": self.sample.provenance(),
            "personas": self.personas.provenance(),
            "fictional": False,
        }


def panel_plans(
    population: RuntimePopulation, spec: ResearchSpecification, *, seed: int
) -> PanelPlans:
    """The run's respondents from ``population``, or the refusal of the step that could not.

    The audience is the design's recorded filters (5a, decision 4); a design that selected none
    draws from the whole population, as 18.6.6 did.
    """
    if spec.n is None or spec.n < 1:
        raise ValueError("a panel sample needs the design's n")
    filters = dict(spec.selection.audience_filters) if spec.selection is not None else None
    sample = draw_panel_sample(population, filters, spec.n, seed)
    personas = panel_personas(population, sample)
    plans = tuple(personas.plan(spec, persona) for persona in personas.personas)
    return PanelPlans(sample=sample, personas=personas, plans=plans)


def respondent_system(population: RuntimePopulation, *, model_binding: str) -> dict[str, str]:
    """The components of the respondent system a panel run's answers came from (ADR 0024 §4).

    ``model_binding`` is the provider, model and route the gateway resolved for the run's first
    request; everything else is a version this code pins.
    """
    return {
        "respondent_prompt_sha256": PROMPT_SHA256,
        "persona_builder": f"{PANEL_PERSONA_VERSION}/{PROFILE_VERSION}",
        "persona_mode": PERSONA_MODE,
        "sampler_version": SAMPLER_VERSION,
        "population_version": population.binding.version_id,
        "model_binding": model_binding,
        "response_process_version": f"{BEHAVIOR_VERSION}/{FACT_LAYER_VERSION}",
    }
