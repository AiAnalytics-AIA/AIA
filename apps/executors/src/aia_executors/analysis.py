"""One analysis module of a native research run: drafted by a model, decided by the gate.

The step (kind ``research_analysis``, :mod:`aia_core.domain.analysis.steps`) runs one of
the eight modules over the run's own specification, dataset and aggregate. Everything
that decides anything lives in ``aia_core``: the inputs and their preflight
(``application.analysis_results.prepare_module``), the runner and its repair bound
(``application.analysis.run_analysis_module``), each turn's request
(``domain.analysis.harness``) and the stored form (``domain.analysis.artifact``). This
executor moves data between them and the worker, and keeps four promises:

* **Nothing is sent that code can refuse.** A module the preflight blocks --
  client-facing on simulated respondents, no citable evidence, a research-questions
  module with no question -- is stored ``BLOCKED`` with zero calls, configured or not.
  A module whose material the gateway would refuse (a Class A design, an undeclared
  lineage, a route approved for nothing) parks before anything is reserved.
* **A retry never pays twice for an answer it has.** Each turn's answer is stored as a
  ``research_analysis_turn`` checkpoint the moment the call returns, keyed by the
  module's reuse key, the turn and exactly what was sent. A later attempt replays the
  turns it finds and sends only the ones it lacks; a checkpoint whose bytes no longer
  match its hash is never replayed, and that turn is asked again. The window left is
  between a call's settlement and that write: a crash there costs that one call again,
  and the ledger shows both.
* **Every outcome is stored, blocked ones too.** ``COMPLETED`` and ``BLOCKED`` both
  succeed the step, with the outcome artifact as its output, so a blocked module
  strands no other and is read back with its reasons. A provider failure is not an
  outcome: it goes back to the worker as the gateway classified it (a quota or a
  refused route parks, an uncertain call waits for a person, a budget short parks),
  and nothing is stored for it.
* **Reuse only on the complete reuse key.** An outcome is reused when its key -- the
  module fingerprint, the run's sources by content and the harness -- is the same;
  the model that drafted it is provenance, not validity (``module_input_fingerprint``).

What it never does: build a field policy or a certificate (``make layer_check``),
construct a claim, call a provider except through :class:`StepModelCaller`, repair a
schema failure inside a turn, or run a model without an explicit configuration.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from aia_core.application.analysis import (
    GenerationTurn,
    ModuleOutcomeKind,
    run_analysis_module,
)
from aia_core.application.analysis_results import (
    PreparedModule,
    SourcesRefused,
    dataset_material,
    module_artifact,
    native_sources,
    prepare_module,
)
from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.application.research import research_artifacts
from aia_core.domain.ai_contracts import ModelCallFailed, ModelRequest, canonical_json
from aia_core.domain.ai_material import (
    MaterialApproval,
    classify_material,
    most_restrictive_material,
)
from aia_core.domain.ai_models import ResolutionError, parse_model_config
from aia_core.domain.analysis import AnalysisModuleId
from aia_core.domain.analysis.artifact import (
    ANALYSIS_MODULE_ARTIFACT,
    ANALYSIS_TURN_ARTIFACT,
    TURN_ARTIFACT_CONTRACT,
    CallRecord,
    ProducedBy,
    TurnArtifact,
    parse_module_artifact,
    parse_turn_artifact,
    turn_fingerprint,
)
from aia_core.domain.analysis.harness import (
    ANALYSIS_CAPABILITY,
    InvalidStructuredOutput,
    analysis_request,
    classify_analysis_material,
    harness_frame,
    request_sha256,
)
from aia_core.domain.analysis.native import NativeEvidenceRefused
from aia_core.domain.analysis.steps import ANALYSIS_STEP_KIND, module_of_node
from aia_core.domain.evidence import ClaimSurface, InstrumentPolicyRefused, Violation
from aia_core.domain.licence import DataLineage
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass
from aia_core.domain.workflow import FailureClass
from aia_core.infrastructure.artifact_repository import Artifact, ArtifactRepository
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import ArtifactStore, IntegrityError, ObjectNotFound
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_worker.executor import (
    Failed,
    StepContext,
    StepExecutor,
    StepFailed,
    StepInput,
    StepOutcome,
    Succeeded,
)

from .ai_runtime import AIRuntimeConfigError, AIRuntimeSettings
from .ai_step import StepModelCaller

__all__ = [
    "ANALYSIS_LANGUAGE",
    "ANALYSIS_UNCONFIGURED",
    "CONTEXT_WINDOW_EXCEEDED",
    "SCHEMA_FAILURE",
    "AnalysisConfig",
    "AnalysisModuleExecutor",
    "analysis_registry",
]

#: The language the modules are written in: the reports' (``domain/report/copy.py``).
ANALYSIS_LANGUAGE: Final = "cs"

#: The gateway's reason for an answer that failed the output contract. The runner's
#: repair loop handles it; any other failure goes back to the worker unchanged.
SCHEMA_FAILURE: Final = "structured_output_invalid"
ANALYSIS_UNCONFIGURED: Final = "analysis_unconfigured"
CONTEXT_WINDOW_EXCEEDED: Final = "context_window_exceeded"

#: Room for a repair turn beyond the first: the previous answer (bounded by the
#: output cap, at most four bytes a token), the repair text and framing.
_REPAIR_HEADROOM_OUTPUTS: Final = 4
_REPAIR_TEXT_BYTES: Final = 8192
_FRAMING_TOKENS: Final = 2048

_UNCONFIGURED_MESSAGE: Final = (
    "AI analýza není zapnutá. Výsledky běhu zůstávají uložené; modul čeká, dokud ji "
    "provozovatel nezapne. Nic nebylo odesláno."
)
_PARK_MESSAGE: Final = (
    "AI analýza pro tento výzkum není povolena: {why}. Nic nebylo odesláno ani "
    "vymyšleno; modul čeká na schválení trasy, licence nebo klienta."
)


@dataclass(frozen=True, slots=True)
class AnalysisConfig:
    """What the composition decided; nothing here comes from a request or the browser.

    Build it with :meth:`from_settings`, which checks it against the model's ceilings.
    """

    policy_version: str
    max_output_tokens: int
    context_window_tokens: int
    #: Budget held per turn: one call, since the harness allows no schema repair.
    reservation_usd: float
    #: Legacy configuration retained for compatibility; it grants no classification.
    fictional_client_ids: frozenset[str]
    material_approvals: tuple[MaterialApproval, ...] = ()

    def __post_init__(self) -> None:
        if not self.policy_version:
            raise ValueError("an analysis configuration names its model policy")
        if self.max_output_tokens <= 0 or self.context_window_tokens <= 0:
            raise ValueError("output cap and context window must be positive")
        if not self.reservation_usd > 0:
            raise ValueError("a metered turn needs a positive reservation")

    @classmethod
    def from_settings(
        cls, settings: AIRuntimeSettings, *, max_output_tokens: int, reservation_usd: float
    ) -> AnalysisConfig:
        """The configuration for ``settings``' model, or :class:`AIRuntimeConfigError`.

        Refuses an output cap above the model's, a reservation that cannot cover one
        call at the model's ceilings (the whole context window at the dearest input
        price, plus the output cap), and a policy that does not bind the capability
        the harness asks for: each would fail at run time, after the run had started.
        """
        if max_output_tokens <= 0:
            raise AIRuntimeConfigError("the analysis output limit must be positive")
        if max_output_tokens > settings.max_output_tokens:
            raise AIRuntimeConfigError("the analysis output limit exceeds the model limit")
        prices = (
            settings.input_usd_per_mtok,
            settings.cache_write_usd_per_mtok or 0.0,
            settings.cache_read_usd_per_mtok or 0.0,
        )
        ceiling = (
            settings.context_window_tokens * max(prices)
            + max_output_tokens * settings.output_usd_per_mtok
        ) / 1_000_000
        if not reservation_usd >= ceiling:
            raise AIRuntimeConfigError(
                f"the analysis reservation must cover one call at the model ceilings "
                f"(${ceiling:.4f})"
            )
        try:
            parse_model_config(settings.model_document()).resolve(
                capability=ANALYSIS_CAPABILITY, policy_version=settings.policy_version
            )
        except ResolutionError as exc:
            raise AIRuntimeConfigError(
                f"analysis runs on {ANALYSIS_CAPABILITY.value}, which this model policy "
                f"does not bind: {exc}"
            ) from exc
        return cls(
            policy_version=settings.policy_version,
            max_output_tokens=max_output_tokens,
            context_window_tokens=settings.context_window_tokens,
            reservation_usd=reservation_usd,
            fictional_client_ids=settings.fictional_client_ids,
            material_approvals=settings.material_approvals,
        )


def _request_bytes(request: ModelRequest) -> int:
    """An upper bound on a request's input tokens: its UTF-8 bytes, contract included."""
    parts = [request.system, *(m.content for m in request.messages)]
    parts.append(canonical_json(request.agent.schema or {}))
    return sum(len(p.encode("utf-8")) for p in parts)


