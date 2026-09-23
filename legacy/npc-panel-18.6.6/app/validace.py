"""Validace panelu proti znamemu realnemu vysledku.

Pouziti:
    from validace import validuj
    v = validuj(
        otazka="Koho byste volil, kdyby byly volby tento vikend?",
        realita={"ANO": 30.5, "ODS": 13.2, "Pirati": 12.1, "SPD": 8.0},
        n=400,
    )
    print(v["report"])

Metrika:
  MAE   — prumerna absolutni odchylka v procentnich bodech
  MAX   — nejhorsi kategorie
  r     — Pearsonova korelace poradi kategorii

Interpretacni prah (doporuceni, ne standard oboru):
  MAE < 3 p.b.  panel pouzitelny pro odhad urovni
  MAE 3-7 p.b.  pouzitelny pro poradi a smer, ne pro cisla
  MAE > 7 p.b.  nepouzitelny bez rekalibrace

ZMENA 17.1.1 — engine parity
----------------------------
Puvodni verze volala ``pipeline.run_pruzkum``, tedy LEGACY respondentni engine
(volny JSON + regex fallback, vsechny otazky najednou, jiny system prompt).
Produkcni klientsky vystup ale vznika v ``dotaznik.run_dotaznik`` (forced tool
use, sekvencni promptovani, historie rozhovoru, probability mode). Validace
tedy merila jiny system, nez ktery se odesila klientovi, a jeji MAE pro produkt
neplatilo. Modul nyni pouziva vyhradne produkcni engine.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from dotaznik import run_dotaznik
from runtime_config import RUN_DEFAULTS, resolve_provider_model
from provider_auth import get_ai_provider, normalize_ai_provider

ENGINE = "dotaznik.run_dotaznik"


def validuj(
    otazka: str,
    realita: dict[str, float],
    n: int = 400,
    *,
    opakovani: int = 1,
    response_mode: str = "probability",
    persona_mode: str = "calibrated",
    **kw: Any,
) -> dict:
    kategorie = list(realita.keys())
    seed0 = int(kw.pop("seed", 1000))
    provider = normalize_ai_provider(kw.pop("provider", get_ai_provider()))
    default_policy = ("strict_openai" if provider == "openai" else
                      "strict_claude_code_subscription" if provider == "claude_code_subscription" else
                      "strict_anthropic")
    provider_policy = kw.pop("provider_policy", default_policy)
    model = resolve_provider_model(provider, kw.pop("model", RUN_DEFAULTS["model"]))
    behy = []
    for i in range(opakovani):
        v = run_dotaznik(
            [{"id": "V1", "text": otazka, "typ": "vyber",
              "kategorie": kategorie, "povolit_nevim": False}],
            n=n, seed=seed0 + i, ulozit=False, tichy=True,
            response_mode=response_mode, persona_mode=persona_mode, model=model, provider_policy=provider_policy, **kw,
        )
        a = v["vysledky"]["V1"]
        # expected_pct = vazeny prumer LLM pravdepodobnosti; celkem_pct = vylosovane
        # odpovedi. Pro validaci proti agregatu je spravny estimator ten prvni,
        # protoze losovani jen pridava Monte Carlo sum navic k realne chybe.
        behy.append(a.get("expected_pct") or a.get("celkem_pct", {}))

    pred = {k: float(np.mean([b.get(k, 0.0) for b in behy])) for k in kategorie}
    sd = {k: float(np.std([b.get(k, 0.0) for b in behy])) for k in kategorie}

    delty = {k: round(pred[k] - realita[k], 1) for k in kategorie}
    mae = round(float(np.mean([abs(d) for d in delty.values()])), 2)
    mx = max(delty, key=lambda k: abs(delty[k]))
    r = float(np.corrcoef([pred[k] for k in kategorie],
                          [realita[k] for k in kategorie])[0, 1])

    radky = [f"VALIDACE  n={n}  behu={opakovani}  engine={ENGINE}",
             f"{'kategorie':28} {'panel':>7} {'realita':>8} {'delta':>7}"]
    for k in sorted(kategorie, key=lambda k: -realita[k]):
        radky.append(f"{k[:28]:28} {pred[k]:7.1f} {realita[k]:8.1f} {delty[k]:+7.1f}")
    radky += ["",
              f"MAE = {mae} p.b.   nejhorsi: {mx} ({delty[mx]:+} p.b.)   r = {r:.3f}",
              "verdikt: " + ("pouzitelne pro cisla" if mae < 3
                             else "pouzitelne pro poradi/smer" if mae < 7
                             else "NEPOUZITELNE bez rekalibrace")]

    return {"predikce": pred, "rozptyl_beh": sd, "realita": realita,
            "delty": delty, "mae": mae, "r": round(r, 3),
            "engine": ENGINE, "provider": provider, "provider_policy": provider_policy, "model": model, "response_mode": response_mode, "persona_mode": persona_mode, "report": "\n".join(radky)}
