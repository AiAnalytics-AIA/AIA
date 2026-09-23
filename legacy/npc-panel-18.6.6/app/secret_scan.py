#!/usr/bin/env python3
"""Conservative secret scan for handoff packaging.

Skips binary/data archives and the documented .env.example placeholders. It is not a
replacement for an enterprise secret scanner, but catches common accidental API keys
or private-key blocks in source/config/docs.
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SKIP_DIRS={'.venv','__pycache__','source_inputs','docs/archive'}
SKIP_SUFFIX={'.zip','.csv','.xlsx','.docx','.pdf','.png','.jpg','.jpeg','.webp','.pyc'}
PATTERNS=[
    ('openai_key', re.compile(r'\bsk-[A-Za-z0-9_-]{24,}\b')),
    ('anthropic_key', re.compile(r'\bsk-ant-[A-Za-z0-9_-]{20,}\b')),
    ('private_key', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
]

def main()->int:
    hits=[]
    for p in ROOT.rglob('*'):
        if not p.is_file(): continue
        rel=p.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts): continue
        if p.suffix.lower() in SKIP_SUFFIX: continue
        if p.name=='.env.example': continue
        try: text=p.read_text(encoding='utf-8',errors='ignore')
        except Exception: continue
        for name,rx in PATTERNS:
            for m in rx.finditer(text):
                hits.append({'file':str(rel),'type':name,'preview':m.group(0)[:12]+'…'})
    env_files=[str(p.relative_to(ROOT)) for p in ROOT.rglob('.env') if p.is_file()]
    if env_files:
        hits.extend({'file':x,'type':'env_file','preview':'.env'} for x in env_files)
    if hits:
        print('SECRET_SCAN_FAIL')
        for h in hits: print(h)
        return 1
    print('SECRET_SCAN_PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
