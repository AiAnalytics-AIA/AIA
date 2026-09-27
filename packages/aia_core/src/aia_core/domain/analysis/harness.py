"""The analysis harness: one turn of one module as one governed model request.

The runner (``aia_core.application.analysis``) decides *what* a turn asks -- the
module's system prompt, the evidence payload, and on a repair turn the violations of
the previous draft. This module decides *how it is asked*: which agent, capability
and output contract, how the material is classified and what it derives from, and
what the harness adds to the domain's prompt. It builds requests and never sends one;
the executor sends each through ``StepModelCaller``.

**One call per turn.** The agent's output contract is the domain's closed
:class:`~.draft.AnalysisDraft`, and it allows **no gateway schema repair**
(``schema_repair_attempts=0``). A draft that fails the schema reaches the runner as
an :class:`InvalidStructuredOutput`, which the evidence check refuses like any other
invalid draft, so the runner's own repair loop -- two repairs at most -- is the only
one. A module therefore makes at most ``1 + MAX_REPAIRS`` calls, and each of them
is a turn the runner counted; a gateway repair inside each turn would have doubled
that without anyone seeing it.

**Class C only for nothing of a client's.** The payload holds the Study's research
questions and its questionnaire wording. It is internal material only when the
operator declared the Study's client fictional *and* every respondent is simulated;
anything else is a client's design, Class A, which the approved route refuses
(ADR 0010). Lineage is the dataset's, as its artifact recorded it; there is no
default.

**The frame.** The harness tells the model what it is interpreting -- simulated
respondents, modelled numbers, which surface -- because the domain's prompt is
written for a client analysis. The frame is text, versioned and fingerprinted like
the prompt; it enforces nothing the gate does not enforce again.

Pure: builds values, no I/O.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from ..ai_contracts import (
    AgentDefinition,
    Message,
    ModelRequest,
    canonical_json,
    schema_fingerprint,
)
from ..ai_models import ModelCapability
from ..evidence import ClaimSurface
from ..fieldwork import NON_EVIDENCE_ORIGINS, DataOrigin
from ..licence import DataLineage
from ..residency import DataClass
from .draft import AnalysisDraft
from .prompt import PROMPT_TEMPLATE_VERSION

__all__ = [
    "AGENT_ID",
    "AGENT_VERSION",
    "ANALYSIS_CAPABILITY",
    "ANALYSIS_HARNESS_VERSION",
    "PROMPT_ID",
    "InvalidStructuredOutput",
    "analysis_agent",
    "analysis_request",
    "classify_analysis_material",
    "harness_frame",
    "harness_labels",
    "harness_sha256",
    "request_sha256",
]

ANALYSIS_HARNESS_VERSION: Final = "aia-analysis-harness-1"
AGENT_ID: Final = "aia.analysis.module"
AGENT_VERSION: Final = "1"
PROMPT_ID: Final = "aia.analysis.module"

#: Interpretation is long-context synthesis of evidence: the capability the design
#: agents also use. Domain code names it; the policy binds it to a model.
ANALYSIS_CAPABILITY: Final = ModelCapability.RESEARCH_REASONING

_FRAME: Final = """\
Harness ({harness}). This module is written for the {surface} surface.
The respondents behind every number are simulated ({origin}): fictional personas answered
by a model or invented by code, not people. Every number is a modelled estimate from those
simulated answers. Nothing in this module is a finding about real people or a population
fact, and no number may be presented as measured. Each evidence row names its question
(question_id) and what it counts (cell); rows listed as suppressed cannot be cited.
"""

_PREVIOUS_INVALID: Final = "(no draft: the previous answer did not match the output schema)"

_SCHEMA_REPORT: Final = """\

