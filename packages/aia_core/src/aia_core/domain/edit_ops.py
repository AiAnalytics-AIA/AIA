"""The working copy's edit vocabulary: one closed set of operations (ADR 0029 decision 1, WCE0).

A person and the Lead change a study's working copy through the same server-validated
operations. This module is that contract, before any writer moves onto it
(``working-copy-edit-ops`` WCE0); every later chunk extends it here and nowhere else:

* **The closed set** (:data:`CATALOGUE`). Every operation the working copy will take, each with
  the item kinds it addresses (the kinds ``design_items`` keys), the fields it writes, whether it
  is a text edit, whether it can touch a locked Sociomap input, whether the Lead's closed output
  can carry it today, and the chunk that owns it. The eight the Lead proposes today
  (:data:`EditOp`: :class:`SetText` … :class:`SetN`) and a question's display condition
  (:class:`RouteSet`, WCE13; a person's alone) are :attr:`Availability.APPLIED`: their payloads
  (:data:`WorkingOp`) and :func:`apply_edit` are here. The rest are
  :attr:`Availability.DECLARED`: named, ruled on and refused by name (``op_not_available``) until
  the chunk that gives each its payload and its apply; nothing is claimed present because a slot
  could hold it.
* **Ids** (:data:`ITEM_ID`, :func:`new_item_id`, :func:`new_op_id`): the grammar an item's stable
  id keeps (the id part of the Lead's ``FOCUS_ID``), the prefix each kind's new ids take (the ones
  ``apply_edit`` and the web already write: ``Q_``, ``sec_``), and an operation's own id for the
  log (M1). Existing content's ids, and the id lists that keep them, are ``item_ids``' (WCE1).
* **Validation** (:func:`refusal`): why an operation cannot apply to a working copy, as a stable
  word from :data:`REFUSALS`, the same words :func:`apply_edit` refuses with.
* **What an operation touches** (:func:`touches`): each ``(item key, field)`` it writes, the unit
  two people's edits conflict on (the owner's D-06: per field, not per item), on the items'
  stable ids (``item_ids``, WCE1), as the field view ``design_fields`` compares them.
* **The lock** (:func:`locked_items`, :func:`lock_refusal`, :func:`whole_copy_lock_refusal`): once
  a design declares a Sociomap input (a ``sociomap_rating`` question, or ``context_objects`` on a
  tracked set), the declared inputs and the sets they rate are locked (the owner's D-30): an
  operation or a whole-copy write that changes one is refused (``sociomap_input_locked``) unless
  its batch carries a person's recorded unlock (``sociomap_unlock``, WCE8).
* **The text-only marker** (:func:`is_text_edit`, :data:`TEXT_EDIT_OPS`): what changes wording and
  nothing the design links to it. It bounds the **default automatic accept**, which takes text
  edits only (ADR 0029 decision 9); it limits nothing a person may apply by hand.

One case file, ``tests/fixtures/edit_ops/cases.json``, holds this module and the web's
``applyLeadEdit`` / ``isTextEdit`` (``apps/web/src/lib/lead.ts``) to the same results, and the
web's trace (``apps/web/src/research/trace.ts``) to ``research_trace``'s link key and
``research_questions_of``. Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Any, Final, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .design_fields import Touch, changed_fields
from .design_items import Documents, ItemKey, item_values
from .design_items import design_items as changed_items
from .item_ids import with_item_ids
from .research_design import SampleSizeLimits, condition_refusal, sample_size_problem

__all__ = [
    "CATALOGUE",
    "ITEM_ID",
    "REFUSALS",
    "TEXT_EDIT_OPS",
    "TEXT_ONLY_FIELDS",
    "TEXT_ONLY_LISTS",
    "VALUE_MAX_CHARS",
    "Availability",
    "EditOp",
    "IdKind",
    "ItemKind",
    "ListAdd",
    "ListRemove",
    "ListReplace",
    "OpName",
    "OpSpec",
    "PlanList",
    "QuestionAdd",
    "QuestionEdit",
    "QuestionRemove",
    "QuestionType",
    "Refused",
    "RouteCondition",
    "RouteSet",
    "SetN",
    "SetText",
    "TextField",
    "TextRuling",
    "Touch",
    "WorkingOp",
    "apply_edit",
    "declares_sociomap_inputs",
    "is_item_id",
    "is_text_edit",
    "lock_refusal",
    "locked_items",
    "new_item_id",
    "new_op_id",
    "op_refusal",
    "question_add_problem",
    "refusal",
    "sample_size_reason",
    "spec_of",
    "touches",
    "whole_copy_lock_refusal",
]

#: The longest text value an edit may write (the Lead's message bound, kept equal to it).
VALUE_MAX_CHARS: Final = 4000


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Why = Annotated[str, Field(min_length=1, max_length=500)]
ItemText = Annotated[str, Field(min_length=1, max_length=1500)]
Option = Annotated[str, Field(min_length=1, max_length=300)]


# --------------------------------------------------------------------------- ids


class IdKind(StrEnum):
    """What carries a stable id (ADR 0029 decision 2): items and the parts of items."""

    OBJECTIVE = "objective"
    RESEARCH_QUESTION = "research_question"
    HYPOTHESIS = "hypothesis"
    TRACKED_SET = "tracked_set"
    SECTION = "section"
    QUESTION = "question"
    OPTION = "option"
    OBJECT = "object"
    ASSUMPTION = "assumption"
    STIMULUS = "stimulus"


#: The prefix of each kind's new ids. ``Q_`` and ``sec_`` are what the web and the Lead's
#: accept already write; the rest are new with WCE1.
ID_PREFIX: Final[Mapping[IdKind, str]] = MappingProxyType(
    {
        IdKind.OBJECTIVE: "obj_",
        IdKind.RESEARCH_QUESTION: "rq_",
        IdKind.HYPOTHESIS: "hyp_",
        IdKind.TRACKED_SET: "set_",
        IdKind.SECTION: "sec_",
        IdKind.QUESTION: "Q_",
        IdKind.OPTION: "opt_",
        IdKind.OBJECT: "o_",
        IdKind.ASSUMPTION: "asm_",
        IdKind.STIMULUS: "stim_",
    }
)

#: An item's stable id: the id part ``FOCUS_ID`` admits, so the interface can name the item.
ITEM_ID: Final = re.compile(r"^[A-Za-z0-9_.\-]{1,80}$")
_OP_ID: Final = re.compile(r"^EOP-[0-9a-f]{32}$")


def new_item_id(kind: IdKind | str) -> str:
    """A fresh id for an item of ``kind``: its prefix and ten hex digits."""
    return ID_PREFIX[IdKind(kind)] + uuid4().hex[:10]


def new_op_id() -> str:
    """A fresh id for one logged operation (``workspace_edit_ops``, M1)."""
    return "EOP-" + uuid4().hex


def is_item_id(text: object) -> bool:
    """Whether ``text`` is an id an item may keep."""
    return isinstance(text, str) and ITEM_ID.fullmatch(text) is not None


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

# --------------------------------------------------------------------------- edits


class SetText(_Closed):
    op: Literal["set_text"]
    field: TextField
    value: str = Field(max_length=VALUE_MAX_CHARS)
    why: Why


class ListAdd(_Closed):
    op: Literal["list_add"]
    list: PlanList
    value: ItemText
    why: Why


class ListReplace(_Closed):
    op: Literal["list_replace"]
    list: PlanList
    old: ItemText
    value: ItemText
    why: Why


class ListRemove(_Closed):
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


class QuestionAdd(_Closed):
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


class QuestionEdit(_Closed):
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


class QuestionRemove(_Closed):
    op: Literal["question_remove"]
    question_id: str = Field(min_length=1, max_length=120)
    why: Why


class SetN(_Closed):
    """A new sample size. Its shape asks only for a whole number; the range is the readiness
    limits in force (``design.readiness.sample_size`` in the Lead's context), which
    :func:`refusal` holds it to at the turn and :func:`apply_edit` again at its accept (plan
    ``run-qc-and-checkpoint`` RQC9). The schema keeps no range of its own: a second range is the
    drift RQC9 removed."""

    op: Literal["set_n"]
    value: int = Field(
        ge=1,
        description="Celý počet respondentů v rozsahu design.readiness.sample_size (min až max).",
    )
    why: Why


class RouteCondition(_Closed):
    """Who a question is for: those whose answer to the earlier choice question stored as
    ``question_id`` is one of ``options`` (``research_design.SpecCondition``'s stored form)."""

    question_id: str = Field(min_length=1, max_length=120)
    options: list[Option] = Field(min_length=1, max_length=40)


class RouteSet(_Closed):
    """A question's display condition set, changed or (``condition`` ``None``) removed (WCE13).
    Held to the compiler's own rule (``research_design.condition_refusal``) before it is
    written: an earlier choice question and answers it has. Not in the Lead's output
    (``in_lead_output`` false): a person sets it on Dotazník."""

    op: Literal["route_set"]
    question_id: str = Field(min_length=1, max_length=120)
    condition: RouteCondition | None
    why: Why


#: The operations the Lead's closed output carries (``research_lead.LeadOutput``).
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
#: Every operation this module applies: the Lead's, and those a person makes alone.
WorkingOp = Annotated[
    SetText
    | ListAdd
    | ListReplace
    | ListRemove
    | QuestionAdd
    | QuestionEdit
    | QuestionRemove
    | SetN
    | RouteSet,
    Field(discriminator="op"),
]

#: The edits that change wording and never structure or the sample: what a researcher may let the
#: Lead apply without a click (the preference ``auto_accept_text_edits``, plan inline-decisions
#: chunk 2). A ``question_edit`` is one only when it changes the text alone (:func:`is_text_edit`).
TEXT_EDIT_OPS: Final = frozenset({"set_text", "question_edit", "list_replace"})
#: The ``set_text`` fields whose edit changes their wording and nothing else. The brief's fields
#: (``goal``, ``decision_use``, ``briefing.*``) are not among them: ``apply_edit`` clears the
#: analysis made of the brief when one changes.
TEXT_ONLY_FIELDS: Final = frozenset({"title", "plan.problem_summary"})
#: The plan lists whose items are wording alone. ``plan.research_questions`` is not among them:
#: the questionnaire's items and the plan's comparisons name a research question by its text
#: (``domain/research_trace.py``), so renaming one unlinks what measures it. Nor is
#: ``plan.objectives``: where a plan states no research questions, its objectives are read as
#: them (``analysis/native.py`` ``research_questions_of``), with the same links by text.
TEXT_ONLY_LISTS: Final = frozenset({"plan.hypotheses"})


def is_text_edit(edit: BaseModel) -> bool:
    """Whether ``edit`` changes wording and nothing the design links to it: a ``set_text`` of the
    title or the problem summary, a ``list_replace`` of a hypothesis, or a ``question_edit`` that
    replaces the text and leaves the options as they are. Adding, removing, re-optioning or
    re-typing anything, the sample size, a brief field (it clears the analysis), a research
    question or an objective (items and comparisons name them by their text) are not.

    A question's new wording still decides how it is read after it: whether code answers it as
    a fact (``respondent_facts``) and which persona topics it draws (``persona_topics``). That is
    true of a clicked accept too; readiness and the question outlook show it before a run."""
    op = getattr(edit, "op", None)
    if op not in TEXT_EDIT_OPS:
        return False
    if isinstance(edit, QuestionEdit):
        return edit.text is not None and edit.options is None
    if isinstance(edit, SetText):
        return edit.field in TEXT_ONLY_FIELDS
    if isinstance(edit, ListReplace):
        return edit.list in TEXT_ONLY_LISTS
    return False


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


# --------------------------------------------------------------------------- applying an edit


class Refused(_Closed):
    """An edit the working content cannot take, and why (a stable word)."""

    reason: str


#: Top-level text fields whose edit changes the brief the analysis was made of, so the
#: analysis is cleared, as the web's ``editBrief`` does; a title edit keeps it.
_BRIEF_FIELDS: Final = frozenset({"goal", "decision_use"})
_NEW_SECTION_TITLE: Final = "Hlavní otázky"
_DEFAULT_SCALE_LABELS: Final = ("vůbec", "zcela")
_DEFAULT_CATEGORIES: Final = ("Ano", "Ne")


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


def _new_question(edit: QuestionAdd, new_id: Callable[[IdKind], str]) -> dict[str, Any]:
    qid = new_id(IdKind.QUESTION)
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
    content: Mapping[str, Any],
    analysis: Mapping[str, Any] | None,
    edit: Any,
    *,
    new_id: Callable[[IdKind], str] = new_item_id,
    sample_size: SampleSizeLimits | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None] | Refused:
    """One accepted Lead edit applied to the working content and analysis, by the web's rules.

    Returns the new content and analysis (copies; the inputs are not changed), or why the edit
    cannot be applied. A brief edit (``goal``, ``decision_use``, any ``briefing.*``) clears
    the analysis, which was made of the brief as it was; a title edit keeps it. A question
    edit's options replace only a selection question's categories, at least two of them;
    options on any other question are refused, never accepted as a change of nothing. The plan
    narrative (``plan.problem_summary`` and the plan lists) is written to both
    ``content.research_plan`` and the analysis (started from the plan when there is none),
    and marks ``ui_state.plan_manual_changed``. A ``set_n`` is refused unless it is a valid n
    under ``sample_size``, the readiness limits in force at the accept; with none given it is
    refused (``sample_size_limits_unknown``), never clamped and never presumed valid.
    """
    named = _named_refusal(edit)
    if named is not None:
        return Refused(reason=named)
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
                    "id": new_id(IdKind.SECTION),
                    "type": "questions",
                    "title": _NEW_SECTION_TITLE,
                    "purpose": "",
                    "questions": [],
                }
                listed.append(target)
        target["questions"] = [*list(target.get("questions") or []), _new_question(edit, new_id)]
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
        reason = sample_size_reason(edit.value, sample_size)
        if reason is not None:
            return Refused(reason=reason)
        body["n"] = edit.value
        return body, working
    if isinstance(edit, RouteSet):
        reason = _route_refusal(body, edit)
        if reason is not None:
            return Refused(reason=reason)
        found = _find_question(body, edit.question_id)
        if found is None:
            return Refused(reason="unknown_question")
        section, i = found
        questions = list(section.get("questions") or [])
        question = dict(questions[i])
        if edit.condition is None:
            question.pop("filtr", None)
        else:
            question["filtr"] = edit.condition.model_dump()
        questions[i] = question
        section["questions"] = questions
        return body, working
    return Refused(reason="unknown_edit")


