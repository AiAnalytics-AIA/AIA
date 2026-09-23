"""Persistent registry for Customer / Special Audience datasets (NPC Panel 15).

An audience is a real row-level dataset supplied by the user. It is never silently
converted into the Czech population panel. Each registered audience carries a data
dictionary, provenance metadata, coverage profile and optional validation benchmarks.

Storage is intentionally transparent and portable:
  data/audiences/<audience_id>/audience.csv
  data/audiences/<audience_id>/metadata.json
  data/audiences/<audience_id>/variables.json
  data/audiences/<audience_id>/benchmarks.csv  (optional)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import re

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
AUDIENCE_ROOT = ROOT / "data" / "audiences"
AUDIENCE_ROOT.mkdir(parents=True, exist_ok=True)

AUDIENCE_TYPES = {"customer", "special_audience"}
STANDARD_ALIASES = {
    "age": "vek", "gender": "pohlavi", "sex": "pohlavi", "education": "vzdelani",
    "region": "kraj", "income": "prijem_cisty_mesicni", "weight": "vaha_kalibrovana",
    "id": "respondent_id", "case_id": "respondent_id",
}
RESERVED_INTERNAL = {"_zdroj_index", "_sample_poradi", "_inclusion_prob", "_analysis_weight", "_persona_zdroj_index"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slug(s: str) -> str:
    x = re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")
    return (x[:48] or "audience")


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for ch in iter(lambda: f.read(1024 * 1024), b""):
            h.update(ch)
    return h.hexdigest()


def _safe_value(x: Any) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    s = str(x).strip()
    return "" if s.lower() in {"nan", "none", "null"} else s


def _read_key_value_sheet(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {}
    cols = [str(c).strip().lower() for c in df.columns]
    if len(cols) >= 2 and cols[0] in {"field", "key", "pole", "klíč", "klic"}:
        return {_safe_value(r.iloc[0]): _safe_value(r.iloc[1]) for _, r in df.iterrows() if _safe_value(r.iloc[0])}
    if df.shape[1] >= 2:
        return {_safe_value(r.iloc[0]): _safe_value(r.iloc[1]) for _, r in df.iterrows() if _safe_value(r.iloc[0])}
    return {}


def _normalize_variables(var_df: pd.DataFrame | None, columns: list[str]) -> list[dict[str, Any]]:
    if var_df is None or var_df.empty:
        out = []
        for c in columns:
            out.append({
                "column": c, "label": c, "type": "auto",
                "role": "profile" if c in {"vek", "pohlavi", "vzdelani", "kraj", "role", "industry", "segment", "customer_status"} else "other",
                "block": "core", "persona_use": c in {"vek", "pohlavi", "vzdelani", "kraj", "role", "industry", "segment", "customer_status"},
                "measured_status": "MEASURED", "source": "uploaded_dataset", "reference_period": "",
            })
        return out
    lookup = {str(c).strip().lower(): c for c in var_df.columns}
    def val(row, *names, default=""):
        for n in names:
            c = lookup.get(n.lower())
            if c is not None:
                return _safe_value(row.get(c))
        return default
    out=[]
    seen=set()
    for _, row in var_df.iterrows():
        col = val(row, "column", "variable", "sloupec", "proměnná", "promenna")
        if not col or col not in columns or col in seen:
            continue
        seen.add(col)
        pu = val(row, "persona_use", "use_in_persona", "pouzit_v_persone", default="no").lower() in {"1","true","yes","ano","y"}
        out.append({
            "column": col,
            "label": val(row, "label", "popis", default=col) or col,
            "type": val(row, "type", "typ", default="auto") or "auto",
            "role": val(row, "role", "role_variable", "role_promenne", default="other") or "other",
            "block": val(row, "block", "blok", default="other") or "other",
            "persona_use": pu,
            "measured_status": val(row, "measured_status", "evidence", default="MEASURED") or "MEASURED",
            "source": val(row, "source", "zdroj", default="uploaded_dataset") or "uploaded_dataset",
            "reference_period": val(row, "reference_period", "obdobi", default=""),
            "categories": val(row, "categories", "kategorie", default=""),
            "missing_codes": val(row, "missing_codes", "chybejici_kody", default=""),
        })
    for c in columns:
        if c not in seen:
            out.append({"column": c, "label": c, "type": "auto", "role": "other", "block": "other",
                        "persona_use": False, "measured_status": "MEASURED", "source": "uploaded_dataset",
                        "reference_period": "", "categories": "", "missing_codes": ""})
    return out


def _persona_fact_text(row: pd.Series, variables: list[dict[str, Any]]) -> str:
    facts=[]
    for v in variables:
        if not v.get("persona_use"):
            continue
        col=v["column"]
        if col not in row.index:
            continue
        value=_safe_value(row.get(col))
        if not value:
            continue
        label=str(v.get("label") or col).strip()
        period=str(v.get("reference_period") or "").strip()
        suffix=f" [{period}]" if period else ""
        facts.append(f"{label}: {value}{suffix}")
        if len(facts) >= 16:
            break
    return "; ".join(facts)


def _normalize_frame(df: pd.DataFrame, variables: list[dict[str, Any]]) -> tuple[pd.DataFrame, list[str]]:
    df = df.copy()
    warnings=[]
    # Friendly aliases only when the canonical destination is absent.
    ren={}
    for c in list(df.columns):
        alias=STANDARD_ALIASES.get(str(c).strip().lower())
        if alias and alias not in df.columns:
            ren[c]=alias
    if ren:
        df=df.rename(columns=ren)
        # keep data-dictionary column names in sync
        for v in variables:
            if v["column"] in ren:
                v["column"] = ren[v["column"]]
    bad = [c for c in df.columns if str(c).startswith("_") and c in RESERVED_INTERNAL]
    if bad:
        raise ValueError("Upload obsahuje rezervované runtime sloupce: " + ", ".join(map(str,bad)))
    if len(df) < 20:
        raise ValueError("Audience musí mít alespoň 20 řádků; menší soubor není vhodný ani pro technický panelový běh.")
    if len(df) < 100:
        warnings.append("Audience má méně než 100 řádků; subgroup výsledky budou velmi nestabilní.")

    id_col=None
    for cand in ("respondent_id","panel_row_id","customer_id","employee_id"):
        if cand in df.columns:
            id_col=cand; break
    if id_col is None:
        df.insert(0,"respondent_id",[f"R{i+1:06d}" for i in range(len(df))])
        id_col="respondent_id"
        warnings.append("Chyběl respondent_id; systém vytvořil technické řádkové ID.")
    ids=df[id_col].astype(str).str.strip()
    if ids.eq("").any() or ids.duplicated().any():
        raise ValueError(f"Sloupec {id_col} musí být neprázdný a unikátní.")
    if "panel_row_id" not in df.columns:
        df["panel_row_id"]=["aud_"+hashlib.sha1(x.encode("utf-8")).hexdigest()[:16] for x in ids]

    if "vaha_kalibrovana" not in df.columns:
        for cand in ("vaha","weight","survey_weight"):
            if cand in df.columns:
                df["vaha_kalibrovana"]=pd.to_numeric(df[cand],errors="coerce")
                break
        else:
            df["vaha_kalibrovana"]=1.0
            warnings.append("Chyběla váha; audience používá rovnoměrnou váhu 1.0.")
    w=pd.to_numeric(df["vaha_kalibrovana"],errors="coerce")
    if w.isna().all() or float(w.fillna(0).sum()) <= 0 or (w.fillna(0)<0).any():
        raise ValueError("vaha_kalibrovana musí být nezáporná numerická proměnná s kladným součtem.")
    df["vaha_kalibrovana"]=w.fillna(0.0)

    # Pass-through measured facts for the LLM persona. This is deliberately one
    # generated text column, not another synthetic score layer.
    df["AUDIENCE_FACTS_TEXT"]=[_persona_fact_text(r,variables) for _,r in df.iterrows()]
    return df, warnings


def _coverage(df: pd.DataFrame, variables: list[dict[str, Any]]) -> dict[str, Any]:
    roles={}
    blocks={}
    persona=[]
    for v in variables:
        c=v["column"]
        if c not in df.columns: continue
        nonmissing=round(float(df[c].notna().mean()),4)
        item={"column":c,"label":v.get("label",c),"nonmissing_share":nonmissing,
              "measured_status":v.get("measured_status","MEASURED")}
        roles.setdefault(v.get("role","other"),[]).append(item)
        blocks.setdefault(v.get("block","other"),[]).append(item)
        if v.get("persona_use"):
            persona.append(item)
    return {"roles":roles,"blocks":blocks,"persona_fields":persona,
            "standard_demographics":[c for c in ("vek","pohlavi","vzdelani","kraj","prijem_cisty_mesicni") if c in df.columns]}


def import_audience_file(path: str | Path, *, filename: str | None = None,
                         audience_name: str | None = None,
                         audience_type: str = "special_audience",
                         description: str = "") -> dict[str, Any]:
    """Validate, normalize and persist a user-supplied audience CSV/XLSX."""
    p=Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    audience_type=str(audience_type or "special_audience").strip().lower()
    if audience_type not in AUDIENCE_TYPES:
        raise ValueError("audience_type musí být customer nebo special_audience")

    metadata={}
    variables_df=None
    benchmarks_df=None
    if p.suffix.lower() in {".xlsx",".xlsm"}:
        book=pd.ExcelFile(p)
        names={s.lower():s for s in book.sheet_names}
        resp_name=names.get("respondents") or names.get("respondenti") or book.sheet_names[0]
        df=pd.read_excel(p,sheet_name=resp_name)
        if "metadata" in names: metadata=_read_key_value_sheet(pd.read_excel(p,sheet_name=names["metadata"]))
        if "variables" in names: variables_df=pd.read_excel(p,sheet_name=names["variables"])
        elif "promenne" in names: variables_df=pd.read_excel(p,sheet_name=names["promenne"])
        if "benchmarks" in names: benchmarks_df=pd.read_excel(p,sheet_name=names["benchmarks"])
    elif p.suffix.lower()==".csv":
        df=pd.read_csv(p,low_memory=False)
    else:
        raise ValueError("Podporovaný upload je .xlsx nebo .csv")

    df.columns=[str(c).strip() for c in df.columns]
    variables=_normalize_variables(variables_df,list(df.columns))
    df,warnings=_normalize_frame(df,variables)
    # Metadata from explicit API wins over workbook fields.
    name=(audience_name or metadata.get("audience_name") or metadata.get("name") or p.stem).strip()
    desc=(description or metadata.get("description") or metadata.get("population_definition") or "").strip()
    aid_base=_slug(name)
    rawhash=_sha256_file(p)
    audience_id=f"{aid_base}-{rawhash[:8]}"
    dest=AUDIENCE_ROOT/audience_id
    dest.mkdir(parents=True,exist_ok=True)
    csvp=dest/"audience.csv"
    df.to_csv(csvp,index=False,encoding="utf-8-sig")

    meta={
        "schema_version":1,"audience_id":audience_id,"name":name,"type":audience_type,
        "description":desc,"population_definition":metadata.get("population_definition",desc),
        "unit_of_analysis":metadata.get("unit_of_analysis","person"),"country":metadata.get("country",""),
        "reference_date":metadata.get("reference_date",""),"source":metadata.get("source","uploaded_by_user"),
        "sampling_method":metadata.get("sampling_method",""),"weighting_method":metadata.get("weighting_method",""),
        "legal_basis_or_consent":metadata.get("legal_basis_or_consent",""),"owner":metadata.get("owner",""),
        "notes":metadata.get("notes",""),"created_at_utc":_utc_now(),"original_filename":filename or p.name,
        "source_sha256":rawhash,"rows":int(len(df)),"columns":int(len(df.columns)),"warnings":warnings,
        "coverage":_coverage(df,variables),"runtime_csv":str(csvp.relative_to(ROOT)).replace("\\","/"),
    }
    (dest/"metadata.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    (dest/"variables.json").write_text(json.dumps(variables,ensure_ascii=False,indent=2),encoding="utf-8")
    if benchmarks_df is not None and not benchmarks_df.empty:
        benchmarks_df.to_csv(dest/"benchmarks.csv",index=False,encoding="utf-8-sig")
    return meta


def list_audiences() -> list[dict[str, Any]]:
    out=[]
    for p in sorted(AUDIENCE_ROOT.glob("*/metadata.json")):
        try:
            m=json.loads(p.read_text(encoding="utf-8"))
            out.append(m)
        except Exception:
            continue
    return sorted(out,key=lambda x:str(x.get("created_at_utc") or ""),reverse=True)


def get_audience(audience_id: str) -> dict[str, Any]:
    # Exact id is safer than reconstructing a slug when the name itself has dashes.
    p=(AUDIENCE_ROOT/str(audience_id)/"metadata.json").resolve()
    if AUDIENCE_ROOT.resolve() not in p.parents or not p.is_file():
        raise KeyError(f"Neznámá audience: {audience_id}")
    return json.loads(p.read_text(encoding="utf-8"))


def load_audience_frame(audience_id: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    m=get_audience(audience_id)
    p=(ROOT/m["runtime_csv"]).resolve()
    if ROOT.resolve() not in p.parents or not p.is_file():
        raise FileNotFoundError(p)
    return pd.read_csv(p,low_memory=False),m


def delete_audience(audience_id: str) -> None:
    import shutil
    p=(AUDIENCE_ROOT/str(audience_id)).resolve()
    if AUDIENCE_ROOT.resolve() not in p.parents or not p.is_dir():
        raise KeyError(audience_id)
    shutil.rmtree(p)


def audience_preflight(audience_id: str, *, required_roles: list[str] | None = None,
                       required_columns: list[str] | None = None, n: int | None = None) -> dict[str, Any]:
    df,m=load_audience_frame(audience_id)
    vars_path=AUDIENCE_ROOT/audience_id/"variables.json"
    variables=json.loads(vars_path.read_text(encoding="utf-8")) if vars_path.is_file() else []
    by_role={}
    for v in variables:
        by_role.setdefault(v.get("role","other"),[]).append(v.get("column"))
    problems=[]; warnings=list(m.get("warnings") or [])
    for r in required_roles or []:
        if not any(c in df.columns for c in by_role.get(r,[])):
            problems.append(f"Audience nemá proměnnou role '{r}'.")
    for c in required_columns or []:
        if c not in df.columns:
            problems.append(f"Audience nemá požadovaný sloupec '{c}'.")
    if n and int(n)>len(df):
        problems.append(f"Požadované N={n} je větší než support audience ({len(df)}); sampling bez náhrady by nebyl možný.")
    w=pd.to_numeric(df.get("vaha_kalibrovana",pd.Series(1.0,index=df.index)),errors="coerce").fillna(0).clip(lower=0)
    ess=float((w.sum()**2)/(np.square(w).sum() or 1.0))
    if ess < 100:
        warnings.append(f"Efektivní velikost audience je nízká (ESS≈{ess:.0f}).")
    coverage=m.get("coverage",{}) or {}
    persona_fields=list(coverage.get("persona_fields") or [])
    if not persona_fields:
        warnings.append("Audience nemá žádné pole povolené pro personu (persona_use=yes); model nebude mít respondent-level profilový kontext.")
    if len(persona_fields)>16:
        warnings.append(f"Audience má {len(persona_fields)} persona_use polí; do jednoho promptu se propustí nejvýše 16 měřených faktů. Zvažte zúžení na rozhodovací signály.")
    sparse=[x for x in persona_fields if float(x.get("nonmissing_share") or 0)<0.5]
    if sparse:
        warnings.append("Více než polovině respondentů chybí některá persona_use pole: " + ", ".join(str(x.get("label") or x.get("column")) for x in sparse[:6]))
    facts=df.get("AUDIENCE_FACTS_TEXT",pd.Series("",index=df.index)).fillna("").astype(str)
    if persona_fields and facts.nunique(dropna=False)<=1:
        warnings.append("Profilový kontext je u všech řádků stejný; audience nebude mít respondent-level heterogenitu v personě.")
    return {"ok":not problems,"audience":m,"rows":len(df),"ess":round(ess,1),"problems":problems,"warnings":warnings,
            "columns":list(df.columns),"coverage":coverage,
            "profile_quality":{"persona_fields":len(persona_fields),"unique_fact_profiles":int(facts.nunique(dropna=False))}}
