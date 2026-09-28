#!/usr/bin/env python3
"""Capture Deep Research leakage-screen and merge fixtures from the vendored 18.6.6 unit.

    python tools/deep_research_capture.py capture   # write the fixtures
    python tools/deep_research_capture.py verify    # re-run and compare, exit 1 on drift

runs the unit's own, unmodified ``research_context.py`` -- ``_canonical_url``,
``_tokens``, ``_similarity``, ``_deterministic_target_overlap``, ``_coerce_findings``
and ``_merge_agents`` -- on fictional inputs written here, and writes

    packages/aia_core/tests/fixtures/deep_research/screen.json
    packages/aia_core/tests/fixtures/deep_research/merge.json
    packages/aia_core/tests/fixtures/deep_research/index.json

``index.json`` pins both fixtures and the unit source they were captured from, by
SHA256. ``test_deep_research_legacy.py`` compares AIA's port
(``aia_core.domain.deep_research.legacy``) with them, exactly.

The module needs only the standard library; its one import of the unit's
configuration (``runtime_config``: two default model names, and a ``.env`` loader
with side effects) is replaced by a stub before it loads, and nothing that would
reach a provider is called. No network, no client material: every input is
invented here.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import sys
import types
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "legacy" / "npc-panel-18.6.6" / "app"
SOURCE = UNIT / "research_context.py"
OUT = ROOT / "packages" / "aia_core" / "tests" / "fixtures" / "deep_research"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_unit_module() -> Any:
    """The unit's ``research_context`` module, loaded by path with a stub configuration."""
    stub = types.ModuleType("runtime_config")
    stub.DEFAULT_ANTHROPIC_RESEARCH_MODEL = "unit-default-anthropic"  # type: ignore[attr-defined]
    stub.DEFAULT_OPENAI_RESEARCH_MODEL = "unit-default-openai"  # type: ignore[attr-defined]
    saved = sys.modules.get("runtime_config")
    sys.modules["runtime_config"] = stub
    try:
        name = "npc_unit_research_context"
        spec = importlib.util.spec_from_file_location(name, SOURCE)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module  # dataclasses resolve their module by name (AGENTS.md)
        spec.loader.exec_module(module)
        return module
    finally:
        if saved is None:
            sys.modules.pop("runtime_config", None)
        else:
            sys.modules["runtime_config"] = saved


# --------------------------------------------------------------------------- #
# Inputs: all fictional
# --------------------------------------------------------------------------- #

URLS: tuple[str, ...] = (
    "https://www.Example.org/zprava/",
    "https://example.org/zprava",
    "HTTPS://WWW.EXAMPLE.ORG/zprava?x=1#frag",
    "http://example.org/a/b/",
    "https://example.org/a/b//",
    "ftp://example.org/file",
    "example.org/no-scheme",
    "https:///no-host",
    "",
    "   https://sub.www.example.org/path/   ",
    "https://example.org:8443/port/",
    "https://user:secret@example.org/cred",
    "https://www.www.example.org/double",
    "https://example.org/?q=%C4%8Desk%C3%A9",
    "not a url at all",
)

TEXT_PAIRS: tuple[tuple[str, str], ...] = (
    ("Spotřeba rostlinných nápojů roste", "Spotřeba rostlinných nápojů v Česku roste"),
    ("Průměrná cena litru je 32 Kč", "Průměrná cena litru"),
    ("", "cokoli"),
    ("a i v ve na se", "je jsou pro do z ze že to u"),
    ("Čeština s diakritikou: žluťoučký kůň úpěl ďábelské ódy", "zlutoucky kun upel dabelske ody"),
    ("Straße à la façon", "strasse a la facon"),
    ("ÆØÅ æøå ÿ Ā ž \u017f", "æøå ÿ ā ž"),
    ("Mean score 4.2 for brand intent", "brand intent mean score"),
    ("Purchase intent 38 % among respondents", "purchase intent among respondents"),
    ("12345 67890 abcd", "12345 abcd efgh"),
    ("Tabák, alkohol a hazard: regulace 2024", "regulace hazardu a tabáku 2024"),
    ("MIXED Case Tokens Here", "mixed case tokens here"),
)

QUESTIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "q1",
        "text": "Jak často kupujete rostlinné nápoje?",
        "kategorie": ["Denně", "Týdně", "Měsíčně", "Nikdy"],
    },
    {"id": "q2", "text": "Souhlasíte se zavedením zálohování plechovek?", "kategorie": []},
    {"id": "q3", "text": "Kterou značku kávy preferujete?", "kategorie": ["Aroma", "Borealis"]},
    {"id": "q4", "text": "How likely would you buy an electric scooter this year?"},
)

CLAIMS: tuple[str, ...] = (
    "38 % respondentů kupuje rostlinné nápoje týdně.",
    "Rostlinné nápoje zdražily o 12 procent kvůli clům.",
    "Většina dotázaných souhlasí se zálohováním plechovek.",
    "Zálohování plechovek zavedlo Slovensko v roce 2022.",
    "Značku kávy Aroma preferuje 41 % kupujících.",
    "Trh s kávou roste o 3 % ročně.",
    "Purchase intent for electric scooters is 22 % this year.",
    "Electric scooter sharing is regulated in Prague since 2021.",
    "Mean score of scooter appeal was 3.9.",
    "Plechovky tvoří 18 % obalového odpadu.",
    "Respondenti preferují levnější varianty.",
    "Nikdo neví.",
)

_TYPES = ("primary_source", "peer_reviewed", "official_report", "other", "Industry", "media")


def _finding(rng: random.Random, i: int) -> dict[str, Any]:
    claim = rng.choice(CLAIMS)
    host = rng.choice(("example.org", "www.example.org", "data.example.net", "journal.example"))
    path = rng.choice(("/a", "/a/", "/b", "/c/d", "/a?x=1"))
    return {
        "claim": claim if rng.random() > 0.05 else "",
        "why_relevant": f"kontext {i}",
        "source_title": f"Zdroj {i}" if rng.random() > 0.05 else "",
        "source_url": f"https://{host}{path}" if rng.random() > 0.08 else "ftp://x/y",
        "source_date": rng.choice((None, "2024-05-01", "", "2023")),
        "evidence_type": rng.choice(_TYPES),
        "geography": rng.choice(("CZ", "SK", "EU", "")),
        "population": rng.choice(("dospělí", "")),
        "topics": rng.sample(
            ("trh", "ceny", "regulace", "chování", " ", "obaly"), rng.randint(0, 4)
        ),
        "source_quality": rng.choice((0.2, 0.54, 0.55, 0.6, 0.75, 0.9, 0.95, 1.0, 1.4, -0.1)),
        "outcome_overlap": rng.random() < 0.15,
        "recommended_use": rng.choice(
            ("context_only", "context_only", "context_only", "exclude_target_leakage", "other")
        ),
    }


def merge_cases() -> list[dict[str, Any]]:
    """Two agents' raw outputs x questions x configuration, covering every branch."""
    rng = random.Random(20260927)
    cases: list[dict[str, Any]] = []
    configs = (
        {"strict_consensus": True, "allow_single_agent_primary": True, "max_context_blocks": 8},
        {"strict_consensus": False, "allow_single_agent_primary": True, "max_context_blocks": 8},
        {"strict_consensus": True, "allow_single_agent_primary": False, "max_context_blocks": 3},
    )
    for n in range(24):
        # A list, not a mapping: the merge depends on the agents' order, and a JSON
        # object written with sorted keys would not keep it.
        agents = [
            {
                "agent": name,
                "raw": {"findings": [_finding(rng, 10 * n + k) for k in range(rng.randint(0, 6))]},
            }
            for name in ("openai", "anthropic")
        ]
        cases.append(
            {
                "id": f"random_{n:02d}",
                "config": configs[n % len(configs)],
                "questions": list(QUESTIONS[: 1 + n % len(QUESTIONS)]),
                "agents": agents,
            }
        )
    # The quirk worth pinning: a peer already used is picked again by a later finding.
    same = "https://example.org/shared"
    cases.append(
        {
            "id": "reused_peer",
            "config": configs[0],
            "questions": [],
            "agents": [
                {
                    "agent": "openai",
                    "raw": {
                        "findings": [
                            _fixed("Trh s kávou roste o 3 % ročně.", same, 0.8),
                            _fixed("Trh s kávou roste o 3 % ročně podle zdroje.", same, 0.7),
                        ]
                    },
                },
                {
                    "agent": "anthropic",
                    "raw": {"findings": [_fixed("Trh s kávou roste o 3 % ročně.", same, 0.9)]},
                },
            ],
        }
    )
    # Ties: equal quality peers, and equal merge confidence in the final sort.
    cases.append(
        {
            "id": "ties",
            "config": configs[0],
            "questions": [],
            "agents": [
                {
                    "agent": "openai",
                    "raw": {
                        "findings": [
                            _fixed(
                                "Plechovky tvoří 18 % obalového odpadu.", "https://a.example/1", 0.7
                            ),
                            _fixed("Zálohování zavedlo Slovensko.", "https://b.example/2", 0.7),
                        ]
                    },
                },
                {
                    "agent": "anthropic",
                    "raw": {
                        "findings": [
                            _fixed(
                                "Plechovky tvoří 18 % obalového odpadu.", "https://c.example/3", 0.7
                            ),
                            _fixed("Zálohování zavedlo Slovensko.", "https://d.example/4", 0.7),
                        ]
                    },
                },
            ],
        }
    )
    return cases


