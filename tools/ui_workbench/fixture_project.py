"""Fixture research projects for the workbench's unit (research-flow plan, chunk 1).

The workbench never calls a model, so a step whose screen shows an AI answer
(the plan's understanding, a built questionnaire, a proposed audience) can be
seen there only from a project that already holds one. This writes such
projects through the unit's own save route, ``POST /api/projects/save``, with
the body ``scheduleServerSave`` sends -- nothing reaches the unit's store any
other way.

Every word is synthetic and fictional, written here, and not taken from a
showcase demo: the demos' brands are reference content that stays under
``legacy/`` (tools/exposure_check.sh, rule 3). The projects are added to as the
research chunks land; each stage says which screen it exists for.

    python tools/ui_workbench/fixture_project.py          # write or refresh them
    python tools/ui_workbench/fixture_project.py --list   # print their /app links

The ids are kept in ``tmp/ui-workbench/fixtures.json`` so a second run updates
the same projects instead of adding more. Stdlib only.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "tmp" / "ui-workbench" / "fixtures.json"
UNIT = "http://127.0.0.1:8767"
FACADE = "http://127.0.0.1:8780"

# The brief: problem types, title, goal, decision, briefing (renderBrief).
BRIEF: dict[str, Any] = {
    "title": "Workbench · ranní nápoj pro dojíždějící",
    "study_type": "custom",
    "goal": (
        "Zjistit, zda nový ranní nápoj v plechovce dává smysl lidem, kteří denně "
        "dojíždějí do práce, komu nejvíc a za jakou cenu."
    ),
    "decision_use": "Rozhodnutí o uvedení, o jedné ze čtyř variant a o ceně do 60 Kč.",
    "briefing": {
        "problem_types": ["product", "portfolio", "price"],
        "product_description": (
            "Fiktivní nápoj pro workbench: lehce sycený, s kofeinem z čaje, bez "
            "přidaného cukru, 0,33 l."
        ),
        "situation": "Kategorie roste, ale pije ji hlavně mladší publikum ve městech.",
        "what_is_known": "Interní ochutnávka preferovala mírnější chuť.",
        "constraints": "Jedna výrobní linka; nejvýše dvě příchutě na startu.",
    },
}

# The plan: the AI's reading of the brief, as renderPlan draws it (ANALYSIS).
ANALYSIS: dict[str, Any] = {
    "problem_summary": (
        "Jde o test nového konceptu a výběr varianty: má ranní nápoj pro dojíždějící "
        "potenciál, která ze čtyř variant je nejsilnější a jaká cena je přijatelná."
    ),
    "objectives": [
        "Změřit zájem o koncept u lidí, kteří denně dojíždějí.",
        "Porovnat čtyři varianty na stejné škále.",
        "Najít cenu, nad kterou zájem výrazně klesá.",
    ],
    "hypotheses": [
        "Mírnější varianta osloví širší publikum než nejsilnější.",
        "Cena nad 49 Kč sníží zkušební nákup o více než třetinu.",
    ],
    "tracked_sets": [
        {
            "title": "Varianty nápoje",
            "object_type": "varianta",
            "purpose": "čtyři varianty téhož nápoje na stejné otázce",
            "objects": ["Varianta Jemná", "Varianta Silná", "Varianta Bylinná", "Varianta Citrus"],
            "object_question": "Jak vás oslovuje {object}?",
            "scale_labels": ["vůbec", "velmi"],
        },
        {
            "title": "Příležitosti pití",
            "object_type": "situace",
            "purpose": "situace, ve kterých by lidé nápoj pili",
            "objects": ["Cesta do práce", "Ráno doma", "Odpoledne v práci", "Před sportem"],
            "object_question": "Jak dobře se nápoj hodí na {object}?",
            "scale_labels": ["vůbec", "velmi"],
        },
    ],
    "questions_for_user": [
        "Má se výzkum omezit na lidi, kteří dojíždějí veřejnou dopravou?",
        "Je cena 60 Kč horní hranicí, nebo jen orientační?",
    ],
    # projectVariants1793: at most three ways to scope the project.
    "project_variants": [
        {
            "id": "focused",
            "badge": "RYCHLÝ",
            "title": "Jen varianty",
            "summary": "Porovnat čtyři varianty a vybrat jednu.",
            "n": 300,
            "complexity": "light",
            "tradeoff": "Bez ceny a bez příležitostí pití.",
            "objectives": ["Porovnat čtyři varianty na stejné škále."],
            "research_questions": ["Která varianta osloví nejvíc lidí?"],
            "hypotheses": [],
        },
        {
            "id": "recommended",
            "badge": "DOPORUČENO",
            "title": "Varianty a cena",
            "summary": "Varianty, cena a situace, ve kterých by lidé nápoj pili.",
            "n": 600,
            "complexity": "standard",
            "tradeoff": "Delší dotazník.",
            "objectives": [
                "Změřit zájem o koncept u lidí, kteří denně dojíždějí.",
                "Porovnat čtyři varianty na stejné škále.",
                "Najít cenu, nad kterou zájem výrazně klesá.",
            ],
            "research_questions": ["Která varianta a za jakou cenu?"],
            "hypotheses": ["Cena nad 49 Kč sníží zkušební nákup o více než třetinu."],
        },
        {
            "id": "broad",
            "badge": "ŠIRŠÍ",
            "title": "Celá kategorie",
            "summary": "K tomu postoje ke kategorii a konkurenci.",
            "n": 1000,
            "complexity": "complex",
            "deep_research": True,
            "tradeoff": "Dražší a delší; kontext z Deep Research.",
            "objectives": ["Pochopit celou kategorii ranních nápojů."],
            "research_questions": ["Kde je v kategorii mezera?"],
            "hypotheses": [],
        },
    ],
}

# The questionnaire: the sections an AI build or an import leaves (renderQuestionnaire's
# editor): a question block with each question type, and a tracked object set.
SECTIONS: list[dict[str, Any]] = [
    {
        "id": "sec_wb_main",
        "type": "questions",
        "title": "Hlavní otázky",
        "purpose": "Zájem a příležitosti pití",
        "questions": [
            {
                "id": "Q_wb1",
                "text": "Jak často během pracovního týdne dojíždíte?",
                "typ": "vyber",
                "kategorie": ["Každý den", "Tři až čtyři dny", "Jeden až dva dny", "Méně často"],
                "povolit_nevim": False,
            },
            {
                "id": "Q_wb2",
                "text": "Jak pravděpodobně byste nápoj vyzkoušeli?",
                "typ": "skala",
                "skala": [1, 10],
                "popisky_skaly": ["vůbec", "zcela"],
                "povolit_nevim": False,
            },
            {
                "id": "Q_wb3",
                "text": "Kde nápoje na cestu obvykle kupujete?",
                "typ": "multi",
                "kategorie": ["Nádraží", "Supermarket", "Čerpací stanice", "Automat"],
                "povolit_nevim": False,
            },
            {
                "id": "Q_wb4",
                "text": "Co by vás přesvědčilo nápoj koupit znovu?",
                "typ": "otevrena",
                "povolit_nevim": False,
            },
        ],
    },
    {
        "id": "sec_wb_set",
        "type": "object_battery",
        "title": "Sledovaná sada — varianty",
        "purpose": "Která varianta osloví nejvíc",
        "object_family": "varianta",
        "object_type": "varianta",
        "objects": ["Varianta Jemná", "Varianta Silná", "Varianta Bylinná", "Varianta Citrus"],
        "object_question": "Jak vás oslovuje {object}?",
        "scale": [1, 10],
        "scale_labels": ["vůbec", "velmi"],
        "familiarity_required": False,
        "output_type": "pozicni_mapa",
        "visualize": True,
        "metadata": {"tracked_set": True},
    },
]

FIXTURES: dict[str, dict[str, Any]] = {
    # The brief with nothing filled in: the first screen as a new project sees it.
    "empty": {"project": {"title": "Workbench · prázdné zadání"}, "analysis": None},
    # Brief and plan filled: every screen up to the questionnaire has content.
    "planned": {"project": BRIEF, "analysis": ANALYSIS},
    # The plan's project with a questionnaire, opened on its editor.
    "questionnaire": {
        "project": {**BRIEF, "sections": SECTIONS, "ui_state": {"questionnaire_path": "manual"}},
        "analysis": ANALYSIS,
    },
    # The questionnaire's project on the ČR 18+ branch, narrowed by a categorical
    # filter and a range, as the factor editor writes them (renderAudience).
    "audience": {
        "project": {
            **BRIEF,
            "sections": SECTIONS,
            "ui_state": {
                "questionnaire_path": "manual",
                "audience_entry": "analytics",
                "analytics_choice": "cz18",
            },
            "audience": {
                "source_mode": "population",
                "strategy": "filters",
                "dataset_id": "",
                "dataset_name": "ČR 18+",
                "description": "Dojíždějící v produktivním věku",
                "filters": {"kraj": ["Fiktivní kraj A"], "vek": {"min": 25, "max": 54}},
                "segment": {"mode": "none"},
            },
        },
        "analysis": ANALYSIS,
    },
}


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        UNIT + path,
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        out: dict[str, Any] = json.load(r)
        return out


def _boot() -> tuple[dict[str, Any], str]:
    """BOOT.empty_project and BOOT.panel.version, as the classic save reads them."""
    with urllib.request.urlopen(UNIT + "/api/bootstrap", timeout=30) as r:
        boot = json.load(r)
    empty = boot.get("empty_project")
    if not isinstance(empty, dict):
        raise SystemExit("The unit's bootstrap has no empty_project.")
    version = (boot.get("panel") or {}).get("version")
    return empty, version if isinstance(version, str) else ""


def _known(project_id: str) -> int | None:
    """The project's current revision, or None if the unit no longer has it."""
    try:
        r = _post("/api/projects/load", {"project_id": project_id})
    except urllib.error.HTTPError:
        return None
    rev = r.get("revision")
    return rev if isinstance(rev, int) else None


