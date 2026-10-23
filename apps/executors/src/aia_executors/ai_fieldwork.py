"""The ``ai_runtime`` fieldwork source: AI respondents, fictional or drawn from the population.

The executor half of :mod:`aia_core.domain.ai_respondent`. For one research run's
fieldwork attempt it builds the roster, classifies the material, asks the gateway
whether it may leave (and **parks** the run if not), then asks each respondent each
block through :class:`~aia_executors.ai_step.StepModelCaller` and draws the answers in
code. It returns the same validated ``FieldworkDataset`` every other source returns,
so Aggregate and the Sociomap read it unchanged.

Who the respondents are is the run's pin (``persona_source``, plan
``panel-grounded-respondents`` 5c): the fictional roster, or -- where the composition gives it a
population loader (5d) -- respondents sampled from the population the run recorded
(:func:`~aia_core.domain.panel_source.panel_plans`), whose dataset is ``MODELLED_AI_PANEL`` and
names its respondent system.

What it never does: call a provider except through ``GovernedModelGateway``, answer a run with a
persona source other than the one it pinned, let a model set an answer, id, weight, donor or
fact, or retry anything on its own.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import monotonic
from typing import Any

from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.application.population import PopulationRuntime
from aia_core.domain.ai_contracts import ModelCallFailed, ModelRequest
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
    SCALE_LABEL_WORDING,
    RespondentOutputInvalid,
    RespondentPlan,
    UnsupportedFact,
    assemble_dataset,
    build_request,
    classify_material,
    fictional_roster,
    fieldwork_seed,
    interpret_block,
    plan_items,
    plan_respondent,
)
from aia_core.domain.deployment import DataClassGates
from aia_core.domain.fieldwork import Answer, PersonaSource, persona_source_of
from aia_core.domain.fieldwork_events import (
    HEARTBEAT_SECONDS,
    FieldworkEvent,
    progress,
    progress_due,
)
from aia_core.domain.licence import DataLineage
from aia_core.domain.material_rules import MaterialRule, classify_by_rule
from aia_core.domain.methodology.pins import is_units_process, read_response_pin
from aia_core.domain.panel_persona import PersonaRefused
from aia_core.domain.panel_source import (
    PanelPlans,
    joint_certificate_record,
    panel_plans,
    respondent_system,
)
from aia_core.domain.pipeline import fingerprint
from aia_core.domain.population.czech import CZ_SYNTHETIC_V17
from aia_core.domain.population.enrichment import AudienceDimensionsEnricher
from aia_core.domain.population.errors import PopulationError
from aia_core.domain.population.runtime import RuntimePopulation
from aia_core.domain.population.sampling import SamplingRefused
from aia_core.domain.providers import Provider
from aia_core.domain.research_design import ResearchSpecification
from aia_core.domain.residency import DataClass
from aia_core.domain.respondent_behavior import BEHAVIOR_VERSION, ResponseProcessSpec
from aia_core.domain.respondent_facts import FACT_LAYER_VERSION
from aia_core.domain.workflow import FailureClass
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.fieldwork_journal import FieldworkJournal
from aia_core.infrastructure.population_source import PopulationAssetSource
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_worker.executor import Failed, StepContext, StepInput
from sqlalchemy.orm import Session

from .ai_step import StepModelCaller

__all__ = [
    "AIFieldwork",
    "AIFieldworkConfig",
    "PopulationLoader",
    "ProducedDataset",
    "fieldwork_seed",
    "population_loader",
]

#: Loads the population a run recorded, inside the step's transaction.
PopulationLoader = Callable[[Session, WorkflowRepository, str], RuntimePopulation]


def population_loader(source: PopulationAssetSource) -> PopulationLoader:
    """The worker's loader: the run's recorded binding, as the ANALYSIS view with its enricher."""

    def load(session: Session, workflow: WorkflowRepository, run_id: str) -> RuntimePopulation:
        runtime = PopulationRuntime(
            session,
            contract=CZ_SYNTHETIC_V17,
            source=source,
            enricher=AudienceDimensionsEnricher(),
        )
        return runtime.load_for_run(workflow, run_id)

    return load


#: Why a refused preflight parks the run: the gate's refusal is policy, not a defect.
_PARK_MESSAGE = (
    "AI respondenti nejsou pro tento výzkum povoleni: {why}. Běh čeká u sběru dat; nic "
    "nebylo odesláno ani vymyšleno. Po schválení trasy nebo licence pokračujte v běhu na Průběhu."
)


#: Why a run whose respondents come from its population waits on a worker without that path.
_POPULATION_UNAVAILABLE = (
    "Populaci, ze které má tento běh respondenty, se nepodařilo načíst: {why}. Běh čeká u sběru "
    "dat; nic nebylo odesláno ani vymyšleno."
)
_PANEL_UNAVAILABLE = (
    "Tento běh má respondenty z populace, ale pracovník je neumí sestavit. Běh čeká u sběru "
    "dat; nic nebylo odesláno ani vymyšleno."
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
    #: ``AIA_AI_SCALE_LABELS_IN_PROMPT`` (off by default): a scale question's verbal labels in
    #: its item, in the provisional wording the methodology owner signs before it is switched
    #: on (input-interactions 3b). On, it changes the respondent prompt's identity, so the
    #: dataset's respondent system and provenance say so.
    scale_labels_in_prompt: bool = False
    #: ``AIA_DATA_CLASS_GATES`` (plan develop-class-advisory), the gateway's own: advisory on
    #: develop only, where the validation's arms send an unclassified specification.
    class_gates: DataClassGates = DataClassGates.ENFORCE
    #: ``AIA_AI_FIELDWORK_CHECKPOINT`` (off by default, run-qc-and-checkpoint RQC0): each
    #: answered respondent block is kept under the lease the moment it returns, and an
    #: interrupted attempt or a retry of the run replays it instead of paying again. Two
    #: lease-fenced writes per block, so it is a switch (CLAUDE.md § 8).
    checkpoint: bool = False
    #: ``AIA_AI_FIELDWORK_HEARTBEAT`` (off by default, run-qc-and-checkpoint RQC7a): a
    #: ``fieldwork_progress`` between a respondent's blocks once ``HEARTBEAT_SECONDS`` passed
    #: without one, so slow answering never reads as a stalled step. At most two lease-fenced
    #: feed writes a minute, so it is a switch (CLAUDE.md § 8).
    heartbeat: bool = False


@dataclass(frozen=True, slots=True)
class ProducedDataset:
    """A dataset and the provenance that goes on its artifact."""

    dataset: Any
    provenance: dict[str, Any]
    #: A modelled dataset's respondent system (ADR 0024 §4), for the artifact's metadata;
    #: ``None`` for a fictional one, which is never validated.
    respondent_system: dict[str, str] | None = None
    #: A modelled dataset's population certificate (complete-study-report B5a); ``None`` for a
    #: fictional one and for a population that carries none.
    joint_certificate: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class Answered:
    """Every plan answered: each respondent's answers, the call ledger, the route preflighted."""

    rows: list[tuple[Any, dict[str, Answer]]]
    calls: list[dict[str, Any]]
    #: The preflight's resolution; ``None`` when no plan had a block (every answer a fact).
    resolution: Any
    #: Per respondent, in ``rows``' order: what each item's draw recorded (its probabilities).
    details: list[dict[str, dict[str, Any]]]
    #: Whether the requests carried the scale labels: the value used, which is what the
    #: dataset records, never the composition's switch read again.
    scale_labels_in_prompt: bool = False


