"""Organization, Client, Study and the authorization model.

AIA is an internal research operating system: a small team produces paid client
studies. **Client and Study are hard isolation boundaries**, not labels. The
authorization chain is:

    User -> Organization membership -> Client grant -> Study grant -> Role

Two rules are load-bearing and are enforced structurally rather than by
convention:

1. **Every client-derived object resolves to a client and a study.** There is no
   object that belongs to an organization but carries client data.

2. **Scope is injected from authenticated application context, never inferred or
   supplied by a caller.** In particular no AI- or model-generated argument may
   determine client or study scope. A model may choose *which tool* to run; it may
   not choose *whose data* that tool reads. :class:`StudyContext` therefore cannot
   be constructed from untrusted input -- see :class:`ScopeGrant`.

Nothing in this module performs I/O. Resolution against the database lives in
``aia_core.application.scope``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Final
from uuid import uuid4

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "DEFAULT_SELF_APPROVAL_ALLOWED",
    "LEGACY_PANEL_ROLES",
    "ROLE_PERMISSIONS",
    "ApprovalIndependence",
    "Client",
    "ClientGrant",
    "ClientStatus",
    "Organization",
    "OrganizationMembership",
    "OrganizationRole",
    "Permission",
    "ScopeDenied",
    "ScopeGrant",
    "ScopeRole",
    "SelfApprovalPolicy",
    "SelfApprovalSource",
    "Slug",
    "Study",
    "StudyContext",
    "StudyGrant",
    "StudyStatus",
    "effective_role",
    "new_client_id",
    "new_organization_id",
    "new_study_id",
    "new_user_id",
    "observe_approval_independence",
    "permissions_for",
    "require_approval_independence",
    "resolve_self_approval_policy",
]


# --------------------------------------------------------------------------- #
# Identity helpers
# --------------------------------------------------------------------------- #


def new_organization_id() -> str:
    """Return a new organization id."""
    return "ORG-" + uuid4().hex[:14]


def new_client_id() -> str:
    """Return a new client id."""
    return "CLI-" + uuid4().hex[:14]


def new_study_id() -> str:
    """Return a new study id."""
    return "STU-" + uuid4().hex[:14]


def new_user_id() -> str:
    """Return a new user id.

    This is AIA's own identifier. The identity provider's subject claim is stored
    separately as ``external_subject`` so that a provider migration does not
    rewrite every foreign key.
    """
    return "USR-" + uuid4().hex[:14]


# --------------------------------------------------------------------------- #
# Roles and permissions
# --------------------------------------------------------------------------- #


class OrganizationRole(StrEnum):
    """A user's role within the organization itself.

    These roles grant *administrative* capability -- creating clients and studies,
    and granting access. They deliberately do **not** grant the ability to read
    client research data: an administrator who needs to work on a client's study
    grants themselves access, and that grant is recorded. Separating "may
    administer" from "may read client data" is what makes the client boundary
    meaningful for a team where everyone is technically an admin.
    """

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


# Who may use the vendored 18.6.6 interface on the product hostname (ADR 0012).
# The unit is single-tenant: whoever uses it sees every project it holds and can
# store provider keys in it, so study-level scope cannot be applied to it. Until a
# feature moves onto AIA's study-scoped model, only organization administrators
# may reach it -- the most restrictive choice that still lets the team work
# (reference open decision D8: "default to the most restrictive role").
LEGACY_PANEL_ROLES: frozenset[OrganizationRole] = frozenset(
    {OrganizationRole.OWNER, OrganizationRole.ADMIN}
)


class ScopeRole(StrEnum):
    """A user's role on a client or a study.

    Ordered by capability. A role granted at the client level applies to every
    study of that client unless a study-level grant overrides it.
    """

    VIEWER = "VIEWER"
    REVIEWER = "REVIEWER"
    RESEARCHER = "RESEARCHER"
    LEAD = "LEAD"


class Permission(StrEnum):
    """A discrete capability checked at an authorization boundary.

    Handlers and services check permissions, never roles. Adding a role therefore
    does not require finding every call site.
    """

    # Reading
    VIEW_STUDY = "VIEW_STUDY"
    VIEW_RESULTS = "VIEW_RESULTS"
    VIEW_COSTS = "VIEW_COSTS"

    # Doing the work
    EDIT_STUDY = "EDIT_STUDY"
    RUN_WORKFLOW = "RUN_WORKFLOW"
    CANCEL_WORKFLOW = "CANCEL_WORKFLOW"
    UPLOAD_DATA = "UPLOAD_DATA"

    # Gatekeeping
    APPROVE_GATE = "APPROVE_GATE"
    APPROVE_BUDGET = "APPROVE_BUDGET"
    SIGN_OFF_DELIVERABLE = "SIGN_OFF_DELIVERABLE"

    # Delivery and administration
    EXPORT_DELIVERABLE = "EXPORT_DELIVERABLE"
    MANAGE_STUDY_ACCESS = "MANAGE_STUDY_ACCESS"
    MANAGE_STUDY_BUDGET = "MANAGE_STUDY_BUDGET"
    DELETE_STUDY = "DELETE_STUDY"


# Role -> permissions. A REVIEWER can approve and sign off but cannot edit the
# study, which keeps review independent of authorship -- the separation the
# methodology's human sign-off gate depends on.
ROLE_PERMISSIONS: Final[dict[ScopeRole, frozenset[Permission]]] = {
    ScopeRole.VIEWER: frozenset(
        {
            Permission.VIEW_STUDY,
            Permission.VIEW_RESULTS,
        }
    ),
    ScopeRole.REVIEWER: frozenset(
        {
            Permission.VIEW_STUDY,
            Permission.VIEW_RESULTS,
            Permission.VIEW_COSTS,
            Permission.APPROVE_GATE,
            Permission.SIGN_OFF_DELIVERABLE,
        }
    ),
    ScopeRole.RESEARCHER: frozenset(
        {
            Permission.VIEW_STUDY,
            Permission.VIEW_RESULTS,
            Permission.VIEW_COSTS,
            Permission.EDIT_STUDY,
            Permission.RUN_WORKFLOW,
            Permission.CANCEL_WORKFLOW,
            Permission.UPLOAD_DATA,
            Permission.EXPORT_DELIVERABLE,
        }
    ),
    ScopeRole.LEAD: frozenset(
        {
            Permission.VIEW_STUDY,
            Permission.VIEW_RESULTS,
            Permission.VIEW_COSTS,
            Permission.EDIT_STUDY,
            Permission.RUN_WORKFLOW,
            Permission.CANCEL_WORKFLOW,
            Permission.UPLOAD_DATA,
            Permission.APPROVE_GATE,
            Permission.APPROVE_BUDGET,
            Permission.SIGN_OFF_DELIVERABLE,
            Permission.EXPORT_DELIVERABLE,
            Permission.MANAGE_STUDY_ACCESS,
            Permission.MANAGE_STUDY_BUDGET,
            Permission.DELETE_STUDY,
        }
    ),
}


def permissions_for(role: ScopeRole) -> frozenset[Permission]:
    """Return the permissions a role confers."""
    return ROLE_PERMISSIONS[role]


def effective_role(
    *, client_role: ScopeRole | None, study_role: ScopeRole | None
) -> ScopeRole | None:
    """Resolve the role a user holds on a study.

    A study-level grant is **authoritative** when present, even when it is
    narrower than the client-level grant. That is the point of a study grant: a
    client LEAD can be deliberately restricted to VIEWER on one sensitive study.

    With no study grant, the client grant applies to every study of that client.
    With neither, the user has no access and the study must be invisible to them.
    """
    if study_role is not None:
        return study_role
    return client_role


class ScopeDenied(PermissionError):
    """Raised when a principal lacks access to a client or study.

    Callers must convert this to a 404, not a 403: confirming that a study exists
    but is not yours discloses another client's engagement.
    """

    def __init__(self, message: str = "not found", *, reason: str = "no_grant") -> None:
        super().__init__(message)
        self.reason = reason


class SeparationOfDutiesViolation(ScopeDenied):
    """Raised when the producer of work approves it without policy permitting it.

    Role separation alone is not enough: a LEAD holds both ``EDIT_STUDY`` and
    ``SIGN_OFF_DELIVERABLE``, so without this check one person could author a
    deliverable and then clear its own review gate by switching hats.

    Independent review is the **default**, not an absolute. See
    :func:`require_approval_independence`.
    """

    def __init__(self, actor_id: str, *, what: str = "this work") -> None:
        super().__init__(
            f"independent review required: {what} was produced by the same person",
            reason="separation_of_duties",
        )
        self.actor_id = actor_id


# --------------------------------------------------------------------------- #
# Self-approval policy
# --------------------------------------------------------------------------- #

# Independent review is the default posture. A deployment that has configured
# nothing gets the safe behaviour.
DEFAULT_SELF_APPROVAL_ALLOWED: Final = False


class SelfApprovalSource(StrEnum):
    """Which level of persisted configuration decided a self-approval policy.

    Recorded on every approval so an auditor can answer "who allowed this?"
    without reconstructing the configuration as it stood at the time.
    """

    DEFAULT = "default"
    ORGANIZATION = "organization"
    CLIENT = "client"
    STUDY = "study"


@dataclass(frozen=True, slots=True)
class SelfApprovalPolicy:
    """The resolved answer to "may the producer approve their own work here?".

    Carries its ``source`` as well as its value because the two together are what
    makes an approval reconstructible: "allowed" is not an audit record, "allowed,
    because this study overrides its client" is.
    """

    allowed: bool = DEFAULT_SELF_APPROVAL_ALLOWED
    source: SelfApprovalSource = SelfApprovalSource.DEFAULT


def resolve_self_approval_policy(
    *,
    organization: bool | None = None,
    client: bool | None = None,
    study: bool | None = None,
) -> SelfApprovalPolicy:
    """Resolve self-approval from the scope hierarchy, most specific first.

    ``study > client > organization > default (false)``.

    Each level is **nullable and inherited** rather than a copied value: ``None``
    means "whatever my parent says". Duplicating the value down the hierarchy
    would mean that enabling self-approval for an organization silently failed to
    reach clients created earlier, which is the kind of divergence nobody notices
    until an approval that should have been refused was not.

    An explicit ``False`` at a level is **not** inheritance: a client that has
    turned self-approval off keeps it off under an organization that turned it on.
    That is why the levels are ``bool | None`` and not ``bool``.
    """
    for value, source in (
        (study, SelfApprovalSource.STUDY),
        (client, SelfApprovalSource.CLIENT),
        (organization, SelfApprovalSource.ORGANIZATION),
    ):
        if value is not None:
            return SelfApprovalPolicy(allowed=bool(value), source=source)
    return SelfApprovalPolicy(
        allowed=DEFAULT_SELF_APPROVAL_ALLOWED, source=SelfApprovalSource.DEFAULT
    )


@dataclass(frozen=True, slots=True)
class ApprovalIndependence:
    """The independence finding for one approval decision, for the audit record.

    Produced by :func:`require_approval_independence` on the *allowed* path. A
    refused approval raises instead, and is recorded by the caller as a denial.
    """

    producer_user_id: str | None
    approver_user_id: str
    self_approved: bool
    policy: SelfApprovalPolicy

    def audit_fields(self) -> dict[str, Any]:
        """The fields an approval record must carry to be reconstructible."""
        return {
            "producer_user_id": self.producer_user_id,
            "approver_user_id": self.approver_user_id,
            "self_approved": self.self_approved,
            "self_approval_allowed": self.policy.allowed,
            "self_approval_source": self.policy.source.value,
        }


def observe_approval_independence(
    *,
    producer_user_id: str | None,
    approving_user_id: str,
    policy: SelfApprovalPolicy,
) -> ApprovalIndependence:
    """Describe the independence of a decision without enforcing anything.

    For decisions that are recorded but not gated on independence -- a
    clarification or a methodology question, where the producer is frequently the
    only person who can answer. The facts are still worth keeping: a pattern of
    one person answering their own questions is visible only if it is recorded.
    """
    return ApprovalIndependence(
        producer_user_id=producer_user_id,
        approver_user_id=approving_user_id,
        self_approved=bool(producer_user_id) and producer_user_id == approving_user_id,
        policy=policy,
    )


def require_approval_independence(
    *,
    producer_user_id: str | None,
    approving_user_id: str,
    policy: SelfApprovalPolicy,
    what: str = "this work",
) -> ApprovalIndependence:
    """Decide whether this person may approve this work, and describe the result.

    Independent review is the default: when the producer is also the approver the
    approval is refused **unless** self-approval has been explicitly enabled by
    policy for this scope.

    Two things this function deliberately does not do:

    * It does not check permission. Policy permitting self-approval is not
      authority to approve -- the caller must still have required
      ``APPROVE_GATE`` or ``SIGN_OFF_DELIVERABLE`` before calling. A policy flag
      that granted authority would turn a convenience setting into a privilege
      escalation.
    * It does not read configuration. ``policy`` must be resolved from persisted
      AIA state by the authorization layer and arrive on a
      :class:`StudyContext`. A model, an agent, a tool argument or a request body
      must never be able to decide that self-approval is permitted; that is the
      whole reason the flag is not a parameter of the approval call.

    An unknown producer (``None``) is not a self-approval and is allowed, because
    a gate with no recorded producer predates provenance and blocking it would
    strand existing work. This function is only as strong as the provenance
    feeding it, which is why every write records a producer.
    """
    independence = observe_approval_independence(
        producer_user_id=producer_user_id,
        approving_user_id=approving_user_id,
        policy=policy,
    )
    if independence.self_approved and not policy.allowed:
        raise SeparationOfDutiesViolation(approving_user_id, what=what)
    return independence


# --------------------------------------------------------------------------- #
# Entities
# --------------------------------------------------------------------------- #


class ClientStatus(StrEnum):
    """Lifecycle of a client relationship."""

    ACTIVE = "ACTIVE"
    DORMANT = "DORMANT"
    ARCHIVED = "ARCHIVED"


class StudyStatus(StrEnum):
    """Lifecycle of one engagement."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    IN_REVIEW = "IN_REVIEW"
    DELIVERED = "DELIVERED"
    ARCHIVED = "ARCHIVED"
    CANCELLED = "CANCELLED"

    @property
    def accepts_work(self) -> bool:
        """True when new workflow runs may start against this study.

        A delivered or archived study is closed: starting a run against it would
        change work a client has already been shown.
        """
        return self in (StudyStatus.DRAFT, StudyStatus.ACTIVE, StudyStatus.IN_REVIEW)


