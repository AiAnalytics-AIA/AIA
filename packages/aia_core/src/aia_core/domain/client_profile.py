"""A client's profile and its contacts (client-workspace C5, decision D5).

The profile is part of the client record: a short code, the industry, the market and a
few sentences about the client, for the people who work with it. Contacts are the people
at the client who receive results. Neither is Client Knowledge: no study context, prompt
or model request reads them, and changing them writes no knowledge revision. The client's
brands and competitors are not here; they are ENTITY items of the client's knowledge,
because studies use them.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import re
from typing import Final
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "PROFILE_LIMITS",
    "ClientContact",
    "ClientProfile",
    "ContactDraft",
    "new_contact_id",
]

#: The most each profile field may hold, in characters.
PROFILE_LIMITS: Final[dict[str, int]] = {
    "short_code": 16,
    "industry": 120,
    "market": 120,
    "description": 4000,
}

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def new_contact_id() -> str:
    """``CON-`` followed by 14 hex characters."""
    return f"CON-{uuid4().hex[:14]}"


def _line(value: str) -> str:
    return " ".join(value.split())


class ClientProfile(BaseModel):
    """What the client record says about the client beyond its name and status.

    Every field may be empty: an empty field is "not filled in", never a guess.
    One-line fields are trimmed with inner whitespace collapsed; the description
    keeps its line breaks and loses only surrounding whitespace.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    short_code: str = Field(default="", max_length=PROFILE_LIMITS["short_code"])
    industry: str = Field(default="", max_length=PROFILE_LIMITS["industry"])
    market: str = Field(default="", max_length=PROFILE_LIMITS["market"])
    description: str = Field(default="", max_length=PROFILE_LIMITS["description"])

    @field_validator("short_code", "industry", "market", mode="before")
    @classmethod
    def _one_line(cls, value: object) -> object:
        return _line(value) if isinstance(value, str) else value

    @field_validator("description", mode="before")
    @classmethod
    def _trimmed(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ContactDraft(BaseModel):
    """A contact as a person writes it: a name is required, the rest may be empty."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="", max_length=120)
    email: str = Field(default="", max_length=254)
    receives_reports: bool = False

    @field_validator("name", "role", "email", mode="before")
    @classmethod
    def _one_line(cls, value: object) -> object:
        return _line(value) if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        if value and not _EMAIL.match(value):
            raise ValueError("not an e-mail address")
        return value


class ClientContact(ContactDraft):
    """A person at the client, kept on the client record and read by no model."""

    contact_id: str
    client_id: str
