"""The Research Lead ("Vedoucí výzkumu"): its closed output, its frozen context, its files.

ADR 0026. A Lead turn is a durable worker step; this module is its pure half:

* **The output is closed** (:class:`LeadOutput`). A reply in Czech, visual commands
  (``view``), proposed edits a person accepts one by one (``edits``), at most one prepared
  request for paid work a person approves (``request``), follow-up suggestions and the
  Lead's own file changes (``self_update``). No tools; nothing in it acts by itself.
* **A reply writes no number the context does not hold.** :func:`lead_contract` is the
  output contract the gateway validates against: the same model with a validator that
  refuses a reply naming any number absent from the frozen context and the prompt, so the
  gateway's one schema repair can correct it. The prompt states the rule; this enforces it.
* **Edits are grounded in the working content** (:func:`ground_edits`): an edit naming a
  question, section or list item the content does not hold is dropped and named. The edits
  themselves, their rules and their apply are the working copy's one vocabulary
  (``domain/edit_ops.py``, ADR 0029); this module re-exports the names it always offered.
* **The context is frozen at enqueue, in a fixed order, and bounded**
  (:func:`freeze_context`): 96 KB of canonical JSON; the oldest turns go first, then the
  turn is refused (:class:`LeadContextTooLarge`), never cut silently.
* **Each researcher has their own Lead** (OpenClaw-style files): a name, a SOUL (its
  personality and working style), a USER file (what it knows of how this researcher works)
  and notes. The Lead changes them only through ``self_update``, when the researcher asks
  in chat; a ``forget`` names only notes this turn was shown (:func:`ground_self_update`).
* **Its data class** follows the owner's rules of 2026-10-19 (:func:`context_classification`,
  ``material_rules``): the design, the study's names and the researcher's messages are Class
  B, the Lead's own files and personal notes Class C, approved knowledge and client-scoped
  notes Class A; an operator's classification of exact bytes can only raise a part; the most
  restrictive wins, and a part no rule covers (an undeclared prompt edit, an earlier reply of
  unknown class) refuses dispatch.

No I/O: stdlib and Pydantic only.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Final, Literal, get_args
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ai_contracts import AgentDefinition, Message, ModelRequest, canonical_json
from .ai_material import MaterialApproval, most_restrictive_material
from .ai_models import ModelCapability
from .edit_ops import (
    TEXT_EDIT_OPS,
    TEXT_ONLY_FIELDS,
    TEXT_ONLY_LISTS,
    EditOp,
    ListAdd,
    ListRemove,
    ListReplace,
    PlanList,
    QuestionAdd,
    QuestionEdit,
    QuestionRemove,
    QuestionType,
    Refused,
    SetN,
    SetText,
    TextField,
    apply_edit,
    is_text_edit,
    question_add_problem,
    refusal,
)
from .licence import DataLineage
from .material_rules import MaterialRule, classify_by_rule, rule_class
from .prompts import PromptPin
from .research_agents import (
    FIXED_PREFIX,
    ResearchAction,
    prompt_class_source,
    prompt_data_class,
)
from .research_design import SampleSizeLimits
from .residency import DataClass

__all__ = [
    "ARTIFACT_TYPE",
    "CONTEXT_MAX_BYTES",
    "DEFAULT_LEAD_NAME",
    "DEFAULT_SOUL",
    "FOCUS_ID",
    "LEAD_AGENT_ID",
    "LEAD_HARNESS_VERSION",
    "LEAD_PROMPT_ID",
    "LEAD_PROMPT_VERSION",
    "MESSAGE_MAX_CHARS",
    "SELF_UPDATE_FILES",
    "STAGES",
    "TEXT_EDIT_OPS",
    "TEXT_ONLY_FIELDS",
    "TEXT_ONLY_LISTS",
    "Dropped",
    "EditOp",
    "LeadContextTooLarge",
    "LeadNote",
    "LeadOutput",
    "LeadTurn",
    "ListAdd",
    "ListRemove",
    "ListReplace",
    "PlanList",
    "QuestionAdd",
    "QuestionEdit",
    "QuestionRemove",
    "QuestionType",
    "Refused",
    "ResearcherLead",
    "SelfUpdate",
    "SelfUpdateApplied",
    "SetN",
    "SetText",
    "Stage",
    "TextField",
    "apply_edit",
    "baseline_task",
    "context_classification",
    "context_data_class",
    "context_sha256",
    "freeze_context",
    "frozen_sample_size",
    "ground_edits",
    "ground_self_update",
    "is_text_edit",
    "layer",
    "lead_contract",
    "lead_prompt",
    "lead_request",
    "lead_request_window_tokens",
    "number_tokens",
    "question_add_problem",
    "readiness_layer",
    "self_update_base",
    "split_self_update",
    "stale_files",
    "unreadable_numbers",
    "waiting_self_update",
]

LEAD_PROMPT_ID: Final = "aia.research.lead"
LEAD_AGENT_ID: Final = LEAD_PROMPT_ID
LEAD_PROMPT_VERSION: Final = "1"
#: 2: the frozen design layer carries the readiness limits in force, and ``set_n`` is held to
#: them rather than to a range of its own (plan ``run-qc-and-checkpoint`` RQC9). A turn queued
#: under 1 has no limits to be grounded against, so the executor refuses it by name.
LEAD_HARNESS_VERSION: Final = "aia-research-lead-2"
#: A turn's stored output. Served only by the Lead's own routes, never the generic ones.
ARTIFACT_TYPE: Final = "research_lead_turn"

#: The frozen context's bound, canonical JSON (ADR 0026 decision 2).
CONTEXT_MAX_BYTES: Final = 96 * 1024
#: A person's message, and the Lead's reply.
MESSAGE_MAX_CHARS: Final = 4000
REPLY_MAX_CHARS: Final = 4000
#: The turns before this one the Lead is shown verbatim.
HISTORY_TURNS: Final = 12
#: The Lead's files and notes.
NAME_MAX_CHARS: Final = 40
SOUL_MAX_CHARS: Final = 2000
USER_MAX_CHARS: Final = 2000
NOTE_MAX_CHARS: Final = 300
#: The newest active notes a turn is shown, and their byte bound.
NOTES_IN_CONTEXT: Final = 40
NOTES_MAX_BYTES: Final = 16_000

DEFAULT_LEAD_NAME: Final = "Vedoucí výzkumu"
#: The SOUL a Lead is hatched with: the code's wording, Class C like a baseline prompt.
DEFAULT_SOUL: Final = """# Vedoucí výzkumu

