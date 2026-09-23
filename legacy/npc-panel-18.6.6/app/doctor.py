#!/usr/bin/env python3
"""Environment and handoff diagnostics for NPC Panel.

Default mode is offline. User-facing LIVE runtime is Claude Code subscription only.
Legacy API diagnostics remain readable for historical compatibility but are not a product fallback.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from env_loader import load_dotenv
load_dotenv()
from provider_auth import has_anthropic_key, has_openai_key, anthropic_key_info, probe_anthropic

ROOT = Path(__file__).resolve().parent
MIN_PY = (3, 11)
REQUIRED_FILES = [
    "VERSION", "PROJECT_POLICY.json", "requirements.txt", ".env.example",
    "FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz", "DATA_PROVENANCE_REGISTRY_v17.csv",
    "PERSONA_SIGNAL_CATALOG_v17.csv", "BUILTIN_SUBPANELS_v17.json",
    "BACKBONE_CENSUS_2021_TARGETS.csv", "CENSUS_LABOUR_FORCE_TARGETS_v17.csv",
    "DONOR_BLOCK_REGISTRY.json", "CORE_JOINT_STATUS.json", "VALIDATION_PROTOCOL.md",
    "ui_server.py", "prototype_server.py", "validation_gate.py", "validation_status.py",
    "core_joint.py", "run_store.py", "provider_auth.py", "runtime_diagnostic.py", "ui_app.html",
]
CORE_PACKAGES = {"pandas", "numpy", "openpyxl", "scikit-learn"}
PACKAGE_IMPORTS = {
    "pandas": "pandas", "numpy": "numpy", "openpyxl": "openpyxl",
    "scikit-learn": "sklearn", "python-docx": "docx", "pypdf": "pypdf",
    "anthropic": "anthropic", "openai": "openai",
}


def _pkg_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _offline_checks(run_tests: bool = False) -> dict:
    out: dict = {
        "python": {
            "version": platform.python_version(),
            "supported": sys.version_info >= MIN_PY,
        },
        "files": {}, "packages": {}, "runtime": {}, "keys": {}, "tests": None,
    }
    for name in REQUIRED_FILES:
        p = ROOT / name
        out["files"][name] = {"exists": p.exists(), "bytes": p.stat().st_size if p.exists() else 0}
    for package, module in PACKAGE_IMPORTS.items():
        ver = _pkg_version(package)
        import_ok = False
        error = None
        if ver is not None:
            try:
                importlib.import_module(module)
                import_ok = True
            except Exception as exc:
                error = str(exc)[:240]
        out["packages"][package] = {"version": ver, "import_ok": import_ok, "error": error}

    out["keys"] = {
        "ANTHROPIC_API_KEY": has_anthropic_key(),
        "OPENAI_API_KEY": has_openai_key(),
        "anthropic": anthropic_key_info(),
        "note": "User-facing LIVE používá explicitně zvolený Claude Code, Claude API nebo OpenAI API. Při chybě krok failne; silent cross-provider/local fallback je vypnutý.",
    }
    try:
        from claude_code_setup import auth_status as _claude_auth_status
        _cs = _claude_auth_status()
        out["keys"]["claude_code_subscription"] = {
            "ready": bool(_cs.get("subscription_verified")),
            "status": _cs.get("status") or _cs.get("message") or "UNKNOWN",
        }
    except Exception as _exc:
        out["keys"]["claude_code_subscription"] = {"ready": False, "status": "UNAVAILABLE", "error": str(_exc)[:240]}

    try:
        from runtime_config import RELEASE, DEFAULT_MODEL, DEFAULT_OPENAI_RESEARCH_MODEL, DEFAULT_ANTHROPIC_RESEARCH_MODEL
        from pipeline import PANEL_PATH
        from diagnostika import diagnostika
        from legal_gate import audit_legal
        from validation_gate import assert_validation_ready
        from system_fingerprint import build_system_fingerprint
        from core_joint import load_joint_status
        import pandas as pd

        panel_path = Path(PANEL_PATH)
        panel = pd.read_csv(panel_path, low_memory=False)
        d = diagnostika(panel)
        legal = audit_legal(use_case="commercial", topics=[], allow_own_estimates=False)
        validation = assert_validation_ready(use_case="internal")
        fp = build_system_fingerprint(panel_path); joint=load_joint_status()
        out["runtime"] = {
            "release": RELEASE,
            "panel_path": str(panel_path),
            "panel_rows": int(len(panel)),
            "panel_diagnostics": d.get("uroven"),
            "system_sha256": fp.get("system_sha256"),
            "survey_model_default": DEFAULT_MODEL,
            "research_runtime": "claude_code_subscription",
            "research_model_default": DEFAULT_ANTHROPIC_RESEARCH_MODEL,
            "licensing_mode": legal.get("mode"),
            "licensing_status": legal.get("status"),
            "validation_status": validation.get("status", "NOT_VALIDATED"),
            "core_joint_status": joint.get("status"),
            "core_joint_client_outputs_allowed": bool(joint.get("client_joint_outputs_allowed")),
        }
    except Exception as exc:
        out["runtime"] = {"error": str(exc)[:1000]}

    if run_tests:
        # Release ZIP does not always ship a tests/ package. Falling back to the
        # bundled selftest keeps doctor useful instead of producing a false FAIL.
        if (ROOT / "tests").is_dir():
            cmd = [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"]
            suite = "unittest"
        else:
            cmd = [sys.executable, str(ROOT / "selftest.py")]
            suite = "selftest.py (tests/ not packaged)"
        cp = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out["tests"] = {
            "pass": cp.returncode == 0,
            "suite": suite,
            "tail": "\n".join(cp.stdout.splitlines()[-8:]),
        }

    core_packages_ok = all(out["packages"][k]["import_ok"] for k in CORE_PACKAGES)
    full_packages_ok = all(v["import_ok"] for v in out["packages"].values())
    out["full_dependencies_ready"] = bool(full_packages_ok)
    required_files_ok = all(v["exists"] for v in out["files"].values())
    runtime_ok = not out["runtime"].get("error") and out["runtime"].get("panel_diagnostics") == "OK"
    tests_ok = (out["tests"] is None) or bool(out["tests"]["pass"])
    out["offline_ready"] = bool(out["python"]["supported"] and core_packages_ok and required_files_ok and runtime_ok and tests_ok)
    return out


def _live_provider_checks() -> dict:
    from runtime_config import DEFAULT_MODEL
    from provider_auth import probe_openai, has_anthropic_key, has_openai_key
    result = {"openai": {}, "anthropic": {}}
    result["anthropic"] = probe_anthropic(DEFAULT_MODEL) if has_anthropic_key() else {"ok":False,"kind":"MISSING","message":"Anthropic key missing"}
    result["openai"] = probe_openai() if has_openai_key() else {"ok":False,"kind":"MISSING","message":"OpenAI key missing"}
    result["any_provider_ok"] = bool(result["anthropic"].get("ok") or result["openai"].get("ok"))
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="NPC Panel handoff doctor (offline by default)")
    ap.add_argument("--tests", action="store_true", help="run the full unittest suite")
    ap.add_argument("--live-providers", action="store_true", help="intentionally call provider APIs to validate keys/models")
    ap.add_argument("--json", action="store_true", help="machine-readable output only")
    ap.add_argument("--full-deps", action="store_true", help="also require optional/live/import SDK dependencies")
    a = ap.parse_args()
    out = _offline_checks(run_tests=a.tests)
    if a.live_providers:
        out["live_providers"] = _live_provider_checks()
        out["live_ready"] = bool(out["live_providers"].get("any_provider_ok"))
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print("NPC PANEL DOCTOR")
        print("================")
        print(f"Offline ready: {'YES' if out['offline_ready'] else 'NO'}")
        print(f"Python: {out['python']['version']} | supported={out['python']['supported']}")
        rt = out.get("runtime", {})
        if rt.get("error"):
            print("Runtime ERROR:", rt["error"])
        else:
            print(f"Release: {rt.get('release')} | panel rows={rt.get('panel_rows')} | diagnostics={rt.get('panel_diagnostics')}")
            print(f"Validation: {rt.get('validation_status')} | licensing mode={rt.get('licensing_mode')} status={rt.get('licensing_status')}")
            print(f"Fingerprint: {rt.get('system_sha256')}")
        missing = [k for k, v in out["packages"].items() if not v["import_ok"]]
        print("Core offline packages:", "OK" if all(out["packages"][k]["import_ok"] for k in CORE_PACKAGES) else "MISSING")
        print("Full dependencies:", "OK" if out["full_dependencies_ready"] else "MISSING/ERROR: " + ", ".join(missing))
        print("API keys: Anthropic=" + ("present" if out["keys"]["ANTHROPIC_API_KEY"] else "missing") +
              ", OpenAI=" + ("present" if out["keys"]["OPENAI_API_KEY"] else "missing"))
        if out.get("tests"):
            print("Tests:", "PASS" if out["tests"]["pass"] else "FAIL")
        if a.live_providers:
            print("Live providers:", json.dumps(out["live_providers"], ensure_ascii=False))
    if not out["offline_ready"]:
        return 1
    if a.full_deps and not out["full_dependencies_ready"]:
        return 3
    if a.live_providers and not out.get("live_ready"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
