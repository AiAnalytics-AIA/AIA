"""Reproducibility manifest and file hashing."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime_config import RELEASE
from system_fingerprint import build_system_fingerprint


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_manifest(*, run_id: str, panel_path: str | Path, brief: dict[str, Any],
                   model: str, mode: str, seed: int | None, n: int,
                   response_mode: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    p = Path(panel_path)
    out = {
        "release": RELEASE,
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "panel_path": str(p.resolve()),
        "panel_sha256": sha256_file(p),
        "brief_sha256": sha256_json(brief),
        "model": model,
        "mode": mode,
        "response_mode": response_mode,
        "seed": seed,
        "n": n,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    fp = build_system_fingerprint(p)
    out["system_sha256"] = fp["system_sha256"]
    out["runtime_code_sha256"] = fp["runtime_code_sha256"]
    out["model_routing_sha256"] = fp["model_routing_sha256"]
    if extra:
        out.update(extra)
    return out


def save_manifest(manifest: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
