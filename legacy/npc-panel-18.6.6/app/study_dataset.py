"""Převod detailního survey runu na standardizovaný dataset modulu VÝZKUM."""
from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from study_contract import StudySpec, slugify

DEMO_SOURCE_DEFAULTS = {
    "pohlavi": "dem_pohlavi", "vek": "dem_vek", "vzdelani": "dem_vzdelani",
    "kraj": "dem_kraj", "prijem_cisty_mesicni": "dem_prijem",
    "trida_spolecenska": "dem_trida",
}


def _encode_categories(s: pd.Series) -> tuple[pd.Series, dict[int, str]]:
    vals = [x for x in s.dropna().astype(str).unique().tolist()]
    vals = sorted(vals)
    mapping = {v: i + 1 for i, v in enumerate(vals)}
    out = s.map(lambda x: mapping.get(str(x)) if pd.notna(x) else np.nan)
    return out, {i: v for v, i in mapping.items()}


def build_study_dataset(run_result: dict[str, Any], spec: StudySpec) -> tuple[pd.DataFrame, list[dict[str, str]], dict[str, Any]]:
    detail: pd.DataFrame = run_result["detail"].copy()
    out = pd.DataFrame(index=detail.index)
    out["respondent_id"] = np.arange(1, len(detail) + 1)
    w = pd.to_numeric(detail.get("_analysis_weight", pd.Series(1.0, index=detail.index)), errors="coerce").fillna(1.0)
    out["vaha"] = w * (len(out) / float(w.sum() or 1.0))
    labels: list[dict[str, str]] = [
        {"var": "respondent_id", "lab": "Identifikátor syntetického respondenta", "values": ""},
        {"var": "vaha", "lab": "Analytická váha; součet = N", "values": ""},
    ]

    # Core demographics are profiling variables only; categorical text is encoded 1..k.
    for src, dst in DEMO_SOURCE_DEFAULTS.items():
        if src not in detail.columns:
            continue
        if src in {"vek", "prijem_cisty_mesicni"}:
            out[dst] = pd.to_numeric(detail[src], errors="coerce")
            labels.append({"var": dst, "lab": src.replace("_", " ").capitalize(), "values": "raw"})
        else:
            enc, mp = _encode_categories(detail[src])
            out[dst] = enc
            labels.append({"var": dst, "lab": src.replace("_", " ").capitalize(),
                           "values": "; ".join(f"{k} = {v}" for k, v in mp.items())})

    for obj in spec.objects:
        f, o = f"fam_{obj.slug}", f"obj_{obj.slug}"
        out[o] = pd.to_numeric(detail[o], errors="coerce") if o in detail else np.nan
        if spec.familiarity_required:
            if f in detail:
                out[f] = detail[f].map({"Neznám": 0, "Znám": 1}).astype("Int64")
            else:
                out[f] = pd.Series([pd.NA] * len(detail), dtype="Int64")
            out.loc[out[f].fillna(0).astype(int) == 0, o] = np.nan
            labels.append({"var": f, "lab": spec.familiarity_question.format(object=obj.label),
                           "values": "0 = neznám; 1 = znám"})
            missing_note = "; prázdné = fam=0"
        else:
            missing_note = "; prázdné = chybějící odpověď"
        labels.append({
            "var": o, "lab": spec.object_question.format(object=obj.label),
            "values": f"1 = {spec.object_scale_labels[0]} … 10 = {spec.object_scale_labels[1]}{missing_note}",
        })

    for c in spec.characteristics:
        var = c.variable
        if c.source_column:
            if c.source_column not in detail:
                continue
            s = detail[c.source_column]
        elif var in detail:
            s = detail[var]
        else:
            continue
        if c.kind in {"attitude", "nps", "frequency", "metric"}:
            out[var] = pd.to_numeric(s, errors="coerce")
            if c.kind in {"attitude","nps"}:
                rng=tuple(c.scale) if len(c.scale)==2 else ((0,10) if c.kind=="nps" else (1,10))
                domain=f"{rng[0]}–{rng[1]}"
            else:
                domain = "1–5" if c.kind == "frequency" else "raw"
            labels.append({"var": var, "lab": c.text, "values": domain})
        elif c.kind == "binary":
            if c.values:
                mp = {v: i for i, v in enumerate(c.values[:2])}
                out[var] = s.map(mp).astype("Int64")
                values_txt = "; ".join(f"{i} = {v}" for v, i in mp.items())
            else:
                vals=sorted(s.dropna().astype(str).unique().tolist())
                if len(vals)>2:
                    raise ValueError(f"{c.name}: binary source_column has more than two observed categories")
                mp={v:i for i,v in enumerate(vals)}
                out[var]=s.map(lambda x: mp.get(str(x)) if pd.notna(x) else pd.NA).astype("Int64")
                values_txt="; ".join(f"{i} = {v}" for v,i in mp.items())
            labels.append({"var": var, "lab": c.text, "values": values_txt})
        else:
            if c.values:
                mp = {v: i + 1 for i, v in enumerate(c.values)}
                out[var] = s.map(mp).astype("Int64")
                values_txt = "; ".join(f"{i} = {v}" for v, i in mp.items())
            else:
                enc, inv = _encode_categories(s)
                out[var] = enc.astype("Int64")
                values_txt = "; ".join(f"{i} = {v}" for i,v in inv.items())
            labels.append({"var": var, "lab": c.text, "values": values_txt})

    meta = {
        "nazev_studie": spec.name, "vyzkumna_otazka": spec.research_question,
        "typ_vystupu": spec.output_type, "N": len(out), "objekty_pocet": len(spec.objects),
        "object_family": spec.object_family,
        "familiarity_required": bool(spec.familiarity_required),
        "object_scale_labels": list(spec.object_scale_labels),
        "verze_panelu": run_result.get("panel_version") or run_result.get("manifest", {}).get("panel_version") or "v15.2",
        "seed": spec.seed, "run_id": run_result.get("run_id", ""),
    }
    return out.reset_index(drop=True), labels, meta