The output schema check of the previous answer reported:
{violations}
"""

#: A repair turn lists at most this many schema violations; the rest are counted.
_SCHEMA_VIOLATIONS_SHOWN: Final = 20


@dataclass(frozen=True, slots=True)
class InvalidStructuredOutput:
    """What a turn produced when the answer failed the output contract at the gateway.

    Not a draft: the evidence check refuses it as ``SCHEMA_INVALID`` ("the draft is not
    a JSON object"), and the next turn shows the model these violations. The call that
    produced it was made, ledgered and paid for like any other.
    """

    violations: tuple[str, ...]


def analysis_agent(*, max_output_tokens: int) -> AgentDefinition:
    """The one agent every analysis module runs as. No tools, no fallback, no schema repair."""
    return AgentDefinition(
        agent_id=AGENT_ID,
        version=AGENT_VERSION,
        capability=ANALYSIS_CAPABILITY,
        prompt_id=PROMPT_ID,
        prompt_version=PROMPT_TEMPLATE_VERSION,
        output_contract=AnalysisDraft,
        max_output_tokens=max_output_tokens,
        schema_repair_attempts=0,
    )


def harness_frame(*, origin: DataOrigin, surface: ClaimSurface) -> str:
    """What the harness adds to the module's system prompt."""
    return _FRAME.format(
        harness=ANALYSIS_HARNESS_VERSION, surface=surface.value, origin=origin.value
    )


def harness_labels(*, origin: DataOrigin, surface: ClaimSurface) -> dict[str, Any]:
    """The labels an outcome carries, so every reader knows what it is looking at."""
    return {
        "surface": surface.value,
        "data_origin": origin.value,
        "simulated_respondents": origin in NON_EVIDENCE_ORIGINS,
        "internal_only": surface is ClaimSurface.INTERNAL,
    }


def harness_sha256() -> str:
    """Identity of everything the harness adds: frame, repair wording, agent, contract."""
    agent = analysis_agent(max_output_tokens=1)
    material = "\x1f".join(
        (
            ANALYSIS_HARNESS_VERSION,
            _FRAME,
            _PREVIOUS_INVALID,
            _SCHEMA_REPORT,
            str(_SCHEMA_VIOLATIONS_SHOWN),
            agent.agent_id,
            agent.version,
            agent.capability.value,
            agent.prompt_id,
            agent.prompt_version,
            str(agent.schema_repair_attempts),
            schema_fingerprint(agent.schema or {}),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def classify_analysis_material(
    *, client_declared_fictional: bool, origin: DataOrigin | None, respondents_fictional: bool
) -> DataClass:
    """Class C only when nothing in the request is a client's; otherwise Class A.

    Unknown is never internal: an origin that is not simulated, or respondents not
    recorded as fictional, make the request client material.
    """
    internal = (
        client_declared_fictional and respondents_fictional and origin in NON_EVIDENCE_ORIGINS
    )
    return DataClass.CLASS_C_INTERNAL if internal else DataClass.CLASS_A_CLIENT_CONFIDENTIAL


def _previous_text(previous: object) -> str:
    if isinstance(previous, InvalidStructuredOutput):
        return _PREVIOUS_INVALID
    if isinstance(previous, Mapping):
        return canonical_json(dict(previous))
    return _PREVIOUS_INVALID


def _repair_text(repair: str, previous: object) -> str:
    if not isinstance(previous, InvalidStructuredOutput) or not previous.violations:
        return repair
    shown = previous.violations[:_SCHEMA_VIOLATIONS_SHOWN]
    listed = "\n".join(f"- {v}" for v in shown)
    hidden = len(previous.violations) - len(shown)
    if hidden:
        listed += f"\n- ... and {hidden} more"
    return repair + _SCHEMA_REPORT.format(violations=listed)


def analysis_request(
    *,
    system: str,
    payload: Mapping[str, Any],
    frame: str,
    repair: str | None,
    previous: object,
    policy_version: str,
    data_class: DataClass,
    lineage: DataLineage,
    max_output_tokens: int,
) -> ModelRequest:
    """One turn as a request: the payload, then (on a repair) the last answer and the fix.

    ``system`` and ``payload`` are the runner's (the domain prompt, the evidence);
    ``repair`` is its repair prompt, ``None`` on the first turn.
    """
    messages = [Message(role="user", content=canonical_json(dict(payload)))]
    if repair is not None:
        messages.append(Message(role="assistant", content=_previous_text(previous)))
        messages.append(Message(role="user", content=_repair_text(repair, previous)))
    return ModelRequest(
        agent=analysis_agent(max_output_tokens=max_output_tokens),
        policy_version=policy_version,
        data_classification=data_class,
        data_lineage=lineage,
        system=f"{system}\n{frame}",
        messages=tuple(messages),
    )


def request_sha256(request: ModelRequest) -> str:
    """Identity of what a request sends, for turn checkpoints: never of who pays for it."""
    return hashlib.sha256(
        canonical_json(
            {
                "agent": [request.agent.agent_id, request.agent.version],
                "prompt": [request.agent.prompt_id, request.agent.prompt_version],
                "schema": schema_fingerprint(request.agent.schema or {}),
                "system": request.system,
                "messages": [[m.role, m.content] for m in request.messages],
                "max_output_tokens": request.output_token_limit,
                "data_class": request.data_classification.value
                if request.data_classification
                else None,
                "lineage": sorted(request.data_lineage.datasets) if request.data_lineage else None,
            }
        ).encode("utf-8")
    ).hexdigest()
