"""Native Research agent jobs over the governed Bedrock seam.

One logical request (plus the gateway's bounded schema repair), one proposal
artifact. No automatic retry: losing a known answer before artifact commit must
not spend again. A saved artifact is checked before any model preflight/call.

The step's output names the items the proposal changes against its baseline, the working
revision its Design Revision came from (``touched_items``, ADR 0026 decision 5); a person's
accept checks them against what changed in the working copy since. A job with no known
baseline records ``None``, and its accept is refused as ``unknown_baseline``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.application.research import research_artifacts
from aia_core.domain.ai_contracts import ModelCallFailed, canonical_json
from aia_core.domain.ai_material import MaterialApproval, classify_material
from aia_core.domain.design_items import Documents
from aia_core.domain.material_rules import MaterialRule, rule_class
from aia_core.domain.prompt_slots import get_slot
from aia_core.domain.prompts import PromptPin
from aia_core.domain.providers import Provider
from aia_core.domain.research_agents import (
    DESIGN_ACTIONS,
    HARNESS_VERSION,
    ResearchAction,
    agent_request,
    design_classification,
    instruction_classification,
    prompt_class_source,
    prompt_data_class,
    prompt_for,
    proposal_result,
    snapshot_hash,
    touched_items,
)
from aia_core.domain.scope import StudyContext
from aia_core.domain.workflow import FailureClass
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import ArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome, Succeeded
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .ai_step import StepModelCaller, class_advisory_fields

ARTIFACT_TYPE = "research_agent_proposal"


def _pin_of(payload: Mapping[str, Any], action: ResearchAction) -> PromptPin:
    """The prompt this job was queued with. Never what is active now.

    A job queued before prompts were data has no pin and ran the code's wording, so it
    still does. A pin that does not hash to its own text, or that names another
    action's prompt, is refused -- the run is not guessed at.
    """
    prompt_id = f"aia.research.{action.value}"
    raw = payload.get("prompt")
    if raw is None:
        slot = get_slot(prompt_id)
        assert slot is not None  # every action is a registered slot
        return slot.baseline_pin()
    pin = PromptPin(**raw)
    if pin.prompt_id != prompt_id:
        raise ValueError(f"prompt pin {pin.prompt_id} is not {prompt_id}")
    return pin


def _touched(
    session: Session,
    scope: StudyContext,
    payload: Mapping[str, Any],
    action: ResearchAction,
    proposal: Mapping[str, Any],
) -> list[str] | None:
    """The items ``proposal`` changes against the working revision the job's design came from.

    ``None`` -- not an empty list -- when that baseline is unknown (a job queued before the
    rule, a design that names no working revision, a revision the working copy does not hold)
    or the job is advice: unknown is never read as "touches nothing".
    """
    base = payload.get("base_workspace_revision")
    if action not in DESIGN_ACTIONS or not isinstance(base, int) or isinstance(base, bool):
        return None
    stored = StudyWorkspaceRepository(session).at_revision(scope, base)
    if stored is None:
        return None
    baseline = Documents(content=dict(stored.content or {}), analysis=stored.analysis)
    return sorted(str(k) for k in touched_items(action, baseline, dict(proposal)))


@dataclass(frozen=True, slots=True)
class ResearchAgentConfig:
    policy_version: str
    max_output_tokens: int
    context_window_tokens: int
    reservation_usd: float
    fictional_client_ids: frozenset[str]
    material_approvals: tuple[MaterialApproval, ...] = ()
    #: Each model request writes a "sent" and an "answered" event (``AIA_AI_STEP_EVENTS``).
    step_events: bool = False


class ResearchAgentExecutor:
    def __init__(
        self,
        *,
        store: ArtifactStore,
        build: BuildIdentity,
        gateway: GovernedModelGateway | None = None,
        config: ResearchAgentConfig | None = None,
    ) -> None:
        self._store, self._build = store, build
        self._gateway, self._config = gateway, config

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        cfg = self._config
        if cfg is None or self._gateway is None:
            return Failed(
                FailureClass.RUNTIME_UNAVAILABLE,
                error={
                    "reason": "research_agents_unconfigured",
                    "message": "AI návrhy výzkumu nejsou zapnuté. Zadání zůstává uložené.",
                },
            )
        if step.payload.get("harness_version") != HARNESS_VERSION:
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={"message": "harness version changed; enqueue a new job"},
            )
        action = ResearchAction(step.payload["action"])
        try:
            pin = _pin_of(step.payload, action)
        except (ValueError, TypeError, ValidationError):
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={
                    "message": "the prompt this job was queued with is not valid; enqueue a new job"
                },
            )
        snapshot = dict(step.payload["snapshot"])
        expected = hashlib.sha256(
            canonical_json(
                {
                    "action": action.value,
                    "context": snapshot_hash(snapshot),
                    "instruction": str(step.payload.get("instruction", "")),
                    "prompt": prompt_for(action, pin.text),
                }
            ).encode()
        ).hexdigest()
        if expected != step.payload["job_fingerprint"]:
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={"message": "context or prompt changed; enqueue a new job"},
            )
        digest = hashlib.sha256(
            canonical_json(
                {
                    "job": step.payload["job_fingerprint"],
                    "design_revision_id": step.payload["design_revision_id"],
                    "policy": cfg.policy_version,
                    "output_budget": cfg.max_output_tokens,
                }
            ).encode()
        ).hexdigest()
        with context.transaction() as (session, _):
            designs = StudyDesignRepository(session, context.scope)
            revision_id = str(step.payload["design_revision_id"])
            revision = designs.get(revision_id)
            if (
                revision.revision != step.project_revision
                or designs.project_id() != step.project_id
            ):
                return Failed(
                    FailureClass.SCHEMA_VIOLATION,
                    error={"message": "job design does not match held scope"},
                )
            baseline = designs.content(revision_id)
            artifacts = research_artifacts(session, context.scope, self._store)
            existing = artifacts.find_reusable(
                project_id=step.project_id,
                stage_type=step.stage_type,
                artifact_type=ARTIFACT_TYPE,
                input_fingerprint=digest,
            )
            if existing is not None:
                stored = artifacts.read_json(existing.artifact_id)  # verifies its bytes
                kept = stored.get("result") if isinstance(stored, dict) else None
                return Succeeded(
                    output={
                        "artifact_id": existing.artifact_id,
                        "reused": True,
                        "touched_items": _touched(
                            session, context.scope, step.payload, action, kept or {}
                        )
                        if isinstance(kept, dict)
                        else None,
                    }
                )
        request = agent_request(
            action,
            snapshot,
            instruction=str(step.payload.get("instruction", "")),
            policy_version=cfg.policy_version,
            max_output_tokens=cfg.max_output_tokens,
            material_approvals=cfg.material_approvals,
            prompt=pin,
        )
        # UTF-8 bytes give a conservative input bound, including the contract and
        # one repair's maximum response. Fail before reserving/sending, never trim.
        prompt_bytes = len(
            (
                request.system + request.messages[0].content + canonical_json(request.agent.schema)
            ).encode()
        )
        if prompt_bytes + 5 * cfg.max_output_tokens + 2048 > cfg.context_window_tokens:
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={"message": "context exceeds the configured model window"},
            )
        caller = StepModelCaller(
            gateway=self._gateway,
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
                    "message": f"AI návrh čeká na povolenou trasu nebo licenci: {exc}",
                },
            )
        context.progress("Připravený kontext; AI zpracovává návrh", action=action.value)
        result = caller.invoke(request)
        assert result.output is not None
        try:
            proposal = proposal_result(action, baseline, result.output, snapshot)
        except ValueError as exc:
            return Failed(FailureClass.SCHEMA_VIOLATION, error={"message": str(exc)})
        # The class the gateway sent it as: the request's or, when a part's class is unknown
        # and the class gates are advisory (develop only), the class it was judged as, with the
        # advisory recorded. Under enforce an unknown class was refused at the preflight above.
        prompt_class = prompt_data_class(pin, cfg.material_approvals)
        instruction_rule = instruction_classification(
            str(step.payload.get("instruction", "")), cfg.material_approvals
        )
        provenance: dict[str, Any] = {
            "agent_id": request.agent.agent_id,
            "agent_version": request.agent.version,
            "harness_version": HARNESS_VERSION,
            "prompt_version": request.agent.prompt_version,
            # The system prompt as sent (the code's frame around the instruction), then the
            # instruction alone and where it came from: the code's wording or an edit.
            "prompt_sha256": hashlib.sha256(request.system.encode()).hexdigest(),
            "prompt_origin": pin.origin,
            "prompt_text_sha256": pin.text_sha256,
            "schema_fingerprint": result.provenance.schema_fingerprint,
            "design_revision_id": revision_id,
            "context_sha256": snapshot_hash(snapshot),
            "knowledge_revisions": [
                {"item_id": k["item_id"], "revision": k["revision"]} for k in snapshot["knowledge"]
            ],
            "omitted_knowledge_ids": snapshot["omitted_knowledge_ids"],
            "call_id": result.call_id,
            "provider_request_id": result.provider_request_id,
            "model": result.resolved_model,
            "route_id": result.provenance.route_id,
            "policy_version": result.provenance.policy_version,
            "cost_usd": result.total_cost_usd,
            "status": "PROPOSED",
            "data_class": result.provenance.data_class.value,
            **class_advisory_fields(result.provenance.class_advisories),
            "material_classification": {
                # The design and a nonempty instruction: Class B by the owner's rule
                # (``rule:design``, ``rule:job_instruction``), or an operator's stricter class
                # of their exact bytes (``operator``); an empty instruction holds no material.
                "design": design_classification(snapshot, cfg.material_approvals).model_dump(
                    mode="json"
                ),
                "instruction": None
                if instruction_rule is None
                else instruction_rule.model_dump(mode="json"),
                # Where the prompt's class came from (prompt_data_class): the code's wording is
                # reviewed with the code; a stored edit travels on its author's recorded
                # declaration, an operator's classification of its exact text, or both (the
                # stricter one wins).
                "prompt": {
                    "origin": pin.origin,
                    "data_class": None if prompt_class is None else prompt_class.value,
                    "source": prompt_class_source(pin, cfg.material_approvals),
                    "text_sha256": pin.text_sha256,
                    "material_sha256": None
                    if pin.origin == "baseline"
                    else classify_material(pin.text, cfg.material_approvals).sha256,
                    "declared_class": pin.declared_class,
                    "declared_by": pin.declared_by,
                },
                "knowledge_class": rule_class(MaterialRule.KNOWLEDGE).value,
            },
        }
        proposal["project"]["agent_provenance"] = {
            "run_id": step.run_id,
            "action": action.value,
            "design_revision_id": revision_id,
            "context_sha256": snapshot_hash(snapshot),
            "harness_version": HARNESS_VERSION,
            "prompt_sha256": provenance["prompt_sha256"],
            "prompt_version": pin.version,
            "prompt_origin": pin.origin,
        }
        with context.transaction() as (session, _):
            artifact, created = research_artifacts(session, context.scope, self._store).put_json(
                payload={"result": proposal, "provenance": provenance},
                project_id=step.project_id,
                revision=step.project_revision,
                stage_type=step.stage_type,
                artifact_type=ARTIFACT_TYPE,
                input_fingerprint=digest,
                runtime_version=self._build.sha or "",
                produced_by_job_id=step.attempt_id,
                metadata={
                    "run_id": step.run_id,
                    "action": action.value,
                    "context_sha256": snapshot_hash(snapshot),
                },
            )
            touched = _touched(session, context.scope, step.payload, action, proposal)
        return Succeeded(
            output={
                "artifact_id": artifact.artifact_id,
                "reused": not created,
                "touched_items": touched,
            }
        )
