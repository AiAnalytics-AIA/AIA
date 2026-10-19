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
  question, section or list item the content does not hold is dropped and named.
* **The context is frozen at enqueue, in a fixed order, and bounded**
  (:func:`freeze_context`): 96 KB of canonical JSON; the oldest turns go first, then the
  turn is refused (:class:`LeadContextTooLarge`), never cut silently.
* **Each researcher has their own Lead** (OpenClaw-style files): a name, a SOUL (its
  personality and working style), a USER file (what it knows of how this researcher works)
  and notes. The Lead changes them only through ``self_update``, when the researcher asks
  in chat; a ``forget`` names only notes this turn was shown (:func:`ground_self_update`).
* **Its data class** follows the design agents' rule (:func:`lead_request`): material is
  classified by its exact bytes, any approved knowledge and any client-scoped note is
  Class A, the most restrictive wins and an unknown class refuses dispatch.

No I/O: stdlib and Pydantic only.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Final, Literal, get_args
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ai_contracts import AgentDefinition, Message, ModelRequest, canonical_json
from .ai_material import MaterialApproval, classify_material, most_restrictive_material
from .ai_models import ModelCapability
from .licence import DataLineage
from .prompts import PromptPin
from .research_agents import FIXED_PREFIX, ResearchAction, prompt_data_class
from .residency import DataClass

__all__ = [
    "CONTEXT_MAX_BYTES",
    "DEFAULT_LEAD_NAME",
    "DEFAULT_SOUL",
    "LEAD_AGENT_ID",
    "LEAD_HARNESS_VERSION",
    "LEAD_PROMPT_ID",
    "LEAD_PROMPT_VERSION",
    "MESSAGE_MAX_CHARS",
    "STAGES",
    "Dropped",
    "LeadContextTooLarge",
    "LeadNote",
    "LeadOutput",
    "LeadTurn",
    "Refused",
    "ResearcherLead",
    "SelfUpdate",
    "SelfUpdateApplied",
    "Stage",
    "apply_edit",
    "baseline_task",
    "context_sha256",
    "freeze_context",
    "ground_edits",
    "ground_self_update",
    "layer",
    "lead_contract",
    "lead_prompt",
    "lead_request",
    "lead_request_window_tokens",
    "number_tokens",
    "question_add_problem",
    "split_self_update",
    "unreadable_numbers",
]

LEAD_PROMPT_ID: Final = "aia.research.lead"
LEAD_AGENT_ID: Final = LEAD_PROMPT_ID
LEAD_PROMPT_VERSION: Final = "1"
LEAD_HARNESS_VERSION: Final = "aia-research-lead-1"

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

TextField = Literal[
    "title",
    "goal",
    "decision_use",
    "briefing.product_description",
    "briefing.situation",
    "briefing.what_is_known",
    "briefing.constraints",
    "plan.problem_summary",
]
PlanList = Literal["plan.objectives", "plan.research_questions", "plan.hypotheses"]
QuestionType = Literal["vyber", "multi", "skala", "otevrena"]

#: A ``data-aia`` id the interface focuses: ``question:q3``, ``brief:goal``.
_TARGET = r"^[a-z_]+:[A-Za-z0-9_.\-]+$"
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


# --------------------------------------------------------------------------- edits


class SetText(Closed):
    op: Literal["set_text"]
    field: TextField
    value: str = Field(max_length=MESSAGE_MAX_CHARS)
    why: Why


class ListAdd(Closed):
    op: Literal["list_add"]
    list: PlanList
    value: ItemText
    why: Why


class ListReplace(Closed):
    op: Literal["list_replace"]
    list: PlanList
    old: ItemText
    value: ItemText
    why: Why


class ListRemove(Closed):
    op: Literal["list_remove"]
    list: PlanList
    old: ItemText
    why: Why


def question_add_problem(qtype: str, options: Sequence[str]) -> str | None:
    """Why a new question of ``qtype`` cannot carry ``options``, as ``apply_edit`` builds it;
    ``None`` when it can. A selection question needs at least two options; an open question
    has none; a scale has none (the default end labels) or exactly two (its end labels).
    Anything else would be shown to the researcher and silently dropped (Codex on #484)."""
    if qtype in ("vyber", "multi"):
        return "too_few_options" if len(options) < 2 else None
    if qtype == "otevrena":
        return "options_on_open_question" if options else None
    if qtype == "skala":
        return None if len(options) in (0, 2) else "scale_labels_not_two"
    return "unknown_question_type"