def _target(step: StepInput) -> tuple[AnalysisModuleId, ClaimSurface] | Failed:
    module = module_of_node(step.node_key)
    named = step.payload.get("analysis_module")
    if module is None or named != module.value:
        return Failed(
            FailureClass.MISSING_CONFIGURATION,
            error={
                "reason": "analysis_step_unnamed",
                "message": f"step {step.node_key!r} does not name its module ({named!r})",
            },
        )
    try:
        surface = ClaimSurface(str(step.payload.get("analysis_surface")))
    except ValueError:
        # No default: a surface is what decides who may read the outcome.
        return Failed(
            FailureClass.MISSING_CONFIGURATION,
            error={
                "reason": "analysis_step_unnamed",
                "message": f"step {step.node_key!r} does not say which surface it writes for",
            },
        )
    return module, surface


def _sources_refused(refused: SourcesRefused) -> Failed:
    """A source refusal as the step's failure. Returned from inside the transaction, never
    raised through it: the worker's rolls back on an exception, and with it the CORRUPT
    mark a read made (OI-77)."""
    failure = (
        FailureClass.MISSING_CONFIGURATION
        if refused.reason == "missing_upstream"
        else FailureClass.SCHEMA_VIOLATION
    )
    return Failed(failure, error={"reason": refused.reason, "message": str(refused)})


