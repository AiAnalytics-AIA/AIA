"""The Research Lead's turn (ADR 0026): one model request over a frozen context.

Modelled on the design agents' executor (``research_agents``): ``StepModelCaller`` over the
governed gateway, the prompt pinned at enqueue, the context frozen and hashed at enqueue,
``ModelCapability.STUDY_LEAD`` (bound to the Lead's own model when one is configured, else
the route's; ADR 0026 amendment, 2026-10-19) and one schema repair. No tools; no automatic
retry.

What the turn produces is its step output -- the grounded :class:`LeadOutput`, what grounding
dropped, what the Lead changed in its own files and the class the turn was sent as -- so the
conversation reads it without an artifact (the product owner, 2026-10-19). The same output is
also stored as an artifact with its provenance, as a design job's is.

The part of the Lead's own ``self_update`` that stays inside the turn's client -- client
notes and forgets -- is applied here, under the turn's lease and the run's scope, in the
transaction that stores the artifact, so a turn found again after a crash never applies it
twice. A personal note or a change to SOUL, USER or the name would load into every client's
studies, so it waits in the step output (``self_update_pending``) for the researcher's yes
(``ResearchLead.decide_self_update``; Codex on #484).

Without ``AIA_AI_RESEARCH_LEAD_ENABLED`` and its two keys the turn parks
(``research_lead_unconfigured``), as analysis parks unconfigured; nothing is sent.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.application.research import research_artifacts
from aia_core.domain.ai_contracts import ModelCallFailed, canonical_json
from aia_core.domain.ai_material import MaterialApproval
from aia_core.domain.prompts import PromptPin
from aia_core.domain.providers import Provider
from aia_core.domain.research_lead import (
    ARTIFACT_TYPE,
    LEAD_HARNESS_VERSION,
    LEAD_PROMPT_ID,
    LeadOutput,
    context_sha256,
    ground_edits,
    ground_self_update,
    layer,
    lead_request,
    self_update_base,
    split_self_update,
    waiting_self_update,
)
from aia_core.domain.workflow import FailureClass
from aia_core.domain.workflow_templates import RESEARCH_LEAD_TURN
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.researcher_lead_repository import (
    LeadNotHatched,
    ResearcherLeadRepository,
)
from aia_core.infrastructure.storage import ArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome, Succeeded
from pydantic import ValidationError

from .ai_step import StepModelCaller

__all__ = [
    "ARTIFACT_TYPE",
    "KIND",
    "LEAD_UNCONFIGURED",
    "LeadAnswer",
    "ResearchLeadConfig",
    "ResearchLeadExecutor",
]

KIND: Final = RESEARCH_LEAD_TURN
#: The park reason when the deployment has not configured the Lead's turns.
LEAD_UNCONFIGURED: Final = "research_lead_unconfigured"


@dataclass(frozen=True, slots=True)
class ResearchLeadConfig:
    """``AIA_AI_RESEARCH_LEAD_*`` as validated by ``AIRuntimeSettings``."""

    policy_version: str
    max_output_tokens: int
    context_window_tokens: int
    reservation_usd: float
    material_approvals: tuple[MaterialApproval, ...] = ()
    #: Each model request writes a "sent" and an "answered" event (``AIA_AI_STEP_EVENTS``).
    step_events: bool = False


def _schema_violation(message: str) -> Failed:
    return Failed(FailureClass.SCHEMA_VIOLATION, error={"message": message})


@dataclass(frozen=True, slots=True)
class LeadAnswer:
    """What answered a turn: the output, the class the turn was sent as (``None`` when no
    model was asked) and the provenance to store beside it."""

    output: LeadOutput
    data_class: str | None
    provenance: dict[str, Any]
    #: True only for a composition that answers without a model (the local workbench).
    scripted: bool = False


class ResearchLeadExecutor:
    """Answers one Lead turn. Built without a gateway or config, it parks every turn.

    The answer comes from :meth:`_answer`; everything around it -- the frozen context's
    checks, reuse, grounding, the Lead's own ``self_update`` and the stored result -- is the
    same for any answer, so a local composition that answers without a model
    (``aia_executors.workbench``) exercises the rest of the pipeline for real.
    """

    def __init__(
        self,
        *,
        store: ArtifactStore,
        build: BuildIdentity,
        gateway: GovernedModelGateway | None = None,
        config: ResearchLeadConfig | None = None,
    ) -> None:
        self._store, self._build = store, build
        self._gateway, self._config = gateway, config

    # -- what a composition provides ----------------------------------------------------

    def _unconfigured(self) -> Failed | None:
        """The park when this composition cannot answer a turn."""
        if self._config is None or self._gateway is None:
            return Failed(
                FailureClass.RUNTIME_UNAVAILABLE,
                error={
                    "reason": LEAD_UNCONFIGURED,
                    "message": "Vedoucí výzkumu není zapnutý. Zpráva zůstává uložená.",
                },
            )
        return None

    def _identity(self) -> dict[str, Any]:
        """What else, beside the turn and its context, makes a stored answer this one's."""
        cfg = self._config
        assert cfg is not None
        return {"policy": cfg.policy_version, "output_budget": cfg.max_output_tokens}

    def _answer(
        self,
        step: StepInput,
        context: StepContext,
        frozen: Mapping[str, Any],
        pin: PromptPin,
    ) -> LeadAnswer | Failed:
        """One model request over the frozen context, and its one repair."""
        cfg, gateway = self._config, self._gateway
        assert cfg is not None and gateway is not None
        payload = step.payload
        try:
            request = lead_request(
                frozen,
                policy_version=cfg.policy_version,
                max_output_tokens=cfg.max_output_tokens,
                material_approvals=cfg.material_approvals,
            )
        except (KeyError, ValueError, TypeError) as exc:
            return _schema_violation(f"the turn's context cannot be sent: {exc}")
        # UTF-8 bytes bound tokens; a turn and its one repair must fit the model's window.
        # Fail before reserving or sending, never trim.
        request_bytes = len(
            (
                request.system + request.messages[0].content + canonical_json(request.agent.schema)
            ).encode()
        )
        if request_bytes + 5 * cfg.max_output_tokens + 2048 > cfg.context_window_tokens:
            return _schema_violation("the turn's context exceeds the configured model window")
        caller = StepModelCaller(
            gateway=gateway,
            context=context,
            runtime_version=self._build.sha or "",
            provider=Provider.AWS_BEDROCK,
            reservation_usd=cfg.reservation_usd,
            announce=cfg.step_events,
        )
        try:
            caller.preflight(request)
        except ModelCallFailed as exc:
            return Failed(
                FailureClass.RUNTIME_UNAVAILABLE,
                error={
                    "reason": exc.reason,
                    "message": f"Vedoucí výzkumu čeká na povolenou trasu nebo licenci: {exc}",
                },
            )
        context.progress("Vedoucí výzkumu odpovídá", turn=str(payload.get("turn_id")))
        result = caller.invoke(request)
        assert result.output is not None
        assert request.data_classification is not None  # an unknown class refused above
        return LeadAnswer(
            output=LeadOutput.model_validate(result.output.model_dump(mode="json")),
            data_class=request.data_classification.value,
            provenance={
                "agent_id": request.agent.agent_id,
                "agent_version": request.agent.version,
                "prompt_version": request.agent.prompt_version,
                "prompt_sha256": hashlib.sha256(request.system.encode()).hexdigest(),
                "prompt_origin": pin.origin,
                "prompt_text_sha256": pin.text_sha256,
                "schema_fingerprint": result.provenance.schema_fingerprint,
                "call_id": result.call_id,
                "provider_request_id": result.provider_request_id,
                "model": result.resolved_model,
                "route_id": result.provenance.route_id,
                "policy_version": result.provenance.policy_version,
                "cost_usd": result.total_cost_usd,
                "data_class": request.data_classification.value,
            },
        )

    # -- the turn ---------------------------------------------------------------------

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        refused = self._unconfigured()
        if refused is not None:
            return refused
        payload: Mapping[str, Any] = step.payload
        if payload.get("harness_version") != LEAD_HARNESS_VERSION:
            return _schema_violation("the Lead's harness changed; send the message again")
        frozen = payload.get("context")
        if not isinstance(frozen, Mapping) or context_sha256(frozen) != payload.get(
            "context_sha256"
        ):
            return _schema_violation("the turn's context changed after it was frozen")
        if payload.get("user_id") != context.scope.actor_id:
            # The run's scope acts for whoever started it; a turn is only that person's.
            return _schema_violation("the turn belongs to another researcher")
        try:
            pin = PromptPin(**layer(frozen, "prompt")["pin"])
            if pin.prompt_id != LEAD_PROMPT_ID:
                raise ValueError(pin.prompt_id)
        except (KeyError, ValueError, TypeError, ValidationError):
            return _schema_violation("the turn's prompt is not valid; send the message again")
        digest = hashlib.sha256(
            canonical_json(
                {
                    "turn": payload.get("turn_id"),
                    "context": payload["context_sha256"],
                    **self._identity(),
                }
            ).encode()
        ).hexdigest()
        with context.transaction() as (session, _):
            if StudyDesignRepository(session, context.scope).project_id() != step.project_id:
                return _schema_violation("the turn's design project is not the Study's")
            artifacts = research_artifacts(session, context.scope, self._store)
            existing = artifacts.find_reusable(
                project_id=step.project_id,
                stage_type=step.stage_type,
                artifact_type=ARTIFACT_TYPE,
                input_fingerprint=digest,
            )
            if existing is not None:
                stored = artifacts.read_json(existing.artifact_id)
                if isinstance(stored, dict) and isinstance(stored.get("result"), dict):
                    return Succeeded(
                        output={**stored["result"], "artifact_id": existing.artifact_id}
                    )

        answer = self._answer(step, context, frozen, pin)
        if isinstance(answer, Failed):
            return answer
        design = layer(frozen, "design")
        grounded, dropped = ground_edits(
            answer.output, design.get("content") or {}, design.get("analysis") or None
        )
        notes = list(layer(frozen, "lead").get("notes") or ())
        shown = [str(n["memory_id"]) for n in notes]
        update, dropped_forgets = ground_self_update(grounded.self_update, shown)
        grounded = grounded.model_copy(update={"self_update": update})
        # What stays inside the turn's client applies now; anything that would reach every
        # client's studies (a personal note kept or forgotten, SOUL, USER, the name) waits for
        # the researcher.
        now, pending = split_self_update(update, notes)
        pending_json = pending.model_dump(mode="json") if pending else None

        with context.transaction() as (session, _):
            applied = None
            dropped_all = [d.model_dump() for d in [*dropped, *dropped_forgets]]
            if now is not None:
                try:
                    applied = ResearcherLeadRepository(session, context.scope).apply_self_update(
                        now, source_turn_id=str(payload.get("turn_id"))
                    )
                except LeadNotHatched:
                    dropped_all.append(
                        {"index": 0, "op": "self_update", "reason": "lead_not_hatched"}
                    )
            step_output: dict[str, Any] = {
                "turn_id": payload.get("turn_id"),
                "lead_output": grounded.model_dump(mode="json"),
                "dropped": dropped_all,
                "self_update_applied": applied.model_dump(mode="json") if applied else None,
                "self_update_pending": pending_json,
                # The same, as the researcher reads it: each note to forget with its text.
                "self_update_waiting": waiting_self_update(pending_json, notes),
                # The files the turn saw: an accept refuses a file changed since.
                "self_update_base": self_update_base(layer(frozen, "lead"))
                if pending_json
                else None,
                "data_class": answer.data_class,
            }
            if answer.scripted:
                step_output["scripted"] = True
            provenance = {
                **answer.provenance,
                "harness_version": LEAD_HARNESS_VERSION,
                "context_sha256": payload["context_sha256"],
                "design_revision_id": payload.get("design_revision_id"),
                "knowledge_revisions": [
                    {"item_id": k["item_id"], "revision": k["revision"]}
                    for k in layer(frozen, "knowledge")["items"]
                ],
                "status": "PROPOSED",
            }
            artifact, _created = research_artifacts(session, context.scope, self._store).put_json(
                payload={"result": step_output, "provenance": provenance},
                project_id=step.project_id,
                revision=step.project_revision,
                stage_type=step.stage_type,
                artifact_type=ARTIFACT_TYPE,
                input_fingerprint=digest,
                runtime_version=self._build.sha or "",
                produced_by_job_id=step.attempt_id,
                metadata={
                    "run_id": step.run_id,
                    "turn_id": payload.get("turn_id"),
                    "context_sha256": payload["context_sha256"],
                },
            )
        return Succeeded(output={**step_output, "artifact_id": artifact.artifact_id})
