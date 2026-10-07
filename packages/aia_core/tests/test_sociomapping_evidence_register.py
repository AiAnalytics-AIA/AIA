"""The Sociomapping evidence register says where every rule comes from, and it stays true.

``docs/migration/sociomapping-evidence-register.json`` records, per rule: product, label,
sources with pages, formula, input type, implementation, validation and uncertainty. This
test keeps it honest: implementations exist, validating tests exist, a rule called
reproduced has a source example behind it, an own test never stands in for source evidence,
and every rule id an output records is in the register.

The canonical block: the NPC Sociomapa audit is the canonical methodology document (the
owner's rule of 2026-10-07). A rule labelled CANONICAL cites it; what it supersedes says so;
every check the audit printed for it is in the vendored fixture, and nothing in the fixture
is orphaned.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
from pathlib import Path

import pytest

from aia_core.domain.sociomap import coherence, declared, fuzzy, heights, hmodel, hmodel_candidate
from aia_core.domain.sociomap.coherence import coherences, merge_classes
from aia_core.domain.sociomap.declared import declared_from_correlations, declared_from_fuzzy
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
from aia_core.domain.sociomap.heights import column_averages, object_average_answers, row_averages
from aia_core.domain.sociomap.hmodel import hmodel_accuracy
from aia_core.domain.sociomap.hmodel_candidate import CandidateParameters, fit_hmodel_candidate
from aia_core.domain.sociomap.models import RatingsMatrix

REPO = Path(__file__).resolve().parents[3]
REGISTER = json.loads(
    (REPO / "docs/migration/sociomapping-evidence-register.json").read_text("utf-8")
)
CANONICAL = REGISTER["canonical"]
AUDIT_CHECKS = json.loads((REPO / CANONICAL["checks_fixture"]).read_text("utf-8"))
RULES = {rule["id"]: rule for rule in REGISTER["rules"]}
LABELS = set(REGISTER["labels"])
KINDS = set(REGISTER["validation_kinds"])
PRODUCTS = {"RTS", "SOMECS", "QED", "LEGACY_AIA", "AIA", "NPC_AUDIT"}
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
        if rule["label"] in {"DOCUMENTED", "REPRODUCED_FROM_EXAMPLE", "INFERRED", "CANONICAL"}:
            paged = [s for s in rule["sources"] if s["page"] is not None]
            assert paged, f"{rule['id']} cites no page"
        if rule["label"] == "CANONICAL":
            documents = {s["document"] for s in rule["sources"]}
            assert documents <= set(CANONICAL["documents"]), (
                f"{rule['id']} cites a non-canonical source"
            )
            assert rule["product"] == "NPC_AUDIT", rule["id"]
        if rule["label"] == "REPRODUCED_FROM_EXAMPLE":
            assert "SOURCE_EXAMPLE" in kinds, f"{rule['id']} is called reproduced without one"
        if rule["label"] == "OPEN":
            assert rule["implementation"] is None, f"{rule['id']} is open but implemented"
            assert rule["resolve_by"] or rule["question"], rule["id"]
        if rule["label"] in {"INFERRED", "PROPOSED", "OPEN"}:
            assert rule["uncertainty"], f"{rule['id']} must say what is uncertain"
        if rule["implementation"] is not None:
            assert rule["validation"], f"{rule['id']} is implemented but never checked"


def test_the_canonical_block_names_what_it_overrides() -> None:
    assert set(CANONICAL["documents"]) <= set(REGISTER["documents"])
    canonical_ids = {r["id"] for r in REGISTER["rules"] if r["label"] == "CANONICAL"}
    assert canonical_ids, "the audit's rules are registered"
    for new, olds in CANONICAL["supersedes"].items():
        assert new in canonical_ids, f"{new} supersedes but is not canonical"
        for old in olds:
            assert old in RULES and RULES[old]["label"] != "CANONICAL", old
            assert new in RULES[old]["uncertainty"], f"{old} does not say it is superseded by {new}"
    for rule_id in canonical_ids:
        assert CANONICAL["checks"].get(rule_id), f"{rule_id} names no printed check"


def test_a_pending_canonical_rule_names_its_open_question() -> None:
    """A rule can be canonical in its formula and still pending in a parameter or its meaning.

    The status says which, so a provisional AIA reading never passes for a decision.
    """
    canonical_ids = {r["id"] for r in REGISTER["rules"] if r["label"] == "CANONICAL"}
    assert set(CANONICAL["status"]) == canonical_ids, "every canonical rule has a status"
    assert set(CANONICAL["status"].values()) <= set(CANONICAL["status_values"])
    for rule_id, status in CANONICAL["status"].items():
        if status != "CANONICAL":
            assert RULES[rule_id]["question"], f"{rule_id} is {status} but names no question"


def test_every_printed_check_is_vendored_and_claimed() -> None:
    checks = AUDIT_CHECKS["checks"]
    claimed = {c for ids in CANONICAL["checks"].values() for c in ids}
    assert claimed == set(checks), "the register and the fixture name the same checks"
    pages = {d: REGISTER["documents"][d]["pages"] for d in CANONICAL["documents"]}
    for check_id, check in checks.items():
        assert 1 <= check["page"] <= min(pages.values()), check_id
        assert check["printed"], f"{check_id} records nothing"
        for rule_id in check["formula_ids"]:
            assert check_id in CANONICAL["checks"][rule_id], (
                f"{check_id} is not listed under {rule_id}"
            )
    for rule_id, ids in CANONICAL["checks"].items():
        for check_id in ids:
            assert rule_id in checks[check_id]["formula_ids"], f"{rule_id} claims {check_id}"


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


def _outputs() -> dict[str, tuple[str, ...]]:
    """Every public function that produces a result, with the rule ids its result records."""
    answers = RatingsMatrix(
        respondent_ids=("p0", "p1", "p2"),
        object_ids=("X", "Y", "Z"),
        values=((1, 3, 2), (4, 6, 5), (7, 8, 9)),
    )
    scaled = rts_scale_answers(answers, (1, 10))
    people = rts_people_matrix("ABC", [[0, 3, 1], [2, 0, 3], [1, 2, 0]], (1, 3))
    entered = FuzzyMatrix.from_square("AB", [[0, 0.3], [0.6, 0]], FuzzySource.ENTERED, ("QED-F1",))
    correlations = rts_object_correlations(scaled)
    return {
        "rts_people_matrix": people.rules,
        "rts_scale_answers": scaled.rules,
        "rts_object_correlations": correlations.rules,
        "rts_fuzzy_from_correlations": rts_fuzzy_from_correlations(correlations).rules,
        "somecs_transform_storm": somecs_transform_storm(
            answers, StormTransform.SOMECS_WITHIN_ROW, StormMissingPolicy.KEEP_EMPTY
        ).rules,
        "somecs_transform_storm (database, zero fill)": somecs_transform_storm(
            answers, StormTransform.SOMECS_WITHIN_DATABASE, StormMissingPolicy.SOMECS_ZERO
        ).rules,
        "weighted_mean_fuzzy": weighted_mean_fuzzy([entered, entered], [1, 1]).mean.rules,
        "legacy_fuzzy_from_relation_1_10": legacy_fuzzy_from_relation_1_10(
            "AB", [[0, 2], [3, 0]]
        ).rules,
        "coherences": coherences(people).rules,
        "merge_classes": merge_classes(people, (("A", "B"), ("C",))).rules,
        "column_averages": column_averages(people).rules,
        "row_averages": row_averages(people).rules,
        "object_average_answers": object_average_answers(scaled).rules,
        "hmodel_accuracy": hmodel_accuracy(people, [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]).rules,
        "declared_from_correlations": declared_from_correlations(correlations).rules,
        "declared_from_fuzzy": declared_from_fuzzy(people).rules,
        "fit_hmodel_candidate": fit_hmodel_candidate(
            declared_from_fuzzy(people), CandidateParameters(random_starts=0)
        ).rules,
    }


# Public functions whose result is not a methodological output, each with the reason.
NOT_OUTPUTS = {
    "alpha_cut": "a view of a CoherenceTree, which carries the provenance",
    "spearman": "arithmetic used by hmodel_accuracy, which records the rules",
    "average_ranks": "arithmetic used by spearman",
}


def test_every_public_result_is_covered_by_the_provenance_check() -> None:
    public = {
        name
        for module in (fuzzy, coherence, heights, hmodel, declared, hmodel_candidate)
        for name in module.__all__
        if inspect.isfunction(getattr(module, name))
    }
    covered = {name.split(" ")[0] for name in _outputs()}
    assert public - set(NOT_OUTPUTS) == covered
    assert set(NOT_OUTPUTS) <= public, "an exemption names a function that no longer exists"


@pytest.mark.parametrize(("producer", "rules"), list(_outputs().items()))
def test_every_rule_id_on_an_output_is_in_the_register(
    producer: str, rules: tuple[str, ...]
) -> None:
    assert rules, f"{producer}: an output names the rules that made it"
    unknown = [r for r in rules if r not in RULES]
    assert not unknown, f"not in the register: {unknown}"
