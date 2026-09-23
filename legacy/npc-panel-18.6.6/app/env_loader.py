"""Minimal .env loader for local desktop use.

No external dependency is required. Existing environment variables always win.
Only a conservative KEY=VALUE syntax is supported; this is intentional for secrets.
"""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_dotenv(path: str | Path | None = None) -> Path | None:
    p = Path(path) if path else ROOT / ".env"
    if not p.exists() or not p.is_file():
        return None
    for raw in p.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not (key[0].isalpha() or key[0] == "_") or not all(c.isalnum() or c == "_" for c in key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)
    return p


LOADED_ENV_FILE = load_dotenv()
