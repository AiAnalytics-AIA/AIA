"""A confirmation run's graph, questionnaire and cost, from its preregistration (7e3)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from aia_core.domain.holdout.bank import HoldoutItem, Option, SourceDocument
from aia_core.domain.holdout.preregistration import HoldoutRefused
from aia_core.domain.holdout.run import (
    ARM_KIND,
    SAMPLE_KIND,
    SCORE_KIND,
    SampledPerson,
    arm_node_key,
    arm_record,
    preregistered_blocks,
    read_arm_record,
    sample_sha256,
    scoring_inputs,
    system_mismatch,
    validation_cost_ceiling,
    validation_requests,
    validation_specification,
    validation_steps,
)
from aia_core.domain.panel_source import pinned_components
from aia_core.domain.population.sampling import draw_panel_sample
from aia_core.domain.workflow import validate_dag


def test_the_graph_samples_once_runs_each_arm_replicate_on_it_and_scores_them_all(
    holdout_records: Any,
) -> None:
    steps = validation_steps(holdout_records.preregistration())
    validate_dag(steps)
    by_key = {s.node_key: s for s in steps}
    arms = [arm_node_key(a, k) for a in ("A", "B", "C", "D", "S") for k in (1, 2, 3)]
    assert list(by_key) == ["sample", *arms, "score"]
    assert by_key["sample"].kind == SAMPLE_KIND and by_key["sample"].depends_on == ()
    assert all(by_key[k].kind == ARM_KIND and by_key[k].depends_on == ("sample",) for k in arms)
    assert by_key["score"].kind == SCORE_KIND and set(by_key["score"].depends_on) == set(arms)
    # Every step reads the run's recorded population, and through nothing else.
    assert all(s.consumes_population for s in steps)


def test_the_questionnaire_is_the_items_as_fielded_in_the_preregistered_block_order(
    holdout_records: Any,
) -> None:
    prereg = holdout_records.preregistration()
    spec = validation_specification(holdout_records.bank(), prereg)
    assert [q.id for q in spec.questions] == ["c1", "c2", "c3"]
    assert preregistered_blocks(prereg) == (("c1", "c2"), ("c3",))
    first = spec.questions[0]
    assert first.typ == "vyber" and first.text.startswith("Do jaké míry souhlasíte")
    # An option's position is its code's: the order fielded.
    assert first.options == ("Rozhodně ano", "Spíše ano", "Ne")
    assert spec.n == 600 and spec.batteries == ()


def test_another_bank_or_an_item_code_would_answer_as_a_fact_is_refused(
    holdout_records: Any,
) -> None:
    prereg = holdout_records.preregistration()
    with pytest.raises(HoldoutRefused) as other:
        validation_specification(
            holdout_records.bank(), holdout_records.preregistration(bank_sha256="e" * 64)
        )
    assert other.value.reason == "holdout_bank_mismatch"
    # "Kolik je vám let?" is a persona fact: code would answer it from the respondent's age.
    with pytest.raises(HoldoutRefused) as fact:
        validation_specification(holdout_records.bank(wording={"c3": "Kolik je vám let?"}), prereg)
    assert fact.value.reason == "holdout_item_is_a_fact"


def test_the_ceiling_is_every_request_at_its_reservation_and_unknown_is_never_zero(
    holdout_records: Any,
) -> None:
    prereg = holdout_records.preregistration()
    # 600 respondents x 2 blocks x 5 model arms x 3 replicates; the code baselines cost nothing.
    assert validation_requests(prereg) == 600 * 2 * 5 * 3
    assert validation_cost_ceiling(prereg, 0.01) == pytest.approx(180.0)
    assert validation_cost_ceiling(prereg, None) is None
    assert validation_cost_ceiling(prereg, 0.0) is None


def test_a_component_or_population_that_moved_is_named_and_the_binding_is_left_to_the_gateway(
    holdout_records: Any,
) -> None:
    current = pinned_components("pv_live")
    prereg = holdout_records.preregistration(system={**current, "model_binding": "any/binding"})
    assert system_mismatch(prereg, current) == ()
    assert system_mismatch(prereg, pinned_components("pv_moved")) == ("population_version",)
    assert system_mismatch(prereg, {**current, "persona_mode": "other"}) == ("persona_mode",)


def test_an_answer_is_recorded_as_its_code_beside_the_probabilities_it_was_drawn_from(
    holdout_records: Any,
) -> None:
    spec = validation_specification(holdout_records.bank(), holdout_records.preregistration())
    codes = {q.id: ["1", "2", "3"] for q in spec.questions}
    probs = {"probabilities": [0.6, 0.3, 0.1]}
    rows = [
        ("R1", {"c1": "Spíše ano", "c2": "Ne", "c3": "Rozhodně ano"}),
        ("R2", {"c1": "Ne", "c2": "Ne", "c3": "Spíše ano"}),
    ]
    details = [dict.fromkeys(("c1", "c2", "c3"), probs)] * 2
    record = arm_record(spec, codes, rows, details)
    assert record["answers"]["c1"] == {"R1": "2", "R2": "3"}
    assert record["probabilities"]["c3"]["R2"] == [0.6, 0.3, 0.1]
    run = read_arm_record("D", 2, record)
    assert (run.arm, run.replicate) == ("D", 2)
    assert run.answers[("c2", "R1")] == "3"
    assert run.probabilities[("c1", "R1")] == (0.6, 0.3, 0.1)


@pytest.mark.parametrize(
    "broken",
    [
        lambda rows, details: ([(rows[0][0], {**rows[0][1], "c1": None})], details[:1]),
        lambda rows, details: ([(rows[0][0], {**rows[0][1], "c1": "Snad"})], details[:1]),
        lambda rows, details: (rows[:1], [{**details[0], "c2": {}}]),
        lambda rows, details: (rows[:1], [{**details[0], "c2": {"probabilities": [1.0]}}]),
        lambda rows, details: (rows, details[:1]),
    ],
)
def test_a_missing_answer_or_draw_is_refused_never_scored_as_an_answer(
    holdout_records: Any, broken: Any
) -> None:
    spec = validation_specification(holdout_records.bank(), holdout_records.preregistration())
    codes = {q.id: ["1", "2", "3"] for q in spec.questions}
    probs = {"probabilities": [0.6, 0.3, 0.1]}
    rows = [
        ("R1", {"c1": "Ne", "c2": "Ne", "c3": "Ne"}),
        ("R2", {"c1": "Ne", "c2": "Ne", "c3": "Ne"}),
    ]
    details = [dict.fromkeys(("c1", "c2", "c3"), probs)] * 2
    with pytest.raises(HoldoutRefused) as refused:
        arm_record(spec, codes, *broken(rows, details))
    assert refused.value.reason == "holdout_answer_missing"


def test_repeated_option_labels_are_refused_because_an_answer_could_not_name_its_code(
    holdout_records: Any,
) -> None:
    bank = holdout_records.bank()
    repeated = replace(bank.items[0], options=(Option("1", "Ano"), Option("2", "Ano")))
    bank = replace(bank, items=(repeated, *bank.items[1:]))
    with pytest.raises(HoldoutRefused) as refused:
        validation_specification(bank, holdout_records.preregistration())
    assert refused.value.reason == "holdout_option_labels_repeat"


def test_the_samples_identity_is_who_was_drawn_and_moves_only_with_the_draw(
    sampled_population: Any,
) -> None:
    population = sampled_population().population
    first = draw_panel_sample(population, None, 200, 5)
    assert sample_sha256(first) == sample_sha256(draw_panel_sample(population, None, 200, 5))
    assert sample_sha256(first) != sample_sha256(draw_panel_sample(population, None, 200, 6))


def _scored_item(field: str, *, ages: tuple[int, int] | None = None) -> HoldoutItem:
    return HoldoutItem(
        field=field,
        survey="ISSP_2022_CZ",
        domain="family",
        wording="Jak moc souhlasíte?",
        options=(Option("1", "Ano"), Option("2", "Spíše ano"), Option("3", "Ne")),
        measured_ages=ages,
        ordinal=True,
        source=SourceDocument("https://example.org/q.pdf", "d" * 64, "3", field),
    )


@pytest.fixture
def scored_population(holdout_population: Any) -> Any:
    """Six people: a core item answered by all but one, a matched-block item, and their cells."""
    return holdout_population(
        {
            "vek": ("core", "POPULATION_ANCHOR", ("25", "40", "70", "33", "52", None)),
            "pohlavi": ("core", "POPULATION_ANCHOR", ("muž", "žena", "muž", "žena", "muž", "žena")),
            "vek_skupina": (
                "core",
                "POPULATION_ANCHOR",
                ("18-29", "30-44", "60-74", "30-44", "45-59", None),
            ),
            "core_item": ("core", "POPULATION_ANCHOR", ("1", "2", "3", None, "1", "2")),
            "block_item": ("family_health", "MATCHED_WHOLE_BLOCK", ("3", "3", "2", "1", "1", "2")),
        }
    )


def _people() -> list[SampledPerson]:
    return [SampledPerson(f"R{i}", i, f"D{i}", 1.0 + i) for i in range(6)]


def test_each_person_is_scored_on_their_own_answer_where_it_is_real(
    scored_population: Any,
) -> None:
    truths, respondents, rows = scoring_inputs(
        scored_population,
        [_scored_item("core_item", ages=(18, 65)), _scored_item("block_item")],
        _people(),
    )
    core, block = truths
    # Ages outside the survey's (R2 is 70) and an unknown age (R5) are not scored; a missing
    # answer (R3) is not scored as any answer.
    assert core.answers == {"R0": "1", "R1": "2", "R4": "1"}
    assert core.person_level is True
    # A matched block's answer is its donor's, scored on every row, never Brier'd as the person's.
    assert block.answers == {f"R{i}": v for i, v in enumerate(("3", "3", "2", "1", "1", "2"))}
    assert block.person_level is False
    assert [r.cell for r in respondents] == [
        "muž|18-29",
        "žena|30-44",
        "muž|60-74",
        "žena|30-44",
        "muž|45-59",
        None,  # an unknown age band puts nobody in a cell
    ]
    assert respondents[3].weight == 4.0 and respondents[3].donor_id == "D3"
    assert rows == {f"R{i}": i for i in range(6)}


def test_a_stored_answer_that_is_no_option_or_an_item_the_population_lacks_is_refused(
    scored_population: Any,
) -> None:
    with pytest.raises(HoldoutRefused) as lacked:
        scoring_inputs(scored_population, [_scored_item("absent")], _people())
    assert lacked.value.reason == "holdout_item_not_in_population"
    narrow = replace(_scored_item("block_item"), options=(Option("1", "A"), Option("2", "B")))
    with pytest.raises(HoldoutRefused) as coerced:
        scoring_inputs(scored_population, [narrow], _people())
    assert coerced.value.reason == "holdout_truth_not_an_option"
