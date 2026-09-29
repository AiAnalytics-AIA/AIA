"""The ``ai_runtime`` fieldwork source: AI respondents on the fictional roster.

The executor half of :mod:`aia_core.domain.ai_respondent`. For one research run's
fieldwork attempt it builds the roster, classifies the material, asks the gateway
whether it may leave (and **parks** the run if not), then asks each respondent each
block through :class:`~aia_executors.ai_step.StepModelCaller` and draws the answers in
code. It returns the same validated ``FieldworkDataset`` every other source returns,
so Aggregate and the Sociomap read it unchanged.

What it never does: call a provider except through ``GovernedModelGateway``, pick a
persona source it was not given (there is one, the fictional roster), let a model set
an answer, id, weight, donor or fact, or retry anything on its own.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.domain.ai_contracts import ModelCallFailed
from aia_core.domain.ai_material import (
    MaterialApproval,
    most_restrictive_material,
)
from aia_core.domain.ai_material import (
    classify_material as classify_input,
)
from aia_core.domain.ai_respondent import (
    AGENT_ID,
    AGENT_VERSION,
    CONTRACT_VERSION,
    GENERATOR,
    PROMPT_ID,
    PROMPT_SHA256,
    PROMPT_VERSION,
    ROSTER_VERSION,
    RespondentOutputInvalid,
    UnsupportedFact,
    assemble_dataset,
    build_request,
    classify_material,
    fictional_roster,
    interpret_block,
    plan_items,
    plan_respondent,
)
from aia_core.domain.fieldwork import Answer
from aia_core.domain.providers import Provider
from aia_core.domain.research_design import ResearchSpecification
from aia_core.domain.respondent_behavior import BEHAVIOR_VERSION
from aia_core.domain.respondent_facts import FACT_LAYER_VERSION
from aia_core.domain.workflow import FailureClass
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_worker.executor import Failed, StepContext, StepInput

from .ai_step import StepModelCaller

__all__ = ["AIFieldwork", "AIFieldworkConfig", "ProducedDataset", "fieldwork_seed"]

#: Why a refused preflight parks the run: the gate's refusal is policy, not a defect.
_PARK_MESSAGE = (
    "AI respondenti nejsou pro tento výzkum povoleni: {why}. Běh čeká u sběru dat; nic "
    "nebylo odesláno ani vymyšleno. Po schválení trasy nebo licence spusťte běh znovu."
)


@dataclass(frozen=True, slots=True)
class AIFieldworkConfig:
    """What the composition decided; nothing here comes from a request or the browser."""

    policy_version: str
    provider: Provider
    reservation_usd: float
    max_output_tokens: int
    #: Legacy configuration retained for compatibility; it grants no classification.
    fictional_client_ids: frozenset[str]
    progress_every: int = 10
    material_approvals: tuple[MaterialApproval, ...] = ()


@dataclass(frozen=True, slots=True)
class ProducedDataset:
    """A dataset and the provenance that goes on its artifact."""

    dataset: Any
    provenance: dict[str, Any]


def fieldwork_seed(spec: ResearchSpecification) -> int:
    """The run's roster and draw seed: from the specification, so a rerun is the same."""
    return int(hashlib.sha256(spec.fingerprint().encode()).hexdigest()[:12], 16)


