"""A confirmation run's graph, questionnaire and cost, from its preregistration (7e3)."""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.holdout.preregistration import HoldoutRefused
from aia_core.domain.holdout.run import (
    ARM_KIND,
    SAMPLE_KIND,
    SCORE_KIND,
    arm_node_key,
    preregistered_blocks,
    system_mismatch,
    validation_cost_ceiling,
    validation_requests,
    validation_specification,
    validation_steps,
)
from aia_core.domain.panel_source import pinned_components
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
