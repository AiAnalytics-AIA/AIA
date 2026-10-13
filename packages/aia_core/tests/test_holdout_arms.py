"""The validation's model arms and the exclusions applied to them (7c)."""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.holdout.arms import Arm, ArmRefused, arm_plans, derangement
from aia_core.domain.panel_persona import panel_personas
from aia_core.domain.population.sampling import draw_panel_sample
from aia_core.domain.research_design import compile_design

DESIGN: dict[str, Any] = {
    "title": "Fiktivní validace",
    "n": 30,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {
                    "id": "rodina_q1",
                    "text": "Jak moc souhlasíte, že rodina je pro vás nejdůležitější?",
                    "typ": "skala",
                    "skala": [1, 4],
                },
                {
                    "id": "rodina_q2",
                    "text": "Jak často trávíte víkend s rodinou?",
                    "typ": "vyber",
                    "kategorie": ["Často", "Občas", "Nikdy"],
                },
            ],
        }
    ],
}


@pytest.fixture
def world(sampled_population: Any) -> Any:
    """200 personas from the fictional population, and the design's specification."""
    population = sampled_population().population
    sample = draw_panel_sample(population, {}, 200, 20261013)
    spec, problems = compile_design(DESIGN)
    assert spec is not None, problems
    return panel_personas(population, sample), spec


def _profiles(plans: Any) -> list[tuple[str, ...]]:
    return [plan.profiles for plan in plans]


def test_the_production_arm_without_exclusions_is_todays_persona(world: Any) -> None:
    personas, spec = world
    today = [personas.plan(spec, p) for p in personas.personas]
    assert arm_plans(personas, spec, Arm.D, exclusions={}) == tuple(today)


def test_arm_a_shows_no_persona_and_keeps_the_facts_and_styles(world: Any) -> None:
    personas, spec = world
    plans = arm_plans(personas, spec, Arm.A, exclusions={})
    today = [personas.plan(spec, p) for p in personas.personas]
    assert all(set(plan.profiles) == {""} for plan in plans)
    assert [p.persona for p in plans] == [p.persona for p in today]
    assert [p.facts for p in plans] == [p.facts for p in today]


def test_arm_b_shows_the_demographic_lines_alone_and_c_no_signal(world: Any) -> None:
    personas, spec = world
    b = arm_plans(personas, spec, Arm.B, exclusions={})
    c = arm_plans(personas, spec, Arm.C, exclusions={})
    for plan_b, plan_c in zip(b, c, strict=True):
        (profile_b,) = plan_b.profiles
        (profile_c,) = plan_c.profiles
        assert profile_b and len(profile_b) <= len(profile_c)
        assert "pracovní" not in profile_b.lower()  # no socio-economic line in B


def test_an_excluded_field_is_never_shown_in_any_arm(world: Any) -> None:
    personas, spec = world
    keep = arm_plans(personas, spec, Arm.D, exclusions={})
    out = arm_plans(personas, spec, Arm.D, exclusions={"rodina_q1": frozenset({"vzdelani"})})
    changed = 0
    for kept, dropped, persona in zip(keep, out, personas.personas, strict=True):
        row = personas.rows[persona.persona_id]
        education = row.get("vzdelani")
        if education is None:
            continue
        # The first-person prose lowercases a value, so compare without case.
        assert str(education).lower() in kept.profiles[0].lower()
        assert str(education).lower() not in dropped.profiles[0].lower()
        changed += 1
    assert changed > 0
    for arm in (Arm.B, Arm.C):
        for plan, persona in zip(
            arm_plans(personas, spec, arm, exclusions={"rodina_q2": frozenset({"vzdelani"})}),
            personas.personas,
            strict=True,
        ):
            education = personas.rows[persona.persona_id].get("vzdelani")
            if education is not None:
                assert str(education).lower() not in plan.profiles[0].lower()


def test_the_shuffled_arm_shows_each_respondent_someone_elses_profile(world: Any) -> None:
    personas, spec = world
    d = arm_plans(personas, spec, Arm.D, exclusions={})
    s = arm_plans(personas, spec, Arm.S, exclusions={}, shuffle_seed=5)
    by_id = {plan.persona.persona_id: plan.profiles for plan in d}
    shown = derangement([p.persona_id for p in personas.personas], 5)
    for plan in s:
        assert plan.profiles == by_id[shown[plan.persona.persona_id]]
        assert shown[plan.persona.persona_id] != plan.persona.persona_id
    assert sorted(_profiles(s)) == sorted(_profiles(d))
    # The person's own facts and styles stay: only the description moves.
    assert [p.persona for p in s] == [p.persona for p in d]
    assert arm_plans(personas, spec, Arm.S, exclusions={}, shuffle_seed=5) == s


def test_a_derangement_has_no_fixed_point_and_moves_only_with_its_seed() -> None:
    ids = [f"r{i}" for i in range(50)]
    a = derangement(ids, 1)
    assert sorted(a.values()) == sorted(ids)
    assert all(k != v for k, v in a.items())
    assert derangement(list(reversed(ids)), 1) == a
    assert derangement(ids, 2) != a
    with pytest.raises(ArmRefused) as refused:
        derangement(["only"], 1)
    assert refused.value.reason == "arm_too_few"


def test_the_shuffled_arm_needs_its_seed(world: Any) -> None:
    personas, spec = world
    with pytest.raises(ArmRefused) as refused:
        arm_plans(personas, spec, Arm.S, exclusions={})
    assert refused.value.reason == "arm_seed_missing"
