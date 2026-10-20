import sys
from pathlib import Path

R = Path(sys.argv[1])
PL = R / ".planning/plans"
SRC = ("the owner's answers on the PM status page, 2026-10-20 about 20:35 UTC, relayed by the coordinator "
       "(page ids Q10, Q11, Q12; `.planning/evidence/scope-freeze/answers-2026-10-20.md`, third table)")


def edit(p, pairs):
    p = Path(p)
    s = p.read_text(encoding="utf-8")
    for o, n in pairs:
        assert s.count(o) == 1, (p.name, o[:70], s.count(o))
        s = s.replace(o, n)
    p.write_text(s, encoding="utf-8")


def add(name, chunks, body):
    f = PL / f"{name}.md"
    lines = f.read_text(encoding="utf-8").split("\n")
    end = lines.index("---", 1)
    lines[end:end] = [f'  - "[ ] {c}"' for c in chunks]
    f.write_text(("\n".join(lines).rstrip("\n") + "\n" + body).rstrip("\n") + "\n", encoding="utf-8")


# ---- lead-orchestration: LO19 (b), LO9d, LO7, LO6
add("lead-orchestration", [
    "LO9d. Every stage worker gets its declared inputs: the upstream accepted items, readiness, question outlook, research trace, earlier proposals' reasons and dismissals, and the newest sealed Deep Research bundle's findings by reference, labelled external context (Q12)",
], f"""
### After the stage-handoff and context-file answers ({SRC})

The owner, on Q12: "we need the highest degree of integration, this needs to be cohesive to produce a
high quality report." All five gaps of the coordinator's stage-handoff audit are closed here and in
the chunks named below.

- **LO9d (W2, after LO9a and `working-copy-edit-ops#WCE7`).** A stage worker today sees the design
  and approved knowledge titles only (`context_snapshot`, `domain/research_agents.py:565-583 @
  7878bad`), so each stage works in a silo and the previous stage's output is not its input. Each
  worker's `LeadWorkerSpec` row declares the inputs it reads, and its context carries them:
  - the upstream stages' accepted items, from WCE7's map of what each stage reads;
  - readiness, the question outlook and the research trace;
  - earlier proposals' reasons and dismissals for the same stage;
  - the newest sealed Deep Research bundle's findings, by reference and labelled external context
    (ADR 0021: never respondent evidence).
  The context stays bounded (the worker's own byte limit), with omissions named. Test: a
  questionnaire worker started after an accepted brief and a Design Research run reads both, and a
  dismissed proposal's reason, by id.
- **LO7.** The Lead's context gains a pending-proposals layer: every proposal still waiting on the
  study, with its stage, proposer and base revision (`application/research_lead.py:858-889 @
  7878bad` builds the layers today without it).
- **LO6's test** also covers a job started through `approve_request`, so a job the Lead's card started
  returns its typed result to the Lead like any other.
- **LO19, the prose part (page Q10: (b)).** Besides the code-built state, the study context file has
  "Poznámky ke studii": any researcher's Lead proposes a note and a person accepts it through the
  existing accept path, with the auto-accept text toggle applying. A note is study material, classed
  by `material_rules.py` like the design. The owner also wrote: "i do want to kinda integrate wordcraft
  and have the lead research be able to live edit the document, once the user is editing the document
  will depend if they revize the text as a comment or rewrite it directly, that will be up to each
  researcher." That live-editing part is **not planned yet**: the coordinator is asking which
  document and what "wordcraft" means.
""")

# ---- assumptions: AOC0 status set, AOC3 hypotheses into analysis
edit(PL / "assumptions-and-open-answer-coding.md", [(
    "The status set itself is still open\n(D-16's second part, master § The scope baseline, Open): AOC0 is not built until it is answered.",
    "The status set (page Q11: (b)) is\nUNTESTED, SUPPORTED, CONTRADICTED and RETIRED; there is no UNVERIFIED, so ADR 0033 decision 2 drops it.\n"
    "- **AOC3 (Q12).** The analysis payload carries `research_plan.hypotheses` and `decision_use`: today\n"
    "  `AnalysisInputs` holds the research questions only (`application/analysis_results.py:570-578 @\n"
    "  7878bad`), so the HYPOTHESES module always says they cannot be assessed\n"
    "  (`domain/analysis/modules.py:99-102`). Test: a study with two stated hypotheses gets a HYPOTHESES\n"
    "  module that evaluates both against admitted evidence.")])

