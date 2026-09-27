"""The evidence a report may print, and its grade on the page (pure).

A report holds no numbers of its own. Every value it prints — a table cell, a
chart point, a KPI, the n in a caption — is a reference into an
:class:`EvidenceLedger`, built only from :class:`AdmittedClaim` objects (which
only ``admit_numeric_claims`` can mint). The renderer looks the row up and
prints ``row.value`` as the evidence rounded it.

**Print grades are deliberately conservative.** The design system prints five
grades (``measured``, ``calibrated``, ``modelled``, ``holdout-pending``,
``unknown``). Whether a measured field is *measured* or *calibrated* depends on
its field ``EvidenceStatus`` (22 of them), and that mapping is
analysis-governance's decision (OI-9). The ledger therefore takes it as data,
``field_grades``, from whoever composes the report. The rules:

* ``MODELED`` basis → ``modelled``, always;
* a claim over several fields that were **not** jointly measured on one person
  → ``unknown`` (it can never print as measured);
* otherwise the **weakest** grade of its fields in ``field_grades``;
* a field missing from ``field_grades`` → ``unknown``, printed ``?``. Never the
  strongest grade by default.

``holdout-pending`` is a statement about the method, not about one number: it is
the document's method status (``validation.METHOD_STATUS_PENDING``), printed on
the cover and in the method callout.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from aia_core.domain.evidence.admission import AdmittedClaim, EvidenceRow, EvidenceTable
from aia_core.domain.evidence.claims import ClaimBasis, ClaimSurface
from aia_core.domain.evidence.support import SupportStatus


class PrintGrade(StrEnum):
    MEASURED = "measured"
    CALIBRATED = "calibrated"
    MODELLED = "modelled"
    HOLDOUT_PENDING = "holdout-pending"
    UNKNOWN = "unknown"


#: Strongest first. A claim prints the weakest grade of the fields behind it.
_STRENGTH: tuple[PrintGrade, ...] = (
    PrintGrade.MEASURED,
    PrintGrade.CALIBRATED,
    PrintGrade.MODELLED,
    PrintGrade.HOLDOUT_PENDING,
    PrintGrade.UNKNOWN,
)


def grade_of(row: EvidenceRow, field_grades: Mapping[str, PrintGrade] | None = None) -> PrintGrade:
    """The grade a row earns on the page. See the module note."""
    if row.basis is ClaimBasis.MODELED:
        return PrintGrade.MODELLED
    if len(row.fields) > 1 and not row.joint:
        return PrintGrade.UNKNOWN
    grades = [(field_grades or {}).get(f, PrintGrade.UNKNOWN) for f in row.fields]
    return max(grades, key=_STRENGTH.index)


class UnknownEvidence(KeyError):
    """A report referenced evidence it does not hold. The document is refused."""


@dataclass(frozen=True, slots=True)
class EvidenceLedger:
    """What a report may print: admitted rows, plus the refs suppressed and why.

    Built from claims, never from rows directly, so a number cannot enter a report
    without having passed admission. ``surface`` is the surface every claim was
    admitted for; a client report requires ``CLIENT_FACING``.
    """

    rows: Mapping[str, EvidenceRow]
    surface: ClaimSurface
    suppressed: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: MappingProxyType({}))
    #: Field → print grade, from analysis-governance's mapping (OI-9). Empty until
    #: then, so every measured-basis number prints "?".
    field_grades: Mapping[str, PrintGrade] = field(default_factory=lambda: MappingProxyType({}))

    @classmethod
    def from_claims(
        cls,
        claims: Iterable[AdmittedClaim],
        *,
        surface: ClaimSurface,
        table: EvidenceTable | None = None,
        field_grades: Mapping[str, PrintGrade] | None = None,
    ) -> EvidenceLedger:
        """The ledger for one report surface.

        Every claim must have been admitted for ``surface``: an internal claim
        in a client report is refused, not filtered. ``table``'s suppressed refs
        are carried so the report can say what it removed.
        """
        rows: dict[str, EvidenceRow] = {}
        for claim in claims:
            if claim.surface is not surface:
                raise ValueError(
                    f"claim {claim.claim_id} was admitted for {claim.surface}, not {surface}"
                )
            ref = claim.row.evidence_ref
            if ref in rows and rows[ref] != claim.row:
                raise ValueError(f"evidence_ref {ref!r} is bound to two different rows")
            rows[ref] = claim.row
        suppressed = (
            {ref: support.reasons for ref, support in table.suppressed.items()} if table else {}
        )
        overlap = set(rows) & set(suppressed)
        if overlap:
            raise ValueError(f"refs both admitted and suppressed: {sorted(overlap)}")
        return cls(
            MappingProxyType(rows),
            surface,
            MappingProxyType(suppressed),
            MappingProxyType(dict(field_grades or {})),
        )

    def row(self, ref: str) -> EvidenceRow:
        try:
            return self.rows[ref]
        except KeyError:
            if ref in self.suppressed:
                raise UnknownEvidence(
                    f"{ref!r} is suppressed; a report omits it, it never prints it"
                ) from None
            raise UnknownEvidence(f"the report cites {ref!r}, which it does not hold") from None

    def is_suppressed(self, ref: str) -> bool:
        return ref in self.suppressed

    def knows(self, ref: str) -> bool:
        return ref in self.rows or ref in self.suppressed

    def grade(self, ref: str) -> PrintGrade:
        """The printed grade of a cited ref (see :func:`grade_of`)."""
        return grade_of(self.row(ref), self.field_grades)

    def is_indicative(self, ref: str) -> bool:
        """INDICATIVE support prints the value with an "orientační" qualifier."""
        return self.row(ref).support.status is SupportStatus.INDICATIVE
