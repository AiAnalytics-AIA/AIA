"""What one Deep Research model request of each kind may read, write and reserve.

Plan ``deep-research-request-limits.md`` (chunk 23 of ``deep-research-web-search.md``). A
request reserves before it leaves, and the reservation must cover the request's primary
call and its one schema repair at their worst. Priced at the whole context window and the
whole research output limit, a verifier batch or an investigator turn reserves what a
synthesizer reading every finding might; a run's ceiling multiplies that by hundreds. Each
kind here states its own window and answer limit instead, and its reservation is derived
from them by the same rule the worker has always applied to the whole window.

Two numbers per kind, both proposed with the presets (DR-5, plan chunk 1):

* ``window_tokens`` -- what a request of the kind must fit: the request's UTF-8 bytes (its
  prompt, message and contract, an upper bound on its input tokens) plus five times its
  output limit (the repair carries the answer back) plus 2048 for framing. ``None`` is the
  model's whole context window. A request that does not fit is refused before anything
  is reserved, as one that does not fit the window always was.
* ``answer_tokens`` -- the kind's output limit. ``None`` is the research output limit.
  Thinking is part of the output, so with thinking on its budget is added, never beyond the
  research output limit.

The reservation of a kind is ``2 x (window x the dearest input price + output limit x the
output price)``: the primary's ceiling fits it, and the repair -- the original, the answer,
the instruction, all within the window -- fits what the primary left. Nothing here is
configured: the worker and the API derive the same numbers from the same model settings.

Pure: stdlib only.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from .agents import AgentRole
from .budgets import MODEL_KINDS, CallKind

__all__ = [
    "REQUEST_LIMITS",
    "REQUEST_LIMITS_VERSION",
    "RESEARCH_KINDS",
    "KindBudget",
    "ModelPrices",
    "RequestLimits",
    "kind_budgets",
    "kind_of",
    "reservation_usd",
    "window_fits",
]

#: The table's identity, proposed until chunk 1 approves it with the presets.
REQUEST_LIMITS_VERSION: Final = "dr-request-limits-1-proposed"

#: Bytes a request may hold beyond its prompt, message, contract and the repair's answer:
#: the gateway's framing, and the output tool's instruction when thinking is on.
FRAMING_BYTES: Final = 2048

#: The answer's bytes per output token the window keeps for the repair, which sends the
#: answer back as input.
ANSWER_BYTES_PER_TOKEN: Final = 5


@dataclass(frozen=True, slots=True)
class RequestLimits:
    """One kind's window and answer limit; ``None`` is the composition's own."""

    window_tokens: int | None
    answer_tokens: int | None

    def __post_init__(self) -> None:
        for name in ("window_tokens", "answer_tokens"):
            value = getattr(self, name)
            if value is not None and value <= 0:
                raise ValueError(f"{name} is a positive number of tokens")


#: Every model kind the research agents send, by :class:`~.budgets.CallKind`. Triage is not
#: here: it runs on the light model, priced by its own entry, and is wired with its route.
RESEARCH_KINDS: Final = MODEL_KINDS - {CallKind.TRIAGE}

#: Proposed (plan ``deep-research-request-limits.md`` § Approach, with the sizes behind
#: each). The planner, the lead and the synthesizer are asked once or a few times a run
#: and read what the run made (every track, every finding): they keep the model's window
#: and the research output limit. The investigator, its internal counterpart and the
#: verifier are asked hundreds of times.
REQUEST_LIMITS: Final[Mapping[CallKind, RequestLimits]] = {
    CallKind.PLANNER: RequestLimits(window_tokens=None, answer_tokens=None),
    CallKind.LEAD: RequestLimits(window_tokens=None, answer_tokens=None),
    CallKind.SYNTHESIZER: RequestLimits(window_tokens=None, answer_tokens=None),
    CallKind.INVESTIGATOR: RequestLimits(window_tokens=144_000, answer_tokens=6_144),
    CallKind.INTERNAL_INVESTIGATOR: RequestLimits(window_tokens=None, answer_tokens=6_144),
    CallKind.VERIFIER: RequestLimits(window_tokens=112_000, answer_tokens=4_096),
}

_KINDS: Final[Mapping[AgentRole, CallKind]] = {
    AgentRole.PLANNER: CallKind.PLANNER,
    AgentRole.LEAD: CallKind.LEAD,
    AgentRole.LEAD_REPLAN: CallKind.LEAD,
    AgentRole.WEB_INVESTIGATOR: CallKind.INVESTIGATOR,
    AgentRole.INVESTIGATOR: CallKind.INVESTIGATOR,
    AgentRole.INTERNAL_INVESTIGATOR: CallKind.INTERNAL_INVESTIGATOR,
    AgentRole.VERIFIER: CallKind.VERIFIER,
    AgentRole.INDEPENDENT_VERIFIER: CallKind.VERIFIER,
    AgentRole.SYNTHESIZER: CallKind.SYNTHESIZER,
    AgentRole.BRIEF_SYNTHESIZER: CallKind.SYNTHESIZER,
}


def kind_of(role: AgentRole) -> CallKind:
    """The kind of call a request of ``role`` is: what it is counted and priced as."""
    return _KINDS[role]


@dataclass(frozen=True, slots=True)
class ModelPrices:
    """The research route's model prices, USD per million tokens; a missing cache price is
    charged at the input rate."""

    input_usd_per_mtok: float
    output_usd_per_mtok: float
    cache_read_usd_per_mtok: float | None = None
    cache_write_usd_per_mtok: float | None = None

    def __post_init__(self) -> None:
        for value in (
            self.input_usd_per_mtok,
            self.output_usd_per_mtok,
            self.cache_read_usd_per_mtok,
            self.cache_write_usd_per_mtok,
        ):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError("a price is a finite, non-negative number")

    @property
    def dearest_input_usd_per_mtok(self) -> float:
        """What an input token can cost at most, whichever cache path it takes."""
        return max(
            self.input_usd_per_mtok,
            self.cache_write_usd_per_mtok or 0.0,
            self.cache_read_usd_per_mtok or 0.0,
        )


def reservation_usd(prices: ModelPrices, *, window_tokens: int, output_tokens: int) -> float:
    """Two calls at ``window_tokens`` of input and ``output_tokens`` of output: a request's
    primary and its one repair. The rule the worker checks the research reservation by."""
    return (
        2
        * (
            window_tokens * prices.dearest_input_usd_per_mtok
            + output_tokens * prices.output_usd_per_mtok
        )
        / 1_000_000
    )


def window_fits(request_bytes: int, *, window_tokens: int, output_tokens: int) -> bool:
    """Whether a request of ``request_bytes`` fits ``window_tokens`` with its repair."""
    return request_bytes + ANSWER_BYTES_PER_TOKEN * output_tokens + FRAMING_BYTES <= window_tokens


@dataclass(frozen=True, slots=True)
class KindBudget:
    """One kind's request, as the composition sends it: window, output limit, reservation."""

    window_tokens: int
    output_tokens: int
    reservation_usd: float