def _route_refusal(content: Mapping[str, Any], edit: RouteSet) -> str | None:
    """Why ``edit`` cannot stand on ``content``: the question must be a stored one, and a
    condition one the compiler takes (``research_design.condition_refusal``)."""
    if edit.question_id not in _question_ids(content)[1]:
        return "unknown_question"
    if edit.condition is None:
        return None
    return condition_refusal(content, edit.question_id, edit.condition.model_dump())


def sample_size_reason(value: int, limits: SampleSizeLimits | None) -> str | None:
    """Why a ``set_n`` cannot be taken under ``limits``, or ``None`` when it can (RQC9): the one
    rule readiness reads (``research_design.sample_size_problem``); no limits known refuses."""
    if limits is None:
        return "sample_size_limits_unknown"
    problem = sample_size_problem(value, limits)
    return None if problem is None else problem.value


# --------------------------------------------------------------------------- the closed set


class OpName(StrEnum):
    """Every operation the working copy takes: today's eight, then the declared rest."""

    # Applied today: the Lead proposes them, a person accepts them (ADR 0026).
    SET_TEXT = "set_text"
    LIST_ADD = "list_add"
    LIST_REPLACE = "list_replace"
    LIST_REMOVE = "list_remove"
    QUESTION_ADD = "question_add"
    QUESTION_EDIT = "question_edit"
    QUESTION_REMOVE = "question_remove"
    SET_N = "set_n"
    # Declared: the questionnaire's manual operations (WCE3b), by stable id (WCE1).
    QUESTION_MOVE = "question_move"
    QUESTION_MERGE = "question_merge"
    SECTION_ADD = "section_add"
    SECTION_EDIT = "section_edit"
    SECTION_REMOVE = "section_remove"
    SECTION_MOVE = "section_move"
    LINK_SET = "link_set"
    SCALE_SET = "scale_set"
    ROUTE_SET = "route_set"
    STIMULUS_SET = "stimulus_set"
    # Declared: the plan's comparable measurements and comparisons (WCE3a).
    SET_ADD = "set_add"
    SET_EDIT = "set_edit"
    SET_REMOVE = "set_remove"
    COMPARISON_SET = "comparison_set"
    # Declared: the audience, the dimensions (WCE10); the sample's size is set_n.
    AUDIENCE_SET = "audience_set"
    DIMENSIONS_SET = "dimensions_set"
    # Declared: the Sociomap's declarations (WCE8).
    SOCIOMAP_DECLARE = "sociomap_declare"
    # Declared: tracked assumptions (assumptions-and-open-answer-coding AOC1).
    ASSUMPTION_ADD = "assumption_add"
    ASSUMPTION_EDIT = "assumption_edit"
    ASSUMPTION_LINK = "assumption_link"
    ASSUMPTION_SET_STATUS = "assumption_set_status"
    # Declared: every other writer of the working copy, recorded as one operation (WCE2).
    WHOLE_COPY = "whole_copy"


