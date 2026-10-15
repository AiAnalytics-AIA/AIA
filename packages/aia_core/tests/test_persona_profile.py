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
import math
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
from aia_core.domain.persona_signals import (
    compatibility_columns,
    grounded_text,
    parse_catalog,
    parse_value_labels,
    render,
    signal_budget,
)
from aia_core.domain.persona_topics import TOPIC_KEYS, block_topics, question_topics
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


# --------------------------------------------------------------------------- #
# Topics (3c)
# --------------------------------------------------------------------------- #

QUESTIONS: list[dict[str, Any]] = _INPUTS["questions"]


def test_the_keyword_table_is_the_units() -> None:
    assert {k: list(v) for k, v in TOPIC_KEYS.items()} == EXPECTED["topic_keys"]


@pytest.mark.parametrize("index", range(len(QUESTIONS)))
def test_a_questions_topics_are_the_units(index: int) -> None:
    q = QUESTIONS[index]
    assert (
        question_topics(q["text"] + " " + " ".join(q["options"]))
        == (EXPECTED["question_topics"][index])
    )


@pytest.mark.parametrize("index", range(len(_INPUTS["blocks"])))
def test_a_blocks_topics_are_the_union_in_first_seen_order(index: int) -> None:
    block = [(QUESTIONS[i]["text"], QUESTIONS[i]["options"]) for i in _INPUTS["blocks"][index]]
    assert block_topics(block) == EXPECTED["block_topics"][index]


def test_the_fixture_reaches_every_topic_and_the_ambiguous_words() -> None:
    seen = {t for topics in EXPECTED["question_topics"] for t in topics}
    assert seen == set(TOPIC_KEYS)
    by_text = {q["text"]: t for q, t in zip(QUESTIONS, EXPECTED["question_topics"], strict=True)}
    assert by_text["Automaticky obnovujete předplatné?"] == ["predplatne"]  # auto != automaticky
    assert "bydleni" not in by_text["Může se to být stát kdykoli?"]  # byt != být
    assert by_text["Jaké je počasí?"] == []


# --------------------------------------------------------------------------- #
# Grounded signals (3d)
# --------------------------------------------------------------------------- #

CATALOG = parse_catalog((FIXTURES / "catalog.csv").read_bytes())
LABELS = parse_value_labels((UNIT / "PERSONA_VALUE_LABELS_v17.json").read_bytes())
SIGNAL_CASES: list[dict[str, Any]] = _INPUTS["signal_cases"]


def _typed_rows(name: str) -> list[dict[str, Typed]]:
    reader = csv.reader(io.StringIO((FIXTURES / name).read_text("utf-8")))
    header, *raw = list(reader)
    columns = {h: [None if r[i] == "" else r[i] for r in raw] for i, h in enumerate(header)}
    kinds = {h: column_type(h, cells) for h, cells in columns.items()}
    return [{h: _typed(columns[h][i], kinds[h]) for h in header} for i in range(len(raw))]


SIGNAL_ROWS = _typed_rows("signals.csv")


def test_the_signal_inputs_are_pinned() -> None:
    assert _sha(FIXTURES / "catalog.csv") == EXPECTED["catalog_sha256"]
    assert _sha(FIXTURES / "signals.csv") == EXPECTED["signal_rows_sha256"]


@pytest.mark.parametrize("index", range(len(SIGNAL_CASES)))
def test_the_grounded_signals_are_the_units(index: int) -> None:
    case = SIGNAL_CASES[index]
    row = SIGNAL_ROWS[case["row"]]
    assert (
        grounded_text(row, case["topics"], CATALOG, LABELS)
        == (EXPECTED["signals"][index]["grounded"])
    )


@pytest.mark.parametrize("index", range(len(SIGNAL_CASES)))
def test_the_whole_persona_with_its_signals_is_the_units(index: int) -> None:
    case = SIGNAL_CASES[index]
    row = SIGNAL_ROWS[case["row"]]
    behaviour = grounded_text(row, case["topics"], CATALOG, LABELS)
    assert persona_text(row, case["topics"], behaviour) == EXPECTED["signals"][index]["persona"]