class QuestionAdd(Closed):
    op: Literal["question_add"]
    section_id: str | None = Field(default=None, min_length=1, max_length=120)
    text: ItemText
    qtype: QuestionType
    options: list[Option] = Field(default_factory=list, max_length=40)
    why: Why

    @model_validator(mode="after")
    def _coherent(self) -> QuestionAdd:
        problem = question_add_problem(self.qtype, self.options)
        if problem == "too_few_options":
            raise ValueError("a selection question needs at least two options")
        if problem == "options_on_open_question":
            raise ValueError("an open question has no options")
        if problem == "scale_labels_not_two":
            raise ValueError("a scale's options are its two end labels, or none")
        return self


class QuestionEdit(Closed):
    op: Literal["question_edit"]
    question_id: str = Field(min_length=1, max_length=120)
    text: ItemText | None = None
    options: list[Option] | None = Field(default=None, max_length=40)
    why: Why

    @model_validator(mode="after")
    def _changes_something(self) -> QuestionEdit:
        if self.text is None and self.options is None:
            raise ValueError("a question edit changes its text, its options or both")
        if self.options is not None and len(self.options) < 2:
            raise ValueError("a selection question's replacement options are at least two")
        return self


class QuestionRemove(Closed):
    op: Literal["question_remove"]
    question_id: str = Field(min_length=1, max_length=120)
    why: Why


class SetN(Closed):
    op: Literal["set_n"]
    value: int = Field(ge=30, le=40_000)
    why: Why


EditOp = Annotated[
    SetText
    | ListAdd
    | ListReplace
    | ListRemove
    | QuestionAdd
    | QuestionEdit
    | QuestionRemove
    | SetN,
    Field(discriminator="op"),
]


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
_NUMBER = re.compile(
    r"(?P<sign>(?<![\w.,])[-\u2212])?"
    r"(?<![\w.,])(?P<num>\d+(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?)(?![\w])"
)
#: A number this guard cannot read exactly: one with an exponent (``1e6``, ``2,5E-3``). Its
#: digits touch a letter, so ``_NUMBER`` sees nothing; a reply writing one is refused, never
#: read as some other number (Codex on #484).
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


def _key(text: str) -> str:
    """A list item as items compare: whitespace collapsed, casefolded."""
    return " ".join(text.split()).casefold()


def _plan_list(
    content: Mapping[str, Any], analysis: Mapping[str, Any] | None, name: str
) -> list[Any]:
    key = name.split(".", 1)[1]
    if isinstance(analysis, Mapping) and isinstance(analysis.get(key), list):
        return list(analysis[key])
    plan = content.get("research_plan")
    if isinstance(plan, Mapping) and isinstance(plan.get(key), list):
        return list(plan[key])
    return []


#: The question types whose options (``kategorie``) an edit may replace.
_SELECTION: Final = frozenset({"vyber", "multi"})


def _question_ids(content: Mapping[str, Any]) -> tuple[set[str], dict[str, Any]]:
    """The questions sections' ids, and each question's id with its type."""
    sections: set[str] = set()
    questions: dict[str, Any] = {}
    for section in content.get("sections") or ():
        if not isinstance(section, Mapping) or section.get("type") != "questions":
            continue
        if section.get("id"):
            sections.add(str(section["id"]))
        for question in section.get("questions") or ():
            if isinstance(question, Mapping) and question.get("id"):
                questions[str(question["id"])] = question.get("typ")
    return sections, questions


