"""The AI respondent's pure part: agent, contract, prompt, facts, answers, dataset.

The model's output is simulated here by building the contract object directly or
by validating JSON through the same deterministic validator the gateway uses.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from aia_core.domain.ai_contracts import (
    canonical_json,
    output_schema,
    schema_supports_strict,
    validate_structured_output,
)
from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.ai_respondent import (
    AGENT_ID,
    MAX_BLOCK_ITEMS,
    PROMPT_SHA256,
    SCALE_LABEL_WORDING,
    RespondentOutputInvalid,
    UnsupportedFact,
    assemble_dataset,
    block_contract,
    build_request,
    classify_material,
    fictional_roster,
    interpret_block,
    plan_items,
    plan_respondent,
    respondent_agent,
    respondent_prompt_sha256,
    scale_label_wording,
)
from aia_core.domain.fieldwork import DataOrigin, FieldworkSource, validate_dataset
from aia_core.domain.licence_determinations import SYNTHETIC_FIXTURE_DATASET
from aia_core.domain.research_design import DONT_KNOW, compile_design
from aia_core.domain.residency import DataClass

DESIGN: dict[str, Any] = {
    "title": "Fiktivní ranní nápoj",
    "n": 20,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {
                    "id": "q_sex",
                    "text": "Jaké je vaše pohlaví?",
                    "typ": "vyber",
                    "kategorie": ["muž", "žena"],
                },
                {
                    "id": "q1",
                    "text": "Jak často pijete kávu?",
                    "typ": "skala",
                    "skala": [1, 5],
                    "povolit_nevim": True,
                },
                {
                    "id": "q2",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic"],
                    "povolit_nevim": True,
                },
                {
                    "id": "q3",
                    "text": "Co ještě pijete?",
                    "typ": "multi",
                    "kategorie": ["Džus", "Vodu", "Mléko"],
                },
                {"id": "q4", "text": "Proč?", "typ": "otevrena"},
            ],
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda", "Limonáda", "Mošt"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
        },
    ],
}


def _spec() -> Any:
    spec, problems = compile_design(DESIGN)
    assert spec is not None, problems
    return spec


def _answer(block: Any, **override: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in block.items:
        if item.kind in ("choice", "scale"):
            out[item.item_id] = {"probabilities": [1.0] + [0.0] * (item.width - 1)}
        elif item.kind == "multi":
            out[item.item_id] = {"selected": [1, 3]}
        else:
            out[item.item_id] = {"text": "Protože mi chutná."}
    out.update(override)
    return out


def _validate(block: Any, payload: dict[str, Any]) -> Any:
    return validate_structured_output(block_contract(block), structured=payload, text="")


def test_the_roster_is_fictional_deterministic_and_carries_its_lineage() -> None:
    a, b = fictional_roster(20, seed=7), fictional_roster(20, seed=7)
    assert a == b and len(a) == 20
    assert fictional_roster(20, seed=8) != a
    assert all(p.fictional and p.lineage == {SYNTHETIC_FIXTURE_DATASET} for p in a)
    assert all(p.persona_id.startswith("FIC-R") and p.donor_id.startswith("FIC-D") for p in a)
    assert "FIKTIVNÍ RESPONDENT" in a[0].profile()


def test_material_is_class_c_only_when_client_and_personas_are_both_fictional() -> None:
    personas = fictional_roster(3, seed=1)
    assert classify_material(personas, client_declared_fictional=True)[0] is (
        DataClass.CLASS_C_INTERNAL
    )
    klass, lineage = classify_material(personas, client_declared_fictional=False)
    assert klass is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
    assert lineage.datasets == {SYNTHETIC_FIXTURE_DATASET}
    panel = personas[0].model_copy(update={"fictional": False, "lineage": frozenset({"piaac"})})
    klass, lineage = classify_material((panel,), client_declared_fictional=True)
    assert klass is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
    assert lineage.datasets == {"piaac"}


def test_facts_are_answered_by_code_and_never_asked() -> None:
    spec = _spec()
    persona = fictional_roster(1, seed=3)[0]
    plan = plan_respondent(spec, persona)
    assert plan.facts == {"q_sex": persona.facts["pohlavi"]}
    asked = [i.item_id for b in plan.blocks for i in b.items]
    assert "q_sex" not in asked
    assert set(asked) | set(plan.facts) == {i.item_id for i in plan_items(spec)}


def test_blocks_hold_at_most_eight_closed_items_and_each_open_question_alone() -> None:
    plan = plan_respondent(_spec(), fictional_roster(1, seed=3)[0])
    for block in plan.blocks:
        kinds = {i.kind for i in block.items}
        assert len(block.items) <= MAX_BLOCK_ITEMS
        if "open" in kinds:
            assert len(block.items) == 1
    assert [len(b.items) for b in plan.blocks] == [3, 1, 7]


def test_an_individual_fact_no_persona_carries_refuses_before_any_request() -> None:
    design = json.loads(json.dumps(DESIGN))
    design["sections"][0]["questions"].append(
        {"id": "q_d", "text": "Máte cukrovku?", "typ": "vyber", "kategorie": ["Ano", "Ne"]}
    )
    spec, _ = compile_design(design)
    assert spec is not None
    with pytest.raises(UnsupportedFact):
        plan_respondent(spec, fictional_roster(1, seed=3)[0])


def test_the_contract_is_strict_one_required_property_per_item() -> None:
    plan = plan_respondent(_spec(), fictional_roster(1, seed=3)[0])
    block = plan.blocks[0]
    schema = output_schema(block_contract(block))
    assert set(schema["properties"]) == {i.item_id for i in block.items}
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False
    assert schema_supports_strict(schema)
    agent = respondent_agent(block, max_output_tokens=900)
    assert (agent.agent_id, agent.capability) == (AGENT_ID, ModelCapability.SIMULATION)
    assert agent.schema_repair_attempts == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda a: a.update({"q9_invented": {"probabilities": [1.0]}}),  # off-question
        lambda a: a.pop("q1"),  # missing
        lambda a: a.update({"q1": {"probabilities": [0.5, 0.5]}}),  # wrong length
        lambda a: a.update({"q2": {"probabilities": [1.5, 0, 0, 0]}}),  # above 1
        lambda a: a.update({"q2": {"probabilities": [-0.1, 0, 0, 1]}}),  # negative
        lambda a: a.update({"q2": {"probabilities": ["1", 0, 0, 0]}}),  # a string
        lambda a: a.update({"q3": {"selected": [4]}}),  # option out of range
        lambda a: a.update({"q2": {"probabilities": [1, 0, 0, 0], "answer": 2}}),  # extra
    ],
)
def test_an_off_contract_answer_is_a_schema_violation(mutate: Any) -> None:
    plan = plan_respondent(_spec(), fictional_roster(1, seed=3)[0])
    block = plan.blocks[0]
    payload = _answer(block)
    mutate(payload)
    verdict = _validate(block, payload)
    assert not verdict.ok and verdict.violations


def test_an_open_answer_is_bounded() -> None:
    plan = plan_respondent(_spec(), fictional_roster(1, seed=3)[0])
    block = plan.blocks[1]
    assert not _validate(block, {"q4": {"text": ""}}).ok
    assert not _validate(block, {"q4": {"text": "x" * 601}}).ok


def test_answers_are_drawn_by_code_reproducibly_and_zero_mass_is_refused() -> None:
    persona = fictional_roster(1, seed=3)[0]
    plan = plan_respondent(_spec(), persona)
    block = plan.blocks[0]
    output = _validate(block, _answer(block)).value
    first, meta = interpret_block(block, output, persona, seed=11)
    again, _ = interpret_block(block, output, persona, seed=11)
    assert first == again
    assert first["q3"] == ["Džus", "Mléko"]
    assert first["q2"] in ("Kávu", "Čaj", "Nic", DONT_KNOW)
    assert meta["q1"]["raw_probabilities"] == [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert "dont_know" in meta["q1"]["behavior"]
    # The model's mass on option 1 is not the answer: behaviour and satisficing move it.
    assert meta["q2"]["probabilities"][0] < 1.0
    zero = _validate(block, _answer(block, q2={"probabilities": [0, 0, 0, 0]})).value
    with pytest.raises(RespondentOutputInvalid, match="q2"):
        interpret_block(block, zero, persona, seed=11)


def test_the_request_carries_class_lineage_prompt_and_no_scope() -> None:
    personas = fictional_roster(2, seed=3)
    plan = plan_respondent(_spec(), personas[0])
    klass, lineage = classify_material(personas, client_declared_fictional=True)
    items = {i.item_id: i for i in plan_items(_spec())}
    request = build_request(
        plan,
        plan.blocks[1],
        {"q1": 3},
        items_by_id=items,
        policy_version="p1",
        data_class=klass,
        lineage=lineage,
        max_output_tokens=900,
    )
    assert request.data_classification is DataClass.CLASS_C_INTERNAL
    assert request.data_lineage == lineage
    assert request.temperature == 0.0
    text = request.messages[0].content
    assert "FIKTIVNÍ RESPONDENT" in text and "Jak často pijete kávu? → 3" in text
    for forbidden in ("organization", "client_id", "study_id"):
        assert forbidden not in canonical_json({"s": request.system, "m": text})
    assert len(PROMPT_SHA256) == 64


def test_the_dataset_is_ai_runtime_synthetic_and_valid_for_its_spec() -> None:
    spec = _spec()
    personas = fictional_roster(spec.n, seed=5)
    rows = []
    for persona in personas:
        plan = plan_respondent(spec, persona)
        answers = dict(plan.facts)
        for block in plan.blocks:
            output = _validate(block, _answer(block)).value
            drawn, _ = interpret_block(block, output, persona, seed=5)
            answers.update(drawn)
        rows.append((persona, answers))
    dataset = assemble_dataset(spec, rows, seed=5)
    validate_dataset(spec, dataset)
    assert dataset.source is FieldworkSource.AI_RUNTIME
    assert dataset.origin is DataOrigin.SYNTHETIC_AI_FICTIONAL and dataset.is_synthetic
    assert {r.respondent_id for r in dataset.respondents} == {p.persona_id for p in personas}


def test_each_block_has_its_own_contract() -> None:
    """The schema is part of what is sent, so its fingerprint differs per block."""
    plan = plan_respondent(_spec(), fictional_roster(1, seed=3)[0])
    a, b = (output_schema(block_contract(block)) for block in plan.blocks[:2])
    assert a != b


def test_the_dataset_origin_is_derived_from_the_personas_never_chosen() -> None:
    """ADR 0024 §1: fictional -> SYNTHETIC_AI_FICTIONAL, panel -> MODELLED_AI_PANEL, a mixed
    roster or any other persona -> refused, not labelled."""
    from aia_core.domain.ai_respondent import dataset_origin
    from aia_core.domain.licence_determinations import PANEL_DERIVED_DATASETS

    fictional = list(fictional_roster(4, seed=3))
    panel = [
        p.model_copy(update={"fictional": False, "lineage": PANEL_DERIVED_DATASETS})
        for p in fictional
    ]
    assert dataset_origin(fictional) is DataOrigin.SYNTHETIC_AI_FICTIONAL
    assert dataset_origin(panel) is DataOrigin.MODELLED_AI_PANEL
    with pytest.raises(ValueError, match="mixed roster"):
        dataset_origin([*fictional[:2], *panel[2:]])
    stray = panel[0].model_copy(update={"lineage": frozenset({"piaac"})})
    with pytest.raises(ValueError, match="mixed roster"):
        dataset_origin([stray])
    with pytest.raises(ValueError, match="at least one"):
        dataset_origin([])


def test_a_panel_dataset_says_it_is_modelled_and_not_synthetic() -> None:
    from aia_core.domain.licence_determinations import PANEL_DERIVED_DATASETS

    spec = _spec()
    personas = [
        p.model_copy(update={"fictional": False, "lineage": PANEL_DERIVED_DATASETS})
        for p in fictional_roster(3, seed=5)
    ]
    dataset = assemble_dataset(spec, [(p, {}) for p in personas], seed=1)
    assert dataset.origin is DataOrigin.MODELLED_AI_PANEL
    assert not dataset.is_synthetic
    assert [r.donor_id for r in dataset.respondents] == [p.donor_id for p in personas]


# --------------------------------------------------------------------------- #
# A scale question's labels in the prompt (input-interactions 3b, IA-7)
# --------------------------------------------------------------------------- #

#: SHA-256 over every request ``_requests(_spec())`` builds, on develop before scale labels were
#: compiled (@ 45e87184): with the switch off nothing a respondent is sent may move.
_REQUESTS_BEFORE_LABELS = "64ff8b4bf45f3359be260aad9ddca6d17ac1c7af26efe72f11cac1d56d3cb3df"


def _labelled(labels: list[str]) -> Any:
    design = json.loads(json.dumps(DESIGN))
    design["sections"][0]["questions"][1]["popisky_skaly"] = labels
    spec, problems = compile_design(design)
    assert spec is not None, problems
    return spec


def _requests(spec: Any, *, scale_labels_in_prompt: bool = False) -> list[str]:
    personas = fictional_roster(2, seed=3)
    klass, lineage = classify_material(personas, client_declared_fictional=True)
    items = {i.item_id: i for i in plan_items(spec)}
    out = []
    for persona in personas:
        plan = plan_respondent(spec, persona)
        for block in plan.blocks:
            request = build_request(
                plan,
                block,
                {},
                items_by_id=items,
                policy_version="p1",
                data_class=klass,
                lineage=lineage,
                max_output_tokens=900,
                scale_labels_in_prompt=scale_labels_in_prompt,
            )
            out.append(request.system + "\x00" + request.messages[0].content)
    return out


def _digest(requests: list[str]) -> str:
    return hashlib.sha256("\x01".join(requests).encode()).hexdigest()


def test_off_the_requests_are_byte_identical_whatever_labels_a_question_declares() -> None:
    assert _digest(_requests(_spec())) == _REQUESTS_BEFORE_LABELS
    labelled = _labelled(["nikdy", "denně"])
    assert labelled.questions[1].scale_labels == ("nikdy", "denně")
    assert _digest(_requests(labelled)) == _REQUESTS_BEFORE_LABELS
    every = _labelled(["nikdy", "výjimečně", "občas", "často", "denně"])
    assert _digest(_requests(every)) == _REQUESTS_BEFORE_LABELS
    assert respondent_prompt_sha256(scale_labels_in_prompt=False) == PROMPT_SHA256


def test_on_a_scale_questions_labels_reach_the_respondent() -> None:
    ends = "\n".join(_requests(_labelled(["nikdy", "denně"]), scale_labels_in_prompt=True))
    assert "Škála 1 až 5 (1 = nikdy, 5 = denně)." in ends
    every = "\n".join(
        _requests(
            _labelled(["nikdy", "výjimečně", "občas", "často", "denně"]),
            scale_labels_in_prompt=True,
        )
    )
    assert "Škála 1 až 5 (1 = nikdy, 2 = výjimečně, 3 = občas, 4 = často, 5 = denně)." in every
    # A tracked set's two ends are written as they always were, switch or not.
    assert "Škála 1 až 10 (1 = vůbec, 10 = velmi)." in every
    # Without labels, a question's scale is the bare numbers, on or off.
    bare = _requests(_spec(), scale_labels_in_prompt=True)
    assert _digest(bare) == _REQUESTS_BEFORE_LABELS
    on = respondent_prompt_sha256(scale_labels_in_prompt=True)
    assert len(on) == 64 and on != PROMPT_SHA256


def test_the_provisional_wording_lives_in_one_function() -> None:
    assert scale_label_wording((1, 10), ("vůbec", "zcela")) == " (1 = vůbec, 10 = zcela)"
    assert scale_label_wording((0, 2), ("ne", "možná", "ano")) == " (0 = ne, 1 = možná, 2 = ano)"
    assert scale_label_wording((1, 10), ()) == ""
    assert SCALE_LABEL_WORDING.startswith("aia-scale-labels-provisional")
