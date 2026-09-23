"""Fail-closed evidence gate for predictive validity.

A dry/smoke benchmark can never unlock a validity claim. VALIDATED requires:
- preregistered blind-human holdout with locked truth,
- all five ablation baselines,
- paired statistical superiority (not only a favorable mean),
- multi-domain coverage,
- immutable benchmark/manifest hashes,
- a tamper-evident ledger entry,
- and the exact same current system fingerprint as the benchmarked system.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import pandas as pd

from benchmark import summarize_benchmark
from validation_stats import paired_validation_stats, domain_coverage, per_domain_performance
from system_fingerprint import build_system_fingerprint
from holdout_protocol import verify_ledger, sha256_file as protocol_sha256_file

ROOT = Path(__file__).resolve().parent
DEFAULT_EVIDENCE_PATH = ROOT / "VALIDATION_EVIDENCE.json"

DEFAULT_THRESHOLDS = {
    "min_questions": 30,
    "min_domains": 5,
    "min_questions_per_domain": 3,
    "max_full_mae_pp": 7.5,
    "min_human_n_per_question": 300,
    "max_human_moe_pp": 5.0,
    "min_relative_improvement_vs_demographics": 0.10,
    "min_relative_improvement_vs_generic": 0.10,
    "min_relative_improvement_vs_shuffled": 0.08,
    "min_win_rate_vs_demographics": 0.60,
    "min_win_rate_vs_generic": 0.60,
    "min_win_rate_vs_shuffled": 0.60,
    "min_win_rate_vs_core": 0.55,
    "require_positive_ci_vs_demographics": True,
    "require_positive_ci_vs_generic": True,
    "require_positive_ci_vs_shuffled": True,
    "min_domain_win_share_vs_demographics": 0.60,
}


def _sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def evaluate_validation(df: pd.DataFrame, thresholds: dict[str, Any] | None = None) -> dict[str, Any]:
    th = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    s = summarize_benchmark(df)
    paired = paired_validation_stats(df, repeats=4000)
    coverage = domain_coverage(df)
    domains = per_domain_performance(df)
    reasons: list[str] = []

    if s.get("status") == "NO_DATA": reasons.append("no benchmark data")
    if not s.get("substantive", False): reasons.append("benchmark is dry/mock, not human-validity evidence")
    if int(s.get("n_questions", 0)) < int(th["min_questions"]):
        reasons.append(f"need >= {th['min_questions']} blind questions")

    if coverage.get("missing_domain"):
        reasons.append("every blind question must have a preregistered domain")
    if int(coverage.get("n_domains", 0)) < int(th["min_domains"]):
        reasons.append(f"need >= {th['min_domains']} benchmark domains")
    too_small = {d: n for d, n in coverage.get("questions_per_domain", {}).items()
                 if int(n) < int(th["min_questions_per_domain"])}
    if too_small:
        reasons.append(f"domains below minimum question count {th['min_questions_per_domain']}: {too_small}")

    full = s.get("mean_mae_pp", {}).get("full")
    if full is None or full > float(th["max_full_mae_pp"]):
        reasons.append(f"full MAE must be <= {th['max_full_mae_pp']} pp")

    rel_checks = [
        ("demographics", "min_relative_improvement_vs_demographics"),
        ("generic", "min_relative_improvement_vs_generic"),
        ("shuffled_full", "min_relative_improvement_vs_shuffled"),
    ]
    for base, key in rel_checks:
        val = s.get(f"full_relative_improvement_vs_{base}")
        if val is None or val < float(th[key]):
            reasons.append(f"full must improve >= {float(th[key])*100:.0f}% vs {base}")

    comp = paired.get("comparisons", {})
    stat_checks = [
        ("demographics", "min_win_rate_vs_demographics", "require_positive_ci_vs_demographics"),
        ("generic", "min_win_rate_vs_generic", "require_positive_ci_vs_generic"),
        ("shuffled_full", "min_win_rate_vs_shuffled", "require_positive_ci_vs_shuffled"),
        ("core", "min_win_rate_vs_core", None),
    ]
    for base, wr_key, ci_key in stat_checks:
        c = comp.get(base, {})
        wr = c.get("win_rate")
        if wr is None or wr < float(th[wr_key]):
            reasons.append(f"paired win-rate vs {base} must be >= {float(th[wr_key])*100:.0f}%")
        if ci_key and th.get(ci_key) and (c.get("improvement_ci_low_pp") is None or c.get("improvement_ci_low_pp") <= 0):
            reasons.append(f"paired bootstrap CI of improvement vs {base} must stay above 0 pp")

    # Prevent the overall average from hiding a system that only works in one topic family.
    dom_evaluable = [v for v in domains.values() if "full" in v and "demographics" in v]
    if dom_evaluable:
        share = sum(v["full"] < v["demographics"] for v in dom_evaluable) / len(dom_evaluable)
        if share < float(th["min_domain_win_share_vs_demographics"]):
            reasons.append(
                f"full must beat demographics in >= {float(th['min_domain_win_share_vs_demographics'])*100:.0f}% of domains"
            )
    else:
        share = None

    required_baselines = {"generic", "demographics", "core", "full", "shuffled_full"}
    if not df.empty:
        for qid, g in df.groupby("question_id"):
            missing_b = required_baselines - set(g["baseline"].astype(str))
            if missing_b: reasons.append(f"{qid}: missing baselines {sorted(missing_b)}")
            if "human_n" not in g or g["human_n"].isna().all():
                reasons.append(f"{qid}: missing human_n")
            else:
                hn = float(pd.to_numeric(g["human_n"], errors="coerce").dropna().max())
                if hn < float(th["min_human_n_per_question"]):
                    reasons.append(f"{qid}: human_n must be >= {th['min_human_n_per_question']}")
            if "human_moe_pp" not in g or g["human_moe_pp"].isna().all():
                reasons.append(f"{qid}: missing human reference uncertainty")
            else:
                hm = float(pd.to_numeric(g["human_moe_pp"], errors="coerce").dropna().max())
                if hm > float(th["max_human_moe_pp"]):
                    reasons.append(f"{qid}: human reference MOE {hm:.2f} pp exceeds {th['max_human_moe_pp']} pp")
            for col in ("holdout_source", "holdout_id", "domain", "prereg_sha256"):
                if col not in g or not g[col].fillna("").astype(str).str.strip().any(): reasons.append(f"{qid}: missing {col}")

    return {
        "status": "VALIDATED" if not reasons else "NOT_VALIDATED",
        "reasons": reasons,
        "thresholds": th,
        "summary": s,
        "paired_stats": paired,
        "domain_coverage": coverage,
        "per_domain": domains,
        "domain_win_share_vs_demographics": share,
    }


def write_validation_evidence(df: pd.DataFrame, path: str | Path = DEFAULT_EVIDENCE_PATH,
                              thresholds: dict[str, Any] | None = None,
                              *, benchmark_csv: str | Path | None = None,
                              benchmark_manifest: str | Path | None = None,
                              preregistration: str | Path | None = None,
                              locked_truth: str | Path | None = None,
                              ledger: str | Path | None = None,
                              holdout_note: str = "",
                              approved_by: str = "", approved_at: str = "",
                              holdout_exclusion_attested: bool = False) -> Path:
    out = evaluate_validation(df, thresholds)
    if benchmark_csv:
        bp = Path(benchmark_csv); out["benchmark_csv"] = str(bp); out["benchmark_sha256"] = _sha256_file(bp)
    if benchmark_manifest:
        mp = Path(benchmark_manifest); out["benchmark_manifest"] = str(mp); out["benchmark_manifest_sha256"] = _sha256_file(mp)
    if preregistration:
        pp = Path(preregistration); out["preregistration"] = str(pp); out["preregistration_sha256"] = _sha256_file(pp)
    if locked_truth:
        lp = Path(locked_truth); out["locked_truth"] = str(lp); out["locked_truth_sha256"] = _sha256_file(lp)
    if ledger:
        led = Path(ledger); out["ledger"] = str(led); out["ledger_sha256"] = _sha256_file(led) if led.exists() else ""
        out["ledger_verification"] = verify_ledger(led)
    out["system_fingerprint"] = build_system_fingerprint()
    out["system_sha256"] = out["system_fingerprint"]["system_sha256"]
    out["holdout_note"] = str(holdout_note)
    out["approved_by"] = str(approved_by).strip(); out["approved_at"] = str(approved_at).strip()
    out["holdout_exclusion_attested"] = bool(holdout_exclusion_attested)

    if out.get("status") == "VALIDATED":
        missing = []
        for fld in ("benchmark_csv", "benchmark_manifest", "preregistration", "locked_truth", "ledger", "approved_by", "approved_at"):
            if not out.get(fld): missing.append(fld)
        if not out.get("holdout_exclusion_attested"): missing.append("holdout_exclusion_attested")
        if not out.get("ledger_verification", {}).get("valid"): missing.append("valid_ledger")
        if missing:
            out["status"] = "NOT_VALIDATED"
            out.setdefault("reasons", []).append("validation evidence missing governance fields: " + ", ".join(missing))
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def _resolve(parent: Path, value: str | None) -> Path | None:
    if not value: return None
    p = Path(value)
    return p if p.is_absolute() else parent / p


def load_validation_evidence(path: str | Path = DEFAULT_EVIDENCE_PATH) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"status": "NOT_VALIDATED", "reasons": ["validation evidence file is missing"], "path": str(p)}
    try: obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e: return {"status": "NOT_VALIDATED", "reasons": [f"invalid validation evidence: {e}"], "path": str(p)}
    # Always expose the current system separately from whatever hash may be stored
    # in historical/pending evidence.  A stale pending evidence file must never look
    # like the current runtime fingerprint.
    current = build_system_fingerprint()
    stored_hash = obj.get("system_sha256") or obj.get("current_system_sha256")
    if stored_hash:
        obj["evidence_system_sha256"] = stored_hash
    obj["current_system_sha256"] = current["system_sha256"]

    if obj.get("status") != "VALIDATED":
        obj.setdefault("reasons", []).append("stored evidence does not have VALIDATED status")
        obj["status"] = "NOT_VALIDATED"
        return obj

    # Exact-system binding: any behavior-changing code/data/model change invalidates old validation.
    if obj.get("system_sha256") != current["system_sha256"]:
        return {**obj, "status": "NOT_VALIDATED", "reasons": ["system fingerprint changed since validation; rerun blind benchmark"],
                "current_system_sha256": current["system_sha256"]}

    bp = _resolve(p.parent, obj.get("benchmark_csv")); expected = obj.get("benchmark_sha256")
    if not bp or not expected or not bp.exists() or _sha256_file(bp) != expected:
        return {**obj, "status": "NOT_VALIDATED", "reasons": ["benchmark CSV missing or hash mismatch"]}
    mp = _resolve(p.parent, obj.get("benchmark_manifest")); mh = obj.get("benchmark_manifest_sha256")
    if not mp or not mh or not mp.exists() or _sha256_file(mp) != mh:
        return {**obj, "status": "NOT_VALIDATED", "reasons": ["benchmark manifest missing or hash mismatch"]}
    try: mani = json.loads(mp.read_text(encoding="utf-8"))
    except Exception as e: return {**obj, "status": "NOT_VALIDATED", "reasons": [f"invalid benchmark manifest: {e}"]}
    if mani.get("mode") == "dry" or not mani.get("summary", {}).get("substantive", False):
        return {**obj, "status": "NOT_VALIDATED", "reasons": ["benchmark manifest is not substantive/live"]}
    if mani.get("benchmark_sha256") != expected:
        return {**obj, "status": "NOT_VALIDATED", "reasons": ["manifest and evidence disagree on benchmark hash"]}
    if mani.get("system_sha256") != current["system_sha256"]:
        return {**obj, "status": "NOT_VALIDATED", "reasons": ["benchmark manifest belongs to another system fingerprint"]}

    # Preregistration and locked truth are immutable inputs to the benchmark.
    for fld, hashfld in (("preregistration", "preregistration_sha256"), ("locked_truth", "locked_truth_sha256")):
        rp = _resolve(p.parent, obj.get(fld)); rh = obj.get(hashfld)
        if not rp or not rh or not rp.exists() or protocol_sha256_file(rp) != rh:
            return {**obj, "status": "NOT_VALIDATED", "reasons": [f"{fld} missing or hash mismatch"]}
    led = _resolve(p.parent, obj.get("ledger"))
    if not led or not led.exists() or not verify_ledger(led).get("valid"):
        return {**obj, "status": "NOT_VALIDATED", "reasons": ["validation ledger missing or invalid"]}
    if obj.get("ledger_sha256") != _sha256_file(led):
        return {**obj, "status": "NOT_VALIDATED", "reasons": ["validation ledger changed after evidence sign-off"]}
    if not str(obj.get("approved_by", "")).strip() or not str(obj.get("approved_at", "")).strip():
        return {**obj, "status": "NOT_VALIDATED", "reasons": ["validation sign-off is missing"]}
    if not bool(obj.get("holdout_exclusion_attested", False)):
        return {**obj, "status": "NOT_VALIDATED", "reasons": ["holdout exclusion attestation is missing"]}

    # Re-evaluate statistics from immutable benchmark bytes, so edited evidence JSON cannot override thresholds.
    df = pd.read_csv(bp)
    fresh = evaluate_validation(df, obj.get("thresholds"))
    if fresh.get("status") != "VALIDATED":
        return {**obj, "status": "NOT_VALIDATED", "reasons": ["benchmark no longer satisfies stored validation thresholds"] + fresh.get("reasons", [])}
    return obj


def assert_validation_ready(*, use_case: str = "internal", evidence_path: str | Path = DEFAULT_EVIDENCE_PATH) -> dict[str, Any]:
    out = load_validation_evidence(evidence_path)
    if str(use_case).lower().strip() in {"commercial", "validated"} and out.get("status") != "VALIDATED":
        reasons = "; ".join(out.get("reasons", [])[:8]) or "no validated blind benchmark"
        raise RuntimeError("Validated/commercial predictive claim blocked: " + reasons)
    return out

def sensitive_gender_segmentation_gate(block_or_topics, *, segment='pohlavi', oos_path=None):
    if str(segment).lower() not in {'pohlavi','sex','gender'}:return {'status':'PASS','suppress':False,'reason':'not gender'}
    topics={str(block_or_topics).lower()} if isinstance(block_or_topics,str) else {str(x).lower() for x in (block_or_topics or [])}
    if not topics & {'social_network','socialni_site','media','media_online','online','reklama'}:return {'status':'PASS','suppress':False,'reason':'outside protected blocks'}
    p=Path(oos_path) if oos_path else ROOT/'OUT_OF_SAMPLE_VALIDATION_v17_1.csv'
    try:
        d=pd.read_csv(p);r=d[d.check_id.astype(str).eq('OOS03')];ok=(not r.empty) and str(r.iloc[0].status).upper()=='PASS' and float(r.iloc[0].observed)>0
    except Exception as e:return {'status':'SUPPRESS','suppress':True,'reason':f'gender evidence unavailable: {e}'}
    return {'status':'PASS' if ok else 'SUPPRESS','suppress':not ok,'reason':'gender direction regression check'}
