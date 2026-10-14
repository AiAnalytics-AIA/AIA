"""The confirmation run's steps (panel-grounded-respondents 7e4): sample, arms and score.

The executor half of :mod:`aia_core.domain.holdout.run`. A run is made from its Study's stored
preregistration (``application/validation.py``), and every input a step reads came from it at
start; nothing here chooses an item, a seed, an exclusion or a model.

- ``holdout_sample`` draws the n respondents once, from the population the run recorded, under
  the preregistered seed, with no audience filter: the whole population, as the preregistration
  was drawn over. It records who was drawn and the sample's identity
  (:func:`~aia_core.domain.holdout.run.sample_sha256`).
- ``holdout_arm`` asks one model arm's replicate. It draws the same sample again and refuses
  if it is not the recorded one (``holdout_sample_moved``), builds the personas, the arm's plans
  over the preregistered blocks with each block's exclusion applied
  (:func:`~aia_core.domain.holdout.arms.arm_plans`), and answers them through the fieldwork's
  own loop (:meth:`AIFieldwork.answer_plans`). The answers come from the preregistered model
  binding or nowhere (``model_binding_changed``, checked at the preflight, before a request).
  It stores each respondent's drawn code and the probabilities it was drawn from.

- ``holdout_score`` scores them (7e4b). It draws the sample once more and checks it, reads
  each sampled person's own answer to every item from the population, every arm replicate's
  stored record and the code baselines L0 and L1, and applies P1-P8 as the preregistration fixed
  them. It writes one immutable verdict artifact: the verdict document, the baselines, the
  preregistration's and the sample's hashes, and the run's ledger totals. Code computes the
  verdict; nobody chooses it (recording it is 7f).

Every step reads the population only through the run's recorded binding. Without the AI runtime
or the panel path an arm **parks**, as a panel research run's fieldwork does; without the panel
path the sample and the score park too. Nothing is answered with fictional respondents instead.

The response process is the unit's (``AIA_RESPONSE_V1``): the respondent system's
``response_process_version`` names the behaviour and fact layers, and a validation does not
choose another process for itself.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Mapping
from typing import Any, Final

from aia_core.application.validation import validation_artifacts
from aia_core.domain.ai_material import most_restrictive_material
from aia_core.domain.ai_respondent import UnsupportedFact, classify_material
from aia_core.domain.holdout.arms import Arm, ArmRefused, arm_plans
from aia_core.domain.holdout.bank import ItemBankRefused, canonical_json, read_item
from aia_core.domain.holdout.baselines import baseline_metrics, l0_predictions, l1_predictions
from aia_core.domain.holdout.preregistration import HoldoutRefused
from aia_core.domain.holdout.run import (
    ARM_ARTIFACT,
    ARM_KIND,
    SAMPLE_ARTIFACT,
    SAMPLE_KIND,
    SCORE_ARTIFACT,
    SCORE_KIND,
    SampledPerson,
    arm_node_key,
    arm_record,
    read_arm_record,
    sample_sha256,
    scoring_inputs,
)
from aia_core.domain.holdout.scoring import ArmRun, verdict
from aia_core.domain.panel_persona import PersonaRefused, panel_personas
from aia_core.domain.pipeline import fingerprint
from aia_core.domain.population.errors import PopulationError
from aia_core.domain.population.runtime import RuntimePopulation
from aia_core.domain.population.sampling import PanelSample, SamplingRefused, draw_panel_sample
from aia_core.domain.research_design import ResearchSpecification
from aia_core.domain.respondent_behavior import AIA_RESPONSE_V1
from aia_core.domain.workflow import FailureClass
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import ArtifactStore
from aia_worker.executor import Failed, StepContext, StepExecutor, StepInput, StepOutcome, Succeeded

from .ai_fieldwork import AIFieldwork, PopulationLoader

__all__ = ["ArmExecutor", "SampleExecutor", "ScoreExecutor", "validation_registry"]

_PANEL_UNAVAILABLE: Final = (
    "Validace má respondenty z populace, ale pracovník je neumí sestavit. Běh čeká; nic nebylo "
    "odesláno ani vymyšleno."
)
_AI_UNAVAILABLE: Final = (
    "AI respondenti nejsou v tomto prostředí nastaveni. Validace čeká u ramene; nic nebylo "
    "odesláno ani vymyšleno."
)


def _refused(reason: str, message: str) -> Failed:
    """What the preregistration or the data cannot support: permanent, said by name."""
    return Failed(FailureClass.SCHEMA_VIOLATION, error={"reason": reason, "message": message})


def _parked(reason: str, message: str) -> Failed:
    return Failed(FailureClass.RUNTIME_UNAVAILABLE, error={"reason": reason, "message": message})


class _ValidationStep:
    def __init__(
        self, *, store: ArtifactStore, build: BuildIdentity, population: PopulationLoader | None
    ) -> None:
        self._store = store
        self._build = build
        self._population = population

    def _draw(
        self, step: StepInput, context: StepContext, *, n: int, seed: int
    ) -> tuple[RuntimePopulation, PanelSample] | Failed:
        """The run's population and its sample under ``seed``, or why not."""
        if self._population is None:
            return _parked("panel_personas_unavailable", _PANEL_UNAVAILABLE)
        try:
            with context.transaction() as (session, workflow):
                population = self._population(session, workflow, step.run_id)
        except PopulationError as exc:
            return _parked("population_unavailable", f"Populaci se nepodařilo načíst: {exc}")
        try:
            return population, draw_panel_sample(population, None, n, seed)
        except SamplingRefused as refused:
            return _refused(refused.reason, str(refused))

    def _store_json(
        self,
        step: StepInput,
        context: StepContext,
        *,
        payload: dict[str, Any],
        artifact_type: str,
        input_fingerprint: str,
    ) -> Succeeded:
        with context.transaction() as (session, _workflow):
            artifact, created = validation_artifacts(session, context.scope, self._store).put_json(
                payload={
                    **payload,
                    "produced_by": {
                        "run_id": step.run_id,
                        "step_id": step.step_id,
                        "kind": step.kind,
                    },
                    "runtime_version": self._build.sha,
                },
                project_id=step.project_id,
                revision=step.project_revision,
                stage_type=step.stage_type,
                artifact_type=artifact_type,
                input_fingerprint=input_fingerprint,
                runtime_version=self._build.sha or "",
                produced_by_job_id=step.attempt_id,
                metadata={"run_id": step.run_id, "step_id": step.step_id},
            )
        return Succeeded(
            output={
                "artifact_id": artifact.artifact_id,
                "artifact_type": artifact_type,
                "sha256": artifact.sha256,
                "size_bytes": artifact.size_bytes,
                "reused": not created,
            }
        )


