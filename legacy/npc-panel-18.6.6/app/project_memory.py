"""Cross-project inspiration and retrieval for NPC Panel 17.9.1.

This is deliberately a *knowledge retrieval* layer, not a hidden project mutator.
It searches immutable project revisions and selected high-level artifacts, excludes
raw respondent data/attachments, and returns provenance-rich hits.  The optional
AI answer may synthesize only the retrieved hits; applying a past question/object
set remains an explicit UI action.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable
import hashlib, html, json, re, unicodedata

from project_store import ProjectStore

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "project_store.sqlite"

# Only high-level reusable knowledge is eligible. Never index respondent-level
# fieldwork, raw datasets, attachments, checkpoints or internal prompt material.
SAFE_ARTIFACT_PREFIXES = (
    "BRIEF", "DEEP_RESEARCH_SUMMARY", "RESEARCH_DESIGN", "QUESTIONNAIRE",
    "AUDIENCE", "DIMENSIONS", "SAMPLE_PLAN", "ANALYSIS_", "CLIENT_REPORT",
    "DELIVERY_MANIFEST", "SIMULATION_SPEC", "SIMULATION_RESEARCH",
    "WORLD_MODEL", "SCENARIO", "COMPARISON", "SIMULATION_REPORT",
)
BLOCKED_ARTIFACT_MARKERS = (
    "FIELDWORK", "RAW_", "RESPONDENT", "JOURNAL", "CHECKPOINT", "PARQUET",
    "INTERNAL_CSV", "ATTACHMENT", "PROMPT", "TRACE", "DIAGNOSTIC",
)


def _now_iso() -> str:
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _norm(s: Any) -> str:
    x = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii")
    x = re.sub(r"[^a-zA-Z0-9]+", " ", x.lower())
    return re.sub(r"\s+", " ", x).strip()


def _tokens(s: Any) -> list[str]:
    return [x for x in _norm(s).split() if len(x) >= 3]


def _loads(x: Any, default: Any) -> Any:
    try:
        return json.loads(x or "")
    except Exception:
        return default


def _clean_text(s: Any, limit: int = 2400) -> str:
    x = str(s or "")
    x = re.sub(r"<[^>]+>", " ", x)
    x = html.unescape(x)
    x = re.sub(r"\s+", " ", x).strip()
    return x[:limit]


def _entry_id(project_id: str, revision: int, kind: str, key: str, text: str) -> str:
    raw = f"{project_id}|{revision}|{kind}|{key}|{text}".encode("utf-8", "ignore")
    return "MEM-" + hashlib.sha256(raw).hexdigest()[:16]


@dataclass
class MemoryHit:
    memory_id: str
    project_id: str
    project_title: str
    project_type: str
    revision: int
    kind: str
    stage_type: str
    label: str
    text: str
    score: float
    created_at: str = ""
    payload: dict[str, Any] | None = None
    artifact_id: str | None = None
    same_project_history: bool = False

    def public(self) -> dict[str, Any]:
        d = asdict(self)
        d["payload"] = self.payload or {}
        d["score"] = round(float(self.score), 3)
        return d


def _question_text(q: dict[str, Any]) -> str:
    parts = [q.get("text") or ""]
    if q.get("kategorie"):
        parts.append("Odpovědi: " + ", ".join(map(str, q.get("kategorie") or [])))
    if q.get("popisky_skaly"):
        parts.append("Škála: " + " – ".join(map(str, q.get("popisky_skaly") or [])))
    return _clean_text(" | ".join(x for x in parts if x))


def _project_entries(row: Any, *, current_project_id: str | None = None, current_revision: int | None = None) -> Iterable[MemoryHit]:
    pid = str(row["project_id"]); rev = int(row["revision"] or 0)
    if current_project_id == pid and current_revision is not None and rev == int(current_revision):
        return []
    p = _loads(row["project_json"], {})
    title = str(row["title"] or p.get("title") or pid)
    ptype = str(row["project_type"] or "research")
    created = str(row["created_at"] or "")
    same = bool(current_project_id and current_project_id == pid)
    out: list[MemoryHit] = []

    def add(kind: str, stage: str, label: str, text: Any, payload: dict[str, Any] | None = None, key: str = ""):
        text2 = _clean_text(text)
        if not text2:
            return
        out.append(MemoryHit(
            memory_id=_entry_id(pid, rev, kind, key or label, text2), project_id=pid,
            project_title=title, project_type=ptype, revision=rev, kind=kind,
            stage_type=stage, label=str(label or kind), text=text2, score=0.0,
            created_at=created, payload=payload or {}, same_project_history=same,
        ))

    if ptype == "simulation":
        sim = p.get("simulation") or p
        add("project", "BRIEF", "Simulační projekt", " | ".join(map(str, [p.get("title") or "", sim.get("context") or sim.get("brief") or ""])), {"title": title})
        contract = p.get("scenario_contract") or sim.get("scenario_contract") or sim.get("change") or sim.get("scenario")
        if contract:
            add("scenario", "SCENARIO_CONTRACT", "Scénář / změna", json.dumps(contract, ensure_ascii=False) if isinstance(contract, (dict, list)) else contract, {"scenario": contract})
        for i, v in enumerate(sim.get("variants") or p.get("variants") or []):
            add("scenario_variant", "VARIANTS", f"Varianta {i+1}", json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v, {"variant": v}, str(i))
        return out

    # Project framing and research design.
    add("project", "BRIEF", "Zadání projektu", " | ".join(map(str, [p.get("goal") or "", p.get("decision_use") or "", (p.get("briefing") or {}).get("product_description") or "", (p.get("briefing") or {}).get("situation") or ""])), {"goal": p.get("goal"), "decision_use": p.get("decision_use")})
    plan = p.get("research_plan") or {}
    if plan:
        add("research_design", "RESEARCH_DESIGN", "Výzkumný návrh", json.dumps(plan, ensure_ascii=False), {"research_plan": plan})
    for i, rq in enumerate(plan.get("research_questions") or []):
        add("research_question", "RESEARCH_DESIGN", f"Výzkumná otázka {i+1}", rq if isinstance(rq, str) else json.dumps(rq, ensure_ascii=False), {"research_question": rq}, str(i))

    # Questionnaire and tracked object sets are the most important reusable memory.
    for si, sec in enumerate(p.get("sections") or []):
        if not isinstance(sec, dict):
            continue
        st = str(sec.get("type") or "questions")
        sec_title = str(sec.get("title") or f"Blok {si+1}")
        if st == "object_battery":
            objects = [str(x) for x in sec.get("objects") or []]
            text = f"{sec_title}. {sec.get('object_question') or ''}. Položky: {', '.join(objects)}"
            add("object_set", "QUESTIONNAIRE", sec_title, text, {"section": sec}, str(sec.get("id") or si))
        for qi, q in enumerate(sec.get("questions") or []):
            if not isinstance(q, dict):
                continue
            label = f"{sec_title} · otázka {qi+1}"
            add("question", "QUESTIONNAIRE", label, _question_text(q), {"question": q, "section_title": sec_title}, str(q.get("id") or f"{si}:{qi}"))

    audience = p.get("audience") or {}
    if audience:
        add("audience", "AUDIENCE", "Audience / cílová skupina", json.dumps(audience, ensure_ascii=False), {"audience": audience})
    dims = p.get("persona_dimensions") or []
    if dims:
        add("dimensions", "DIMENSIONS", "Dimenze", json.dumps(dims, ensure_ascii=False), {"persona_dimensions": dims})
    return out


def _artifact_is_safe(artifact_type: str) -> bool:
    t = str(artifact_type or "").upper()
    if any(x in t for x in BLOCKED_ARTIFACT_MARKERS):
        return False
    return any(t.startswith(x) for x in SAFE_ARTIFACT_PREFIXES)


def _artifact_entries(ps: ProjectStore, *, current_project_id: str | None = None, current_revision: int | None = None, max_rows: int = 250) -> Iterable[MemoryHit]:
    rows = ps.cx.execute(
        """SELECT a.*,p.title,p.project_type FROM project_artifacts a
           JOIN projects p ON p.project_id=a.project_id
           WHERE a.status='VALID' AND COALESCE(a.size_bytes,0)<=1000000
             AND COALESCE(a.is_current,1)=1
           ORDER BY a.created_at DESC LIMIT ?""", (int(max_rows),)
    ).fetchall()
    out: list[MemoryHit] = []
    for r in rows:
        if not _artifact_is_safe(r["artifact_type"]):
            continue
        pid = str(r["project_id"]); rev = int(r["revision"] or 0)
        if current_project_id == pid and current_revision is not None and rev == int(current_revision):
            continue
        fp = Path(str(r["path"] or ""))
        if not fp.is_file():
            continue
        try:
            if fp.suffix.lower() in {".json"}:
                obj = json.loads(fp.read_text(encoding="utf-8", errors="replace"))
                raw = json.dumps(obj, ensure_ascii=False)
            elif fp.suffix.lower() in {".txt", ".md", ".html", ".htm"}:
                raw = fp.read_text(encoding="utf-8", errors="replace")
            else:
                continue
        except Exception:
            continue
        text = _clean_text(raw, 3000)
        if not text:
            continue
        kind = "analysis" if str(r["artifact_type"]).upper().startswith("ANALYSIS_") else "artifact"
        if "REPORT" in str(r["artifact_type"]).upper(): kind = "report"
        mid = _entry_id(pid, rev, kind, str(r["artifact_id"]), text)
        out.append(MemoryHit(mid, pid, str(r["title"] or pid), str(r["project_type"] or "research"), rev,
                             kind, str(r["stage_type"] or ""), str(r["artifact_type"]), text, 0.0,
                             str(r["created_at"] or ""), {"artifact_type": r["artifact_type"]}, str(r["artifact_id"]),
                             bool(current_project_id and current_project_id == pid)))
    return out


def _demo_entries(*, current_project_id: str | None = None) -> Iterable[MemoryHit]:
    """Safe high-level memory from bundled read-only DEMOs.

    Raw respondent CSV/SQLite and attachments are deliberately never read.
    """
    try:
        from demo_showcase import catalog as demo_catalog, load as demo_load
    except Exception:
        return []
    out=[]
    for meta in demo_catalog():
        try:d=demo_load(meta['project_id'])
        except Exception:continue
        pid=str(meta['project_id']);rev=int(meta.get('revision') or 1);title=str(meta.get('title') or pid)
        def add(kind,stage,label,text,payload=None,key=''):
            text2=_clean_text(text)
            if not text2:return
            out.append(MemoryHit(_entry_id(pid,rev,kind,key or label,text2),pid,title,'research',rev,kind,stage,label,text2,0.0,'2026-08-24T20:16:00',payload or {},None,False))
        a=d.get('assignment') or {}
        add('project','BRIEF','DEMO zadání',' | '.join(str(x or '') for x in (a.get('client_need'),a.get('primary_decision'))),{'demo':True})
        for i,q in enumerate(a.get('questions') or []):add('research_question','RESEARCH_DESIGN',f'DEMO výzkumná otázka {i+1}',q,{'research_question':q,'demo':True},str(i))
        for i,q in enumerate(d.get('questionnaire') or []):
            if isinstance(q,dict):add('question','QUESTIONNAIRE',f'DEMO otázka {i+1}',_question_text(q),{'question':q,'demo':True},str(q.get('id') or i))
        aud=d.get('audience') or {}
        if aud:add('audience','AUDIENCE','DEMO audience',json.dumps(aud,ensure_ascii=False),{'audience':aud,'demo':True})
        ex=d.get('executive') or {}
        if ex:add('analysis','ANALYSIS','DEMO závěr',json.dumps(ex,ensure_ascii=False),{'demo':True})
        for i,w in enumerate(d.get('worlds') or []):
            if isinstance(w,dict):add('scenario_variant','WORLDS',f'DEMO svět {i+1}',json.dumps({k:w.get(k) for k in ('name','headline','assumption','winner','risk','implication') if w.get(k) is not None},ensure_ascii=False),{'demo':True,'world':w},str(i))
    return out


def _kind_hint(query: str) -> str | None:
    q = _norm(query)
    if any(x in q for x in ("otaz", "dotaznik", "formulac")): return "question"
    if any(x in q for x in ("objekt", "znack", "media", "atribut", "sada")): return "object_set"
    if any(x in q for x in ("audience", "cilov", "populac", "koho")): return "audience"
    if any(x in q for x in ("dimen", "persona", "psycholog")): return "dimensions"
    if any(x in q for x in ("scenar", "simul", "svet", "varianta")): return "scenario"
    if any(x in q for x in ("vysled", "zaver", "report", "analyz")): return "analysis"
    return None


def _score(query: str, h: MemoryHit, *, current_project_id: str | None = None) -> float:
    qn = _norm(query); doc = _norm(f"{h.project_title} {h.label} {h.text}")
    toks = _tokens(query)
    if not toks:
        base = 0.25
    else:
        present = sum(1 for t in set(toks) if t in doc)
        base = 4.0 * present / max(1, len(set(toks)))
        base += min(2.5, sum(doc.count(t) for t in set(toks)) * 0.18)
    if qn and len(qn) >= 5 and qn in doc: base += 5.0
    hint = _kind_hint(query)
    if hint:
        if h.kind == hint: base += 3.5
        elif hint == "analysis" and h.kind in {"analysis", "report"}: base += 3.0
        elif hint == "scenario" and h.kind in {"scenario", "scenario_variant"}: base += 3.0
    # Prefer other projects for "previous project" inspiration, while still allowing
    # older revisions of the current project to appear when genuinely relevant.
    if current_project_id and h.project_id == current_project_id:
        base -= 0.35
    # Question/object memory is intentionally slightly favored for reusable design.
    if h.kind == "question": base += 0.45
    if h.kind == "object_set": base += 0.30
    return base


def search(query: str, *, db_path: str | Path = DEFAULT_DB, current_project_id: str | None = None,
           current_revision: int | None = None, current_project: dict[str, Any] | None = None,
           limit: int = 12, kinds: list[str] | None = None) -> dict[str, Any]:
    q = str(query or "").strip()
    if not q:
        raise ValueError("Napište, co chcete v historii projektů najít.")
    db = Path(db_path)
    # Generic requests such as "jakou otázku jsme použili dřív" become much more
    # useful when the current goal is included as retrieval context.
    retrieval_q = q
    if current_project:
        goal = _clean_text(current_project.get("goal") or (current_project.get("briefing") or {}).get("product_description") or "", 500)
        if goal and len(_tokens(q)) <= 8:
            retrieval_q = q + " " + goal
    candidates: list[MemoryHit] = []; seen=set(); ps=None
    try:
        if db.exists():
            ps=ProjectStore(db)
            rows = ps.cx.execute(
                """SELECT r.project_id,r.revision,r.created_at,r.project_json,p.title,p.project_type,p.modified_at
                   FROM project_revisions r JOIN projects p ON p.project_id=r.project_id
                   ORDER BY p.modified_at DESC,r.revision DESC LIMIT 700"""
            ).fetchall()
            for row in rows:
                for h in _project_entries(row,current_project_id=current_project_id,current_revision=current_revision):
                    if kinds and h.kind not in kinds:continue
                    key=(h.project_id,h.kind,_norm(h.text))
                    if key in seen:continue
                    seen.add(key);candidates.append(h)
            for h in _artifact_entries(ps,current_project_id=current_project_id,current_revision=current_revision):
                if kinds and h.kind not in kinds:continue
                key=(h.project_id,h.kind,_norm(h.text))
                if key in seen:continue
                seen.add(key);candidates.append(h)
        for h in _demo_entries(current_project_id=current_project_id):
            if kinds and h.kind not in kinds:continue
            key=(h.project_id,h.kind,_norm(h.text))
            if key in seen:continue
            seen.add(key);candidates.append(h)
        for h in candidates:h.score=_score(retrieval_q,h,current_project_id=current_project_id)
        ranked=sorted(candidates,key=lambda x:(x.score,x.created_at),reverse=True)
        min_score=0.2 if _kind_hint(q) else 0.65
        hits=[x for x in ranked if x.score>=min_score][:max(1,min(40,int(limit)))]
        return {"query":q,"retrieval_query":retrieval_q,"hits":[h.public() for h in hits],"count":len(hits),
                "message":(f"Nalezeno {len(hits)} relevantních záznamů z historie projektů a DEMO knihovny." if hits else "V historii projektů ani DEMO knihovně jsem nenašel dostatečně podobný záznam."),"searched_at":_now_iso()}
    finally:
        if ps:ps.close()

def _answer_schema() -> dict[str, Any]:
    return {
        "type":"object","properties":{
            "answer":{"type":"string"},
            "source_ids":{"type":"array","items":{"type":"string"}},
            "follow_up_suggestions":{"type":"array","items":{"type":"string"}},
        },"required":["answer","source_ids","follow_up_suggestions"],"additionalProperties":False,
    }


ASSISTANT_SYSTEM = """Jsi AI asistent NPC Panelu. Pomáháš uživateli s aktuálním výzkumem a můžeš čerpat inspiraci z HISTORIE PROJEKTŮ, kterou dostaneš jako očíslované zdroje.

