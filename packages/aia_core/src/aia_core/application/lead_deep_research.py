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
from ..domain.lead_commands import (
    DEEP_RESEARCH_RETRY,
    DEEP_RESEARCH_STOP,
    DESIGN_RESEARCH_STARTS,
    INTERPRETATION_RESEARCH_STARTS,
)
from ..domain.research import retryable
from ..domain.research_lead import (
    DeepResearchRetryRequest,
    DesignResearchRequest,
    InterpretationResearchRequest,
    LeadTurn,
)
from ..domain.run_cost import DeepResearchPrices
from ..domain.scope import StudyContext
from ..domain.wallet import ChargeKind
from ..domain.workflow import WorkflowRunStatus
from ..infrastructure.storage import ArtifactStore
from ..infrastructure.workflow_repository import WorkflowRepository
from .deep_research import (
    DeepResearchQuote,
    DeepResearchRuns,
    FrozenStart,
    ResearchTargetNotFound,
    StartVerdict,
)
from .lead_chat_start import wallet_admits
from .wallet import StudyWallets
from .workflows import StartedRun

__all__ = [
    "INTERPRETATION_TITLE",
    "DeepResearchCardRequest",
    "DeepResearchCardSettings",
    "DeepResearchCardUnavailable",
    "DeepResearchTargetMoved",
    "TypedDeepResearchRefused",
    "approve_deep_research_card",
    "approve_typed_deep_research",
    "card_target",
    "interpretation_target",
    "retry_target",
    "start_research",
    "stop_target",
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
    ``study_prices``, ``deep_research_mode``) and the store its pins are read from;
    ``document_store``, the store a document's text is read from under
    ``AIA_DEEP_RESEARCH_DOCUMENT_TEXT`` (client-knowledge-lifecycle K8b), ``None`` when off."""

    prices: DeepResearchPrices | None
    modes: tuple[ResearchMode, ...]
    store: ArtifactStore
    document_store: ArtifactStore | None = None


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


def start_research(
    session: Session,
    scope: StudyContext,
    runs: DeepResearchRuns,
    start: FrozenStart,
    *,
    settings: DeepResearchCardSettings,
    wallets: StudyWallets,
    wallet_enabled: bool,
    confirm_cost_usd: float | None,
) -> tuple[StartedRun, DeepResearchQuote, float | None]:
    """Steps 2 and 3 of the module, shared by a Lead card and a typed start (LO5a.3): quote the
    one frozen spec, hold its ceiling to the wallet when it is on, create the run; the ceiling
    returned is the one the created run pinned, else the quote's."""
    quoted = runs.quote(
        start.spec, prices=settings.prices, modes=settings.modes, retry_of=start.retry_of
    )
    ceiling = quoted.ceiling.total_usd if quoted.ceiling is not None else None
    # Unapproved live settings refuse first (the start below raises them), so the person is
    # never asked to confirm a cost for a run that cannot start (stand-in review of #1006).
    if wallet_enabled and quoted.verdict not in (
        StartVerdict.EXISTS,
        StartVerdict.LIVE_SETTINGS_UNAPPROVED,
    ):
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
    return started, quoted, ceiling


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
    runs = DeepResearchRuns(session, scope, document_store=settings.document_store)
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
    wallets = StudyWallets(session, scope, enabled=wallet_enabled)
    started, quoted, ceiling = start_research(
        session,
        scope,
        runs,
        start,
        settings=settings,
        wallets=wallets,
        wallet_enabled=wallet_enabled,
        confirm_cost_usd=confirm_cost_usd,
    )

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
        # A run another start had made stays that start's: its spend is not booked to this card.
        reused=not started.created,
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