def _validate_slug(value: str) -> str:
    """Normalise and validate a URL-safe slug.

    Slugs appear in URLs (``/org/{slug}/…``) and in object storage keys, so they
    are restricted to characters that are safe in both and cannot be used for
    traversal or to escape a storage prefix.

    Case and surrounding whitespace are *normalised* rather than rejected, because
    a user typing "Acme-Corp" means the same client as "acme-corp". Anything else
    outside ``[a-z0-9-]`` is rejected: silently stripping characters would let two
    distinct names collapse into one slug.

    ASCII-only is deliberate. ``str.isalnum()`` accepts letters like "č", which are
    legal in a URL path but not in every S3 key or DNS label, so the check is
    explicit rather than relying on Unicode categories.
    """
    slug = (value or "").strip().lower()
    if not slug:
        raise ValueError("slug must not be empty")
    if len(slug) > 64:
        raise ValueError("slug must be at most 64 characters")
    if not all(("a" <= c <= "z") or ("0" <= c <= "9") or c == "-" for c in slug):
        raise ValueError("slug may contain only ASCII lowercase letters, digits and hyphens")
    if slug.startswith("-") or slug.endswith("-"):
        raise ValueError("slug must not start or end with a hyphen")
    if "--" in slug:
        raise ValueError("slug must not contain consecutive hyphens")
    return slug


