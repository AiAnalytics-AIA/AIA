"""AI proposals from a client's document, paid by the client (lifecycle K2d3).

One step, ``client_source_proposals``, run as the client's own work: no study, the
client's budget holds and pays every call (client-budget CB3). It reads the exact
reading the run was queued with, asks the model batch by batch
(``domain.source_proposals``), keeps only proposals whose quote is literally in the
segment they name, and files those as client knowledge *proposals* (``authored: "ai"``),
never as knowledge. A person accepts or not.

Off unless ``AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED`` composes the gateway; unconfigured,
the step parks (``client_source_proposals_unconfigured``) without spending an attempt.
A document takes at most ``MAX_REQUESTS`` requests, each within a stated window its hold is
sized to (K2d6); one over is refused by name before any is sent. One attempt
(``max_attempts=1``): a step that lost its answers is started again by a person, never
re-sent by the worker. Filing is once per run, so a recovered step that had already filed
files nothing twice.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Final

from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.domain.ai_contracts import ModelCallFailed, ModelRequest, canonical_json
from aia_core.domain.ai_material import MaterialApproval, most_restrictive_material
from aia_core.domain.deep_research.request_limits import window_fits
from aia_core.domain.knowledge import ProposalDraft
from aia_core.domain.material_rules import OPERATOR_SOURCE, MaterialRule, rule_class, source_rule
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass
from aia_core.domain.scope import ClientWorkContext
from aia_core.domain.source_proposals import (
    HARNESS_VERSION,
    PROMPT_ID,
    PROMPT_VERSION,
    NotExtractable,
    SourceProposals,
    batch_classification,
    batches,
    ground,
    proposal_request,
    request_bytes,
    request_window_tokens,
    require_extractable,
    require_within_requests,
)
from aia_core.domain.workflow import FailureClass
from aia_core.domain.workflow_templates import CLIENT_SOURCE_PROPOSALS
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from aia_core.infrastructure.client_source_repository import (
    ClientSourceRepository,
    SourceReadingChanged,
)
from aia_core.infrastructure.client_work_journal import ClientWorkJournal
from aia_core.infrastructure.storage import ArtifactStore
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome, Succeeded

from .ai_runtime import AIRuntimeSettings
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
    #: An operator's exact-bytes classifications: they raise a batch's class, never lower it.
    material_approvals: tuple[MaterialApproval, ...] = ()

    @classmethod
    def from_settings(cls, settings: AIRuntimeSettings) -> SourceProposalsConfig:
        """The step's configuration from the worker's AI runtime settings, in one place."""
        return cls(
            policy_version=settings.policy_version,
            max_output_tokens=settings.client_source_max_output_tokens,
            reservation_usd=settings.client_source_reservation_usd,
            step_events=settings.step_events,
            material_approvals=settings.material_approvals,
        )


def _answer_class(answer: dict[str, Any]) -> tuple[str, str]:
    """The class a journaled answer was sent as, and what gave it (a rule, or ``operator``).
    An answer kept before classes were journaled was sent as Class A, the client's source,
    which every request then declared."""
    source = answer.get("class_source") or MaterialRule.CLIENT_SOURCE.value
    data_class = answer.get("data_class") or rule_class(MaterialRule(source)).value
    return str(data_class), str(source)


def _request_key(request: ModelRequest, cfg: SourceProposalsConfig) -> str:
    """What identifies an answer: exactly what was sent, under which policy and harness."""
    return hashlib.sha256(
        canonical_json(
            {
                "harness": HARNESS_VERSION,
                "policy": cfg.policy_version,
                "max_output_tokens": cfg.max_output_tokens,
                "system": request.system,
                "message": request.messages[0].content,
                "schema": request.agent.schema,
            }
        ).encode()
    ).hexdigest()


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
        try:
            # The burst and the money have a ceiling whatever the text is made of (K2d6).
            require_within_requests(work)
        except NotExtractable as exc:
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={
                    "reason": exc.reason,
                    "message": f"z podkladu nelze navrhovat: {exc.reason}",
                },
            )
        caller = StepModelCaller(
            gateway=self._gateway,
            context=context,
            runtime_version=self._build.sha or "",
            provider=Provider.AWS_BEDROCK,
            reservation_usd=cfg.reservation_usd,
            announce=cfg.step_events,
        )
        # A client's source is Class A; one a person marked "Interní dokument" is Class C
        # (the owner's rule, 2026-10-19), raised by an operator's classification of a batch's
        # exact material. Read as it stands when the requests are built.
        internal = record.internal is not None
        classes = [
            batch_classification(batch, internal=internal, approvals=cfg.material_approvals)
            for batch in work
        ]
        # The class the requests were built as: the most restrictive batch's, and what gave
        # it -- the source's rule, or an operator who raised a batch above it.
        built_class = most_restrictive_material([c.data_class for c in classes]) or rule_class(
            source_rule(internal=internal)
        )
        raised = [c for c in classes if c.data_class is built_class and c.source == OPERATOR_SOURCE]
        built_source = OPERATOR_SOURCE if raised else source_rule(internal=internal).value
        requests = [
            proposal_request(
                batch,
                policy_version=cfg.policy_version,
                max_output_tokens=cfg.max_output_tokens,
                internal=internal,
                approvals=cfg.material_approvals,
            )
            for batch in work
        ]
        # Every request fits the window its hold was sized to; by construction, checked anyway.
        window = request_window_tokens(cfg.max_output_tokens)
        if any(
            not window_fits(
                request_bytes(r), window_tokens=window, output_tokens=cfg.max_output_tokens
            )
            for r in requests
        ):
            return Failed(
                FailureClass.SCHEMA_VIOLATION,
                error={"reason": "request_too_large", "message": "a request exceeds its window"},
            )
        # What was already answered -- by an earlier attempt parked at the budget or
        # released, or by an earlier run over this reading -- is replayed, never re-sent.
        keys = [_request_key(r, cfg) for r in requests]
        with context.transaction() as (session, _):
            journal = ClientWorkJournal(session, scope)
            kept_answers = {k: journal.get(k) for k in keys}
        # Every class still to be sent is asked before the first request leaves: a batch an
        # operator raised above the rest would otherwise be refused only after the earlier
        # ones were sent and paid for.
        unsent: dict[DataClass | None, ModelRequest] = {}
        for request, key in zip(requests, keys, strict=True):
            if kept_answers[key] is None:
                unsent.setdefault(request.data_classification, request)
        if unsent:
            try:
                for request in unsent.values():
                    caller.preflight(request)
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
        sent = replayed = 0
        answer_classes: set[str] = set()
        for batch, request, key, ruled in zip(work, requests, keys, classes, strict=True):
            context.checkpoint()
            context.progress(
                f"Čtu část {batch.index + 1} z {len(work)}",
                batch=batch.index + 1,
                batches=len(work),
            )
            answer = kept_answers[key]
            if answer is None:
                # The mark the requests were built under must still hold when each one leaves:
                # a person who unmarks a source mid-run stops what is not yet sent. What was
                # answered is kept; a new start builds every request under the mark then.
                with context.transaction() as (session, _):
                    marked = ClientSourceRepository(session, self._store).marked_internal(
                        scope, source_id
                    )
                if marked != (record.internal is not None):
                    return Failed(
                        FailureClass.SCHEMA_VIOLATION,
                        error={
                            "reason": "source_class_changed",
                            "message": "označení Interní dokument se během návrhů změnilo; "
                            "spusťte návrhy znovu",
                        },
                    )
                result = caller.invoke(request)
                assert isinstance(result.output, SourceProposals)
                answer = {
                    "output": result.output.model_dump(mode="json"),
                    "call_id": result.call_id,
                    "model": result.resolved_model,
                    "route_id": result.provenance.route_id,
                    "policy_version": result.provenance.policy_version,
                    # The class this answer was sent as: a replay names it, not the mark the
                    # source carries when it is replayed.
                    "data_class": ruled.data_class.value,
                    "class_source": ruled.source,
                }
                # Kept the moment it returns, under the lease: a stop before the next
                # batch resumes here rather than paying for this one again.
                with context.transaction() as (session, _):
                    answer = ClientWorkJournal(session, scope).put(
                        key, run_id=step.run_id, payload=answer
                    )
                sent += 1
            else:
                replayed += 1
            answer_class, answer_source = _answer_class(answer)
            answer_classes.add(answer_class)
            output = SourceProposals.model_validate(answer["output"])
            grounding = ground(batch, output)
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
                    "call_id": answer["call_id"],
                    "model": answer["model"],
                    "route_id": answer["route_id"],
                    "policy_version": answer["policy_version"],
                    "data_class": answer_class,
                    "class_source": answer_source,
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
                "sent": sent,
                "replayed": replayed,
                "proposed": len(filed),
                "dropped": dropped,
                # The class the requests were built as, and the rule that gave it.
                "data_class": built_class.value,
                "class_source": built_source,
                # The classes the answers used were sent as: a replay keeps its own.
                "answer_classes": sorted(answer_classes),
            }
        )
