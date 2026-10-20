import json, re, sys
from pathlib import Path
R = Path(sys.argv[1]); OUT = Path(sys.argv[2])
P = R/".planning/plans"
master = (P/"mvp-master-plan.md").read_text()
contracts = (R/".planning/mvp-execution-contracts.md").read_text()

def section(text, start, end):
    i = text.index(start); j = text.index(end, i+len(start)); return text[i:j]

def rows(block):
    out=[]
    for l in block.splitlines():
        if l.startswith("|") and not re.match(r"^\|\s*-", l):
            cells=[c.strip() for c in l.strip().strip("|").split("|")]
            out.append(cells)
    return out[1:]  # drop header

def frontmatter(name):
    t=(P/f"{name}.md").read_text()
    m=re.match(r"---\n(.*?)\n---", t, re.S)
    fm=m.group(1) if m else ""
    status=re.search(r"status:\s*(\S+)", fm)
    chunks=[]
    for c in re.findall(r'^\s*-\s*"(.*)"\s*$', fm, re.M):
        mm=re.match(r"\[(.)\]\s*([^\s.]+)\.?\s*(.*)", c)
        if mm: chunks.append({"id":mm.group(2).rstrip('.'),"done":mm.group(1)=="x","dropped":mm.group(1)=="-","title":mm.group(3).replace('\\"','"')})
    title=re.search(r"^# (.+)$", t, re.M)
    return {"status":status.group(1) if status else "?","chunks":chunks,"heading":title.group(1) if title else name}

core=[]
for r in rows(section(master,"### 3.1 Core","### 3.2")):
    name=r[0].strip("`"); fm=frontmatter(name)
    core.append({"plan":name,"session":r[1],"gates":r[2],"needs":r[3],**fm})
other=[]
for r in rows(section(master,"### 3.2","### 3.3")):
    other.append({"plan":r[0].replace("`",""),"role":r[1],"why":r[2]})

erows=[]
for r in rows(section(contracts,"## Predecessors across plans","## Every other open chunk")):
    if not re.match(r"E\d+",r[0]): continue
    erows.append({"id":r[0],"wave":r[1],"deliverable":r[2],"needs":[x.strip() for x in r[3].split(",") if x.strip() not in ("—","")],"proof":r[4],
                  "chunks":re.findall(r"`([a-z0-9-]+#[A-Za-z0-9]+)`", r[2])})
waves={}
for e in erows:
    for c in e["chunks"]: waves[c]={"wave":e["wave"],"row":e["id"]}
for r in rows(section(contracts,"## Every other open chunk","## Gate records")):
    m=re.match(r"`([a-z0-9-]+#[A-Za-z0-9]+)`", r[0])
    if m: waves.setdefault(m.group(1),{"wave":r[1],"row":None,"basis":r[2]})

gates=[{"gate":r[0],"evidence":r[1],"not":r[2]} for r in rows(section(contracts,"## Gate records","I-0–I-3 may"))]
dev=(R/".planning/mvp-development-plan.md").read_text()
gate_meaning={re.sub(r"\*","",r[0]).split()[0]:{"name":re.sub(r"\*","",r[0]),"holds":r[1],"criteria":r[2]} for r in rows(section(dev,"## 1. The gates","### Reach is not"))}

pm=json.loads((R/"docs/migration/parity-matrix.json").read_text())
ac_built={r[0]:re.findall(r"`([a-z0-9-]+#[A-Za-z0-9]+)`",r[1]) for r in rows(section(master,"### 3.4","## 4. "))}
acs=[{"id":c["id"],"statement":c["statement"],"built_by":ac_built.get(c["id"],[])} for c in pm["mvp_acceptance"]["criteria"]]

activation=[{"switch":r[0],"needed_by":r[1],"set_by":r[2],"evidence":r[3]} for r in rows(section(master,"## 4. The activation matrix","## 5. "))]
interfaces=[{"id":r[0],"text":" | ".join(r[1:])} for r in rows(section(master,"## 5. The interfaces","## 6. ")) if re.match(r"I\d+",r[0])]
g61=section(master,"### 6.1","### 6.2")
gaps=[{"id":r[0],"gap":r[1],"chunks":re.findall(r"`([a-z0-9-]+#[A-Za-z0-9]+)`",r[2]) if len(r)>2 else []} for r in rows(g61) if re.match(r"G\d+",r[0])]
settled=[{"decision":r[0],"by":r[1],"where":r[2]} for r in rows(section(master,"### 11.1","### 11.2"))]
open_q=[{"id":r[0],"q":r[1],"blocks":r[2],"rec":r[3] if len(r)>3 else ""} for r in rows(section(master,"### 11.4","### 11.5")) if len(r)>=3]
overrides=[{"id":r[0],"plans":r[1],"override":r[2],"moves":r[3]} for r in rows(section(master,"### 11.3","### 11.4")) if re.match(r"S\d",r[0])]
risks=section(master,"## 10. Risks of the whole","## 11. ")
data=dict(core=core,other=other,erows=erows,waves=waves,gates=gates,gate_meaning=gate_meaning,acs=acs,activation=activation,interfaces=interfaces,gaps=gaps,settled=settled,open=open_q,overrides=overrides,risks=risks)
OUT.write_text(json.dumps(data,ensure_ascii=False,indent=1))
print({k:len(v) if hasattr(v,'__len__') else v for k,v in data.items()})
print("chunks:",sum(len(c["chunks"]) for c in core),"done:",sum(1 for c in core for x in c["chunks"] if x["done"]))
missing=[f'{c["plan"]}#{x["id"]}' for c in core for x in c["chunks"] if not x["done"] and f'{c["plan"]}#{x["id"]}' not in waves]
print("open core chunks with no wave found:",len(missing),missing[:15])
