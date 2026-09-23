#!/usr/bin/env python3
"""CLI for preregistering, locking and signing blind-human validation evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pandas as pd

from holdout_protocol import preregister, lock_truth, append_ledger, verify_ledger, sha256_file, assert_holdout_unconsumed
from validation_gate import write_validation_evidence, load_validation_evidence


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("preregister")
    a.add_argument("spec"); a.add_argument("out"); a.add_argument("--analyst", default=""); a.add_argument("--ledger", default="validation_ledger.jsonl")

    a = sub.add_parser("lock-truth")
    a.add_argument("prereg"); a.add_argument("truth"); a.add_argument("out"); a.add_argument("--ledger", default="validation_ledger.jsonl")

    a = sub.add_parser("sign")
    a.add_argument("benchmark_csv"); a.add_argument("benchmark_manifest"); a.add_argument("prereg"); a.add_argument("locked_truth")
    a.add_argument("--ledger", default="validation_ledger.jsonl"); a.add_argument("--out", default="VALIDATION_EVIDENCE.json")
    a.add_argument("--approved-by", required=True); a.add_argument("--approved-at", required=True); a.add_argument("--attest-holdout-excluded", action="store_true")

    a = sub.add_parser("status")
    a.add_argument("--evidence", default="VALIDATION_EVIDENCE.json")

    args = ap.parse_args()
    if args.cmd == "preregister":
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        p = preregister(spec, args.out, analyst=args.analyst)
        append_ledger(args.ledger, {"event": "preregistered", "artifact": str(p.resolve()), "sha256": sha256_file(p)})
        print(p); return 0
    if args.cmd == "lock-truth":
        truth = json.loads(Path(args.truth).read_text(encoding="utf-8"))
        p = lock_truth(args.prereg, truth, args.out)
        append_ledger(args.ledger, {"event": "truth_locked", "artifact": str(p.resolve()), "sha256": sha256_file(p), "prereg": str(Path(args.prereg).resolve())})
        print(p); return 0
    if args.cmd == "sign":
        if not args.attest_holdout_excluded:
            raise SystemExit("Refusing to sign: --attest-holdout-excluded is required")
        led = Path(args.ledger)
        locked_hash = assert_holdout_unconsumed(led, args.locked_truth)
        mani_obj = json.loads(Path(args.benchmark_manifest).read_text(encoding="utf-8"))
        append_ledger(led, {"event": "benchmark_completed", "benchmark_csv": str(Path(args.benchmark_csv).resolve()),
                            "benchmark_sha256": sha256_file(args.benchmark_csv), "manifest_sha256": sha256_file(args.benchmark_manifest),
                            "locked_truth_sha256": locked_hash, "system_sha256": mani_obj.get("system_sha256", "")})
        append_ledger(led, {"event": "validation_approved", "approved_by": args.approved_by, "approved_at": args.approved_at,
                            "holdout_exclusion_attested": True})
        df = pd.read_csv(args.benchmark_csv)
        p = write_validation_evidence(df, args.out, benchmark_csv=args.benchmark_csv,
                                      benchmark_manifest=args.benchmark_manifest, preregistration=args.prereg,
                                      locked_truth=args.locked_truth, ledger=led,
                                      approved_by=args.approved_by, approved_at=args.approved_at,
                                      holdout_exclusion_attested=True)
        obj = json.loads(p.read_text(encoding="utf-8"))
        print(json.dumps({"path": str(p), "status": obj.get("status"), "reasons": obj.get("reasons", [])}, ensure_ascii=False, indent=2))
        return 0 if obj.get("status") == "VALIDATED" else 2
    if args.cmd == "status":
        obj = load_validation_evidence(args.evidence)
        print(json.dumps(obj, ensure_ascii=False, indent=2)); return 0 if obj.get("status") == "VALIDATED" else 2
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
