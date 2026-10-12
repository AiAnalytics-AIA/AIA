"""A panel respondent's profile against 18.6.6's own ``generate_persona_text`` (chunk 3b).

``tests/fixtures/persona_profile/expected.json`` is what the unit's unmodified function returned
in the mode 18.6.6 ran (``calibrated`` -> ``core``, adaptive) on fictional rows read as the unit
reads its panel, with the behavioural block empty (``tools/persona_capture.py``). Every case is
EXACT, character for character.
"""

from __future__ import annotations

# ruff: noqa: RUF001 - the en dashes are 18.6.6's own Czech text, kept verbatim for EXACT parity
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.persona_profile import (
    MAX_WORDS,
    age_band,
    first_person,
    household_facts,
    income_band,
    persona_text,
    profile_lines,
)
from aia_core.domain.population.audience import Typed, _typed, column_type

FIXTURES = Path(__file__).parent / "fixtures" / "persona_profile"
UNIT = Path(__file__).resolve().parents[3] / "legacy" / "npc-panel-18.6.6" / "app"
EXPECTED: dict[str, Any] = json.loads((FIXTURES / "expected.json").read_text("utf-8"))
_INPUTS: dict[str, Any] = json.loads((FIXTURES / "cases.json").read_text("utf-8"))
CASES: dict[str, dict[str, Any]] = {c["id"]: c for c in _INPUTS["profiles"]}
PROSE: dict[str, list[str]] = {c["id"]: c["lines"] for c in _INPUTS["prose"]}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows() -> list[dict[str, Typed]]:
    """The fixture rows typed as ``read_csv`` types them: each column's type from all its cells."""
    reader = csv.reader(io.StringIO((FIXTURES / "rows.csv").read_text("utf-8")))
    header, *raw = list(reader)
    columns = {h: [None if r[i] == "" else r[i] for r in raw] for i, h in enumerate(header)}
    kinds = {h: column_type(h, cells) for h, cells in columns.items()}
    return [{h: _typed(columns[h][i], kinds[h]) for h in header} for i in range(len(raw))]


ROWS = _rows()


def test_the_fixture_is_pinned_to_its_inputs_and_the_unit_sources() -> None:
    assert _sha(FIXTURES / "rows.csv") == EXPECTED["rows_sha256"]
    assert _sha(FIXTURES / "cases.json") == EXPECTED["cases_sha256"]
    for name, sha in EXPECTED["unit_sources"].items():
        assert _sha(UNIT / name) == sha, f"{name} changed; re-run tools/persona_capture.py"


@pytest.mark.parametrize("case", EXPECTED["cases"], ids=lambda c: c["id"])
def test_the_profile_is_the_units_character_for_character(case: dict[str, Any]) -> None:
    inputs = CASES[case["id"]]
    assert persona_text(ROWS[inputs["row"]], inputs["topics"]) == case["text"]


@pytest.mark.parametrize("case", EXPECTED["prose"], ids=lambda c: c["id"])
def test_the_prose_is_the_units_prefixes_drops_and_word_cap(case: dict[str, Any]) -> None:
    assert first_person(PROSE[case["id"]]) == case["text"]


def test_the_long_prose_cases_reach_the_cap() -> None:
    long = [c["text"] for c in EXPECTED["prose"] if c["id"].startswith(("F03", "F04"))]
    assert all(len(t.split()) <= MAX_WORDS for t in long)
    assert any(len(t.split()) == MAX_WORDS for t in long)


def test_the_fixture_reaches_every_branch_it_claims() -> None:
    texts = " ".join(c["text"] for c in EXPECTED["cases"])
    for phrase in (
        "Pracovní výdělek",
        "Osobní příjem",
        "Relativní příjmová pozice",
        "Příjmová pozice (compatibility proxy)",
        "Současně: student/ka",
        "Aktuální profesní skupina",
        "Poslední/uváděná profesní skupina",
        "nemá stálého partnera",
        "nežijí ve společné domácnosti",
        "Zdraví v core datech",
        "Brand-specific background: NEDODÁN",
        "Domácnost:",
        "bez auta",
        "ve věku neuvedeno",
    ):
        assert phrase in texts, phrase


def test_the_legacy_social_class_never_reaches_the_profile() -> None:
    """Adaptive mode drops ``trida_spolecenska`` (``pipeline.py:639-642``)."""
    assert all("Socioekonomický kontext" not in c["text"] for c in EXPECTED["cases"])


def test_a_missing_sex_is_not_stamped_as_a_woman() -> None:
    """The unit's ``str(NaN)`` is "nan", a non-empty string, so it wrote "žena"."""
    row = {**ROWS[0], "pohlavi": None}
    assert profile_lines(row, [])[0] == "Pohlaví: neuvedeno"
    assert persona_text(row, []).startswith("Jsem člověk, ve věku")


def test_a_missing_student_flag_is_not_a_student() -> None:
    """The unit's ``bool(NaN)`` is True, so an employed person became a student too."""
    row = {**ROWS[0], "zamestnani_status": "employed", "is_student": None}
    assert not any(line.startswith("Současně") for line in profile_lines(row, []))


def test_the_profile_is_cut_at_a_clause_boundary_within_185_words() -> None:
    lines = ["Pohlaví: muž", "Věk: 40 let"] + [
        f"Signál {i}: hodnota {i}; další." for i in range(80)
    ]
    text = first_person(lines)
    assert len(text.split()) <= MAX_WORDS
    assert text.endswith(".")


def test_the_bands_are_the_units() -> None:
    assert age_band("x") == "věk neuveden"
    assert age_band(17) == "méně než 18 let"
    assert age_band(24.0) == "18–24 let"
    assert age_band(80) == "75 a více let"
    assert income_band(0) == "příjem neuveden"
    assert income_band(19999.9) == "do 20 tisíc Kč čistého měsíčně"
    assert income_band(60000) == "60 tisíc Kč a více čistého měsíčně"


def test_household_facts_follow_the_topics() -> None:
    row: dict[str, Typed] = {"F_rodinny_stav": "rozvedeny", "F_auto": None, "F_deti": 1, "F_sam": 0}
    assert household_facts(row, []) == ""
    assert household_facts(row, ["vztahy"]) == "rozvedený(á), děti v domácnosti"
    assert household_facts(row, ["auto"]) == "bez auta"
