"""A Lead card that starts Deep Research, approved by the person (lead-orchestration LO5a.2).

The Lead prepares the request (LO5a.1: a preset, a design focus, an Interpretation target from
its turn's frozen candidates, or a retry); the person's approval starts it on the server under
the same gates as the stage's own start, in one transaction and in LO1's order:

1. **Freeze once.** A design card freezes the Design Revision it was quoted on with its focus
   (``DeepResearchRuns.freeze_design(…, focus=)``); an Interpretation card resolves its target
   from the turn's own frozen ``targets`` layer, never from today's study, and freezes it with
   every pin verified (``freeze_interpretation``); a retry card re-freezes the run it names
   (``retry_spec``). That one spec is the one quoted and the one enqueued.
2. **Quote** it (``DeepResearchRuns.quote``, DRL-0's admission), and with the study wallet on
   (``AIA_STUDY_WALLET_ENABLED``) hold its ceiling to the wallet as a person's typed start is
   held (:func:`~aia_core.application.lead_chat_start.wallet_admits`, ``StartPath.CHAT_START``).
3. **Create the run** (``start_frozen``): the threshold, the live settings and the ``spend`` row
   are the start's own.
4. **Record** the card's ``lead_job_request`` row: the run, its purpose, target, preset, focus,
   ceiling and the confirmed ``spend``.
5. With the wallet on, write the ``lead_card`` row naming the run (decision ``start``, migration
   M3b) and **charge** it at the ceiling the created run pinned (the start admits again, so a
   setting changed since the quote is charged as pinned, never as quoted); a refused charge
   raises, and the request's transaction rolls back the run and both rows with it.

A start that finds its run already there (the same spec, started on the stage or by an earlier
card) returns it, charges nothing and records the card as decided. The stage's starts are
unchanged, and so is ``NotAPaidRequest`` for a research run's card, which only opens its stage.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from ..domain.deep_research.budgets import ResearchMode
from ..domain.deep_research.contracts import Channel
from ..domain.deep_research.integration import (
    DeepResearchPurpose,
    InterpretationLineage,
    ResearchTargetRef,
)
from ..domain.research_lead import (
    DeepResearchRetryRequest,
    DesignResearchRequest,
    InterpretationResearchRequest,
    LeadTurn,
)
from ..domain.run_cost import DeepResearchPrices
from ..domain.scope import StudyContext
from ..domain.wallet import ChargeKind
from ..infrastructure.storage import ArtifactStore
from ..infrastructure.workflow_repository import WorkflowRepository
from .deep_research import DeepResearchRuns, FrozenStart, ResearchTargetNotFound, StartVerdict
from .lead_chat_start import wallet_admits
from .wallet import StudyWallets

__all__ = [
    "INTERPRETATION_TITLE",
    "DeepResearchCardRequest",
    "DeepResearchCardSettings",
    "DeepResearchCardUnavailable",
    "approve_deep_research_card",
    "card_target",
]

DeepResearchCardRequest = (
    DesignResearchRequest | InterpretationResearchRequest | DeepResearchRetryRequest
)

#: The stage's own channel and Interpretation title (``api.ts`` ``deepResearch.start`` and
#: ``interpret``), so a card's run is the run the same stage start would make: the same spec and
#: fingerprint, found by idempotency whichever started it first. A title is never identity.
CARD_CHANNELS: Final = (Channel.WEB,)
INTERPRETATION_TITLE: Final = "Literární rešerše pro interpretaci studie"

_REF: Final[TypeAdapter[ResearchTargetRef]] = TypeAdapter(ResearchTargetRef)


class DeepResearchCardUnavailable(Exception):
    """A Deep Research card approved where no Deep Research start was composed for it (the
    caller gave no :class:`DeepResearchCardSettings`): nothing is frozen, written or held."""

    reason = "deep_research_start_unavailable"


@dataclass(frozen=True, slots=True)
class DeepResearchCardSettings:
    """What a Deep Research card's start takes from the deployment, never from the request: the
    prices and the mode the stage's own routes pass (``routers/deep_research.py``
    ``study_prices``, ``deep_research_mode``) and the store its pins are read from."""

    prices: DeepResearchPrices | None
    modes: tuple[ResearchMode, ...]
    store: ArtifactStore


def card_target(frozen: Mapping[str, Any] | None, target_id: str | None) -> ResearchTargetRef:
    """The ADR 0021 target an Interpretation card names, from the turn's frozen ``targets``
    layer: its ``target``, or the layer's default when it named none. Read from what the turn
    was shown, never from today's study; one it cannot find is
    :class:`~aia_core.application.deep_research.ResearchTargetNotFound`."""
    layers = (frozen or {}).get("layers") or []
    layer = next((e for e in layers if isinstance(e, Mapping) and e.get("layer") == "targets"), {})
    wanted = target_id if target_id is not None else layer.get("default")
    for candidate in layer.get("candidates") or ():
        if isinstance(candidate, Mapping) and candidate.get("id") == wanted:
            try:
                return _REF.validate_python(candidate.get("ref"))
            except ValidationError as exc:
                raise ResearchTargetNotFound(str(wanted)) from exc
    raise ResearchTargetNotFound(str(wanted))


def _research_run_id(target: object) -> str | None:
    """The research run an Interpretation target is a result of; ``None`` for a design's."""
    run_id = getattr(target, "research_run_id", None)
    return str(run_id) if run_id is not None else None