class ItemKind(StrEnum):
    """What an operation addresses: ``design_items``' kinds, and the kinds its chunks add."""

    BRIEF = "brief"
    PLAN = "plan"
    OBJECTIVE = "objective"
    RESEARCH_QUESTION = "research_question"
    HYPOTHESIS = "hypothesis"
    TRACKED_SET = "tracked_set"
    SECTION = "section"
    QUESTION = "question"
    BATTERY = "battery"
    AUDIENCE = "audience"
    DIMENSIONS = "dimensions"
    N = "n"
    ASSUMPTION = "assumption"
    STIMULUS = "stimulus"
    #: The working copy as a whole: a whole-copy write's items are what it changed.
    COPY = "copy"


class TextRuling(StrEnum):
    """Whether an operation is a text edit: wording only, nothing linked to it changed."""

    #: Never a text edit: it adds, removes, moves, re-options, re-types or resizes.
    STRUCTURAL = "structural"
    #: A text edit for some payloads only; :func:`is_text_edit` decides per edit, and an
    #: operation without its payload yet (declared) is never one.
    BY_PAYLOAD = "by_payload"


class Availability(StrEnum):
    #: Its payload and its apply are in this module.
    APPLIED = "applied"
    #: Named and ruled on; refused (``op_not_available``) until its chunk lands.
    DECLARED = "declared"


