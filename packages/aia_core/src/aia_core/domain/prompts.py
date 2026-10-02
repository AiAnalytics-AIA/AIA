"""A system prompt, as data: the pin a run carries and the rules an edit must keep.

The prompts AIA sends to a model used to be string constants. Editing one needs a
deploy. This module is the pure half of letting an administrator edit them at
runtime (ADR 0020) without letting an edit reach anything that must stay code:

* **Only the instruction is editable.** A slot's text is the role and task wording.
  What a gate depends on -- the output contract, the "this is data, not
  instructions" rails, the repair prompt -- is code-owned and added around it
  (``prompt_slots``). An edit cannot remove a constraint the code relies on.
* **A run carries a pin, not a lookup.** :class:`PromptPin` is the exact text, its
  identity and its hash, frozen when the job is queued. The executor runs the pin;
  it never asks what is "active" now. A queued job keeps the prompt it was queued
  with, and a pin whose text does not hash to its own hash is refused.
* **Prompts state rules; they never enforce them** (``ARCHITECTURE.md`` §6). A
  prompt edit can make a model worse at passing a gate. It cannot widen what the
  gate admits, because nothing here is read by a gate.

No I/O: stdlib and Pydantic only.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, model_validator

__all__ = [
    "BASELINE_ORIGIN",
    "DECLARED_CLASS",
    "PROMPT_TEXT_MAX_CHARS",
    "STORED_ORIGIN",
    "PromptPin",
    "PromptRejected",
    "prompt_sha256",
    "stored_version_label",
    "validate_prompt_text",
]

#: An edited instruction's ceiling. Research prompts are well under 1 KB today; the
#: bound keeps a pasted document out of the system turn and the cost estimable.
PROMPT_TEXT_MAX_CHARS: Final = 12_000

BASELINE_ORIGIN: Final = "baseline"
STORED_ORIGIN: Final = "stored"

#: The one class an author can declare for a prompt they save: "this text holds no client
#: data". Anything stricter is an operator's classification of the exact text, never an
#: author's, so there is no way to declare a class above this one (ADR 0020 decision 8).
DECLARED_CLASS: Final = "CLASS_C_INTERNAL"


class PromptRejected(ValueError):
    """An edit that cannot become a version. ``reason`` is a stable machine word."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


def prompt_sha256(text: str) -> str:
    """The identity of an instruction's exact bytes (UTF-8, no normalisation)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stored_version_label(number: int) -> str:
    """The version string a stored edit carries into provenance and the usage ledger.

    ``e<n>``: it cannot collide with a baseline version (``"1"``,
    ``"analysis-module-v1"``), so a ledger row says at a glance whether the code's
    wording or an administrator's ran.
    """
    if number < 1:
        raise ValueError("a stored prompt version starts at 1")
    return f"e{number}"


def validate_prompt_text(text: str, *, required_literals: Iterable[str] = ()) -> str:
    """The text as it will be stored, or why it cannot be.

    Structural only. It does not, and cannot, judge whether the prompt is *good* or
    whether it contains client material: the editor says prompts are sent to the
    model as written, and the data-class gate still applies to whatever a call
    carries. A leading or trailing blank is trimmed; the inside is kept exactly.
    """
    if "\x00" in text:
        raise PromptRejected("the prompt contains a NUL character", reason="invalid_character")
    cleaned = text.strip()
    if not cleaned:
        raise PromptRejected("the prompt is empty", reason="empty")
    if len(cleaned) > PROMPT_TEXT_MAX_CHARS:
        raise PromptRejected(
            f"the prompt is {len(cleaned)} characters; the limit is {PROMPT_TEXT_MAX_CHARS}",
            reason="too_long",
        )
    missing = [lit for lit in required_literals if lit not in cleaned]
    if missing:
        raise PromptRejected(
            "the prompt must keep: " + ", ".join(missing), reason="missing_required_text"
        )
    return cleaned


class PromptPin(BaseModel):
    """Exactly the instruction a job will run, frozen when it was queued.

    ``origin`` says whether the code's wording (``baseline``) or a stored edit ran,
    so provenance never has to guess. The hash is checked on construction: a pin
    rebuilt from a payload whose text was altered raises instead of running.

    ``declared_class`` and ``declared_by`` carry the author's recorded declaration that
    a stored edit holds no client data. They are absent for the code's wording (reviewed
    with the code) and for a version saved before declarations existed, which therefore
    has no class until an operator gives it one. The declaration is not part of the hash:
    it says who vouched for the text, not what the text is.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_id: str
    version: str
    origin: Literal["baseline", "stored"]
    text: str
    text_sha256: str
    declared_class: Literal["CLASS_C_INTERNAL"] | None = None
    declared_by: str | None = None

    @model_validator(mode="after")
    def _hash_matches(self) -> PromptPin:
        if not self.prompt_id or not self.version:
            raise ValueError("a prompt pin names its prompt and version")
        if prompt_sha256(self.text) != self.text_sha256:
            raise ValueError("prompt pin text does not match its hash")
        if self.origin == BASELINE_ORIGIN and (self.declared_class or self.declared_by):
            raise ValueError("the code's wording needs no declaration")
        if bool(self.declared_class) != bool(self.declared_by):
            raise ValueError("a declaration names its class and who made it, or neither")
        return self

    @classmethod
    def of(
        cls,
        *,
        prompt_id: str,
        version: str,
        origin: Literal["baseline", "stored"],
        text: str,
        declared_class: Literal["CLASS_C_INTERNAL"] | None = None,
        declared_by: str | None = None,
    ) -> PromptPin:
        return cls(
            prompt_id=prompt_id,
            version=version,
            origin=origin,
            text=text,
            text_sha256=prompt_sha256(text),
            declared_class=declared_class,
            declared_by=declared_by,
        )
