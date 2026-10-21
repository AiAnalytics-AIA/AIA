"""Which Sociomap methods are approved for use, by exact specification (complete-study-report B4).

Until now one global switch, ``D6_OPEN``, made every Sociomap ``INTERNAL_ONLY``. The owner's
2026-10-13 decision is narrower than flipping it: the report may use the *current*
methodology, aia-sociomap-3, as it stands, because AIA is already prepared to upgrade it.
A switch cannot say "this method, at this specification": a register can.

An entry names a method id **and** the fingerprint of the specification it approves, so an
edited version (``aia-sociomap-3+e1``), a changed preset or a stored version with replaced
formulas is never approved by an entry written for another; it reads ``INTERNAL_ONLY`` until
its own entry is added. A method absent from the register is ``INTERNAL_ONLY``: approval is
never presumed. Status is read from the register whenever a map is read, from the method id
and fingerprint the run recorded beside its maps, so a decision applies to every run that
computed exactly the approved method, and to no other.

Adding an entry is a methodology decision recorded in the plan that carries it, never a fix.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field


class MethodologyStatus(StrEnum):
    #: The Study's researchers may look at it; nobody else, nowhere else.
    INTERNAL_ONLY = "INTERNAL_ONLY"
    #: Approved in the register: a client-facing surface may render it, with its note.
    CLIENT_FACING = "CLIENT_FACING"


class MethodApproval(BaseModel):
    """One decision: this method, at this specification, may be used as ``status`` says."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    method_id: str = Field(min_length=1)
    spec_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: MethodologyStatus
    decided_by: str = Field(min_length=1)
    decided_on: date
    #: Where the decision is recorded, for the reader who asks why.
    record: str = Field(min_length=1)
    #: Printed beside every map computed under it: what the approval does and does not say.
    reader_note: str = Field(min_length=1)


SOCIOMAP_REGISTER: Final[tuple[MethodApproval, ...]] = (
    MethodApproval(
        method_id="aia-sociomap-3",
        spec_fingerprint="e16dc0d0636109322900ab56ed9613e6b2d4f6e65f2dd7e26b9ada059b7cf241",
        status=MethodologyStatus.CLIENT_FACING,
        decided_by="vlastník produktu",
        decided_on=date(2026, 10, 13),
        record=(
            ".planning/plans/complete-study-report.md, Owner decisions (2026-10-13): "
            "use the current, unfinished Sociomap methodology in the report"
        ),
        reader_note=(
            "Mapa je počítána průběžnou metodikou AIA aia-sociomap-3, kterou vlastník produktu "
            "13. 10. 2026 schválil k použití ve zprávách. Metodika se dále zpřesňuje; mapa "
            "zobrazuje vztahy mezi hodnocenými objekty, nikoli jejich příčinu."
        ),
    ),
    MethodApproval(
        method_id="aia-sociomap-5",
        spec_fingerprint="8b0b486443024475a64c06dd0124a24a0a39d3b6bf3937813715cd98032969e0",
        status=MethodologyStatus.CLIENT_FACING,
        decided_by="metodik AIA",
        decided_on=date(2026, 10, 21),
        record=(
            ".planning/plans/signed-off-sociomap-method.md, chunk 8: the methodology owner "
            "(2026-10-21) approved aia-sociomap-5 for reports when it became the default"
        ),
        reader_note=(
            "Mapa je počítána schválenou metodikou AIA aia-sociomap-5, kterou metodik AIA "
            "21. 10. 2026 schválil k použití ve zprávách. Zobrazuje vztahy mezi hodnocenými "
            "objekty, nikoli jejich příčinu; jak spolehlivě je mapa určena, uvádí kontrola "
            "polovin vzorku a poloměr nejistoty."
        ),
    ),
)


def approval_of(
    method_id: str, spec_fingerprint: str, formulas: Mapping[str, str] | None = None
) -> MethodApproval | None:
    """The register's entry for exactly this method, or None. A method whose formulas a
    stored version replaced is a different method and matches no entry written for its base."""
    if formulas:
        return None
    return next(
        (
            a
            for a in SOCIOMAP_REGISTER
            if a.method_id == method_id and a.spec_fingerprint == spec_fingerprint
        ),
        None,
    )


def method_status(
    method_id: str, spec_fingerprint: str, formulas: Mapping[str, str] | None = None
) -> MethodologyStatus:
    """The register's status for exactly this method; ``INTERNAL_ONLY`` when it has none."""
    approval = approval_of(method_id, spec_fingerprint, formulas)
    return MethodologyStatus.INTERNAL_ONLY if approval is None else approval.status


def recorded_statuses(result: Mapping[str, Any]) -> dict[str, MethodApproval | None]:
    """Each method a stored Sociomap result recorded (``methods``: id, fingerprint, formulas)
    with its register entry, or None. A result stored before methods were recorded has none."""
    out: dict[str, MethodApproval | None] = {}
    for method in result.get("methods") or ():
        if not isinstance(method, Mapping):
            continue
        method_id, digest = method.get("method_id"), method.get("spec_fingerprint")
        if isinstance(method_id, str) and isinstance(digest, str):
            formulas = method.get("formulas")
            out[method_id] = approval_of(
                method_id, digest, formulas if isinstance(formulas, Mapping) else None
            )
    return out
