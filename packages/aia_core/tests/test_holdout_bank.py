"""The holdout item bank and which items a population can hold out (7b)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from aia_core.domain.holdout.bank import (
    BANK_VERSION,
    ItemBankRefused,
    read_item_bank,
)
from aia_core.domain.holdout.eligibility import (
    MIN_EFFECTIVE_DONORS,
    assess_bank,
    assess_item,
    scored_rows,
)

SHA = "a" * 64


def _item(field: str, **overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "field": field,
        "survey": "ISSP_2022_CZ",
        "domain": "family_health",
        "wording": "Jak moc souhlasíte s tím, že ... ?",
        "options": [
            {"code": "1", "label": "Rozhodně souhlasím"},
            {"code": "2", "label": "Spíše souhlasím"},
            {"code": "3", "label": "Spíše nesouhlasím"},
            {"code": "4", "label": "Rozhodně nesouhlasím"},
        ],
        "measured_ages": None,
        "ordinal": True,
        "source": {
            "url": "https://example.org/issp2022cz.pdf",
            "sha256": SHA,
            "page": "12",
            "item_id": "Q3a",
        },
    }
    item.update(overrides)
    return item


def _bank(*items: dict[str, Any]) -> bytes:
    return json.dumps({"bank_version": BANK_VERSION, "items": list(items)}).encode()


@pytest.fixture
def population(holdout_population: Any) -> Any:
    """900 rows, a donor of their own up to ``donors`` (so support is about ``donors``)."""

    def build(n: int = 900, donors: int = 600) -> Any:
        def cells(f: Any) -> tuple[str | None, ...]:
            return tuple(f(i) for i in range(n))

        return holdout_population(
            {
                "vek": ("core", "POPULATION_ANCHOR", cells(lambda i: str(20 + i % 60))),
                "core_donor_id": (
                    "provenance",
                    "PROVENANCE_OR_CORE",
                    cells(lambda i: f"c{i % donors}"),
                ),
                "_donor_family_health_id": (
                    "provenance",
                    "PROVENANCE_OR_CORE",
                    cells(lambda i: f"f{i % donors}"),
                ),
                "pohlavi": (
                    "core",
                    "POPULATION_ANCHOR",
                    cells(lambda i: "muž" if i % 2 else "žena"),
                ),
                "rodina_q3a": (
                    "family_health",
                    "MATCHED_WHOLE_BLOCK",
                    cells(lambda i: str(1 + i % 4)),
                ),
                "piaac_skill": (
                    "piaac_core",
                    "MEASURED_CORE_PIAAC",
                    cells(lambda i: str(1 + i % 3)),
                ),
                "modelled_pref": (
                    "marketing",
                    "MODELED_MARKETING_PRIOR",
                    cells(lambda i: str(1 + i % 4)),
                ),
                "sparse_q": (
                    "family_health",
                    "MATCHED_WHOLE_BLOCK",
                    cells(lambda i: str(1 + i % 4) if i % 3 == 0 else None),
                ),
            }
        )

    return build


def test_a_bank_is_pinned_by_its_canonical_form_not_its_formatting() -> None:
    raw = {"bank_version": BANK_VERSION, "items": [_item("rodina_q3a")]}
    compact = json.dumps(raw).encode()
    spaced = json.dumps(raw, indent=4).encode()
    assert read_item_bank(compact).sha256 == read_item_bank(spaced).sha256
    changed = _bank(_item("rodina_q3a", wording="Jiné znění?"))
    assert read_item_bank(changed).sha256 != read_item_bank(compact).sha256


@pytest.mark.parametrize(
    ("item", "reason"),
    [
        (_item("x", survey="EUROBAROMETER"), "item_survey"),
        (_item("x", options=[{"code": "1", "label": "Ano"}]), "item_not_closed"),
        (
            _item("x", options=[{"code": str(i), "label": str(i)} for i in range(12)]),
            "item_not_closed",
        ),
        (_item("x", wording="  "), "item_bank_malformed"),
        (
            _item(
                "x", source={"url": "http://x.cz/q.pdf", "sha256": SHA, "page": "1", "item_id": "Q"}
            ),
            "item_source_missing",
        ),
        (
            _item(
                "x",
                source={"url": "https://x.cz/q.pdf", "sha256": "abc", "page": "1", "item_id": "Q"},
            ),
            "item_source_missing",
        ),
        (_item("x", source=None), "item_source_missing"),
        (_item("x", measured_ages=[66, 18]), "item_bank_malformed"),
        (_item("x", ordinal="yes"), "item_bank_malformed"),
        (
            _item("x", options=[{"code": "1", "label": "A"}, {"code": "1", "label": "B"}]),
            "item_bank_malformed",
        ),
    ],
)
def test_a_bank_that_is_not_well_formed_is_refused_by_name(
    item: dict[str, Any], reason: str
) -> None:
    with pytest.raises(ItemBankRefused) as refused:
        read_item_bank(_bank(item))
    assert refused.value.reason == reason


def test_a_bank_without_its_version_or_items_or_with_a_field_twice_is_refused() -> None:
    with pytest.raises(ItemBankRefused) as refused:
        read_item_bank(json.dumps({"items": [_item("x")]}).encode())
    assert refused.value.reason == "item_bank_version"
    with pytest.raises(ItemBankRefused):
        read_item_bank(_bank())
    with pytest.raises(ItemBankRefused):
        read_item_bank(_bank(_item("x"), _item("x")))
    with pytest.raises(ItemBankRefused):
        read_item_bank(b"not json")


def test_a_measured_answered_supported_item_is_eligible(population: Any) -> None:
    bank = read_item_bank(_bank(_item("rodina_q3a")))
    (assessment,) = assess_bank(population(), bank)
    assert assessment.eligible, assessment.reasons
    assert assessment.coverage == pytest.approx(1.0)
    assert assessment.donor_field == "_donor_family_health_id"
    assert assessment.effective_donors is not None
    assert assessment.effective_donors >= MIN_EFFECTIVE_DONORS


def test_a_modelled_field_is_never_truth(population: Any) -> None:
    item = read_item_bank(_bank(_item("modelled_pref"))).item("modelled_pref")
    assert "not_measured" in assess_item(population(), item).reasons


def test_what_the_respondent_is_told_is_never_held_out(population: Any) -> None:
    item = read_item_bank(
        _bank(
            _item(
                "pohlavi",
                options=[{"code": "muž", "label": "muž"}, {"code": "žena", "label": "žena"}],
            )
        )
    ).item("pohlavi")
    assert "given_to_respondent" in assess_item(population(), item).reasons


def test_a_stored_value_that_is_not_an_option_fails_and_is_never_coerced(population: Any) -> None:
    three = [{"code": str(c), "label": str(c)} for c in (1, 2, 3)]
    item = read_item_bank(_bank(_item("rodina_q3a", options=three))).item("rodina_q3a")
    assert "value_not_an_option" in assess_item(population(), item).reasons


def test_an_item_too_few_answered_or_supported_fails_with_every_reason(population: Any) -> None:
    sparse = read_item_bank(_bank(_item("sparse_q"))).item("sparse_q")
    assert "low_coverage" in assess_item(population(), sparse).reasons
    thin = read_item_bank(_bank(_item("rodina_q3a"))).item("rodina_q3a")
    reasons = assess_item(population(donors=200), thin).reasons
    assert reasons == ("low_support",)


def test_a_core_item_is_scored_only_in_the_ages_its_survey_asked(population: Any) -> None:
    world = population()
    item = read_item_bank(
        _bank(
            _item(
                "piaac_skill",
                survey="PIAAC_2023_CZ",
                domain="skills",
                measured_ages=[18, 65],
                options=[{"code": str(c), "label": str(c)} for c in (1, 2, 3)],
            )
        )
    ).item("piaac_skill")
    rows = scored_rows(world, item)
    ages = world.column("vek")
    assert rows and all(18 <= int(ages[i]) <= 65 for i in rows)  # type: ignore[arg-type]
    assert len(rows) < len(ages)
    assessment = assess_item(world, item)
    assert assessment.donor_field == "core_donor_id"
    assert assessment.eligible, assessment.reasons


def test_an_item_the_population_lacks_says_so(population: Any) -> None:
    item = read_item_bank(_bank(_item("not_there"))).item("not_there")
    assert assess_item(population(), item).reasons == ("not_in_population",)


def test_a_missing_donor_makes_support_unknown_never_counted(population: Any) -> None:
    world = population()
    donors = list(world.columns["_donor_family_health_id"])
    donors[5] = None
    world.columns["_donor_family_health_id"] = tuple(donors)
    item = read_item_bank(_bank(_item("rodina_q3a"))).item("rodina_q3a")
    assessment = assess_item(world, item)
    assert "donor_unknown" in assessment.reasons
    assert assessment.effective_donors is None