- Jsem věcný a stručný parťák pro výzkum.
- Nejdřív řeknu hlavní věc, pak její důsledek a další krok.
- Rozlišuji doložené, domněnku a návrh.
- Ptám se jen na to, co rozhodnutí opravdu změní.
"""
DEFAULT_USER: Final = ""

Stage = Literal[
    "brief",
    "design",
    "questionnaire",
    "audience",
    "dimensions",
    "sample",
    "fieldwork",
    "results",
    "sociomap",
    "analysis",
    "report",
]
STAGES: Final[tuple[str, ...]] = get_args(Stage)


#: A ``data-aia`` id the interface focuses: ``question:q3``, ``brief:goal``.
_TARGET = r"^[a-z_]+:[A-Za-z0-9_.\-]+$"
#: What a person's message may say it is about: an element of a stage screen, in the forms the
#: web's targetOfElement produces (``question:<id>``, ``section:<id>``, ``brief:<field>``,
#: ``plan:<part>``). The id reaches the model unclassified, so it may be an identifier and
#: nothing else; the free text beside it is the label, which is classified.
FOCUS_ID: Final = re.compile(r"^(?:question|section|brief|plan):[A-Za-z0-9_.\-]{1,80}$")
_MEMORY_ID = r"^LMM-[0-9a-f]{1,32}$"


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Why = Annotated[str, Field(min_length=1, max_length=500)]
ItemText = Annotated[str, Field(min_length=1, max_length=1500)]
Option = Annotated[str, Field(min_length=1, max_length=300)]


# --------------------------------------------------------------------------- view


class OpenStage(Closed):
    op: Literal["open_stage"]
    stage: Stage


class FocusItem(Closed):
    op: Literal["focus"]
    target: str = Field(min_length=3, max_length=200, pattern=_TARGET)


ViewOp = Annotated[OpenStage | FocusItem, Field(discriminator="op")]


# --------------------------------------------------------------------------- requests


class AgentJobRequest(Closed):
    """A specialist job, prepared; a person approves it (ADR 0026 decision 7)."""

    kind: Literal["agent_job"]
    action: ResearchAction
    why: Why


class ResearchRunRequest(Closed):
    kind: Literal["research_run"]
    why: Why


class DesignResearchRequest(Closed):
    kind: Literal["design_research"]
    why: Why


class InterpretationResearchRequest(Closed):
    kind: Literal["interpretation_research"]
    why: Why


JobRequest = Annotated[
    AgentJobRequest | ResearchRunRequest | DesignResearchRequest | InterpretationResearchRequest,
    Field(discriminator="kind"),
]


# --------------------------------------------------------------------------- the Lead's files


class RememberNote(Closed):
    scope: Literal["personal", "client"]
    text: str = Field(min_length=1, max_length=NOTE_MAX_CHARS)


class SelfUpdate(Closed):
    """The Lead's change to its own files, asked for in chat. ``soul`` and ``user`` replace
    the whole file; ``forget`` names notes this turn was shown."""

    name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX_CHARS)
    soul: str | None = Field(default=None, max_length=SOUL_MAX_CHARS)
    user: str | None = Field(default=None, max_length=USER_MAX_CHARS)
    remember: list[RememberNote] = Field(default_factory=list, max_length=2)
    forget: list[Annotated[str, Field(pattern=_MEMORY_ID)]] = Field(
        default_factory=list, max_length=5
    )

    @property
    def is_empty(self) -> bool:
        return (
            self.name is None
            and self.soul is None
            and self.user is None
            and not self.remember
            and not self.forget
        )


class LeadOutput(Closed):
    """What one Lead turn returns. Nothing in it changes anything by itself."""

    reply: str = Field(min_length=1, max_length=REPLY_MAX_CHARS)
    view: list[ViewOp] = Field(default_factory=list, max_length=3)
    edits: list[EditOp] = Field(default_factory=list, max_length=12)
    request: JobRequest | None = None
    follow: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        default_factory=list, max_length=3
    )
    self_update: SelfUpdate | None = None


# --------------------------------------------------------------------------- numbers

#: A number as a person writes one: digits, thousands grouped by a space (also NBSP or a
#: narrow NBSP), a decimal comma or point. Not inside a word: ``q3`` is an id, not a three.
#: A leading minus (``-`` or U+2212) is the number's sign only where it does not join two
#: words or numbers: in ``2026-10-19`` it is a hyphen, so ``10`` and ``19`` stay unsigned.
#: A number starts where no word, digit or decimal mark precedes it, so ``Q1``, ``B2`` or
#: ``goal2`` hold none: those digits belong to an identifier. It ends where no digit follows,
#: whatever does: ``7x``, ``3krát`` and ``18letých`` write 7, 3 and 18 (the review of
#: baac33d5: a number glued to its word passed the guard unread).
_NUMBER = re.compile(
    r"(?P<sign>(?<![\w.,])[-\u2212])?"
    r"(?<![\w.,])(?P<num>\d+(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?)(?!\d)"
)
#: A number this guard cannot read exactly: one with an exponent (``1e6``, ``2,5E-3``).
#: ``_NUMBER`` would read only its mantissa; a reply writing one is refused, never read as
#: some other number (Codex on #484).
_EXPONENT = re.compile(r"(?<![\w.,])[-\u2212+]?\d+(?:[.,]\d+)?[eE][-+\u2212]?\d+(?![\w])")


def _canonical_number(sign: str | None, token: str) -> str | None:
    plain = re.sub(r"[ \u00a0\u202f]", "", token).replace(",", ".")
    try:
        value = Decimal(plain)
    except InvalidOperation:  # pragma: no cover - the pattern admits only numbers
        return None
    text = format(value.normalize(), "f")
    text = text if "." not in text else text.rstrip("0").rstrip(".")
    # A sign is part of the number: -5 is not 5. Zero has none to keep.
    return f"-{text}" if sign and value != 0 else text


def number_tokens(text: str) -> frozenset[str]:
    """Every number written in ``text``, canonical and signed: ``12,50`` and ``12.5`` are one
    number, ``-5`` (or ``\u22125``) another than ``5``."""
    found = (_canonical_number(m.group("sign"), m.group("num")) for m in _NUMBER.finditer(text))
    return frozenset(n for n in found if n is not None)


def unreadable_numbers(text: str) -> list[str]:
    """The numbers in ``text`` written in a form the guard cannot read exactly (exponents)."""
    return [m.group(0) for m in _EXPONENT.finditer(text)]


def lead_contract(allowed_text: str) -> type[LeadOutput]:
    """The output contract a turn is validated against: :class:`LeadOutput`, refusing a
    reply that writes a number ``allowed_text`` (the frozen context and the prompt) does not.

    A validation error, so the gateway's one schema repair tells the model which numbers.
    """
    allowed = number_tokens(allowed_text)

    class CheckedLeadOutput(LeadOutput):
        model_config = ConfigDict(extra="forbid", frozen=True, title="LeadOutput")

        @model_validator(mode="after")
        def _numbers_from_the_context(self) -> CheckedLeadOutput:
            unreadable = unreadable_numbers(self.reply)
            if unreadable:
                raise ValueError(
                    "reply writes numbers in a form that cannot be checked: "
                    + ", ".join(unreadable[:10])
                    + "; write a number out in digits as the context holds it, or none"
                )
            unknown = sorted(number_tokens(self.reply) - allowed)
            if unknown:
                raise ValueError(
                    "reply writes numbers that are not in the context: "
                    + ", ".join(unknown[:10])
                    + "; write only numbers the context holds, or none"
                )
            return self

    return CheckedLeadOutput


# --------------------------------------------------------------------------- grounding


class Dropped(Closed):
    """An edit or file change left out, and why (a stable word)."""

    index: int
    op: str
    reason: str


def ground_edits(
    output: LeadOutput,
    content: Mapping[str, Any],
    analysis: Mapping[str, Any] | None = None,
    *,
    sample_size: SampleSizeLimits | None,
) -> tuple[LeadOutput, list[Dropped]]:
    """``output`` with only the edits the working content can take, and the rest named.

    A question or section id must be one of a questions section in ``content["sections"]``;
    a list item's ``old`` must be in its plan list (the working ``analysis`` first, else
    ``content["research_plan"]``), compared whitespace-collapsed and casefolded; a
    ``list_add`` already present is dropped too (``edit_ops.refusal``). A ``set_n`` must be a
    valid n under ``sample_size``, the readiness limits the turn was frozen with; with no limits
    known it is dropped (``sample_size_limits_unknown``), never presumed valid. Nothing else is
    judged here: a person accepts each edit that is left.
    """
    kept: list[Any] = []
    dropped: list[Dropped] = []
    for i, edit in enumerate(output.edits):
        # The vocabulary's own rule, the one apply_edit refuses with (domain/edit_ops.py).
        reason = refusal(edit, content, analysis, sample_size=sample_size)
        if reason is None:
            kept.append(edit)
        else:
            dropped.append(Dropped(index=i, op=edit.op, reason=reason))
    return output.model_copy(update={"edits": kept}), dropped


def readiness_layer(sample_size: SampleSizeLimits, methodology_version: str) -> dict[str, Any]:
    """The readiness limits in force as the design layer carries them (``design.readiness``):
    what a turn's ``set_n`` is held to, and what the Lead may say n can be."""
    return {
        "methodology_version": methodology_version,
        "sample_size": {"min": sample_size.min, "max": sample_size.max},
    }