def _fixed(claim: str, url: str, quality: float) -> dict[str, Any]:
    return {
        "claim": claim,
        "why_relevant": "",
        "source_title": "Zdroj",
        "source_url": url,
        "source_date": None,
        "evidence_type": "other",
        "geography": "CZ",
        "population": "",
        "topics": [],
        "source_quality": quality,
        "outcome_overlap": False,
        "recommended_use": "context_only",
    }


# --------------------------------------------------------------------------- #
# Capture
# --------------------------------------------------------------------------- #


def capture_screen(unit: Any) -> dict[str, Any]:
    urls = [{"url": u, "canonical": unit._canonical_url(u)} for u in URLS]
    texts = sorted({t for pair in TEXT_PAIRS for t in pair} | set(CLAIMS))
    tokens = [{"text": t, "tokens": sorted(unit._tokens(t))} for t in texts]
    pairs = [{"a": a, "b": b, "similarity": unit._similarity(a, b)} for a, b in TEXT_PAIRS]
    pairs += [
        {"a": a, "b": b, "similarity": unit._similarity(a, b)}
        for a in CLAIMS
        for b in CLAIMS
        if a < b
    ]
    overlap = []
    for claim in CLAIMS:
        item = unit.EvidenceItem(claim=claim, why_relevant="", source_title="t", source_url="u")
        overlap.append(
            {
                "claim": claim,
                "questions": list(QUESTIONS),
                "overlap": unit._deterministic_target_overlap(item, list(QUESTIONS)),
                "per_question": [unit._deterministic_target_overlap(item, [q]) for q in QUESTIONS],
            }
        )
    return {"canonical_url": urls, "tokens": tokens, "similarity": pairs, "target_overlap": overlap}


def capture_merge(unit: Any) -> dict[str, Any]:
    out = []
    for case in merge_cases():
        cfg = unit.ResearchConfig(enabled=True, **case["config"])
        agents = []
        coerced: list[list[dict[str, Any]]] = []
        for entry in case["agents"]:
            name = entry["agent"]
            findings = unit._coerce_findings(entry["raw"], name)
            coerced.append([asdict(f) for f in findings])
            agents.append(unit.AgentResearch(name, f"mock-{name}", "", "", findings))
        accepted, quarantined = unit._merge_agents(agents, cfg, case["questions"])
        out.append(
            {
                **case,
                "expected": {"coerced": coerced, "accepted": accepted, "quarantined": quarantined},
            }
        )
    return {"cases": out}


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def render() -> dict[str, str]:
    unit = load_unit_module()
    files = {
        "screen.json": _dump(capture_screen(unit)),
        "merge.json": _dump(capture_merge(unit)),
    }
    index = {
        "captured_with": "tools/deep_research_capture.py",
        "unit_source": {"research_context.py": _sha(SOURCE)},
        "fixtures": {
            name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in files.items()
        },
    }
    files["index.json"] = _dump(index)
    return files


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"capture", "verify"}:
        print(__doc__)
        return 2
    files = render()
    if argv[1] == "capture":
        OUT.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (OUT / name).write_text(text, encoding="utf-8")
        print(f"wrote {len(files)} files to {OUT.relative_to(ROOT)}")
        return 0
    drift = [n for n, text in files.items() if (OUT / n).read_text(encoding="utf-8") != text]
    if drift:
        print("fixtures differ from a fresh capture: " + ", ".join(drift))
        return 1
    print("fixtures reproduce from the unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
