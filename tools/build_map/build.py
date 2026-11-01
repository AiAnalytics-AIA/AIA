"""Build the AIA Build Map page from a develop checkout, the stage map and the curated overlay.

Usage: python3 tools/build_map/build.py <a checkout of origin/develop> <out.html>
Then publish out.html to the Build Map artifact (README.md beside this file).

Live from the checkout: every plan's status and chunks, the master plan's register (core / outside /
after the MVP), the execution contracts' groups and waves, the activation matrix, and every plan's
references to other plans. Open PRs come from `gh api` (the page says "unknown" without it).
Hand-kept beside this file: categories, stage purposes, the queue and the open questions
(curated.json), develop's state from the infra audit (develop_state.json), and the stage
hand-offs and gaps (stagemap.json).
"""

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
if len(sys.argv) != 3:
    sys.exit("usage: python3 build.py <a checkout of origin/develop> <out.html>")
wt, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
if not (wt / ".planning/plans/mvp-master-plan.md").exists():
    sys.exit(f"not a develop checkout: {wt}/.planning/plans/mvp-master-plan.md is missing")
cur = json.loads((HERE / "curated.json").read_text("utf-8"))
smap = json.loads((HERE / "stagemap.json").read_text("utf-8"))


def front(text):
    if not text.startswith("---"):
        return None, []
    fm = text.split("---", 2)[1]
    status = re.search(r"^status:\s*([\w-]+)", fm, re.M)
    chunks = re.findall(r'^\s*-\s*"(.*)"\s*$', fm, re.M) or re.findall(
        r"^\s*-\s*'(.*)'\s*$", fm, re.M
    )
    return (status.group(1) if status else None), chunks


def title_of(text):
    m = re.search(r"^# (.+)$", text, re.M)
    return m.group(1).strip() if m else ""


plans = {}
for p in sorted((wt / ".planning/plans").glob("*.md")) + sorted(
    (wt / ".planning/plans/done").glob("*.md")
):
    slug = p.stem
    if slug == "README":
        continue
    text = p.read_text("utf-8")
    status, chunks = front(text)
    items = []
    for c in chunks:
        m = re.match(r"\[( |x)\]\s*(.*)", c)
        if not m:
            continue
        body = m.group(2)
        cid = re.match(r"([A-Za-z0-9][\w.\-]*?)\.\s", body)
        items.append({"done": m.group(1) == "x", "id": cid.group(1) if cid else None, "text": body})
    plans[slug] = {
        "slug": slug,
        "title": title_of(text),
        "status": status or "unknown",
        "chunks": items,
        "done": sum(c["done"] for c in items),
        "total": len(items),
        "archived": "/done/" in str(p),
        "_text": text,
    }

# The master plan's register: core (3.1), outside the development plan (3.2), after the MVP (3.3).
mp = plans["mvp-master-plan"]["_text"]


def section(a, b):
    i, j = mp.find(a), mp.find(b)
    return mp[i:j] if i >= 0 and j > i else ""


def slugs_in(sec):
    return set(re.findall(r"^\|\s*`([a-z0-9\-]+)`", sec, re.M)) | {
        s
        for row in re.findall(r"^\|([^|]+)\|", sec, re.M)
        for s in re.findall(r"`([a-z0-9\-]+)`", row)
    }


core = slugs_in(section("### 3.1", "### 3.2"))
outside = slugs_in(section("### 3.2", "### 3.3"))
after = slugs_in(section("### 3.3", "### 3.4"))

for s, p in plans.items():
    if p["status"] == "done":
        role = "done"
    elif s in cur["roles"]["post"] or s in after:
        role = "after"
    elif s in core:
        role = "core"
    elif s in outside:
        role = "support"
    else:
        role = "support"
    p["role"] = role

# Categories.
assign = {s: e for e, ss in cur["assign"].items() for s in ss}
missing = [s for s, p in plans.items() if p["status"] != "done" and s not in assign]
if missing:
    sys.exit(f"unassigned active plans: {missing}")
for s, p in plans.items():
    if s in assign:
        p["epic"] = assign[s]
        continue
    for epic, keys in cur["done_keywords"]:
        if any(k in s for k in keys):
            p["epic"] = epic
            break

# References between plans: "slug#", "slug.md" or "`slug`" in a plan's text.
edges = []
for a, pa in plans.items():
    for b in plans:
        if a == b:
            continue
        n = len(re.findall(r"(?<![\w-])" + re.escape(b) + r"(?:#|\.md|`)", pa["_text"]))
        if n:
            edges.append([a, b, n])


# Chunk lookup for queue refs.
def chunk_state(ref):
    slug, _, cid = ref.partition("#")
    p = plans.get(slug)
    if not p:
        return None
    for c in p["chunks"]:
        if c["id"] and (c["id"] == cid or c["id"].rstrip(".") == cid):
            return {"done": c["done"], "text": c["text"]}
    return None


for item in cur["queue"]["next"]:
    item["state"] = chunk_state(item["ref"])

