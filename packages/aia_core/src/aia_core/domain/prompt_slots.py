"""Every system prompt AIA sends a model: which are editable, and what is code.

One registry, so the settings page, the store and the executors agree on the
identifiers (anti-pattern A6: an id written in three places drifts). A slot is
either **wired** -- a stored edit is resolved when a job is queued and pinned to it
-- or listed with its baseline only, saying why it cannot be edited yet. Nothing
claims an edit takes effect where no composition reads it.

The baseline of a slot is the text the current code ships: for every
wired slot ``slot.assemble(slot.baseline_text)`` is byte-identical to that prompt
(a test pins it). The code-owned part (``fixed_prefix``) is added around whatever a
stored edit says, and an edit is validated against ``required_literals``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .ai_contracts import canonical_json
from .ai_respondent import PROMPT_ID as RESPONDENT_PROMPT_ID
from .ai_respondent import PROMPT_VERSION as RESPONDENT_PROMPT_VERSION
from .ai_respondent import SYSTEM_PROMPT as RESPONDENT_SYSTEM_PROMPT
from .analysis.prompt import _SYSTEM as ANALYSIS_TEMPLATE
from .analysis.prompt import PROMPT_TEMPLATE_VERSION as ANALYSIS_PROMPT_VERSION
from .deep_research.agents import AGENT_IDS as DEEP_RESEARCH_AGENT_IDS
from .deep_research.agents import AgentRole
from .deep_research.agents import prompt_for as deep_research_prompt_for
from .deep_research.agents import prompt_version_for as deep_research_prompt_version
from .prompts import PromptPin, PromptRejected, validate_prompt_text
from .research_agents import (
    FIXED_PREFIX as RESEARCH_FIXED_PREFIX,
)
from .research_agents import (
    ResearchAction,
    baseline_task,
    prompt_version_for,
)
from .research_lead import LEAD_PROMPT_ID, LEAD_PROMPT_MAX_PIN_BYTES, LEAD_PROMPT_VERSION
from .research_lead import baseline_task as lead_baseline_task

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
    #: The most bytes the prompt's pin may take in a context, as canonical JSON with its
    #: largest framing (ADR 0041: the Lead's prompt layer is 12 KB). ``None``: no bound
    #: beyond the text's characters.
    max_pin_bytes: int | None = None

    @property
    def wired(self) -> bool:
        return self.unwired_reason is None

    def assemble(self, instruction: str) -> str:
        """The system prompt sent to the model: the code's frame around the instruction."""
        return self.fixed_prefix + instruction

    def check(self, text: str) -> str:
        """``text`` as it would be stored, or :class:`PromptRejected`. Wired slots only."""
        cleaned = validate_prompt_text(text, required_literals=self.required_literals)
        self.check_pin_size(cleaned)
        return cleaned

    def pin_bytes(self, text: str) -> int:
        """The bytes ``text``'s pin takes in a context, with the largest framing a stored
        version can carry: a long version label, a declared class and a full-length author."""
        pin = PromptPin.of(
            prompt_id=self.prompt_id,
            version="stored-999999",
            origin="stored",
            text=text,
            declared_class="CLASS_C_INTERNAL",
            declared_by="x" * 64,
        )
        return len(canonical_json({"layer": "prompt", "pin": pin.model_dump(mode="json")}).encode())

    def check_pin_size(self, text: str) -> None:
        """:class:`PromptRejected` (``too_large_for_context``) when ``text``'s pin is over
        :attr:`max_pin_bytes`: refused where it is saved or activated, never at a turn. Text
        that fits in characters can be over in bytes (Czech, escaping)."""
        if self.max_pin_bytes is None:
            return
        size = self.pin_bytes(text)
        if size > self.max_pin_bytes:
            raise PromptRejected(
                f"the prompt takes {size} bytes in the Lead's context; "
                f"the limit is {self.max_pin_bytes}",
                reason="too_large_for_context",
            )

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
            baseline_version=prompt_version_for(action),
            baseline_text=baseline_task(action),
            fixed_prefix=RESEARCH_FIXED_PREFIX,
            # The build prompt names the placeholder the questionnaire contract validates.
            required_literals=("{object}",) if action is ResearchAction.BUILD else (),
        )
        for action in ResearchAction
    ] + [
        # The Research Lead (ADR 0026): the same rails, its own task wording.
        PromptSlot(
            prompt_id=LEAD_PROMPT_ID,
            family="research_agents",
            baseline_version=LEAD_PROMPT_VERSION,
            baseline_text=lead_baseline_task(),
            fixed_prefix=RESEARCH_FIXED_PREFIX,
            max_pin_bytes=LEAD_PROMPT_MAX_PIN_BYTES,
        )
    ]


def _unwired_slots() -> list[PromptSlot]:
    deep = [
        PromptSlot(
            prompt_id=DEEP_RESEARCH_AGENT_IDS[role],
            family="deep_research",
            baseline_version=deep_research_prompt_version(role),
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
