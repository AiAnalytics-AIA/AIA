"""NPC PANEL v2 — machine-readable data contracts for synthetic dimensions.

The goal is not to prove that a source is licensed for every use. The goal is
to make provenance/denominator gaps impossible to hide in code: every D_
dimension must declare role, confidence, year, unit and eligible population.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import pandas as pd

REQUIRED_PROV = ("zdroj_role", "jistota", "rok", "citlive", "unit", "eligible_population")
ALLOWED_ROLES = {"ANCHOR", "BRIDGE", "SPECIALIST", "CALIBRATION", "OWN_ESTIMATE"}


def audit_dimension_contracts() -> dict[str, list[str]]:
    from dispozice import DIMENZE
    fail: list[str] = []
    warn: list[str] = []
    for dim, d in DIMENZE.items():
        prov = d.get("prov") or {}
        missing = [k for k in REQUIRED_PROV if k not in prov]
        if missing:
            fail.append(f"{dim}: chybi provenance pole {missing}")
            continue
        if prov["zdroj_role"] not in ALLOWED_ROLES:
            fail.append(f"{dim}: neznamy zdroj_role={prov['zdroj_role']}")
        try:
            conf = float(prov["jistota"])
        except Exception:
            fail.append(f"{dim}: jistota neni cislo")
            conf = 0
        if not 0 <= conf <= 1:
            fail.append(f"{dim}: jistota mimo 0..1 ({conf})")
        if not str(d.get("zdroj", "")).strip():
            fail.append(f"{dim}: chybi zdroj")
        if prov["zdroj_role"] == "OWN_ESTIMATE":
            warn.append(f"{dim}: OWN_ESTIMATE; nepouzivat jako tvrdy fakt")
        if prov.get("unit") == "person_from_household_calibration":
            warn.append(f"{dim}: household kotva projektovana na osobu")
        if prov.get("eligible_population") != "CR_18+":
            warn.append(f"{dim}: denominator={prov.get('eligible_population')}")
    return {"fail": fail, "warning": warn}


def dimension_dictionary() -> pd.DataFrame:
    from dispozice import DIMENZE
    rows: list[dict[str, Any]] = []
    for dim, d in DIMENZE.items():
        p = d.get("prov", {})
        rows.append({
            "dimension": dim,
            "column": f"D_{dim}",
            "block": d.get("blok"),
            "marker": d.get("marker"),
            "anchor": d.get("kotva"),
            "source": d.get("zdroj"),
            "source_role": p.get("zdroj_role"),
            "confidence": p.get("jistota"),
            "source_year": p.get("rok"),
            "sensitive": p.get("citlive"),
            "unit": p.get("unit"),
            "eligible_population": p.get("eligible_population"),
            "eligibility_source": p.get("eligibility_source"),
            "unit_warning": p.get("unit_warning"),
            "topics": "|".join(d.get("temata", [])),
        })
    return pd.DataFrame(rows)


def export_dimension_dictionary(path: str | Path = "DIMENSION_DATA_DICTIONARY_v2.csv") -> Path:
    path = Path(path)
    dimension_dictionary().to_csv(path, index=False)
    return path


if __name__ == "__main__":
    a = audit_dimension_contracts()
    print(f"FAIL={len(a['fail'])} WARNING={len(a['warning'])}")
    for x in a["fail"]:
        print("FAIL", x)
    p = export_dimension_dictionary()
    print(p)