@dataclass(frozen=True, slots=True)
class OpSpec:
    """One operation of the vocabulary."""

    name: OpName
    kinds: tuple[ItemKind, ...]
    #: The fields it writes, as :func:`touches` names them; ``item`` is the item's existence.
    fields: tuple[str, ...]
    text: TextRuling
    #: Whether it can change a Sociomap input (so the lock is asked).
    may_touch_locked: bool
    #: Whether the Lead's closed output (``research_lead.LeadOutput``) carries it today. Widening
    #: the Lead's vocabulary is its own versioned change (WCE10), never implied by this list.
    in_lead_output: bool
    availability: Availability
    #: The chunk that gives it its payload and its apply, or that owns it today.
    chunk: str


def _spec(
    name: OpName,
    kinds: tuple[ItemKind, ...],
    fields: tuple[str, ...],
    text: TextRuling,
    *,
    locked: bool,
    chunk: str,
    lead: bool = False,
    applied: bool = False,
) -> OpSpec:
    return OpSpec(
        name=name,
        kinds=kinds,
        fields=fields,
        text=text,
        may_touch_locked=locked,
        in_lead_output=lead,
        availability=Availability.APPLIED if applied else Availability.DECLARED,
        chunk=chunk,
    )


_K = ItemKind
_S, _P = TextRuling.STRUCTURAL, TextRuling.BY_PAYLOAD
_PLAN_LISTS = (_K.OBJECTIVE, _K.RESEARCH_QUESTION, _K.HYPOTHESIS)
_NOW = "ADR 0026 (the Lead's edits)"

