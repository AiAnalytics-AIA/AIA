from __future__ import annotations
from pathlib import Path
import hashlib, json, sys
from edition_config import build_version

ROOT=Path(__file__).resolve().parent
VERSION=build_version()
CHECKSUM=ROOT/f"SHA256SUMS_{VERSION.replace('.','_')}.txt"
BAD_TOKENS=("Γ","├","┬","╬","öÇ","Γî","Ã","Â")


def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()


def files():
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file(): continue
        if '__pycache__' in p.parts or '.venv' in p.parts: continue
        rel=p.relative_to(ROOT)
        if rel==CHECKSUM.relative_to(ROOT): continue
        yield p,rel


def scan()->dict:
    bad_names=[]; remnants=[]; old_checksums=[]
    for p,rel in files():
        n=p.name
        if any(tok in n for tok in BAD_TOKENS): bad_names.append(rel.as_posix())
        if n.endswith('.bak') or '.pre' in n or n.endswith('.orig'): remnants.append(rel.as_posix())
        if n.startswith('SHA256SUMS') and n!=CHECKSUM.name and not str(rel).startswith('audit_reference/'): old_checksums.append(rel.as_posix())
    return {'bad_filenames':bad_names,'developer_remnants':remnants,'old_checksum_files':old_checksums}


def write()->Path:
    state=scan()
    if any(state.values()): raise RuntimeError(json.dumps(state,ensure_ascii=False))
    rows=[f"{sha256(p)}  {rel.as_posix()}" for p,rel in files()]
    CHECKSUM.write_text('\n'.join(rows)+'\n',encoding='utf-8')
    return CHECKSUM


def verify()->dict:
    failed=[]; checked=0
    for line in CHECKSUM.read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        h,rel=line.split('  ',1);p=ROOT/rel;checked+=1
        if not p.is_file() or sha256(p)!=h: failed.append(rel)
    state=scan(); ok=not failed and not any(state.values())
    return {'version':VERSION,'checked':checked,'failed':failed,**state,'status':'PASS' if ok else 'FAIL'}

if __name__=='__main__':
    if '--verify' in sys.argv:
        print(json.dumps(verify(),ensure_ascii=False,indent=2)); raise SystemExit(0 if verify()['status']=='PASS' else 1)
    write(); result=verify();print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['status']=='PASS' else 1)