class _Turns:
    """The runner's generator for one attempt: each turn replayed, or asked once."""

    def __init__(
        self,
        *,
        executor: AnalysisModuleExecutor,
        step: StepInput,
        context: StepContext,
        prepared: PreparedModule,
        caller: StepModelCaller,
        config: AnalysisConfig,
        data_class: DataClass,
        lineage: DataLineage | None,
    ) -> None:
        self._executor, self._step, self._context = executor, step, context
        self._prepared, self._caller, self._config = prepared, caller, config
        self._data_class, self._lineage = data_class, lineage
        self._frame = harness_frame(
            origin=prepared.evidence.origin, surface=prepared.inputs.surface
        )
        self.calls: list[CallRecord] = []
        self.turn_ids: list[str] = []
        self.last: object | None = None
        self._cleared = False

    def request(self, turn: GenerationTurn) -> ModelRequest:
        return analysis_request(
            system=turn.system,
            payload=turn.payload,
            frame=self._frame,
            repair=turn.repair,
            previous=turn.previous,
            policy_version=self._config.policy_version,
            data_class=self._data_class,
            lineage=self._lineage,
            max_output_tokens=self._config.max_output_tokens,
        )

    def generate(self, turn: GenerationTurn) -> object:
        # Between turns: a cancelled, stopping or lease-less attempt stops here, and
        # every turn it answered is already a checkpoint.
        self._context.checkpoint()
        request = self.request(turn)
        sent = request_sha256(request)
        key = turn_fingerprint(
            reuse_fingerprint=self._prepared.reuse_fingerprint,
            turn=turn.attempt,
            request_sha256=sent,
        )
        replayed = self._executor.stored_turn(self._step, self._context, key)
        if replayed is not None:
            answer, artifact_id = replayed
            if (answer.module_id, answer.turn, answer.reuse_fingerprint, answer.request_sha256) != (
                turn.module_id,
                turn.attempt,
                self._prepared.reuse_fingerprint,
                sent,
            ):
                raise StepFailed(
                    FailureClass.SCHEMA_VIOLATION,
                    "a stored turn does not answer the request it is filed under",
                    error={"reason": "turn_checkpoint_mismatch", "artifact_id": artifact_id},
                )
            self._keep(turn.attempt, sent, answer, artifact_id, replayed=True)
            return self._answer(answer)
        self._fits(request, turn)
        if not self._cleared:
            self._clear(request)
        self._context.progress("AI analyzuje modul", module=turn.module_id.value, turn=turn.attempt)
        answer = self._ask(turn, request, sent)
        artifact_id = self._executor.store_turn(self._step, self._context, key, answer)
        self._keep(turn.attempt, sent, answer, artifact_id, replayed=False)
        return self._answer(answer)

    def _fits(self, request: ModelRequest, turn: GenerationTurn) -> None:
        """Refuse a turn the model window cannot hold, before anything is reserved.

        The first turn must also leave room for a repair turn after it (the previous
        answer and the repair text), so a module is not started that cannot finish.
        """
        cfg = self._config
        need = _request_bytes(request) + cfg.max_output_tokens + _FRAMING_TOKENS
        if turn.attempt == 1:
            need += _REPAIR_HEADROOM_OUTPUTS * cfg.max_output_tokens + _REPAIR_TEXT_BYTES
        if need > cfg.context_window_tokens:
            raise StepFailed(
                FailureClass.SCHEMA_VIOLATION,
                "the module's turn exceeds the configured model window",
                error={
                    "reason": CONTEXT_WINDOW_EXCEEDED,
                    "turn": turn.attempt,
                    "needed_tokens": need,
                    "context_window_tokens": cfg.context_window_tokens,
                },
            )

    def _clear(self, request: ModelRequest) -> None:
        """Ask the gateway whether this material may leave at all. Spends nothing.

        A refusal -- a Class A design on a Class C route, an undeclared lineage, an
        unbound capability -- parks the step: it is policy, not a defect, and no timer
        clears it.
        """
        try:
            self._caller.preflight(request)
        except ModelCallFailed as refused:
            lineage = sorted(self._lineage.datasets) if self._lineage is not None else None
            raise StepFailed(
                FailureClass.RUNTIME_UNAVAILABLE,
                _PARK_MESSAGE.format(why=str(refused)),
                error={
                    "reason": refused.reason,
                    "message": _PARK_MESSAGE.format(why=str(refused)),
                    "data_class": self._data_class.value,
                    "lineage": lineage,
                },
            ) from refused
        self._cleared = True

    def _ask(self, turn: GenerationTurn, request: ModelRequest, sent: str) -> TurnArtifact:
        """One call. A schema failure is an answer; every other failure is the worker's."""
        base: dict[str, Any] = {
            "kind": ANALYSIS_TURN_ARTIFACT,
            "contract_version": TURN_ARTIFACT_CONTRACT,
            "module_id": turn.module_id,
            "turn": turn.attempt,
            "reuse_fingerprint": self._prepared.reuse_fingerprint,
            "request_sha256": sent,
            "produced_by": self._executor.produced_by(self._step),
            "runtime_version": self._executor.runtime_version,
        }
        try:
            result = self._caller.invoke(request)
        except StepFailed as failed:
            cause = failed.__cause__
            if (
                failed.failure is not FailureClass.SCHEMA_VIOLATION
                or failed.error.get("reason") != SCHEMA_FAILURE
                or not isinstance(cause, ModelCallFailed)
            ):
                raise
            terminal = [e for e in cause.usage_events if e.outcome.is_terminal]
            last = terminal[-1] if terminal else None
            return TurnArtifact(
                **base,
                answer="SCHEMA_INVALID",
                draft=None,
                schema_violations=tuple(str(v) for v in cause.violations)
                or ("the answer did not match the output contract",),
                call_id=last.call_id if last else None,
                provider_request_id=cause.provider_request_id,
                model=last.model if last else None,
                route_id=last.route_id if last else None,
                policy_version=last.policy_version if last else None,
                cost_usd=sum(e.cost_usd for e in terminal),
                cost_basis=last.cost_basis.value if last else None,
            )
        assert result.output is not None  # a structured agent's result has one
        return TurnArtifact(
            **base,
            answer="DRAFT",
            draft=result.output.model_dump(mode="json"),
            schema_violations=(),
            call_id=result.call_id,
            provider_request_id=result.provider_request_id,
            model=result.resolved_model,
            route_id=result.provenance.route_id,
            policy_version=result.provenance.policy_version,
            cost_usd=result.total_cost_usd,
            cost_basis=result.cost_basis.value,
        )

    def _keep(
        self, turn: int, sent: str, answer: TurnArtifact, artifact_id: str, *, replayed: bool
    ) -> None:
        self.calls.append(
            CallRecord(
                turn=turn,
                request_sha256=sent,
                answer=answer.answer,
                turn_artifact_id=artifact_id,
                replayed=replayed,
                call_id=answer.call_id,
                provider_request_id=answer.provider_request_id,
                model=answer.model,
                route_id=answer.route_id,
                policy_version=answer.policy_version,
                cost_usd=answer.cost_usd,
                cost_basis=answer.cost_basis,
            )
        )
        self.turn_ids.append(artifact_id)

    def _answer(self, answer: TurnArtifact) -> object:
        if answer.draft is None:
            self.last = InvalidStructuredOutput(answer.schema_violations)
        else:
            self.last = answer.draft.model_dump(mode="json")
        return self.last