def frozen_sample_size(design: Mapping[str, Any]) -> SampleSizeLimits | None:
    """The sample-size limits a turn was frozen with (:func:`readiness_layer`), or ``None``
    when the design layer holds none it can read."""
    readiness = design.get("readiness")
    if not isinstance(readiness, Mapping):
        return None
    try:
        return SampleSizeLimits.model_validate(readiness.get("sample_size"))
    except ValueError:
        return None


def ground_self_update(
    update: SelfUpdate | None, shown_memory_ids: Sequence[str]
) -> tuple[SelfUpdate | None, list[Dropped]]:
    """``update`` with only the forgets that name a note this turn was shown.

    The context holds only the researcher's own active notes that apply to this study, so a
    note of another researcher, of another client or already forgotten cannot be named.
    """
    if update is None:
        return None, []
    shown = set(shown_memory_ids)
    kept: list[str] = []
    dropped: list[Dropped] = []
    for i, memory_id in enumerate(update.forget):
        if memory_id in shown and memory_id not in kept:
            kept.append(memory_id)
        else:
            dropped.append(Dropped(index=i, op="forget", reason="unknown_memory"))
    grounded = update.model_copy(update={"forget": kept})
    return (None if grounded.is_empty else grounded), dropped


def split_self_update(
    update: SelfUpdate | None, shown_notes: Sequence[Mapping[str, Any]]
) -> tuple[SelfUpdate | None, SelfUpdate | None]:
    """``update`` as what applies now and what waits for the researcher's yes.

    The model's choice of scope is not an isolation boundary (Codex on #484): a "personal"
    note, or a SOUL, USER or name change, loads into every study of every client, so a client
    fact written there by mistake or by injection would leave its client. Only what stays
    inside the turn's own client applies at once: client notes (bound to the turn's client by
    the repository) and forgetting a client note of this client. Forgetting a personal note
    changes every client's studies too, so it waits like the rest; so does a forget whose note
    ``shown_notes`` (the notes the turn was shown, by ``memory_id`` and ``scope``) does not
    name as a client note. Everything that waits does so until the researcher accepts it
    (ADR 0026: the Lead proposes, a person decides).
    """
    if update is None:
        return None, None
    client_notes = {str(n.get("memory_id")) for n in shown_notes if n.get("scope") == "client"}
    now = SelfUpdate(
        remember=[n for n in update.remember if n.scope == "client"],
        forget=[m for m in update.forget if m in client_notes],
    )
    waits = SelfUpdate(
        name=update.name,
        soul=update.soul,
        user=update.user,
        remember=[n for n in update.remember if n.scope == "personal"],
        forget=[m for m in update.forget if m not in client_notes],
    )
    return (None if now.is_empty else now), (None if waits.is_empty else waits)