class SampleExecutor(_ValidationStep):
    """``holdout_sample``: the confirmation's respondents, drawn once and recorded."""

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        payload = step.payload
        n, seed = int(payload["n"]), int(payload["sample_seed"])
        drawn = self._draw(step, context, n=n, seed=seed)
        if isinstance(drawn, Failed):
            return drawn
        _population, sample = drawn
        identity = sample_sha256(sample)
        stored = self._store_json(
            step,
            context,
            payload={
                "kind": SAMPLE_ARTIFACT,
                "preregistration_sha256": payload["preregistration_sha256"],
                "sample_sha256": identity,
                "provenance": sample.provenance(),
                "respondents": [
                    {
                        "row": r.row,
                        "donor": r.donor,
                        "base_weight": r.base_weight,
                        "analysis_weight": r.analysis_weight,
                    }
                    for r in sample.respondents
                ],
            },
            artifact_type=SAMPLE_ARTIFACT,
            # The draw is a function of the population, n and the seed: a retry finds it.
            input_fingerprint=fingerprint(
                {"preregistration": payload["preregistration_sha256"], "sample": identity}
            ),
        )
        context.progress("vzorek validace vylosován", respondents=len(sample.respondents))
        return Succeeded(
            output={
                **stored.output,
                "sample_sha256": identity,
                "n": n,
                "sample_seed": seed,
                "respondents": len(sample.respondents),
            }
        )


