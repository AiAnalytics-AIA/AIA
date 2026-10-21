"""Compiling a design and deciding whether it can run (ADR 0016, PR C chunk 4).

The compile rules follow the unit where cited; what the unit does and AIA does
not yet (conditional routing, familiarity questions) is refused by readiness,
never skipped. The fictional dataset is deterministic and answers only what the
specification asks.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from aia_core.domain.fieldwork import DataOrigin, InvalidDataset, validate_dataset
from aia_core.domain.research_design import (
    AIA_READINESS_V1,
    COMPILER_VERSION,
    DONT_KNOW,
    CheckStatus,
    ResearchSpecification,
    SampleSizeLimits,
    SampleSizeProblem,
    assess_readiness,
    compile_design,
    prepare,
    sample_size_problem,
)
from aia_core.domain.sociomap.relations import AUDIT_PROVISIONAL_N_MIN
from aia_core.domain.synthetic_fieldwork import synthetic_dataset

DESIGN: dict[str, Any] = {
    "title": "Ranní nápoj",
    "n": 120,
    "audience": {"source_mode": "population", "strategy": "population", "filters": {}},
    "sections": [
        {
            "type": "questions",
            "id": "Úvod",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                {
                    "id": "q2",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic", "Kávu"],
                    "povolit_nevim": True,
                },
                {
                    "text": "Co ještě?",
                    "typ": "multi",
                    "kategorie": ["Pečivo", "Ovoce"],
                },
                {"id": "q1", "text": "Proč?", "typ": "otevrena"},
            ],
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_type": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda", "Káva"],
            "object_question": "Jak hodnotíte",
        },
        {"type": "notes", "text": "not part of the study"},
    ],
}


def _check(readiness: Any, check_id: str) -> Any:
    return next(c for c in readiness.checks if c.id == check_id)


def test_a_design_compiles_to_what_fieldwork_asks() -> None:
    spec, problems = compile_design(DESIGN)
    assert problems == () and spec is not None
    q = {x.id: x for x in spec.questions}
    assert list(q) == ["q1", "q2", "uvod_3", "q1_2"], "ids stay unique; a missing id is made"
    assert q["q1"].scale == (1, 5) and q["q1"].section_id == "uvod"
    # Duplicate categories collapse, and "don't know" is an option only where allowed.
    assert q["q2"].options == ("Kávu", "Čaj", "Nic", DONT_KNOW)
    assert q["uvod_3"].options == ("Pečivo", "Ovoce")
    (battery,) = spec.batteries
    assert battery.family == "nápoje" and battery.scale == (1, 10)
    assert [o.label for o in battery.objects] == ["Káva", "Čaj", "Kakao", "Džus", "Voda"]
    assert battery.question_template == "Jak hodnotíte {object}?"
    assert battery.question_id(battery.objects[0]) == "napoje_obj_kava"
    assert spec.n == 120 and spec.audience["has_filters"] is False
    assert spec.fingerprint() == compile_design(copy.deepcopy(DESIGN))[0].fingerprint()  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("section", "code"),
    [
        (
            {"type": "questions", "questions": [{"text": "x", "typ": "skala?"}]},
            "unknown_question_type",
        ),
        ({"type": "questions", "questions": [{"typ": "skala"}]}, "question_without_text"),
        (
            {"type": "questions", "questions": [{"text": "x", "typ": "vyber", "kategorie": ["a"]}]},
            "too_few_categories",
        ),
        (
            {"type": "questions", "questions": [{"text": "x", "typ": "skala", "skala": [5, 1]}]},
            "invalid_scale",
        ),
        ({"type": "object_battery", "objects": ["a", "b", "c"]}, "battery_without_family"),
        ({"type": "object_battery", "object_family": "f", "objects": ["a", "b"]}, "battery_size"),
    ],
)
def test_what_cannot_be_compiled_is_named_and_nothing_is_guessed(section: Any, code: str) -> None:
    spec, problems = compile_design({"n": 100, "sections": [section]})
    assert spec is None
    assert [p.code for p in problems] == [code]


def test_an_empty_questionnaire_does_not_compile() -> None:
    spec, problems = compile_design({"n": 100, "sections": []})
    assert spec is None and problems[0].code == "empty_questionnaire"


def test_readiness_is_named_checks_and_a_fail_blocks() -> None:
    spec, _ = compile_design(DESIGN)
    assert spec is not None
    ready = assess_readiness(spec, pair_n_min=AUDIT_PROVISIONAL_N_MIN)
    assert ready.ready and ready.rules == "aia-structural-readiness-1"
    assert _check(ready, "sample_size").status is CheckStatus.PASS
    assert _check(ready, "sociomap_input").status is CheckStatus.PASS

    for n, status in (
        (None, CheckStatus.FAIL),
        (19, CheckStatus.FAIL),
        (10001, CheckStatus.FAIL),
        (20, CheckStatus.PASS),
    ):
        _, r = prepare({**DESIGN, "n": n}, pair_n_min=AUDIT_PROVISIONAL_N_MIN)
        assert _check(r, "sample_size").status is status and r.ready is (status is CheckStatus.PASS)


@pytest.mark.parametrize(
    ("n", "problem"),
    [
        (None, SampleSizeProblem.MISSING),
        (True, SampleSizeProblem.MISSING),  # a boolean is not a count
        (250.5, SampleSizeProblem.MISSING),
        ("300", SampleSizeProblem.MISSING),
        (19, SampleSizeProblem.OUT_OF_RANGE),
        (10_001, SampleSizeProblem.OUT_OF_RANGE),
        (20, None),
        (10_000, None),
    ],
)
def test_the_one_rule_for_a_valid_n_refuses_and_never_clamps(n: object, problem: object) -> None:
    # RQC9: readiness, the Lead and the web (through the API's limits) all ask this one rule.
    assert sample_size_problem(n, AIA_READINESS_V1.sample_size) is problem


def test_a_valid_n_is_judged_by_the_limits_given_not_the_preset() -> None:
    narrow = SampleSizeLimits(min=100, max=500)
    assert sample_size_problem(50, narrow) is SampleSizeProblem.OUT_OF_RANGE
    assert sample_size_problem(500, narrow) is None
    assert sample_size_problem(5000, AIA_READINESS_V1.sample_size) is None


def test_what_the_unit_does_and_aia_does_not_yet_is_refused_not_skipped() -> None:
    """Skipping a filter would put answers in the data nobody would have been asked for."""
    filtered = copy.deepcopy(DESIGN)
    filtered["sections"][0]["questions"][2]["filtr"] = "q2 == 'Kávu'"
    _, r = prepare(filtered, pair_n_min=AUDIT_PROVISIONAL_N_MIN)
    assert not r.ready and _check(r, "conditional_questions").status is CheckStatus.FAIL
    # The way out is in AIA (PC15): the classic interface it once named is gone (ADR 0018).
    said = _check(r, "conditional_questions").message
    assert "klasick" not in said and "Dotazníku" in said
    familiar = copy.deepcopy(DESIGN)
    familiar["sections"][1]["familiarity_required"] = True
    _, r = prepare(familiar, pair_n_min=AUDIT_PROVISIONAL_N_MIN)
    assert not r.ready and _check(r, "battery_familiarity").status is CheckStatus.FAIL
    audience = {**DESIGN, "audience": {"source_mode": "customer", "filters": {"age": [18, 35]}}}
    _, r = prepare(audience, pair_n_min=AUDIT_PROVISIONAL_N_MIN)
    assert r.ready and _check(r, "audience").status is CheckStatus.WARN


def test_the_audience_check_says_whether_the_run_will_apply_the_filters() -> None:
    """Plan panel-grounded-respondents 6d: a run pinned to its population draws under the
    design's filters, so readiness says they apply; any other run, that they do not."""
    n = AUDIT_PROVISIONAL_N_MIN
    filtered = {**DESIGN, "audience": {"source_mode": "population", "filters": {"vek": [30, 59]}}}
    _, roster = prepare(filtered, pair_n_min=n)
    assert _check(roster, "audience").status is CheckStatus.WARN
    assert "nepoužije filtry" in _check(roster, "audience").message
    _, panel = prepare(filtered, pair_n_min=n, filters_applied=True)
    assert _check(panel, "audience").status is CheckStatus.PASS
    assert _check(panel, "audience").message == (
        "Filtry se uplatní při výběru respondentů z populace."
    )
    # The whole population needs no filter either way.
    for applied in (False, True):
        _, whole = prepare(DESIGN, pair_n_min=n, filters_applied=applied)
        assert _check(whole, "audience").message == "Celá populace."
    # An own audience or special dataset AIA does not have stays a warning, saying what the
    # run will do instead.
    own = {**DESIGN, "audience": {"source_mode": "customer", "filters": {"vek": [18, 35]}}}
    _, own_panel = prepare(own, pair_n_min=n, filters_applied=True)
    assert _check(own_panel, "audience").status is CheckStatus.WARN
    assert "pod uloženými filtry" in _check(own_panel, "audience").message
    own_nothing = {**DESIGN, "audience": {"source_mode": "customer", "filters": {}}}
    _, bare = prepare(own_nothing, pair_n_min=n, filters_applied=True)
    assert _check(bare, "audience").message.endswith("z populace.")