def _charge_kind(purpose: DeepResearchPurpose) -> ChargeKind:
    if purpose is DeepResearchPurpose.INTERPRETATION_RESEARCH:
        return ChargeKind.INTERPRETATION_RESEARCH
    return ChargeKind.DEEP_RESEARCH


def approve_deep_research_card(
    session: Session,
    scope: StudyContext,
    turn: LeadTurn,
    request: DeepResearchCardRequest,
    *,
    frozen: Mapping[str, Any] | None,
    submit_design: Callable[[], Any],
    settings: DeepResearchCardSettings,
    confirm_cost_usd: float | None,
    wallet_enabled: bool,
) -> dict[str, Any]:
    """Start what the Lead's Deep Research card prepared, once (see the module).

    ``frozen``: the turn's frozen context, where an Interpretation card's target is read.
    ``submit_design()``: the working content as the Design Revision a design card researches,
    after the caller's LO10 check. The caller holds the conversation's lock and has refused an
    approved card, a stale one and a switched-off Lead before this is called.
    """
    assert turn.run_id is not None
    runs = DeepResearchRuns(session, scope)
    runs.require_start()
    if isinstance(request, DesignResearchRequest):
        revision = submit_design()
        focus = tuple(request.focus)
        start = FrozenStart(
            runs.freeze_design(
                design_revision_id=revision.revision_id,
                preset_name=request.preset,
                channels=CARD_CHANNELS,
                focus=focus,
            ),
            focus=focus,
        )
    elif isinstance(request, InterpretationResearchRequest):
        start = FrozenStart(
            runs.freeze_interpretation(
                target=card_target(frozen, request.target),
                preset_name=request.preset,
                store=settings.store,
                channels=CARD_CHANNELS,
                title=INTERPRETATION_TITLE,
            )
        )
    else:
        start = runs.retry_spec(request.run_id, store=settings.store)
    spec = start.spec

    quoted = runs.quote(spec, prices=settings.prices, modes=settings.modes, retry_of=start.retry_of)
    ceiling = quoted.ceiling.total_usd if quoted.ceiling is not None else None
    wallets = StudyWallets(session, scope, enabled=wallet_enabled)
    if wallet_enabled and quoted.verdict is not StartVerdict.EXISTS:
        wallet_admits(session, scope, wallets, ceiling, confirm_cost_usd=confirm_cost_usd)
    started = runs.start_frozen(
        start, prices=settings.prices, modes=settings.modes, confirm_cost_usd=confirm_cost_usd
    )
    if started.created:
        # The start admits again, reading the organization's settings again: a route allowance
        # changed since the quote moves the ceiling the run pins. What is recorded and charged is
        # that pinned ceiling, never the quote's, so a larger one meets the wallet's own check
        # (and rolls the start back) rather than running past the remainder (review of #1006).
        pinned = started.run["metadata"].get("cost_ceiling_usd")
        ceiling = float(pinned) if pinned is not None else None

    # The card's own decision, with what it started; a run that already existed was confirmed
    # (or not) when it was created, so this approval confirmed no new spend.
    spend: dict[str, float] | None = None
    if (
        started.created
        and quoted.verdict is StartVerdict.CONFIRM
        and ceiling is not None
        and quoted.threshold_usd is not None
        and confirm_cost_usd is not None
    ):
        spend = {
            "ceiling_usd": ceiling,
            "limit_usd": quoted.threshold_usd,
            "confirmed_usd": confirm_cost_usd,
        }
    workflows = WorkflowRepository(session, scope)
    lineage = spec.lineage
    design_revision_id = (
        lineage.design.design_revision_id
        if isinstance(lineage, InterpretationLineage)
        else lineage.design_revision_id
    )
    workflows.record_lead_job_approval(
        turn.run_id,
        turn_id=turn.turn_id,
        agent_run_id=started.run_id,
        design_revision_id=design_revision_id,
        action=request.kind,
        spend=spend,
        details={
            "purpose": spec.purpose.value,
            "target": spec.target.model_dump(mode="json"),
            "preset": spec.engine_request.preset,
            "focus": list(start.focus),
            "ceiling_usd": ceiling,
            **({"retry_of": start.retry_of} if start.retry_of else {}),
        },
    )
    if wallet_enabled and started.created:
        decision_id = workflows.record_lead_card(
            started.run_id, turn_id=turn.turn_id, kind=request.kind, ceiling_usd=ceiling
        )
        wallets.charge(
            run_id=started.run_id,
            kind=_charge_kind(spec.purpose),
            ceiling_usd=ceiling,
            approval_decision_id=decision_id,
        )
    return {
        "run_id": started.run_id,
        "design_revision_id": design_revision_id,
        "status": started.run["status"].value,
        # Where its run is followed: a retry card does not say which checkpoint it retries, and
        # an Interpretation run is shown under the research run it interprets, not the newest.
        "purpose": spec.purpose.value,
        "research_run_id": _research_run_id(spec.target),
    }