#: The Lead's files a self-update replaces, as the frozen ``lead`` layer names them.
SELF_UPDATE_FILES: Final = ("name", "soul", "user")


def self_update_base(lead: Mapping[str, Any]) -> dict[str, str]:
    """The files a turn saw (its frozen ``lead`` layer): what a waiting change replaces."""
    return {f: str(lead.get(f) or "") for f in SELF_UPDATE_FILES}


def stale_files(
    pending: Mapping[str, Any], base: Mapping[str, Any] | None, current: Mapping[str, str]
) -> list[str]:
    """The files ``pending`` would replace that changed since its turn saw them.

    Accepting an older turn's change must not silently put back what a newer one wrote (the
    review of baac33d5). A turn stored without a base cannot show it saw the current text, so
    every file it changes counts as stale (unknown is not current). Notes have no base.
    """
    changed = [f for f in SELF_UPDATE_FILES if pending.get(f) is not None]
    if not isinstance(base, Mapping):
        return changed
    return [f for f in changed if base.get(f) != current.get(f)]


def waiting_self_update(
    pending: Mapping[str, Any] | None, shown_notes: Sequence[Mapping[str, Any]]
) -> dict[str, Any] | None:
    """What waits for the researcher, in the words the interface shows: the file changes, the
    personal notes to keep, and each note to forget with the text the turn was shown (a note
    the turn was not shown keeps its id and no text)."""
    if not isinstance(pending, Mapping):
        return None
    texts = {str(n.get("memory_id")): str(n.get("text") or "") for n in shown_notes}
    return {
        "name": pending.get("name"),
        "soul": pending.get("soul"),
        "user": pending.get("user"),
        "remember": [str(n.get("text")) for n in pending.get("remember") or ()],
        "forget": [
            {"memory_id": str(m), "text": texts.get(str(m))} for m in pending.get("forget") or ()
        ],
    }