def ground_edits(
    output: LeadOutput,
    content: Mapping[str, Any],
    analysis: Mapping[str, Any] | None = None,
) -> tuple[LeadOutput, list[Dropped]]:
    """``output`` with only the edits the working content can take, and the rest named.

    A question or section id must be one of a questions section in ``content["sections"]``;
    a list item's ``old`` must be in its plan list (the working ``analysis`` first, else
    ``content["research_plan"]``), compared whitespace-collapsed and casefolded; a
    ``list_add`` already present is dropped too. Nothing else is judged here: a person
    accepts each edit that is left.
    """
    sections, questions = _question_ids(content)
    kept: list[Any] = []
    dropped: list[Dropped] = []
    for i, edit in enumerate(output.edits):
        reason: str | None = None
        if isinstance(edit, QuestionEdit | QuestionRemove):
            if edit.question_id not in questions:
                reason = "unknown_question"
            elif (
                isinstance(edit, QuestionEdit)
                and edit.options is not None
                and questions[edit.question_id] not in _SELECTION
            ):
                reason = "options_on_non_selection"
        elif isinstance(edit, QuestionAdd):
            if edit.section_id is not None and edit.section_id not in sections:
                reason = "unknown_section"
            else:
                reason = question_add_problem(edit.qtype, edit.options)
        elif isinstance(edit, ListReplace | ListRemove):
            items = {_key(str(x)) for x in _plan_list(content, analysis, edit.list)}
            if _key(edit.old) not in items:
                reason = "unknown_item"
        elif isinstance(edit, ListAdd):
            items = {_key(str(x)) for x in _plan_list(content, analysis, edit.list)}
            if _key(edit.value) in items:
                reason = "already_present"
        if reason is None:
            kept.append(edit)
        else:
            dropped.append(Dropped(index=i, op=edit.op, reason=reason))
    return output.model_copy(update={"edits": kept}), dropped


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
    update: SelfUpdate | None,
) -> tuple[SelfUpdate | None, SelfUpdate | None]:
    """``update`` as what applies now and what waits for the researcher's yes.

    The model's choice of scope is not an isolation boundary (Codex on #484): a "personal"
    note, or a SOUL, USER or name change, loads into every study of every client, so a client
    fact written there by mistake or by injection would leave its client. Only what stays
    inside the turn's own client applies at once: client notes (bound to the turn's client by
    the repository) and forgets (which reach only notes the turn was shown). Everything else
    waits until the researcher accepts it (ADR 0026: the Lead proposes, a person decides).
    """
    if update is None:
        return None, None
    now = SelfUpdate(
        remember=[n for n in update.remember if n.scope == "client"], forget=list(update.forget)
    )
    waits = SelfUpdate(
        name=update.name,
        soul=update.soul,
        user=update.user,
        remember=[n for n in update.remember if n.scope == "personal"],
    )
    return (None if now.is_empty else now), (None if waits.is_empty else waits)


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


def _material_class(value: Any, approvals: tuple[MaterialApproval, ...]) -> DataClass | None:
    return classify_material(value, approvals).data_class


def lead_files_data_class(
    lead: Mapping[str, Any], approvals: tuple[MaterialApproval, ...]
) -> DataClass | None:
    """The class of the Lead's files and notes: the hatch defaults are the code's wording
    (Class C); anything else is classified by its exact text, a client note is Class A, and
    the most restrictive wins (an unknown one refuses dispatch)."""
    classes: list[DataClass | None] = [DataClass.CLASS_C_INTERNAL]
    soul = str(lead.get("soul") or "")
    user = str(lead.get("user") or "")
    name = str(lead.get("name") or "")
    if soul != DEFAULT_SOUL:
        classes.append(_material_class(soul, approvals))
    if user != DEFAULT_USER:
        classes.append(_material_class(user, approvals))
    if name != DEFAULT_LEAD_NAME:
        classes.append(_material_class(name, approvals))
    for note in lead.get("notes") or ():
        classes.append(_material_class(str(note["text"]), approvals))
        if note.get("scope") == "client":
            classes.append(DataClass.CLASS_A_CLIENT_CONFIDENTIAL)
    return most_restrictive_material(classes)