class AnalysisModuleExecutor:
    """``research_analysis``: one module, to a stored ``COMPLETED`` or ``BLOCKED``."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        build: BuildIdentity,
        language: str = ANALYSIS_LANGUAGE,
        gateway: GovernedModelGateway | None = None,
        config: AnalysisConfig | None = None,
    ) -> None:
        if (gateway is None) != (config is None):
            raise ValueError("a model gateway and its analysis configuration come together")
        self._store, self._build, self._language = store, build, language
        self._gateway, self._config = gateway, config

    @property
    def runtime_version(self) -> str | None:
        return self._build.sha

    def produced_by(self, step: StepInput) -> ProducedBy:
        return ProducedBy(
            run_id=step.run_id, step_id=step.step_id, attempt_id=step.attempt_id, kind=step.kind
        )

    # -- the step --------------------------------------------------------------------

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        target = _target(step)
        if isinstance(target, Failed):
            return target
        module, surface = target
        with context.transaction() as (session, workflow):
            try:
                sources = native_sources(
                    session, context.scope, self._store, workflow.get_run(step.run_id)
                )
                prepared = prepare_module(
                    sources, module_id=module, surface=surface, language=self._language
                )
            except SourcesRefused as refused:
                return _sources_refused(refused)
            except (NativeEvidenceRefused, InstrumentPolicyRefused) as refused:
                return Failed(
                    FailureClass.SCHEMA_VIOLATION,
                    error={"reason": "evidence_refused", "message": str(refused)},
                )
            repo = research_artifacts(session, context.scope, self._store)
            reused = self._reusable(repo, step, prepared)
            if reused is not None:
                return reused
            if prepared.preflight:
                # Code refused the module before any model could be asked: stored, not
                # parked, whatever the configuration, and nothing reserved.
                return self._stored(
                    repo,
                    step,
                    prepared,
                    outcome=ModuleOutcomeKind.BLOCKED,
                    draft=None,
                    violations=prepared.preflight,
                    turns=None,
                )
            if self._gateway is None or self._config is None:
                return Failed(
                    FailureClass.RUNTIME_UNAVAILABLE,
                    error={"reason": ANALYSIS_UNCONFIGURED, "message": _UNCONFIGURED_MESSAGE},
                )
            try:
                material = dataset_material(session, context.scope, self._store, sources)
            except SourcesRefused as refused:
                return _sources_refused(refused)
            design = StudyDesignRepository(session, context.scope).content(
                sources.refs.design_revision_id
            )
        cfg, gateway = self._config, self._gateway
        dataset_class = classify_analysis_material(
            client_declared_fictional=True,  # classify the design separately from its data
            origin=prepared.evidence.origin,
            respondents_fictional=material.respondents_fictional,
        )
        data_class = most_restrictive_material(
            [dataset_class, classify_material(design, cfg.material_approvals).data_class]
        )
        if data_class is None:
            return Failed(
                FailureClass.RUNTIME_UNAVAILABLE,
                error={
                    "reason": "egress_unclassified_material",
                    "message": "Zadání nemá klasifikaci vstupních dat. Nic nebylo odesláno.",
                },
            )
        caller = StepModelCaller(
            gateway=gateway,
            context=context,
            runtime_version=self._build.sha or "",
            provider=Provider.AWS_BEDROCK,
            reservation_usd=cfg.reservation_usd,
        )
        turns = _Turns(
            executor=self,
            step=step,
            context=context,
            prepared=prepared,
            caller=caller,
            config=cfg,
            data_class=data_class,
            lineage=material.lineage,
        )
        outcome = run_analysis_module(
            module, prepared.inputs, turns, max_repairs=prepared.harness.max_repairs
        )
        if outcome.input_fingerprint != prepared.module_fingerprint:  # pragma: no cover
            raise AssertionError("the runner judged the module on other inputs")
        completed = outcome.kind is ModuleOutcomeKind.COMPLETED
        if completed and not isinstance(turns.last, Mapping):  # pragma: no cover
            raise AssertionError("a completed module's last answer is its accepted draft")
        context.checkpoint()
        with context.transaction() as (session, _workflow):
            return self._stored(
                research_artifacts(session, context.scope, self._store),
                step,
                prepared,
                outcome=outcome.kind,
                draft=turns.last if completed and isinstance(turns.last, Mapping) else None,
                violations=outcome.violations,
                turns=turns,
            )

    # -- storage ---------------------------------------------------------------------

    def _put(
        self,
        repo: ArtifactRepository,
        step: StepInput,
        prepared: PreparedModule,
        *,
        payload: dict[str, Any],
        artifact_type: str,
        input_fingerprint: str,
        depends_on: list[str],
        metadata: dict[str, Any],
    ) -> tuple[Artifact, bool]:
        refs = prepared.sources.refs
        return repo.put_json(
            payload=payload,
            project_id=step.project_id,
            revision=step.project_revision,
            stage_type=step.stage_type,
            artifact_type=artifact_type,
            input_fingerprint=input_fingerprint,
            runtime_version=self._build.sha or "",
            produced_by_job_id=step.attempt_id,
            metadata={
                "run_id": step.run_id,
                "step_id": step.step_id,
                "analysis_module": prepared.module_id.value,
                **metadata,
            },
            depends_on=[
                refs.specification.artifact_id,
                refs.dataset.artifact_id,
                refs.aggregate.artifact_id,
                *depends_on,
            ],
        )

    def stored_turn(
        self, step: StepInput, context: StepContext, key: str
    ) -> tuple[TurnArtifact, str] | None:
        """The turn answer stored under ``key``, if a readable one exists."""
        with context.transaction() as (session, _workflow):
            repo = research_artifacts(session, context.scope, self._store)
            found = repo.find_reusable(
                project_id=step.project_id,
                stage_type=step.stage_type,
                artifact_type=ANALYSIS_TURN_ARTIFACT,
                input_fingerprint=key,
            )
            if found is None:
                return None
            try:
                stored = repo.read_json(found.artifact_id)
            except (IntegrityError, ObjectNotFound):
                # Marked CORRUPT by the read; the turn is asked again and both calls
                # are on the ledger.
                return None
        try:
            return parse_turn_artifact(stored), found.artifact_id
        except ValueError as exc:
            raise StepFailed(
                FailureClass.SCHEMA_VIOLATION,
                "a stored turn breaks its contract",
                error={"reason": "turn_checkpoint_contract", "artifact_id": found.artifact_id},
            ) from exc

    def store_turn(
        self, step: StepInput, context: StepContext, key: str, answer: TurnArtifact
    ) -> str:
        """Store one turn's answer the moment it is known. Fenced by the lease."""
        with context.transaction() as (session, _workflow):
            repo = research_artifacts(session, context.scope, self._store)
            artifact, _ = repo.put_json(
                payload=answer.model_dump(mode="json"),
                project_id=step.project_id,
                revision=step.project_revision,
                stage_type=step.stage_type,
                artifact_type=ANALYSIS_TURN_ARTIFACT,
                input_fingerprint=key,
                runtime_version=self._build.sha or "",
                produced_by_job_id=step.attempt_id,
                metadata={
                    "run_id": step.run_id,
                    "step_id": step.step_id,
                    "analysis_module": answer.module_id.value,
                    "turn": answer.turn,
                    "answer": answer.answer,
                },
            )
        return artifact.artifact_id

    def _reusable(
        self, repo: ArtifactRepository, step: StepInput, prepared: PreparedModule
    ) -> Succeeded | Failed | None:
        found = repo.find_reusable(
            project_id=step.project_id,
            stage_type=step.stage_type,
            artifact_type=ANALYSIS_MODULE_ARTIFACT,
            input_fingerprint=prepared.reuse_fingerprint,
        )
        if found is None:
            return None
        try:
            record = parse_module_artifact(repo.read_json(found.artifact_id))
        except (IntegrityError, ObjectNotFound):
            return None  # marked CORRUPT by the read: computed again, turns replayed
        except ValueError as exc:
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={"reason": "outcome_contract", "message": str(exc)},
            )
        if (
            record.module_id is not prepared.module_id
            or record.reuse_fingerprint != prepared.reuse_fingerprint
        ):
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={"reason": "outcome_mismatch", "message": found.artifact_id},
            )
        return self._succeeded(found, record.outcome, prepared, reused=True, sent=0, replayed=0)

    def _stored(
        self,
        repo: ArtifactRepository,
        step: StepInput,
        prepared: PreparedModule,
        *,
        outcome: ModuleOutcomeKind,
        draft: Mapping[str, Any] | None,
        violations: Sequence[Violation],
        turns: _Turns | None,
    ) -> Succeeded:
        calls = tuple(turns.calls) if turns is not None else ()
        record = module_artifact(
            prepared,
            outcome=outcome,
            draft=draft,
            violations=violations,
            calls=calls,
            produced_by=self.produced_by(step),
            runtime_version=self._build.sha,
        )
        artifact, _ = self._put(
            repo,
            step,
            prepared,
            payload=record.model_dump(mode="json"),
            artifact_type=ANALYSIS_MODULE_ARTIFACT,
            input_fingerprint=prepared.reuse_fingerprint,
            depends_on=list(turns.turn_ids) if turns is not None else [],
            metadata={"outcome": record.outcome, "surface": record.surface.value},
        )
        return self._succeeded(
            artifact,
            record.outcome,
            prepared,
            reused=False,
            sent=sum(1 for c in calls if not c.replayed),
            replayed=sum(1 for c in calls if c.replayed),
            spent=sum(c.cost_usd for c in calls if not c.replayed),
        )

    @staticmethod
    def _succeeded(
        artifact: Artifact,
        outcome: str,
        prepared: PreparedModule,
        *,
        reused: bool,
        sent: int,
        replayed: int,
        spent: float = 0.0,
    ) -> Succeeded:
        return Succeeded(
            output={
                "artifact_id": artifact.artifact_id,
                "artifact_type": ANALYSIS_MODULE_ARTIFACT,
                "sha256": artifact.sha256,
                "size_bytes": artifact.size_bytes,
                "reused": reused,
                "analysis_module": prepared.module_id.value,
                "outcome": outcome,
                "surface": prepared.inputs.surface.value,
                "method_status": prepared.method_status,
                "calls_sent": sent,
                "calls_replayed": replayed,
                "cost_usd": spent,
            }
        )


def analysis_registry(
    *,
    store: ArtifactStore,
    build: BuildIdentity,
    language: str = ANALYSIS_LANGUAGE,
    gateway: GovernedModelGateway | None = None,
    config: AnalysisConfig | None = None,
) -> dict[str, StepExecutor]:
    """The analysis step kind -> its executor, for the composition that registers it.

    Without ``gateway`` and ``config`` a module the preflight blocks is still stored
    ``BLOCKED`` and every other module parks (``analysis_unconfigured``).
    """
    return {
        ANALYSIS_STEP_KIND: AnalysisModuleExecutor(
            store=store, build=build, language=language, gateway=gateway, config=config
        )
    }
