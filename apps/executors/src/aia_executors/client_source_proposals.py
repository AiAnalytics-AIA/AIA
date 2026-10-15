"""AI proposals from a client's document, paid by the client (lifecycle K2d3).

One step, ``client_source_proposals``, run as the client's own work: no study, the
client's budget holds and pays every call (client-budget CB3). It reads the exact
reading the run was queued with, asks the model batch by batch
(``domain.source_proposals``), keeps only proposals whose quote is literally in the
segment they name, and files those as client knowledge *proposals* (``authored: "ai"``),
never as knowledge. A person accepts or not.

Off unless ``AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED`` composes the gateway; unconfigured,
the step parks (``client_source_proposals_unconfigured``) without spending an attempt.
One attempt (``max_attempts=1``): a step that lost its answers is started again by a
person, never re-sent by the worker. Filing is once per run, so a recovered step that
had already filed files nothing twice.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Final

from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.domain.ai_contracts import ModelCallFailed
from aia_core.domain.knowledge import ProposalDraft
from aia_core.domain.providers import Provider
from aia_core.domain.scope import ClientWorkContext
from aia_core.domain.source_proposals import (
    HARNESS_VERSION,
    PROMPT_ID,
    PROMPT_VERSION,
    NotExtractable,
    SourceProposals,
    batches,
    ground,
    proposal_request,
    require_extractable,
)
from aia_core.domain.workflow import FailureClass
from aia_core.domain.workflow_templates import CLIENT_SOURCE_PROPOSALS
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from aia_core.infrastructure.client_source_repository import (
    ClientSourceRepository,
    SourceReadingChanged,
)
from aia_core.infrastructure.storage import ArtifactStore
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome, Succeeded

from .ai_step import StepModelCaller

__all__ = ["KIND", "ClientSourceProposalsExecutor", "SourceProposalsConfig"]

KIND: Final = CLIENT_SOURCE_PROPOSALS


@dataclass(frozen=True, slots=True)
class SourceProposalsConfig:
    policy_version: str
    max_output_tokens: int
    #: Held per request: the primary and its one schema repair at the model's ceilings.
    reservation_usd: float
    #: Each model request writes a "sent" and an "answered" event (``AIA_AI_STEP_EVENTS``).
    step_events: bool = False


class ClientSourceProposalsExecutor:
    def __init__(
        self,
        *,
        store: ArtifactStore,
        build: BuildIdentity,
        gateway: GovernedModelGateway | None = None,
        config: SourceProposalsConfig | None = None,
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
                    "reason": "client_source_proposals_unconfigured",
                    "message": "AI návrhy znalostí z podkladů nejsou zapnuté. Podklad zůstává "
                    "uložený.",
                },
            )
        scope = context.work_scope
        if not isinstance(scope, ClientWorkContext):
            return Failed(
                FailureClass.PERMISSION,
                error={"reason": "not_client_work", "message": "návrhy platí klient, ne studie"},
            )
        if step.payload.get("harness_version") != HARNESS_VERSION:
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={
                    "reason": "harness_changed",
                    "message": "harness version changed; start the proposals again",
                },
            )
        source_id = str(step.payload["source_id"])
        reading_sha256 = str(step.payload["reading_sha256"])
        with context.transaction() as (session, _):
            try:
                record, reading = ClientSourceRepository(session, self._store).pinned_reading(
                    scope, source_id, reading_sha256=reading_sha256
                )
            except SourceReadingChanged:
                return Failed(
                    FailureClass.SCHEMA_VIOLATION,
                    error={
                        "reason": "reading_changed",
                        "message": "podklad byl mezitím přečten znovu; spusťte návrhy znovu",
                    },
                )
        try:
            require_extractable(record.family, reading)
        except NotExtractable as exc:
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={
                    "reason": exc.reason,
                    "message": f"z podkladu nelze navrhovat: {exc.reason}",
                },
            )
        work = batches(reading)
        caller = StepModelCaller(
            gateway=self._gateway,
            context=context,
            runtime_version=self._build.sha or "",
            provider=Provider.AWS_BEDROCK,
            reservation_usd=cfg.reservation_usd,
            announce=cfg.step_events,
        )
        requests = [
            proposal_request(
                batch, policy_version=cfg.policy_version, max_output_tokens=cfg.max_output_tokens
            )
            for batch in work
        ]
        try:
            caller.preflight(requests[0])
        except ModelCallFailed as exc:
            return Failed(
                FailureClass.RUNTIME_UNAVAILABLE,
                error={
                    "reason": exc.reason,
                    "message": f"AI návrhy čekají na povolenou trasu: {exc}",
                },
            )
        prompt_sha256 = hashlib.sha256(requests[0].system.encode()).hexdigest()
        drafts: list[ProposalDraft] = []
        dropped: dict[str, int] = {}
        for batch, request in zip(work, requests, strict=True):
            context.checkpoint()
            context.progress(
                f"Čtu část {batch.index + 1} z {len(work)}",
                batch=batch.index + 1,
                batches=len(work),
            )
            result = caller.invoke(request)
            assert isinstance(result.output, SourceProposals)
            grounding = ground(batch, result.output)
            for reason, count in grounding.dropped.items():
                dropped[reason] = dropped.get(reason, 0) + count
            for kept in grounding.kept:
                locator = kept.locator.model_dump(mode="json", exclude_none=True)
                provenance: dict[str, Any] = {
                    "source_id": record.source_id,
                    "source_sha256": record.sha256,
                    "reader": reading.reader,
                    "reading_sha256": reading_sha256,
                    "segment": kept.segment,
                    "locator": locator,
                    "agent_id": PROMPT_ID,
                    "prompt_version": PROMPT_VERSION,
                    "prompt_sha256": prompt_sha256,
                    "harness_version": HARNESS_VERSION,
                    "call_id": result.call_id,
                    "model": result.resolved_model,
                    "route_id": result.provenance.route_id,
                    "policy_version": result.provenance.policy_version,
                }
                drafts.append(
                    ProposalDraft(
                        kind=kept.kind,
                        title=kept.title,
                        summary=kept.summary,
                        content={"quote": kept.quote, "locator": locator},
                        provenance=provenance,
                    )
                )
        with context.transaction() as (session, _):
            filed = ClientKnowledgeRepository(session).propose_from_client_work(
                scope, run_id=step.run_id, drafts=drafts
            )
        return Succeeded(
            output={
                "source_id": record.source_id,
                "reading_sha256": reading_sha256,
                "batches": len(work),
                "proposed": len(filed),
                "dropped": dropped,
            }
        )
