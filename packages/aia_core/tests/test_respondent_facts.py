"""The ported factual layer against the unit's own ``factual_layer.py``.

The unit's module is stdlib-only, so it is imported here straight from the frozen
tree (read, never edited) and both implementations are asked the same questions.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from aia_core.domain.research_design import DONT_KNOW, SpecQuestion
from aia_core.domain.respondent_facts import (
    FactStatus,
    UnansweredFact,
    choice_index,
    classify_question,
    deterministic_answer,
)

UNIT = Path(__file__).resolve().parents[3] / "legacy" / "npc-panel-18.6.6" / "app"
#: factual_layer.py as ported; a regenerated unit that changes it fails here first.
UNIT_SHA = "a32d81dc0ec0362a94bbe67b92291c5a12538d73ec27c36ef8ee8a8d7abad28b"


@pytest.fixture(scope="module")
def unit() -> ModuleType:
    spec = importlib.util.spec_from_file_location("unit_factual_layer", UNIT / "factual_layer.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # its dataclasses resolve their module by name
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[spec.name]
        raise
    return module


def test_the_unit_source_is_the_one_ported() -> None:
    digest = hashlib.sha256((UNIT / "factual_layer.py").read_bytes()).hexdigest()
    assert digest == UNIT_SHA


TEXTS = [
    "Jaké je vaše pohlaví?",
    "Kolik je vám let?",
    "Jaké máte vzdělání?",
    "Ve kterém kraji bydlíte?",
    "Jste zaměstnaný?",
    "Máte děti?",
    "Koho byste volil, kdyby se volby konaly zítra?",
    "Máte cukrovku?",
    "Vlastníte hypotéku?",
    "Používáte značku Nokia?",
    "Jak často pijete kávu?",
    "Jak hodnotíte čaj?",
    "Co si ráno koupíte?",
]
FIELDS: list[set[str]] = [set(), {"pohlavi", "vek", "vzdelani", "kraj"}, {"vek"}]


def _q(text: str, typ: str = "vyber", options: tuple[str, ...] = ("Ano", "Ne")) -> SpecQuestion:
    scale = (18, 99) if typ == "skala" else None
    return SpecQuestion(id="q", section_id="s", text=text, typ=typ, options=options, scale=scale)


@pytest.mark.parametrize("text", TEXTS)
@pytest.mark.parametrize("fields", FIELDS, ids=["no-fields", "fictional-persona", "age-only"])
def test_classification_matches_the_unit(unit: ModuleType, text: str, fields: set[str]) -> None:
    theirs = unit.classify_question(SimpleNamespace(text=text, metadata={}), fields)
    mine = classify_question(_q(text), fields)
    assert (mine.status.value, mine.field) == (theirs.status, theirs.field)


CHOICES: list[tuple[tuple[str, ...], Any]] = [
    (("muž", "žena"), "žena"),
    (("Muž", "Žena"), "muž"),
    (("18\u201329", "30-44", "45-59", "60+"), 37),
    (("18-29", "30-44", "45-59", "75 a více"), 80),
    (("do 30", "30-59", "nad 59"), 22),
    (("Ano, mám", "Ne, nemám"), True),
    (("Ano", "Ne"), "0"),
    (("ženatý/vdaná", "svobodný/svobodná"), "zenaty_vdana"),
    (("základní", "střední s maturitou", "VOŠ/VŠ"), "VOŠ/VŠ"),
    (("Praha", "Středočeský kraj"), "Středočeský"),
    (("A", "B"), "C"),
    (("A", "B"), None),
]


@pytest.mark.parametrize(("categories", "value"), CHOICES)
def test_choice_mapping_matches_the_unit(
    unit: ModuleType, categories: tuple[str, ...], value: Any
) -> None:
    theirs = unit._choice_index(list(categories), value)
    mine = choice_index(categories, value)
    assert mine == (None if theirs is None else theirs - 1)


def test_a_direct_fact_is_answered_from_the_persona() -> None:
    q = _q("Jaké je vaše pohlaví?", options=("muž", "žena", DONT_KNOW))
    spec = classify_question(q, {"pohlavi"})
    assert spec.status is FactStatus.DIRECT
    assert deterministic_answer(q, {"pohlavi": "žena"}, spec) == "žena"
    age = _q("Kolik je vám let?", typ="skala", options=())
    assert deterministic_answer(age, {"vek": 41}, classify_question(age, {"vek"})) == 41


def test_a_fact_that_does_not_map_is_refused_not_guessed() -> None:
    # Options sharing no substring with the value: the unit's soft match maps "žena"
    # onto "A" ("a" is in "žena"), and so does the port.
    q = _q("Jaké je vaše pohlaví?", options=("X1", "Y2"))
    spec = classify_question(q, {"pohlavi"})
    with pytest.raises(UnansweredFact):
        deterministic_answer(q, {"pohlavi": "žena"}, spec)
    old = _q("Kolik je vám let?", typ="skala", options=())
    with pytest.raises(UnansweredFact):
        deterministic_answer(old, {"vek": 120}, classify_question(old, {"vek"}))


def test_an_individual_fact_the_persona_lacks_is_unsupported() -> None:
    assert classify_question(_q("Máte cukrovku?"), {"vek"}).status is FactStatus.UNSUPPORTED
    party = classify_question(_q("Koho byste volil?"), {"vek", "pohlavi"})
    assert (party.status, party.field) == (FactStatus.UNSUPPORTED, "F_strana")