def context_data_class(
    context: Mapping[str, Any],
    approvals: tuple[MaterialApproval, ...],
    prompt: PromptPin,
) -> DataClass | None:
    """The class a turn is sent as, by the design agents' rule (``agent_request``).

    The design (its content and analysis), the study's identity, the message and every
    earlier message are classified by their exact bytes; an earlier reply carries the class
    its turn was sent as (unknown refuses); approved knowledge and client notes are Class A;
    the prompt is classified as the agents' is. The most restrictive wins; unknown refuses.
    """
    design = layer(context, "design")
    study = layer(context, "study")
    view = layer(context, "view")
    classes: list[DataClass | None] = [
        _material_class(design.get("content") or {}, approvals),
        prompt_data_class(prompt, approvals),
        lead_files_data_class(layer(context, "lead"), approvals),
        _material_class(
            {"study": study.get("name"), "client": study.get("client_name")}, approvals
        ),
    ]
    if design.get("analysis"):
        classes.append(_material_class(design["analysis"], approvals))
    if view.get("message"):
        classes.append(_material_class(view["message"], approvals))
    for turn in layer(context, "conversation")["turns"]:
        if turn.get("actor") == "person":
            classes.append(_material_class(turn.get("text") or "", approvals))
        else:
            known = turn.get("data_class")
            classes.append(DataClass(known) if known in DataClass._value2member_map_ else None)
    knowledge = layer(context, "knowledge")["items"]
    classes.extend(DataClass.CLASS_A_CLIENT_CONFIDENTIAL for _ in knowledge)
    return most_restrictive_material(classes)


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
            capability=ModelCapability.RESEARCH_REASONING,
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


# --------------------------------------------------------------------------- applying an edit


class Refused(Closed):
    """An edit the working content cannot take, and why (a stable word)."""

    reason: str


#: Top-level text fields whose edit changes the brief the analysis was made of, so the
#: analysis is cleared, as the web's ``editBrief`` does; a title edit keeps it.
_BRIEF_FIELDS: Final = frozenset({"goal", "decision_use"})
_NEW_SECTION_TITLE: Final = "Hlavní otázky"
_DEFAULT_SCALE_LABELS: Final = ("vůbec", "zcela")
_DEFAULT_CATEGORIES: Final = ("Ano", "Ne")


def _short_hex() -> str:
    return uuid4().hex[:10]


def _narrative(
    content: dict[str, Any], analysis: dict[str, Any] | None
) -> tuple[dict[str, Any], dict[str, Any]] | Refused:
    """The plan narrative's two homes, ready to write: ``content.research_plan`` and the
    analysis, which starts from the plan when there is none."""
    raw = content.get("research_plan")
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        return Refused(reason="plan_not_an_object")
    plan = dict(raw)
    started = dict(analysis) if isinstance(analysis, dict) else dict(plan)
    return plan, started


def _write_narrative(
    content: dict[str, Any], plan: dict[str, Any], analysis: dict[str, Any], key: str, value: Any
) -> dict[str, Any]:
    plan[key] = value
    analysis[key] = value
    content["research_plan"] = plan
    ui = content.get("ui_state")
    ui_state = dict(ui) if isinstance(ui, dict) else {}
    ui_state["plan_manual_changed"] = True
    content["ui_state"] = ui_state
    return analysis


def _question_sections(content: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        s
        for s in content.get("sections") or []
        if isinstance(s, dict) and s.get("type") == "questions"
    ]


def _find_question(content: dict[str, Any], question_id: str) -> tuple[dict[str, Any], int] | None:
    for section in _question_sections(content):
        for i, q in enumerate(section.get("questions") or []):
            if isinstance(q, dict) and q.get("id") == question_id:
                return section, i
    return None


def _new_question(edit: QuestionAdd) -> dict[str, Any]:
    qid = "Q_" + _short_hex()
    if edit.qtype == "skala":
        labels = list(edit.options) if len(edit.options) == 2 else list(_DEFAULT_SCALE_LABELS)
        return {
            "id": qid,
            "text": edit.text,
            "typ": "skala",
            "skala": [1, 10],
            "popisky_skaly": labels,
            "povolit_nevim": False,
        }
    if edit.qtype == "otevrena":
        return {"id": qid, "text": edit.text, "typ": "otevrena", "povolit_nevim": False}
    return {
        "id": qid,
        "text": edit.text,
        "typ": edit.qtype,
        "kategorie": list(edit.options) or list(_DEFAULT_CATEGORIES),
        "povolit_nevim": False,
    }