# A validated, normalised slug. Using one annotated type keeps every entity's
# rule identical -- a per-model validator would drift.
Slug = Annotated[str, AfterValidator(_validate_slug)]


class Organization(BaseModel):
    """The AIA team itself. The outermost tenant boundary."""

    model_config = ConfigDict(extra="forbid")

    organization_id: str = Field(default_factory=new_organization_id)
    slug: Slug
    name: str
    # Base of the self-approval hierarchy. ``None`` means "not configured", which
    # resolves to the default of False -- see `resolve_self_approval_policy`.
    allow_self_approval: bool | None = None
    created_at: datetime | None = None


class Client(BaseModel):
    """A paying client. A hard confidentiality boundary."""

    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(default_factory=new_client_id)
    organization_id: str
    slug: Slug
    name: str
    status: ClientStatus = ClientStatus.ACTIVE
    # Free-form internal reference, e.g. an accounting code. Never client-visible.
    reference: str = ""
    # Overrides the organization setting for this client's studies. ``None``
    # inherits; an explicit False overrides an organization that allows it,
    # because a client's contract may require independent review regardless.
    allow_self_approval: bool | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None


class Study(BaseModel):
    """One client engagement: the unit of budget, delivery and access."""

    model_config = ConfigDict(extra="forbid")

    study_id: str = Field(default_factory=new_study_id)
    organization_id: str
    client_id: str
    slug: Slug
    name: str
    status: StudyStatus = StudyStatus.DRAFT

    # Budget is held at the study level because that is what is quoted to a
    # client. Enforcement happens before any paid provider call.
    budget_usd: float = 0.0
    spent_usd: float = 0.0

    # Most specific level of the self-approval hierarchy. ``None`` inherits from
    # the client, then the organization, then the default of False.
    allow_self_approval: bool | None = None

    created_at: datetime | None = None
    modified_at: datetime | None = None
    delivered_at: datetime | None = None

    @field_validator("budget_usd", "spent_usd")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("monetary amounts must not be negative")
        return float(v)

    @property
    def remaining_usd(self) -> float:
        """Budget headroom, never negative."""
        return max(0.0, self.budget_usd - self.spent_usd)