def request_key(request: ModelRequest, binding: str) -> str:
    """What identifies a respondent block's answer: exactly what was sent, to which model and
    route, under which policy, contract and class. The block's output contract follows from its
    items, which the messages carry, so its version stands for it."""
    agent = request.agent
    return fingerprint(
        {
            "agent": [agent.agent_id, agent.version, CONTRACT_VERSION],
            "binding": binding,
            "policy": request.policy_version,
            "class": request.data_classification.value if request.data_classification else None,
            "max_output_tokens": request.max_output_tokens,
            "system": request.system,
            "messages": [[m.role, m.content] for m in request.messages],
        }
    )


class _RunJournal:
    """A run lineage's kept answers: read once, each new one written in its own lease-fenced
    transaction before the next request leaves."""

    def __init__(self, context: StepContext, lineage_run_id: str) -> None:
        self._context = context
        self._lineage = lineage_run_id

    def _journal(self, session: Session) -> FieldworkJournal:
        return FieldworkJournal(session, self._context.scope, lineage_run_id=self._lineage)

    def kept(self) -> dict[str, dict[str, Any]]:
        with self._context.transaction() as (session, _):
            return self._journal(session).kept()

    def put(self, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Keep ``payload`` once; returns what is kept (an earlier answer wins a race)."""
        with self._context.transaction() as (session, _):
            return self._journal(session).put(
                key, run_id=self._context.step.run_id, payload=payload
            )


class AIFieldwork:
    """``research_fieldwork``'s producer for ``FieldworkSource.AI_RUNTIME``."""

    def __init__(
        self,
        *,
        gateway: GovernedModelGateway,
        config: AIFieldworkConfig,
        build: BuildIdentity,
        caller_factory: Callable[..., StepModelCaller] = StepModelCaller,
        population: PopulationLoader | None = None,
    ) -> None:
        self._gateway = gateway
        self._config = config
        self._build = build
        self._caller_factory = caller_factory
        self._population = population

    @property
    def class_gates(self) -> DataClassGates:
        """``AIA_DATA_CLASS_GATES`` as composed: whether a class-only refusal is advisory."""
        return self._config.class_gates

    @property
    def population(self) -> PopulationLoader | None:
        """The loader of a run's recorded population; ``None`` when this composition reads none
        (``AIA_AI_POPULATION_PERSONAS_ENABLED`` off)."""
        return self._population

    def answer_plans(
        self,
        plans: Sequence[RespondentPlan],
        spec: ResearchSpecification,
        context: StepContext,
        *,
        seed: int,
        response: ResponseProcessSpec,
        data_class: DataClass,
        lineage: DataLineage,
        require_binding: str | None = None,
        scale_labels_in_prompt: bool | None = None,
        journal: _RunJournal | None = None,
    ) -> Answered | Failed:
        """Ask the model every block of every plan and draw the answers by code.

        Everything fieldwork does after the plans are chosen: the preflight on the first plan
        with a block, one request per respondent block, the draw, the call ledger and the
        progress. It depends only on its arguments, so a caller with plans of its own (the
        validation's arms, panel-grounded-respondents 7e) answers them exactly as a run does.

        ``require_binding`` is the provider, model and route the answers must come from (a
        validation's preregistered binding): the preflight's resolution is compared with it
        before the first request, and a different one fails by name, nothing sent.

        ``scale_labels_in_prompt`` overrides the composition's switch: a validation's arms ask
        the respondent system it preregistered, which names its prompt.

        ``journal`` keeps each answered block and replays a kept one instead of sending it again
        (RQC0). A replayed block's call record says so and costs this attempt nothing.
        """
        cfg = self._config
        labelled = (
            cfg.scale_labels_in_prompt
            if scale_labels_in_prompt is None
            else (scale_labels_in_prompt)
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
                response=response,
                scale_labels_in_prompt=labelled,
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
            resolved = self.binding(resolution)
            if require_binding is not None and resolved != require_binding:
                # The respondent system is not the one asked for: a different system's answers
                # would be scored as this one's. Permanent, never retried, nothing sent.
                return Failed(
                    FailureClass.SCHEMA_VIOLATION,
                    error={
                        "message": (
                            f"Model {resolved} není model {require_binding}, pro který byl běh "
                            "zaregistrován. Nic nebylo odesláno."
                        ),
                        "reason": "model_binding_changed",
                        "expected": require_binding,
                        "resolved": resolved,
                    },
                )

        binding = self.binding(resolution) if resolution is not None else ""
        kept = journal.kept() if journal is not None else {}
        calls: list[dict[str, Any]] = []
        rows: list[tuple[Any, dict[str, Answer]]] = []
        details: list[dict[str, dict[str, Any]]] = []
        sent = replayed = 0
        last_report = monotonic()

        def report(done: int) -> None:
            nonlocal last_report
            context.progress(
                FieldworkEvent.PROGRESS,
                **progress(respondents=done, of=len(plans), sent=sent, replayed=replayed),
            )
            last_report = monotonic()

        for index, plan in enumerate(plans):
            context.checkpoint()
            answers: dict[str, Answer] = dict(plan.facts)
            detail: dict[str, dict[str, Any]] = {}
            for block in plan.blocks:
                request = request_for(index, block.index, answers)
                contract = request.agent.output_contract
                assert contract is not None  # a respondent block's agent is structured
                key = request_key(request, binding)
                answer = kept.get(key)
                if answer is not None:
                    output = contract.model_validate(answer["output"])
                    # Paid for by the run that answered it; this attempt sent nothing. Two
                    # respondents can send the same request, so the record names this one.
                    record = {
                        **answer["call"],
                        "respondent_id": plan.persona.persona_id,
                        "block": block.index,
                        "replayed_from_run": answer["run_id"],
                        "cost_usd": 0.0,
                        "calls": 0,
                    }
                else:
                    result = caller.invoke(request)
                    assert result.output is not None  # a structured agent's result has one
                    output = result.output
                    record = {
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
                try:
                    drawn, meta = interpret_block(
                        block, output, plan.persona, seed=seed, response=response
                    )
                except RespondentOutputInvalid as exc:
                    return Failed(
                        FailureClass.SCHEMA_VIOLATION,
                        error={
                            "message": f"Odpověď respondenta neprošla kontrolou: {exc}",
                            "reason": "respondent_output_invalid",
                            "call_id": record["call_id"],
                            "provider_request_id": record["provider_request_id"],
                        },
                    )
                if journal is not None and answer is None:
                    # Kept only once the draw accepted it, before the next request leaves: a
                    # stop after this point never pays for this block again. A raced attempt's
                    # earlier answer wins, and the draw is taken from what is kept.
                    dumped = output.model_dump(mode="json", by_alias=True)
                    stored = journal.put(
                        key, {"output": dumped, "call": record, "run_id": context.step.run_id}
                    )
                    if stored["output"] != dumped:
                        drawn, meta = interpret_block(
                            block,
                            contract.model_validate(stored["output"]),
                            plan.persona,
                            seed=seed,
                            response=response,
                        )
                answers.update(drawn)
                detail.update(meta)
                calls.append(record)
                if answer is None:
                    sent += 1
                else:
                    replayed += 1
                # The heartbeat between a respondent's blocks (the last one is counted below), so
                # a respondent of many blocks on a slow model still reports. A single call that
                # takes longer writes nothing until it returns: Průběh shows the step's own time.
                last_block = block is plan.blocks[-1]
                quiet = monotonic() - last_report >= HEARTBEAT_SECONDS
                if cfg.heartbeat and not last_block and quiet:
                    report(index)
            rows.append((plan.persona, answers))
            details.append(detail)
            done = index + 1
            idle = monotonic() - last_report if cfg.heartbeat else 0.0
            if progress_due(
                respondents=done, of=len(plans), idle_seconds=idle, every=cfg.progress_every
            ):
                report(done)

        return Answered(
            rows=rows,
            calls=calls,
            resolution=resolution,
            details=details,
            scale_labels_in_prompt=labelled,
        )

    def binding(self, resolution: Any) -> str:
        """The provider, model and route a preflight resolved, as a respondent system names it."""
        return f"{self._config.provider.value}/{resolution.model}/{resolution.route_id}"

    def material(self, value: Any) -> Any:
        """``value``'s classification under the operator's content-bound approvals; unknown is
        ``None``, never a class (``ai_material.classify_material``)."""
        return classify_input(value, self._config.material_approvals)

    def produce(
        self, spec: ResearchSpecification, step: StepInput, context: StepContext
    ) -> ProducedDataset | Failed:
        cfg = self._config
        try:
            persona_source = persona_source_of(step.payload)
        except ValueError as exc:
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={"message": str(exc), "reason": "persona_source_unknown"},
            )
        if persona_source is PersonaSource.PANEL and self._population is None:
            # The run pinned respondents drawn from its population; this worker composes no
            # panel path. It waits, and never answers with the fictional roster instead.
            return Failed(
                FailureClass.RUNTIME_UNAVAILABLE,
                error={
                    "message": _PANEL_UNAVAILABLE,
                    "reason": "panel_personas_unavailable",
                    "source": "ai_runtime",
                },
            )
        if spec.n is None or spec.n < 1:
            return Failed(FailureClass.SCHEMA_VIOLATION, error={"message": "no sample size"})
        seed = fieldwork_seed(spec)
        try:
            response = read_response_pin(step.payload.get("response"))
        except ValueError as exc:
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={"reason": "response_pin_invalid", "message": str(exc)},
            )
        population: RuntimePopulation | None = None
        built: PanelPlans | None = None
        if persona_source is PersonaSource.PANEL:
            assert self._population is not None  # parked above otherwise
            try:
                with context.transaction() as (session, workflow):
                    population = self._population(session, workflow, step.run_id)
                built = panel_plans(population, spec, seed=seed, response=response)
            except (SamplingRefused, PersonaRefused) as refused:
                # The design asks for a sample or a persona this population cannot give: no
                # smaller sample, no narrower persona, and nothing sent.
                return Failed(
                    FailureClass.SCHEMA_VIOLATION,
                    error={"message": str(refused), "reason": refused.reason},
                )
            except UnsupportedFact as exc:
                return Failed(
                    FailureClass.SCHEMA_VIOLATION,
                    error={
                        "message": f"Otázka se ptá na fakt, který respondent nemá: {exc}",
                        "reason": "respondent_fact_unsupported",
                    },
                )
            except PopulationError as exc:
                return Failed(
                    FailureClass.RUNTIME_UNAVAILABLE,
                    error={
                        "message": _POPULATION_UNAVAILABLE.format(why=str(exc)),
                        "reason": "population_unavailable",
                        "source": "ai_runtime",
                    },
                )
            personas = tuple(plan.persona for plan in built.plans)
        else:
            personas = fictional_roster(spec.n, seed=seed, response=response)
        if built is None and not all(p.fictional for p in personas):
            # Population-built personas come only through the run's pinned panel source; a
            # roster that is not fictional is a defect. Fail here, before a call is paid for.
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={
                    "message": (
                        "Fiktivní respondenti nejsou fiktivní; respondenti z populace patří jen "
                        "běhu, který je má připnuté. Nic nebylo odesláno."
                    ),
                    "reason": "persona_source_unsupported",
                },
            )
        data_class, lineage = classify_material(
            personas,
            client_declared_fictional=True,  # the roster's actual fictional provenance, below
        )
        with context.transaction() as (session, workflow):
            run = workflow.get_run(step.run_id)
            revision_id = str(run["metadata"]["design_revision_id"])
            design = StudyDesignRepository(session, context.scope).content(revision_id)
            run_lineage = workflow.retry_root(step.run_id) if cfg.checkpoint else None
        # The run's design is Class B by the owner's rule (2026-10-19, ``material_rules``);
        # an operator's classification of its exact bytes can only raise it, and the roster's
        # or the panel's class can only raise it too.
        decision = classify_by_rule(design, MaterialRule.DESIGN, cfg.material_approvals)
        classified = most_restrictive_material([data_class, decision.data_class])
        assert classified is not None  # both are classes: the personas' and the design's
        data_class = classified
        try:
            plans = (
                list(built.plans)
                if built is not None
                else [plan_respondent(spec, p) for p in personas]
            )
        except UnsupportedFact as exc:
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={
                    "message": f"Otázka se ptá na fakt, který respondent nemá: {exc}",
                    "reason": "respondent_fact_unsupported",
                },
            )
        answered = self.answer_plans(
            plans,
            spec,
            context,
            seed=seed,
            response=response,
            data_class=data_class,
            lineage=lineage,
            journal=_RunJournal(context, run_lineage) if run_lineage is not None else None,
        )
        if isinstance(answered, Failed):
            return answered
        rows, calls, resolution = answered.rows, answered.calls, answered.resolution

        dataset = assemble_dataset(spec, rows, seed=seed)
        provenance = {
            "agent": {"id": AGENT_ID, "version": AGENT_VERSION},
            "prompt": {
                "id": PROMPT_ID,
                "version": PROMPT_VERSION,
                "sha256": PROMPT_SHA256,
                # Only when on: a run made with the switch off records what it always did.
                **(
                    {"scale_labels": SCALE_LABEL_WORDING} if answered.scale_labels_in_prompt else {}
                ),
            },
            "contract_version": CONTRACT_VERSION,
            "generator": GENERATOR,
            "behavior_version": BEHAVIOR_VERSION,
            "response_process": {
                "name": response.methodology_version,
                "sha256": fingerprint(response.model_dump(mode="json")),
                "unit": is_units_process(response),
            },
            "fact_layer_version": FACT_LAYER_VERSION,
            "persona_source": (
                built.provenance(population)
                if built is not None and population is not None
                else {"roster": ROSTER_VERSION, "fictional": True, "seed": seed}
            ),
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
        system: dict[str, str] | None = None
        if population is not None and resolution is not None:
            system = respondent_system(
                population,
                model_binding=self.binding(resolution),
                scale_labels_in_prompt=answered.scale_labels_in_prompt,
            )
        return ProducedDataset(
            dataset=dataset,
            provenance=provenance,
            respondent_system=system,
            joint_certificate=(
                joint_certificate_record(population)
                if population is not None and system is not None
                else None
            ),
        )
