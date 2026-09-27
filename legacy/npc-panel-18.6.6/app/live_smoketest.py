#!/usr/bin/env python3
"""Minimal paid transport smoke test (3 synthetic respondents, 1 question)."""
from __future__ import annotations
import os
from env_loader import load_dotenv
load_dotenv()
from dotaznik import run_dotaznik
from runtime_config import DEFAULT_MODEL


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("SKIP: ANTHROPIC_API_KEY není nastaven. Nastav klíč a spusť znovu.")
        return 2
    qs=[{"id":"SMOKE1","text":"Dáváte přednost nákupu potravin osobně, nebo online?",
         "typ":"vyber","kategorie":["spíše osobně","spíše online","je mi to jedno"]}]
    v=run_dotaznik(qs,n=3,nazev="live-smoke",model=DEFAULT_MODEL,mode="sync",seed=91001,
                   response_mode="probability",ulozit=False,checkpoint=False,tichy=False)
    a=v["vysledky"]["SMOKE1"]
    ok=(v["n_chyb_call"]==0 and "expected_pct" in a and a.get("n_platnych")==3)
    print("PASS" if ok else "FAIL", {"model":v["model"],"call_errors":v["n_chyb_call"],
                                     "expected_pct":a.get("expected_pct"),"cost_usd":v["naklady_usd"]})
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
