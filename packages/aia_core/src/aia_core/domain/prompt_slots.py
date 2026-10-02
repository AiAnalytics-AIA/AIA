"""Every system prompt AIA sends a model: which are editable, and what is code.

One registry, so the settings page, the store and the executors agree on the
identifiers (anti-pattern A6: an id written in three places drifts). A slot is
either **wired** -- a stored edit is resolved when a job is queued and pinned to it
-- or listed with its baseline only, saying why it cannot be edited yet. Nothing
claims an edit takes effect where no composition reads it.

The baseline of a slot is the text the code has always sent, unchanged: for every
wired slot ``slot.assemble(slot.baseline_text)`` is byte-identical to that prompt
(a test pins it). The code-owned part (``fixed_prefix``) is added around whatever a
stored edit says, and an edit is validated against ``required_literals``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .ai_respondent import PROMPT_ID as RESPONDENT_PROMPT_ID
from .ai_respondent import PROMPT_VERSION as RESPONDENT_PROMPT_VERSION
from .ai_respondent import SYSTEM_PROMPT as RESPONDENT_SYSTEM_PROMPT
from .analysis.prompt import _SYSTEM as ANALYSIS_TEMPLATE
from .analysis.prompt import PROMPT_TEMPLATE_VERSION as ANALYSIS_PROMPT_VERSION
from .deep_research.agents import AGENT_IDS as DEEP_RESEARCH_AGENT_IDS
from .deep_research.agents import PROMPT_VERSION as DEEP_RESEARCH_PROMPT_VERSION
from .deep_research.agents import AgentRole
from .deep_research.agents import prompt_for as deep_research_prompt_for
from .prompts import PromptPin, validate_prompt_text
from .research_agents import (
    BASELINE_PROMPT_VERSION as RESEARCH_PROMPT_VERSION,
)
from .research_agents import (
    FIXED_PREFIX as RESEARCH_FIXED_PREFIX,
)
from .research_agents import (
    ResearchAction,
    baseline_task,
)

__all__ = [
    "PromptSlot",
    "get_slot",
    "slots",
    "wired_prompt_ids",
]

#: Why a slot is listed but cannot be edited yet. Stable words; the page words them.
NOT_RUN_BY_ANY_COMPOSITION: Final = "not_run_by_any_composition"
FEEDS_A_REUSE_FINGERPRINT: Final = "feeds_a_reuse_fingerprint"
RENDERED_FROM_CODE: Final = "rendered_from_code"


@dataclass(frozen=True, slots=True)
class PromptSlot:
    """One prompt's identity, its code-owned frame and its editable baseline."""

    prompt_id: str
    #: Which family of steps sends it (the page groups slots by this).
    family: str
    baseline_version: str
    #: The wording this code ships. For an unwired slot, shown and never edited.
    baseline_text: str
    #: Code-owned text placed before the editable instruction.
    fixed_prefix: str = ""
    #: Literals an edit must keep (for example a placeholder the output contract names).
    required_literals: tuple[str, ...] = ()
    #: ``None`` when wired; otherwise the stable reason no edit can take effect yet.
    unwired_reason: str | None = None

    @property
    def wired(self) -> bool:
        return self.unwired_reason is None

    def assemble(self, instruction: str) -> str:
        """The system prompt sent to the model: the code's frame around the instruction."""
        return self.fixed_prefix + instruction

    def check(self, text: str) -> str:
        """``text`` as it would be stored, or :class:`PromptRejected`. Wired slots only."""
        return validate_prompt_text(text, required_literals=self.required_literals)

    def baseline_pin(self) -> PromptPin:
        return PromptPin.of(
            prompt_id=self.prompt_id,
            version=self.baseline_version,
            origin="baseline",
            text=self.baseline_text,
        )


def _research_slots() -> list[PromptSlot]:
    return [
        PromptSlot(
            prompt_id=f"aia.research.{action.value}",
            family="research_agents",
            baseline_version=RESEARCH_PROMPT_VERSION,
            baseline_text=baseline_task(action),
            fixed_prefix=RESEARCH_FIXED_PREFIX,
            # The build prompt names the placeholder the questionnaire contract validates.
            required_literals=("{object}",) if action is ResearchAction.BUILD else (),
        )
        for action in ResearchAction
    ]


def _unwired_slots() -> list[PromptSlot]:
    deep = [
        PromptSlot(
            prompt_id=DEEP_RESEARCH_AGENT_IDS[role],
            family="deep_research",
            baseline_version=DEEP_RESEARCH_PROMPT_VERSION,
            baseline_text=deep_research_prompt_for(role),
            unwired_reason=NOT_RUN_BY_ANY_COMPOSITION,
        )
        for role in AgentRole
    ]
    return [
        PromptSlot(
            prompt_id=RESPONDENT_PROMPT_ID,
            family="respondent",
            baseline_version=RESPONDENT_PROMPT_VERSION,
            baseline_text=RESPONDENT_SYSTEM_PROMPT,
            unwired_reason=FEEDS_A_REUSE_FINGERPRINT,
        ),
        PromptSlot(
            prompt_id="aia.analysis.module",
            family="analysis",
            baseline_version=ANALYSIS_PROMPT_VERSION,
            baseline_text=ANALYSIS_TEMPLATE,
            unwired_reason=NOT_RUN_BY_ANY_COMPOSITION,
        ),
        *deep,
    ]


_SLOTS: Final[tuple[PromptSlot, ...]] = tuple(_research_slots() + _unwired_slots())
_BY_ID: Final[dict[str, PromptSlot]] = {s.prompt_id: s for s in _SLOTS}
if len(_BY_ID) != len(_SLOTS):  # pragma: no cover - a duplicate id is a coding error
    raise RuntimeError("duplicate prompt id in the slot registry")


def slots() -> tuple[PromptSlot, ...]:
    """Every prompt, in the order the page shows them."""
    return _SLOTS


def get_slot(prompt_id: str) -> PromptSlot | None:
    return _BY_ID.get(prompt_id)


def wired_prompt_ids() -> frozenset[str]:
    return frozenset(s.prompt_id for s in _SLOTS if s.wired)
