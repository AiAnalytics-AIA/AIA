"""Licence eligibility: may material derived from *these datasets* reach *this route*?

ADR 0016 decision 5 (D3). A gate of its own, beside residency and not a kind of
it. Residency (:mod:`.residency`, ADR 0008) asks whether a class of material may
leave AIA over a route. This asks what residency cannot: whether the **licences**
of the datasets the material was computed from allow it to reach a model provider
at all. They are decided by different people -- residency by the operator's
contracts, licensing by the data owner and legal -- change for different reasons,
and refuse with different reasons. ``GovernedModelGateway`` requires both.

Two things are kept apart here, deliberately:

* the **engineering rule** (:meth:`LicencePolicy.authorise`, code): every
  dataset the material derives from must have a determination that approves this
  route. An undeclared lineage, an unknown dataset, or a determination that is
  anything but approved for this route means no transmission.
* the **determinations** (:mod:`.licence_determinations`, policy data): per
  dataset, what legal and the data owner have decided, by whom, when and on what
  basis. Approval changes a determination; it never changes this module.

Fails closed, like residency: a lineage nobody declared is refused rather than
assumed to be clean, because the case nobody declared is the case that leaks.
Pure: no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Final

from .residency import ProviderRoute

__all__ = [
    "ANY_APPROVED_ROUTE",
    "DataLineage",
    "LicenceDenied",
    "LicenceDetermination",
    "LicencePolicy",
    "LicenceStatus",
]

#: A determination approving every route the egress policy approves -- only for
#: material AIA itself owns outright (its own fictional fixtures).
ANY_APPROVED_ROUTE: Final = "*"


class LicenceStatus(StrEnum):
    """Where a dataset's transmission determination stands."""

    #: Legal and the data owner approved transmission to the named routes.
    APPROVED = "APPROVED"
    #: Not decided. Treated exactly like a refusal.
    UNDETERMINED = "UNDETERMINED"
    #: Decided: no transmission.
    REFUSED = "REFUSED"


@dataclass(frozen=True, slots=True)
class LicenceDetermination:
    """What has been decided about sending one dataset's derivatives to a provider.

    ``approved_routes`` names routes (ADR 0008's unit of approval), never
    providers: the same provider over another account or region is another
    answer. It is meaningful only when ``status`` is ``APPROVED``.
    """

    dataset: str
    description: str
    status: LicenceStatus
    basis: str
    decided_by: str
    decided_on: date | None
    approved_routes: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.status is not LicenceStatus.APPROVED and self.approved_routes:
            raise ValueError(f"{self.dataset}: only an approved determination names routes")
        if self.status is LicenceStatus.APPROVED and not (self.decided_on and self.decided_by):
            raise ValueError(f"{self.dataset}: an approval says who approved it, and when")

    def approves(self, route: ProviderRoute) -> bool:
        """True only when this determination approves ``route``."""
        return self.status is LicenceStatus.APPROVED and (
            ANY_APPROVED_ROUTE in self.approved_routes or route.route_id in self.approved_routes
        )


@dataclass(frozen=True, slots=True)
class DataLineage:
    """The datasets a piece of material was computed from, declared by its holder.

    ``DataLineage.none()`` is a declaration too -- "derived from no dataset", for a
    prompt of methodology text alone -- and is the only way to say it. There is no
    default: a request that does not declare its lineage carries ``None`` and is
    refused at the boundary.
    """

    datasets: frozenset[str]

    @classmethod
    def of(cls, *datasets: str) -> DataLineage:
        if not datasets or any(not d or not d.strip() for d in datasets):
            raise ValueError("a lineage names datasets; use DataLineage.none() for none")
        return cls(frozenset(datasets))

    @classmethod
    def none(cls) -> DataLineage:
        """Material derived from no dataset at all."""
        return cls(frozenset())


class LicenceDenied(PermissionError):
    """Material may not reach this route: a dataset it derives from is not cleared.

    Deliberately not an :class:`~aia_core.domain.residency.EgressDenied`: a licence
    refusal is not a residency refusal, and a handler that caught one as the other
    would report the wrong gate -- or, worse, treat clearing one as clearing both.
    Like a residency denial it is a hard stop with no suggested alternative.
    """

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class LicencePolicy:
    """The recorded determinations, and the rule that reads them."""

    determinations: tuple[LicenceDetermination, ...]

    def __post_init__(self) -> None:
        seen = [d.dataset for d in self.determinations]
        if len(seen) != len(set(seen)):
            raise ValueError("one determination per dataset")

    def determination(self, dataset: str) -> LicenceDetermination | None:
        return next((d for d in self.determinations if d.dataset == dataset), None)

    def authorise(self, *, lineage: DataLineage | None, route: ProviderRoute) -> None:
        """Return when every dataset in ``lineage`` is cleared for ``route``; else raise.

        Checked in order, each a way a licence gets bypassed in practice:

        1. **The lineage must be declared.** ``None`` is refused, not read as "no data".
        2. **Every dataset must be known.** A dataset with no determination has had
           nothing decided about it, which is not the same as permission.
        3. **Every determination must approve this route.** Undetermined is refused
           exactly as refused is; approval for one route is not approval for another.
        """
        if not isinstance(lineage, DataLineage):
            raise LicenceDenied(
                "material must declare the datasets it derives from before it may reach a model",
                reason="lineage_undeclared",
            )
        for dataset in sorted(lineage.datasets):
            found = self.determination(dataset)
            if found is None:
                raise LicenceDenied(
                    f"no licence determination for dataset {dataset!r}",
                    reason="dataset_unknown",
                )
            if not found.approves(route):
                reason = (
                    "not_approved_for_route"
                    if found.status is LicenceStatus.APPROVED
                    else found.status.value.lower()
                )
                raise LicenceDenied(
                    f"dataset {dataset!r} is not cleared for route {route.route_id} "
                    f"({found.status.value}: {found.basis})",
                    reason=reason,
                )
