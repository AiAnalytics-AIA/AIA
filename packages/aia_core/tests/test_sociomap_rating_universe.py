"""The declared rating universe and object roles (plan sociomap-formula-corrections § 8.2, S3/I2).

A Sociomap's F2 rescaling reads every rating item of the study; which items those are is a
declaration in the design, never an inference from a column's type. A tracked set's
objects are PRIMARY unless the design declares some context (SECONDARY).
"""

from __future__ import annotations

import copy
import random
from typing import Any

import pytest

from aia_core.domain.research_design import compile_design
from aia_core.domain.research_sociomap import (
    battery_sociomap,
    default_methods,
    rating_universe,
    research_sociomaps,
)
from aia_core.domain.sociomap import (
    AIA_SOCIOMAP_V1,
    AIA_SOCIOMAP_V2,
    SociomapArtifactV3,
    read_artifact,
)
from aia_core.domain.sociomap.metrics import primary_scores

DESIGN: dict[str, Any] = {
    "title": "Ranní nápoj",
    "n": 60,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                {
                    "id": "q2",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic"],
                },
            ],
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
        },
    ],
}
#: What develop's compiler gave DESIGN before the declarations existed (``751d7ae``).
DEVELOP_FINGERPRINT = "b3bb6cb3cec31d1e1f05c9bd3f976d95a29c9543bb9ad64f17e6b7d685d5ea35"


def _compile(design: dict[str, Any]) -> Any:
    spec, problems = compile_design(design)
    assert spec is not None, problems
    return spec


def _with(**changes: Any) -> dict[str, Any]:
    design = copy.deepcopy(DESIGN)
    if "rating" in changes:
        design["sections"][0]["questions"][changes["rating"]]["sociomap_rating"] = True
    if "context" in changes:
        design["sections"][1]["context_objects"] = changes["context"]
    return design


# ------------------------------------------------------------------ the compiler --


def test_a_design_without_the_declarations_keeps_develops_fingerprint() -> None:
    spec = _compile(DESIGN)
    assert spec.fingerprint() == DEVELOP_FINGERPRINT
    assert spec.rating_questions() == ()
    (battery,) = spec.batteries
    assert battery.roles_declared is False and battery.context_objects == ()
    assert set(battery.object_roles().values()) == {"primary"}


def test_a_scale_question_declared_a_rating_item_is_one_and_moves_the_fingerprint() -> None:
    spec = _compile(_with(rating=0))
    (q,) = spec.rating_questions()
    assert q.id == "q1" and q.scale == (1, 5)
    assert spec.fingerprint() != DEVELOP_FINGERPRINT


def test_only_a_scale_question_can_be_a_rating_item() -> None:
    spec, problems = compile_design(_with(rating=1))
    assert spec is None
    assert [p.code for p in problems] == ["rating_item_not_scale"]


def test_a_truthy_value_that_is_not_true_declares_nothing() -> None:
    design = copy.deepcopy(DESIGN)
    design["sections"][0]["questions"][0]["sociomap_rating"] = "yes"
    assert _compile(design).rating_questions() == ()


def test_context_objects_are_secondary_by_label() -> None:
    spec = _compile(_with(context=["Voda", "Džus"]))
    (battery,) = spec.batteries
    assert battery.roles_declared is True
    roles = battery.object_roles()
    assert roles == {
        "kava": "primary",
        "caj": "primary",
        "kakao": "primary",
        "dzus": "secondary",
        "voda": "secondary",
    }
    assert spec.fingerprint() != DEVELOP_FINGERPRINT


def test_declaring_no_context_object_is_still_a_declaration() -> None:
    spec = _compile(_with(context=[]))
    (battery,) = spec.batteries
    assert battery.roles_declared is True and battery.context_objects == ()
    assert spec.fingerprint() != DEVELOP_FINGERPRINT


@pytest.mark.parametrize(
    ("context", "code"),
    [
        (["Mléko"], "unknown_context_object"),
        ("Voda", "unknown_context_object"),
        (["Káva", "Čaj", "Kakao", "Džus", "Voda"], "no_primary_object"),
    ],
)
def test_a_context_declaration_that_cannot_hold_is_refused(context: Any, code: str) -> None:
    spec, problems = compile_design(_with(context=context))
    assert spec is None
    assert [p.code for p in problems] == [code]


# ---------------------------------------------------------- the universe in use --


class _Respondent:
    def __init__(self, rid: str, answers: dict[str, int]) -> None:
        self.respondent_id, self.answers, self.weight = rid, answers, 1.0
        self.donor_id = f"D-{rid}"


class _Dataset:
    def __init__(self, respondents: list[_Respondent]) -> None:
        self.respondents = respondents
        self.origin = None