def kind_budgets(
    prices: ModelPrices,
    *,
    context_window_tokens: int,
    max_output_tokens: int,
    thinking_budget_tokens: int | None = None,
    limits: Mapping[CallKind, RequestLimits] = REQUEST_LIMITS,
) -> dict[CallKind, KindBudget]:
    """Every research kind's budget under one composition's model settings.

    ``max_output_tokens`` is the research output limit, which no kind exceeds;
    ``thinking_budget_tokens`` (thinking on) is added to each kind's answer limit within it.
    """
    if context_window_tokens <= 0 or max_output_tokens <= 0:
        raise ValueError("a window and an output limit are positive numbers of tokens")
    missing = RESEARCH_KINDS - set(limits)
    if missing:
        raise ValueError(f"no request limits for {sorted(k.value for k in missing)}")
    thinking = thinking_budget_tokens or 0
    budgets: dict[CallKind, KindBudget] = {}
    for kind in sorted(RESEARCH_KINDS):
        stated = limits[kind]
        window = min(context_window_tokens, stated.window_tokens or context_window_tokens)
        output = (
            max_output_tokens
            if stated.answer_tokens is None
            else min(max_output_tokens, stated.answer_tokens + thinking)
        )
        budgets[kind] = KindBudget(
            window_tokens=window,
            output_tokens=output,
            reservation_usd=reservation_usd(prices, window_tokens=window, output_tokens=output),
        )
    return budgets
