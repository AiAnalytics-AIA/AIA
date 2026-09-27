"""The composition a Deep Research step runs on, and the meter its tool calls go through."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.application.web_retrieval import WebRetrieval
from aia_core.domain.deep_research.agents import PROMPT_VERSION
from aia_core.domain.deep_research.classification import CLASSIFIER_VERSION
from aia_core.domain.deep_research.contracts import HARNESS_VERSION, Channel
from aia_core.domain.deep_research.grounding import GROUNDING_VERSION
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

    def inputs(self) -> TrackInputs:
        return TrackInputs(
            policy_version=self.config.policy_version,
            prompt_versions={Channel.INTERNAL: PROMPT_VERSION, Channel.WEB: PROMPT_VERSION},
            web_retrieval=self.retrieval.identity() if self.retrieval is not None else None,
        )

    def versions(self) -> dict[str, str]:
        """Every rule and prompt version a run's result depends on, recorded on the plan."""
        return {
            "harness": HARNESS_VERSION,
            "prompt": PROMPT_VERSION,
            "grounding": GROUNDING_VERSION,
            "classifier": CLASSIFIER_VERSION,
            "merge": MERGE_RULES_VERSION,
            "source_table": self.source_table.version,
            "policy": self.config.policy_version,
            "preset_status": PRESET_STATUS,
        }


# --------------------------------------------------------------------------- #
# The tool meter
# --------------------------------------------------------------------------- #


class StepToolMeter:
    """The cost contract for tools, over a step's context. It never charges the study.

    Every entry is journaled as a progress event (``TOOL_EVENT_KINDS``) -- committed
    and lease-fenced -- and the ``DISPATCHED`` entry is journaled after a
    checkpoint and **before** the call leaves, so a cancelled, stopping or
    lease-less step stops first, and a process that dies in flight leaves the
    dispatch on record. Its ceiling is zero and it does not charge the study's
    budget, so only a free call can be reserved at all: a priced route is refused
    by the gate (``tool_metering_unavailable``) and, were it not, by the ledger.
    """

    def __init__(self, context: StepContext) -> None:
        self._context = context
        self._ledger = InMemoryToolLedger(budget_usd=0.0)

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
        self._ledger.dispatching(event)
        self._journal(event)

    def outcome(self, event: ToolUsageEvent) -> None:
        self._ledger.outcome(event)
        self._journal(event)

    def committed_usd(self) -> float:
        return self._ledger.committed_usd()

    def events(self) -> tuple[ToolUsageEvent, ...]:
        return self._ledger.events()

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