def apply_edit(
    content: Mapping[str, Any], analysis: Mapping[str, Any] | None, edit: Any
) -> tuple[dict[str, Any], dict[str, Any] | None] | Refused:
    """One accepted Lead edit applied to the working content and analysis, by the web's rules.

    Returns the new content and analysis (copies; the inputs are not changed), or why the edit
    cannot be applied. A brief edit (``goal``, ``decision_use``, any ``briefing.*``) clears
    the analysis, which was made of the brief as it was; a title edit keeps it. A question
    edit's options replace only a selection question's categories, at least two of them;
    options on any other question are refused, never accepted as a change of nothing. The plan
    narrative (``plan.problem_summary`` and the plan lists) is written to both
    ``content.research_plan`` and the analysis (started from the plan when there is none),
    and marks ``ui_state.plan_manual_changed``.
    """
    body: dict[str, Any] = deepcopy(dict(content))
    working: dict[str, Any] | None = deepcopy(dict(analysis)) if analysis is not None else None
    if isinstance(edit, SetText):
        if edit.field == "plan.problem_summary":
            homes = _narrative(body, working)
            if isinstance(homes, Refused):
                return homes
            plan, started = homes
            return body, _write_narrative(body, plan, started, "problem_summary", edit.value)
        if edit.field.startswith("briefing."):
            raw = body.get("briefing")
            if raw is not None and not isinstance(raw, dict):
                return Refused(reason="briefing_not_an_object")
            briefing = dict(raw or {})
            briefing[edit.field.split(".", 1)[1]] = edit.value
            body["briefing"] = briefing
            return body, None
        body[edit.field] = edit.value
        return body, (None if edit.field in _BRIEF_FIELDS else working)
    if isinstance(edit, ListAdd | ListReplace | ListRemove):
        homes = _narrative(body, working)
        if isinstance(homes, Refused):
            return homes
        plan, started = homes
        key = edit.list.split(".", 1)[1]
        current = started.get(key) if isinstance(started.get(key), list) else plan.get(key)
        items = [str(x) for x in current] if isinstance(current, list) else []
        keys = [_key(x) for x in items]
        if isinstance(edit, ListAdd):
            if _key(edit.value) in keys:
                return Refused(reason="already_present")
            items.append(edit.value)
        else:
            if _key(edit.old) not in keys:
                return Refused(reason="unknown_item")
            at = keys.index(_key(edit.old))
            if isinstance(edit, ListReplace):
                items[at] = edit.value
            else:
                del items[at]
        return body, _write_narrative(body, plan, started, key, items)
    if isinstance(edit, QuestionAdd):
        problem = question_add_problem(edit.qtype, edit.options)
        if problem is not None:
            # Never a question other than the one the researcher was shown and accepted.
            return Refused(reason=problem)
        sections = body.get("sections")
        if sections is not None and not isinstance(sections, list):
            return Refused(reason="sections_not_a_list")
        listed: list[Any] = [dict(s) if isinstance(s, dict) else s for s in sections or []]
        body["sections"] = listed
        target: dict[str, Any] | None = None
        if edit.section_id is not None:
            target = next(
                (
                    s
                    for s in listed
                    if isinstance(s, dict)
                    and s.get("id") == edit.section_id
                    and s.get("type") == "questions"
                ),
                None,
            )
            if target is None:
                return Refused(reason="unknown_section")
        else:
            target = next(
                (s for s in listed if isinstance(s, dict) and s.get("type") == "questions"), None
            )
            if target is None:
                target = {
                    "id": "sec_" + _short_hex(),
                    "type": "questions",
                    "title": _NEW_SECTION_TITLE,
                    "purpose": "",
                    "questions": [],
                }
                listed.append(target)
        target["questions"] = [*list(target.get("questions") or []), _new_question(edit)]
        return body, working
    if isinstance(edit, QuestionEdit | QuestionRemove):
        found = _find_question(body, edit.question_id)
        if found is None:
            return Refused(reason="unknown_question")
        section, i = found
        questions = list(section.get("questions") or [])
        if isinstance(edit, QuestionRemove):
            del questions[i]
        else:
            question = dict(questions[i])
            if edit.options is not None:
                # Options replace a selection question's categories, and only with a real
                # choice; on any other question they would change nothing yet be accepted.
                if question.get("typ") not in _SELECTION:
                    return Refused(reason="options_on_non_selection")
                if len(edit.options) < 2:
                    return Refused(reason="too_few_options")
                question["kategorie"] = list(edit.options)
            if edit.text is not None:
                question["text"] = edit.text
            questions[i] = question
        section["questions"] = questions
        return body, working
    if isinstance(edit, SetN):
        body["n"] = edit.value
        return body, working
    return Refused(reason="unknown_edit")
