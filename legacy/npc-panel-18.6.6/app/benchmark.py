"""Blind human holdout / ablation benchmark for NPC Panel.

This is the release-defining measurement. A benchmark has substantive meaning only
when ``truth_pct`` comes from real human responses that were excluded from panel
construction/calibration and the run uses a live model, not ``mode=dry``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import kendalltau

from dotaznik import run_dotaznik
from runtime_config import DEFAULT_MODEL, resolve_provider_model
from pipeline import PANEL_PATH
from system_fingerprint import build_system_fingerprint
from persona_calibration import disable_active_calibration

BASELINES = {
    "generic": {"persona_mode": "none", "shuffle_persona": False},
    "demographics": {"persona_mode": "demographics", "shuffle_persona": False},
    "core": {"persona_mode": "core", "shuffle_persona": False},
    "full": {"persona_mode": "full", "shuffle_persona": False},
    "shuffled_full": {"persona_mode": "full", "shuffle_persona": True},
}


def _metrics(pred: dict[str, float], truth: dict[str, float]) -> dict[str, float]:
    cats = sorted(set(pred) | set(truth))
    e = np.array([pred.get(c, 0.0) - truth.get(c, 0.0) for c in cats], dtype=float)
    pv=np.array([pred.get(c,0.0) for c in cats],dtype=float); tv=np.array([truth.get(c,0.0) for c in cats],dtype=float)
    tau = kendalltau(pv, tv, nan_policy="omit").statistic if len(cats) >= 2 else np.nan
    tvar=float(np.var(tv)); pvar=float(np.var(pv))
    return {
        "mae_pp": round(float(np.mean(np.abs(e))), 3),
        "rmse_pp": round(float(np.sqrt(np.mean(e ** 2))), 3),
        "tvd_pp": round(float(0.5 * np.sum(np.abs(e))), 3),
        "kendall_tau": None if not np.isfinite(tau) else round(float(tau), 4),
        "variance_ratio": None if tvar <= 1e-12 else round(float(pvar/tvar), 4),
    }


def _target_metrics(pred: dict[str,float], truth: dict[str,float], q: dict) -> dict[str,float|None|str]:
    targets=[str(x) for x in (q.get("target_answers") or [])]
    errs={str(c):round(float(pred.get(c,0.0)-truth.get(c,0.0)),3) for c in sorted(set(pred)|set(truth))}
    out={"category_error_json":json.dumps(errs,ensure_ascii=False,sort_keys=True),
         "max_abs_category_error_pp":round(max((abs(v) for v in errs.values()),default=0.0),3),
         "target_answers_json":json.dumps(targets,ensure_ascii=False),
         "target_pred_pct":None,"target_truth_pct":None,"target_bias_pp":None,"target_abs_error_pp":None}
    if targets:
        pp=sum(float(pred.get(c,0.0)) for c in targets); tt=sum(float(truth.get(c,0.0)) for c in targets)
        out.update(target_pred_pct=round(pp,3),target_truth_pct=round(tt,3),target_bias_pp=round(pp-tt,3),target_abs_error_pp=round(abs(pp-tt),3))
    return out


def _human_moe_pp(q: dict) -> tuple[float | None, str]:
    """Return supplied 95% MOE or a transparent SRS approximation from human_n.

    The SRS fallback is not promoted to a design-aware survey interval; it is stored
    only so the benchmark exposes the precision of the human reference itself.
    """
    if q.get("human_moe_pp") is not None:
        return float(q["human_moe_pp"]), "supplied"
    try:
        n = float(q.get("human_n"))
        if n <= 0: return None, "missing"
        ps = [float(x)/100 for x in q.get("truth_pct", {}).values()]
        if not ps: return None, "missing"
        se = max((p*(1-p)/n) ** 0.5 for p in ps) * 100
        deff = float(q.get("human_design_effect", 1.0) or 1.0)
        return round(1.96 * se * (deff ** 0.5), 3), "srs_approx" if deff == 1 else "design_effect_adjusted"
    except Exception:
        return None, "missing"


def run_benchmark(spec: dict, *, n: int = 500, panel_path: str | None = None,
                  model: str = DEFAULT_MODEL, mode: str = "sync",
                  seed: int = 42, baselines: tuple[str, ...] | None = None,
                  budget_max_usd: float | None = None, provider: str | None = None) -> pd.DataFrame:
    from provider_auth import get_ai_provider, normalize_ai_provider
    provider = normalize_ai_provider(provider or get_ai_provider())
    model = resolve_provider_model(provider, model)
    names = tuple(baselines or BASELINES.keys())
    unknown = [x for x in names if x not in BASELINES]
    if unknown:
        raise ValueError(f"Unknown benchmark baselines: {unknown}")
    rows = []
    spent_total = 0.0
    for qi, q in enumerate(spec.get("questions", [])):
        truth = q.get("truth_pct")
        if not truth:
            raise ValueError(f"{q.get('id')}: chybi truth_pct")
        q_for_run = {k: val for k, val in q.items()
                     if k not in {"truth_pct", "human_n", "holdout_source", "holdout_id",
                                  "fieldwork_start", "fieldwork_end", "methodology", "domain",
                                  "human_moe_pp", "human_design_effect", "benchmark_role",
                                  "target_answers", "segment_id", "segment_label", "filters", "benchmark_id"}}
        unit_id=str(q.get("benchmark_id") or (str(q.get("id")) + ("::"+str(q.get("segment_id")) if q.get("segment_id") else "")))
        for name in names:
            cfg = BASELINES[name]
            # Benchmark measures raw recipes. An already active calibration profile must
            # never leak back into the benchmark that is supposed to evaluate it.
            with disable_active_calibration():
                remaining = None if budget_max_usd is None else max(0.0, float(budget_max_usd) - spent_total)
                if mode != "dry" and remaining is not None and remaining <= 0:
                    raise RuntimeError(f"BENCHMARK_BUDGET_CAP: hard budget ${float(budget_max_usd):.4f} byl vyčerpán před {q.get('id')}/{name}.")
                v = run_dotaznik(
                    [q_for_run], n=n, panel_path=panel_path, model=model, mode=mode,
                    filtry=q.get("filters") or None, seed=seed + qi * 10007, ulozit=False, tichy=True,
                    persona_mode=cfg["persona_mode"], shuffle_persona=cfg["shuffle_persona"],
                    allow_own_estimates=False, provider_policy=("strict_"+provider) if mode != "dry" else "fallback",
                    budget_max_usd=remaining,
                )
            spent_total += float(v.get("naklady_usd") or 0.0)
            if mode != "dry" and str(v.get("run_status") or "") == "PARTIAL_BUDGET_CAP":
                raise RuntimeError(f"BENCHMARK_BUDGET_CAP: hard budget zastavil {q.get('id')}/{name}; nekompletní rameno se do kalibrace nepoužije.")
            answer = v["vysledky"][q["id"]]
            pred = answer.get("expected_pct") or answer.get("celkem_pct", {})
            m = _metrics(pred, truth); tm=_target_metrics(pred,truth,q)
            human_moe, human_moe_method = _human_moe_pp(q)
            rows.append({
                "question_id": unit_id, "source_question_id":q["id"], "baseline": name, **m, **tm,
                "human_n": q.get("human_n"), "holdout_source": q.get("holdout_source", ""),
                "holdout_id": q.get("holdout_id", ""), "domain": q.get("domain", ""),
                "fieldwork_start": q.get("fieldwork_start", ""),
                "fieldwork_end": q.get("fieldwork_end", ""),
                "methodology": q.get("methodology", ""),
                "benchmark_role": str(q.get("benchmark_role") or "BLIND_HOLDOUT").upper(),
                "segment_id":str(q.get("segment_id") or ""),"segment_label":str(q.get("segment_label") or ""),
                "filters_json":json.dumps(q.get("filters") or {},ensure_ascii=False,sort_keys=True),
                "human_moe_pp": human_moe, "human_moe_method": human_moe_method,
                "prereg_sha256": spec.get("prereg_sha256", ""), "mode": mode, "provider": provider,
                "benchmark_spent_usd_cumulative": round(spent_total, 6),
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        for base in ("generic", "demographics", "shuffled_full"):
            b = df[df.baseline == base].set_index("question_id")["mae_pp"]
            df[f"mae_improvement_vs_{base}_pp"] = [
                round(float(b.get(r.question_id, np.nan) - r.mae_pp), 3)
                for r in df.itertuples()
            ]
    return df


def summarize_benchmark(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"status": "NO_DATA"}
    means = df.groupby("baseline")["mae_pp"].mean().to_dict()
    full = float(means.get("full", np.nan))
    summary = {"mean_mae_pp": {k: round(float(v), 3) for k, v in means.items()},
               "mean_rmse_pp": {k:round(float(v),3) for k,v in df.groupby("baseline")["rmse_pp"].mean().to_dict().items()} if "rmse_pp" in df else {},
               "mean_tvd_pp": {k:round(float(v),3) for k,v in df.groupby("baseline")["tvd_pp"].mean().to_dict().items()} if "tvd_pp" in df else {},
               "mean_kendall_tau": {k:round(float(v),4) for k,v in df.groupby("baseline")["kendall_tau"].mean().dropna().to_dict().items()} if "kendall_tau" in df else {},
               "n_questions": int(df["question_id"].nunique()),
               "substantive": not (df["mode"] == "dry").all()}
    if "target_bias_pp" in df:
        t=df[pd.to_numeric(df["target_bias_pp"],errors="coerce").notna()].copy()
        if not t.empty:
            t["target_bias_pp"]=pd.to_numeric(t["target_bias_pp"],errors="coerce")
            t["target_abs_error_pp"]=pd.to_numeric(t["target_abs_error_pp"],errors="coerce")
            summary["mean_target_bias_pp"]={k:round(float(v),3) for k,v in t.groupby("baseline")["target_bias_pp"].mean().to_dict().items()}
            summary["mean_target_abs_error_pp"]={k:round(float(v),3) for k,v in t.groupby("baseline")["target_abs_error_pp"].mean().to_dict().items()}
    for b in ("generic", "demographics", "shuffled_full"):
        if b in means and np.isfinite(full):
            summary[f"full_improvement_vs_{b}_pp"] = round(float(means[b] - full), 3)
            summary[f"full_relative_improvement_vs_{b}"] = (
                round(float((means[b] - full) / means[b]), 4) if means[b] else None)
    return summary


def summarize_benchmark_by_role(df: pd.DataFrame) -> dict[str, dict]:
    out={}
    if df.empty: return out
    roles=df["benchmark_role"].fillna("BLIND_HOLDOUT").astype(str).str.upper() if "benchmark_role" in df else pd.Series(["BLIND_HOLDOUT"]*len(df),index=df.index)
    for role in sorted(roles.unique()):
        part=df[roles==role]
        sm=summarize_benchmark(part)
        val=pd.to_numeric(part["benchmark_spent_usd_cumulative"],errors="coerce").max() if "benchmark_spent_usd_cumulative" in part else 0.0
        sm["spent_usd"] = round(float(val),6) if pd.notna(val) else 0.0
        out[role]=sm
    return out


def summarize_benchmark_by_segment(df: pd.DataFrame) -> dict[str,dict]:
    if df.empty or "segment_id" not in df: return {}
    out={}
    seg=df["segment_id"].fillna("").astype(str)
    for sid in sorted(x for x in seg.unique() if x):
        out[sid]=summarize_benchmark(df[seg==sid])
    return out


def _sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_json(obj: object) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def write_benchmark_manifest(*, spec: dict, out_csv: str | Path, panel_path: str | None,
                             model: str, mode: str, n: int, seed: int,
                             summary: dict) -> Path:
    csv_path = Path(out_csv).resolve()
    panel = Path(panel_path or PANEL_PATH).resolve()
    fingerprint = build_system_fingerprint(panel)
    manifest = {
        "kind": "npc_blind_human_benchmark",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "benchmark_csv": str(csv_path),
        "benchmark_sha256": _sha256_file(csv_path),
        "spec_sha256": _sha256_json(spec),
        "panel_path": str(panel),
        "panel_sha256": _sha256_file(panel),
        "model": resolve_model(model),
        "mode": mode,
        "n_per_question": int(n),
        "seed": int(seed),
        "baselines": list(BASELINES),
        "prereg_sha256": spec.get("prereg_sha256", ""),
        "locked_truth_sha256": spec.get("locked_truth_sha256", ""),
        "system_fingerprint": fingerprint,
        "system_sha256": fingerprint["system_sha256"],
        "summary": summary,
    }
    mp = csv_path.with_suffix(csv_path.suffix + ".manifest.json")
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return mp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--panel")
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--mode", default="sync", choices=["sync", "batch", "dry"])
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("-o", "--out", default="benchmark_results.csv")
    ap.add_argument("--activate-persona-calibration", action="store_true", help="Po benchmarku fitne aktivní personu pouze z benchmark_role=CALIBRATION; BLIND_HOLDOUT se ignoruje.")
    ap.add_argument("--budget-max-usd", type=float, default=None, help="Hard cap přes celý benchmark; live běh je fail-closed.")
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    df = run_benchmark(spec, n=a.n, panel_path=a.panel, model=a.model,
                       mode=a.mode, seed=a.seed, budget_max_usd=a.budget_max_usd)
    df.to_csv(a.out, index=False)
    summary = summarize_benchmark(df)
    manifest = write_benchmark_manifest(spec=spec, out_csv=a.out, panel_path=a.panel,
                                        model=a.model, mode=a.mode, n=a.n, seed=a.seed,
                                        summary=summary)
    print(df.to_string(index=False))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if a.activate_persona_calibration:
        from persona_calibration import fit_calibration_profile
        profile=fit_calibration_profile(df,source={"benchmark_csv":str(Path(a.out).resolve()),"benchmark_manifest":str(manifest)},activate=True)
        print("[persona calibration] "+json.dumps({"profile_hash":profile.get("profile_hash"),"global_mode":profile.get("global_mode"),"n_questions":profile.get("n_questions")},ensure_ascii=False))
    print(f"[ulozeno] {a.out}")
    print(f"[manifest] {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
