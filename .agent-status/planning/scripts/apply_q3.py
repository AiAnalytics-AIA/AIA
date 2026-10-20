import sys
from pathlib import Path

R = Path(sys.argv[1])
PL = R / ".planning/plans"
SRC = ("the owner's answers on the PM status page, 2026-10-20 20:50-21:04 UTC, relayed by the coordinator "
       "(page ids Q13 to Q18; `.planning/evidence/scope-freeze/answers-2026-10-20.md`, fourth table)")


def edit(p, pairs):
    p = Path(p)
    s = p.read_text(encoding="utf-8")
    for o, n in pairs:
        assert s.count(o) == 1, (p.name, o[:70], s.count(o))
        s = s.replace(o, n)
    p.write_text(s, encoding="utf-8")


def append(name, body):
    f = PL / f"{name}.md"
    f.write_text(f.read_text(encoding="utf-8").rstrip("\n") + "\n" + body.rstrip("\n") + "\n", encoding="utf-8")


append("lead-orchestration", f"""
### After the editing, departure and lookup answers ({SRC})

- **LO19 and the reports (page Q13: (a)).** How a Lead's edit reaches a document is each
  researcher's own setting: **tracked-change suggestions** the researcher accepts or rejects (the
  default), or **direct rewrites** that stay undoable. It applies to the study context file's notes
  (LO19) and to report documents (`report-delivery#RD6`), on top of their existing rules (every
  number a ledger ref in a report). The editor itself is open: the owner names Wordcraft
  (`github.com/storytold/wordcraft`, an open-source Rust/WASM Word reimplementation with an MCP
  server, alpha), and whether AIA adopts it is being asked; nothing here depends on that choice.
- **LO11 (page Q14: (a)).** A departed member's Lead is **sealed** when the member is deactivated
  (`two-roles-human-ai-gates#8`): no turn runs, nothing is read by anyone, its files and notes stay
  as they were. It is deleted at the end of MVPQ-07's retention (30 days), through
  `study-data-lifecycle`'s delete path, with the content-free usage and audit rows kept. Still no
  handover and no admin read (D-32 to D-34). Test: a deactivated member's Lead refuses a turn and an
  admin read, and is gone after the retention end.
- **LO20 (page Q18: (a)).** A Lead web lookup needs **no plan card or approval**: it runs inside the
  turn, bounded to **3 queries, 5 fetched pages and 2 lookups per turn**, with a hold on the wallet
  before it leaves (the hold refuses it when the wallet cannot cover it). OPEN clients only. Tests:
  a fourth query in one turn is refused by name; a lookup with too little wallet is refused before
  anything is sent.
""")

append("report-delivery", f"""
### After the editing and old-method answers ({SRC})

- **RD6 (page Q13: (a)).** A Lead's report edit reaches the document as the researcher has chosen:
  tracked-change suggestions by default, or direct, undoable rewrites (`lead-orchestration` § After
  the editing, departure and lookup answers). The editor is open (Wordcraft is being asked about).
- **Old-method reports (page Q17: (a)).** A report already **approved** from a `-1`/`-3` run stays
  downloadable as approved, unchanged.
""")

append("signed-off-sociomap-method", f"""
### After the old-method answer ({SRC})

- **8 (page Q17: (a)).** A retry of a run that pinned `-1` or `-3` is **refused**, worded with a link
  that starts a new run on `-5` from the same Design Revision. Approved reports of such runs stay
  downloadable (`report-delivery#RD3`). Test: a retry of a `-3` run returns the refusal and the new
  run link, and starts nothing.
""")

edit(PL / "production-environment.md", [(
    "Production moves to a **new domain**, not yet named: open in the baseline.",
    "Production's hostname is **`app.ai-analytics.ai`** (page Q15: (a)): its Cognito and Google\n  callbacks and the certificate are for that name.")])

append("deep-research-web-search", f"""
### After the release-route answer ({SRC})

- **53 (page Q16: (a)).** At release, Brave serves OPEN clients' web research, as MVP-27 amended has
  it. The owner's note asks for Brave for **Class B** queries too (a CLASSIFIED client's design
  queries); that is being confirmed and is **open** in the baseline. Until it is answered, a
  CLASSIFIED client's web tracks stay parked as today.
""")

