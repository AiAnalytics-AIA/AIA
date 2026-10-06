"""The composition a Deep Research step runs on, and the meter its tool calls go through."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from aia_core.application.acquisition_ladder import LadderConfig
from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.application.web_retrieval import WebRetrieval
from aia_core.domain.ai_contracts import check_thinking_budget
from aia_core.domain.ai_material import MaterialApproval
from aia_core.domain.deep_research.agents import PROMPT_VERSION
from aia_core.domain.deep_research.classification import CLASSIFIER_VERSION
from aia_core.domain.deep_research.contracts import HARNESS_VERSION, Channel
from aia_core.domain.deep_research.grounding import GROUNDING_VERSION
from aia_core.domain.deep_research.investigator import INVESTIGATOR_VERSION
from aia_core.domain.deep_research.merge import MERGE_RULES_VERSION
from aia_core.domain.deep_research.planning import PRESET_STATUS, TrackInputs
from aia_core.domain.deep_research.sources import SourceTable
from aia_core.domain.deep_research.tooling import (
    TOOL_EVENT_KINDS,
    InMemoryToolLedger,
    ToolKind,
    ToolOutcome,
    ToolReservation,
    ToolUsageEvent,
)
from aia_core.domain.providers import Provider
from aia_worker.executor import StepContext

__all__ = ["DeepResearchConfig", "DeepResearchRuntime", "StepToolMeter"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# The composition
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class DeepResearchConfig:
    """The model side of a composition: policy, limits, the reservation per request."""

    policy_version: str
    max_output_tokens: int
    context_window_tokens: int
    #: Held per logical request; covers the primary call and one schema repair.
    reservation_usd: float
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

    def __post_init__(self) -> None:
        if self.thinking_budget_tokens is not None:
            check_thinking_budget(self.thinking_budget_tokens, self.max_output_tokens)


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
    #: What the agent-directed investigator's ``ladder`` may use beyond the gate (the
    #: reputation register, Common Crawl's crawls). None: the ladder's defaults -- no
    #: register, no crawl. Read only in the agent-directed mode.
    ladder: LadderConfig | None = None

    def inputs(self) -> TrackInputs:
        return TrackInputs(
            policy_version=self.config.policy_version,
            prompt_versions={Channel.INTERNAL: PROMPT_VERSION, Channel.WEB: PROMPT_VERSION},
            web_retrieval=self.retrieval.identity() if self.retrieval is not None else None,
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
            # Only when on: the mode a run was planned in is the mode it investigates in.
            versions["investigator"] = self._investigator()
        return versions


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
            page = workflow.events(step.run_id, since=since, limit=_EVENTS_PAGE)
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
