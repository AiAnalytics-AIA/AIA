from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
P=ROOT/'BUILD_EDITION.json'
DEFAULT={
    'version':'18.6.6',
    'edition':'COMPLETE_FINAL_THREE_PROVIDER',
    'claude_code_enabled':True,
    'claude_api_enabled':True,
    'openai_api_enabled':True,
    'label':'Guided UX · NPC Panel 18.6 · Complete Final',
    'default_provider':'claude_code_subscription',
    'allowed_live_providers':['claude_code_subscription','anthropic','openai'],
}
def load_edition():
    try:
        x=json.loads(P.read_text(encoding='utf-8')) if P.is_file() else {}
    except Exception:
        x={}
    return {**DEFAULT,**x}
def claude_code_enabled()->bool:return bool(load_edition().get('claude_code_enabled'))
def allowed_providers()->set[str]:
    return set(load_edition().get('allowed_live_providers') or DEFAULT['allowed_live_providers'])
def build_version()->str:return str(load_edition().get('version','UNKNOWN'))
