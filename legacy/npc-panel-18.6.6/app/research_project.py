"""User-facing research project model for NPC Panel 15.0.

The product unit is one research project, not separate Survey / Audience / Map apps.
A project can contain ordinary questionnaire blocks and any number of independent
tracked-object sets.  A tracked set is a comparable item family evaluated with
the same question/scale. 4-15 items is a recommendation, not a universal hard rule: brands, media channels, emotions, relationships, processes,
attributes, occupations, alternatives, etc.

Claude may propose or revise a project, but normalization and compilation are
strictly deterministic and remain authoritative.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any
import html, re
import re

from runtime_config import resolve_model, resolve_provider_model
from study_contract import StudySpec, slugify
from navrh import _validuj as validate_standard_brief
from provider_auth import get_ai_provider, normalize_ai_provider
from product_policy import sample_size_bounds, tracked_set_limits, tracked_set_warning

QUESTION_TYPES = {"vyber", "multi", "skala", "otevrena"}
SECTION_TYPES = {"questions", "object_battery"}
PERSONA_MODES = {"full", "demographics", "core", "none", "calibrated"}
AUDIENCE_STRATEGIES = {"population", "filters", "discover", "segment"}
AUDIENCE_SOURCE_MODES = {"population", "customer", "special_audience"}
STUDY_TYPES = {"elections", "public_opinion", "brand", "concept_test", "satisfaction", "segmentation", "scenario", "custom"}
COMPLEXITY_LEVELS = {"short", "standard", "deep", "custom"}


def _clean_text(x: Any, fallback: str = "") -> str:
    text=html.unescape(str(x if x is not None else fallback)).strip()
    # Defensive cleanup for malformed tool/XML artifacts such as <item> and the
    # observed character-per-line rendering: "<\ni\nt...>\nZ\nj...".
    text=re.sub(r"<\s*/?\s*i\s*t\s*e\s*m\s*>","",text,flags=re.I)
    text=re.sub(r"<[^>]{1,80}>","",text)
    lines=[ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines)>=5 and sum(len(ln)==1 for ln in lines)/len(lines)>=0.65:
        text=''.join(lines)
    else:
        text='\n'.join(lines) if len(lines)>1 else (lines[0] if lines else '')
    return re.sub(r"[ \t]+"," ",text).strip()


def _unique_id(base: str, used: set[str], prefix: str = "q") -> str:
    root = slugify(base) or prefix
    if root[0].isdigit():
        root = f"{prefix}_{root}"
    cand = root
    i = 2
    while cand in used:
        cand = f"{root}_{i}"
        i += 1
    used.add(cand)
    return cand


def empty_project(*, title: str = "Nový výzkum", goal: str = "", n: int = 300) -> dict[str, Any]:
    return {
        "schema_version": 3,
        "title": title,
        "study_type": "custom",
        "study_config": {},
        "instrument_library": {"version": "", "missing_slots": [], "skipped_instruments": []},
        "goal": goal,
        "decision_use": "",
        "briefing": {
            "product_description": "",
            "situation": "",
            "what_is_known": "",
            "constraints": "",
        },
        "research_plan": {
            "status": "draft",
            "problem_summary": "",
            "objectives": [],
            "research_questions": [],
            "hypotheses": [],
            "recommended_topics": [],
            "non_object_measures": [],
            "questions_for_user": [],
            "complexity": "standard",
            "estimated_minutes": None,
            "method_reason": "",
        },
        "audience": {
            "source_mode": "population",
            "dataset_id": "",
            "dataset_name": "ČR 18+",
            "builtin_subpanel": "",
            "strategy": "population",
            "description": "ČR 18+",
            "filters": {},
            "segment": {"mode": "none"},
            "product_description": "",
            "success_definition": "",
            "discovery_note": "",
            "subpanel_status": "",
            "support_tier": "",
            "support_summary": {},
            "audience_recommendation": {},
        },
        "n": int(n),
        # The v15.2 coherent core is the safest practical population default; extended/legacy layers remain diagnostic.
        "persona_mode": "calibrated",
        "persona_dimensions": {"approved": []},
        "panel_mode": "standard",
        "ai_panel_profile": {},
        "model": "sonnet",
        "ui_state": {"questionnaire_path":"choose","audience_entry":"choose","persona_path":"choose"},
        "research_context": True,
        "pre_research": {},
        "run_policy": {"provider": get_ai_provider(), "allow_provider_fallback": False},
        "budget": {"max_usd": None, "warning_pct": 80},
        "sections": [],
        "discovery": {"enabled": False, "question_id": "", "positive_answers": [], "min_positive": 20},
        "notes": [],
    }


def _normalize_question(q: dict[str, Any], *, section_id: str, used: set[str], ordinal: int) -> dict[str, Any]:
    if not isinstance(q, dict):
        raise ValueError("Otázka musí být objekt.")
    typ = _clean_text(q.get("typ") or "vyber")
    if typ not in QUESTION_TYPES:
        raise ValueError(f"Neznámý typ otázky: {typ}")
    text = _clean_text(q.get("text"))
    if not text:
        raise ValueError("Otázka nemá text.")
    raw_id = _clean_text(q.get("id") or f"{section_id}_{ordinal}")
    qid = _unique_id(raw_id, used)
    out = {"id": qid, "text": text, "typ": typ}
    cats = [_clean_text(x) for x in (q.get("kategorie") or []) if _clean_text(x)]
    if typ in {"vyber", "multi"}:
        if len(cats) < 2:
            raise ValueError(f"{qid}: výběrová otázka potřebuje alespoň 2 kategorie.")
        out["kategorie"] = cats[:24]
    if typ == "skala":
        sc = list(q.get("skala") or [1, 10])[:2]
        if len(sc) != 2:
            sc = [1, 10]
        out["skala"] = [int(sc[0]), int(sc[1])]
        labs = [_clean_text(x) for x in (q.get("popisky_skaly") or [])][:2]
        if len(labs) == 2 and all(labs):
            out["popisky_skaly"] = labs
    if typ == "otevrena":
        out["max_slov"] = max(5, min(120, int(q.get("max_slov") or 35)))
    out["povolit_nevim"] = bool(q.get("povolit_nevim", False))
    if _clean_text(q.get("filtr")):
        # Store filters already repaired against the questions asked so far, so the
        # project file holds an expression the linter and the runtime both accept.
        from filter_syntax import repair_filter
        fixed, _note = repair_filter(_clean_text(q.get("filtr")), set(used) - {qid})
        out["filtr"] = fixed or _clean_text(q.get("filtr"))
    topics = [_clean_text(x) for x in (q.get("topics") or []) if _clean_text(x)]
    if topics:
        out["topics"] = topics[:6]
    md = dict(q.get("metadata") or {})
    md.update({"research_section": section_id, "research_section_type": "questions", "mapped_object": False})
    out["metadata"] = md
    return out


def _normalize_research_plan(raw: Any) -> dict[str, Any]:
    r = raw if isinstance(raw, dict) else {}
    complexity = _clean_text(r.get("complexity") or "standard")
    if complexity not in COMPLEXITY_LEVELS:
        complexity = "standard"
    est = r.get("estimated_minutes")
    try:
        est = round(float(est), 1) if est not in (None, "") else None
    except Exception:
        est = None
    non_objects = []
    for x in r.get("non_object_measures") or []:
        if isinstance(x, dict):
            name = _clean_text(x.get("name"))
            if name:
                non_objects.append({
                    "name": name,
                    "reason": _clean_text(x.get("reason")),
                    "question_type": _clean_text(x.get("question_type")),
                })
        elif _clean_text(x):
            non_objects.append({"name": _clean_text(x), "reason": "", "question_type": ""})
    return {
        "status": _clean_text(r.get("status") or "draft"),
        "problem_summary": _clean_text(r.get("problem_summary")),
        "objectives": [_clean_text(x) for x in (r.get("objectives") or []) if _clean_text(x)][:12],
        "research_questions": [_clean_text(x) for x in (r.get("research_questions") or []) if _clean_text(x)][:8],
        "hypotheses": [_clean_text(x) for x in (r.get("hypotheses") or []) if _clean_text(x)][:12],
        "recommended_topics": [_clean_text(x) for x in (r.get("recommended_topics") or []) if _clean_text(x)][:16],
        "non_object_measures": non_objects[:20],
        "questions_for_user": [_clean_text(x) for x in (r.get("questions_for_user") or []) if _clean_text(x)][:10],
        "complexity": complexity,
        "estimated_minutes": est,
        "method_reason": _clean_text(r.get("method_reason")),
    }


def normalize_project(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = deepcopy(raw or {})
    _nmin, _nmax, _ndef = sample_size_bounds()
    p = empty_project(
        title=_clean_text(raw.get("title") or "Nový výzkum"),
        goal=_clean_text(raw.get("goal")),
        n=max(_nmin, min(_nmax, int(raw.get("n") or _ndef))),
    )
    p["decision_use"] = _clean_text(raw.get("decision_use"))
    st = _clean_text(raw.get("study_type") or "custom")
    p["study_type"] = st if st in STUDY_TYPES else "custom"
    p["study_config"] = dict(raw.get("study_config") or {})
    p["instrument_library"] = dict(raw.get("instrument_library") or p["instrument_library"])

    br = raw.get("briefing") if isinstance(raw.get("briefing"), dict) else {}
    p["briefing"] = {
        "product_description": _clean_text(br.get("product_description") or raw.get("product_description")),
        "situation": _clean_text(br.get("situation")),
        "what_is_known": _clean_text(br.get("what_is_known")),
        "constraints": _clean_text(br.get("constraints")),
        # 17.8.9 guided UX: multi-intent brief and source context are durable project state.
        "problem_type": _clean_text(br.get("problem_type")),
        "problem_types": [_clean_text(x) for x in (br.get("problem_types") or []) if _clean_text(x)][:8],
        "review_comments": _clean_text(br.get("review_comments")),
        "attachments": deepcopy(br.get("attachments") or [])[:20],
        "attachments_context": _clean_text(br.get("attachments_context")),
    }
    p["research_plan"] = _normalize_research_plan(raw.get("research_plan"))
    p["design_variants"] = [dict(x) for x in (raw.get("design_variants") or []) if isinstance(x,dict)][:3]
    p["selected_design_variant"] = _clean_text(raw.get("selected_design_variant") or "recommended")

    p["persona_mode"] = _clean_text(raw.get("persona_mode") or "calibrated")
    if p["persona_mode"] not in PERSONA_MODES:
        p["persona_mode"] = "calibrated"
    pdim = raw.get("persona_dimensions") if isinstance(raw.get("persona_dimensions"), dict) else {}
    p["persona_dimensions"] = {"approved": list(dict.fromkeys(_clean_text(x).lower() for x in (pdim.get("approved") or []) if _clean_text(x)))[:12]}
    p["requested_dimensions"] = [dict(x) for x in (raw.get("requested_dimensions") or []) if isinstance(x,dict)][:20]
    p["panel_mode"] = _clean_text(raw.get("panel_mode") or "standard").lower()
    if p["panel_mode"] not in {"standard","ai_panel"}: p["panel_mode"] = "standard"
    aip = raw.get("ai_panel_profile") if isinstance(raw.get("ai_panel_profile"), dict) else {}
    p["ai_panel_profile"] = dict(aip) if p["panel_mode"] == "ai_panel" else {}
    p["model"] = _clean_text(raw.get("model") or "sonnet")
    p["ui_state"] = dict(raw.get("ui_state") or p.get("ui_state") or {"questionnaire_path":"choose","audience_entry":"choose","persona_path":"choose"})
    p["research_context"] = bool(raw.get("research_context", True))
    _pre = raw.get("pre_research") if isinstance(raw.get("pre_research"), dict) else {}
    p["pre_research"] = dict(_pre)
    rp = raw.get("run_policy") if isinstance(raw.get("run_policy"), dict) else {}
    # Production runs are fail-closed on the explicitly selected provider. The
    # provider is part of the project for reproducibility, while Settings supplies
    # the default for newly created projects. Cross-provider fallback stays disabled.
    p["run_policy"] = {"provider": normalize_ai_provider(rp.get("provider") or get_ai_provider()),
                       "allow_provider_fallback": False}
    bg = raw.get("budget") if isinstance(raw.get("budget"), dict) else {}
    max_usd = bg.get("max_usd")
    try: max_usd = round(float(max_usd), 4) if max_usd not in (None, "") else None
    except Exception: max_usd = None
    if max_usd is not None and max_usd <= 0: max_usd = None
    try: warning_pct = max(1, min(99, int(bg.get("warning_pct") or 80)))
    except Exception: warning_pct = 80
    p["budget"] = {"max_usd": max_usd, "warning_pct": warning_pct}

    aud = raw.get("audience") or {}
    strategy = _clean_text(aud.get("strategy") or ("filters" if aud.get("filters") else "population"))
    if strategy not in AUDIENCE_STRATEGIES:
        strategy = "population"
    source_mode = _clean_text(aud.get("source_mode") or "population")
    if source_mode not in AUDIENCE_SOURCE_MODES:
        source_mode = "population"
    p["audience"] = {
        "source_mode": source_mode,
        "dataset_id": _clean_text(aud.get("dataset_id")),
        "dataset_name": _clean_text(aud.get("dataset_name") or ("ČR 18+" if source_mode == "population" else aud.get("description"))),
        "builtin_subpanel": _clean_text(aud.get("builtin_subpanel")) if source_mode == "population" else "",
        "strategy": strategy,
        "description": _clean_text(aud.get("description") or ("ČR 18+" if source_mode == "population" else aud.get("dataset_name"))),
        "filters": dict(aud.get("filters") or {}),
        "segment": dict(aud.get("segment") or {"mode": "none"}),
        "product_description": _clean_text(aud.get("product_description") or p["briefing"]["product_description"]),
        "success_definition": _clean_text(aud.get("success_definition")),
        "discovery_note": _clean_text(aud.get("discovery_note")),
        "subpanel_status": _clean_text(aud.get("subpanel_status")),
        "support_tier": _clean_text(aud.get("support_tier")),
        "support_summary": dict(aud.get("support_summary") or {}),
        "audience_recommendation": dict(aud.get("audience_recommendation") or {}),
        "customer_kind": _clean_text(aud.get("customer_kind") or ""),
        "employee_industry": _clean_text(aud.get("employee_industry") or ""),
        "employee_positions": _clean_text(aud.get("employee_positions") or ""),
        "special_catalog_key": _clean_text(aud.get("special_catalog_key") or ""),
    }
    if not p["audience"]["segment"]:
        p["audience"]["segment"] = {"mode": "none"}

    sections = []
    section_ids: set[str] = set()
    question_ids: set[str] = set()
    for i, sec in enumerate(raw.get("sections") or [], start=1):
        if not isinstance(sec, dict):
            continue
        st = _clean_text(sec.get("type") or "questions")
        if st not in SECTION_TYPES:
            continue
        sid = _unique_id(_clean_text(sec.get("id") or sec.get("title") or f"sekce_{i}"), section_ids, "sec")
        title = _clean_text(sec.get("title") or ("Sledovaná sada" if st == "object_battery" else f"Blok {i}"))
        purpose = _clean_text(sec.get("purpose"))
        if st == "questions":
            qs = []
            for qi, q in enumerate(sec.get("questions") or [], start=1):
                qs.append(_normalize_question(q, section_id=sid, used=question_ids, ordinal=qi))
            sections.append({"id": sid, "type": st, "title": title, "purpose": purpose, "questions": qs})
            continue

        # object_family is kept as the backend/canonical field. object_type is accepted as a UI alias.
        family = _clean_text(sec.get("object_family") or sec.get("object_type"))
        objects = list(dict.fromkeys(_clean_text(x) for x in (sec.get("objects") or []) if _clean_text(x)))
        if not family:
            raise ValueError(f"{title}: pojmenuj typ sledovaných položek (např. média, emoce, značky, vztahy).")
        output_type = _clean_text(sec.get("output_type") or "pozicni_mapa")
        if output_type not in {"pozicni_mapa", "segmentace", "lovebrand", "test_konceptu"}:
            output_type = "pozicni_mapa"
        hard_min, hard_max, _recommended = tracked_set_limits(output_type)
        if not hard_min <= len(objects) <= hard_max:
            raise ValueError(f"{title}: tento typ výstupu potřebuje {hard_min}–{hard_max} srovnatelných položek stejného typu.")
        # Familiarity is an explicit research-design choice. It is NOT inferred from the word "attribute".
        fam_req = bool(sec.get("familiarity_required", False))
        oq = _clean_text(sec.get("object_question") or "Jak hodnotíte položku {object}?")
        if "{object}" not in oq:
            oq = oq.rstrip(" ?") + " {object}?"
        labs = [_clean_text(x) for x in (sec.get("scale_labels") or ["vůbec", "velmi"])][:2]
        if len(labs) != 2 or not all(labs):
            labs = ["vůbec", "velmi"]
        metadata = dict(sec.get("metadata") or {})
        metadata.setdefault("tracked_set", True)
        metadata.setdefault("object_type", family)
        _set_warning = tracked_set_warning(len(objects), output_type)
        if _set_warning:
            metadata.setdefault("design_warning", _set_warning)
        spec_dict = {
            "name": title,
            "research_question": purpose or p["goal"] or f"Jak respondenti hodnotí položky typu {family}?",
            "output_type": output_type,
            "objects": [{"label": x, "family": family} for x in objects],
            "object_family": family,
            "object_question": oq,
            "object_scale_labels": tuple(labs),
            "familiarity_required": fam_req,
            "characteristics": [],
            "n": p["n"],
            "metadata": metadata,
        }
        try:
            StudySpec(**spec_dict)
        except ValueError as exc:
            if output_type != "test_konceptu" or "price_bands" not in str(exc):
                raise
        sections.append({
            "id": sid, "type": st, "title": title, "purpose": purpose,
            "object_family": family, "object_type": family, "objects": objects, "object_question": oq,
            "scale_labels": labs, "familiarity_required": fam_req,
            "output_type": output_type, "visualize": bool(sec.get("visualize", True)),
            "metadata": metadata,
        })

    p["sections"] = sections
    disc = raw.get("discovery") or {}
    p["discovery"] = {
        "enabled": bool(disc.get("enabled", False)),
        "question_id": _clean_text(disc.get("question_id")),
        "positive_answers": [_clean_text(x) for x in (disc.get("positive_answers") or []) if _clean_text(x)],
        "min_positive": max(10, int(disc.get("min_positive") or 20)),
    }
    p["notes"] = [_clean_text(x) for x in (raw.get("notes") or []) if _clean_text(x)][:30]
    return p


def _prefixed_battery_questions(section: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sid = section["id"]
    spec = StudySpec(
        name=section["title"],
        research_question=section.get("purpose") or f"Jak respondenti hodnotí {section['object_family']}?",
        output_type=section.get("output_type") or "pozicni_mapa",
        objects=[{"label": x, "family": section["object_family"]} for x in section["objects"]],
        object_family=section["object_family"],
        object_question=section["object_question"],
        object_scale_labels=tuple(section["scale_labels"]),
        familiarity_required=section["familiarity_required"],
        characteristics=[],
        metadata=section.get("metadata") or {},
    )
    compiled = []
    mapping = {"fam": {}, "obj": {}}
    for q in spec.questionnaire():
        q = deepcopy(q)
        old = q["id"]
        new = f"{sid}_{old}"
        if q.get("filtr"):
            q["filtr"] = re.sub(r"\bfam_([A-Za-z0-9_]+)\b", rf"{sid}_fam_\1", q["filtr"])
        q["id"] = new
        md = dict(q.get("metadata") or {})
        md.update({
            "research_section": sid,
            "research_section_type": "object_battery",
            "battery_id": sid,
            "mapped_object": old.startswith("obj_"),
            "object_type": section["object_family"],
        })
        q["metadata"] = md
        compiled.append(q)
        if old.startswith("fam_"):
            mapping["fam"][old[4:]] = new
        if old.startswith("obj_"):
            mapping["obj"][old[4:]] = new
    meta = {"section": section, "mapping": mapping, "spec": spec.to_dict()}
    return compiled, meta


def compile_project(raw: dict[str, Any]) -> dict[str, Any]:
    p = normalize_project(raw)
    from instrument_library import missing_slots
    missing = missing_slots(str(p.get("study_type") or "custom"), dict(p.get("study_config") or {}))
    if missing:
        raise ValueError("Chybí povinné vstupy pro tento typ studie: " + ", ".join(missing) + ". Doplňte je v kroku Návrh výzkumu.")
    questions: list[dict[str, Any]] = []
    batteries: list[dict[str, Any]] = []
    for sec in p["sections"]:
        if sec["type"] == "questions":
            questions.extend(deepcopy(sec["questions"]))
        else:
            q, meta = _prefixed_battery_questions(sec)
            questions.extend(q)
            batteries.append(meta)
    if not questions:
        raise ValueError("Dotazník je prázdný. Přidej alespoň jednu otázku nebo sledovanou sadu.")
    cleaned = validate_standard_brief({"nazev": p["title"], "otazky": questions})["otazky"]
    brief = {
        "nazev": p["title"], "n": p["n"], "mode": "dry", "seed": 42,
        "model": resolve_provider_model(p["run_policy"]["provider"], p.get("model") or "sonnet"), "response_mode": "probability",
        "persona_mode": p["persona_mode"], "persona_topic_allowlist": list(p.get("persona_dimensions",{}).get("approved") or []), "filtry": p["audience"]["filters"],
        "panel_mode": p.get("panel_mode","standard"), "ai_panel_profile": deepcopy(p.get("ai_panel_profile") or {}),
        "audience_source": {"mode": p["audience"].get("source_mode","population"),
                            "dataset_id": p["audience"].get("dataset_id",""),
                            "dataset_name": p["audience"].get("dataset_name",""),
                            "builtin_subpanel": p["audience"].get("builtin_subpanel",""),
                            "support_tier": p["audience"].get("support_tier",""),
                            "subpanel_status": p["audience"].get("subpanel_status","")},
        "study_type": p.get("study_type","custom"),
        "study_config": deepcopy(p.get("study_config") or {}),
        "segment": p["audience"]["segment"], "otazky": cleaned,
        "research_context": {"enabled": p["research_context"]},
        "use_case": "internal", "allow_own_estimates": False,
        "provider_policy": "strict_" + p["run_policy"]["provider"],
        "budget": deepcopy(p["budget"]),
        "discovery": deepcopy(p["discovery"]),
        "_research_project": {"schema_version": 3, "section_ids": [s["id"] for s in p["sections"]]},
    }
    return {"project": p, "brief": brief, "batteries": batteries}


def classify_items(raw: dict[str, Any]) -> dict[str, Any]:
    """Explain what is and is not a mapped object in the current project."""
    p = normalize_project(raw)
    tracked = []
    non_objects = []
    for sec in p["sections"]:
        if sec["type"] == "object_battery":
            tracked.append({
                "id": sec["id"], "title": sec["title"], "object_type": sec["object_family"],
                "objects": list(sec["objects"]), "question": sec["object_question"],
                "visualize": bool(sec.get("visualize", True)),
            })
        else:
            for q in sec.get("questions") or []:
                non_objects.append({"id": q["id"], "text": q["text"], "reason": "samostatná otázka / outcome, ne položka společné mapovací škály"})
    for x in p.get("research_plan", {}).get("non_object_measures") or []:
        if x.get("name") and not any(y["text"] == x["name"] for y in non_objects):
            non_objects.append({"id": "", "text": x["name"], "reason": x.get("reason") or "nemá být mapováno jako objekt"})
    return {"tracked_sets": tracked, "non_objects": non_objects}


def project_stats(raw: dict[str, Any]) -> dict[str, Any]:
    c = compile_project(raw)
    p = c["project"]
    return {
        "sections": len(p["sections"]),
        "ordinary_questions": sum(len(s.get("questions") or []) for s in p["sections"] if s["type"] == "questions"),
        "object_batteries": sum(1 for s in p["sections"] if s["type"] == "object_battery"),
        "tracked_sets": sum(1 for s in p["sections"] if s["type"] == "object_battery"),
        "mapped_items": sum(len(s.get("objects") or []) for s in p["sections"] if s["type"] == "object_battery"),
        "compiled_questions": len(c["brief"]["otazky"]),
        "n": p["n"],
        "study_type": p.get("study_type","custom"),
        "audience_source_mode": p.get("audience",{}).get("source_mode","population"),
        "audience_dataset_id": p.get("audience",{}).get("dataset_id",""),
        "persona_mode": p["persona_mode"],
        "model": c["brief"]["model"],
    }
