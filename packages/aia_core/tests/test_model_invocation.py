"""A model's identity and its invocation target (develop-spend-attribution 5a).

The identity (an ``eu.`` profile id) is what is priced, bound and recorded; the target is what
the Converse URL names: the identity itself, or an application inference profile ARN over it in
the route's EU region. Nothing here calls AWS; the ARNs are fictional.
"""

from __future__ import annotations

import pytest

from aia_core.domain.model_invocation import (
    InvocationTargetRefused,
    ModelInvocation,
    invocation_target,
)

MODEL = "eu.test.route-model:1"
PROFILE = "arn:aws:bedrock:eu-central-1:123456789012:application-inference-profile/a1b2c3d4e5f6"


def test_without_a_target_the_identity_is_what_is_called() -> None:
    for unset in (None, "", "   "):
        called = invocation_target(MODEL, unset, region="eu-central-1")
        assert called == ModelInvocation(identity=MODEL, target=MODEL)
        assert not called.through_application_profile


def test_an_application_profile_in_the_routes_region_is_the_target() -> None:
    called = invocation_target(MODEL, f"  {PROFILE} ", region="eu-central-1")
    assert called == ModelInvocation(identity=MODEL, target=PROFILE)
    assert called.through_application_profile


@pytest.mark.parametrize(
    ("target", "match"),
    [
        # A system-defined profile's ARN, a foundation model's, a bare id: not what chunk 1 makes.
        (
            "arn:aws:bedrock:eu-central-1:123456789012:inference-profile/eu.test.route-model:1",
            "not an application inference profile ARN",
        ),
        (
            "arn:aws:bedrock:eu-central-1::foundation-model/test.route-model:1",
            "not an application inference profile ARN",
        ),
        ("eu.test.other-model:1", "not an application inference profile ARN"),
        (PROFILE.replace("123456789012", "1234"), "not an application inference profile ARN"),
        (PROFILE + "/extra", "not an application inference profile ARN"),
        (PROFILE.replace("eu-central-1", "us-east-1"), "not the route's EU region"),
        (PROFILE.replace("eu-central-1", "eu-west-1"), "not the route's EU region"),
    ],
)
def test_any_other_target_is_refused_by_name(target: str, match: str) -> None:
    with pytest.raises(InvocationTargetRefused, match=match):
        invocation_target(MODEL, target, region="eu-central-1")


def test_a_target_in_a_non_eu_region_is_refused_even_where_the_region_matches() -> None:
    us = PROFILE.replace("eu-central-1", "us-east-1")
    with pytest.raises(InvocationTargetRefused, match="EU region"):
        invocation_target(MODEL, us, region="us-east-1")


def test_a_target_needs_its_identity() -> None:
    with pytest.raises(InvocationTargetRefused, match="model identity"):
        invocation_target("  ", PROFILE, region="eu-central-1")


@pytest.mark.parametrize(
    "target",
    [
        PROFILE.replace("eu-central-1", "us-east-1"),
        PROFILE.replace("application-inference-profile", "inference-profile"),
        PROFILE + "/extra",
    ],
)
def test_a_refusal_never_prints_the_account_id(target: str) -> None:
    """A start-up refusal names the rule broken; the account id in the ARN is masked."""
    with pytest.raises(InvocationTargetRefused) as refused:
        invocation_target(MODEL, target, region="eu-central-1")
    assert "123456789012" not in str(refused.value)
    assert "************" in str(refused.value)
    assert MODEL not in str(refused.value)
