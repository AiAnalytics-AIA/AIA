"""A person's typed start, approved from its card: the chat start (lead-orchestration LO5).

The composer's typed commands are matched by code (:mod:`aia_core.domain.lead_commands`) and
stored on the person's own turn (its ``command``, through ``StudyLeadRepository``): no model is
in the path, so the card is the person's command and not Lead output. It stays approvable while
the Lead is switched off (D22, Q43); the Lead's kill switch refuses only cards its model
prepared (``ResearchLead.approve_request``).

Approving it starts the work under the same gates as the same work's other starts, in one
transaction and in LO1's order:

1. **Quote** (only with the study wallet on, ``AIA_STUDY_WALLET_ENABLED``): the ceiling against
   the wallet under the study row's lock, by ``money.start_verdict(CHAT_START)`` -- inside the
   wallet only, and the confirmation threshold asks in the same exchange
   (:class:`ChatStartRefused` ``outside_wallet`` / ``ceiling_unknown``, or the start's own
   :class:`~aia_core.application.research.CostConfirmationRequired`). With the wallet off,
   nothing is quoted or charged, as for every start today; the threshold still asks (LO15).
2. **Create the run** through the work's own start (``ResearchAgentJobs.start``,
   ``ResearchRuns.start``), which applies the threshold again and writes its ``spend`` row.
3. **Write ``chat_start``** naming the run (decision ``start``), the person's approval.
4. **Charge** the wallet at the ceiling when it is on; a refused charge raises, and the request's
   transaction rolls back the run and the row with it.

A start that finds its work already there (the same job on the same design, the revision's run)
returns it and writes nothing: it was authorised, and paid for, when it was created.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..domain.approval_ledger import ApprovalSubject
from ..domain.fieldwork import FieldworkSource, PersonaSource
from ..domain.lead_commands import RESEARCH_RUN, command_for, match_command
from ..domain.money import StartPath, StartVerdictKind, start_verdict
from ..domain.population import PopulationImportContract
from ..domain.research_lead import LeadTurn
from ..domain.scope import StudyContext
from ..domain.wallet import ChargeKind
from ..infrastructure.scope_repository import ScopeRepository
from ..infrastructure.workflow_repository import CHAT_START_REUSE, WorkflowRepository
from .research import (
    CostConfirmationRequired,
    ResearchAgentJobs,
    ResearchRuns,
    RunReservations,
    existing_start,
)
from .wallet import StudyWallets
from .workflows import StartedRun

__all__ = [
    "ChatStartRefused",
    "RunStartSettings",
    "approve_chat_start",
    "chat_start_decisions",
]


class ChatStartRefused(Exception):
    """A typed start the wallet does not admit (``outside_wallet``, ``ceiling_unknown``), or a
    stored command no code names any more (``unknown_command``). Nothing is written."""

    def __init__(
        self, reason: str, *, ceiling_usd: float | None = None, remaining_usd: float | None = None
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.ceiling_usd = ceiling_usd
        self.remaining_usd = remaining_usd


@dataclass(frozen=True, slots=True)
class RunStartSettings:
    """What a research run's start takes from the deployment, never from the request: the same
    values ``POST …/research/runs`` passes (``routers/research.py`` ``start_run``)."""

    fieldwork_source: FieldworkSource
    analysis_enabled: bool
    sociomapping_enabled: bool
    reservations: RunReservations
    persona_source: PersonaSource
    require_answerability: bool
    population_contract: PopulationImportContract
    population_id: str
    #: AIA_AI_ANALYSIS_EXTERNAL_CONTEXT: the run pins its Design Research context
    #: (evidence-integrity 7)
    external_context: bool = False


def chat_start_decisions(
    workflows: WorkflowRepository, turn_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """The ``chat_start`` rows naming these person turns, by turn id: the run each started, or
    for a ``reuse`` row the run it found already started (``reused``)."""
    if not turn_ids:
        return {}
    wanted = set(turn_ids)
    found: dict[str, dict[str, Any]] = {}
    for entry in workflows.ledger({ApprovalSubject.CHAT_START}):
        comment = json.loads(entry.comment or "{}")
        turn_id = comment.get("turn_id")
        if turn_id in wanted and turn_id not in found:
            reused = entry.decision == CHAT_START_REUSE
            run_id = comment.get("run_id") if reused else entry.run_id
            found[turn_id] = {"run_id": run_id, "comment": comment, "reused": reused}
    return found


def approve_chat_start(
    session: Session,
    scope: StudyContext,
    turn: LeadTurn,
    *,
    submit_design: Callable[[str], Any],
    confirm_cost_usd: float | None,
    reservation_usd: float | None,
    run_start: RunStartSettings | None,
    wallet_enabled: bool,
) -> dict[str, Any]:
    """Start the work the person's typed command named (``turn.command``), once.

    ``submit_design(source_stage)`` submits the working content as a Design Revision, as the
    Lead's approval does. ``run_start`` is the deployment's run settings; without them a typed
    research run is refused (``run_start_unavailable``). The caller holds the conversation's lock
    (``StudyLeadRepository.lock``), so two approvals of one card are decided one after the other.
    """
    assert turn.actor == "person" and turn.command is not None
    workflows = WorkflowRepository(session, scope)
    done = chat_start_decisions(workflows, [turn.turn_id]).get(turn.turn_id)
    if done is not None:
        run = workflows.get_run(str(done["run_id"]))
        return {
            "run_id": run["run_id"],
            "design_revision_id": run["metadata"]["design_revision_id"],
            "status": run["status"].value,
        }
    # The stored text, matched again by today's code: the command the server matched when the
    # person typed it, and the instruction they typed after it. A name no command has any more,
    # or text that no longer matches it, starts nothing.
    command = command_for(turn.command)
    matched = match_command(turn.text)
    if command is None or matched is None or matched.command is not command:
        raise ChatStartRefused("unknown_command")
    wallets = StudyWallets(session, scope, enabled=wallet_enabled)
    threshold = ScopeRepository(session).get_study(scope).spend_confirm_usd

    def quote(ceiling: float | None) -> None:
        """Step 1: inside the wallet, else refused; the threshold asks in the same exchange."""
        if not wallet_enabled:
            return
        _verdict, remaining = wallets.quote(ceiling)
        verdict = start_verdict(
            StartPath.CHAT_START,
            ceiling_usd=ceiling,
            threshold_usd=threshold,
            confirmed_usd=confirm_cost_usd,
            wallet_remaining_usd=remaining,
        )
        if verdict.kind is StartVerdictKind.REFUSED:
            raise ChatStartRefused(
                verdict.reason or "refused", ceiling_usd=ceiling, remaining_usd=remaining
            )
        if verdict.kind is StartVerdictKind.ASK:
            assert ceiling is not None and threshold is not None
            raise CostConfirmationRequired(ceiling_usd=ceiling, limit_usd=threshold)

    # A start that would find its run already there (the same job or run on the same design,
    # started by an earlier approval or on its stage) is not held to the wallet or the threshold
    # again: nothing is created or charged, and the card is decided by a reuse row below.
    if command.start == RESEARCH_RUN:
        if run_start is None:
            raise ChatStartRefused("run_start_unavailable")
        revision = submit_design("run")
        runs = ResearchRuns(
            session,
            scope,
            population_contract=run_start.population_contract,
            population_id=run_start.population_id,
        )
        outlook = runs.outlook(
            revision.revision_id,
            persona_source=run_start.persona_source,
            fieldwork_source=run_start.fieldwork_source,
        )
        run_kwargs: dict[str, Any] = {
            "design_revision_id": revision.revision_id,
            "fieldwork_source": run_start.fieldwork_source,
            "analysis_enabled": run_start.analysis_enabled,
            "external_context": run_start.external_context,
            "sociomapping_enabled": run_start.sociomapping_enabled,
            "reservations": run_start.reservations,
            "persona_source": run_start.persona_source,
            "require_answerability": run_start.require_answerability,
        }
        found = existing_start(session, scope, lambda: runs.start(**run_kwargs, _probe=True))
        ceiling: float | None = None
        if outlook.spec is not None:
            # A design that does not compile is refused by the start itself, by name.
            ceiling = runs.cost_ceiling(
                outlook.spec,
                fieldwork_source=run_start.fieldwork_source,
                analysis_enabled=run_start.analysis_enabled,
                reservations=run_start.reservations,
            ).total_usd
            if found is None:
                quote(ceiling)
        started: StartedRun = runs.start(**run_kwargs, confirm_cost_usd=confirm_cost_usd)
        kind = ChargeKind.RESEARCH_RUN
    else:
        assert command.action is not None
        action = command.action
        revision = submit_design(_SOURCE_STAGE.get(action.value, "questionnaire"))
        jobs = ResearchAgentJobs(session, scope, reservation_usd=reservation_usd)
        found = existing_start(
            session,
            scope,
            lambda: jobs.start(
                design_revision_id=revision.revision_id,
                action=action,
                instruction=matched.instruction,
                _probe=True,
            ),
        )
        if found is None:
            quote(reservation_usd)
        started = jobs.start(
            design_revision_id=revision.revision_id,
            action=action,
            instruction=matched.instruction,
            confirm_cost_usd=confirm_cost_usd,
        )
        ceiling = reservation_usd
        kind = ChargeKind.AGENT_JOB

    if not started.created:
        # The same job on the same design, started by an earlier approval: nothing starts and
        # nothing is charged, but this card is decided, so it never asks again.
        workflows.record_chat_start(
            started.run_id,
            turn_id=turn.turn_id,
            start=command.start,
            ceiling_usd=ceiling,
            design_revision_id=revision.revision_id,
            reused=True,
        )
    else:
        decision_id = workflows.record_chat_start(
            started.run_id,
            turn_id=turn.turn_id,
            start=command.start,
            ceiling_usd=ceiling,
            design_revision_id=revision.revision_id,
        )
        if wallet_enabled:
            wallets.charge(
                run_id=started.run_id,
                kind=kind,
                ceiling_usd=ceiling,
                approval_decision_id=decision_id,
            )
    return {
        "run_id": started.run_id,
        "design_revision_id": revision.revision_id,
        "status": started.run["status"].value,
    }


#: The stage a Design Revision is submitted from for a typed design job, as the Lead's approval
#: and the web's own buttons submit it.
_SOURCE_STAGE: dict[str, str] = {
    "analyze_brief": "brief",
    "propose_audience": "audience",
    "suggest_dimensions": "persona",
}
