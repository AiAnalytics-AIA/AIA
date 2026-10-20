import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from questions import Q  # noqa: E402

S=lambda **k:k
sess=[
 S(id="session_01YEVg53K5fKSGUfcKPTdrRk",title="AIA PM: coordinator 2",category="PM",state="working",doing="Running /pmstatus; watching develop CI for #519-#521 and the domain move.",plan=None,prs=[],needs=None,blocked_by=[],next="Put Q1-Q8 to you when you ask; merge #516→#522→#523 after your signature.",context_pct=60,last_update="2026-10-20T19:20:00Z",reply="received"),
 S(id="session_01RxUnHwTXGVFYjwzfpKi9kT",title="AIA planning 2: master plan + docs PRs",category="Planning",state="waiting-on-nigel",doing="Finished freeze step 4 part 2: all 48 answers applied, dated baseline written (#523).",plan=dict(path=".planning/plans/mvp-master-plan.md",chunk="MP16 — the owner signs the scope baseline",done=7,total=17),prs=[dict(num=516,title="48-decision list",state="draft",ci="green"),dict(num=522,title="Consolidated 102 proposed edits",state="draft",ci="green"),dict(num=523,title="Scope baseline",state="draft",ci="green")],needs="Your answers to Q1-Q8, then your signature on MP16.",blocked_by=["N1"],next="Apply each answer to the plans #523 names; you sign MP16.",context_pct=56,last_update="2026-10-20T19:18:27Z",reply="received"),
 S(id="session_015hqQ6KEtJb864UHuU74ypp",title="AIA scope 2: methodology packet",category="Scope inputs",state="waiting-on-nigel",doing="Packet finished (MVPQ-13 = -5 canonical; MQ-01..24 for Arigamaru).",plan=None,prs=[dict(num=510,title="MVP methodology packet",state="draft",ci="green")],needs="Your review of the packet PDF before it goes to Arigamaru.",blocked_by=["N3"],next="Add your edits as one commit; then you send it to Arigamaru.",context_pct=None,last_update="2026-10-20T19:18:29Z",reply="received"),
 S(id="session_01Qg43kRfsZ97FjA8XenP28x",title="AIA scope 3: MVP ADR drafts",category="Scope inputs",state="waiting-on-nigel",doing="ADRs 0028-0038 drafted (0038: MVP ships aia-sociomap-5).",plan=None,prs=[dict(num=512,title="ADRs 0028-0038 (Proposed)",state="draft",ci="green")],needs="Accept / amend / reject each ADR and answer its 'Open for Nigel' items.",blocked_by=["N5"],next="Apply your decisions as amendments; docs PR adds index rows.",context_pct=15,last_update="2026-10-20T19:18:13Z",reply="received"),
 S(id="session_01EWprA36RBr7HAF58DTxTNn",title="AIA scope 1b: reverse scope audit",category="Scope inputs",state="waiting-on-review",doing="313-row audit delivered; its 14 edits and 23 questions are already folded into #516/#522.",plan=None,prs=[dict(num=513,title="Reverse scope audit",state="draft",ci="green")],needs="Nothing new: merges with the baseline.",blocked_by=["N1"],next="Merged as evidence after you sign.",context_pct=None,last_update="2026-10-20T19:18:08Z",reply="received"),
 S(id="session_01Hv8Phz319H6u3HLQ2BgF6C",title="AIA scope 1c: client pages + Settings",category="Scope inputs",state="waiting-on-review",doing="Impact note delivered; N1-N12 folded into #516/#522.",plan=None,prs=[dict(num=514,title="Client pages + Settings impact",state="draft",ci="green")],needs="Nothing new: merges with the baseline.",blocked_by=["N1"],next="Merged as evidence after you sign.",context_pct=3,last_update="2026-10-20T19:18:17Z",reply="received"),
 S(id="session_01FskpgUny4pDAMYFBLvAj4S",title="AIA scope 1a: cross-check tracks 5-7",category="Scope inputs",state="waiting-on-review",doing="21 findings (G58-G78) delivered; folded into #522.",plan=None,prs=[dict(num=515,title="Cross-check tracks 5-7",state="draft",ci="green")],needs="Nothing new: merges with the baseline.",blocked_by=["N1"],next="Merged as evidence after you sign.",context_pct=None,last_update="2026-10-20T19:18:25Z",reply="received"),
 S(id="session_01LBR1SyjXK8uYR5VdBjGAEJ",title="AIA infra audit",category="Infra",state="waiting-on-nigel",doing="Cutover plan for dev.ai-analytics.ai ready (2 add / 3 change / 1 destroy, 0 denials) with runbook + rollback; #519 and #521 merged.",plan=None,prs=[dict(num=519,title="Terraform ≥1.10 + lock file",state="merged",ci="green"),dict(num=521,title="Ignore user_data on the host",state="merged",ci="green")],needs="(1) 'commit and push the IdP fix' in its session; (2) the dig check once Webglobe's NS change is live.",blocked_by=["N2","N4"],next="Open the IdP fix PR; after delegation, run the cutover with you.",context_pct=None,last_update="2026-10-20T19:18:10Z",reply="received"),
 S(id="session_01AXkfBjA7hUPZipWXSoHzEc",title="AIA fix: Docker dependency layer",category="Infra",state="waiting-on-nigel",doing="Fix done and verified locally: same image, a small change adds 6.6 MB instead of 250 MB, rebuild 52 s instead of 4.5 min.",plan=dict(path=".planning/plans/image-build-layers.md",chunk="3 — the layer check",done=3,total=3),prs=[],needs="Your own 'commit and push' in its session (the permission classifier blocked it).",blocked_by=["N6"],next="Open the draft PR; the first develop deploy proves the PDF image variant.",context_pct=27,last_update="2026-10-20T19:18:11Z",reply="received"),
 S(id="session_01QzemVrHfQp8jsVEqXb9W6x",title="AIA fix: Next.js 16.4 security",category="Security/CI",state="done",doing="#509 (Next 16.4.2 + blocking pip-audit) and #518 (npm gate) merged and deployed.",plan=None,prs=[dict(num=509,title="Next 16.4.2 + pip-audit",state="merged",ci="green"),dict(num=518,title="npm audit gate",state="merged",ci="green")],needs=None,blocked_by=[],next="Idle. The braces exception expires 2026-11-20.",context_pct=32,last_update="2026-10-20T19:18:21Z",reply="received"),
 S(id="session_01End3azGdHNr1MtxRjUqqZ8",title="AIA design: MVP workbench artifact",category="Design",state="waiting-on-nigel",doing="Design v2 published (11 screens, Peněženka).",plan=None,prs=[],needs="Your feedback on the design, when you have time (not blocking).",blocked_by=[],next="Apply your feedback.",context_pct=36,last_update="2026-10-20T19:18:14Z",reply="received"),
]
needs=[
 dict(id="N1",title="Answer Q1-Q8, then sign the scope baseline (#523)",why="Scope freeze: no MVP feature code starts until you sign. 7 sessions' work merges with it.",example="Q1: does the switch to -5 merge as soon as it's built (maps internal until Arigamaru's register entry), or wait for the entry?",recommendation="Answer Q1-Q8 under 'Your decisions' on this page; I'll apply them, then you sign in planning 2.",unblocks=["planning","scope-inputs","build"],where="Your decisions (this page), then planning 2"),
 dict(id="N2",title="Confirm the Webglobe nameserver change",why="The domain move to dev.ai-analytics.ai can't start until .ai shows the AWS nameservers.",example="dig +short NS ai-analytics.ai @a.nic.ai shows four awsdns names.",recommendation="Your coworker confirms the e-mail; then run the dig and tell me.",unblocks=["d4","d5"],where="Webglobe e-mail + CloudShell"),
 dict(id="N4",title="'commit and push the IdP fix' (infra session)",why="Makes Terraform match what Cognito really does and keeps the domain cutover plan clean.",example="Type exactly: commit and push the IdP fix",recommendation="Do it before the domain cutover.",unblocks=["i2","d5"],where="AIA infra audit session"),
 dict(id="N6",title="'commit and push' the Docker layer fix",why="Stops ~1 GB of host disk per deploy and cuts rebuilds from 4.5 min to under a minute.",example="Type: commit and push",recommendation="Yes: equivalence is proven (68 packages, 10,157 files identical).",unblocks=["k2"],where="AIA fix: Docker dependency layer session"),
 dict(id="N3",title="Review the methodology packet (#510)",why="Arigamaru's 24 MQ answers gate the numerical MVP chunks; nothing goes to him before you review.",example="The PDF I sent earlier (methodology + engineering companion).",recommendation="Read it, then say 'send to Arigamaru'.",unblocks=["m2"],where="PDF / PR #510"),
 dict(id="N5",title="Decide ADRs 0028-0038 (#512)",why="The architecture of the wallet, working copy, Lead and production depends on them; most are already settled by your 48 answers.",example="ADR 0028: the wallet and plan card. Accept as drafted?",recommendation="Accept them with the baseline signature; I'll list only the 'Open for Nigel' items left.",unblocks=["build"],where="PR #512"),
]
ws=[
 dict(id="freeze",title="Scope freeze → MVP build",steps=[
  dict(id="f1",title="48 answers (#516)",status="done",owner="Nigel",depends_on=[]),
  dict(id="f2",title="Baseline drafted (#522/#523)",status="done",owner="Planning 2",depends_on=["f1"]),
  dict(id="f3",title="Q1-Q8 answered",status="waiting",owner="Nigel",depends_on=["f2"]),
  dict(id="f4",title="Sign MP16",status="waiting",owner="Nigel",depends_on=["f3"]),
  dict(id="f5",title="Merge #516→#522→#523 (+#510-#515)",status="todo",owner="Coordinator",depends_on=["f4"]),
  dict(id="f6",title="Start W0/W1 build lanes",status="blocked",owner="Coordinator",depends_on=["f5"])]),
 dict(id="domain",title="Develop → dev.ai-analytics.ai",steps=[
  dict(id="d1",title="Route 53 zone created",status="done",owner="Nigel",depends_on=[]),
  dict(id="d2",title="Parked mail records",status="active",owner="Nigel",depends_on=["d1"]),
  dict(id="d3",title="Webglobe NS → AWS (e-mail confirm)",status="waiting",owner="Coworker",depends_on=["d1"]),
  dict(id="d4",title="dig shows awsdns",status="todo",owner="Nigel",depends_on=["d3"]),
  dict(id="d5",title="terraform apply + SSM DSN + GitHub var",status="todo",owner="Infra + Nigel",depends_on=["d4","i2"]),
  dict(id="d6",title="Redeploy + smoke + re-login",status="todo",owner="Coordinator",depends_on=["d5"])]),
 dict(id="infra",title="Infra hardening",steps=[
  dict(id="i1",title="#519 lock file, #521 user_data",status="done",owner="Infra",depends_on=[]),
  dict(id="i2",title="Google IdP fix PR",status="waiting",owner="Nigel → Infra",depends_on=[]),
  dict(id="k1",title="Docker layer fix verified",status="done",owner="Docker",depends_on=[]),
  dict(id="k2",title="Docker PR + first deploy",status="waiting",owner="Nigel → Docker",depends_on=["k1"])]),
 dict(id="method",title="Methodology (aia-sociomap-5)",steps=[
  dict(id="m1",title="Packet #510 written",status="done",owner="Scope 2",depends_on=[]),
  dict(id="m2",title="Your review",status="waiting",owner="Nigel",depends_on=["m1"]),
  dict(id="m3",title="Arigamaru answers MQ-01..24",status="todo",owner="Arigamaru",depends_on=["m2"]),
  dict(id="m4",title="-5 register entry + numeric chunks",status="blocked",owner="Build",depends_on=["m3","f4"])]),
 dict(id="docs",title="Documentation",steps=[
  dict(id="o1",title="20-doc Drive set + archive",status="done",owner="Coordinator",depends_on=[]),
  dict(id="o2",title="Repo docs PR (stale ADR index etc.)",status="todo",owner="Planning 2",depends_on=["f5"])]),
]
nxt=[
 dict(id="A1",who="Coworker / Nigel",what="Confirm Webglobe NS e-mail; run the dig check.",after=[]),
 dict(id="A2",who="Nigel",what="'commit and push' in the infra session (IdP fix) and in the Docker session.",after=[]),
 dict(id="A3",who="Coordinator",what="Review and merge the IdP and Docker PRs when green; watch the deploy.",after=["A2"]),
 dict(id="A4",who="Nigel + Infra",what="Domain cutover (~10 min downtime, then everyone re-logs in).",after=["A1","A3"]),
 dict(id="A5",who="Nigel",what="Go through Q1-Q8 with me, then sign the baseline.",after=[]),
 dict(id="A6",who="Coordinator",what="Merge #516→#522→#523 and the evidence PRs; start the W0/W1 lanes.",after=["A5"]),
 dict(id="A7",who="Nigel",what="Review the methodology packet, then send it to Arigamaru.",after=[]),
]
rec=[
 dict(when="2026-10-20T19:05:00Z",what="Route 53 zone ai-analytics.ai created; cutover plan clean."),
 dict(when="2026-10-20T19:00:00Z",what="Documentation: 20 Google Docs, a consistency review (9 fixes), 19 old docs archived."),
 dict(when="2026-10-20T18:30:00Z",what="Deployed 47e55368 (Next 16.4.2, blocking audits, wallet rename)."),
 dict(when="2026-10-20T18:25:00Z",what="Merged #520, #519, #521."),
 dict(when="2026-10-20T17:45:00Z",what="Scope baseline drafted (#522, #523) from all 48 answers."),
 dict(when="2026-10-20T17:20:00Z",what="Merged #511 (wallet) and #518 (npm gate); terraform-plan-read attached."),
]

