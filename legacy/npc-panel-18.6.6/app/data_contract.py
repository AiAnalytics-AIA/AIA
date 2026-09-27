from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
ROOT=Path(__file__).resolve().parent
@lru_cache(maxsize=1)
def contract():
    return json.loads((ROOT/"DATA_CONTRACT_v17.json").read_text(encoding="utf-8"))
def path(key:str)->Path:
    return ROOT/str(contract()[key])
def panel_path()->Path:return path("panel")
def weight(role:str="default_current")->str:return str(contract().get("weights",{}).get(role) or "vaha_kalibrovana")
