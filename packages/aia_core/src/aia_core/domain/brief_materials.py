"""The Brief's materials: a client dataset a study names, and what it may be used for.

**PROPOSED interface** (plan ``client-data-in-analysis`` chunk 8a, W0). ADR 0027 is still
Proposed and no data contract exists yet (chunk 2): this module fixes the shape a Brief stores,
what ``brief_signature`` signs of it and the one rule that decides whether an attached dataset
may feed analysis, so the W1 Brief UI (``research-lead-workbench`` 18) and chunks 2, 8 and 9 build
against one interface. It is to be reviewed with S1 before workbench 18; chunk 8 implements the
accepted version.

**A Brief material** (:class:`BriefMaterial`, stored in ``briefing.materials``, a list beside the
legacy ``briefing.attachments``):

- ``kind`` -- ``client_dataset``: one of the study's client's sources (``client_sources``), named,
  never copied: the Brief holds no row, no column and no file.
- ``source_id`` -- the client source (``SRC-`` and 16 hex characters).
- ``reading_sha256`` -- the SHA-256 of the source's reading the person picked, as the client's
  source repository stores it: a newer reading of the same file is a different material.
- ``contract_id`` / ``contract_version`` -- the data contract the person intends to use it under,
  both or neither (chunk 2 issues them). Naming a contract is an intent, not an acceptance.

**No eligibility is stored.** A material carries no use, eligibility or admission state: the
model is closed (``extra="forbid"``), so an entry claiming one is refused when read, and
``brief_signature`` signs only the four fields above, so a browser that writes ``"eligible"`` or
``"admitted": true`` beside an entry changes nothing a server reads. Eligibility is computed, here,
from the accepted contracts the server holds (:func:`eligibility_of`): a dataset with no accepted
contract is :attr:`Eligibility.NO_CONTRACT` -- visible as a source, unavailable to analysis -- and
no contract is accepted anywhere until chunk 2 exists. **No client dataset is admitted by being
attached.**

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, model_validator

__all__ = [
    "BRIEF_MATERIALS_VERSION",
    "AcceptedContract",
    "BriefMaterial",
    "Eligibility",
    "MaterialProblem",
    "eligibility_of",
    "material_signature",
    "read_materials",
]

#: The interface's version: proposed until ADR 0027 and chunk 2's contract are accepted.
BRIEF_MATERIALS_VERSION: Final = "aia-brief-materials-0-proposed"

_SOURCE_ID: Final = re.compile(r"SRC-[0-9a-f]{16}")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")


class BriefMaterial(BaseModel):
    """One material a Brief names. Closed: no state beyond what a person picked."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["client_dataset"]
    source_id: str = Field(pattern=_SOURCE_ID.pattern)
    reading_sha256: str = Field(pattern=_SHA256.pattern)
    contract_id: str | None = Field(default=None, min_length=1, max_length=120)
    contract_version: StrictInt | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _both_or_neither(self) -> BriefMaterial:
        if (self.contract_id is None) != (self.contract_version is None):
            raise ValueError("a contract is named by its id and its version, both or neither")
        return self


class Eligibility(StrEnum):
    """What a material may be used for, computed by :func:`eligibility_of`, never stored."""

    #: No data contract named: visible as the client's source, unavailable to analysis.
    NO_CONTRACT = "no_contract"
    #: A contract named that the server holds no acceptance of (none exists before chunk 2).
    CONTRACT_NOT_ACCEPTED = "contract_not_accepted"
    #: An accepted contract of another version, another source or another reading.
    CONTRACT_STALE = "contract_stale"
    #: An accepted contract for exactly this source, reading and version.
    ELIGIBLE = "eligible"


@dataclass(frozen=True, slots=True)
class AcceptedContract:
    """A data contract a person accepted (chunk 2 produces these; nothing does yet): which
    source and reading it was accepted over, at which version."""

    contract_id: str
    version: int
    source_id: str
    reading_sha256: str


@dataclass(frozen=True, slots=True)
class MaterialProblem:
    """Why one entry of ``briefing.materials`` is not a material: its index and the reason."""

    index: int
    reason: str


def eligibility_of(
    material: BriefMaterial, accepted: Mapping[str, AcceptedContract]
) -> Eligibility:
    """Whether ``material`` may feed analysis, by the accepted contracts the server holds
    (keyed by contract id). Only an acceptance of exactly this source, reading and version makes
    it :attr:`Eligibility.ELIGIBLE`; anything less is a named refusal. Nothing the Brief says
    about itself is read."""
    if material.contract_id is None:
        return Eligibility.NO_CONTRACT
    contract = accepted.get(material.contract_id)
    if contract is None:
        return Eligibility.CONTRACT_NOT_ACCEPTED
    if (contract.version, contract.source_id, contract.reading_sha256) != (
        material.contract_version,
        material.source_id,
        material.reading_sha256,
    ):
        return Eligibility.CONTRACT_STALE
    return Eligibility.ELIGIBLE


def read_materials(
    briefing: Mapping[str, Any],
) -> tuple[list[BriefMaterial], list[MaterialProblem]]:
    """``briefing.materials`` as materials, and each entry that is not one, by index.

    An entry with a field the interface does not have (an ``eligibility`` or ``admitted`` the
    browser wrote, say) is refused (``unknown_field``), never read past; a malformed one is
    ``invalid_material``. Missing or empty, there are none."""
    raw = briefing.get("materials")
    if raw is None:
        return [], []
    if not isinstance(raw, list):
        return [], [MaterialProblem(index=-1, reason="materials_not_a_list")]
    kept: list[BriefMaterial] = []
    problems: list[MaterialProblem] = []
    for i, entry in enumerate(raw):
        try:
            kept.append(BriefMaterial.model_validate(entry))
        except ValidationError as exc:
            extra = any(e["type"] == "extra_forbidden" for e in exc.errors())
            problems.append(
                MaterialProblem(index=i, reason="unknown_field" if extra else "invalid_material")
            )
    return kept, problems


def _js_int(value: Any) -> int | None:
    """``Number.isInteger(value) ? value : null`` as the browser signs it: a JSON ``3.0`` is 3."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def material_signature(materials: Sequence[Any]) -> list[dict[str, Any] | None]:
    """What ``brief_signature`` signs of ``briefing.materials`` (``materialSignature`` in
    ``apps/web/src/research/brief-materials.ts``, held to it by the shared cases): per entry its
    source, reading and named contract, in the person's order; ``None`` for an entry that is not
    an object. Never an eligibility or any other field: a signature cannot label a dataset
    admitted."""
    signed: list[dict[str, Any] | None] = []
    for entry in materials:
        if not isinstance(entry, Mapping):
            signed.append(None)
            continue
        signed.append(
            {
                "source_id": entry.get("source_id")
                if isinstance(entry.get("source_id"), str)
                else None,
                "reading_sha256": entry.get("reading_sha256")
                if isinstance(entry.get("reading_sha256"), str)
                else None,
                "contract_id": entry.get("contract_id")
                if isinstance(entry.get("contract_id"), str)
                else None,
                "contract_version": _js_int(entry.get("contract_version")),
            }
        )
    return signed