# --------------------------------------------------------------------------- the prompt

_TASK: Final = """Jsi Vedoucí výzkumu: osobní výzkumný parťák jednoho výzkumníka v AIA. Provázíš
ho studií od zadání po report. Ve vrstvě lead máš své jméno, svůj SOUL (povahu a styl práce),
soubor USER (co víš o tom, jak tento výzkumník pracuje) a poznámky (notes). Řiď se jimi.

Co děláš:
- Stav studie vysvětluješ výhradně z dodaného kontextu (study, design, runs, conversation,
  view). Co v kontextu není, označ jako neposkytnuté.
- Změny artefaktů navrhuješ jen v poli edits a u každé uveď why. Každou změnu přijme nebo
  odmítne člověk; nikdy netvrď, že jsi návrh výzkumu změnil.
- Placenou práci (specialistu, běh výzkumu, rešerši) jen připravíš, nejvýše jednu, v poli
  request. Spustí ji až člověk; netvrď, že běží.
- Pohled řídíš polem view: open_stage otevře fázi, focus zaměří položku jejím
  identifikátorem (například question:q3, brief:goal, plan:research_questions).
- Do reply nepiš žádné číslo, které v kontextu není. Čísla neodhaduj, nepočítej ani
  nezaokrouhluj; aplikace odpověď s cizím číslem odmítne.
- Odpovídej česky, stručně a prakticky: hlavní věc, její důsledek, další krok. V follow
  nabídni nejvýše tři krátké navazující otázky.

Pozdrav (view.kind je greeting): tři až pět řádků. Kde studie stojí, co čeká na
výzkumníka a doporučený další krok. Je-li lead.first_conversation true, krátce se představ
a polož jednu až dvě otázky na to, jak výzkumník rád pracuje.

Tvé soubory (self_update):
- name, soul a user měň jen tehdy, když o to výzkumník požádá, nebo když je jeho trvalá
  preference zřejmá. soul a user posíláš celé, jako úplnou náhradu.
- remember: nejvýše dvě krátké poznámky o trvalých pracovních preferencích. Poznámka
  personal platí ve všech studiích a smí obsahovat jen styl práce a preference; poznámka
  client se váže ke klientovi této studie.
- forget: jen memory_id poznámek z lead.notes.
- Do soul, user ani do poznámky personal nikdy nepiš fakt o klientovi: jméno, plán, číslo
  ani výsledek.
- Co jsi ve svých souborech změnil, vždy řekni v reply. Když nic neměníš, self_update je null.

Vrať pouze objekt LeadOutput: reply, view, edits, request, follow, self_update."""