def test_a_design_that_does_not_compile_is_not_ready() -> None:
    spec, r = prepare(
        {"n": 100, "sections": [{"type": "questions", "questions": [{"typ": "vyber"}]}]},
        pair_n_min=AUDIT_PROVISIONAL_N_MIN,
    )
    assert spec is None and not r.ready
    assert [c.status for c in r.checks] == [CheckStatus.FAIL]


def test_the_fictional_dataset_is_deterministic_labelled_and_answers_only_the_spec() -> None:
    spec, _ = compile_design(DESIGN)
    assert spec is not None
    first = synthetic_dataset(spec, seed=7)
    assert first == synthetic_dataset(spec, seed=7)
    assert first != synthetic_dataset(spec, seed=8)
    assert first.origin is DataOrigin.SYNTHETIC_FIXTURE and first.is_synthetic
    assert len(first.respondents) == 120
    assert len({r.donor_id for r in first.respondents}) <= 40
    validate_dataset(spec, first)
    answered = set(first.respondents[0].answers)
    assert answered == {q.id for q in spec.questions} | set(spec.battery_questions())


def test_a_dataset_is_checked_against_its_specification() -> None:
    spec, _ = compile_design(DESIGN)
    assert spec is not None
    good = synthetic_dataset(spec, seed=1)
    other, _ = compile_design({**DESIGN, "n": 121})
    assert other is not None
    with pytest.raises(InvalidDataset, match="different specification"):
        validate_dataset(other, good)

    def with_answer(qid: str, value: Any) -> Any:
        first = good.respondents[0].model_copy(
            update={"answers": {**good.respondents[0].answers, qid: value}}
        )
        return good.model_copy(update={"respondents": (first, *good.respondents[1:])})

    for qid, value, match in (
        ("q1", 9, "off the scale"),
        ("q2", "Pivo", "not an option"),
        ("napoje_obj_kava", 11, "off the 1-10 scale"),
        ("unasked", "x", "unknown items"),
        ("uvod_3", [DONT_KNOW], "are not options"),
    ):
        with pytest.raises(InvalidDataset, match=match):
            validate_dataset(spec, with_answer(qid, value))


