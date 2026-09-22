"""EU data residency and the outbound egress boundary.

EU residency is a **frozen invariant**, not an open question. Everything derived
from a client's engagement -- source data, artifacts, backups, retrieval indexes,
caches, logs and traces carrying client information, and any AI inference over
identifiable or confidential client material -- is processed under EU residency
rules.

This module is the decision function that makes that enforceable rather than
aspirational. It answers one question:

    may *this* material, under *this* authorised scope, leave AIA over *this*
    route?

and it **fails closed**: anything it cannot positively justify is denied. That is
the whole design. A residency rule that permits what it has not been told about
is a rule that permits everything, because the case nobody configured is exactly
the case that leaks.

Nothing here names a vendor, a region string or a hosting product. Which provider
or transport satisfies these constraints is a separate, ADR-governed choice; the
invariant is what is frozen. Recording an approved route is how an implementation
declares that it has met the constraint -- the route does not get to redefine it.

No I/O. The approved routes come from trusted configuration, and the scope comes
from the authorization layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from .scope import ScopeGrant, StudyContext

__all__ = [
    "DataClass",
    "EgressDecision",
    "EgressDenied",
    "EgressPolicy",
    "ProviderRoute",
    "ResidencyZone",
    "evaluate_egress",
]


class DataClass(StrEnum):
    """What is being sent out. Drives which routes are permissible at all.

    Classification is a property of the material, decided by the code that holds
    it. There is deliberately no "unclassified" member: absence of a class is
    represented by ``None`` at the call site and is always refused, so that
    forgetting to classify fails loudly instead of defaulting to the most
    permissive answer.
    """

    #: Raw client documents, row-level datasets, personal data, NDA material.
    CLASS_A_CLIENT_CONFIDENTIAL = "CLASS_A_CLIENT_CONFIDENTIAL"
    #: Aggregates, segment profiles, summaries derived from client material.
    CLASS_B_DERIVED_CLIENT = "CLASS_B_DERIVED_CLIENT"
    #: Internal and non-client material: methodology text, public sources, prompts
    #: carrying no client information.
    CLASS_C_INTERNAL = "CLASS_C_INTERNAL"

    @property
    def is_client_material(self) -> bool:
        """True when this class carries client information in any form."""
        return self is not DataClass.CLASS_C_INTERNAL


class ResidencyZone(StrEnum):
    """Where processing physically happens for a route.

    ``UNKNOWN`` exists so that an under-specified route is representable and
    therefore refusable. Modelling it as "probably fine" is how residency
    breaches happen.
    """

    EU = "EU"
    NON_EU = "NON_EU"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ProviderRoute:
    """One approved way for material to leave AIA.

    A route is an assertion made by configuration -- "this provider, over this
    transport, processes in this zone under these terms". It is trusted because it
    comes from deployment configuration rather than from a request; it is not
    trusted to *define* the rules, only to state its own properties, which the
    rules below then judge.

    The defaults are the restrictive ones. A route that declares nothing is
    useless for client material, which is the correct posture for a route somebody
    added without reading this file.
    """

    route_id: str
    provider: str
    zone: ResidencyZone = ResidencyZone.UNKNOWN

    #: The operator has confirmed processing, and any provider-side storage,
    #: happens within the EU under a data processing agreement.
    eu_processing_approved: bool = False
    #: Submitted material is contractually excluded from provider model training.
    excluded_from_training: bool = False
    #: Provider-side retention in days. ``0`` means nothing is retained beyond the
    #: request. ``None`` means unspecified, which is not the same as zero.
    retention_days: int | None = None
    #: Classes this route is explicitly approved to carry. Empty means none.
    approved_for: frozenset[DataClass] = field(default_factory=frozenset)

    @property
    def is_eu_processing(self) -> bool:
        """True when this route is a confirmed EU-processing route."""
        return self.zone is ResidencyZone.EU and self.eu_processing_approved

    @property
    def has_bounded_retention(self) -> bool:
        """True when provider-side retention is specified and finite."""
        return self.retention_days is not None and self.retention_days >= 0


@dataclass(frozen=True, slots=True)
class EgressDecision:
    """An allowed egress, with the facts that allowed it.

    Returned only on the permitted path; a refusal raises. It carries the scope,
    the class and the route so that provenance and cost attribution can be written
    from the same decision that authorised the call, rather than reconstructed
    afterwards from something that might disagree.
    """

    organization_id: str
    client_id: str
    study_id: str
    actor_id: str
    data_class: DataClass
    route_id: str
    provider: str
    zone: ResidencyZone

    def audit_fields(self) -> dict[str, str]:
        """The fields an egress record must carry."""
        return {
            "organization_id": self.organization_id,
            "client_id": self.client_id,
            "study_id": self.study_id,
            "actor_id": self.actor_id,
            "data_class": self.data_class.value,
            "route_id": self.route_id,
            "provider": self.provider,
            "residency_zone": self.zone.value,
        }


class EgressDenied(PermissionError):
    """Raised when material may not leave AIA over the requested route.

    A denial is a hard stop, never a downgrade. There is deliberately no
    ``suggested_route`` field: "this route is refused, try the cheaper one" is how
    a residency control becomes a formality.
    """

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


# Classes that may never travel over a route that is not confirmed EU processing.
_EU_ONLY_CLASSES: Final = frozenset(
    {DataClass.CLASS_A_CLIENT_CONFIDENTIAL, DataClass.CLASS_B_DERIVED_CLIENT}
)


def evaluate_egress(
    *,
    scope: StudyContext,
    data_class: DataClass | None,
    route: ProviderRoute | None,
) -> EgressDecision:
    """Authorise one outbound call, or raise :class:`EgressDenied`.

    The checks, in order, each of which is a way a residency rule gets bypassed in
    practice:

    1. **The scope must be issued.** An egress decision without an authorised
       StudyContext has no client to attribute the call to and no evidence a human
       authorised anything. A model-supplied dictionary cannot stand in for one.
    2. **The material must be classified.** Unclassified client data must not
       leave AIA. ``None`` is refused rather than assumed to be internal.
    3. **A route must exist.** No configured route means no egress -- not a
       default provider.
    4. **The route must be approved for this class.** Approval is per class: a
       route cleared for internal prompts is not thereby cleared for a client's
       row-level dataset.
    5. **Client material requires confirmed EU processing.** Classes A and B may
       only travel over a route whose zone is EU *and* which the operator has
       confirmed as EU-processing. An ``UNKNOWN`` zone is refused.
    6. **Client material requires training exclusion and specified retention.**
       Residency is not only about geography: material processed in the EU but
       retained indefinitely, or used to train a provider's model, has still left
       the client's control.
    7. **Class A may not use an arbitrary direct provider API.** It requires a
       route explicitly approved for Class A, which is the same check as (4) and is
       restated here because it is the constraint people try to argue around.

    Class C may use broader approved routes, including non-EU ones, but still
    requires an approved route and still produces a decision record -- provenance
    and cost attribution are owed for every paid call regardless of what it
    carried.
    """
    if not isinstance(scope, StudyContext) or not isinstance(scope.grant, ScopeGrant):
        raise EgressDenied(
            "egress requires an authorised study context", reason="unauthorised_scope"
        )

    if data_class is None:
        raise EgressDenied(
            "material must be classified before it may leave AIA",
            reason="unclassified_material",
        )

    if route is None:
        raise EgressDenied("no approved route for this request", reason="no_approved_route")

    if data_class not in route.approved_for:
        raise EgressDenied(
            f"route {route.route_id} is not approved for {data_class.value}",
            reason="route_not_approved_for_class",
        )

    if data_class in _EU_ONLY_CLASSES:
        if not route.is_eu_processing:
            raise EgressDenied(
                f"{data_class.value} requires confirmed EU processing; "
                f"route {route.route_id} is {route.zone.value}",
                reason="residency_violation",
            )
        if not route.excluded_from_training:
            raise EgressDenied(
                f"{data_class.value} requires contractual exclusion from training",
                reason="training_exclusion_missing",
            )
        if not route.has_bounded_retention:
            raise EgressDenied(
                f"{data_class.value} requires a specified provider retention period",
                reason="retention_unspecified",
            )

    return EgressDecision(
        organization_id=scope.organization_id,
        client_id=scope.client_id,
        study_id=scope.study_id,
        actor_id=scope.actor_id,
        data_class=data_class,
        route_id=route.route_id,
        provider=route.provider,
        zone=route.zone,
    )


@dataclass(frozen=True, slots=True)
class EgressPolicy:
    """The set of routes a deployment has approved. Fails closed when empty.

    Lookup is by route id rather than by provider name, because a provider name is
    not a route: the same provider reached over a different transport, account or
    region is a different residency answer and must be a different route.
    """

    routes: tuple[ProviderRoute, ...] = ()

    def route(self, route_id: str) -> ProviderRoute | None:
        """Return the approved route with this id, or None."""
        return next((r for r in self.routes if r.route_id == route_id), None)

    def routes_for(self, data_class: DataClass) -> tuple[ProviderRoute, ...]:
        """Return the routes approved to carry this class.

        Used to answer "can this study run at all" before work starts, rather than
        discovering mid-pipeline that nothing may carry a client's data.
        """
        return tuple(r for r in self.routes if data_class in r.approved_for)

    def authorise(
        self,
        *,
        scope: StudyContext,
        data_class: DataClass | None,
        route_id: str | None,
    ) -> EgressDecision:
        """Resolve a route id and authorise the call, or raise.

        An unknown route id is refused as "no approved route" rather than looked up
        anywhere else. Falling back to a default provider when the requested one is
        not configured is precisely the silent substitution the product forbids.
        """
        return evaluate_egress(
            scope=scope,
            data_class=data_class,
            route=self.route(route_id) if route_id else None,
        )
