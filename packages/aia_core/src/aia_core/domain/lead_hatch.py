"""Hatching a researcher's Lead (lead-identity LI1): what the person writes, what the model
returns, and the checks between them. Pure: stdlib and Pydantic.

The product owner, 2026-10-25: the model writes the Lead's SOUL and USER at hatching, never code
instead; the person sees them and accepts before they are kept (ADR 0030 decision 2); a Lead is
hatched once.

* :class:`HatchInput` is what the person writes: the name, four traits, how it should work and
  about them. Its class is ``MaterialRule.LEAD_HATCH`` (Class C).
* :class:`HatchOutput` is the request's closed answer: the two files and the first greeting,
  each bounded as a Lead file is (``research_lead.SOUL_MAX_BYTES`` / ``USER_MAX_BYTES``).
* :func:`hatch_refusals` is ADR 0030 decision 3's check of a personal file, which no other code
  ran before this: a text naming any client of the organization, or a number, is refused
  (``client_fact_in_personal_file``). A personal file goes into every client's studies; a client
  fact belongs in a client note. The person still sees the files before they are kept, which
  covers what no check catches.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .research_lead import (
    NAME_MAX_CHARS,
    SOUL_MAX_BYTES,
    SOUL_MAX_CHARS,
    USER_MAX_BYTES,
    USER_MAX_CHARS,
)

__all__ = [
    "ABOUT_MAX_CHARS",
    "BRIEF_MAX_BYTES",
    "BRIEF_MAX_CHARS",
    "GREETING_MAX_CHARS",
    "NAME_MAX_BYTES",
    "HatchInput",
    "HatchOutput",
    "HatchRefusal",
    "Traits",
    "hatch_refusals",
    "personal_text_refusal",
]

#: The name as the hatch takes it: the Lead's name bound in characters, and in bytes so a
#: four-byte name cannot overflow its layer.
NAME_MAX_BYTES: Final = 160
#: "Jak má pracovat": what the person writes about how the Lead should work.
BRIEF_MAX_CHARS: Final = 1500
#: Bytes as well, so a brief of multibyte text keeps the request within its window.
BRIEF_MAX_BYTES: Final = 3000
#: "O vás": optional, what the Lead should know about them.
ABOUT_MAX_CHARS: Final = USER_MAX_CHARS
#: The Lead's first words, stored as its first turn when the files are accepted.
GREETING_MAX_CHARS: Final = 600


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Traits(_Closed):
    """The four choices of the hatching's second step, each one of two (the artboard)."""

    tone: Literal["vecny", "vrely"]
    answers: Literal["strucne", "podrobne"]
    initiative: Literal["ceka", "navrhuje"]
    numbers: Literal["vzdy_nejistota", "jen_dulezita"]


def _within_bytes(value: str, limit: int, what: str) -> str:
    if len(value.encode("utf-8")) > limit:
        raise ValueError(f"{what} is over {limit} bytes of UTF-8")
    return value


class HatchInput(_Closed):
    """What a researcher writes when hatching their Lead (``MaterialRule.LEAD_HATCH``)."""

    name: str = Field(min_length=1, max_length=NAME_MAX_CHARS)
    traits: Traits
    brief: str = Field(default="", max_length=BRIEF_MAX_CHARS)
    about: str = Field(default="", max_length=ABOUT_MAX_CHARS)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("the name is empty")
        return _within_bytes(value, NAME_MAX_BYTES, "the name")

    @field_validator("brief")
    @classmethod
    def _brief(cls, value: str) -> str:
        return _within_bytes(value.strip(), BRIEF_MAX_BYTES, "the brief")

    @field_validator("about")
    @classmethod
    def _about(cls, value: str) -> str:
        return _within_bytes(value.strip(), USER_MAX_BYTES, "about")


class HatchOutput(_Closed):
    """The hatch request's closed answer. Nothing in it is kept until the person accepts."""

    soul: str = Field(min_length=1, max_length=SOUL_MAX_CHARS)
    user: str = Field(default="", max_length=USER_MAX_CHARS)
    greeting: str = Field(min_length=1, max_length=GREETING_MAX_CHARS)

    @field_validator("soul")
    @classmethod
    def _soul(cls, value: str) -> str:
        return _within_bytes(value, SOUL_MAX_BYTES, "SOUL")

    @field_validator("user")
    @classmethod
    def _user(cls, value: str) -> str:
        return _within_bytes(value, USER_MAX_BYTES, "USER")


HatchRefusal = Literal["client_fact_in_personal_file"]

#: A number as a person writes one: a digit, alone or in a group. Ids such as ``Q3`` are not
#: numbers here either; a personal file has no ids to write.
_NUMBER: Final = re.compile(r"(?<![^\W\d_])\d")


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _names(text: str, client_names: Iterable[str]) -> bool:
    folded = _fold(text)
    for name in client_names:
        needle = _fold(name).strip()
        if needle and re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", folded):
            return True
    return False


def personal_text_refusal(text: str, client_names: Iterable[str]) -> HatchRefusal | None:
    """ADR 0030 decision 3: a personal text naming any client of the organization, or holding a
    number, is refused. Names are matched whole, accent-folded and case-folded."""
    if _NUMBER.search(text) or _names(text, client_names):
        return "client_fact_in_personal_file"
    return None


def hatch_refusals(output: HatchOutput, client_names: Iterable[str]) -> dict[str, HatchRefusal]:
    """Each file of ``output`` that :func:`personal_text_refusal` refuses, by file. The greeting
    is checked too: it becomes the Lead's first turn in every client's studies."""
    names = tuple(client_names)
    found: dict[str, HatchRefusal] = {}
    for field in ("soul", "user", "greeting"):
        reason = personal_text_refusal(getattr(output, field), names)
        if reason is not None:
            found[field] = reason
    return found