# master plan
M = PL / "mvp-master-plan.md"
s = M.read_text(encoding="utf-8")
o = "| — | The owner's note on the Lead live-editing documents (\"integrate wordcraft\"), with page Q10: which document, and what it means; the coordinator is asking | the owner | not planned yet |\n"
n = ("| — | The editor for tracked-change and direct Lead edits (page Q13): the owner names Wordcraft "
     "(`github.com/storytold/wordcraft`, open-source Rust/WASM, MCP server, alpha); whether AIA adopts it is being asked | the owner | `lead-orchestration#LO19`, `report-delivery#RD6` |\n"
     "| — | Brave for Class B queries too (page Q16's note): a CLASSIFIED client's design queries to Brave; being confirmed | the owner | `deep-research-web-search#53` |\n")
assert s.count(o) == 1
s = s.replace(o, n)
o = "| — | Production's new domain name (D-20: \"i will be changing to a new domain\") | the owner | `production-environment#PE1`, Cognito callbacks |\n"
assert s.count(o) == 1
s = s.replace(o, "")
o = "production moves to a new domain the owner has\nnot yet named, and the Bedrock quota is an operator's"
assert s.count(o) == 1
s = s.replace(o, "production's hostname is `app.ai-analytics.ai`\n(page Q15), and the Bedrock quota is an operator's")
o = "the production domain (new, not yet named: D-20), Cognito and Google callbacks;"
assert s.count(o) == 1
s = s.replace(o, "the production hostname `app.ai-analytics.ai` (page Q15), Cognito and Google callbacks;")
anchor = "### Open: signing does not answer these"
table = """### The owner's answers of 20:50-21:04 UTC (page Q13 to Q18)

Relayed by the coordinator from the PM status page; recorded in
[`answers-2026-10-20.md`](../evidence/scope-freeze/answers-2026-10-20.md) (fourth table).

| Page | Answer | Chunks |
|---|---|---|
| Q13 | A Lead's edits reach the study context file and reports as each researcher chooses: tracked-change suggestions (default) or direct, undoable rewrites; the editor is open (Wordcraft?) | `lead-orchestration#LO19`, `report-delivery#RD6` |
| Q14 | A departed member's Lead is sealed, then deleted at MVPQ-07's retention end | `lead-orchestration#LO11` |
| Q15 | Production's hostname is `app.ai-analytics.ai` | `production-environment#PE1` |
| Q16 | Brave at release for OPEN clients; Brave for Class B queries is being confirmed (Open) | `deep-research-web-search#53` |
| Q17 | Approved old-method reports stay downloadable; an old-method retry is refused with a link to a new `-5` run | `signed-off-sociomap-method#8`, `report-delivery#RD3` |
| Q18 | A Lead web lookup needs no card: 3 queries, 5 pages and 2 lookups per turn, a wallet hold, OPEN clients only | `lead-orchestration#LO20` |

"""
assert s.count(anchor) == 1
s = s.replace(anchor, table + anchor)
M.write_text(s, encoding="utf-8")

A = R / ".planning/evidence/scope-freeze/answers-2026-10-20.md"
t = A.read_text(encoding="utf-8").rstrip("\n")
t += """

## Page Q13 to Q18

These were answered on the PM status page between 20:50 and 21:04 UTC. The coordinator relayed
them; the planning session did not read the page itself. The owner's notes are paraphrased by the
coordinator where marked.

| Page id | Question | Choice | Answer |
|---|---|---|---|
| Q13 | How a Lead's edits reach a document | a | Per researcher: tracked-change suggestions by default, or direct, undoable Lead rewrites, for the study context file and reports. The owner names Wordcraft (github.com/storytold/wordcraft) as the editor; whether to adopt it is a follow-up |
| Q14 | A departed member's Lead | a | Sealed, then deleted at MVPQ-07's retention end |
| Q15 | Production's hostname | a | app.ai-analytics.ai |
| Q16 | The release search route | a | Brave at release for OPEN clients; his note (as relayed) asks for Brave for Class B queries too, being confirmed |
| Q17 | Old-method reports and retries | a | Approved old-method reports stay downloadable; old-method retries are refused with a link to a new -5 run |
| Q18 | The Lead's web lookup | a | No card; within 3 queries, 5 pages and 2 lookups per turn; a wallet hold; OPEN clients only |
"""
A.write_text(t + "\n", encoding="utf-8")
print("ok")
