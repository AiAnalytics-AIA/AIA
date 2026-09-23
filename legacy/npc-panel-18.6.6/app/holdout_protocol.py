"""Preregistered, append-only blind-human-holdout protocol.

The protocol deliberately separates three moments:
1) preregister questions/analysis before truth is imported,
2) lock human truth against that preregistration,
3) benchmark the frozen system and append evidence to a hash-chained ledger.

The blind holdout is never used for automatic calibration or model fitting.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from typing import Any
import hashlib
import json
import math

REQUIRED_QUESTION_FIELDS = {"id", "text", "kategorie", "domain"}
REQUIRED_TRUTH_FIELDS = {"truth_pct", "human_n", "holdout_source", "holdout_id"}


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj)).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for c in iter(lambda: f.read(1024 * 1024), b""):
            h.update(c)
    return h.hexdigest()


def _validate_distribution(d: dict[str, Any], cats: list[str], qid: str) -> None:
    missing = set(cats) - set(d)
    extra = set(d) - set(cats)
    if missing or extra:
        raise ValueError(f"{qid}: truth_pct categories mismatch; missing={sorted(missing)} extra={sorted(extra)}")
    vals = [float(d[c]) for c in cats]
    if any((not math.isfinite(x) or x < 0 or x > 100) for x in vals):
        raise ValueError(f"{qid}: truth_pct must contain finite percentages 0..100")
    if abs(sum(vals) - 100.0) > 0.75:
        raise ValueError(f"{qid}: truth_pct must sum to ~100, got {sum(vals):.3f}")


def validate_preregistration(spec: dict) -> dict:
    qs = list(spec.get("questions") or [])
    if len(qs) < 1:
        raise ValueError("preregistration requires questions")
    ids = []
    for q in qs:
        miss = REQUIRED_QUESTION_FIELDS - set(q)
        if miss:
            raise ValueError(f"question missing prereg fields: {sorted(miss)}")
        qid = str(q["id"]).strip()
        if not qid:
            raise ValueError("empty question id")
        ids.append(qid)
        cats = list(q.get("kategorie") or [])
        if len(cats) < 2 or len(set(map(str, cats))) != len(cats):
            raise ValueError(f"{qid}: categories must be unique and >=2")
        if "truth_pct" in q:
            raise ValueError(f"{qid}: preregistration must be created before truth is attached")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate question ids in preregistration")
    return {"n_questions": len(qs), "domains": sorted({str(q["domain"]) for q in qs})}


def preregister(spec: dict, out_path: str | Path, *, analyst: str = "", note: str = "") -> Path:
    summary = validate_preregistration(spec)
    frozen = {
        "kind": "npc_blind_holdout_preregistration",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "analyst": str(analyst).strip(),
        "note": str(note),
        "analysis_plan": spec.get("analysis_plan", {
            "primary_metric": "question-level MAE pp",
            "baselines": ["generic", "demographics", "core", "full", "shuffled_full"],
            "paired_question_analysis": True,
        }),
        "questions": [
            {k: q[k] for k in q if k not in REQUIRED_TRUTH_FIELDS}
            for q in spec["questions"]
        ],
        "summary": summary,
    }
    frozen["prereg_sha256"] = sha256_json({k: v for k, v in frozen.items() if k != "prereg_sha256"})
    p = Path(out_path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def lock_truth(prereg_path: str | Path, truth_spec: dict, out_path: str | Path) -> Path:
    pp = Path(prereg_path)
    pre = json.loads(pp.read_text(encoding="utf-8"))
    expected = pre.get("prereg_sha256")
    actual = sha256_json({k: v for k, v in pre.items() if k != "prereg_sha256"})
    if not expected or expected != actual:
        raise ValueError("preregistration hash mismatch")
    preq = {str(q["id"]): q for q in pre["questions"]}
    truthq = {str(q["id"]): q for q in truth_spec.get("questions", [])}
    if set(preq) != set(truthq):
        raise ValueError("truth question IDs differ from preregistration")
    locked = []
    holdout_ids = []
    for qid, pq in preq.items():
        tq = truthq[qid]
        for fld in REQUIRED_TRUTH_FIELDS:
            if fld not in tq or tq[fld] in (None, ""):
                raise ValueError(f"{qid}: missing {fld}")
        # Wording, categories and domain must remain frozen.
        for fld in ("text", "kategorie", "domain"):
            if tq.get(fld, pq.get(fld)) != pq.get(fld):
                raise ValueError(f"{qid}: {fld} differs from preregistration")
        _validate_distribution(tq["truth_pct"], list(pq["kategorie"]), qid)
        if int(tq["human_n"]) <= 0:
            raise ValueError(f"{qid}: human_n must be >0")
        holdout_ids.append(str(tq["holdout_id"]))
        locked.append({**pq, **{k: tq[k] for k in REQUIRED_TRUTH_FIELDS},
                       "fieldwork_start": tq.get("fieldwork_start", ""),
                       "fieldwork_end": tq.get("fieldwork_end", ""),
                       "methodology": tq.get("methodology", ""),
                       "human_moe_pp": tq.get("human_moe_pp"),
                       "human_design_effect": tq.get("human_design_effect", 1.0)})
    if len(holdout_ids) != len(set(holdout_ids)):
        raise ValueError("holdout_id must be unique per question")

    # Exact-item contamination check against calibration provenance. Sharing an
    # institution is allowed; reusing the exact holdout item/wave identifier is not.
    try:
        from dispozice import DIMENZE
        calibration_sources = "\n".join(str(d.get("zdroj", "")) for d in DIMENZE.values()).lower()
        contaminated = [hid for hid in holdout_ids if hid.strip() and hid.strip().lower() in calibration_sources]
        if contaminated:
            raise ValueError(f"holdout item already appears in calibration provenance: {contaminated}")
    except ImportError:
        pass
    out = {
        "kind": "npc_locked_blind_holdout",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "preregistration": str(pp.resolve()),
        "prereg_sha256": expected,
        "questions": locked,
    }
    out["locked_truth_sha256"] = sha256_json({k: v for k, v in out.items() if k != "locked_truth_sha256"})
    p = Path(out_path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def append_ledger(ledger_path: str | Path, event: dict[str, Any]) -> dict[str, Any]:
    """Append an event to a tamper-evident JSONL hash chain."""
    p = Path(ledger_path); p.parent.mkdir(parents=True, exist_ok=True)
    prev = "GENESIS"
    seq = 1
    if p.exists():
        lines = [x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
        if lines:
            last = json.loads(lines[-1])
            prev = str(last["entry_sha256"])
            seq = int(last["seq"]) + 1
    record = {
        "seq": seq,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "previous_sha256": prev,
        **event,
    }
    record["entry_sha256"] = sha256_json(record)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    return record


def verify_ledger(ledger_path: str | Path) -> dict[str, Any]:
    p = Path(ledger_path)
    if not p.exists():
        return {"valid": False, "entries": 0, "reason": "ledger missing"}
    prev = "GENESIS"; n = 0
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line); n += 1
        got = rec.pop("entry_sha256", None)
        if rec.get("previous_sha256") != prev:
            return {"valid": False, "entries": n, "reason": "broken previous hash"}
        calc = sha256_json(rec)
        if got != calc:
            return {"valid": False, "entries": n, "reason": "entry hash mismatch"}
        prev = got
    return {"valid": True, "entries": n, "head_sha256": prev}


def consumed_holdout_hashes(ledger_path: str | Path) -> set[str]:
    p = Path(ledger_path)
    out: set[str] = set()
    if not p.exists():
        return out
    if not verify_ledger(p).get("valid"):
        raise ValueError("cannot inspect consumed holdouts: ledger is invalid")
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("event") == "benchmark_completed" and rec.get("locked_truth_sha256"):
            out.add(str(rec["locked_truth_sha256"]))
    return out


def assert_holdout_unconsumed(ledger_path: str | Path, locked_truth_path: str | Path) -> str:
    h = sha256_file(locked_truth_path)
    if h in consumed_holdout_hashes(ledger_path):
        raise RuntimeError("This blind holdout has already been consumed by a certified benchmark. Use a new holdout after changing/tuning the system.")
    return h