class OrganizationMembership(BaseModel):
    """A user's membership of an organization."""

    model_config = ConfigDict(extra="forbid")

    organization_id: str
    user_id: str
    role: OrganizationRole = OrganizationRole.MEMBER
    created_at: datetime | None = None

    @property
    def may_administer(self) -> bool:
        """True when this member may create clients and studies and grant access.

        Administrative capability does not include reading client research data;
        that still requires an explicit grant.
        """
        return self.role in (OrganizationRole.OWNER, OrganizationRole.ADMIN)


class ClientGrant(BaseModel):
    """A user's role on a client, applying to all of that client's studies."""

    model_config = ConfigDict(extra="forbid")

    client_id: str
    user_id: str
    role: ScopeRole
    granted_by: str | None = None
    created_at: datetime | None = None


class StudyGrant(BaseModel):
    """A user's role on one study.

    Authoritative over a client grant, in both directions: it can widen access for
    someone brought in for a single study, and narrow it for a sensitive one.
    """

    model_config = ConfigDict(extra="forbid")

    study_id: str
    user_id: str
    role: ScopeRole
    granted_by: str | None = None
    created_at: datetime | None = None


# --------------------------------------------------------------------------- #
# StudyContext -- the injected scope
# --------------------------------------------------------------------------- #