class ArmExecutor(_ValidationStep):
    """``holdout_arm``: one model arm's replicate, answered through fieldwork's own loop."""

    def __init__(
        self, *, store: ArtifactStore, build: BuildIdentity, ai: AIFieldwork | None
    ) -> None:
        super().__init__(store=store, build=build, population=ai.population if ai else None)
        self._ai = ai

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        if self._ai is None:
            return _parked("ai_runtime_unavailable", _AI_UNAVAILABLE)
        payload = step.payload
        with context.transaction() as (_session, workflow):
            sample_step = workflow.step_output(step.run_id, "sample") or {}
        if not sample_step.get("sample_sha256"):
            return Failed(
                FailureClass.MISSING_CONFIGURATION,
                error={"message": "the run's 'sample' step recorded no sample"},
            )
        drawn = self._draw(
            step, context, n=int(sample_step["n"]), seed=int(sample_step["sample_seed"])
        )
        if isinstance(drawn, Failed):
            return drawn
        population, sample = drawn
        if sample_sha256(sample) != sample_step["sample_sha256"]:
            return _refused(
                "holdout_sample_moved",
                "the sample drawn again is not the one the sample step recorded",
            )
        spec = ResearchSpecification.model_validate(payload["specification"])
        exclusions: Mapping[str, frozenset[str]] = {
            item: frozenset(fields) for item, fields in payload["exclusions"].items()
        }
        try:
            personas = panel_personas(population, sample, response=AIA_RESPONSE_V1)
            plans = arm_plans(
                personas,
                spec,
                Arm(payload["arm"]),
                exclusions=exclusions,
                shuffle_seed=payload.get("shuffle_seed"),
                blocks=payload["blocks"],
            )
        except (PersonaRefused, ArmRefused) as refused:
            return _refused(refused.reason, str(refused))
        except UnsupportedFact as exc:
            return _refused("respondent_fact_unsupported", str(exc))

        persona_class, lineage = classify_material(
            [p.persona for p in plans], client_declared_fictional=False
        )
        decision = self._ai.material(spec.model_dump(mode="json"))
        data_class = most_restrictive_material([persona_class, decision.data_class])
        if data_class is None:
            return _parked(
                "egress_unclassified_material",
                "Dotazník validace nemá klasifikaci vstupních dat. Nic nebylo odesláno.",
            )
        answered = self._ai.answer_plans(
            plans,
            spec,
            context,
            seed=int(payload["seed"]),
            response=AIA_RESPONSE_V1,
            data_class=data_class,
            lineage=lineage,
            require_binding=str(payload["model_binding"]),
        )
        if isinstance(answered, Failed):
            return answered
        try:
            record = arm_record(
                spec,
                payload["codes"],
                [(persona.persona_id, answers) for persona, answers in answered.rows],
                answered.details,
            )
        except HoldoutRefused as refused:
            return _refused(refused.reason, str(refused))
        total = sum(c["cost_usd"] for c in answered.calls)
        context.checkpoint()
        stored = self._store_json(
            step,
            context,
            payload={
                "kind": ARM_ARTIFACT,
                "preregistration_sha256": payload["preregistration_sha256"],
                "sample_sha256": sample_step["sample_sha256"],
                "arm": payload["arm"],
                "replicate": payload["replicate"],
                "seed": payload["seed"],
                "model_binding": payload["model_binding"],
                "data_class": data_class.value,
                "lineage": sorted(lineage.datasets),
                **record,
                "calls": answered.calls,
                "total_cost_usd": total,
            },
            artifact_type=ARM_ARTIFACT,
            # A model's answers are not a function of the inputs: each attempt is its own.
            input_fingerprint=fingerprint({"step": step.step_id, "attempt": step.attempt_id}),
        )
        return Succeeded(
            output={
                **stored.output,
                "arm": payload["arm"],
                "replicate": payload["replicate"],
                "respondents": len(answered.rows),
                "requests": len(answered.calls),
                "total_cost_usd": total,
            }
        )


