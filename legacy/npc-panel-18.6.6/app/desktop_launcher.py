#!/usr/bin/env python3
"""Friendly local launcher for NPC Panel 17.1.2.

This file uses only the Python standard library. It never performs a paid API call
without an explicit menu choice. The normal entry point is the integrated web workflow; this file remains an advanced diagnostics launcher.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def _ensure_env_file() -> Path:
    env = ROOT / ".env"
    if not env.exists():
        src = ROOT / ".env.example"
        if src.exists():
            shutil.copy2(src, env)
            print(f"Vytvořen {env.name} z .env.example. API klíče zatím nejsou vyplněné.")
    return env


def _run(args: list[str], *, env: dict | None = None) -> int:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    print("\n$", " ".join([PY, *args]))
    return subprocess.call([PY, *args], cwd=ROOT, env=merged)


def _open_path(p: Path) -> None:
    p = p.resolve()
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(p))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
    except Exception:
        print("Otevři ručně:", p)


def start_web() -> int:
    print("\nSpouštím produktové UI: http://127.0.0.1:8766")
    print("Bez AI = technická zkouška bez respondentních AI volání. Server ukončíš Ctrl+C.\n")
    return _run(["ui_server.py", "--host", "127.0.0.1", "--port", "8766"])


def configure_keys() -> None:
    p = _ensure_env_file()
    print("\nDo .env vlož ANTHROPIC_API_KEY pro běh S AI.")
    print("OPENAI_API_KEY je potřeba jen pro Research Context ON.")
    _open_path(p)


def open_outputs() -> None:
    p = ROOT / "runs"
    p.mkdir(exist_ok=True)
    _open_path(p)


def menu() -> int:
    _ensure_env_file()
    while True:
        print("\n" + "=" * 68)
        print("NPC PANEL 17.1.2 — POKROČILÁ DIAGNOSTIKA")
        print("=" * 68)
        print("1  Otevřít produktové webové UI")
        print("2  Offline diagnostika + všechny testy")
        print("3  Bez AI — technické demo standardního survey")
        print("4  Bez AI — technické demo VÝZKUM")
        print("5  Evidence audit v14")
        print("6  Ověřit API klíče/modely (může udělat miniaturní placený call)")
        print("7  Upravit .env / API klíče")
        print("8  Otevřít složku runs")
        print("9  Bez AI — technické demo ensemble")
        print("0  Konec")
        choice = input("\nVolba: ").strip()
        if choice == "1":
            start_web()
        elif choice == "2":
            _run(["doctor.py", "--tests"])
        elif choice == "3":
            _run(["npc.py", "survey", "brief_ukazka.json", "--", "--dry"])
        elif choice == "4":
            _run(["npc.py", "study", "examples/study_segmentace_quick.json", "--", "--mode", "dry", "--out", "runs/study_demo"])
        elif choice == "5":
            _run(["npc.py", "evidence", "--panel", "FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz", "--out", "runs/EFFECTIVE_EVIDENCE_AUDIT_v17.csv"])
        elif choice == "6":
            print("\nPOZOR: Anthropic fallback může udělat velmi malý placený request.")
            if input("Pokračovat? [a/N]: ").strip().lower() in {"a", "ano", "y", "yes"}:
                _run(["doctor.py", "--live-providers"])
        elif choice == "7":
            configure_keys()
        elif choice == "8":
            open_outputs()
        elif choice == "9":
            _run(["npc.py", "survey", "examples/ensemble_brief.json", "--", "--dry"])
        elif choice == "0":
            return 0
        else:
            print("Neznámá volba.")


if __name__ == "__main__":
    raise SystemExit(menu())
