"""Evidence-first release status.

This file deliberately does NOT assign a self-authored 1–10 product score. It reports
what can be mechanically verified and keeps external predictive validity separate.
"""
from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
from validation_gate import load_validation_evidence
from system_fingerprint import build_system_fingerprint
from validation_status import validation_tier
from core_joint import load_joint_status

ROOT=Path(__file__).resolve().parent

def build_scorecard(*,skip_tests=False)->dict:
    evidence=load_validation_evidence(); fp=build_system_fingerprint()
    test_ok=True; test_summary="SKIPPED"
    if not skip_tests:
        p=subprocess.run([sys.executable,"-m","pytest","-q"],cwd=ROOT,
                         stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        test_ok=p.returncode==0; test_summary=p.stdout[-1200:]
    try:
        from provenance import audit_dimension_contracts
        prov=audit_dimension_contracts(); provenance_ok=not prov.get("fail")
    except Exception as e:
        provenance_ok=False; prov={"error":str(e)}
    try:
        from holdout_registry import assert_holdout_clean
        h=assert_holdout_clean(); holdout_ok=not h.get("fail")
    except Exception as e:
        holdout_ok=False; h={"error":str(e)}
    tier=validation_tier(); joint=load_joint_status()
    blockers=[]
    if not test_ok:blockers.append("test_suite")
    if not provenance_ok:blockers.append("provenance_contract")
    if not holdout_ok:blockers.append("holdout_leak")
    if not joint.get("client_joint_outputs_allowed"):blockers.append("core_joint_ablation")
    if tier!="HOLDOUT_VALIDATED":blockers.append("external_human_holdout")
    return {
        "release":fp["release"],"system_sha256":fp["system_sha256"],
        "engineering_status":"PASS" if test_ok and provenance_ok and holdout_ok else "BLOCK",
        "tests_pass":test_ok,"test_summary":test_summary,
        "provenance_contract_pass":provenance_ok,"holdout_hard_gate_pass":holdout_ok,
        "validation_tier":tier,"validation_evidence_status":evidence.get("status","NOT_VALIDATED"),
        "core_joint_status":joint.get("status"),"core_joint_client_outputs_allowed":joint.get("client_joint_outputs_allowed"),
        "external_predictive_validity":"ESTABLISHED_FOR_THIS_FINGERPRINT" if tier=="HOLDOUT_VALIDATED" else "NOT_YET_ESTABLISHED",
        "release_blockers_for_validated_claim":blockers,
        "numeric_product_score":None,
        "note":"No self-awarded score. Predictive quality must be reported from out-of-sample human benchmarks.",
    }

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--skip-tests",action="store_true");a=ap.parse_args()
    out=build_scorecard(skip_tests=a.skip_tests);print(json.dumps(out,ensure_ascii=False,indent=2))
    return 0 if out["engineering_status"]=="PASS" else 1
if __name__=="__main__":raise SystemExit(main())
