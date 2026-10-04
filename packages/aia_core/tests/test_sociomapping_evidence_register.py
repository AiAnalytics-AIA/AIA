"""The Sociomapping evidence register says where every rule comes from, and it stays true.

``docs/migration/sociomapping-evidence-register.json`` records, per rule: product, label,
sources with pages, formula, input type, implementation, validation and uncertainty. This
test keeps it honest: implementations exist, validating tests exist, a rule called
reproduced has a source example behind it, an own test never stands in for source evidence,
and every rule id an output records is in the register.
"""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import pytest

from aia_core.domain.sociomap.coherence import merge_classes
from aia_core.domain.sociomap.fuzzy import (
    FuzzyMatrix,
    FuzzySource,
    StormMissingPolicy,
    StormTransform,
    legacy_fuzzy_from_relation_1_10,
    rts_fuzzy_from_correlations,
    rts_object_correlations,
    rts_people_matrix,
    rts_scale_answers,
    somecs_transform_storm,
    weighted_mean_fuzzy,
)
from aia_core.domain.sociomap.hmodel import hmodel_accuracy
from aia_core.domain.sociomap.models import RatingsMatrix

REPO = Path(__file__).resolve().parents[3]
REGISTER = json.loads(
    (REPO / "docs/migration/sociomapping-evidence-register.json").read_text("utf-8")
)
RULES = {rule["id"]: rule for rule in REGISTER["rules"]}
LABELS = set(REGISTER["labels"])
KINDS = set(REGISTER["validation_kinds"])
PRODUCTS = {"RTS", "SOMECS", "QED", "LEGACY_AIA", "AIA"}
FIELDS = {
    "id", "title", "product", "label", "sources", "formula", "applies_to",
    "implementation", "validation", "uncertainty", "resolve_by", "question",
}  # fmt: skip


def test_every_rule_has_every_field_and_a_known_label() -> None:
    assert len(RULES) == len(REGISTER["rules"]), "rule ids are unique"
    for rule in REGISTER["rules"]:
        assert set(rule) == FIELDS, rule["id"]
        assert rule["label"] in LABELS, rule["id"]
        assert rule["product"] in PRODUCTS, rule["id"]
        for source in rule["sources"]:
            assert source["document"] in REGISTER["documents"], rule["id"]
            assert source["states"].strip(), rule["id"]


def test_labels_are_backed_by_what_they_claim() -> None:
    for rule in REGISTER["rules"]:
        kinds = {v["kind"] for v in rule["validation"]}
        assert kinds <= KINDS, rule["id"]
        if rule["label"] in {"DOCUMENTED", "REPRODUCED_FROM_EXAMPLE", "INFERRED"}:
            paged = [s for s in rule["sources"] if s["page"] is not None]
            assert paged, f"{rule['id']} cites no page"
        if rule["label"] == "REPRODUCED_FROM_EXAMPLE":
            assert "SOURCE_EXAMPLE" in kinds, f"{rule['id']} is called reproduced without one"
        if rule["label"] == "OPEN":
            assert rule["implementation"] is None, f"{rule['id']} is open but implemented"
            assert rule["resolve_by"] or rule["question"], rule["id"]
        if rule["label"] in {"INFERRED", "PROPOSED", "OPEN"}:
            assert rule["uncertainty"], f"{rule['id']} must say what is uncertain"
        if rule["implementation"] is not None:
            assert rule["validation"], f"{rule['id']} is implemented but never checked"


def test_implementations_exist() -> None:
    for rule in REGISTER["rules"]:
        if rule["implementation"] is None:
            continue
        module, _, symbol = rule["implementation"].partition(":")
        assert hasattr(importlib.import_module(module), symbol), rule["implementation"]


def test_validating_tests_exist() -> None:
    for rule in REGISTER["rules"]:
        for validation in rule["validation"]:
            path, _, name = validation["test"].partition("::")
            tree = ast.parse((REPO / path).read_text("utf-8"))
            names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
            assert name in names, f"{rule['id']}: {validation['test']} does not exist"


def _outputs() -> list[tuple[str, ...]]:
    answers = RatingsMatrix(
        respondent_ids=("p0", "p1", "p2"),
        object_ids=("X", "Y", "Z"),
        values=((1, 3, 2), (4, 6, 5), (7, 8, 9)),
    )
    scaled = rts_scale_answers(answers, (1, 10))
    people = rts_people_matrix("ABC", [[0, 3, 1], [2, 0, 3], [1, 2, 0]], (1, 3))
    entered = FuzzyMatrix.from_square("AB", [[0, 0.3], [0.6, 0]], FuzzySource.ENTERED, ("QED-F1",))
    correlations = rts_object_correlations(scaled)
    return [
        people.rules,
        scaled.rules,
        correlations.rules,
        rts_fuzzy_from_correlations(correlations).rules,
        somecs_transform_storm(
            answers, StormTransform.SOMECS_WITHIN_ROW, StormMissingPolicy.KEEP_EMPTY
        ).rules,
        somecs_transform_storm(
            answers, StormTransform.SOMECS_WITHIN_DATABASE, StormMissingPolicy.SOMECS_ZERO
        ).rules,
        weighted_mean_fuzzy([entered, entered], [1, 1]).mean.rules,
        legacy_fuzzy_from_relation_1_10("AB", [[0, 2], [3, 0]]).rules,
        merge_classes(people, (("A", "B"), ("C",))).rules,
        hmodel_accuracy(people, [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]).rules,
    ]


@pytest.mark.parametrize("rules", _outputs())
def test_every_rule_id_on_an_output_is_in_the_register(rules: tuple[str, ...]) -> None:
    assert rules, "an output names the rules that made it"
    unknown = [r for r in rules if r not in RULES]
    assert not unknown, f"not in the register: {unknown}"
