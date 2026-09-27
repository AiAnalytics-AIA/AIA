from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
FILE=ROOT/'TYPOLOGY_REFERENCE_2026.json'

def load_typology_reference():
    if not FILE.exists(): return {'runtime_role':'UNAVAILABLE','types':[]}
    return json.loads(FILE.read_text(encoding='utf-8'))

_RELEVANCE=re.compile(r'polit|volb|stran|ideolog|hodnot|společ|spolec|důvěr|duver|instituc|migr|segment|typolog|veřejn|verejn|radikal|autor',re.I)

def compact_typology_context(text:str='', *, force:bool=False) -> dict:
    """Small AI-facing reference, never a respondent assignment table."""
    ref=load_typology_reference()
    if ref.get('runtime_role')=='UNAVAILABLE': return {}
    if not force and not _RELEVANCE.search(str(text or '')): return {}
    types=[]
    for t in ref.get('types') or []:
        types.append({
            'name':t.get('name'),
            'historical_share_pct_2019_2021':t.get('historical_share_pct_2019_2021'),
            'status':t.get('status'),
            'original_profile_summary':str(t.get('original_profile_summary') or '')[:700],
            'hexaco_hypothesis':str(t.get('hexaco_hypothesis') or '')[:500],
            'ambiguity_warning':str(t.get('ambiguity_warning') or '')[:650],
            'socioeconomic_context_2026':str(t.get('socioeconomic_context_2026') or '')[:650],
            'political_context_2026':str(t.get('political_context_2026') or '')[:650],
        })
    return {
        'runtime_role':'HYPOTHESIS_REFERENCE_ONLY',
        'hard_rule':'Never assign these types to individual panel rows, never calibrate to their historical shares, and never present HEXACO reinterpretations as measured Czech traits.',
        'allowed_use':'Generate testable hypotheses, candidate subgroup comparisons, instrument recommendations and scenario mechanisms; measured respondent-level fields remain authoritative.',
        'types':types,
        'document_recommendations':ref.get('document_recommendations') or [],
    }
