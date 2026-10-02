"""Native Research agent jobs over the governed Bedrock seam.

One logical request (plus the gateway's bounded schema repair), one proposal
artifact. No automatic retry: losing a known answer before artifact commit must
not spend again. A saved artifact is checked before any model preflight/call.
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
from aia_core.domain.prompt_slots import get_slot
from aia_core.domain.prompts import PromptPin
from aia_core.domain.providers import Provider
from aia_core.domain.research_agents import (
    HARNESS_VERSION,
    ResearchAction,
    agent_request,
    prompt_for,
    proposal_result,
    snapshot_hash,
)
from aia_core.domain.workflow import FailureClass
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import ArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome, Succeeded
from pydantic import ValidationError

from .ai_step import StepModelCaller

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


@dataclass(frozen=True, slots=True)
class ResearchAgentConfig:
    policy_version: str
    max_output_tokens: int
    context_window_tokens: int
    reservation_usd: float
    fictional_client_ids: frozenset[str]
    material_approvals: tuple[MaterialApproval, ...] = ()


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
                artifacts.read(existing.artifact_id)  # verify bytes, not only existence
                return Succeeded(output={"artifact_id": existing.artifact_id, "reused": True})
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
        assert request.data_classification is not None
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
            "data_class": request.data_classification.value,
            "material_classification": {
                "design": classify_material(snapshot["design"], cfg.material_approvals).model_dump(
                    mode="json"
                ),
                "instruction": classify_material(
                    str(step.payload.get("instruction", "")), cfg.material_approvals
                ).model_dump(mode="json"),
                "knowledge_class": "CLASS_A_CLIENT_CONFIDENTIAL",
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
        return Succeeded(output={"artifact_id": artifact.artifact_id, "reused": not created})
