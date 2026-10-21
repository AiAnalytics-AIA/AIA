"""A model's identity and its invocation target are two things (develop-spend-attribution 5a).

The **model identity** is what AIA reasons about: the pinned EU inference profile id
(``eu.<provider>.<model>…``, ADR 0010) that the catalogue prices, the model policy binds a
capability to, the request profile is declared for, the licence determination names the route of,
and every usage-ledger row records. It is validated as before and never loosened: an alias is
refused, a non-EU id is refused.

The **invocation target** is what the request names on the wire: the ``modelId`` of Bedrock's
``Converse`` path. By default it is the identity itself. To attribute spend to a deployment, an
operator creates an *application inference profile* over the identity's system profile, tagged
``Environment=<deployment>`` (``develop-spend-attribution`` chunk 1), and names its ARN as the
target. The call then goes through that profile and its cost carries the tag; the model, its
prices and its route are the identity's, unchanged.

So an ARN never becomes a model identity -- nothing prices, binds or records one -- and a target is
accepted only in the one shape chunk 1 creates: an application inference profile ARN in the
route's own EU region. Whether the profile really copies the identity's system profile is a fact
in AWS (``aws bedrock get-inference-profile``), checked by the operator who sets the pair; the
worker does not call AWS to find out, and says so in its refusal of a wrong shape.

Why no ``inference_profile_arn`` column (lane M9): the ledger's model fields carry the identity,
which is what a row is priced by; the reconciliation (chunk 3) compares the ledger's total with the
AWS cost record filtered by the tag over the same window, so it needs no per-row ARN. The target in
force is configuration, recorded with the worker's composition (``lead-orchestration`` LO12b/LO12c).
Pure: stdlib only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

__all__ = [
    "APPLICATION_PROFILE_ARN",
    "InvocationTargetRefused",
    "ModelInvocation",
    "invocation_target",
]

#: An application inference profile's ARN, as Bedrock issues it: its region, the account, the id.
APPLICATION_PROFILE_ARN: Final = re.compile(
    r"^arn:aws:bedrock:(?P<region>[a-z]{2}-[a-z]+-\d):(?P<account>\d{12}):"
    r"application-inference-profile/(?P<profile>[a-z0-9]{1,64})$"
)


class InvocationTargetRefused(ValueError):
    """A configured invocation target is not one AIA sends a model's calls through."""


@dataclass(frozen=True, slots=True)
class ModelInvocation:
    """One model as AIA knows it (``identity``) and as the request names it (``target``)."""

    identity: str
    target: str

    @property
    def through_application_profile(self) -> bool:
        return self.target != self.identity


def invocation_target(identity: str, target: str | None, *, region: str) -> ModelInvocation:
    """The pair a deployment configured, checked: ``target`` ``None`` (or blank) is the identity.

    A target is refused (:class:`InvocationTargetRefused`) unless it is an application inference
    profile ARN in ``region`` -- the route's source region, because Bedrock serves a profile only
    in its own region and ADR 0010's route is EU. ``identity`` is not re-validated here: each
    model's own settings validate it as they always did, before this is asked.
    """
    identity = identity.strip()
    if not identity:
        raise InvocationTargetRefused("a model's invocation target needs its model identity")
    raw = (target or "").strip()
    if not raw:
        return ModelInvocation(identity=identity, target=identity)
    found = APPLICATION_PROFILE_ARN.match(raw)
    if found is None:
        raise InvocationTargetRefused(
            f"{raw!r} is not an application inference profile ARN "
            "(arn:aws:bedrock:<region>:<account>:application-inference-profile/<id>); the model "
            f"identity {identity!r} is set on its own key and is never replaced by an ARN"
        )
    if found["region"] != region.strip() or not region.strip().startswith("eu-"):
        raise InvocationTargetRefused(
            f"the application inference profile {raw!r} is in {found['region']}, not the "
            f"route's EU region {region!r} (ADR 0010)"
        )
    return ModelInvocation(identity=identity, target=raw)