class ScoreExecutor(_ValidationStep):
    """``holdout_score``: the truths, the arms and the baselines -> the verdict artifact."""

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        payload = step.payload
        document = payload["preregistration"]
        sha = str(payload["preregistration_sha256"])
        if hashlib.sha256(canonical_json(document)).hexdigest() != sha:
            return _refused(
                "holdout_preregistration_altered",
                "the score step's preregistration is not the one the run was started from",
            )
        try:
            items = [read_item(raw) for raw in payload["items"]]
        except ItemBankRefused as refused:
            return _refused(refused.reason, str(refused))
        with context.transaction() as (_session, workflow):
            sample_step = workflow.step_output(step.run_id, "sample") or {}
            arm_steps = {
                (str(arm), k): workflow.step_output(step.run_id, arm_node_key(str(arm), k)) or {}
                for arm in document["model_arms"]
                for k in range(1, len(document["replicate_seeds"]) + 1)
            }
        if not sample_step.get("sample_sha256"):
            return Failed(
                FailureClass.MISSING_CONFIGURATION,
                error={"message": "the run's 'sample' step recorded no sample"},
            )
        missing = sorted(arm_node_key(a, k) for (a, k), out in arm_steps.items() if not out)
        if missing:
            return Failed(
                FailureClass.MISSING_CONFIGURATION,
                error={"message": f"arm steps recorded nothing: {', '.join(missing)}"},
            )
        drawn = self._draw(
            step, context, n=int(sample_step["n"]), seed=int(sample_step["sample_seed"])
        )
        if isinstance(drawn, Failed):
            return drawn
        population, sample = drawn
        if sample_sha256(sample) != sample_step["sample_sha256"]:
            return _refused(
                "holdout_sample_moved",
                "the sample drawn again is not the one the sample step recorded",
            )
        try:
            personas = panel_personas(population, sample, response=AIA_RESPONSE_V1)
        except PersonaRefused as refused:
            return _refused(refused.reason, str(refused))
        sampled = [
            SampledPerson(
                respondent_id=persona.persona_id,
                row=respondent.row,
                donor_id=persona.donor_id,
                weight=persona.weight,
            )
            for persona, respondent in zip(personas.personas, sample.respondents, strict=True)
        ]
        try:
            truths, respondents, rows = scoring_inputs(population, items, sampled)
        except HoldoutRefused as refused:
            return _refused(refused.reason, str(refused))

        runs: dict[str, list[ArmRun]] = {}
        requests = 0
        cost = 0.0
        with context.transaction() as (session, _workflow):
            artifacts = validation_artifacts(session, context.scope, self._store)
            for (arm, k), out in arm_steps.items():
                record = artifacts.read_json(str(out["artifact_id"]))
                if record.get("sample_sha256") != sample_step["sample_sha256"]:
                    return _refused(
                        "holdout_sample_moved", f"{arm_node_key(arm, k)} asked another sample"
                    )
                runs.setdefault(arm, []).append(read_arm_record(arm, k, record))
                requests += len(record.get("calls", ()))
                cost += float(record.get("total_cost_usd", 0.0))
        context.checkpoint()
        bootstrap = document["bootstrap"]
        try:
            computed = verdict(
                truths,
                respondents,
                runs,
                bootstrap_seed=int(bootstrap["seed"]),
                bootstrap_resamples=int(bootstrap["resamples"]),
            )
        except ValueError as exc:
            return _refused("holdout_verdict_refused", str(exc))
        baselines = {
            name: [
                dataclasses.asdict(m)
                for m in baseline_metrics(truths, respondents, predict(population, items, rows))
            ]
            for name, predict in (("L0", l0_predictions), ("L1", l1_predictions))
        }
        stored = self._store_json(
            step,
            context,
            payload={
                "kind": SCORE_ARTIFACT,
                "preregistration_sha256": sha,
                "sample_sha256": sample_step["sample_sha256"],
                "respondent_system_fingerprint": document["respondent_system"]["fingerprint"],
                "verdict": computed.document(),
                "baselines": baselines,
                "scored": {t.item: len(t.answers) for t in truths},
                "ledger": {"requests": requests, "total_cost_usd": cost},
            },
            artifact_type=SCORE_ARTIFACT,
            # The verdict is a function of the stored records: a retry finds it.
            input_fingerprint=fingerprint(
                {
                    "preregistration": sha,
                    "arms": sorted(str(out["artifact_id"]) for out in arm_steps.values()),
                }
            ),
        )
        context.progress("validace vyhodnocena", verdict="PASS" if computed.passed else "FAIL")
        return Succeeded(
            output={
                **stored.output,
                "verdict": "PASS" if computed.passed else "FAIL",
                "requests": requests,
                "total_cost_usd": cost,
            }
        )


def validation_registry(
    *, store: ArtifactStore, build: BuildIdentity, ai: AIFieldwork | None
) -> dict[str, StepExecutor]:
    """The confirmation run's step kinds -> executors, over the composition's fieldwork."""
    population = ai.population if ai is not None else None
    return {
        SAMPLE_KIND: SampleExecutor(store=store, build=build, population=population),
        ARM_KIND: ArmExecutor(store=store, build=build, ai=ai),
        SCORE_KIND: ScoreExecutor(store=store, build=build, population=population),
    }
