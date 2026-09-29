"""Fixture research studies for the workbench (research-flow plan, chunk 1; ADR 0018).

The workbench never calls a model, so a step whose screen shows an AI answer
(the plan's understanding, a built questionnaire, a proposed audience) can be
seen there only from a study that already holds one. This writes such studies'
working content through AIA's own route, ``PUT
/api/v1/studies/<study>/workspace/content``, as the seeded operator -- the route
the stages save through -- over the research template AIA serves with the
content. Nothing reaches the 18.6.6 unit.

Every word is synthetic and fictional, written here, and not taken from a
showcase demo: the demos' brands are reference content that stays under
``legacy/`` (tools/exposure_check.sh, rule 3). The fixtures are added to as the
research chunks land; each stage says which screen it exists for.

    python tools/ui_workbench/fixture_project.py          # write or refresh them
    python tools/ui_workbench/fixture_project.py --list   # print their /app links

Each fixture is an AIA study of the seeded fictional client Horizont Mobility
(``POST /api/v1/clients/<client>/studies``), opened at
``/app/clients/<client>/research/<study>/<stage>`` as on develop. The studies are
kept in ``tmp/ui-workbench/studies.json``, so a second run saves a new revision of
the same studies instead of adding more. Stdlib only.
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
STUDIES = ROOT / "tmp" / "ui-workbench" / "studies.json"
# The workbench's operator: the local API's development credential (api_standin.py).
OPERATOR = "workbench@example.invalid"
CLIENT = "Horizont Mobility"
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
    # The audience's project with dimensions chosen from the catalogue, one
    # requested dimension waiting for evidence, and a sample set by hand
    # (renderPersona): the chips, the rows, the request and the sample drawn.
    "persona": {
        "project": {
            **BRIEF,
            "sections": SECTIONS,
            "ui_state": {
                "questionnaire_path": "manual",
                "audience_entry": "analytics",
                "analytics_choice": "cz18",
            },
            "persona_dimensions": {"approved": ["media", "cena", "technologie"]},
            "requested_dimensions": [
                {
                    "label": "Vztah k fiktivní službě",
                    "status": "needs_evidence",
                    "source_strategy": "document_or_research",
                }
            ],
            "n": 450,
        },
        "analysis": ANALYSIS,
    },
}


def _api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    req = urllib.request.Request(
        FACADE + "/api/v1" + path,
        data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
        headers={"content-type": "application/json", "authorization": f"Bearer {OPERATOR}"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _content(study: str) -> dict[str, Any] | None:
    """The study's working content as AIA serves it, or None if AIA has no such study."""
    try:
        out: dict[str, Any] = _api("GET", f"/studies/{study}/workspace/content")
    except urllib.error.HTTPError:
        return None
    return out


def project_of(fx: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    """The fixture's project: its own fields over the research template's."""
    project = copy.deepcopy(template)
    for k, v in fx["project"].items():
        project[k] = {**project.get(k, {}), **v} if isinstance(v, dict) else v
    return project


def write() -> dict[str, dict[str, str]]:
    """Each fixture's study under the workbench client, holding the fixture as its content."""
    clients = [c for c in _api("GET", "/workspace/clients") if c["name"].startswith(CLIENT)]
    if not clients:
        raise SystemExit(f"The workbench's API has no client named {CLIENT!r}; is it seeded?")
    client = clients[0]["client_id"]
    known: dict[str, dict[str, str]] = json.loads(STUDIES.read_text()) if STUDIES.exists() else {}
    out: dict[str, dict[str, str]] = {}
    for key, fx in FIXTURES.items():
        study = (known.get(key) or {}).get("study")
        current = _content(study) if study else None
        if current is None:  # a fresh API: a new study for the fixture
            made = _api(
                "POST",
                f"/clients/{client}/studies",
                {"name": f"Workbench · {key}", "kind": "RESEARCH"},
            )
            study = made["study_id"]
            current = _content(study)
            if current is None:
                raise SystemExit(f"AIA does not serve the new study {study}'s content")
        assert study is not None
        _api(
            "PUT",
            f"/studies/{study}/workspace/content",
            {
                "content": project_of(fx, current["template"]),
                "analysis": fx["analysis"],
                "base_revision": current["revision"],
                "reason": "workbench_fixture",
            },
        )
        out[key] = {"client": client, "study": study}
    STUDIES.parent.mkdir(parents=True, exist_ok=True)
    STUDIES.write_text(json.dumps(out, indent=2) + "\n")
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--list", action="store_true", help="print the fixtures' links, write nothing")
    a = ap.parse_args(argv)
    if a.list:
        studies = json.loads(STUDIES.read_text()) if STUDIES.exists() else {}
    else:
        try:
            studies = write()
        except urllib.error.URLError as e:
            print(f"The workbench is not reachable at {FACADE} ({e.reason}).")
            print("Start it with `make ui-workbench`.")
            return 1
    print(f"Sign in first: {FACADE}/workbench/sign-in")
    for key, s in studies.items():
        where = f"/app/clients/{s['client']}/research/{s['study']}/brief"
        print(f"{key:13} {s['study']}  {FACADE}{where}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