class AIFieldwork:
    """``research_fieldwork``'s producer for ``FieldworkSource.AI_RUNTIME``."""

    def __init__(
        self,
        *,
        gateway: GovernedModelGateway,
        config: AIFieldworkConfig,
        build: BuildIdentity,
        caller_factory: Callable[..., StepModelCaller] = StepModelCaller,
    ) -> None:
        self._gateway = gateway
        self._config = config
        self._build = build
        self._caller_factory = caller_factory

    def produce(
        self, spec: ResearchSpecification, step: StepInput, context: StepContext
    ) -> ProducedDataset | Failed:
        cfg = self._config
        if spec.n is None or spec.n < 1:
            return Failed(FailureClass.SCHEMA_VIOLATION, error={"message": "no sample size"})
        seed = fieldwork_seed(spec)
        personas = fictional_roster(spec.n, seed=seed)
        data_class, lineage = classify_material(
            personas,
            client_declared_fictional=True,  # the roster's actual fictional provenance, below
        )
        with context.transaction() as (session, workflow):
            run = workflow.get_run(step.run_id)
            revision_id = str(run["metadata"]["design_revision_id"])
            design = StudyDesignRepository(session, context.scope).content(revision_id)
        decision = classify_input(design, cfg.material_approvals)
        classified = most_restrictive_material([data_class, decision.data_class])
        if classified is None:
            return Failed(
                FailureClass.RUNTIME_UNAVAILABLE,
                error={
                    "reason": "egress_unclassified_material",
                    "message": "Zadání nemá klasifikaci vstupních dat. Nic nebylo odesláno.",
                },
            )
        data_class = classified
        try:
            plans = [plan_respondent(spec, p) for p in personas]
        except UnsupportedFact as exc:
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={
                    "message": f"Otázka se ptá na fakt, který respondent nemá: {exc}",
                    "reason": "respondent_fact_unsupported",
                },
            )
        items = {i.item_id: i for i in plan_items(spec)}
        caller = self._caller_factory(
            gateway=self._gateway,
            context=context,
            runtime_version=self._build.sha or "",
            provider=cfg.provider,
            reservation_usd=cfg.reservation_usd,
        )

        def request_for(index: int, block_index: int, answers: dict[str, Answer]) -> Any:
            plan = plans[index]
            return build_request(
                plan,
                plan.blocks[block_index],
                answers,
                items_by_id=items,
                policy_version=cfg.policy_version,
                data_class=data_class,
                lineage=lineage,
                max_output_tokens=cfg.max_output_tokens,
            )

        first = next((i for i, p in enumerate(plans) if p.blocks), None)
        resolution = None
        if first is not None:
            try:
                resolution = caller.preflight(request_for(first, 0, dict(plans[first].facts)))
            except ModelCallFailed as refused:
                return Failed(
                    FailureClass.RUNTIME_UNAVAILABLE,
                    error={
                        "message": _PARK_MESSAGE.format(why=str(refused)),
                        "reason": refused.reason,
                        "data_class": data_class.value,
                        "lineage": sorted(lineage.datasets),
                        "source": "ai_runtime",
                    },
                )

        calls: list[dict[str, Any]] = []
        rows: list[tuple[Any, dict[str, Answer]]] = []
        for index, plan in enumerate(plans):
            context.checkpoint()
            answers: dict[str, Answer] = dict(plan.facts)
            for block in plan.blocks:
                result = caller.invoke(request_for(index, block.index, answers))
                assert result.output is not None  # a structured agent's result has one
                try:
                    drawn, _ = interpret_block(block, result.output, plan.persona, seed=seed)
                except RespondentOutputInvalid as exc:
                    return Failed(
                        FailureClass.SCHEMA_VIOLATION,
                        error={
                            "message": f"Odpověď respondenta neprošla kontrolou: {exc}",
                            "reason": "respondent_output_invalid",
                            "call_id": result.call_id,
                            "provider_request_id": result.provider_request_id,
                        },
                    )
                answers.update(drawn)
                calls.append(
                    {
                        "respondent_id": plan.persona.persona_id,
                        "block": block.index,
                        "call_id": result.call_id,
                        "provider_request_id": result.provider_request_id,
                        "model": result.resolved_model,
                        "route_id": result.provenance.route_id,
                        "policy_version": result.provenance.policy_version,
                        "schema_fingerprint": result.provenance.schema_fingerprint,
                        "cost_usd": result.total_cost_usd,
                        "cost_basis": result.cost_basis.value,
                        "calls": len({e.call_id for e in result.usage_events}),
                    }
                )
            rows.append((plan.persona, answers))
            done = index + 1
            if done % max(1, cfg.progress_every) == 0 or done == len(plans):
                context.progress("AI respondenti odpověděli", respondents=done, of=len(plans))

        dataset = assemble_dataset(spec, rows, seed=seed)
        provenance = {
            "agent": {"id": AGENT_ID, "version": AGENT_VERSION},
            "prompt": {"id": PROMPT_ID, "version": PROMPT_VERSION, "sha256": PROMPT_SHA256},
            "contract_version": CONTRACT_VERSION,
            "generator": GENERATOR,
            "behavior_version": BEHAVIOR_VERSION,
            "fact_layer_version": FACT_LAYER_VERSION,
            "persona_source": {"roster": ROSTER_VERSION, "fictional": True, "seed": seed},
            "data_class": data_class.value,
            "material_classification": decision.model_dump(mode="json"),
            "lineage": sorted(lineage.datasets),
            "policy_version": cfg.policy_version,
            "route_id": resolution.route_id if resolution else None,
            "model": resolution.model if resolution else None,
            "runtime_version": self._build.sha,
            "attempt_id": step.attempt_id,
            "calls": calls,
            "total_cost_usd": sum(c["cost_usd"] for c in calls),
        }
        return ProducedDataset(dataset=dataset, provenance=provenance)