# The build sequence: the execution contracts' cross-plan groups (E-ids, wave, needs) and the
# wave of every other open chunk of a core plan (.planning/mvp-execution-contracts.md).
ec = (wt / ".planning/mvp-execution-contracts.md").read_text("utf-8")
ia, ib, ic = (
    ec.find("## Predecessors across plans"),
    ec.find("## Every other open chunk"),
    ec.find("## Gate records"),
)
groups = []
for eid, wave, deliv, needs, proof in re.findall(
    r"^\| (E\d+) \| ([^|]*?) \| (.*?) \| (.*?) \| (.*?) \|$", ec[ia:ib], re.M
):
    refs = re.findall(r"`([a-z0-9\-]+#[\w.\-]+)`", deliv)
    groups.append(
        {
            "id": eid,
            "wave": wave.strip(),
            "needs": re.findall(r"E\d+", needs),
            "chunks": [{"ref": r, "state": chunk_state(r)} for r in refs],
            "proof": re.sub(r"`", "", proof)[:400],
        }
    )
loose = []
grouped = {c["ref"] for g in groups for c in g["chunks"]}
for ref, wave, basis in re.findall(
    r"^\| `([a-z0-9\-]+#[\w.\-]+)` \| ([^|]+?) \| (.*?) \|$", ec[ib:ic], re.M
):
    if ref in grouped:
        continue
    w = re.match(r"(W\d|POST|UNSCHEDULED)", wave.strip())
    loose.append(
        {
            "ref": ref,
            "wave": w.group(1) if w else wave.strip()[:12],
            "state": chunk_state(ref),
            "basis": re.sub(r"`", "", basis)[:200],
        }
    )

# The activation matrix (mvp-master-plan §4): what must be switched on, and who throws it.
act_sec = section("## 4. The activation matrix", "## 5.")
activation = []


def clean(s):
    return re.sub(r"\*\*|`", "", s).strip()


for sw, need, by, ev in re.findall(r"^\| (.+?) \| (.+?) \| (.+?) \| (.+?) \|$", act_sec, re.M):
    if sw.startswith("Switch") or set(sw) <= set("-| "):
        continue
    activation.append(
        {
            "switch": clean(sw),
            "needed_by": clean(need)[:260],
            "set_by": clean(by),
            "evidence": clean(ev),
        }
    )
develop_state = {}
ds_file = HERE / "develop_state.json"
if ds_file.exists():
    develop_state = json.loads(ds_file.read_text("utf-8"))

# Stages: purpose (curated), live progress from the plan, hand-offs and gaps from the stage map.
stages = []
for s in smap["stages"]:
    st = s["stage"]
    name = st["name"]
    if name not in cur["stage_purpose"]:
        continue
    slug = Path(st["plan"].split()[0]).stem
    p = plans.get(slug, {})
    stages.append(
        {
            "name": name,
            "phase": st["phase"],
            "plan": slug,
            "purpose": cur["stage_purpose"][name],
            "done": p.get("done"),
            "total": p.get("total"),
            "next": next((c["text"] for c in p.get("chunks", []) if not c["done"]), None),
            "built": s.get("built", []),
            "backend_gaps": s.get("backend_gaps", []),
            "frontend_gaps": s.get("frontend_gaps", []),
            "proposed": [c for c in cur["proposed_chunks"] if c["stage"] == name],
            "done_ids": [c["id"] for c in p.get("chunks", []) if c["done"] and c["id"]],
        }
    )

# Open PRs, live.
prs = []
try:
    raw = subprocess.run(
        [
            "gh",
            "api",
            "repos/aianalytics-aia/aia/pulls?state=open&per_page=50",
            "--jq",
            "[.[]|{n:.number,t:.title,draft:.draft,by:.user.login,head:.head.sha[0:8]}]",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout
    prs = json.loads(raw)
except Exception:  # the page says it could not read them
    prs = None

sha = subprocess.run(
    ["git", "-C", str(wt), "rev-parse", "HEAD"], capture_output=True, text=True
).stdout.strip()
for p in plans.values():
    p.pop("_text")
    # The page shows the next open chunk and the counts; keep every chunk for the drawer.

data = {
    "built_at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC"),
    "develop_sha": sha,
    "stagemap_sha": smap["develop_sha"],
    "epics": cur["epics"],
    "plans": list(plans.values()),
    "edges": edges,
    "stages": stages,
    "chain": smap["chain"],
    "critical_path": smap.get("critical_path", []),
    "queue": cur["queue"],
    "proposed": cur["proposed_chunks"],
    "questions": cur["questions"],
    "agile": cur["agile"],
    "prs": prs,
    "groups": groups,
    "loose": loose,
    "activation": activation,
    "develop_state": develop_state,
}
tpl = (HERE / "page.tpl.html").read_text("utf-8")
payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
out.write_text(tpl.replace("/*__DATA__*/null", payload), "utf-8")
act = [p for p in plans.values() if p["status"] != "done"]
print(
    f"{len(plans)} plans ({len(act)} open), {len(edges)} references, {len(stages)} stages, "
    f"core {sum(p['role'] == 'core' for p in act)}, "
    f"PRs {None if prs is None else len(prs)} -> {out}"
)