def test_the_signal_fixture_reaches_every_kind_role_and_cap() -> None:
    texts = " ".join(s["grounded"] for s in EXPECTED["signals"])
    for phrase in (
        "populační průměr",  # bfi_z
        "/5 [",  # scale5
        "/4 [",
        "/6 [",
        "min/den",
        "h/týden",
        "(0–1)",
        "PHQ-9",
        "GAD-7",
        "účast ve volbách: ",  # yesno
        "více než jednou týdně",  # text, the duplicated key's later value
        "(0=",  # anchors compacted
        "; vyšší hodnota",  # values with a direction
    ):
        assert phrase in texts, phrase
    for role in (
        "měřeno v core donorovi",
        "měřeno ve stejném core donorovi",
        "statisticky přiřazený celý donor blok",
        "kalibrovaný behaviorální model",
        "modelový hodnotový proxy",
        "kalibrovaný modelový kompozit",
        "kalibrovaná modelová položka",
        "something else",
        ", match ",
    ):
        assert role in texts, role
    assert "modelový sklon" not in texts  # a MODELED_BEHAVIOR_PRIOR is never shown
    assert "chybí" not in texts and "bez témat" not in texts
    # The ISSP block holds five signals; the unit shows at most three of them at once.
    assert all(s["grounded"].count("ISSP") <= 3 for s in EXPECTED["signals"])
    assert any(s["grounded"].count("ISSP") == 3 for s in EXPECTED["signals"])


def test_the_budget_is_the_policys() -> None:
    assert [signal_budget(["a"] * 0), signal_budget(["a"])] == [4, 4]
    assert signal_budget(["a", "b", "c"]) == 5
    assert signal_budget([str(i) for i in range(20)]) == 8


def test_a_population_with_compatibility_columns_is_named() -> None:
    assert compatibility_columns(["vek", "P_media_tv_10", "P_value_local_10", "Px"]) == (
        "P_media_tv_10",
        "P_value_local_10",
    )


def _same(a: Any, b: Any) -> bool:
    """Equal, NaN equal to NaN (the unit's empty priority and min_abs_z read NaN)."""
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return bool(a == b)


def test_the_catalog_is_read_as_the_unit_reads_it() -> None:
    expected = EXPECTED["catalog_parsed"]
    assert len(CATALOG) == len(expected)
    for signal, want in zip(CATALOG, expected, strict=True):
        got = {
            "column": signal.column,
            "label": signal.label,
            "topics": sorted(signal.topics),
            "source": signal.source,
            "wave": signal.wave,
            "evidence_role": signal.evidence_role,
            "block": signal.block,
            "kind": signal.kind,
            "priority": signal.priority,
            "min_abs_z": signal.min_abs_z,
            "concept": signal.concept,
        }
        assert set(got) == set(want)
        for key in got:
            assert _same(got[key], want[key]), (signal.column, key, got[key], want[key])


@pytest.mark.parametrize("index", range(len(SIGNAL_ROWS)))
def test_every_signal_renders_with_the_units_text_and_score(index: int) -> None:
    row = SIGNAL_ROWS[index]
    for signal, want in zip(CATALOG, EXPECTED["renders"][index], strict=True):
        got = render(signal, row, LABELS)
        if want is None:
            assert got is None, signal.column
        else:
            assert got is not None and got[0] == want[0], signal.column
            assert _same(got[1], want[1]), (signal.column, got[1], want[1])


@pytest.mark.parametrize("index", range(len(_INPUTS["anchors"])))
def test_anchor_prose_is_compacted_as_the_unit_does(index: int) -> None:
    from aia_core.domain.persona_signals import _compact_anchor

    assert _compact_anchor(*_INPUTS["anchors"][index]) == EXPECTED["anchors"][index]


def test_a_signal_with_an_unknown_priority_ranks_last() -> None:
    """The one difference in the ranking: 18.6.6 left a NaN score where Python's sort put it,
    which differs between Python versions; AIA ranks it after every known score."""
    from dataclasses import replace

    base = next(s for s in CATALOG if s.column == "SIG_brand")
    known = replace(base, column="SIG_known", label="známé", priority=0.01)
    unknown = replace(base, column="SIG_unknown", label="neznámé", priority=math.nan)
    row: dict[str, Typed] = {"SIG_known": 5, "SIG_unknown": 9}
    text = grounded_text(row, ["znacka"], [unknown, known], LABELS)
    assert text.index("známé") < text.index("neznámé")
    assert all(not math.isnan(s.priority) for s in CATALOG if s.column != "SIG_raw")
