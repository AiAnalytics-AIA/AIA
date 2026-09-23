#!/usr/bin/env python3
"""One-command local release self-test. Guaranteed no paid/external research calls."""
from __future__ import annotations

import json
import tempfile
from unittest.mock import patch
from pathlib import Path

import pandas as pd

from diagnostika import diagnostika
from dotaznik import run_dotaznik
from domain_readiness import readiness_for_topics
from holdout_registry import assert_holdout_clean
from legal_gate import audit_legal
from pipeline import PANEL_PATH, Panel, sample_representative
from provenance import audit_dimension_contracts
from qc import kontrola
from report import export_xlsx
from report_html import export_html
from research_context import run_dual_research
from survey_lint import lint_questions
from validation_gate import assert_validation_ready

ROOT = Path(__file__).resolve().parent
SELFTEST_QUESTIONNAIRE = ROOT / "selftest_questionnaire.json"


def main() -> int:
    checks = {}
    panel_df = pd.read_csv(PANEL_PATH, low_memory=False, dtype={'occupation_isco08':'string'})
    d = diagnostika(panel_df)
    checks["panel_diagnostics"] = d["uroven"]
    pa = audit_dimension_contracts()
    checks["data_contract_failures"] = len(pa["fail"])
    ho = assert_holdout_clean()
    checks["holdout_hard_failures"] = len(ho.get("fail", []))
    checks["holdout_institution_overlap_info"] = {"n":len(ho.get("review", [])),"status":"INFO_ONLY","note":"Same publisher may appear on both sides; exact item/wave overlap is the hard gate."}

    brief = json.loads(SELFTEST_QUESTIONNAIRE.read_text(encoding="utf-8"))
    lint = lint_questions(brief["otazky"])
    checks["questionnaire_lint"] = "OK" if lint["ok"] else "ERROR"

    # OFF means no provider/API call even when keys are absent.
    rb = run_dual_research(False, brief["otazky"])
    checks["research_context_off_true_off"] = (not rb.enabled and not rb.agents)

    # Governance state is surfaced, not silently treated as cleared/validated.
    legal = audit_legal(use_case="internal", topics=["cena", "potraviny"], allow_own_estimates=False)
    checks["licensing_policy_mode"] = legal.get("mode")
    checks["licensing_mode"] = legal.get("mode")
    checks["licensing_status"] = legal["status"]
    checks["licensing_evidence_present"] = bool(legal.get("licensing_evidence_present", False))
    checks["legal_unresolved_sources"] = len(legal["warnings"])
    validation = assert_validation_ready(use_case="internal")
    checks["validation_status"] = validation.get("status", "NOT_VALIDATED")
    readiness = readiness_for_topics(["cena", "potraviny"], panel=panel_df)
    checks["domain_evidence_coverage"] = {"overall": readiness["overall"], "minimum_score": readiness["minimum_score"], "domains": readiness["domains"]}

    panel = Panel.load(PANEL_PATH, hlasit=False)
    sample = sample_representative(panel, 128, seed=20260814)
    checks["unique_pps_sample"] = sample["_zdroj_index"].nunique() == 128

    v = run_dotaznik(brief["otazky"], n=32, filtry=brief.get("filtry"),
                     nazev="selftest", mode="dry", seed=20260814,
                     persona_mode="full", response_mode="probability",
                     allow_own_estimates=False, kontext_udalosti=None,
                     ulozit=False, checkpoint=False, tichy=True)
    q = kontrola(v)
    expected_dry_warning_fragments={"synteticke verbatimy se opakuji","hodne respondentu ma uplne stejnou sadu"}
    observed_warning_text={str(x.get("nalez","")) for x in q.get("nalezy",[]) if x.get("uroven")=="VAROVANI"}
    unexpected=[x for x in observed_warning_text if not any(f in x for f in expected_dry_warning_fragments)]
    checks["dry_run_qc"] = q["uroven"]
    checks["dry_run_qc_contract"] = {
        "status":"PASS" if q["uroven"]!="KRITICKE" and not unexpected else "FAIL",
        "expected_dry_mock_warnings":sorted(expected_dry_warning_fragments),
        "unexpected_warnings":unexpected,
        "note":"Dry mock intentionally reuses simple verbatim templates and may duplicate response vectors; any other warning fails selftest."
    }
    checks["dry_run_call_errors"] = v["n_chyb_call"]
    checks["expected_probability_output"] = all(
        (x.get("typ") not in {"vyber", "skala"}) or
        ("expected_pct" in x or "expected_mean" in x)
        for x in v["vysledky"].values()
    )
    checks["own_estimates_default_off"] = not bool(v.get("allow_own_estimates", False))
    checks["sampling"] = str(v.get("sampling") or "").startswith("representative_balanced_without_replacement")

    # Full Simulation must remain fully testable without API keys. The self-test
    # uses two DRY worlds and temporary stores, proving stochastic inoculation,
    # freeze manifest and benchmark eligibility without creating persistent runs.
    import full_simulation as fs
    with tempfile.TemporaryDirectory() as fstd:
        fstd=Path(fstd); rr=fstd/"runs"; bb=fstd/"bench"; rr.mkdir(); bb.mkdir()
        spec={"topic":"selftest product","domain":"selftest","objective":"blind_forecast",
              "questions":[{"id":"fs_q1","text":"Vyzkoušel/a byste tento koncept?","kategorie":["Ano","Ne"]}],
              "n":50,"worlds":2,"seed":20260816,"mode":"dry","model":"sonnet",
              "research_enabled":False,"world_model_provider":"heuristic",
              "include_core_baseline":False,"include_demographics_baseline":False,"use_learning_profile":False}
        with patch.object(fs,"RUN_ROOT",rr), patch.object(fs,"BENCH_ROOT",bb):
            fr=fs.run_full_simulation(spec,panel_path=PANEL_PATH)
            fd=rr/fr["run_id"]
            checks["fullsim_dry_freeze"]=(fd/"FROZEN.lock").exists() and (fd/"prediction_manifest.json").exists()
            checks["fullsim_blind_eligible"]=bool(fr["manifest"].get("benchmark_eligible"))
            checks["fullsim_worlds"]=int(fr["manifest"].get("worlds",0))
            checks["fullsim_1015_router"]=bool((fr.get("decision_router") or {}).get("recommended_mode"))
            checks["fullsim_synthetic_response_sample"]=(fd/"synthetic_response_sample.csv.gz").exists()
            from fullsim_learning import register_human_calibration
            calrows=[{"fs_q1":"Ano" if i<30 else "Ne","weight":1.0} for i in range(50)]
            hc=register_human_calibration(fr["run_id"],{"source":"selftest pre-truth","rows":calrows},run_root=rr,bench_root=bb,sizes=(25,50),seed=1)
            checks["fullsim_hybrid_rectification"]=bool(hc.get("predictions")) and bool(hc.get("stability",{}).get("recommended_n"))

    with tempfile.TemporaryDirectory() as td:
        xp = export_xlsx(v, Path(td)/"selftest.xlsx")
        hp = export_html(v, Path(td)/"selftest.html")
        checks["xlsx_report"] = xp.exists() and xp.stat().st_size > 1000
        checks["html_report"] = hp.exists() and hp.stat().st_size > 500

    hard_ok = (
        checks["panel_diagnostics"] == "OK" and
        checks["data_contract_failures"] == 0 and
        checks["holdout_hard_failures"] == 0 and
        checks["questionnaire_lint"] == "OK" and
        checks["research_context_off_true_off"] and
        checks["licensing_status"] in {"PASS","REVIEW_REQUIRED"} and
        checks["dry_run_call_errors"] == 0 and
        checks["dry_run_qc_contract"]["status"] == "PASS" and
        checks["expected_probability_output"] and
        checks["unique_pps_sample"] and
        checks["own_estimates_default_off"] and
        checks["sampling"] and
        checks["fullsim_dry_freeze"] and checks["fullsim_blind_eligible"] and checks["fullsim_worlds"] == 2 and
        checks["fullsim_1015_router"] and checks["fullsim_synthetic_response_sample"] and checks["fullsim_hybrid_rectification"] and
        checks["xlsx_report"] and checks["html_report"]
    )
    print(json.dumps({"status": "PASS" if hard_ok else "FAIL", "checks": checks},
                     ensure_ascii=False, indent=2))
    return 0 if hard_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