# Explainers: explainers/<session-id>/<slug>.html, each saved by the coordinator from a session's
# "EXPLAINER <title> — <function>" message. Title, function and height come from, in order: a sidecar
# <slug>.json {"title", "function", "height"}; a first-line comment
# <!-- EXPLAINER <title> — <function> [height=<px>] -->; the page's <title>; the slug.
import glob
import re
HERE = os.path.dirname(os.path.abspath(__file__))
MAX_EXPLAINER = 40 * 1024
HEAD = re.compile(r"^\s*<!--\s*EXPLAINER\s+(.*?)\s*-->", re.S)


def load_explainers(session_id):
    out = []
    for path in sorted(glob.glob(os.path.join(HERE, "explainers", session_id, "*.html"))):
        raw = open(path, encoding="utf-8").read()
        if len(raw.encode("utf-8")) > MAX_EXPLAINER:
            print(f"skipped {path}: over 40 KB", file=sys.stderr)
            continue
        slug = os.path.splitext(os.path.basename(path))[0]
        title, function, height = slug.replace("-", " "), None, None
        m = HEAD.match(raw)
        if m:
            head = m.group(1)
            hm = re.search(r"\bheight=(\d+)\s*$", head)
            if hm:
                height = int(hm.group(1))
                head = head[: hm.start()].strip()
            parts = re.split(r"\s+[—-]\s+", head, maxsplit=1)
            title = parts[0] or title
            function = parts[1] if len(parts) > 1 else None
        else:
            tm = re.search(r"<title>(.*?)</title>", raw, re.S | re.I)
            if tm and tm.group(1).strip():
                title = tm.group(1).strip()
        side = os.path.splitext(path)[0] + ".json"
        if os.path.exists(side):
            meta = json.load(open(side, encoding="utf-8"))
            if isinstance(meta, dict):
                title = str(meta.get("title") or title)
                function = meta.get("function") or function
                if isinstance(meta.get("height"), (int, float)):
                    height = int(meta["height"])
        item = dict(id=slug, title=title, function=function, html=raw)
        if height:
            item["height"] = height
        out.append(item)
    return out


for s_ in sess:
    ex = load_explainers(s_["id"])
    if ex:
        s_["explainers"] = ex

d=dict(generated_at="2026-10-20T19:25:00Z",develop_sha="7878bad",headline="Ten sessions report. Nothing is broken; nine wait on you. Two quick 'commit and push' words and the Webglobe confirmation unblock the infra work; Q1-Q8 plus your signature unblock the whole MVP build.",needs_nigel=needs,sessions=sess,workstreams=ws,next_actions=nxt,recent=rec,questions=Q,decided=[])
json.dump(d,open('status.json','w'),ensure_ascii=False,indent=1)