#: The closed operation set, one entry per :class:`OpName`.
CATALOGUE: Final[Mapping[OpName, OpSpec]] = MappingProxyType(
    {
        s.name: s
        for s in (
            _spec(OpName.SET_TEXT, (_K.BRIEF, _K.PLAN), ("text",), _P, locked=False,
                  chunk=_NOW, lead=True, applied=True),
            _spec(OpName.LIST_ADD, _PLAN_LISTS, ("item",), _S, locked=False,
                  chunk=_NOW, lead=True, applied=True),
            _spec(OpName.LIST_REPLACE, _PLAN_LISTS, ("text",), _P, locked=False,
                  chunk=_NOW, lead=True, applied=True),
            _spec(OpName.LIST_REMOVE, _PLAN_LISTS, ("item",), _S, locked=False,
                  chunk=_NOW, lead=True, applied=True),
            _spec(OpName.QUESTION_ADD, (_K.SECTION, _K.QUESTION), ("questions", "item"), _S,
                  locked=False, chunk=_NOW, lead=True, applied=True),
            _spec(OpName.QUESTION_EDIT, (_K.QUESTION,), ("text", "kategorie"), _P,
                  locked=True, chunk=_NOW, lead=True, applied=True),
            _spec(OpName.QUESTION_REMOVE, (_K.QUESTION, _K.SECTION), ("item", "questions"), _S,
                  locked=True, chunk=_NOW, lead=True, applied=True),
            _spec(OpName.SET_N, (_K.N,), ("value",), _S, locked=False,
                  chunk=_NOW, lead=True, applied=True),
            _spec(OpName.QUESTION_MOVE, (_K.QUESTION, _K.SECTION), ("questions",), _S,
                  locked=True, chunk="WCE3b"),
            _spec(OpName.QUESTION_MERGE, (_K.QUESTION, _K.SECTION), ("item", "questions"), _S,
                  locked=True, chunk="WCE3b"),
            _spec(OpName.SECTION_ADD, (_K.SECTION, _K.BATTERY), ("item",), _S,
                  locked=False, chunk="WCE3b"),
            _spec(OpName.SECTION_EDIT, (_K.SECTION, _K.BATTERY), ("title", "purpose", "objects"),
                  _P, locked=True, chunk="WCE3b"),
            _spec(OpName.SECTION_REMOVE, (_K.SECTION, _K.BATTERY), ("item",), _S,
                  locked=True, chunk="WCE3b"),
            _spec(OpName.SECTION_MOVE, (_K.SECTION, _K.BATTERY), ("order",), _S,
                  locked=False, chunk="WCE3b"),
            _spec(OpName.LINK_SET, (_K.QUESTION, _K.BATTERY), ("research_questions",), _S,
                  locked=False, chunk="WCE3b"),
            _spec(OpName.SCALE_SET, (_K.QUESTION, _K.BATTERY), ("scale", "scale_labels"), _S,
                  locked=True, chunk="WCE3b"),
            _spec(OpName.ROUTE_SET, (_K.QUESTION,), ("filtr",), _S,
                  locked=True, chunk="WCE13", applied=True),
            _spec(OpName.STIMULUS_SET, (_K.QUESTION, _K.STIMULUS), ("context",), _S,
                  locked=True, chunk="WCE14"),
            _spec(OpName.SET_ADD, (_K.TRACKED_SET,), ("item",), _S,
                  locked=False, chunk="WCE3a"),
            _spec(OpName.SET_EDIT, (_K.TRACKED_SET,), ("title", "purpose", "objects"), _P,
                  locked=False, chunk="WCE3a"),
            _spec(OpName.SET_REMOVE, (_K.TRACKED_SET,), ("item",), _S,
                  locked=False, chunk="WCE3a"),
            _spec(OpName.COMPARISON_SET, (_K.PLAN,), ("research_question_comparisons",), _S,
                  locked=False, chunk="WCE3a"),
            _spec(OpName.AUDIENCE_SET, (_K.AUDIENCE,), ("description", "filters"), _S,
                  locked=False, chunk="WCE10"),
            _spec(OpName.DIMENSIONS_SET, (_K.DIMENSIONS,), ("approved",), _S,
                  locked=False, chunk="WCE10"),
            _spec(OpName.SOCIOMAP_DECLARE, (_K.QUESTION, _K.BATTERY),
                  ("sociomap_rating", "context_objects"), _S, locked=True, chunk="WCE8"),
            _spec(OpName.ASSUMPTION_ADD, (_K.ASSUMPTION,), ("item",), _S,
                  locked=False, chunk="AOC1"),
            _spec(OpName.ASSUMPTION_EDIT, (_K.ASSUMPTION,), ("statement",), _P,
                  locked=False, chunk="AOC1"),
            _spec(OpName.ASSUMPTION_LINK, (_K.ASSUMPTION,), ("links",), _S,
                  locked=False, chunk="AOC1"),
            _spec(OpName.ASSUMPTION_SET_STATUS, (_K.ASSUMPTION,), ("status",), _S,
                  locked=False, chunk="AOC1"),
            _spec(OpName.WHOLE_COPY, (_K.COPY,), ("*",), _S, locked=True, chunk="WCE2"),
        )
    }
)  # fmt: skip

