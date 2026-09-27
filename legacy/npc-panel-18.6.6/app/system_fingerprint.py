"""Immutable system fingerprint for validation/release evidence.

A predictive-validity claim is valid only for the exact system that was benchmarked.
Changing panel bytes, runtime code, model routing or core data contracts changes the
fingerprint and automatically invalidates old evidence.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable
import hashlib
import json
import sys
from importlib import metadata

ROOT = Path(__file__).resolve().parent

# Docs/reports/tests are intentionally excluded: validation tracks behavior-changing
# runtime/config/data, not prose. Python test files are excluded from the runtime hash.
# Predictive/system-governance code only. Handoff/diagnostic wrappers are excluded so
# editing a README helper, doctor, packaging check or release display cannot falsely
# invalidate a human predictive-validation certificate.
NON_BEHAVIORAL_TOOLING = {
    "doctor.py", "handoff_verify.py", "secret_scan.py", "portability_check.py",
    "selftest.py", "release_gate.py", "release_scorecard.py", "prototype_server.py",
    "ui_server.py", "desktop_launcher.py", "npc.py", "audience.py", "study_validity.py",
    "cost_estimator.py", "joint_structure_audit.py", "core_joint.py", "run_store.py",
    "live_smoketest.py", "make_mock_panel.py", "coherence_audit_v17.py", "validate_v17.py",
}
RUNTIME_FILES = [
    p for p in ROOT.glob("*.py")
    if not p.name.startswith("test_") and p.name not in NON_BEHAVIORAL_TOOLING
] + [p for p in (ROOT / "npc_ingest").glob("*.py") if p.name != "__init__.py"]
CONFIG_FILES = [
    ROOT / "requirements.txt",
    ROOT / "PROJECT_POLICY.json",
    ROOT / "PRODUCT_POLICY.json",
    ROOT / "CORE_JOINT_STATUS.json",
    ROOT / "PERSONA_SIGNAL_CATALOG_v17.csv",
    ROOT / "DATA_PROVENANCE_REGISTRY_v17.csv",
    ROOT / "DONOR_BLOCK_REGISTRY.json",
    ROOT / "BACKBONE_CENSUS_2021_TARGETS.csv",
    ROOT / "CENSUS_LABOUR_FORCE_TARGETS_v17.csv",
    ROOT / "INSTRUMENT_LIBRARY_v1.json",
]


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _tree_hash(paths: Iterable[Path]) -> tuple[str, dict[str, str]]:
    entries: dict[str, str] = {}
    for p in sorted({Path(x).resolve() for x in paths if Path(x).exists()}):
        entries[str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else p.name] = sha256_file(p)
    raw = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest(), entries


def build_system_fingerprint(panel_path: str | Path | None = None) -> dict:
    from pipeline import PANEL_PATH
    from runtime_config import RELEASE, MODELS, DEFAULT_MODEL

    panel = Path(panel_path or PANEL_PATH).resolve()
    code_hash, code_files = _tree_hash(RUNTIME_FILES)
    config_hash, config_files = _tree_hash(CONFIG_FILES)
    model_map = {k: v.model_id for k, v in MODELS.items()}
    model_raw = json.dumps({"models": model_map, "default": DEFAULT_MODEL}, sort_keys=True).encode("utf-8")
    model_hash = hashlib.sha256(model_raw).hexdigest()
    packages = {}
    for pkg in ("anthropic", "openai", "numpy", "pandas", "scikit-learn"):
        try:
            packages[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            packages[pkg] = "NOT_INSTALLED"
    environment = {"python": sys.version.split()[0], "packages": packages}
    env_hash = hashlib.sha256(json.dumps(environment, sort_keys=True).encode("utf-8")).hexdigest()
    obj = {
        "release": RELEASE,
        "panel_sha256": sha256_file(panel),
        "runtime_code_sha256": code_hash,
        "config_sha256": config_hash,
        "model_routing_sha256": model_hash,
        "model_routing": model_map,
        "environment": environment,
        "environment_sha256": env_hash,
    }
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    obj["system_sha256"] = hashlib.sha256(raw).hexdigest()
    obj["runtime_files"] = code_files
    obj["config_files"] = config_files
    return obj


def current_system_sha256(panel_path: str | Path | None = None) -> str:
    return build_system_fingerprint(panel_path)["system_sha256"]
