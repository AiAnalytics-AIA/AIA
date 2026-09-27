"""Pass-through profile for real Customer / Special Audience rows."""
from __future__ import annotations
from typing import Any
import pandas as pd


def audience_facts_text(row: pd.Series) -> str:
    txt=str(row.get("AUDIENCE_FACTS_TEXT") or "").strip()
    if not txt or txt.lower()=="nan":
        return ""
    return "Skutečné údaje z nahrané audience [MEASURED]: " + txt
