"""Explicit three-provider LIVE runtime policy.

Production transports are Claude Code subscription, Claude API and OpenAI API.
The selected provider is fail-closed. Cross-provider switching is never automatic;
any provider change must be an explicit user/project action and is recorded.
"""
from __future__ import annotations
from typing import Any

CLAUDE_CODE='claude_code_subscription'
CLAUDE_API='anthropic'       # internal provider id; UI label is Claude API
OPENAI='openai'
LIVE_PROVIDERS={CLAUDE_CODE,CLAUDE_API,OPENAI}
POLICIES={'CLAUDE_CODE_ONLY','CLAUDE_API_ONLY','OPENAI_ONLY','CLAUDE_CODE_THEN_API'}
UI_LABELS={CLAUDE_CODE:'Claude Code',CLAUDE_API:'Claude API',OPENAI:'OpenAI API'}
MODEL_ROLES=('research_model','design_model','respondent_model','analysis_model','report_polish_model')

def normalize_live_provider(value:str|None, default:str=CLAUDE_CODE)->str:
    v=str(value or '').strip().lower()
    if v in {'claude_api','anthropic_api','api','anthropic'}: return CLAUDE_API
    if v in {'claude_code','subscription','claude_code_subscription'}: return CLAUDE_CODE
    if v in {'openai','openai_api'}: return OPENAI
    return default

def normalize_policy(value:str|None)->str:
    v=str(value or 'CLAUDE_CODE_ONLY').strip().upper()
    return v if v in POLICIES else 'CLAUDE_CODE_ONLY'

def provider_for_stage(*,preferred_provider:str|None=None,policy:str|None=None,stage_override:str|None=None,explicit_api_continue:bool=False)->str:
    if stage_override: return normalize_live_provider(stage_override)
    pol=normalize_policy(policy)
    if pol=='CLAUDE_API_ONLY': return CLAUDE_API
    if pol=='OPENAI_ONLY': return OPENAI
    if pol=='CLAUDE_CODE_ONLY': return CLAUDE_CODE
    if pol=='CLAUDE_CODE_THEN_API' and explicit_api_continue: return CLAUDE_API
    return normalize_live_provider(preferred_provider,CLAUDE_CODE)

def ui_provider(provider:str|None)->str: return UI_LABELS.get(normalize_live_provider(provider), 'Claude Code')

def policy_for_provider(provider:str|None)->str:
    p=normalize_live_provider(provider)
    return 'OPENAI_ONLY' if p==OPENAI else ('CLAUDE_API_ONLY' if p==CLAUDE_API else 'CLAUDE_CODE_ONLY')

def api_budget_check(*,spent_usd:float=0,reserved_usd:float=0,estimate_usd:float=0,max_api_cost_usd:float=10.0)->dict[str,Any]:
    projected=max(0.0,float(spent_usd))+max(0.0,float(reserved_usd))+max(0.0,float(estimate_usd))
    cap=max(0.0,float(max_api_cost_usd))
    return {'allowed':projected<=cap+1e-9,'projected_usd':round(projected,6),'max_api_cost_usd':round(cap,6),'remaining_usd':round(max(0.0,cap-float(spent_usd)-float(reserved_usd)),6)}
