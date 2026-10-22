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

import hashlib
from dataclasses import dataclass
from typing import Any, Final

from .ai_respondent import RespondentPlan, respondent_prompt_sha256
from .fieldwork import PersonaSource
from .panel_persona import PANEL_PERSONA_VERSION, PanelPersonas, panel_personas, persona_allowlist
from .persona_profile import PERSONA_MODE, PROFILE_VERSION
from .population.runtime import RuntimePopulation
from .population.sampling import SAMPLER_VERSION, PanelSample, draw_panel_sample
from .research_design import ResearchSpecification
from .respondent_behavior import AIA_RESPONSE_V1, BEHAVIOR_VERSION, ResponseProcessSpec
from .respondent_facts import FACT_LAYER_VERSION

__all__ = [
    "PANEL_SOURCE",
    "PanelPlans",
    "joint_certificate_record",
    "panel_filters",
    "panel_plans",
    "pinned_components",
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
    #: The study's selected dimensions the profiles were filtered to (5c); empty: none.
    topic_allowlist: tuple[str, ...] = ()

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
            "personas": {
                **self.personas.provenance(),
                # Only when a selection applied, so a run without one records what it did.
                **(
                    {"persona_topic_allowlist": list(self.topic_allowlist)}
                    if self.topic_allowlist
                    else {}
                ),
            },
            "fictional": False,
        }


def panel_filters(spec: ResearchSpecification) -> dict[str, Any] | None:
    """The audience a panel run's sample is drawn from: the design's recorded filters; ``None``
    when it selected none (the whole population, as 18.6.6 drew)."""
    return dict(spec.selection.audience_filters) if spec.selection is not None else None


def panel_plans(
    population: RuntimePopulation,
    spec: ResearchSpecification,
    *,
    seed: int,
    response: ResponseProcessSpec = AIA_RESPONSE_V1,
) -> PanelPlans:
    """The run's respondents from ``population``, or the refusal of the step that could not.

    The audience is the design's recorded filters (5a, decision 4); a design that selected none
    draws from the whole population, as 18.6.6 did.
    """
    if spec.n is None or spec.n < 1:
        raise ValueError("a panel sample needs the design's n")
    sample = draw_panel_sample(population, panel_filters(spec), spec.n, seed)
    personas = panel_personas(population, sample, response=response)
    plans = tuple(personas.plan(spec, persona) for persona in personas.personas)
    return PanelPlans(
        sample=sample, personas=personas, plans=plans, topic_allowlist=persona_allowlist(spec)
    )


def respondent_system(
    population: RuntimePopulation, *, model_binding: str, scale_labels_in_prompt: bool = False
) -> dict[str, str]:
    """The components of the respondent system a panel run's answers came from (ADR 0024 §4).

    ``model_binding`` is the provider, model and route the gateway resolved for the run's first
    request; everything else is a version this code pins. ``scale_labels_in_prompt`` is whether
    the run's items carried their scale labels (``AIA_AI_SCALE_LABELS_IN_PROMPT``).
    """
    return {
        **pinned_components(
            population.binding.version_id, scale_labels_in_prompt=scale_labels_in_prompt
        ),
        "model_binding": model_binding,
    }


def joint_certificate_record(population: RuntimePopulation) -> dict[str, str] | None:
    """The certificate a panel run's respondents were drawn under, as its dataset records it:
    the text, its SHA-256 and the panel SHA-256 the loader verified it against. None when the
    population carries no certificate (its run's evidence is then judged uncertified)."""
    held = population.joint_certificate
    if held is None:
        return None
    data, panel_sha256 = held
    text = data.decode("utf-8-sig")
    # The digest is of the text as recorded (UTF-8, no byte-order mark), which is what is read.
    return {
        "certificate": text,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "panel_sha256": panel_sha256,
    }


def pinned_components(
    population_version: str, *, scale_labels_in_prompt: bool = False
) -> dict[str, str]:
    """Every respondent system component but the model binding: what this code pins, over
    ``population_version``. A validation's start compares these with its preregistration,
    before the gateway has resolved a binding (panel-grounded-respondents 7e3).

    With ``scale_labels_in_prompt`` the respondent prompt is another one, and so is its
    SHA-256 (``ai_respondent.respondent_prompt_sha256``); off, the components are exactly
    what they were before the switch existed."""
    return {
        "respondent_prompt_sha256": respondent_prompt_sha256(
            scale_labels_in_prompt=scale_labels_in_prompt
        ),
        "persona_builder": f"{PANEL_PERSONA_VERSION}/{PROFILE_VERSION}",
        "persona_mode": PERSONA_MODE,
        "sampler_version": SAMPLER_VERSION,
        "population_version": population_version,
        "response_process_version": f"{BEHAVIOR_VERSION}/{FACT_LAYER_VERSION}",
    }
