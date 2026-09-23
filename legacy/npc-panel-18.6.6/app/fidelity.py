"""Question-level evidence/fidelity policy for the 10.13 HTML protocol.

This layer never upgrades a synthetic estimate merely because it looks stable.
GREEN requires an actual validated human holdout status.  Until such evidence is
installed, relative tests are AMBER and absolute WTP/market-size questions are
RED/refused for client claims.
"""
from __future__ import annotations
from pathlib import Path
import json, re

ROOT=Path(__file__).resolve().parent

ABSOLUTE_PATTERNS=[
    r'kolik\s+(?:kč|korun|byste\s+zaplat|zaplatil)', r'maxim[aá]ln[ií]\s+cena',
    r'ochot[an]\w*\s+zaplat', r'velikost\s+trhu', r'kolik\s+lid[ií]', r'kolik\s+z[aá]kazn[ií]k',
    r'tržb', r'obrat', r'v\s*kč',
]
RELATIVE_PATTERNS=[r'kter[áý]\s+variant',r'porovnej',r'prefer',r'pořad',r'znění',r'koncept\s+[ab]']


def classify_question(text: str, qtype: str='') -> str:
    t=str(text or '').lower()
    if any(re.search(p,t) for p in ABSOLUTE_PATTERNS): return 'absolute_value'
    if any(re.search(p,t) for p in RELATIVE_PATTERNS): return 'relative_comparison'
    if qtype=='otevrena': return 'open_ended'
    if qtype=='skala': return 'rating_scale'
    return 'distribution'


def _validation_status() -> str:
    for name in ('VALIDATION_EVIDENCE.json','validation_evidence.json'):
        p=ROOT/name
        if p.exists():
            try: return str(json.loads(p.read_text(encoding='utf-8')).get('status','UNVALIDATED')).upper()
            except Exception: pass
    try:
        from validation_gate import load_validation_evidence
        return str(load_validation_evidence().get('status','UNVALIDATED')).upper()
    except Exception:
        return 'UNVALIDATED'


def evidence_rating(text: str, qtype: str='', *, validation_status: str|None=None) -> dict:
    kind=classify_question(text,qtype); status=(validation_status or _validation_status()).upper()
    if kind=='absolute_value':
        return {'rating':'RED','mode':'REFUSE','question_type':kind,
                'reason':'Absolutní WTP/velikost trhu není validovaný claim. Přeformulujte na relativní pořadí, cenové pásmo nebo A/B srovnání.'}
    if status=='VALIDATED':
        return {'rating':'GREEN','mode':'RECOMMEND' if kind=='relative_comparison' else 'JUST_SHOW','question_type':kind,
                'reason':'K dispozici je validovaný human holdout pro release; stále zobrazujeme interval a manifest.'}
    return {'rating':'AMBER','mode':'RECOMMEND' if kind=='relative_comparison' else 'JUST_SHOW','question_type':kind,
            'reason':'Syntetický výsledek bez dostatečného blind human holdoutu; používejte pro exploraci/relativní rozhodnutí, ne jako publikovatelný populační fakt.'}


def falsification_condition(text: str, qtype: str='', rating: dict|None=None) -> str:
    r=rating or evidence_rating(text,qtype)
    if r['rating']=='RED':
        return 'Závěr nelze přijmout v této absolutní podobě; potřeboval by přímé lidské měření stejné otázky a stejné cílové populace.'
    if r['question_type']=='relative_comparison':
        return 'Doporučení přestává platit, pokud se pořadí variant obrátí na předem zamčeném lidském holdoutu nebo při rozumné změně znění/pořadí na stejném vzorku.'
    return 'Závěr přestává platit, pokud srovnatelný lidský holdout stejné populace a wording ukáže efekt mimo uvedený interval nebo opačný segmentový gradient.'
