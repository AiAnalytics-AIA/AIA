"""Conservative pre-run cost/time ranges with optional run-store telemetry."""
from __future__ import annotations
import json, statistics
from pathlib import Path
from typing import Any
from runtime_config import provider_pricing, resolve_provider_model


def _telemetry_rates(store_path: str|Path, model: str) -> list[float]:
    rs=None
    try:
        from run_store import RunStore
        rs=RunStore(store_path)
        rows=rs.list_runs(300)
    except Exception:
        return []
    finally:
        if rs is not None:
            rs.close()
    out=[]
    for r in rows:
        if str(r.get("model")) != str(model): continue
        cost=r.get("cost_usd"); n=r.get("n") or 0; qn=r.get("question_count") or 0
        if cost is None or not n or not qn: continue
        try:
            rate=float(cost)/(float(n)*float(qn))
            if rate>0: out.append(rate)
        except Exception: pass
    return out


def estimate_range(brief: dict[str,Any], store_path="data/run_store.sqlite") -> dict[str,Any]:
    n=max(0,int(brief.get("n",120) or 0)); qn=max(1,len([q for q in brief.get("otazky",[]) if str(q.get("text","")).strip()]))
    calls=n*qn
    from provider_auth import get_ai_provider
    policy=str(brief.get("provider_policy") or ("strict_"+get_ai_provider())).lower()
    provider="openai" if "openai" in policy else "anthropic"
    model=resolve_provider_model(provider,brief.get("model")); cin,cout=provider_pricing(provider,model)
    tele=_telemetry_rates(store_path,model)
    if len(tele)>=3:
        med=statistics.median(tele); lo=statistics.quantiles(tele,n=4)[0] if len(tele)>=4 else med*.75; hi=statistics.quantiles(tele,n=4)[2] if len(tele)>=4 else med*1.35
        source=f"telemetrie {len(tele)} předchozích běhů"
    else:
        # deliberately broad: persona length/routing/caching vary by question.
        lo=(550/1e6*cin + 25/1e6*cout); med=(850/1e6*cin + 50/1e6*cout); hi=(1350/1e6*cin + 95/1e6*cout)
        source="konzervativní tokenový rozsah; bude nahrazen vlastní telemetrií"
    research=bool((brief.get("research_context") or {}).get("enabled") if isinstance(brief.get("research_context"),dict) else brief.get("research_context"))
    return {
        "calls":calls,"provider":provider,"model":model,
        "usd_low":round(calls*lo,2),"usd_typical":round(calls*med,2),"usd_high":round(calls*hi,2),
        "source":source,
        "research_context_not_included":research,
        "note":"Odhad nezahrnuje retries ani Research Context; LIVE reportuje skutečné náklady."
    }
