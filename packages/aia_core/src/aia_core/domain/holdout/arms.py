"""The validation's model arms: what each respondent is shown (panel-grounded-respondents 7a, 7c).

Every arm asks the same sample the same blocks under the same prompt, response process and
model binding. Only the profile text differs, and in every arm the block's exclusion
(:mod:`.leakage`) is applied before anything is written:

======  =========================================================================
Arm     The profile shown with a block
======  =========================================================================
``A``   none: the question only (an empty profile; the request's frame is unchanged)
``B``   demographics: the base lines alone (sex, age, education, region)
``C``   the core profile: base, socio-economic and household lines, no catalog signal
``D``   the production persona (``PanelPersonas.profile``): the system validated
``S``   D's profiles deranged: each respondent shown another sampled respondent's
======  =========================================================================

What stays the respondent's own in every arm: the facts code answers, and the response styles
code draws with (``respondent_behavior``), since the response process is part of the system
and does not change between arms. ``S`` therefore isolates the profile text: the person's own
process with somebody else's description.

``D`` with no exclusion is today's ``PanelPersonas.plan``, byte for byte; a test holds it so.

A confirmation run asks the preregistered blocks (``blocks``), not the questionnaire's own split:
``split_blocks`` fills each request to eight items, so two short domain blocks would become one
request whose exclusion is neither block's. A plan whose items code would answer as facts is
refused here too, since a held-out item answered by code would score the code.
Nothing on a client run's path takes an arm or an exclusion: ``panel_plans`` is untouched, and
only a validation run builds plans here.

Pure: stdlib only.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Final

from ..ai_respondent import Block, RespondentPlan, plan_respondent
from ..panel_persona import PanelPersonas
from ..persona_profile import persona_text
from ..persona_signals import grounded_text
from ..persona_topics import block_topics
from ..population.audience import Typed
from ..research_design import ResearchSpecification

__all__ = [
    "BASE_COLUMNS",
    "Arm",
    "ArmRefused",
    "arm_plans",
    "derangement",
]

#: The demographic base lines (``persona_profile.profile_lines``' first four).
BASE_COLUMNS: Final = ("pohlavi", "vek", "vzdelani", "kraj")


class Arm(StrEnum):
    """A model arm of the validation (7a)."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    S = "S"


class ArmRefused(ValueError):
    """The arm cannot be built as asked. ``reason`` names why."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


def derangement(ids: Sequence[str], seed: int) -> dict[str, str]:
    """A seeded permutation of ``ids`` with no fixed point: whose profile each one is shown.

    Sattolo's algorithm over the sorted ids yields one cycle through all of them, so nobody is
    shown their own. Fewer than two respondents cannot be deranged.
    """
    ordered = sorted(ids)
    if len(ordered) < 2:
        raise ArmRefused("a shuffled arm needs at least two respondents", reason="arm_too_few")
    target = list(ordered)
    rng = random.Random(f"derangement:{seed}")
    for i in range(len(target) - 1, 0, -1):
        j = rng.randrange(i)
        target[i], target[j] = target[j], target[i]
    return dict(zip(ordered, target, strict=True))


def _excluded(block: Block, exclusions: Mapping[str, frozenset[str]]) -> frozenset[str]:
    out: frozenset[str] = frozenset()
    for item in block.items:
        out |= exclusions.get(item.item_id, frozenset())
    return out


def _profile(
    personas: PanelPersonas, persona_id: str, arm: Arm, block: Block, excluded: frozenset[str]
) -> str:
    if arm is Arm.A:
        return ""
    row: dict[str, Typed] = {
        k: v for k, v in personas.rows[persona_id].items() if k not in excluded
    }
    topics = block_topics([(item.text, item.labels) for item in block.items])
    if arm is Arm.B:
        return persona_text({k: row[k] for k in BASE_COLUMNS if k in row}, topics, "")
    if arm is Arm.C:
        return persona_text(row, topics, "")
    catalog = tuple(s for s in personas.catalog if s.column not in excluded)
    return persona_text(row, topics, grounded_text(row, topics, catalog, personas.labels))


def _reblocked(base: RespondentPlan, blocks: Sequence[Sequence[str]]) -> tuple[Block, ...]:
    if base.facts:
        raise ArmRefused(
            f"code answers {sorted(base.facts)} as facts; a held-out item is the respondent's",
            reason="arm_item_is_a_fact",
        )
    items = {item.item_id: item for block in base.blocks for item in block.items}
    wanted = [item for block in blocks for item in block]
    if sorted(wanted) != sorted(items) or len(set(wanted)) != len(wanted):
        raise ArmRefused(
            "the blocks are not exactly the questionnaire's items", reason="arm_blocks_mismatch"
        )
    return tuple(Block(index, tuple(items[i] for i in block)) for index, block in enumerate(blocks))


def arm_plans(
    personas: PanelPersonas,
    spec: ResearchSpecification,
    arm: Arm,
    *,
    exclusions: Mapping[str, frozenset[str]],
    shuffle_seed: int | None = None,
    blocks: Sequence[Sequence[str]] | None = None,
) -> tuple[RespondentPlan, ...]:
    """Every respondent's plan under ``arm``. ``exclusions`` maps an item id to the fields its
    respondents are not given (a block's is the union over its items); ``S`` needs a seed.
    ``blocks``, when given, are the requests asked, each a list of item ids, in order."""
    if arm is Arm.S and shuffle_seed is None:
        raise ArmRefused("the shuffled arm needs its seed", reason="arm_seed_missing")
    shown = (
        derangement([p.persona_id for p in personas.personas], shuffle_seed)  # type: ignore[arg-type]
        if arm is Arm.S
        else None
    )
    plans = []
    for persona in personas.personas:
        base = plan_respondent(spec, persona)
        asked = base.blocks if blocks is None else _reblocked(base, blocks)
        source = shown[persona.persona_id] if shown is not None else persona.persona_id
        profile_arm = Arm.D if arm is Arm.S else arm
        plans.append(
            RespondentPlan(
                persona=persona,
                facts=base.facts,
                blocks=asked,
                profiles=tuple(
                    _profile(personas, source, profile_arm, block, _excluded(block, exclusions))
                    for block in asked
                ),
            )
        )
    return tuple(plans)
