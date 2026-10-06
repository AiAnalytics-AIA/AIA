"""The truth set: a closed format, fixed by a pinned hash, verified before it counts.

Plan ``deep-research-web-search.md`` chunk 25. Every figure here is FICTIONAL
(invented publishers on ``.example`` hosts, the year 2091); the real set's template
carries no value at all.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain.deep_research.reputation import REPUTATION_REGISTER_VERSION
from aia_core.domain.deep_research.truth_set import (
    FICTIONAL_REGISTER_VERSION,
    TruthSet,
    TruthSetRefused,
    VerificationStatus,
    add_pin,
    admit_truth_set,
    empty_pins,
    load_pins,
    load_truth_set,
    parse_value,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).parent / "fixtures" / "deep_research_accuracy"
FICTIONAL = FIXTURES / "fictional_truth_set.json"
FICTIONAL_PINS = FIXTURES / "pins.json"
TEMPLATE = ROOT / "docs" / "evaluation" / "deep-research" / "czech-public-facts.template.json"
REAL_PINS = ROOT / "docs" / "evaluation" / "deep-research" / "truth-set-pins.json"


def _raw(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _load(data: dict[str, Any]) -> TruthSet:
    return load_truth_set(json.dumps(data, ensure_ascii=False))


def _verified_real() -> dict[str, Any]:
    """A real-shaped set of one verified fact. Its value is a placeholder, never scored."""
    data = _raw(TEMPLATE)
    fact = data["facts"][0]
    fact["question"] = "Kolik obyvatel mělo Česko k 31. 12. roku X?"
    fact["expected"].update(
        value_text="1",
        period="2091",
        geography="CZ",
        population="PERSONS",
        measure_name="počet obyvatel",
    )
    fact["primary"].update(url="https://csu.gov.cz/x", dataset_id="X", cell="X!CZ/2091")
    fact["recorded_at"] = "2026-10-06"
    fact["recorded_by"] = "researcher"
    fact["verification"] = {
        "status": "verified",
        "verified_by": "second researcher",
        "verified_at": "2026-10-07",
        "note": None,
    }
    data["facts"] = [fact]
    data["set_id"] = "test-real-shape"
    return data


# --------------------------------------------------------------------------- values


@pytest.mark.parametrize(
    ("text", "value", "decimals"),
    [
        ("10 450", 10450.0, 0),
        ("10\u00a0450,6", 10450.6, 1),
        ("10\u202f450", 10450.0, 0),
        ("42,5", 42.5, 1),
        ("-0,30", -0.3, 2),
        ("\u22121,2", -1.2, 1),
        ("450", 450.0, 0),
    ],
)
def test_a_printed_czech_figure_is_read_with_its_decimals(
    text: str, value: float, decimals: int
) -> None:
    assert parse_value(text) == (value, decimals)


@pytest.mark.parametrize("text", ["42.5", "1 0450", "45 %", "", "4 500 0", "1,2 mld."])
def test_anything_but_a_printed_figure_is_refused(text: str) -> None:
    with pytest.raises(ValueError):
        parse_value(text)


# --------------------------------------------------------------------------- format


def test_the_fictional_fixture_is_fictional_through_and_through() -> None:
    truth = load_truth_set(FICTIONAL.read_text(encoding="utf-8"))
    assert truth.fictional
    assert truth.register_version == FICTIONAL_REGISTER_VERSION
    for fact in truth.facts:
        assert fact.primary.host is not None and fact.primary.host.endswith(".example")
        assert fact.expected.period is not None and fact.expected.period.startswith("209")
        assert fact.scorable
    assert {p.canonical_name for p in truth.register().publishers} == {
        "Fiktivní statistický úřad",
        "Fiktivní obchodní komora",
    }


def test_the_real_template_has_fifty_slots_and_no_value() -> None:
    truth = load_truth_set(TEMPLATE.read_text(encoding="utf-8"))
    assert not truth.fictional
    assert truth.register_version == REPUTATION_REGISTER_VERSION
    assert len(truth.facts) == 50
    assert dict(truth.topics()) == {"population": 13, "prices": 13, "consumption": 12, "trade": 12}
    assert len(truth.unverified()) == 50
    for fact in truth.facts:
        assert fact.expected.value_text is None
        assert fact.question is None
        assert fact.primary.url is None and fact.primary.cell is None
        assert fact.verification.status is VerificationStatus.UNVERIFIED
        assert not fact.scorable


def test_the_real_manifest_pins_nothing_yet() -> None:
    assert load_pins(REAL_PINS.read_text(encoding="utf-8")).pins == ()


def test_the_fixture_is_pinned_at_its_current_hash() -> None:
    truth = load_truth_set(FICTIONAL.read_text(encoding="utf-8"))
    pins = load_pins(FICTIONAL_PINS.read_text(encoding="utf-8"))
    pin = pins.pin_for(truth.set_id)
    assert pin is not None and pin.sha256 == truth.sha256()


def test_the_hash_ignores_formatting_and_follows_content() -> None:
    data = _raw(FICTIONAL)
    a = load_truth_set(json.dumps(data))
    b = load_truth_set(json.dumps(data, indent=4, ensure_ascii=False))
    assert a.sha256() == b.sha256()
    data["facts"][0]["expected"]["value_text"] = "10 451"
    assert load_truth_set(json.dumps(data)).sha256() != a.sha256()


def _broken(change: Any) -> None:
    data = _raw(FICTIONAL)
    change(data)
    with pytest.raises(ValidationError):
        _load(data)


def test_an_unknown_field_is_refused() -> None:
    _broken(lambda d: d["facts"][0].update(extra="x"))


def test_a_unit_outside_the_vocabulary_is_refused() -> None:
    _broken(lambda d: d["facts"][0]["expected"].update(unit="Kč"))


def test_a_period_that_cannot_be_placed_is_refused() -> None:
    _broken(lambda d: d["facts"][0]["expected"].update(period="Q2"))


def test_a_scale_no_text_writes_is_refused() -> None:
    _broken(lambda d: d["facts"][0]["expected"].update(scale=100))


def test_a_fact_that_is_not_class_c_is_refused() -> None:
    _broken(lambda d: d["facts"][0].update(data_class="CLASS_B_DERIVED_CLIENT"))


def test_a_fact_id_names_its_topic() -> None:
    _broken(lambda d: d["facts"][0].update(fact_id="trade-09"))


def test_two_facts_asking_one_question_are_refused() -> None:
    _broken(lambda d: d["facts"][1].update(question=d["facts"][0]["question"]))


def test_a_publisher_outside_the_register_is_refused() -> None:
    _broken(lambda d: d["facts"][0]["primary"].update(publisher="register:nobody"))


def test_a_fictional_fact_on_a_real_host_is_refused() -> None:
    _broken(lambda d: d["facts"][0]["primary"].update(url="https://csu.gov.cz/x"))


def test_a_fictional_publisher_on_a_real_host_is_refused() -> None:
    _broken(lambda d: d["fictional_publishers"][0].update(hosts=["statistika.cz"]))


def test_a_real_set_names_no_fictional_publisher() -> None:
    data = _raw(TEMPLATE)
    data["fictional_publishers"] = [{"name": "Fiktivní úřad", "hosts": ["x.example"]}]
    with pytest.raises(ValidationError):
        _load(data)


def test_an_absolute_tolerance_states_its_reason() -> None:
    _broken(
        lambda d: d["facts"][0].update(
            tolerance={"kind": "absolute", "amount": "0,1", "reason": None}
        )
    )


def test_a_verified_fact_is_complete_and_names_its_verifier() -> None:
    _load(_verified_real())
    missing_cell = _verified_real()
    missing_cell["facts"][0]["primary"]["cell"] = None
    with pytest.raises(ValidationError, match=r"primary\.cell"):
        _load(missing_cell)
    anonymous = _verified_real()
    anonymous["facts"][0]["verification"]["verified_by"] = None
    with pytest.raises(ValidationError, match="who verified"):
        _load(anonymous)
    early = _verified_real()
    early["facts"][0]["verification"]["verified_at"] = "2026-10-01"
    with pytest.raises(ValidationError, match="before it was recorded"):
        _load(early)


# --------------------------------------------------------------------------- pins


def test_admission_needs_the_pin_and_the_same_hash() -> None:
    truth = load_truth_set(FICTIONAL.read_text(encoding="utf-8"))
    with pytest.raises(TruthSetRefused, match="not pinned"):
        admit_truth_set(truth, empty_pins(), allow_unverified=True)
    pins = load_pins(FICTIONAL_PINS.read_text(encoding="utf-8"))
    admit_truth_set(truth, pins, allow_unverified=True)
    data = _raw(FICTIONAL)
    data["facts"][0]["expected"]["value_text"] = "10 451"
    with pytest.raises(TruthSetRefused, match="changed after it was fixed"):
        admit_truth_set(_load(data), pins, allow_unverified=True)


def test_unverified_facts_need_the_explicit_allowance() -> None:
    truth = load_truth_set(FICTIONAL.read_text(encoding="utf-8"))
    pins = load_pins(FICTIONAL_PINS.read_text(encoding="utf-8"))
    with pytest.raises(TruthSetRefused, match="not verified"):
        admit_truth_set(truth, pins, allow_unverified=False)


def test_a_real_set_is_never_scored_unverified() -> None:
    real = _load(_verified_real())
    pins = add_pin(empty_pins(), real, path="x.json", pinned_at=date(2026, 10, 7), pinned_by="r")
    admit_truth_set(real, pins, allow_unverified=False)
    with pytest.raises(TruthSetRefused, match="only in a fictional set"):
        admit_truth_set(real, pins, allow_unverified=True)


def test_the_template_cannot_be_pinned_until_every_fact_is_verified() -> None:
    template = load_truth_set(TEMPLATE.read_text(encoding="utf-8"))
    with pytest.raises(TruthSetRefused, match="50 fact"):
        add_pin(empty_pins(), template, path="t.json", pinned_at=date(2026, 10, 6), pinned_by="r")


def test_a_set_id_is_pinned_once() -> None:
    truth = load_truth_set(FICTIONAL.read_text(encoding="utf-8"))
    pins = load_pins(FICTIONAL_PINS.read_text(encoding="utf-8"))
    again = add_pin(pins, truth, path="elsewhere.json", pinned_at=date(2027, 1, 1), pinned_by="x")
    assert again == pins
    data = _raw(FICTIONAL)
    data["facts"][0]["expected"]["value_text"] = "10 451"
    with pytest.raises(TruthSetRefused, match="new set_id"):
        add_pin(pins, _load(data), path="x.json", pinned_at=date(2027, 1, 1), pinned_by="x")


def test_a_manifest_pinning_one_set_twice_is_refused() -> None:
    data = _raw(FICTIONAL_PINS)
    data["pins"] = data["pins"] * 2
    with pytest.raises(ValidationError, match="pinned twice"):
        load_pins(json.dumps(data))
