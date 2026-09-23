#!/usr/bin/env python3
"""Fast bounded handoff integrity verifier.

This is intentionally not the regression suite.  Release testing is run separately.
The verifier checks package hygiene and offline environment readiness only, so it is
safe to run on a freshly unpacked handoff without API calls.
"""
from __future__ import annotations
import json, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def run(cmd, timeout=30):
    try:
        p=subprocess.run(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                         text=True,timeout=timeout)
        shown=" ".join(map(str,cmd)).replace(str(sys.executable),"python")
        clean=p.stdout.replace(str(ROOT),"<PROJECT_ROOT>").replace(str(sys.executable),"python")
        return {"command":shown,"returncode":p.returncode,
                "output":clean[-12000:],"timed_out":False}
    except subprocess.TimeoutExpired as exc:
        out=exc.stdout or ""
        if isinstance(out,bytes): out=out.decode('utf-8',errors='replace')
        return {"command":" ".join(map(str,cmd)),"returncode":124,
                "output":str(out)[-12000:],"timed_out":True,
                "error":f"timeout after {timeout}s"}

def main():
    checks={
        "secret_scan":run([sys.executable,"secret_scan.py"]),
        "portability":run([sys.executable,"portability_check.py"]),
        "doctor_offline":run([sys.executable,"doctor.py","--json"],timeout=45),
    }
    obj={
        "generated_at_utc":time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        "checks":checks,
        "regression_suite_command":"python -m pytest -q",
        "selftest_command":"python selftest.py",
        "release_gate_command":"python release_gate.py --skip-tests",
        "note":"Predictive/commercial validation remains a separate human-evidence gate.",
        "pass":all(v['returncode']==0 and not v.get('timed_out') for v in checks.values()),
    }
    out=ROOT/'HANDOFF_VERIFICATION.json'
    out.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(out)
    print('HANDOFF_VERIFICATION_PASS' if obj['pass'] else 'HANDOFF_VERIFICATION_FAIL')
    return 0 if obj['pass'] else 1
if __name__=='__main__': raise SystemExit(main())