def baseline_task() -> str:
    """The Lead's task wording this code ships: the editable part's baseline (ADR 0020)."""
    return _TASK


def lead_prompt(task: str | None = None) -> str:
    """The system prompt of a turn: the research rails, then the Lead's task wording."""
    return FIXED_PREFIX + (_TASK if task is None else task)


# --------------------------------------------------------------------------- the context


class LeadContextTooLarge(ValueError):
    """The frozen context exceeds its bound with every droppable turn dropped."""

    reason = "lead_context_too_large"


def context_bytes(context: Mapping[str, Any]) -> int:
    return len(canonical_json(context).encode("utf-8"))


def context_sha256(context: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(context).encode("utf-8")).hexdigest()


def layer(context: Mapping[str, Any], name: str) -> dict[str, Any]:
    """One layer of a frozen context, by name."""
    for entry in context["layers"]:
        if entry["layer"] == name:
            return dict(entry)
    raise KeyError(name)


def notes_layer(notes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The newest notes, at most :data:`NOTES_IN_CONTEXT` and :data:`NOTES_MAX_BYTES`;
    ``notes`` come newest first."""
    kept: list[dict[str, Any]] = []
    for note in list(notes)[:NOTES_IN_CONTEXT]:
        entry = {
            "memory_id": str(note["memory_id"]),
            "scope": str(note["scope"]),
            "text": str(note["text"]),
        }
        if len(canonical_json([*kept, entry]).encode("utf-8")) > NOTES_MAX_BYTES:
            break
        kept.append(entry)
    return kept


def freeze_context(
    *,
    prompt: PromptPin,
    lead: Mapping[str, Any],
    knowledge: Sequence[Mapping[str, Any]],
    omitted_knowledge_ids: Sequence[str],
    study: Mapping[str, Any],
    design: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]],
    view: Mapping[str, Any],
    conversation: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """The turn's context, its layers in ADR 0026's order, within :data:`CONTEXT_MAX_BYTES`.

    ``conversation`` is the turns before this one, oldest first; only the newest
    :data:`HISTORY_TURNS` are kept, and the oldest of those go first when the whole is over
    its bound. With none left to drop it is refused (:class:`LeadContextTooLarge`).
    """
    turns = [dict(t) for t in list(conversation)[-HISTORY_TURNS:]]
    dropped = max(0, len(conversation) - len(turns))
    while True:
        context: dict[str, Any] = {
            "harness_version": LEAD_HARNESS_VERSION,
            "layers": [
                {"layer": "prompt", "pin": prompt.model_dump(mode="json")},
                {"layer": "lead", **dict(lead)},
                {
                    "layer": "knowledge",
                    "items": [dict(k) for k in knowledge],
                    "omitted_ids": list(omitted_knowledge_ids),
                },
                {"layer": "study", **dict(study)},
                {"layer": "design", **dict(design)},
                {"layer": "runs", "runs": [dict(r) for r in runs]},
                {"layer": "view", **dict(view)},
                {"layer": "conversation", "turns": turns, "omitted_turns": dropped},
            ],
        }
        if context_bytes(context) <= CONTEXT_MAX_BYTES:
            return context
        if not turns:
            raise LeadContextTooLarge(
                f"the Lead's context exceeds {CONTEXT_MAX_BYTES} bytes with no turn to drop"
            )
        turns.pop(0)
        dropped += 1


def model_message(context: Mapping[str, Any]) -> str:
    """What the model is sent as its user turn: every layer but the prompt, which is the
    system turn."""
    return canonical_json(
        {"context": [entry for entry in context["layers"] if entry["layer"] != "prompt"]}
    )


# --------------------------------------------------------------------------- the request


def _part(
    part: str, value: Any, rule: MaterialRule, approvals: tuple[MaterialApproval, ...]
) -> dict[str, Any]:
    ruled = classify_by_rule(value, rule, approvals)
    return {
        "part": part,
        "data_class": ruled.data_class.value,
        "source": ruled.source,
        "sha256": ruled.sha256,
    }


def _lead_files(
    lead: Mapping[str, Any], approvals: tuple[MaterialApproval, ...]
) -> list[dict[str, Any]]:
    """The Lead's files and notes: its name, SOUL, USER and personal notes are Class C by rule
    (they change only when the researcher asks it to remember), a client-scoped note Class A;
    a note of any other scope is covered by no rule and refuses."""
    parts = [
        _part("lead_name", str(lead.get("name") or ""), MaterialRule.LEAD_FILES, approvals),
        _part("lead_soul", str(lead.get("soul") or ""), MaterialRule.LEAD_FILES, approvals),
        _part("lead_user", str(lead.get("user") or ""), MaterialRule.LEAD_FILES, approvals),
    ]
    for note in lead.get("notes") or ():
        text = str(note["text"])
        scope = note.get("scope")
        if scope == "client":
            parts.append(_part("client_note", text, MaterialRule.CLIENT_NOTE, approvals))
        elif scope == "personal":
            parts.append(_part("personal_note", text, MaterialRule.LEAD_FILES, approvals))
        else:
            parts.append({"part": "note", "data_class": None, "source": "unknown"})
    return parts


def context_classification(
    context: Mapping[str, Any],
    approvals: tuple[MaterialApproval, ...],
    prompt: PromptPin,
) -> list[dict[str, Any]]:
    """Each part of a turn's context with its class and who answered for it.

    By the owner's rules (``material_rules``): the design (its content and analysis) and the
    study's and client's names are Class B; the message, the focus's label (text the browser
    sends beside it) and every earlier message of the researcher take the study's class (B);
    the Lead's files and personal notes are Class C and a client note Class A; approved
    knowledge is Class A. An operator's classification of a part's exact bytes can only raise
    it. The prompt is classified as the agents' is (``prompt_data_class``); an earlier reply
    carries the class its turn was sent as. A part's ``data_class`` is ``None`` when no rule
    covers it, which refuses the turn.
    """
    design = layer(context, "design")
    study = layer(context, "study")
    view = layer(context, "view")
    prompt_class = prompt_data_class(prompt, approvals)
    parts: list[dict[str, Any]] = [
        _part("design", design.get("content") or {}, MaterialRule.DESIGN, approvals),
        {
            "part": "prompt",
            "data_class": None if prompt_class is None else prompt_class.value,
            "source": prompt_class_source(prompt, approvals),
        },
        *_lead_files(layer(context, "lead"), approvals),
        _part(
            "study_name",
            {"study": study.get("name"), "client": study.get("client_name")},
            MaterialRule.STUDY_NAME,
            approvals,
        ),
    ]
    if design.get("analysis"):
        parts.append(_part("design_analysis", design["analysis"], MaterialRule.DESIGN, approvals))
    if view.get("message"):
        parts.append(_part("message", view["message"], MaterialRule.LEAD_MESSAGE, approvals))
    focus = view.get("focus")
    if isinstance(focus, Mapping) and focus.get("label"):
        parts.append(
            _part("focus_label", str(focus["label"]), MaterialRule.LEAD_MESSAGE, approvals)
        )
    for turn in layer(context, "conversation")["turns"]:
        if turn.get("actor") == "person":
            parts.append(
                _part(
                    "earlier_message",
                    turn.get("text") or "",
                    MaterialRule.LEAD_MESSAGE,
                    approvals,
                )
            )
        else:
            known = turn.get("data_class")
            parts.append(
                {
                    "part": "earlier_reply",
                    "data_class": known if known in DataClass._value2member_map_ else None,
                    "source": "turn",
                }
            )
    knowledge = layer(context, "knowledge")["items"]
    parts.extend(
        {
            "part": "knowledge",
            "data_class": rule_class(MaterialRule.KNOWLEDGE).value,
            "source": MaterialRule.KNOWLEDGE.value,
        }
        for _ in knowledge
    )
    return parts


def context_data_class(
    context: Mapping[str, Any],
    approvals: tuple[MaterialApproval, ...],
    prompt: PromptPin,
) -> DataClass | None:
    """The class a turn is sent as: the most restrictive of its parts'
    (:func:`context_classification`); a part of unknown class refuses."""
    return most_restrictive_material(
        [
            None if p["data_class"] is None else DataClass(p["data_class"])
            for p in context_classification(context, approvals, prompt)
        ]
    )


def lead_request(
    context: Mapping[str, Any],
    *,
    policy_version: str,
    max_output_tokens: int,
    material_approvals: tuple[MaterialApproval, ...] = (),
) -> ModelRequest:
    """One Lead turn's model request: no tools, one schema repair, the frozen prompt.

    The prompt is the pin the context froze; a pin for another prompt is refused. The
    output contract refuses a reply with a number the context and prompt do not hold.
    """
    prompt = PromptPin(**layer(context, "prompt")["pin"])
    if prompt.prompt_id != LEAD_PROMPT_ID:
        raise ValueError(f"prompt pin {prompt.prompt_id} does not belong to {LEAD_PROMPT_ID}")
    system = lead_prompt(prompt.text)
    message = model_message(context)
    knowledge = layer(context, "knowledge")["items"]
    lineage = DataLineage.none()
    if any(k.get("kind") in {"DATASET", "ARTIFACT", "FINDING"} for k in knowledge):
        lineage = DataLineage.of("unclassified-client-knowledge")
    return ModelRequest(
        agent=AgentDefinition(
            agent_id=LEAD_AGENT_ID,
            version="1",
            capability=ModelCapability.STUDY_LEAD,
            prompt_id=LEAD_PROMPT_ID,
            prompt_version=prompt.version,
            output_contract=lead_contract(system + "\n" + message),
            max_output_tokens=max_output_tokens,
            schema_repair_attempts=1,
        ),
        policy_version=policy_version,
        data_classification=context_data_class(context, material_approvals, prompt),
        data_lineage=lineage,
        system=system,
        messages=(Message(role="user", content=message),),
    )


#: What the gateway counts around a request's own bytes (``input_token_bound``), and what a
#: repair adds besides the refused answer (``request_limits``): generous, never under.
_FRAMING_BYTES: Final = 2048 + 256 + 16 * 4
_ANSWER_BYTES_PER_TOKEN: Final = 5


def lead_request_window_tokens(max_output_tokens: int) -> int:
    """The input tokens a turn and its one schema repair can take, at most.

    The frozen context (prompt pin included) is at most :data:`CONTEXT_MAX_BYTES`, and the
    pin's text is sent once, as the system turn behind the code's rails; the output
    contract's schema is sent beside it; a repair adds the refused answer. A token is at
    least one byte, so bytes bound tokens. The worker's hold is sized to two calls at this
    window.
    """
    schema = canonical_json(lead_contract("").model_json_schema(mode="validation"))
    return (
        CONTEXT_MAX_BYTES
        + len(FIXED_PREFIX.encode("utf-8"))
        + len(schema.encode("utf-8"))
        + _ANSWER_BYTES_PER_TOKEN * max_output_tokens
        + _FRAMING_BYTES
    )


# --------------------------------------------------------------------------- records


def _new_id(prefix: str) -> str:
    return prefix + uuid4().hex[:20]


def new_turn_id() -> str:
    return _new_id("LDT-")


def new_lead_id() -> str:
    return _new_id("LEAD-")


def new_memory_id() -> str:
    return _new_id("LMM-")


def new_lead_revision_id() -> str:
    return _new_id("LRV-")


class LeadTurn(Closed):
    """One turn of a researcher's conversation in a Study, as stored."""

    turn_id: str
    study_id: str
    user_id: str
    sequence_no: int
    actor: Literal["person", "lead"]
    kind: Literal["message", "greeting"]
    stage: str
    text: str | None
    focus: dict[str, str] | None
    run_id: str | None
    workspace_revision: int | None
    design_revision_id: str | None
    created_by: str
    created_at: datetime
    #: The typed start the server matched in this person's message (lead-orchestration LO5,
    #: ``domain/lead_commands.py``: ``agent_job:<action>`` or ``research_run``); ``None`` for
    #: any other turn. Its card is the person's command, never Lead output (D22).
    command: str | None = None


class ResearcherLead(Closed):
    """A researcher's own Lead and its files, as stored."""

    lead_id: str
    organization_id: str
    user_id: str
    name: str
    soul: str
    user: str
    hatched_at: datetime
    updated_at: datetime
    #: The researcher's standing choice to have the Lead's text edits (:func:`is_text_edit`)
    #: accepted without a click. Off unless they turn it on (plan inline-decisions chunk 2).
    auto_accept_text_edits: bool = False


class LeadNote(Closed):
    """One active note in a Lead's memory."""

    memory_id: str
    scope: Literal["personal", "client"]
    client_id: str | None
    client_name: str | None = None
    text: str
    source_turn_id: str | None
    created_by: Literal["lead", "person"]
    created_at: datetime


class SelfUpdateApplied(Closed):
    """What a turn's ``self_update`` changed, for the interface to say so."""

    name: bool = False
    soul: bool = False
    user: bool = False
    remembered: list[str] = Field(default_factory=list)
    forgotten: list[str] = Field(default_factory=list)
