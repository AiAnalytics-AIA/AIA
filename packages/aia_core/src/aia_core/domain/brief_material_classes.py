"""The class of each material a Brief carries, as Podklady shows it (artifact-brief BRF3).

V2's Podklady prints a data-class chip beside every material, with the aside "třída dat určuje,
kam smí". The class is the code's and the owner's decision (:mod:`aia_core.domain.material_rules`),
never the browser's: this module answers it for each entry of ``briefing.attachments`` so the
screen only prints what it is told.

A Brief's file and link are the study's design (``MaterialRule.DESIGN``: "the attachment excerpts
the design carries"), Class B by rule. What an operator's exact-bytes classification would raise
is not known here: approvals are the worker's (``material_approvals``), applied to the design as a
whole when it is sent, and they only ever raise a class. So the answer is the rule's class and the
rule as its source -- the least strict class the material can leave under, never a claim that it
was not raised.

An entry that is not a file or a link record has no rule and no class: ``data_class`` is ``None``
and the screen says "třída neznámá" (never C, never guessed).

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .material_rules import MaterialRule, rule_class
from .residency import DataClass

__all__ = ["BriefMaterialClass", "brief_material_classes"]


class BriefMaterialClass(BaseModel):
    """One entry of ``briefing.attachments`` and the class its rule gives it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: The entry's position in ``briefing.attachments``.
    index: int
    kind: Literal["file", "url"] | None
    #: The file's ``attachment_id`` or the link's ``url``; ``None`` when the entry names neither.
    ref: str | None
    #: ``None``: no rule names this entry, so its class is unknown.
    data_class: DataClass | None
    #: ``rule:<name>``; ``None`` with an unknown class.
    class_source: str | None


def _ref(entry: Mapping[str, Any], key: str) -> str | None:
    value = entry.get(key)
    return value if isinstance(value, str) and value else None


def _classified(index: int, entry: Any) -> BriefMaterialClass:
    if isinstance(entry, Mapping):
        kind = entry.get("kind", "file")
        if kind == "file":
            return _ruled(index, "file", _ref(entry, "attachment_id"))
        if kind == "url" and _ref(entry, "url"):
            return _ruled(index, "url", _ref(entry, "url"))
    return BriefMaterialClass(index=index, kind=None, ref=None, data_class=None, class_source=None)


def _ruled(index: int, kind: Literal["file", "url"], ref: str | None) -> BriefMaterialClass:
    rule = MaterialRule.DESIGN
    return BriefMaterialClass(
        index=index, kind=kind, ref=ref, data_class=rule_class(rule), class_source=rule.value
    )


def brief_material_classes(content: Mapping[str, Any] | None) -> list[BriefMaterialClass]:
    """Every entry of the working content's ``briefing.attachments``, in order, with its class.

    No content, no briefing or no attachments: an empty list.
    """
    briefing = (content or {}).get("briefing")
    entries = briefing.get("attachments") if isinstance(briefing, Mapping) else None
    if not isinstance(entries, list):
        return []
    return [_classified(i, entry) for i, entry in enumerate(entries)]