def write() -> dict[str, str]:
    empty, panel_version = _boot()
    ids: dict[str, str] = json.loads(STATE.read_text()) if STATE.exists() else {}
    for key, fx in FIXTURES.items():
        project = copy.deepcopy(empty)
        for k, v in fx["project"].items():
            project[k] = {**project.get(k, {}), **v} if isinstance(v, dict) else v
        previous = ids.get(key)
        revision = _known(previous) if previous else None
        # scheduleServerSave's body, key for key.
        body = {
            "project_id": previous if revision is not None else None,
            "parent_project_id": None,
            "project_type": "research",
            "project": project,
            "analysis": fx["analysis"],
            "panel_version": panel_version,
            "reason": "workbench_fixture",
        }
        r = _post("/api/projects/save", body)
        pid = r.get("project_id")
        if not isinstance(pid, str):
            raise SystemExit(f"The unit did not return a project id for {key}: {r}")
        ids[key] = pid
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(ids, indent=2) + "\n")
    return ids


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--list", action="store_true", help="print the fixtures' links, write nothing")
    a = ap.parse_args(argv)
    if a.list:
        ids = json.loads(STATE.read_text()) if STATE.exists() else {}
    else:
        try:
            ids = write()
        except urllib.error.URLError as e:
            print(f"The workbench's unit is not reachable at {UNIT} ({e.reason}).")
            print("Start it with `make ui-workbench`.")
            return 1
    for key, pid in ids.items():
        print(f"{key:8} {pid}  {FACADE}/app/research/{pid}/brief")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