# ---- working-copy-edit-ops: WCE7
p = PL / "working-copy-edit-ops.md"
s = p.read_text(encoding="utf-8").rstrip("\n")
s += f"""

### After the stage-handoff answer ({SRC})

- **WCE7 (Q12).** A declared map of what each stage reads (its upstream stages and items), the one
  source for "current / changed / re-check", for `lead-orchestration#LO9d`'s worker inputs and for
  staleness. A **pending proposal** built on an older upstream item is flagged "postaveno na starší
  verzi …", not only a run: today the lane marks a run's staleness only (`apps/web/src/research/
  lane.ts:34-96 @ 7878bad`). Test: accepting a brief change flags a pending questionnaire proposal
  built before it.
"""
p.write_text(s + "\n", encoding="utf-8")

# ---- contracts
edit(R / ".planning/mvp-execution-contracts.md", [(
    "| `lead-orchestration#LO19` |",
    "| `lead-orchestration#LO9d` | W2 | scope freeze, Q12: after LO9a and `working-copy-edit-ops#WCE7` |\n| `lead-orchestration#LO19` |")])

# ---- master plan
M = PL / "mvp-master-plan.md"
s = M.read_text(encoding="utf-8")
a = s.index("| Q9 | Who may write the prose part")
b = s.index("\n", s.index("| — | An assumption's status set")) + 1
s = s[:a] + s[b:]
anchor = "### Open: signing does not answer these"
extra = f"""### The owner's answers to the questions those raised (2026-10-20, about 20:35 UTC)

Answered on the PM status page (page ids in brackets), relayed by the coordinator, and recorded in
[`answers-2026-10-20.md`](../evidence/scope-freeze/answers-2026-10-20.md) (third table).

| # | Answer | Chunks |
|---|---|---|
| Q9 (page Q10) | The study context file is code-built plus "Poznámky ke studii" that any researcher's Lead proposes and a person accepts; the auto-accept toggle applies. His note on live-editing documents is being clarified and is not planned yet | `lead-orchestration#LO19` |
| Status set (page Q11) | An assumption is UNTESTED, SUPPORTED, CONTRADICTED or RETIRED; no UNVERIFIED | `assumptions-and-open-answer-coding#AOC0` |
| Stage handoff (page Q12) | (a) all five gaps closed: every stage worker gets its declared upstream inputs, hypotheses reach the analysis, staleness reaches pending proposals, the Lead sees pending proposals, a card-started job returns to the Lead | `lead-orchestration#LO9d`, `assumptions-and-open-answer-coding#AOC3`, `working-copy-edit-ops#WCE7`, `lead-orchestration#LO7`, `lead-orchestration#LO6` |

"""
assert s.count(anchor) == 1
s = s.replace(anchor, extra + anchor)
o = "| — | Production's new domain name (D-20"
assert s.count(o) == 1
s = s.replace(o, "| — | The owner's note on the Lead live-editing documents (\"integrate wordcraft\"), with page Q10: which document, and what it means; the coordinator is asking | the owner | not planned yet |\n" + o)
o = "| Added by Q1-Q8 |"
assert s.count(o) == 1
s = s.replace(o, "| Added by the follow-ups | Stage-to-stage handoff: every stage worker's declared inputs, hypotheses in the analysis, staleness on pending proposals, pending proposals in the Lead's context (Q12); Lead-proposed study notes (page Q10); the RETIRED status (page Q11) | `lead-orchestration#LO9d`, `assumptions-and-open-answer-coding#AOC3`, `working-copy-edit-ops#WCE7`, `lead-orchestration#LO7`, `lead-orchestration#LO19`, `assumptions-and-open-answer-coding#AOC0` |\n" + o)
M.write_text(s, encoding="utf-8")

# ---- answers record
A = R / ".planning/evidence/scope-freeze/answers-2026-10-20.md"
t = A.read_text(encoding="utf-8").rstrip("\n")
t += """

## The follow-up questions (page Q10 to Q12)

The baseline's last three questions were answered on the PM status page at about 20:35 UTC. The
coordinator relayed the answers from the page's data rows, which carry the owner's user id. The
planning session did not read the page itself. The owner's own notes are quoted verbatim.

| Page id | Question | Choice | Answer |
|---|---|---|---|
| Q10 | Who writes the study context file's prose | b | Code plus "Poznámky ke studii": any Lead proposes, a person accepts; the auto-accept toggle applies. "i do want to kinda integrate wordcraft and have the lead research be able to live edit the document, once the user is editing the document will depend if they revize the text as a comment or rewrite it directly, that will be up to each researcher." |
| Q11 | An assumption's status set | b | UNTESTED / SUPPORTED / CONTRADICTED / RETIRED; no UNVERIFIED |
| Q12 | Stage-to-stage handoff | a | Close all five gaps. "we need the highest degree of integration, this needs to be cohesive to produce a high quality report" |
"""
A.write_text(t + "\n", encoding="utf-8")
print("ok")
