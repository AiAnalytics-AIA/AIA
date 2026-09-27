"""The 18.6.6 leakage screen and merge rules, EXACT against the unit's own code.

Fixtures are captured by ``tools/deep_research_capture.py``, which runs the vendored
``legacy/npc-panel-18.6.6/app/research_context.py`` unmodified; ``index.json`` pins
them and the unit source by SHA256. The unit needs only the standard library, so
the capture is also re-run here: a fixture that no longer reproduces from the
vendored unit fails, exactly as a port that no longer matches the fixture does.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.deep_research.legacy import (
    LegacyFinding,
    LegacyMergeConfig,
    canonical_url,
    coerce_findings,
    deterministic_target_overlap,
    merge_agents,
    similarity,
    tokens,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "deep_research"
UNIT = ROOT / "legacy" / "npc-panel-18.6.6" / "app"
INDEX = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))
SCREEN = json.loads((FIXTURES / "screen.json").read_text(encoding="utf-8"))
MERGE = json.loads((FIXTURES / "merge.json").read_text(encoding="utf-8"))["cases"]


def test_fixtures_are_pinned_and_the_unit_source_is_the_one_captured() -> None:
    for name, sha in INDEX["fixtures"].items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == sha, name
    for name, sha in INDEX["unit_source"].items():
        assert hashlib.sha256((UNIT / name).read_bytes()).hexdigest() == sha, name


def test_the_fixtures_reproduce_from_the_vendored_unit(tool_loader: Any) -> None:
    capture = tool_loader("deep_research_capture")
    fresh = capture.render()
    drift = [name for name, text in fresh.items() if (FIXTURES / name).read_text("utf-8") != text]
    assert drift == []


@pytest.mark.parametrize("case", SCREEN["canonical_url"], ids=lambda c: repr(c["url"]))
def test_canonical_url_matches_the_unit(case: dict[str, Any]) -> None:
    assert canonical_url(case["url"]) == case["canonical"]


@pytest.mark.parametrize("case", SCREEN["tokens"], ids=lambda c: c["text"][:30])
def test_tokens_match_the_unit(case: dict[str, Any]) -> None:
    assert sorted(tokens(case["text"])) == case["tokens"]


def test_similarity_matches_the_unit() -> None:
    for case in SCREEN["similarity"]:
        assert similarity(case["a"], case["b"]) == case["similarity"], (case["a"], case["b"])


@pytest.mark.parametrize("case", SCREEN["target_overlap"], ids=lambda c: c["claim"][:30])
def test_target_overlap_matches_the_unit(case: dict[str, Any]) -> None:
    assert deterministic_target_overlap(case["claim"], case["questions"]) is case["overlap"]
    for question, expected in zip(case["questions"], case["per_question"], strict=True):
        assert deterministic_target_overlap(case["claim"], [question]) is expected


@pytest.mark.parametrize("case", MERGE, ids=lambda c: c["id"])
def test_coerce_and_merge_match_the_unit(case: dict[str, Any]) -> None:
    findings: list[LegacyFinding] = []
    for entry, expected in zip(case["agents"], case["expected"]["coerced"], strict=True):
        coerced = coerce_findings(entry["raw"], entry["agent"])
        assert [f.as_record() for f in coerced] == expected
        findings.extend(coerced)
    accepted, quarantined = merge_agents(
        findings, LegacyMergeConfig(**case["config"]), case["questions"]
    )
    assert accepted == case["expected"]["accepted"]
    assert quarantined == case["expected"]["quarantined"]


def test_every_merge_branch_is_exercised_by_the_captures() -> None:
    seen: Counter[str] = Counter()
    for case in MERGE:
        seen.update(q["reason"] for q in case["expected"]["quarantined"])
        seen.update(
            "consensus" if a["consensus"] else "single_agent" for a in case["expected"]["accepted"]
        )
    assert set(seen) == {
        "target_outcome_overlap",
        "deterministic_target_overlap",
        "low_source_quality",
        "no_independent_confirmation",
        "consensus",
        "single_agent",
    }


def test_a_consumed_peer_is_paired_again_as_the_unit_does() -> None:
    case = next(c for c in MERGE if c["id"] == "reused_peer")
    urls = [tuple(a["supporting_urls"]) for a in case["expected"]["accepted"]]
    assert len(urls) == 2 and urls[0] == urls[1]