def test_a_fictional_dataset_needs_n() -> None:
    spec, _ = compile_design({**DESIGN, "n": None})
    assert spec is not None
    with pytest.raises(ValueError, match="needs the specification's n"):
        synthetic_dataset(spec, seed=1)


# --------------------------------------------------------------------------- #
# Scale labels and whole-number ends (input-interactions 3b; IA-2, IA-7)
# --------------------------------------------------------------------------- #

#: ``DESIGN``'s specification fingerprint on develop before scale labels were compiled
#: (@ 45e87184, compiler ``aia-research-compile-1``): a specification stored then must read
#: back to exactly it, whatever this compiler does.
_FINGERPRINT_BEFORE_LABELS = "c3bdb0965fa401bbdcb96a3ceae59496c3ca275e74c2ddfda40b5fb4310f1447"


def _scale_question(**fields: Any) -> dict[str, Any]:
    return {
        "n": 100,
        "sections": [
            {
                "type": "questions",
                "questions": [{"id": "s", "text": "Jak?", "typ": "skala", **fields}],
            }
        ],
    }


def _as_stored_on_develop(spec: Any) -> dict[str, Any]:
    """A specification as develop's compile step stored it: compile-1, no ``scale_labels``
    on a question."""
    body = spec.model_dump(mode="json")
    body["compiler_version"] = "aia-research-compile-1"
    for question in body["questions"]:
        del question["scale_labels"]
    return body