#: Every word an operation is refused with, here and by the web (the case file reads them).
REFUSALS: Final = frozenset(
    {
        "already_present",
        "briefing_not_an_object",
        "condition_ambiguous_question",
        "condition_forward_reference",
        "condition_not_choice",
        "condition_unknown_option",
        "condition_unknown_question",
        "condition_unstructured",
        "op_not_available",
        "options_on_non_selection",
        "options_on_open_question",
        "plan_not_an_object",
        "sample_size_limits_unknown",
        "sample_size_out_of_range",
        "scale_labels_not_two",
        "sections_not_a_list",
        "sociomap_input_locked",
        "too_few_options",
        "unknown_edit",
        "unknown_item",
        "unknown_question",
        "unknown_question_type",
        "unknown_section",
    }
)


def spec_of(name: str) -> OpSpec | None:
    """The vocabulary's entry for ``name``, or ``None``: no such operation."""
    try:
        return CATALOGUE[OpName(name)]
    except ValueError:
        return None


# --------------------------------------------------------------------------- validation


def op_refusal(name: str) -> str | None:
    """Why an operation named ``name`` cannot be applied at all: ``unknown_edit`` when the
    vocabulary has no such operation, ``op_not_available`` when it declares one whose chunk has
    not landed; ``None`` for an operation this module applies."""
    spec = spec_of(name)
    if spec is None:
        return "unknown_edit"
    return "op_not_available" if spec.availability is Availability.DECLARED else None


