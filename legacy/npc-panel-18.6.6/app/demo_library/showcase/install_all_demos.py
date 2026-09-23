"""Registry-driven integration skeleton for all NPC Panel DEMO projects."""
from pathlib import Path
import json, importlib.util

def ensure_all_demos(project_store, artifact_store, root):
    root=Path(root)
    registry=json.loads((root/'DEMO_REGISTRY.json').read_text(encoding='utf-8'))
    out=[]
    for item in registry:
        folder=root/item['relative_path']
        spec=importlib.util.spec_from_file_location('npc_demo_loader', folder/'demo_project_loader.py')
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        out.append(mod.ensure_demo_project(project_store,artifact_store,folder))
    return out
