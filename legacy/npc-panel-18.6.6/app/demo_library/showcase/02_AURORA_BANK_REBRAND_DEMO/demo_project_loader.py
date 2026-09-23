"""Aurora Bank Rebrand DEMO — read-only DEMO seed adapter.

Napoj na aktuální ProjectStore/ArtifactStore. Otevření DEMO nesmí volat AI/API.
"""
from __future__ import annotations
import json
from pathlib import Path
DEMO_PROJECT_ID='PRJ-DEMO-AURORA-REBRAND'
DEMO_TITLE='Aurora Bank Rebrand DEMO'

def load_demo_contract(asset_root):
    root=Path(asset_root)
    return json.loads((root/'DEMO_PROJECT_SEED.json').read_text(encoding='utf-8'))

def ensure_demo_project(project_store, artifact_store, asset_root):
    root=Path(asset_root)
    existing=project_store.get(DEMO_PROJECT_ID) if hasattr(project_store,'get') else None
    if existing:return {'project_id':DEMO_PROJECT_ID,'created':False}
    contract=load_demo_contract(root)
    created=project_store.create_project(project_type='research',title=DEMO_TITLE,project=contract,runtime_version='DEMO-SEED')
    return {'project_id':created.get('project_id',DEMO_PROJECT_ID),'revision':created.get('revision',1),'created':True,'register_manifest':'ARTIFACT_MANIFEST.json'}