def _data(spec: Any, seed: int, n: int = 200) -> _Dataset:
    rng = random.Random(seed)
    (battery,) = spec.batteries
    people = []
    for k in range(n):
        g, f = rng.gauss(0, 1.0), rng.gauss(0, 1.0)
        answers = {
            battery.question_id(o): int(
                min(10, max(1, round(5.5 + g + 2 * w * f + rng.gauss(0, 1.5))))
            )
            for o, w in zip(battery.objects, [0.9, 0.7, -0.6, 0.5, 0.0], strict=True)
        }
        answers["q1"] = rng.randint(1, 5)
        people.append(_Respondent(f"P{k}", answers))
    return _Dataset(people)


def _body(spec: Any, data: _Dataset) -> dict[str, Any]:
    (battery,) = spec.batteries
    return battery_sociomap(
        battery,
        data,  # type: ignore[arg-type]
        rated_with=spec.batteries,
        connectedness_interval=False,
        map_spec=AIA_SOCIOMAP_V1,
        object_maps=(AIA_SOCIOMAP_V2,),
        rating_questions=spec.rating_questions(),
    )


def test_a_declared_rating_question_enters_every_persons_scale() -> None:
    plain, rated = _compile(DESIGN), _compile(_with(rating=0))
    data = _data(plain, 1)
    without, with_q = _body(plain, data), _body(rated, data)
    assert without["relation_rescaled"]["rating_questions"] == []
    assert with_q["relation_rescaled"]["rating_questions"] == ["q1"]
    # q1 moves people's bounds (F2), so the family's r~ moves; the unit's raw matrix does not.
    assert with_q["relation_rescaled"]["r"] != without["relation_rescaled"]["r"]
    assert with_q["relation"]["r"] == without["relation"]["r"]
    art = read_artifact(with_q["maps"]["aia-sociomap-2"])
    assert isinstance(art, SociomapArtifactV3)
    assert [i.item_id for i in art.items][-1] == "q1"
    assert (art.items[-1].scale_min, art.items[-1].scale_max) == (1.0, 5.0)


def test_an_undeclared_numeric_question_never_enters_the_universe() -> None:
    plain = _compile(DESIGN)
    data = _data(plain, 2)
    before = _body(plain, data)
    for r in data.respondents:
        r.answers["q1"] = 1 if r.answers["q1"] > 2 else 5
    after = _body(plain, data)
    assert after["relation_rescaled"] == before["relation_rescaled"]
    assert after["maps"] == before["maps"]


def test_the_universe_is_the_sets_then_the_declared_questions() -> None:
    spec = _compile(_with(rating=0))
    universe = rating_universe(spec.batteries, spec.rating_questions())
    (battery,) = spec.batteries
    assert universe == [(battery.question_id(o), 1, 10) for o in battery.objects] + [("q1", 1, 5)]
    with pytest.raises(ValueError, match="not a declared scale rating item"):
        rating_universe(spec.batteries, _compile(DESIGN).questions[:1])


def test_a_context_object_has_no_score_and_scores_nobody() -> None:
    declared = _compile(_with(context=["Voda"]))
    data = _data(declared, 3)
    body = _body(declared, data)
    assert body["roles"] == {
        "declared": True,
        "by_object": {
            "kava": "primary",
            "caj": "primary",
            "kakao": "primary",
            "dzus": "primary",
            "voda": "secondary",
        },
    }
    scores = body["object_scores"]
    assert scores["secondary"] == ["voda"] and "voda" not in scores["primary"]
    # The PRIMARY scores are the primaries' own relations: voda's pairs are not read.
    r, status = body["relation_rescaled"]["r"], body["relation_rescaled"]["status"]
    keep = [0, 1, 2, 3]
    sub = primary_scores(
        ["kava", "caj", "kakao", "dzus"],
        [[r[i][j] for j in keep] for i in keep],
        [[status[i][j] for j in keep] for i in keep],
        dict.fromkeys(["kava", "caj", "kakao", "dzus"], "primary"),
    ).to_payload()
    assert scores["objects"] == sub["objects"]
    art = read_artifact(body["maps"]["aia-sociomap-2"])
    assert isinstance(art, SociomapArtifactV3)
    assert art.roles["voda"] == "secondary"
    assert art.scores == scores
    # A context object is still placed on the map: it is mapped and related.
    assert art.layout is not None and len(art.layout.points) == 5


def test_research_sociomaps_reads_the_specifications_declarations() -> None:
    spec = _compile(_with(rating=0, context=["Voda"]))
    body = research_sociomaps(
        spec,
        _data(spec, 4),  # type: ignore[arg-type]
        methods=default_methods(),
        connectedness_interval=False,
    )
    (battery,) = body["batteries"]
    assert battery["relation_rescaled"]["rating_questions"] == ["q1"]
    assert battery["roles"]["by_object"]["voda"] == "secondary"