class TypedDeepResearchRefused(Exception):
    """A typed Deep Research start, retry or stop with nothing to act on, by name (LO5a.3):
    ``no_default_target`` (an Interpretation start naming no target, with no completed
    research-questions module to default to), ``no_retryable_deep_research``,
    ``no_running_deep_research``. Nothing is written."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class DeepResearchTargetMoved(Exception):
    """The card named the run it would retry or stop, and another is that run now: nothing
    happens until the person confirms ``current_run_id`` (as :class:`~aia_core.application.
    lead_chat_start.AnalysisRetryTargetMoved`)."""

    def __init__(self, reason: str, *, current_run_id: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.current_run_id = current_run_id


#: The states a typed retry and a typed stop can act on, chosen in the query before its limit,
#: so newer runs in other states never hide them (Codex P2 on #1144).
_RETRYABLE: Final = tuple(s for s in WorkflowRunStatus if retryable(s))
_UNENDED: Final = tuple(s for s in WorkflowRunStatus if not s.is_terminal)


def retry_target(runs: DeepResearchRuns) -> dict[str, Any] | None:
    """The run a typed "Zopakuj rešerši" retries: the study's newest Deep Research run that can be
    retried (failed or cancelled), which its card names; ``None`` when there is none."""
    return next(iter(runs.runs(limit=1, statuses=_RETRYABLE)), None)


def stop_target(runs: DeepResearchRuns) -> dict[str, Any] | None:
    """The run a typed "Zastav rešerši" stops: the study's newest Deep Research run that has not
    ended (running, queued or waiting); ``None`` when there is none."""
    return next(iter(runs.runs(limit=1, statuses=_UNENDED)), None)


def interpretation_target(
    targets: Mapping[str, Any] | None, target: Mapping[str, Any] | None
) -> ResearchTargetRef:
    """The target a typed Interpretation start names: ``target``, the reference of the candidate
    the person chose, only while ``targets`` (the list the server just built over the study's
    completed runs) still holds it; else the list's default. Never a position in the list, which
    a newer completed run shifts (Codex P1 on #1144), and never the person's text; a reference
    the list does not hold is
    :class:`~aia_core.application.deep_research.ResearchTargetNotFound`."""
    if target is None:
        if targets is None or targets.get("default") is None:
            raise TypedDeepResearchRefused("no_default_target")
        return card_target({"layers": [{"layer": "targets", **targets}]}, None)
    try:
        wanted = _REF.dump_python(_REF.validate_python(target), mode="json")
    except ValidationError as exc:
        raise ResearchTargetNotFound("target") from exc
    for candidate in (targets or {}).get("candidates") or ():
        if isinstance(candidate, Mapping) and candidate.get("ref") == wanted:
            return _REF.validate_python(wanted)
    raise ResearchTargetNotFound("target")


def approve_typed_deep_research(
    session: Session,
    scope: StudyContext,
    turn: LeadTurn,
    start_name: str,
    preset: str | None,
    *,
    settings: DeepResearchCardSettings | None,
    submit_design: Callable[[], Any],
    targets: Callable[[], Mapping[str, Any] | None],
    target: Mapping[str, Any] | None,
    shown_run_id: str | None,
    confirm_cost_usd: float | None,
    wallet_enabled: bool,
) -> dict[str, Any]:
    """A person's typed Deep Research start, retry or stop (lead-orchestration LO5a.3), once.

    The caller (``approve_chat_start``) holds the conversation's lock, has found no decision of
    this turn yet and re-matched its text; ``confirm_cost_usd`` is the confirmed amount it issued.
    A start follows the module's order with a ``chat_start`` row naming the run in place of the
    card's two rows: freeze once, quote, hold to the wallet, create, record, charge at the pinned
    ceiling. ``targets()`` builds the Interpretation candidates now, at approval; ``target``
    names one by its reference, else the default. ``shown_run_id``: the run a retry's or a
    stop's card named, so a newer one is never acted on unasked. A stop cancels and charges
    nothing; its row is ``stop``.
    """
    if settings is None:
        raise DeepResearchCardUnavailable("no Deep Research start is composed here")
    runs = DeepResearchRuns(session, scope, document_store=settings.document_store)
    workflows = WorkflowRepository(session, scope)
    if start_name == DEEP_RESEARCH_STOP:
        stoppable = stop_target(runs)
        if stoppable is None:
            raise TypedDeepResearchRefused("no_running_deep_research")
        run_id = str(stoppable["run_id"])
        if shown_run_id is not None and shown_run_id != run_id:
            raise DeepResearchTargetMoved("deep_research_stop_target_moved", current_run_id=run_id)
        status = runs.cancel(run_id, reason="researcher")
        workflows.record_chat_start(
            run_id,
            turn_id=turn.turn_id,
            start=start_name,
            ceiling_usd=None,
            design_revision_id=str(stoppable["metadata"]["design_revision_id"]),
            stopped=True,
        )
        return {
            "run_id": run_id,
            "design_revision_id": str(stoppable["metadata"]["design_revision_id"]),
            "status": status.value,
        }

    runs.require_start()
    if start_name in DESIGN_RESEARCH_STARTS:
        assert preset is not None
        revision = submit_design()
        start = FrozenStart(
            runs.freeze_design(
                design_revision_id=revision.revision_id,
                preset_name=preset,
                channels=CARD_CHANNELS,
            )
        )
    elif start_name in INTERPRETATION_RESEARCH_STARTS:
        assert preset is not None
        start = FrozenStart(
            runs.freeze_interpretation(
                target=interpretation_target(targets(), target),
                preset_name=preset,
                store=settings.store,
                channels=CARD_CHANNELS,
                title=INTERPRETATION_TITLE,
            )
        )
    else:
        assert start_name == DEEP_RESEARCH_RETRY
        retryable = retry_target(runs)
        if retryable is None:
            raise TypedDeepResearchRefused("no_retryable_deep_research")
        run_id = str(retryable["run_id"])
        if shown_run_id is not None and shown_run_id != run_id:
            raise DeepResearchTargetMoved("deep_research_retry_target_moved", current_run_id=run_id)
        start = runs.retry_spec(run_id, store=settings.store)

    spec = start.spec
    wallets = StudyWallets(session, scope, enabled=wallet_enabled)
    started, _quoted, ceiling = start_research(
        session,
        scope,
        runs,
        start,
        settings=settings,
        wallets=wallets,
        wallet_enabled=wallet_enabled,
        confirm_cost_usd=confirm_cost_usd,
    )
    lineage = spec.lineage
    design_revision_id = (
        lineage.design.design_revision_id
        if isinstance(lineage, InterpretationLineage)
        else lineage.design_revision_id
    )
    decision_id = workflows.record_chat_start(
        started.run_id,
        turn_id=turn.turn_id,
        start=start_name,
        ceiling_usd=ceiling,
        design_revision_id=design_revision_id,
        # A run another start had made stays that start's: nothing is charged to this card.
        reused=not started.created,
    )
    if wallet_enabled and started.created:
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
        "purpose": spec.purpose.value,
        "research_run_id": _research_run_id(spec.target),
    }
