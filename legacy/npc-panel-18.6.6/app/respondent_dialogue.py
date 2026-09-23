"""Grounded + explicitly simulated dialogue with NPC respondents and segments.

The default path is local/deterministic and answers only from the selected
respondent rows.  The optional simulation path is a separate epistemic mode:
it may use the selected AI provider, is fail-closed, and is always labelled as
an extension beyond measured answers.
"""
from __future__ import annotations

import json, math, re, unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

CONTRACT_VERSION = "18.6.6-respondent-dialogue-v1"
MODES = {"grounded", "simulated"}
TARGETS = {"respondent", "segment"}
_SIM_WARNING = (
    "SIMULACE NAD RÁMEC NAMĚŘENÝCH ODPOVĚDÍ. Tato formulace není skutečná "
    "odpověď respondenta ani doslovný výrok členů segmentu; jde o modelovou "
    "extrapolaci konzistentní s dostupnými daty."
)


def _safe(v: Any) -> Any:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v.item() if hasattr(v, "item") else v


def _norm(x: Any) -> str:
    s = unicodedata.normalize("NFKD", str(x or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _label(col: str) -> str:
    try:
        from visualization_lab import _label as lab
        return lab(str(col))
    except Exception:
        x = str(col)
        for p in ("obj_", "q_", "dem_", "att_", "beh_", "bin_"):
            if x.startswith(p):
                x = x[len(p):]
        return x.replace("_", " ").strip().capitalize()


def _rid(row: pd.Series, pos: int) -> str:
    try:
        from visualization_lab import _id_value
        return _id_value(row, pos)
    except Exception:
        for c in ("respondent_id", "panel_row_id", "id", "ID"):
            if c in row.index and pd.notna(row[c]):
                return str(row[c])
        return f"R{pos+1:05d}"


def _load_file(path: Path) -> pd.DataFrame:
    from visualization_lab import load_respondent_file
    return load_respondent_file(path)


def load_rows(candidate_paths: list[tuple[Path, str]], respondent_ids: list[str] | None = None) -> dict[str, Any]:
    """Load the first map-compatible respondent source and resolve requested ids."""
    wanted = {str(x) for x in (respondent_ids or [])}
    errors: list[str] = []
    for raw_path, source in candidate_paths:
        p = Path(raw_path)
        try:
            df = _load_file(p)
            if df is None or df.empty:
                continue
            ids = [_rid(row, i) for i, (_, row) in enumerate(df.iterrows())]
            work = df.copy()
            work.insert(0, "__npc_dialogue_id", ids)
            if wanted:
                selected = work[work["__npc_dialogue_id"].astype(str).isin(wanted)].copy()
                if selected.empty:
                    continue
            else:
                selected = work
            return {"df": work, "selected": selected, "source": source, "source_file": p.name}
        except Exception as exc:
            errors.append(f"{p.name}: {exc}")
    raise ValueError("Respondentní data pro dialog nejsou dostupná. " + " | ".join(errors[:4]))


def _fields_from_row(row: pd.Series) -> list[dict[str, Any]]:
    out = []
    for col in row.index:
        if col == "__npc_dialogue_id":
            continue
        val = _safe(row[col])
        if val is None or (isinstance(val, str) and not val.strip()):
            continue
        out.append({"key": str(col), "label": _label(str(col)), "value": val, "measured": True})
    return out


def _query_tokens(q: str) -> list[str]:
    stop = {"proc", "proč", "jsi", "jste", "tak", "takhle", "hodnotil", "hodnotila", "hodnotite", "vysoko", "nizko", "nízko", "co", "si", "myslis", "myslíš", "o", "na", "jak", "je", "to", "ten", "ta", "tohle", "moc", "velmi", "segment", "skupina"}
    return [x for x in _norm(q).split() if len(x) >= 3 and x not in {_norm(s) for s in stop}]


def _field_score(question: str, field: dict[str, Any]) -> float:
    q = _norm(question)
    lab = _norm(field["label"])
    key = _norm(field["key"])
    if lab and lab in q:
        return 100.0 + len(lab)
    if key and key in q:
        return 90.0 + len(key)
    toks = _query_tokens(question)
    score = 0.0
    for t in toks:
        if t in lab or t in key:
            score += 12.0
        else:
            lt = set(lab.split()) | set(key.split())
            if any(x.startswith(t) or t.startswith(x) for x in lt if len(x) >= 3):
                score += 5.0
    return score


def _matched_fields(question: str, fields: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    scored = [(round(_field_score(question, f), 4), f) for f in fields]
    scored.sort(key=lambda x: (-x[0], x[1]["label"]))
    positive = [dict(f, match_score=s) for s, f in scored if s > 0]
    return positive[:limit]


def _num(v: Any) -> float | None:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _why_question(q: str) -> bool:
    n = _norm(q)
    return any(x in n.split() for x in ("proc", "duvod", "důvod", "motiv")) or n.startswith("why ")


def _related_row_evidence(fields: list[dict[str, Any]], matched: list[dict[str, Any]], sample_df: pd.DataFrame | None = None, limit: int = 5) -> list[dict[str, Any]]:
    matched_keys = {x["key"] for x in matched}
    if sample_df is not None and matched and matched[0]["key"] in sample_df.columns:
        target_col = matched[0]["key"]
        y = pd.to_numeric(sample_df[target_col], errors="coerce")
        by_key = {f["key"]: f for f in fields}
        corr_rows = []
        if y.notna().sum() >= 8 and float(y.std()) > 1e-12:
            for c in sample_df.columns:
                if str(c) in matched_keys or str(c) == "__npc_dialogue_id" or str(c) not in by_key:
                    continue
                x = pd.to_numeric(sample_df[c], errors="coerce")
                ok = x.notna() & y.notna()
                if int(ok.sum()) < 8 or float(x[ok].std()) < 1e-12:
                    continue
                r = float(np.corrcoef(x[ok], y[ok])[0, 1])
                if math.isfinite(r):
                    corr_rows.append((abs(r), r, by_key[str(c)]))
            corr_rows.sort(key=lambda z: (-z[0], z[2]["label"]))
            return [dict(f, relation="sample_association", r=round(r, 4), n=int((pd.to_numeric(sample_df[f["key"]], errors="coerce").notna() & y.notna()).sum())) for _, r, f in corr_rows[:limit]]
    # Fallback when there is no numeric target/sample context: use salient measured values only.
    target = _num(matched[0]["value"]) if matched else None
    numeric = []
    for f in fields:
        if f["key"] in matched_keys:
            continue
        x = _num(f["value"])
        if x is None:
            continue
        sal = 0.0
        if 0 <= x <= 10.5:
            sal = abs(x - 5.5)
        elif 0 <= x <= 100:
            sal = abs(x - 50.0) / 10.0
        if target is not None and 0 <= target <= 10.5 and 0 <= x <= 10.5:
            sal += 2.0 if ((target >= 7 and x >= 7) or (target <= 4 and x <= 4)) else 0.0
        numeric.append((sal, f))
    numeric.sort(key=lambda x: (-x[0], x[1]["label"]))
    return [dict(f, relation="measured_context") for score, f in numeric[:limit] if score > 0]


def grounded_respondent(row: pd.Series, question: str, *, sample_df: pd.DataFrame | None = None) -> dict[str, Any]:
    fields = _fields_from_row(row)
    matched = _matched_fields(question, fields)
    related = _related_row_evidence(fields, matched, sample_df=sample_df)
    rid = str(row.get("__npc_dialogue_id") or "respondent")
    why = _why_question(question)
    lines: list[str] = []
    evidence: list[dict[str, Any]] = []
    if matched:
        first = matched[0]
        lines.append(f"V uložených odpovědích respondenta {rid} je **{first['label']} = {first['value']}**.")
        evidence.append({"type": "direct_response", "label": first["label"], "value": first["value"], "source_column": first["key"]})
        for f in matched[1:3]:
            evidence.append({"type": "direct_response", "label": f["label"], "value": f["value"], "source_column": f["key"]})
        if sample_df is not None:
            key = first["key"]
            if key in sample_df.columns:
                s = pd.to_numeric(sample_df[key], errors="coerce")
                xv = _num(first["value"])
                if xv is not None and s.notna().any():
                    mean = float(s.mean())
                    rank = float((s <= xv).mean() * 100.0)
                    lines.append(f"Pro kontext: průměr ve vzorku je {mean:.2f}; tato hodnota je přibližně na {rank:.0f}. percentilu vzorku.")
                    evidence.append({"type": "sample_context", "label": f"Průměr · {first['label']}", "value": round(mean, 3), "n": int(s.notna().sum())})
    else:
        lines.append("V uloženém řádku nevidím otázku/položku, kterou lze spolehlivě spojit s tímto dotazem.")
    if related:
        parts = [f"{f['label']} = {f['value']}" + (f" (ve vzorku r={f['r']:.2f})" if f.get('r') is not None else "") for f in related[:4]]
        lines.append("Další naměřený kontext stejného respondenta: " + "; ".join(parts) + ".")
        evidence.extend({"type": "sample_association_not_causation" if f.get("r") is not None else "measured_context", "label": f["label"], "value": f["value"], "source_column": f["key"], **({"r": f["r"], "n": f.get("n")} if f.get("r") is not None else {})} for f in related[:4])
    if why:
        lines.append("**Skutečný důvod ale z těchto dat nemohu tvrdit**, pokud nebyl přímo položen jako otevřená/explicitní otázka. Výše jsou doložené odpovědi a souvislosti, ne vymyšlený motiv.")
    elif not matched:
        lines.append("Mohu odpovídat jen z fyzicky uložených odpovědí; pro hypotetické pokračování přepněte na režim „Simulovat nad rámec“.")
    return {"answer": " ".join(lines), "evidence": evidence[:10], "epistemic_status": "MEASURED_ONLY", "warning": None,
            "target": {"type": "respondent", "respondent_id": rid}, "can_simulate": True}


def _aggregate_field(df: pd.DataFrame, col: str) -> dict[str, Any]:
    raw = df[col]
    num = pd.to_numeric(raw, errors="coerce")
    if num.notna().sum() >= max(3, int(len(df) * 0.25)):
        vals = num.dropna()
        out = {"kind": "numeric", "n": int(len(vals)), "mean": round(float(vals.mean()), 4), "median": round(float(vals.median()), 4),
               "min": round(float(vals.min()), 4), "max": round(float(vals.max()), 4)}
        if float(vals.min()) >= 0 and float(vals.max()) <= 10.5:
            out["share_8plus"] = round(float((vals >= 8).mean()), 4)
            out["share_3minus"] = round(float((vals <= 3).mean()), 4)
        return out
    vc = raw.dropna().astype(str).value_counts().head(6)
    return {"kind": "categorical", "n": int(raw.notna().sum()), "top": [{"value": k, "count": int(v), "share": round(int(v) / max(1, int(raw.notna().sum())), 4)} for k, v in vc.items()]}


def _segment_match_fields(question: str, df: pd.DataFrame) -> list[str]:
    fields = [{"key": str(c), "label": _label(str(c)), "value": ""} for c in df.columns if c != "__npc_dialogue_id"]
    matched = _matched_fields(question, fields, limit=8)
    structural = {"respondent_id", "panel_row_id", "id", "ID", "segment", "persona"}
    substantive = [x for x in matched if x["key"] not in structural and not str(x["key"]).startswith("dem_")]
    chosen = substantive if substantive else matched
    return [x["key"] for x in chosen[:4]]


def _segment_related(df: pd.DataFrame, target_col: str, limit: int = 4) -> list[dict[str, Any]]:
    y = pd.to_numeric(df[target_col], errors="coerce")
    if y.notna().sum() < 5:
        return []
    rows = []
    for c in df.columns:
        if c in {target_col, "__npc_dialogue_id"}:
            continue
        x = pd.to_numeric(df[c], errors="coerce")
        ok = x.notna() & y.notna()
        if int(ok.sum()) < 5 or float(x[ok].std()) < 1e-12 or float(y[ok].std()) < 1e-12:
            continue
        r = float(np.corrcoef(x[ok], y[ok])[0, 1])
        if math.isfinite(r):
            rows.append({"label": _label(str(c)), "source_column": str(c), "r": round(r, 4), "n": int(ok.sum())})
    rows.sort(key=lambda x: (-abs(x["r"]), x["label"]))
    return rows[:limit]


def grounded_segment(selected: pd.DataFrame, question: str, *, all_df: pd.DataFrame | None = None, label: str = "Vybraný segment") -> dict[str, Any]:
    n = len(selected)
    cols = _segment_match_fields(question, selected)
    evidence: list[dict[str, Any]] = []
    lines = [f"Odpovídám za **{label} (N={n})** pouze z naměřených řádků v tomto segmentu."]
    why = _why_question(question)
    if cols:
        for c in cols[:2]:
            agg = _aggregate_field(selected, c)
            lab = _label(c)
            if agg["kind"] == "numeric":
                text = f"{lab}: průměr {agg['mean']:.2f}, medián {agg['median']:.2f}, N={agg['n']}"
                if "share_8plus" in agg:
                    text += f", {100*agg['share_8plus']:.1f} % má hodnotu ≥8"
                if all_df is not None and c in all_df.columns:
                    rest = all_df[~all_df["__npc_dialogue_id"].astype(str).isin(set(selected["__npc_dialogue_id"].astype(str)))]
                    rn = pd.to_numeric(rest[c], errors="coerce")
                    if rn.notna().any():
                        text += f"; mimo segment je průměr {float(rn.mean()):.2f}"
                lines.append(text + ".")
            else:
                top = ", ".join(f"{x['value']} {100*x['share']:.1f} %" for x in agg["top"][:4])
                lines.append(f"{lab}: {top}.")
            evidence.append({"type": "segment_statistic", "label": lab, "source_column": c, **agg})
        rel = _segment_related(selected, cols[0]) if why else []
        if rel:
            lines.append("Nejsilnější měřené asociace s touto položkou v segmentu: " + "; ".join(f"{x['label']} r={x['r']:.2f}" for x in rel) + ".")
            evidence.extend({"type": "association_not_causation", **x} for x in rel)
    else:
        lines.append("V dotazu se nepodařilo spolehlivě určit konkrétní uloženou proměnnou. Můžu pracovat s přesněji pojmenovanou otázkou/objektem.")
    if why:
        lines.append("**Tyto asociace nejsou důvod ani kauzalita.** Pokud dotazník přímo nezjišťoval motiv, grounded režim ho nedopočítává.")
    return {"answer": " ".join(lines), "evidence": evidence[:12], "epistemic_status": "MEASURED_SEGMENT_ONLY", "warning": None,
            "target": {"type": "segment", "label": label, "n": n}, "can_simulate": True}


def _privacy_minimized_context(result: dict[str, Any]) -> dict[str, Any]:
    """Only aggregate/evidence snippets go to the provider, never the raw row/file."""
    return {"target": result.get("target"), "grounded_answer": result.get("answer"), "evidence": (result.get("evidence") or [])[:10],
            "epistemic_status": result.get("epistemic_status")}


def _sim_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {
        "answer": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "evidence_used": {"type": "array", "items": {"type": "string"}}
    }, "required": ["answer", "assumptions", "evidence_used"], "additionalProperties": False}


def simulate_extension(question: str, grounded: dict[str, Any], *, provider: str = "claude_code_subscription", model: str = "sonnet") -> dict[str, Any]:
    from ai_router import call_structured
    target = (grounded.get("target") or {}).get("type") or "respondent"
    if target == "respondent":
        role = "hypotetická odpověď tohoto syntetického respondenta"
    else:
        role = "syntetizovaná typická odpověď vybraného segmentu; nesmí tvrdit, že ji řekl každý člen"
    system = f"""Jsi NPC respondent dialogue simulator. Vytváříš {role}.
Použij pouze předaný MEASURED kontext jako kotvu. Nesmíš měnit ani popírat změřené hodnoty.
Cokoliv, co není přímo v evidence, je hypotetická extrapolace. Neuváděj ji jako fakt, reálný výrok nebo skutečně změřený motiv.
Nevymýšlej identitu, diagnózu, politickou příslušnost ani citlivý osobní údaj, který v kontextu není.
Odpověď napiš česky, přirozeně a stručně. U segmentu mluv jako syntéza typického postoje, ne jako jednomyslný segment."""
    payload = _privacy_minimized_context(grounded)
    rr = call_structured(system=system, messages=[{"role": "user", "content": json.dumps({"question": question, "measured_context": payload}, ensure_ascii=False)}],
                         schema=_sim_schema(), schema_name="npc_respondent_dialogue_simulation", anthropic_model=model or "sonnet",
                         openai_model=(model if provider == "openai" else None), max_tokens=900, prefer=provider or "claude_code_subscription",
                         allow_fallback=False, claude_interactive=True)
    data = rr.get("data") or {}
    return {"answer": str(data.get("answer") or ""), "assumptions": list(data.get("assumptions") or []), "evidence_used": list(data.get("evidence_used") or []),
            "evidence": grounded.get("evidence") or [], "epistemic_status": "SIMULATED_EXTENSION", "warning": _SIM_WARNING,
            "target": grounded.get("target"), "provider": rr.get("provider"), "model": rr.get("model"), "fallback_used": bool(rr.get("fallback_used")),
            "grounded_basis": grounded.get("answer"), "can_simulate": True}


def dialogue(*, candidate_paths: list[tuple[Path, str]], question: str, target_type: str, respondent_id: str | None = None,
             respondent_ids: list[str] | None = None, segment_label: str = "Vybraný segment", mode: str = "grounded",
             provider: str = "claude_code_subscription", model: str = "sonnet") -> dict[str, Any]:
    q = str(question or "").strip()
    if not q:
        raise ValueError("Napište otázku pro respondenta nebo segment.")
    tt = str(target_type or "respondent").strip().lower()
    md = str(mode or "grounded").strip().lower()
    if tt not in TARGETS:
        raise ValueError("target_type musí být respondent nebo segment")
    if md not in MODES:
        raise ValueError("mode musí být grounded nebo simulated")
    if tt == "respondent":
        rid = str(respondent_id or "").strip()
        if not rid:
            raise ValueError("Chybí respondent_id")
        loaded = load_rows(candidate_paths, [rid])
        row = loaded["selected"].iloc[0]
        base = grounded_respondent(row, q, sample_df=loaded["df"])
    else:
        ids = [str(x) for x in (respondent_ids or []) if str(x).strip()]
        if not ids:
            raise ValueError("Segment nemá žádné respondent_ids")
        if len(ids) > 10000:
            raise ValueError("Segment je příliš velký pro dialog (max 10 000 řádků).")
        loaded = load_rows(candidate_paths, ids)
        base = grounded_segment(loaded["selected"], q, all_df=loaded["df"], label=str(segment_label or "Vybraný segment"))
    base.update({"contract_version": CONTRACT_VERSION, "mode": "grounded", "source": loaded["source"], "source_file": loaded["source_file"],
                 "truth_contract": "Grounded mode uses only physically stored respondent rows. It does not invent motives or missing answers."})
    if md == "grounded":
        return base
    out = simulate_extension(q, base, provider=provider, model=model)
    out.update({"contract_version": CONTRACT_VERSION, "mode": "simulated", "source": loaded["source"], "source_file": loaded["source_file"],
                "truth_contract": "Simulation is explicitly separated from measured answers and never becomes observed truth, calibration evidence, or predictive validation."})
    return out
