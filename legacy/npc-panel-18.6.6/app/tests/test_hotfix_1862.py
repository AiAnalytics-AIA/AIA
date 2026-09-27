from __future__ import annotations

from pathlib import Path


def test_project_creation_openai_policy_and_overview(tmp_path, monkeypatch):
    import ui_server
    monkeypatch.setattr(ui_server, "ROOT", tmp_path)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    created = ui_server.create_project_state({
        "project_type": "research",
        "title": "Hotfix test",
        "project": {"title": "Hotfix test", "goal": "Ověřit runtime"},
        "preferred_provider": "openai",
    })
    assert created["provider_policy"] == "OPENAI_ONLY"
    overview = ui_server.project_overview({"project_id": created["project_id"]})
    assert isinstance(overview.get("stages"), list)
    assert len(overview["stages"]) == 13


def test_questionnaire_ai_route_keeps_selected_provider(monkeypatch):
    import research_designer as rd
    import ui_server
    import legacy_job_dispatch

    calls = []
    def fake_structured(*, system, prompt, tool, model, max_tokens, provider=None, interactive=False, max_turns=8):
        calls.append((tool.get("name"), provider))
        if tool.get("name") in {"submit_fast_research_analysis", "submit_research_analysis"}:
            return ({
                "title":"Test nápojů bez cukru", "problem_summary":"Zjistit reakci.",
                "decision_use":"Rozhodnout o uvedení.", "objectives":["Změřit zájem"],
                "research_questions":["Kdo má zájem?"], "hypotheses":["Aktivní lidé preferují bez cukru."],
                "recommended_topics":["health", "sport"],
                "tracked_sets":[{"title":"Nápoje", "object_type":"značky nápojů", "purpose":"Pozice",
                    "objects":["Coca-Cola Zero", "Pepsi Max", "Mattoni", "Kofola"],
                    "object_question":"Jaký je váš vztah k {object}?", "scale_labels":["negativní", "pozitivní"],
                    "familiarity_required":False, "why_map":"Pozice značek", "objects_are_suggested":True}],
                "non_object_measures":[{"name":"Sport", "reason":"Segmentace", "question_type":"scale"}],
                "audience_recommendation":{"strategy":"population", "description":"ČR 18+", "reason":"Screening"},
                "study_slots":{}, "questions_for_user":[], "complexity":"standard", "estimated_minutes":5,
                "method_reason":"Kvantitativní průzkum", "ready_for_questionnaire":True,
            }, {"provider":provider, "model":model, "mock":True})
        if tool.get("name") == "submit_questionnaire_project":
            return ({"message":"Dotazník připraven.", "project":{
                "schema_version":3, "title":"Test nápojů bez cukru", "goal":"Zjistit reakci.",
                "decision_use":"Rozhodnout o uvedení.", "briefing":{"goal":"Zjistit reakci."},
                "research_plan":{}, "audience":{"description":"ČR 18+", "filters":{}}, "n":300,
                "persona_mode":"calibrated", "model":"gpt-5-mini", "research_context":False,
                "sections":[
                    {"id":"q1", "type":"questions", "title":"Chování", "questions":[
                        {"id":"q_sport", "text":"Jak často sportujete?", "typ":"skala", "skala":[1,10], "popisky_skaly":["nikdy","často"], "povolit_nevim":True, "topics":["sport"]}
                    ]},
                    {"id":"tracked_1", "type":"object_battery", "title":"Nápoje", "object_family":"nápoje", "object_type":"značky nápojů",
                     "objects":["Coca-Cola Zero", "Pepsi Max", "Mattoni", "Kofola"],
                     "object_question":"Jaký je váš vztah k {object}?", "scale_labels":["negativní","pozitivní"],
                     "familiarity_required":False, "output_type":"pozicni_mapa", "visualize":True, "metadata":{}}
                ], "notes":[]
            }}, {"provider":provider, "model":model, "mock":True})
        raise AssertionError(tool.get("name"))

    monkeypatch.setattr(rd, "_structured_with_fallback", fake_structured)
    briefing = {"goal":"Zjistit reakci na nový nápoj bez cukru."}
    analyzed = legacy_job_dispatch.execute_legacy("research_analysis", {"briefing":briefing, "n":300, "provider":"openai", "model":"gpt-5-mini"}, "a")
    built = legacy_job_dispatch.execute_legacy("questionnaire_build", {"analysis":analyzed["analysis"], "briefing":briefing, "project":analyzed["project"], "n":300, "provider":"openai", "model":"gpt-5-mini"}, "q")
    assert built["project"]["sections"]
    assert built["_ai"]["provider"] == "openai"
    assert calls == [("submit_fast_research_analysis", "openai"), ("submit_questionnaire_project", "openai")]


def test_openai_is_allowed_in_live_simulation_gate(monkeypatch):
    import ui_server
    import legacy_job_dispatch
    import full_simulation

    monkeypatch.setattr(ui_server, "has_openai_key", lambda: True)
    monkeypatch.setattr(ui_server, "_fullsim_spec_from_payload", lambda payload: {
        "mode":"sync", "provider":"openai", "scenario_contract":{"status":"APPROVED"}, "include_core_baseline":False
    })
    monkeypatch.setattr(ui_server, "_panel_path_for_project", lambda project: "dummy.csv")
    monkeypatch.setattr(full_simulation, "prepare_full_simulation", lambda req, **kw: {"prepared": True})
    monkeypatch.setattr(full_simulation, "run_full_simulation", lambda req, **kw: {"ok": True, "provider": req.get("provider")})
    monkeypatch.setattr(full_simulation, "validate_full_simulation_result", lambda run, **kw: run)
    out = legacy_job_dispatch.execute_legacy("fullsim_pipeline", {
        "provider":"openai", "confirm_live":True, "scenario_contract":{"status":"APPROVED"}
    }, "sim")
    assert out["ok"] is True
    assert out["provider"] == "openai"


def test_sociomap_hotfix_ui_contract():
    html = (Path(__file__).resolve().parents[1] / "ui_app.html").read_text(encoding="utf-8")
    assert "NPC_PANEL_18_6_2_RUNTIME_SOCIO_HOTFIX" in html
    assert "if(!PROJECT_ID) return null" in html
    assert "Sociomapa · nástroj výsledků" in html
    assert "Hustota respondentů" in html
    assert "maso 1 · maso <= 2" in html
    assert "b.onclick=()=>go('sociomap')" in html
    assert "tabs.appendChild(b)" in html  # Sociomapa tab moved last
    assert "v.appendChild(card)" in html  # Sociomapa result card moved to bottom
    assert "Zobrazit skupinu ${L} na mapě" in html
