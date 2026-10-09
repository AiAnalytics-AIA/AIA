"""The composition a Deep Research step runs on, and the meter its tool calls go through."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Final

from aia_core.application.acquisition_ladder import LadderConfig
from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.application.web_retrieval import ArchiveRetrieval, DatasetAccess, WebRetrieval
from aia_core.domain.ai_contracts import check_thinking_budget
from aia_core.domain.ai_material import MaterialApproval
from aia_core.domain.deep_research.agents import PROMPT_VERSION
from aia_core.domain.deep_research.brief import BRIEF_VERSION
from aia_core.domain.deep_research.budgets import CallKind
from aia_core.domain.deep_research.calibration import VERIFIER_CALIBRATION
from aia_core.domain.deep_research.classification import CLASSIFIER_VERSION
from aia_core.domain.deep_research.confidence import CONFIDENCE_WEIGHTS_V1, ConfidenceWeights
from aia_core.domain.deep_research.contracts import HARNESS_VERSION, Channel
from aia_core.domain.deep_research.grounding import GROUNDING_VERSION
from aia_core.domain.deep_research.investigator import INVESTIGATOR_VERSION
from aia_core.domain.deep_research.lead import LEAD_VERSION
from aia_core.domain.deep_research.merge import MERGE_RULES_VERSION
from aia_core.domain.deep_research.planning import PRESET_STATUS, TrackInputs
from aia_core.domain.deep_research.reputation import ReputationRegister
from aia_core.domain.deep_research.request_limits import (
    REQUEST_LIMITS,
    REQUEST_LIMITS_VERSION,
    KindBudget,
    ModelPrices,
    RequestLimits,
    kind_budgets,
)
from aia_core.domain.deep_research.sources import SourceTable
from aia_core.domain.deep_research.tooling import (
    TOOL_EVENT_KINDS,
    InMemoryToolLedger,
    ToolKind,
    ToolOutcome,
    ToolReservation,
    ToolRoute,
    ToolUsageEvent,
)
from aia_core.domain.deep_research.verification import VERIFICATION_RULES_VERSION
from aia_core.domain.providers import Provider
from aia_worker.executor import StepContext

from ..ai_step import ModelConcurrency

__all__ = ["DeepResearchConfig", "DeepResearchRuntime", "StepToolMeter"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# The composition
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class DeepResearchConfig:
    """The model side of a composition: policy, limits, each kind's reservation.

    ``max_output_tokens`` is the research output limit and ``context_window_tokens`` the
    model's window; ``prices`` are the route's. Each kind of request's window, output limit
    and reservation (the primary call and its one schema repair) are derived from them
    (``domain/deep_research/request_limits.py``): :meth:`budget`.
    """

    policy_version: str
    max_output_tokens: int
    context_window_tokens: int
    prices: ModelPrices
    fictional_client_ids: frozenset[str]
    provider: Provider = Provider.AWS_BEDROCK
    material_approvals: tuple[MaterialApproval, ...] = ()
    #: Extended thinking for every agent request, within ``max_output_tokens`` (so the
    #: reservation, sized on that limit, covers it); ``None`` sends no thinking.
    thinking_budget_tokens: int | None = None
    #: Web tracks run as the agent-directed investigator's turns (chunk 9) instead of
    #: the planner's queries. Off: every request, fingerprint and count is the
    #: planned mode's, exactly as before the mode existed.
    agent_directed: bool = False
    #: A lead researcher plans the agent-directed web research (chunk 11): subjects
    #: sized by effort, tasks in waves, a re-plan after each wave. Needs
    #: ``agent_directed``; off, every request and fingerprint is chunk 9's.
    lead: bool = False
    #: Tracks run in steps of their own, claimable by any worker (chunk 21): the
    #: ``investigate`` step hands out every track that would make a call and joins
    #: them. Off, one step researches every track, as before. Recorded nowhere: a
    #: track's result, fingerprint and every artifact are the same either way.
    fan_out: bool = False
    #: Each research kind's window and answer limit; ``None`` is the code's table
    #: (``request_limits.REQUEST_LIMITS``). A run's own come from the settings it pinned,
    #: through :meth:`under` (chunk 43c).
    limits: Mapping[CallKind, RequestLimits] | None = None
    _budgets: dict[CallKind, KindBudget] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.thinking_budget_tokens is not None:
            check_thinking_budget(self.thinking_budget_tokens, self.max_output_tokens)
        if self.lead and not self.agent_directed:
            raise ValueError("the lead researcher plans agent-directed tracks only")
        object.__setattr__(
            self,
            "_budgets",
            kind_budgets(
                self.prices,
                context_window_tokens=self.context_window_tokens,
                max_output_tokens=self.max_output_tokens,
                thinking_budget_tokens=self.thinking_budget_tokens,
                limits=REQUEST_LIMITS if self.limits is None else self.limits,
            ),
        )

    def under(self, limits: Mapping[CallKind, RequestLimits] | None) -> DeepResearchConfig:
        """This composition sized by ``limits`` (a run's pinned request limits); ``None``,
        or the limits it already has, is this one."""
        if limits is None or limits == (self.limits or REQUEST_LIMITS):
            return self
        return replace(self, limits=dict(limits))

    def budget(self, kind: CallKind) -> KindBudget:
        """What a request of ``kind`` may read, write and reserve in this composition."""
        return self._budgets[kind]

    @property
    def largest_reservation_usd(self) -> float:
        """The most any one request reserves: what a caller holds when not told otherwise."""
        return max(b.reservation_usd for b in self._budgets.values())


@dataclass(frozen=True, slots=True)
class DeepResearchRuntime:
    """Everything a Deep Research step may use. Built by a composition, never by a step."""

    gateway: GovernedModelGateway
    config: DeepResearchConfig
    #: ``None``: no retrieval in this composition, and every web track is blocked.
    retrieval: WebRetrieval | None
    source_table: SourceTable
    #: The journal's clock: when a tool call was made (a snapshot keeps its own time).
    clock: Callable[[], datetime] = _utcnow
    #: The reputation register the agent-directed review names publishers by (chunk 12).
    #: ``None``: publishers are hosts, nothing is traced to a primary source. The planned
    #: mode never reads it.
    register: ReputationRegister | None = None
    #: The weights an agent-directed brief's confidence is computed by (chunk 13; proposed
    #: until approved with the tiers). The planned mode never reads them.
    weights: ConfidenceWeights = CONFIDENCE_WEIGHTS_V1
    #: What the agent-directed investigator's ``ladder`` may use beyond the gate (the
    #: reputation register, Common Crawl's crawls). None: the ladder's defaults -- no
    #: register, no crawl. Read only in the agent-directed mode.
    ladder: LadderConfig | None = None
    #: Model requests in flight across every worker on the route (chunk 21): every
    #: agent request holds one slot. ``None``: unbounded here, as before fan-out.
    model_slots: ModelConcurrency | None = None
    #: Common Crawl's URL index and archived records (plan chunk 18), which the ladder's
    #: rung 9 asks for a dead or moved page. ``None``: no crawl to ask.
    archive: ArchiveRetrieval | None = None
    #: The public dataset connectors the ladder may query (chunks 14-16), each on its own
    #: route. Empty: none.
    datasets: tuple[DatasetAccess, ...] = ()
    #: The archive lookups (Wayback CDX, chunk 15) the ladder may ask with a permit.
    archives: tuple[DatasetAccess, ...] = ()

    def __post_init__(self) -> None:
        if self.retrieval is None and (self.archive or self.datasets or self.archives):
            # The gate holds them beside web retrieval and refuses a mode that differs
            # from it; without retrieval there is no gate to give them to.
            raise ValueError("dataset and archive routes need web retrieval beside them")

    def web_identity(self) -> dict[str, object] | None:
        """What a web track's result depends on: the retrieval's routes, and the dataset
        and archive routes only when this composition gives some, so a composition
        without them fingerprints exactly as before they existed (plan chunk 23a)."""
        if self.retrieval is None:
            return None
        identity: dict[str, object] = dict(self.retrieval.identity())
        if self.datasets:
            identity["datasets"] = sorted(_route_identity(d.route) for d in self.datasets)
        if self.archives:
            identity["archives"] = sorted(_route_identity(a.route) for a in self.archives)
        if self.archive is not None:
            identity["archive"] = [
                _route_identity(self.archive.index_route),
                _route_identity(self.archive.archive_route),
            ]
        return identity

    def sign_off_routes(self) -> tuple[str, ...]:
        """Every route this composition gives that needs its run's organization to have
        approved the live settings (``ToolRoute.needs_sign_off``), by route id."""
        routes: list[ToolRoute] = []
        if self.retrieval is not None:
            routes += [self.retrieval.search_route, self.retrieval.fetch_route]
        if self.archive is not None:
            routes += [self.archive.index_route, self.archive.archive_route]
        routes += [d.route for d in (*self.datasets, *self.archives)]
        return tuple(sorted({r.route_id for r in routes if r.needs_sign_off}))

    def inputs(self) -> TrackInputs:
        return TrackInputs(
            policy_version=self.config.policy_version,
            prompt_versions={Channel.INTERNAL: PROMPT_VERSION, Channel.WEB: PROMPT_VERSION},
            web_retrieval=self.web_identity(),
            thinking_budget_tokens=self.config.thinking_budget_tokens,
            investigator=self._investigator() if self.config.agent_directed else None,
        )

    def _investigator(self) -> str:
        """The investigator's version, and the ladder configuration's identity when one
        is set (without one, exactly the version: no fingerprint moves)."""
        if self.ladder is None:
            return INVESTIGATOR_VERSION
        return f"{INVESTIGATOR_VERSION}/ladder-{self.ladder.identity()}"

    def versions(self) -> dict[str, str]:
        """Every rule and prompt version a run's result depends on, recorded on the plan.

        The thinking budget only when set, so a plan recorded without it still matches.
        """
        versions = {
            "harness": HARNESS_VERSION,
            # The table the harness's request limits come from (``request_limits``).
            "request_limits": REQUEST_LIMITS_VERSION,
            "prompt": PROMPT_VERSION,
            "grounding": GROUNDING_VERSION,
            "classifier": CLASSIFIER_VERSION,
            "merge": MERGE_RULES_VERSION,
            "source_table": self.source_table.version,
            "policy": self.config.policy_version,
            "preset_status": PRESET_STATUS,
        }
        if self.config.thinking_budget_tokens is not None:
            versions["thinking_budget_tokens"] = str(self.config.thinking_budget_tokens)
        if self.config.agent_directed:
            # Only when on: the mode a run was planned in is the mode it investigates in,
            # the rules and register it is verified by, and the brief's rules and weights.
            versions["investigator"] = self._investigator()
            versions["verification"] = VERIFICATION_RULES_VERSION
            # What is known of the independent verifier's error rates (chunk 48).
            versions["verifier_calibration"] = VERIFIER_CALIBRATION
            versions["register"] = self.register.version if self.register is not None else "none"
            versions["brief"] = BRIEF_VERSION
            versions["confidence_weights"] = self.weights.version
        if self.config.lead:
            # Only when on: a run planned by the lead is investigated by its waves.
            versions["lead"] = LEAD_VERSION
        return versions


def _route_identity(route: ToolRoute) -> list[object]:
    """One route as ``WebRetrieval.identity`` names its two: id, adapter, mode, price."""
    return [route.route_id, route.adapter_id, route.retrieval_mode.value, route.price_usd_per_call]


# --------------------------------------------------------------------------- #
# The tool meter
# --------------------------------------------------------------------------- #


#: The event type ``WorkflowRepository.record_progress`` writes a progress event under.
_PROGRESS: Final = "STEP_PROGRESS"
#: ``WorkflowRepository.events`` returns at most this many events per page.
_EVENTS_PAGE: Final = 2000


def _earlier_tool_entries(context: StepContext) -> list[ToolUsageEvent]:
    """The tool entries earlier attempts of this step journaled, in journal order."""
    step = context.step
    kinds = frozenset(TOOL_EVENT_KINDS.values())
    entries: list[ToolUsageEvent] = []
    since = 0
    with context.transaction() as (_session, workflow):
        while True:
            page = workflow.events(
                step.run_id, since=since, limit=_EVENTS_PAGE, step_id=step.step_id
            )
            entries.extend(
                ToolUsageEvent.model_validate(event["payload"])
                for event in page
                if event["step_id"] == step.step_id
                and event["attempt_id"] != step.attempt_id
                and event["event_type"] == _PROGRESS
                and event["message"] in kinds
            )
            if len(page) < _EVENTS_PAGE:
                return entries
            since = int(page[-1]["event_id"])


class StepToolMeter:
    """The cost contract for tools, over a step's context. It never charges the study.

    Every entry is journaled as a progress event (``TOOL_EVENT_KINDS``) -- committed
    and lease-fenced -- and the ``DISPATCHED`` entry is journaled after a
    checkpoint and **before** the call leaves, so a cancelled, stopping or
    lease-less step stops first, and a process that dies in flight leaves the
    dispatch on record. Its ceiling is zero and it does not charge the study's
    budget, so only a free call can be reserved at all: a priced route is refused
    by the gate (``tool_metering_unavailable``) and, were it not, by the ledger.

    A step that sends tool calls builds its meter with :meth:`resuming`: recovery
    reads a model call's dispatch mark but not these entries, so the meter reads
    them itself, and a call an earlier attempt left in flight is never sent again.
    A meter built plainly (to ask the gate what could leave) refuses to dispatch.
    """

    def __init__(self, context: StepContext) -> None:
        self._context = context
        self._ledger = InMemoryToolLedger(budget_usd=0.0)
        self._resumed = False
        self._earlier: tuple[ToolUsageEvent, ...] = ()

    @classmethod
    def resuming(cls, context: StepContext, *, clock: Callable[[], datetime]) -> StepToolMeter:
        """The meter of a step that sends tool calls, holding its earlier attempts' entries.

        Everything they journaled counts again (a track's allowance spans attempts),
        and a call one left ``DISPATCHED`` -- its process died, or its lease went, in
        flight -- is closed ``UNCERTAIN`` and journaled so: :meth:`uncertain` is then
        true for its track, which ends ``INCOMPLETE`` without sending anything.
        """
        meter = cls(context)
        earlier = _earlier_tool_entries(context)
        for closure in meter._ledger.adopt(earlier, closed_at=clock()):
            meter._journal(closure)
        meter._earlier = tuple(earlier)
        meter._resumed = True
        return meter

    def dispatched_earlier(self, track_id: str) -> Counter[str]:
        """Request fingerprints an earlier attempt of this step dispatched for a track.

        What a resumed step must not send again: it was sent, and what came back is
        only known if the step recorded it.
        """
        return Counter(
            e.request_fingerprint
            for e in self._earlier
            if e.track_id == track_id and e.outcome is ToolOutcome.DISPATCHED
        )

    @property
    def charges_study_budget(self) -> bool:
        return False

    def reserve(
        self, *, tool: ToolKind, route_id: str, track_id: str, amount_usd: float
    ) -> ToolReservation:
        return self._ledger.reserve(
            tool=tool, route_id=route_id, track_id=track_id, amount_usd=amount_usd
        )

    def _journal(self, event: ToolUsageEvent) -> None:
        self._context.progress(TOOL_EVENT_KINDS[event.outcome], **event.model_dump(mode="json"))

    def dispatching(self, event: ToolUsageEvent) -> None:
        self._context.checkpoint()
        if not self._resumed:
            raise RuntimeError(
                "a meter sends a tool call only once it holds its step's journal: "
                "build it with StepToolMeter.resuming"
            )
        self._ledger.dispatching(event)
        self._journal(event)

    def outcome(self, event: ToolUsageEvent) -> None:
        self._ledger.outcome(event)
        self._journal(event)

    def committed_usd(self) -> float:
        return self._ledger.committed_usd()

    def events(self) -> tuple[ToolUsageEvent, ...]:
        return self._ledger.events()

    def uncertain(self, track_id: str) -> bool:
        """True once a call of this track may have been served with no answer on record."""
        return any(
            e.track_id == track_id and e.outcome is ToolOutcome.UNCERTAIN
            for e in self._ledger.events()
        )

    def track_usage(self, track_id: str) -> tuple[int, int, int, float]:
        """(searches sent, fetches sent, credits, cost) of one track, from the journal."""
        events = [e for e in self._ledger.events() if e.track_id == track_id]
        sent = [e for e in events if e.outcome is ToolOutcome.DISPATCHED]
        terminal = [e for e in events if e.outcome.is_terminal]
        return (
            sum(1 for e in sent if e.tool is ToolKind.WEB_SEARCH),
            sum(1 for e in sent if e.tool is ToolKind.WEB_FETCH),
            sum(e.credits for e in terminal),
            sum(
                e.ceiling_usd if e.outcome is ToolOutcome.UNCERTAIN else e.cost_usd
                for e in terminal
            ),
        )
