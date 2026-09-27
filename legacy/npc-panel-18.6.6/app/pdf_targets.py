"""Track-B PDF target extraction with explicit human confirmation.

Extraction uses the existing Anthropic provider path; it does not change survey or
orchestration model routing. No target is merged until the structured draft has
been exported and explicitly confirmed by the caller.
"""
from __future__ import annotations

from anthropic_compat import create_message
from pathlib import Path
import json,re
import pandas as pd

def extract_pdf_text(path:str|Path)->str:
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)

def draft_targets(path:str|Path,*,model:str|None=None,provider:str|None=None,max_chars=80000)->pd.DataFrame:
    from runtime_config import DEFAULT_MODEL
    from provider_auth import get_ai_provider
    from ai_router import call_structured
    text=extract_pdf_text(path)[:max_chars]
    prompt='Z textu studie vytáhni pouze explicitně publikované populační marginály vhodné pro raking NPC panelu. Nic nedopočítávej.'
    schema={"type":"object","properties":{"targets":{"type":"array","items":{"type":"object","properties":{
        "variable":{"type":"string"},"category":{"type":"string"},"target_share":{"type":"number"},
        "source_quote":{"type":"string"},"page_or_section":{"type":"string"},"confidence":{"type":"number"}},
        "required":["variable","category","target_share","source_quote","page_or_section","confidence"],"additionalProperties":False}}},
        "required":["targets"],"additionalProperties":False}
    rr=call_structured(system="Jsi konzervativní extraktor statistických tabulek. Nevymýšlej chybějící hodnoty.",
        messages=[{"role":"user","content":prompt+"\n\nTEXT:\n"+text}],schema=schema,schema_name="population_targets",
        anthropic_model=model or DEFAULT_MODEL,max_tokens=4000,prefer=(provider or get_ai_provider()),allow_fallback=False)
    rows=(rr.get("data") or {}).get("targets") or []
    df=pd.DataFrame(rows)
    if not {"variable","category","target_share"}<=set(df): raise ValueError("Incomplete target extraction")
    df["confirmed"]=False; return df

def confirmed_targets(draft:pd.DataFrame)->pd.DataFrame:
    if "confirmed" not in draft or not bool(draft["confirmed"].all()): raise ValueError("All PDF-extracted targets require explicit human confirmation")
    return draft[["variable","category","target_share"]].copy()