def _named_refusal(edit: object) -> str | None:
    """:func:`op_refusal` of whatever ``edit`` names as its ``op``: the first question every
    entry point asks, so a declared operation is ``op_not_available`` everywhere."""
    op = getattr(edit, "op", None)
    return op_refusal(op) if isinstance(op, str) else "unknown_edit"


def refusal(
    edit: BaseModel,
    content: Mapping[str, Any],
    analysis: Mapping[str, Any] | None = None,
    *,
    sample_size: SampleSizeLimits | None = None,
) -> str | None:
    """Why ``edit`` cannot apply to the working copy, as a word of :data:`REFUSALS`, or ``None``.

    A question or section id must be one of a questions section; a list item's ``old`` must be in
    its plan list (the working analysis first, else ``content.research_plan``), compared
    whitespace-collapsed and casefolded, and a ``list_add`` already there is refused; a new
    question must be one its type can carry; options replace only a selection question's. This is
    the grounding the Lead's edits pass (``research_lead.ground_edits``), and :func:`apply_edit`
    refuses with the same words. A ``set_n`` must be a valid n under ``sample_size``, the readiness
    limits in force (:func:`sample_size_reason`); with none given it is refused, never presumed
    valid. The lock is asked separately (:func:`lock_refusal`)."""
    named = _named_refusal(edit)
    if named is not None:
        return named
    sections, questions = _question_ids(content)
    if isinstance(edit, QuestionEdit | QuestionRemove):
        if edit.question_id not in questions:
            return "unknown_question"
        if (
            isinstance(edit, QuestionEdit)
            and edit.options is not None
            and questions[edit.question_id] not in _SELECTION
        ):
            return "options_on_non_selection"
        return None
    if isinstance(edit, QuestionAdd):
        if edit.section_id is not None and edit.section_id not in sections:
            return "unknown_section"
        return question_add_problem(edit.qtype, edit.options)
    if isinstance(edit, ListReplace | ListRemove):
        items = {_key(str(x)) for x in _plan_list(content, analysis, edit.list)}
        return None if _key(edit.old) in items else "unknown_item"
    if isinstance(edit, ListAdd):
        items = {_key(str(x)) for x in _plan_list(content, analysis, edit.list)}
        return "already_present" if _key(edit.value) in items else None
    if isinstance(edit, SetN):
        return sample_size_reason(edit.value, sample_size)
    if isinstance(edit, RouteSet):
        return _route_refusal(content, edit)
    if isinstance(edit, SetText):
        return None
    return "unknown_edit"


# --------------------------------------------------------------------------- what it touches

#: The ids :func:`touches` names an added item by when the caller gives none: the kind's prefix
#: and ``new``. A caller that will apply the edit passes the ``new_id`` it applies it with.
_PLACEHOLDER: Final[Callable[[IdKind], str]] = lambda kind: ID_PREFIX[IdKind(kind)] + "new"  # noqa: E731
#: What an operation changes besides what a person wrote: the stages' own state.
_CONSEQUENCES: Final = frozenset({ItemKey("content", "field", "ui_state")})
_APPLIED_TYPES: Final = (SetText, ListAdd, ListReplace, ListRemove, QuestionAdd, QuestionEdit,
                         QuestionRemove, SetN, RouteSet)  # fmt: skip


