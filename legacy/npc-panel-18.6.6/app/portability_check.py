#!/usr/bin/env python3
"""Check that the handoff runtime does not depend on this machine's absolute path."""
from __future__ import annotations
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
# Generated run artifacts legitimately record the absolute path of the machine that
# produced them. They are data, not runtime, and must not fail a handoff check whose
# purpose is proving the *code* runs from any directory.
SKIP={'source_inputs','source_materials','docs','implicates','implicates_v14','__pycache__','.venv',
      'full_simulation_runs','full_simulation_benchmarks','full_simulation_batches','runs',
      'prototype_outputs','logs','diagnostics'}
SKIP_NAMES={'HANDOFF_VERIFICATION.json','PROJECT_STATE.json','RELEASE_MANIFEST_10_6_0.txt','portability_check.py'}
patterns=[re.compile(r'/mnt/data/'),re.compile(r'[A-Za-z]:\\\\Users\\\\')]
hits=[]
for p in ROOT.rglob('*'):
    if not p.is_file() or p.name in SKIP_NAMES or any(x in SKIP for x in p.relative_to(ROOT).parts): continue
    if p.suffix.lower() not in {'.py','.json','.md','.txt','.sh','.bat','.toml','.yaml','.yml','.example'} and p.name!='.env.example': continue
    try: text=p.read_text(encoding='utf-8',errors='ignore')
    except Exception: continue
    for rx in patterns:
        if rx.search(text): hits.append(str(p.relative_to(ROOT))); break
if hits:
    print('PORTABILITY_FAIL')
    for x in hits: print(x)
    raise SystemExit(1)
print('PORTABILITY_PASS')
