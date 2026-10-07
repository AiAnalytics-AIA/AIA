"""Deep Research's settings catalogue (ADR 0022, plan chunk 40)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aia_core.domain.deep_research.budgets import ROUTE_ALLOWANCES
from aia_core.domain.deep_research.request_limits import REQUEST_LIMITS
from aia_core.domain.deep_research.settings import (
    CATALOGUE,
    SECRET_WORDS,
    ApprovedValue,
    Origin,
    SettingDefinition,
    SettingGroup,
    SettingInvalid,
    SettingType,
    definition,
    effective,
    validate,
)

WHEN = datetime(2026, 10, 7, tzinfo=UTC)


def approved(value: object, version: int = 1) -> ApprovedValue:
    return ApprovedValue(value=value, version=version, approved_by="USR-1", approved_at=WHEN)  # type: ignore[arg-type]


# ------------------------------------------------------------------ defaults are today's code


def test_storing_nothing_changes_nothing_every_default_is_todays_constant() -> None:
    for preset, allowance in ROUTE_ALLOWANCES.items():
        for field in ("triage_reads", "crawl_pages", "connector_calls", "index_queries"):
            cap = getattr(allowance, field)
            key = f"budgets.allowance.{preset.lower()}.{field}"
            if cap:
                assert definition(key).default == cap
            else:  # a zero cap is not a setting: nothing to lower
                with pytest.raises(SettingInvalid):
                    definition(key)
    for kind, limits in REQUEST_LIMITS.items():
        assert definition(f"limits.{kind.value}.window_tokens").default == limits.window_tokens
        assert definition(f"limits.{kind.value}.answer_tokens").default == limits.answer_tokens
    for key in (
        "budgets.presets",
        "sources.tiers",
        "sources.reputation_register",
        "sources.confidence_weights",
        "extraction.record_presets",
    ):
        assert definition(key).default == "proposed"


def test_what_the_code_does_not_hold_defaults_to_unknown_never_zero() -> None:
    for key in (
        "provider.search.price_per_1000",
        "budgets.run_limit.standard",
        "models.light.model_id",
        "retention.snapshots",
        "quotas.model_requests_per_minute",
    ):
        assert definition(key).default is None


def test_with_nothing_approved_every_value_is_its_proposed_default() -> None:
    settings = effective({})
    assert {e.origin for e in settings.values} == {Origin.PROPOSED_DEFAULT}
    assert len(settings.values) == len(CATALOGUE)
    assert settings.value("extraction.denylist") == ()


# ------------------------------------------------------------------ the catalogue's own rules


def test_no_setting_names_a_secret() -> None:
    for defn in CATALOGUE:
        parts = defn.key.replace("_", ".").split(".")
        assert not set(parts) & set(SECRET_WORDS), defn.key
    with pytest.raises(ValueError, match="secret"):
        SettingDefinition(
            "provider.search.api_key", SettingGroup.PROVIDER, SettingType.TEXT, "x", None
        )


def test_every_key_is_unique_and_grouped() -> None:
    assert len({d.key for d in CATALOGUE}) == len(CATALOGUE)
    assert {d.group for d in CATALOGUE} == set(SettingGroup)


def test_only_a_number_can_be_a_cap() -> None:
    with pytest.raises(ValueError, match="lower-only"):
        SettingDefinition(
            "extraction.x.y", SettingGroup.EXTRACTION, SettingType.TEXT, "x", None, lower_only=True
        )


# ------------------------------------------------------------------ validation


def test_a_cap_only_lowers() -> None:
    assert validate("budgets.allowance.exhaustive.crawl_pages", 400) == 400
    with pytest.raises(SettingInvalid, match="only lower"):
        validate("budgets.allowance.exhaustive.crawl_pages", 1001)
    assert validate("limits.investigator.window_tokens", 100_000) == 100_000
    with pytest.raises(SettingInvalid, match="only lower"):
        validate("limits.investigator.window_tokens", 150_000)
    # A model-window default (None) has no ceiling of its own: any number lowers it.
    assert validate("limits.planner.window_tokens", 180_000) == 180_000


@pytest.mark.parametrize(
    ("key", "value", "reason"),
    [
        ("budgets.allowance.exhaustive.crawl_pages", -1, "below the minimum"),
        ("budgets.allowance.exhaustive.crawl_pages", 1.5, "whole number"),
        ("budgets.allowance.exhaustive.crawl_pages", True, "not a number"),
        ("provider.search.price_per_1000", float("nan"), "finite"),
        ("provider.search.price_per_1000", "5", "not a number"),
        ("provider.search.terms_url", "http://brave.com/terms", "https"),
        ("provider.search.terms_date", "7.10.2026", "date"),
        ("provider.search.failed_requests_billed", "yes", "yes or no"),
        ("models.light.model_id", "anthropic.claude-haiku", "EU inference profile"),
        ("models.light.model_id", "eu.anthropic.claude-latest", "EU inference profile"),
        ("sources.reputation_register", "done", "one of"),
        ("extraction.denylist", ["shop.example", "not a host"], "not a host name"),
        ("extraction.denylist", "shop.example", "not a list"),
        ("extraction.personal_data_patterns", ["(unclosed"], "valid pattern"),
        ("retention.snapshots", 0, "below the minimum"),
        ("provider.search.plan", "   ", "empty"),
        ("provider.search.plan", None, "withdrawing"),
        ("provider.search.api_key", "x", "not a Deep Research setting"),
    ],
)
def test_a_wrong_value_is_refused_with_its_reason(key: str, value: object, reason: str) -> None:
    with pytest.raises(SettingInvalid, match=reason):
        validate(key, value)


def test_values_are_normalised() -> None:
    assert validate("extraction.denylist", ["Shop.Example.", "a.example", "shop.example"]) == (
        "a.example",
        "shop.example",
    )
    assert validate("provider.search.terms_date", "2026-10-07") == "2026-10-07"
    assert validate("provider.search.price_per_1000", 5) == 5.0
    assert validate("models.light.model_id", "eu.anthropic.claude-haiku-4-5-20251001-v1:0") == (
        "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    )


# ------------------------------------------------------------------ what is in force


def test_an_approved_value_is_in_force_and_says_who_approved_it() -> None:
    settings = effective({"retention.snapshots": approved(90, version=3)})
    item = settings["retention.snapshots"]
    assert (item.value, item.origin, item.version, item.approved_by) == (
        90,
        Origin.APPROVED,
        3,
        "USR-1",
    )
    assert settings["retention.datasets"].origin is Origin.PROPOSED_DEFAULT


def test_a_stored_key_the_catalogue_does_not_hold_is_refused() -> None:
    with pytest.raises(SettingInvalid, match="not a Deep Research setting"):
        effective({"provider.search.api_key": approved("x")})


def test_a_stored_value_the_catalogue_now_refuses_fails_closed() -> None:
    with pytest.raises(SettingInvalid):
        effective({"budgets.allowance.exhaustive.crawl_pages": approved(5000)})


def test_the_method_digest_moves_with_a_cap_and_not_with_a_price_or_a_retention() -> None:
    base = effective({})
    cap = effective({"budgets.allowance.exhaustive.crawl_pages": approved(500)})
    price = effective({"provider.search.price_per_1000": approved(5.0)})
    retention = effective({"retention.snapshots": approved(30)})
    assert cap.method_digest() != base.method_digest()
    assert price.method_digest() == base.method_digest() == retention.method_digest()
    assert len({base.digest(), cap.digest(), price.digest(), retention.digest()}) == 4


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("extraction.denylist", ["shop.example"]),
        ("extraction.personal_data_patterns", [r"\bcustomer-\d+\b"]),
        ("extraction.record_presets", "approved"),
    ],
)
def test_the_method_digest_moves_with_each_admission_policy(key: str, value: object) -> None:
    # A stored capture or dataset is reused by its key, without its gates applied again: what a
    # run may admit must therefore move the key, or a newly denied host's capture is reused.
    assert definition(key).method
    changed = effective({key: approved(value)})
    assert changed.method_digest() != effective({}).method_digest()


def test_live_needs_every_required_setting_approved_and_a_table_approved_as_approved() -> None:
    nothing = effective({}).missing_for_live()
    required = tuple(d.key for d in CATALOGUE if d.required_for_live)
    assert nothing == required and "provider.search.price_per_1000" in nothing
    # Approving a status as "proposed" records the decision but does not sign it off.
    still = effective({"sources.reputation_register": approved("proposed")}).missing_for_live()
    assert "sources.reputation_register" in still
    signed = effective({"sources.reputation_register": approved("approved")}).missing_for_live()
    assert "sources.reputation_register" not in signed
    # Caps are not required: their proposed default is a safe ceiling.
    assert not any(k.startswith("budgets.allowance.") for k in nothing)