def test_a_specification_stored_before_the_labels_reads_back_as_stored() -> None:
    spec, _ = compile_design(DESIGN)
    assert spec is not None and spec.compiler_version == COMPILER_VERSION
    assert COMPILER_VERSION == "aia-research-compile-2"
    stored = ResearchSpecification.model_validate(_as_stored_on_develop(spec))
    assert all(q.scale_labels == () for q in stored.questions)
    assert stored.fingerprint() == _FINGERPRINT_BEFORE_LABELS
    # The new compiler is another identity: its artifact is never one compile-1 stored.
    assert spec.fingerprint() != _FINGERPRINT_BEFORE_LABELS


def test_a_design_without_labels_compiles_without_them() -> None:
    spec, _ = compile_design(DESIGN)
    assert spec is not None and all(q.scale_labels == () for q in spec.questions)
    blank = copy.deepcopy(DESIGN)
    blank["sections"][0]["questions"][0]["popisky_skaly"] = ["", " "]
    blank_spec, _ = compile_design(blank)
    assert blank_spec is not None and blank_spec.fingerprint() == spec.fingerprint()


def test_a_scale_questions_labels_are_compiled_as_its_ends_or_every_point() -> None:
    ends, problems = compile_design(
        _scale_question(skala=[1, 10], popisky_skaly=["vůbec", "zcela"])
    )
    assert problems == () and ends is not None
    (q,) = ends.questions
    assert q.scale_labels == ("vůbec", "zcela") and q.end_labels == ("vůbec", "zcela")
    every = ["rozhodně ne", "spíše ne", "nevím", "spíše ano", "rozhodně ano"]
    points, problems = compile_design(_scale_question(skala=[1, 5], popisky_skaly=every))
    assert problems == () and points is not None
    assert points.questions[0].scale_labels == tuple(every)
    assert points.questions[0].end_labels == ("rozhodně ne", "rozhodně ano")
    # Declared labels are part of what respondents may be told: they move the fingerprint.
    bare, _ = compile_design(_scale_question(skala=[1, 10]))
    assert bare is not None and bare.questions[0].end_labels is None
    assert bare.fingerprint() != ends.fingerprint()