Pravidla:
- Historické zdroje jsou inspirace, ne automaticky správný vzor pro nový projekt.
- U každého konkrétního tvrzení o minulém projektu uveď v textu zdroj ve formátu [1], [2] podle pořadí RETRIEVED SOURCES.
- Nikdy netvrď, že se něco v projektu změnilo. Nic automaticky neupravuješ.
- Když doporučíš znovu použít otázku, vysvětli proč a zda ji má smysl upravit pro aktuální cílovku/rámování.
- Nepracuj s raw respondentními daty; ta nejsou do paměti vůbec předávána.
- Pokud zdroje odpověď nepodporují, řekni to.
- Odpovídej česky, stručně a prakticky.
"""


def answer(message: str, *, db_path: str | Path = DEFAULT_DB, current_project_id: str | None = None,
           current_revision: int | None = None, current_project: dict[str, Any] | None = None,
           history: list[dict[str, str]] | None = None, provider: str | None = None, model: str = "sonnet",
           limit: int = 12) -> dict[str, Any]:
    msg = str(message or "").strip()
    if not msg: raise ValueError("Napište AI asistentovi otázku.")
    found = search(msg, db_path=db_path, current_project_id=current_project_id, current_revision=current_revision,
                   current_project=current_project, limit=limit)
    hits = found.get("hits") or []
    if not hits:
        return {"answer":"V uložené historii zatím nemám dost podobný projekt nebo otázku. Můžu ale pracovat s aktuálním projektem a navrhnout nový postup.",
                "sources":[],"hits":[],"follow_up_suggestions":["Zkusit hledat podle konkrétního tématu nebo formulace otázky"],
                "_ai":{"used":False,"reason":"NO_RETRIEVED_SOURCES"}}
    source_lines=[]
    for i,h in enumerate(hits,1):
        source_lines.append(f"[{i}] id={h['memory_id']} | projekt={h['project_title']} | project_id={h['project_id']} | rev={h['revision']} | typ={h['kind']} | etapa={h['stage_type']} | label={h['label']}\n{h['text']}")
    current = {
        "title": (current_project or {}).get("title"), "goal": (current_project or {}).get("goal"),
        "decision_use": (current_project or {}).get("decision_use"), "audience": (current_project or {}).get("audience"),
    }
    safe_hist=[]
    for x in (history or [])[-8:]:
        role=str(x.get("role") or ""); content=str(x.get("content") or "").strip()
        if role in {"user","assistant"} and content: safe_hist.append({"role":role,"content":content[:2200]})
    user_context = "AKTUÁLNÍ PROJEKT:\n"+json.dumps(current,ensure_ascii=False,default=str)+"\n\nRETRIEVED SOURCES:\n"+"\n\n".join(source_lines)+"\n\nDOTAZ UŽIVATELE:\n"+msg
    try:
        from ai_router import call_structured
        from provider_auth import get_ai_provider, normalize_ai_provider
        selected=normalize_ai_provider(provider or ((current_project or {}).get("run_policy") or {}).get("provider") or get_ai_provider())
        rr=call_structured(system=ASSISTANT_SYSTEM,messages=safe_hist+[{"role":"user","content":user_context}],schema=_answer_schema(),schema_name="npc_project_memory_assistant",anthropic_model=model,max_tokens=1600,prefer=selected,openai_model=None,allow_fallback=False)
        data=rr.get("data") or {}
        valid_ids={h["memory_id"] for h in hits}
        selected_ids=[x for x in data.get("source_ids") or [] if x in valid_ids]
        sources=[h for h in hits if h["memory_id"] in selected_ids]
        if not sources: sources=hits[:5]
        return {"answer":str(data.get("answer") or ""),"sources":sources,"hits":hits,
                "follow_up_suggestions":[str(x) for x in data.get("follow_up_suggestions") or []][:5],
                "_ai":{"used":True,"provider":rr.get("provider") or selected,"model":rr.get("model") or model,"fallback_used":bool(rr.get("fallback_used")),"source_count":len(sources)}}
    except Exception as exc:
        # Retrieval must remain useful even when the interactive model is temporarily
        # unavailable. Do not invent a synthesized answer; surface the exact hits.
        from provider_diagnostics import explain_router_failure
        try: selected
        except NameError:
            from provider_auth import get_ai_provider, normalize_ai_provider
            selected=normalize_ai_provider(provider or get_ai_provider())
        diag=explain_router_failure(exc,provider=selected)
        return {"answer":f"Našel jsem {len(hits)} relevantních záznamů v historii. AI syntéza se teď nedokončila, ale zdroje níže můžete rovnou otevřít nebo znovu použít.",
                "sources":hits[:6],"hits":hits,"follow_up_suggestions":[],
                "_ai":{"used":False,"provider":selected,"failed":True,"kind":diag.get("kind"),"message":diag.get("message")}}
