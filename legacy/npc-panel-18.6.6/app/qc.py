"""
NPC PANEL — qc.py
Kontrola kvality behu. Pousti se automaticky po kazdem behu.

Syntetický panel selhava jinak nez realny teren. Realny teren ma problem
s podvodniky a nepozornosti; syntetický panel ma problem s tim, ze model
ignoruje personu a generuje sum kolem jednoho prumeru. Tenhle modul hleda
prave tohle.

    from qc import kontrola, tabulka_qc
    q = kontrola(vysledky)
    print(tabulka_qc(q))
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

SEGMENTY_QC = ["pohlavi", "vek_skupina", "vzdelani", "kraj", "trida_spolecenska"]

# prahy — moje kalibrace, ne standard oboru; uprav podle prvnich ostrych behu
PRAHY = {
    "chybovost_max": 0.05,       # podil neparsovatelnych / chybnych odpovedi
    "nevim_min": 0.02,           # pod tim je panel nerealne rozhodny
    "nevim_max": 0.35,           # nad tim je otazka spatne polozena
    "koncentrace_max": 0.90,     # jedna kategorie nad 90 % = degenerovana otazka
    "cramer_min": 0.08,          # pod tim persona neovlivnuje odpoved
    "straightline_max": 0.15,    # podil respondentu se stejnou odpovedi na vse
    "duplicity_max": 0.10,       # podil identickych vektoru odpovedi
    "verbatim_unikaty_min": 0.70,
    "mean_maxprob_max": 0.95,    # probability mode: almost deterministic model
    "mean_entropy_min": 0.08,    # normalized 0..1; near-zero = collapse
    "behavior_shift_warn": 0.35, # mean L1 probability shift; response-process layer dominates latent preference
}


def _cramer_v(a: pd.Series, b: pd.Series) -> float:
    """Cramerovo V s Bergsmovou korekci na pocet kategorii.

    Bez korekce vychazi u promennych s mnoha kategoriemi (kraj: 14 urovni)
    kladne V i pri uplne nahodnych datech — u n=400 klidne 0,15. Korekce
    posouva nulovou hypotezu zpet na 0, takze prah 0,08 neco znamena.
    """
    tab = pd.crosstab(a, b)
    r, k = tab.shape
    if r < 2 or k < 2:
        return 0.0
    n = tab.to_numpy().sum()
    if n < 2:
        return 0.0
    ocek = np.outer(tab.sum(1), tab.sum(0)) / n
    with np.errstate(divide="ignore", invalid="ignore"):
        chi2 = np.nansum((tab.to_numpy() - ocek) ** 2 / ocek)
    phi2 = max(0.0, chi2 / n - (k - 1) * (r - 1) / (n - 1))
    rk = r - (r - 1) ** 2 / (n - 1)
    kk = k - (k - 1) ** 2 / (n - 1)
    jm = min(kk - 1, rk - 1)
    return float(np.sqrt(phi2 / jm)) if jm > 0 else 0.0


def _otazky_z_vysledku(v: dict) -> list[dict]:
    if "otazky" in v:
        return v["otazky"]
    return [{"id": "odpoved", "text": v.get("otazka", ""), "typ": "vyber"}]


def kontrola(v: dict, prahy: dict[str, float] | None = None) -> dict:
    """Vrati nalezy + celkovy verdikt. Nemeni data."""
    p = {**PRAHY, **(prahy or {})}
    detail: pd.DataFrame = v["detail"]
    otazky = _otazky_z_vysledku(v)
    nalezy: list[dict[str, Any]] = []
    metriky: dict[str, Any] = {}

    def flag(uroven: str, kde: str, co: str, hodnota: Any = None) -> None:
        nalezy.append({"uroven": uroven, "kde": kde, "nalez": co, "hodnota": hodnota})

    # --- 1. technicka chybovost
    n = len(detail)
    chyb = int(detail["_chyba"].notna().sum()) if "_chyba" in detail else v.get("n_chyb", 0)
    metriky["chybovost"] = round(chyb / n, 4) if n else 0.0
    if metriky["chybovost"] > p["chybovost_max"]:
        flag("KRITICKE", "beh", "vysoka chybovost volani / neparsovatelne odpovedi",
             metriky["chybovost"])

    seg = v.get("segment") or {}
    if seg.get("mode") not in (None, "none"):
        ess = float(seg.get("ess_population") or 0)
        metriky["segment_ess"] = round(ess, 2)
        metriky["segment_confidence_class"] = seg.get("confidence_class")
        if seg.get("warning"):
            flag("KRITICKE", "segment", str(seg.get("warning")), ess)
        if seg.get("confidence_class") == "C":
            flag("VAROVANI", "segment", "exploracni segment C nema externi prevalencni kotvu",
                 seg.get("prevalence_calibrated"))

    zavrene = [o for o in otazky if o["typ"] in ("vyber", "multi")]
    skaly = [o for o in otazky if o["typ"] == "skala"]
    otevrene = [o for o in otazky if o["typ"] == "otevrena"]

    # --- 2. per otazka: chybejici, nevim, koncentrace, diferenciace
    per_otazku = {}
    for o in otazky:
        oid = o["id"]
        if oid not in detail.columns:
            continue
        elig_col = f"_eligible_{oid}"
        base = detail[detail[elig_col].fillna(False)] if elig_col in detail.columns else detail
        s = base[oid]
        ok = s.notna()
        m: dict[str, Any] = {"n_eligible": int(len(base)),
                             "n_platnych": int(ok.sum()),
                             "podil_chybi": round(1 - ok.mean(), 3) if len(base) else 0.0}
        if m["podil_chybi"] > 0.20:
            flag("VAROVANI", oid, "vic nez 20 % respondentu neodpovedelo",
                 m["podil_chybi"])

        if o["typ"] == "vyber":
            vals = s[ok].astype(str)
            podily = vals.value_counts(normalize=True)
            m["nevim"] = round(float(podily.get("Nevím / neodpovím", 0.0)), 3)
            m["koncentrace"] = round(float(podily.max()), 3)
            if m["nevim"] < p["nevim_min"]:
                flag("VAROVANI", oid,
                     "temer nikdo neodpovedel 'nevim' — nerealne rozhodne", m["nevim"])
            if m["nevim"] > p["nevim_max"]:
                flag("VAROVANI", oid, "prilis mnoho 'nevim' — otazka je nejasna",
                     m["nevim"])
            if m["koncentrace"] > p["koncentrace_max"]:
                flag("VAROVANI", oid, "jedna kategorie pohltila skoro vse",
                     m["koncentrace"])

            v_seg = {}
            for seg in SEGMENTY_QC:
                if seg in detail.columns:
                    v_seg[seg] = round(_cramer_v(base.loc[ok, seg], vals), 3)
            m["cramer_v"] = v_seg
            if v_seg and max(v_seg.values()) < p["cramer_min"]:
                flag("VAROVANI", oid,
                     "slaba demograficka diferenciace; sama o sobe NEmeri efekt persony",
                     max(v_seg.values()))

        elif o["typ"] == "skala":
            x = pd.to_numeric(s[ok], errors="coerce")
            m.update({"prumer": round(float(x.mean()), 2),
                      "sd": round(float(x.std()), 2)})
            if m["sd"] < 0.5:
                flag("VAROVANI", oid, "temer nulovy rozptyl na skale", m["sd"])
            rozdily = {}
            for seg in SEGMENTY_QC:
                if seg in detail.columns:
                    g = x.groupby(base.loc[ok, seg]).mean()
                    if len(g) > 1:
                        rozdily[seg] = round(float(g.max() - g.min()), 2)
            m["rozpeti_prumeru_segmentu"] = rozdily
            if rozdily and max(rozdily.values()) < 0.3 * (x.max() - x.min() or 1) * 0.2:
                flag("VAROVANI", oid, "segmenty se na skale temer nelisi",
                     max(rozdily.values()))

        elif o["typ"] == "otevrena":
            txt = [str(t).strip().lower() for t in s[ok]]
            if txt:
                m["podil_unikatu"] = round(len(set(txt)) / len(txt), 3)
                m["prum_slov"] = round(float(np.mean([len(t.split()) for t in txt])), 1)
                if m["podil_unikatu"] < p["verbatim_unikaty_min"]:
                    flag("VAROVANI" if v.get("mode") == "dry" else "KRITICKE", oid,
                         "synteticke verbatimy se opakuji — model recykluje formulace",
                         m["podil_unikatu"])

        # Probability elicitation diagnostics: these are model-level uncertainty
        # signals, not population confidence intervals.
        ep = f"_entropy_{oid}"
        mp = f"_maxprob_{oid}"
        if ep in base.columns and base[ep].notna().any():
            e = pd.to_numeric(base[ep], errors="coerce").dropna()
            x = pd.to_numeric(base[mp], errors="coerce").dropna()
            m["mean_response_entropy"] = round(float(e.mean()), 3) if len(e) else None
            m["mean_max_probability"] = round(float(x.mean()), 3) if len(x) else None
            m["share_maxprob_gt_09"] = round(float((x > 0.9).mean()), 3) if len(x) else None
            if len(x) and float(x.mean()) > p["mean_maxprob_max"]:
                flag("VAROVANI", oid, "LLM je téměř deterministické napříč personami",
                     round(float(x.mean()), 3))
            if len(e) and float(e.mean()) < p["mean_entropy_min"]:
                flag("VAROVANI", oid, "pravděpodobnostní odpovědi mají téměř nulovou entropii",
                     round(float(e.mean()), 3))
        bp = f"_behavior_l1_{oid}"
        if bp in base.columns and base[bp].notna().any():
            bv = pd.to_numeric(base[bp], errors="coerce").dropna()
            m["mean_behavior_l1_shift"] = round(float(bv.mean()), 4) if len(bv) else None
            m["p95_behavior_l1_shift"] = round(float(bv.quantile(.95)), 4) if len(bv) else None
            if len(bv) and float(bv.mean()) > p["behavior_shift_warn"]:
                flag("VAROVANI", oid, "behavioral response layer meni pravdepodobnosti velmi silne",
                     round(float(bv.mean()), 3))
        per_otazku[o["id"]] = m
    metriky["per_otazku"] = per_otazku

    # --- 3. straightlining na skalach
    if len(skaly) >= 3:
        m = detail[[o["id"] for o in skaly]].apply(pd.to_numeric, errors="coerce")
        stejne = m.nunique(axis=1) == 1
        metriky["straightlining"] = round(float(stejne.mean()), 3)
        if metriky["straightlining"] > p["straightline_max"]:
            flag("VAROVANI", "beh", "cast respondentu odpovida na vsechny skaly stejne",
                 metriky["straightlining"])

    # --- 4. mode collapse: identicke vektory odpovedi
    # Collision rate is meaningful only when the theoretical response space is
    # comfortably larger than n. With two 4-way questions and n=500 duplicates
    # are mathematically unavoidable and must not be called model collapse.
    fixed = [o for o in otazky if o["typ"] in ("vyber", "skala") and o["id"] in detail.columns]
    sloupce = [o["id"] for o in fixed]
    if len(sloupce) >= 2:
        space = 1
        for o in fixed:
            if o["typ"] == "vyber":
                k = max(2, len(o.get("volby") or []))
            else:
                # run metadata for scales does not currently retain endpoints;
                # use observed cardinality as a conservative lower bound.
                k = max(2, int(detail[o["id"]].nunique(dropna=True)))
            space *= k
            if space > 10_000_000:
                break
        klice = detail[sloupce].apply(lambda r: "|".join(str(x) for x in r), axis=1)
        dup = round(float(1 - klice.nunique() / len(klice)), 3)
        metriky["podil_duplicitnich_vektoru"] = dup
        metriky["response_space_lower_bound"] = int(space)
        if space >= 5 * max(len(detail), 1) and dup > p["duplicity_max"]:
            flag("VAROVANI", "beh",
                 "hodne respondentu ma uplne stejnou sadu odpovedi i pres velky prostor odpovedi",
                 dup)

    # --- 5. sila persony celkove
    vs = [max(m["cramer_v"].values()) for m in per_otazku.values()
          if m.get("cramer_v")]
    if vs:
        metriky["prumerne_max_cramer_v"] = round(float(np.mean(vs)), 3)
        if metriky["prumerne_max_cramer_v"] < p["cramer_min"]:
            flag("VAROVANI", "beh",
                 "napric dotaznikem je slaba demograficka diferenciace; "
                 "pro efekt persony pouzij ablation benchmark, ne Cramerovo V",
                 metriky["prumerne_max_cramer_v"])

    metriky["persona_effect_verified"] = bool(v.get("ablation"))
    if not v.get("ablation") and v.get("mode") != "dry":
        flag("VAROVANI", "beh",
             "efekt plne persony nebyl v tomto behu overen ablation testem", None)

    uroven = ("KRITICKE" if any(x["uroven"] == "KRITICKE" for x in nalezy)
              else "VAROVANI" if nalezy else "OK")
    verdikt = {
        "OK": "Bez automatickych nalezu; stale jde o syntetickou simulaci, ne lidsky teren.",
        "VAROVANI": "Pouzitelne s vyhradou — projdi nalezy nez to posles klientovi.",
        "KRITICKE": "NEPOSILAT KLIENTOVI. Panel nebo prompt nefunguje, "
                    "opakuj beh po oprave.",
    }[uroven]
    return {"uroven": uroven, "verdikt": verdikt, "nalezy": nalezy, "metriky": metriky}


def tabulka_qc(q: dict) -> str:
    r = [f"=== KONTROLA KVALITY: {q['uroven']} ===", q["verdikt"], ""]
    for nl in sorted(q["nalezy"], key=lambda x: x["uroven"] != "KRITICKE"):
        h = f"  ({nl['hodnota']})" if nl["hodnota"] is not None else ""
        r.append(f"  [{nl['uroven']:9}] {nl['kde']:10} {nl['nalez']}{h}")
    m = q["metriky"]
    r += ["", f"  chybovost: {m.get('chybovost')}   "
              f"prum. max Cramer V: {m.get('prumerne_max_cramer_v', 'n/a')}   "
              f"duplicitni vektory: {m.get('podil_duplicitnich_vektoru', 'n/a')}   "
              f"straightlining: {m.get('straightlining', 'n/a')}"]
    return "\n".join(r)
