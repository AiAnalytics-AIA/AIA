"""PIAAC 2023 employment bridge for the Czech synthetic population.

The bridge uses respondent-level PIAAC employment status (C2_D05), age, gender,
and detailed education. It deliberately does not infer employment above age 65,
because the PIAAC adult PUF ends there. For 66+ the status remains unknown and
work-conditioned attributes stay unavailable unless another respondent-level
source supplies employment.

The shipped cell table is derived from the user-supplied PIAAC 2023 Czech PUF.
LFS 2025 remains a calibration/validation source, not a respondent donor.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

DEFAULT_TABLE = Path(__file__).with_name("EMPLOYMENT_BRIDGE_PIAAC2023.csv")
AGE_BINS = [18, 25, 35, 45, 55, 66]  # left-closed: 18-24 ... 55-65
AGE_LABELS = ["18-24", "25-34", "35-44", "45-54", "55-65"]


def _edu4_from_piaac(x: float) -> str | None:
    if pd.isna(x):
        return None
    x = int(x)
    if x in {1, 2, 3}:
        return "základní"
    if x in {4, 5}:
        return "střední bez maturity"
    if x in {6, 7, 8, 9, 10}:
        return "střední s maturitou"
    if x in {11, 12, 13, 14}:
        return "VOŠ/VŠ"
    return None


def build_cell_table(piaac_csv: str | Path, out: str | Path = DEFAULT_TABLE,
                     shrink_n: float = 30.0) -> pd.DataFrame:
    """Build weighted empirical-Bayes cells from the Czech PIAAC PUF."""
    use = ["C2_D05", "AGE_R", "GENDER_R", "B2_Q01_TC1", "SPFWT0"]
    d = pd.read_csv(piaac_csv, sep=";", usecols=use, low_memory=False)
    for c in use:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d[d["C2_D05"].isin([1, 2, 3]) & d["AGE_R"].between(18, 65)
          & d["GENDER_R"].isin([1, 2]) & d["SPFWT0"].gt(0)].copy()
    d["employed"] = (d["C2_D05"] == 1).astype(int)
    d["pohlavi"] = d["GENDER_R"].map({1: "muž", 2: "žena"})
    d["vzdelani"] = d["B2_Q01_TC1"].map(_edu4_from_piaac)
    d["age_band"] = pd.cut(d["AGE_R"], AGE_BINS, labels=AGE_LABELS,
                            right=False, include_lowest=True).astype(str)
    d = d[d["vzdelani"].notna() & d["age_band"].isin(AGE_LABELS)]

    def wp(g: pd.DataFrame) -> float:
        return float(np.average(g["employed"], weights=g["SPFWT0"]))

    parent = d.groupby(["age_band", "pohlavi"], observed=True).apply(
        wp, include_groups=False).rename("p_parent").reset_index()
    rows = []
    for keys, g in d.groupby(["age_band", "pohlavi", "vzdelani"], observed=True):
        p_cell = wp(g)
        p_parent = float(parent[(parent.age_band == keys[0]) &
                                (parent.pohlavi == keys[1])]["p_parent"].iloc[0])
        n = len(g)
        lam = n / (n + shrink_n)
        p = lam * p_cell + (1 - lam) * p_parent
        rows.append({
            "age_band": keys[0], "pohlavi": keys[1], "vzdelani": keys[2],
            "n_unweighted": n, "p_employed_weighted_raw": round(p_cell, 6),
            "p_parent_age_sex": round(p_parent, 6),
            "shrinkage_lambda": round(lam, 6), "p_employed": round(p, 6),
            "source": "PIAAC 2023 CZ PUF C2_D05; SPFWT0",
            "eligible_age": "18-65",
        })
    out_df = pd.DataFrame(rows).sort_values(["age_band", "pohlavi", "vzdelani"])
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out, index=False)
    return out_df


def add_employment_status(df: pd.DataFrame, table_path: str | Path = DEFAULT_TABLE,
                          seed: int = 20260814) -> pd.DataFrame:
    """Probabilistically impute current employment for age 18-65.

    Outputs:
      zamestnan_p       conditional probability from PIAAC bridge
      zamestnan         1/0 draw for age 18-65, NaN outside source support
      zamestnan_source  provenance label
    """
    t = pd.read_csv(table_path)
    key_to_p = {(str(r.age_band), str(r.pohlavi), str(r.vzdelani)): float(r.p_employed)
                for r in t.itertuples()}
    # Fallback parent probabilities in case a sparse education cell is absent.
    # Build explicitly to avoid pandas groupby.apply API/version differences.
    parent_map = {}
    for (ab, sex), g in t.groupby(["age_band", "pohlavi"]):
        parent_map[(str(ab), str(sex))] = float(np.average(g["p_parent_age_sex"],
                                                              weights=g["n_unweighted"]))

    out = df.copy()
    age = pd.to_numeric(out["vek"], errors="coerce")
    band = pd.cut(age, AGE_BINS, labels=AGE_LABELS, right=False, include_lowest=True)
    p = np.full(len(out), np.nan, dtype=float)
    for i, (ab, sex, edu, a) in enumerate(zip(band.astype(object), out["pohlavi"],
                                               out["vzdelani"], age)):
        if pd.isna(a) or a < 18 or a > 65 or pd.isna(ab):
            continue
        sexn = "muž" if str(sex).lower().startswith("mu") else "žena"
        p[i] = key_to_p.get((str(ab), sexn, str(edu)),
                            parent_map.get((str(ab), sexn), np.nan))
    rng = np.random.default_rng(seed)
    draw = np.full(len(out), np.nan, dtype=float)
    valid = np.isfinite(p)
    draw[valid] = (rng.random(valid.sum()) < p[valid]).astype(float)
    out["zamestnan_p"] = np.round(p, 6)
    out["zamestnan"] = draw
    out["zamestnan_source"] = np.where(
        valid, "PIAAC2023 bridge: C2_D05|age|gender|education", "outside PIAAC age support")
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("panel")
    ap.add_argument("-o", "--out", default="panel_with_employment.csv")
    ap.add_argument("--table", default=str(DEFAULT_TABLE))
    ap.add_argument("--seed", type=int, default=20260814)
    a = ap.parse_args()
    x = pd.read_csv(a.panel, low_memory=False)
    add_employment_status(x, a.table, a.seed).to_csv(a.out, index=False)