def touches(
    edit: BaseModel,
    content: Mapping[str, Any],
    *,
    new_id: Callable[[IdKind], str] = _PLACEHOLDER,
) -> frozenset[Touch]:
    """Every ``(item key, field)`` ``edit`` writes in the working copy ``content`` (D-06).

    Exactly what applying it changes: the edit is applied to ``content`` with its ids written in
    (:mod:`.item_ids`) and the two are compared field by field (:mod:`.design_fields`), so the keys
    are the items' stable ids, the same ``design_items`` and :func:`locked_items` use. A reworded
    list entry touches its one item's ``text``; an added item (a question, a list entry, the
    section a first question creates) touches its own ``item`` and nothing of its section or list,
    so two people adding to one section touch different keys; a removed one its ``item``. An added
    item is named by ``new_id`` (by default a placeholder, ``Q_new``). The stages' own state
    (``ui_state``), which an edit of the plan also marks, is not listed; nor is the analysis a
    brief edit clears (:func:`apply_edit`): consequences of the edit, not what a person wrote. An
    edit the copy refuses touches nothing."""
    if not isinstance(edit, _APPLIED_TYPES):
        raise TypeError(f"not an operation the vocabulary applies: {type(edit).__name__}")
    base, _ = with_item_ids(content)
    if isinstance(edit, SetN):
        # What a sample size writes does not depend on the limits it is checked against
        # (``apply_edit``'s ``sample_size``): a value out of range is refused there, not untouched.
        after: dict[str, Any] = {**base, "n": edit.value}
    else:
        applied = apply_edit(base, None, edit, new_id=new_id)
        if isinstance(applied, Refused):
            return frozenset()
        after = applied[0]
    changed = changed_fields(Documents(content=base), Documents(content=after))
    return frozenset(t for t in changed if t[0] not in _CONSEQUENCES)


# --------------------------------------------------------------------------- the lock


def declares_sociomap_inputs(content: Mapping[str, Any]) -> bool:
    """Whether the design declares a Sociomap input: a question marked ``sociomap_rating``, or a
    tracked set (an ``object_battery`` section) that declares its ``context_objects``. These are
    the declarations ``research_design`` compiles (``rating_item``, ``roles_declared``)."""
    for section in content.get("sections") or ():
        if not isinstance(section, Mapping):
            continue
        if section.get("type") == "object_battery" and "context_objects" in section:
            return True
        for question in section.get("questions") or ():
            if isinstance(question, Mapping) and question.get("sociomap_rating") is True:
                return True
    return False


def locked_items(content: Mapping[str, Any]) -> frozenset[ItemKey]:
    """The items a declared Sociomap reads, locked (the owner's D-30, ADR 0029 decision 8).

    Nothing is locked until the design declares an input. Then: every question marked
    ``sociomap_rating`` and every tracked set of the questionnaire (each ``object_battery``
    section), because the map rates every set's objects and every declared rating question
    together (``research_sociomap.rating_universe`` over ``spec.batteries``). The plan's own
    ``tracked_sets`` are not locked: the map is compiled from the questionnaire's sections alone
    (``research_design.compile_design``), so nothing the map reads is in them. Keys are
    ``design_items``', so a whole-copy write's changed items are compared on the same keys."""
    if not declares_sociomap_inputs(content):
        return frozenset()
    locked: set[ItemKey] = set()
    for key, value in item_values(Documents(content=dict(content))).items():
        if key.document != "content":
            continue
        rating = isinstance(value, Mapping) and value.get("sociomap_rating") is True
        if key.kind == "battery" or (key.kind == "question" and rating):
            locked.add(key)
    return frozenset(locked)


def lock_refusal(
    edit: BaseModel, content: Mapping[str, Any], *, unlocked: bool = False
) -> str | None:
    """``sociomap_input_locked`` when ``edit`` writes a locked item of ``content`` and its batch
    carries no unlock; else ``None``. An operation the vocabulary cannot apply is refused first,
    with :func:`op_refusal`'s word, as :func:`refusal` and :func:`apply_edit` refuse it.
    ``unlocked`` is a person's recorded ``sociomap_unlock`` for
    this working revision (WCE8): the Lead can never supply one."""
    named = _named_refusal(edit)
    if named is not None:
        return named
    if unlocked:
        return None
    locked = locked_items(content)
    if not locked:
        return None
    hit = {key for key, _ in touches(edit, content)} & locked
    return "sociomap_input_locked" if hit else None


def whole_copy_lock_refusal(
    before: Documents | Mapping[str, Any],
    after: Documents | Mapping[str, Any],
    *,
    unlocked: bool = False,
) -> str | None:
    """``sociomap_input_locked`` when a whole-copy write (the PUT, an import, a reuse, a
    migration, an accept, an autosave: WCE2) changes an item ``before`` had locked, without an
    unlock; else ``None``. The changed items are ``design_items``' difference, so a write that
    leaves every locked item as it was passes whatever else it changes."""
    if unlocked:
        return None
    base = before if isinstance(before, Documents) else Documents.of(before)
    locked = locked_items(base.content)
    if not locked:
        return None
    return "sociomap_input_locked" if changed_items(base, after) & locked else None