@pytest.mark.parametrize(
    ("labels", "words"),
    [
        (["a", "b", "c"], "10 bodů a popisků je 3"),
        (["a"], "10 bodů a popisků je 1"),
        ([str(i) for i in range(9)], "10 bodů a popisků je 9"),
        (["a", "", "c", "d", "e", "f", "g", "h", "i", "j"], "je prázdný"),
        (["vůbec", ""], "je prázdný"),
        (["Ano", "ano"], "stejný popisek"),
        (["x" * 61, "y"], "víc než 60 znaků"),
        ("vůbec-zcela", "nejsou seznam textů"),
        ([1, 10], "nejsou seznam textů"),
    ],
)
def test_labels_that_break_the_rule_are_left_out_and_said_never_refused(
    labels: Any, words: str
) -> None:
    """A design that compiled on develop still compiles: such labels are none declared --
    nothing sent, nothing printed -- and readiness says why, a WARN, never a FAIL."""
    design = _scale_question(skala=[1, 10], popisky_skaly=labels)
    spec, problems = compile_design(design)
    assert problems == () and spec is not None
    assert spec.questions[0].scale_labels == ()
    _, readiness = prepare(design, pair_n_min=AUDIT_PROVISIONAL_N_MIN)
    (ignored,) = [c for c in readiness.checks if c.id.startswith("compile:scale_labels_ignored")]
    assert ignored.status is CheckStatus.WARN and words in ignored.message
    assert "Respondenti uvidí jen čísla škály" in ignored.message
    assert not any(c.status is CheckStatus.FAIL for c in readiness.checks if "scale" in c.id)


@pytest.mark.parametrize("skala", [[2.5, 10], [1, 9.5], [True, 10], ["1.5", 10]])
def test_a_scale_end_that_is_not_whole_is_refused_in_words(skala: list[Any]) -> None:
    """IA-2: never truncated by int(). Kontrola shows it as a check in words."""
    design = _scale_question(skala=skala)
    spec, problems = compile_design(design)
    assert spec is None and [p.code for p in problems] == ["invalid_scale"]
    _, readiness = prepare(design, pair_n_min=AUDIT_PROVISIONAL_N_MIN)
    (check,) = readiness.checks
    assert check.id == "compile:invalid_scale:s" and check.status is CheckStatus.FAIL
    assert "škála musí mít dvě celá čísla" in check.message and not readiness.ready


def test_a_whole_number_end_written_otherwise_is_the_number_it_writes() -> None:
    for skala in ([1.0, 10.0], ["1", " 10 "]):
        spec, problems = compile_design(_scale_question(skala=skala))
        assert problems == () and spec is not None and spec.questions[0].scale == (1, 10)


def test_a_label_of_sixty_characters_is_kept() -> None:
    spec, problems = compile_design(_scale_question(skala=[1, 10], popisky_skaly=["x" * 60, "y"]))
    assert problems == () and spec is not None
    assert spec.questions[0].scale_labels == ("x" * 60, "y")


def test_a_sets_labels_follow_the_same_rule() -> None:
    battery = DESIGN["sections"][1]
    every = [f"bod {i}" for i in range(1, 11)]
    spec, problems = compile_design({**DESIGN, "sections": [{**battery, "scale_labels": every}]})
    assert problems == () and spec is not None
    assert spec.batteries[0].scale_labels == tuple(every)
    assert spec.batteries[0].end_labels == ("bod 1", "bod 10")
    default, _ = compile_design({**DESIGN, "sections": [battery]})
    assert default is not None and default.batteries[0].scale_labels == ("vůbec", "velmi")
    for labels in (["a", "b", "c"], ["a", "a"], ["vůbec", ""]):
        design = {**DESIGN, "sections": [{**battery, "scale_labels": labels}]}
        broken, problems = compile_design(design)
        assert problems == () and broken is not None
        assert broken.batteries[0].scale_labels == ("vůbec", "velmi")
        _, readiness = prepare(design, pair_n_min=AUDIT_PROVISIONAL_N_MIN)
        (ignored,) = [c for c in readiness.checks if c.id.startswith("compile:scale_labels")]
        assert ignored.status is CheckStatus.WARN and "„vůbec“ a „velmi“" in ignored.message
    _, problems = compile_design({**DESIGN, "sections": [{**battery, "scale": [1, 7.5]}]})
    assert [p.code for p in problems] == ["invalid_scale"]