# Sentinel proving a context was produced by the authorization layer. It is a
# module-private object, so a dict decoded from a model response, a tool argument
# or an HTTP body can never carry it. This is the structural half of the rule
# "scope is injected, never supplied".
_SCOPE_ISSUER: Final = object()


@dataclass(frozen=True, slots=True)
class ScopeGrant:
    """Proof that the authorization layer authorised a scope.

    Only ``aia_core.application.scope`` constructs these, by passing the private
    issuer sentinel. Everything else can pass a :class:`ScopeGrant` around but
    cannot forge one.
    """

    _issuer: Any

    def __post_init__(self) -> None:
        if self._issuer is not _SCOPE_ISSUER:
            raise ScopeDenied(
                "scope may only be issued by the authorization layer",
                reason="forged_scope",
            )

    @classmethod
    def _issue(cls) -> ScopeGrant:
        """Issue a grant. Internal to the authorization layer."""
        return cls(_issuer=_SCOPE_ISSUER)


@dataclass(frozen=True, slots=True)
class StudyContext:
    """The authenticated, authorised scope every client-derived operation runs in.

    Every repository that touches client data requires one of these. Because it
    can only be produced by the authorization layer from a verified principal, a
    handler, a background job or an AI tool cannot widen its own scope: the worst
    a compromised tool argument can do is fail to resolve.

    ``role`` is the effective role after combining client and study grants, and
    ``permissions`` is derived from it so that callers check capability rather
    than role.
    """

    organization_id: str
    client_id: str
    study_id: str
    actor_id: str
    role: ScopeRole
    permissions: frozenset[Permission]
    organization_role: OrganizationRole
    grant: ScopeGrant
    study_status: StudyStatus = StudyStatus.ACTIVE
    # Resolved from persisted organization/client/study configuration by the
    # authorization layer. It travels on the context precisely so that it cannot
    # be passed as an argument to an approval call: a model, an agent or a request
    # body can supply an argument, but none of them can issue a StudyContext.
    self_approval: SelfApprovalPolicy = field(default_factory=SelfApprovalPolicy)
    request_id: str | None = None

    def __post_init__(self) -> None:
        # Defence in depth: a StudyContext with a forged grant is unusable even if
        # someone bypasses the resolver.
        if not isinstance(self.grant, ScopeGrant):
            raise ScopeDenied("study context requires an issued grant", reason="forged_scope")
        for name in ("organization_id", "client_id", "study_id", "actor_id"):
            if not getattr(self, name):
                raise ScopeDenied(f"{name} is required in a study context", reason="incomplete")

    def has(self, permission: Permission) -> bool:
        """True when this scope confers ``permission``."""
        return permission in self.permissions

    def require(self, permission: Permission) -> None:
        """Raise :class:`ScopeDenied` unless this scope confers ``permission``."""
        if permission not in self.permissions:
            raise ScopeDenied(
                f"role {self.role.value} does not permit {permission.value}",
                reason="insufficient_role",
            )

    def require_open_study(self) -> None:
        """Raise unless the study still accepts new work.

        A delivered or archived study is closed; starting a run against it would
        alter work a client has already been shown.
        """
        if not self.study_status.accepts_work:
            raise ScopeDenied(
                f"study is {self.study_status.value} and accepts no further work",
                reason="study_closed",
            )

    def audit_fields(self) -> dict[str, Any]:
        """Scope fields to attach to an audit or usage record."""
        return {
            "organization_id": self.organization_id,
            "client_id": self.client_id,
            "study_id": self.study_id,
            "actor_id": self.actor_id,
            "role": self.role.value,
            "request_id": self.request_id,
        }

    def __repr__(self) -> str:
        # Deliberately terse: study contexts appear in log lines and exception
        # messages, and a client id is less sensitive than a client name.
        return (
            f"StudyContext(org={self.organization_id}, client={self.client_id}, "
            f"study={self.study_id}, role={self.role.value})"
        )


@dataclass(frozen=True, slots=True)
class OrganizationContext:
    """Authorised organization-level scope, for administration only.

    Deliberately carries **no client or study id**: it cannot be used to read
    client research data. Operations that need client data require a
    :class:`StudyContext`, which requires a grant.
    """

    organization_id: str
    actor_id: str
    organization_role: OrganizationRole
    grant: ScopeGrant
    request_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.grant, ScopeGrant):
            raise ScopeDenied(
                "organization context requires an issued grant", reason="forged_scope"
            )

    @property
    def may_administer(self) -> bool:
        """True when this actor may create clients and studies and grant access."""
        return self.organization_role in (OrganizationRole.OWNER, OrganizationRole.ADMIN)

    def require_administer(self) -> None:
        """Raise unless this actor may administer the organization."""
        if not self.may_administer:
            raise ScopeDenied(
                "organization administration requires OWNER or ADMIN",
                reason="insufficient_role",
            )


@dataclass(frozen=True, slots=True)
class ResolvedAccess:
    """Internal result of an access lookup, before a context is built."""

    organization_role: OrganizationRole
    client_role: ScopeRole | None = None
    study_role: ScopeRole | None = None
    denied_reason: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
