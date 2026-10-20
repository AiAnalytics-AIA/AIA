import sys
from pathlib import Path

R = Path(sys.argv[1])
PL = R / ".planning/plans"
SRC = ("the owner's answers on the PM status page, 2026-10-20, relayed by the coordinator at 21:41 UTC "
       "(page ids Q19 to Q21; `.planning/evidence/scope-freeze/answers-2026-10-20.md`, fifth table)")


def edit(p, pairs):
    p = Path(p)
    s = p.read_text(encoding="utf-8")
    for o, n in pairs:
        assert s.count(o) == 1, (p.name, o[:70], s.count(o))
        s = s.replace(o, n)
    p.write_text(s, encoding="utf-8")


def add_chunk(name, after_line_prefix, line):
    f = PL / f"{name}.md"
    s = f.read_text(encoding="utf-8")
    head, sep, body = s.partition("\n---\n")
    lines = head.split("\n")
    idx = [i for i, l in enumerate(lines) if l.startswith(after_line_prefix)]
    assert len(idx) == 1, (name, after_line_prefix, idx)
    lines.insert(idx[0] + 1, line)
    f.write_text("\n".join(lines) + sep + body, encoding="utf-8")


def append(name, body):
    f = PL / f"{name}.md"
    f.write_text(f.read_text(encoding="utf-8").rstrip("\n") + "\n" + body.rstrip("\n") + "\n", encoding="utf-8")


# Q19: the editor spike
add_chunk("research-lead-workbench", '  - "[ ] 32.',
          '  - "[ ] 33. Editor spike (Q19): Wordcraft, ONLYOFFICE Docs and Collabora Online compared against Tiptap for the study context file and reports, on Word-like UX, tracked changes and comments, Lead-driven edits, ledger refs through a round trip, DOCX fidelity, licence and EU self-hosting; a go/no-go to the owner"')

append("research-lead-workbench", f"""
### After the editor answer ({SRC})

- **33 (W1, page Q19: (a)).** Evaluate before adopting. A time-boxed spike compares editors for the
  study context file (`lead-orchestration#LO19`) and the report documents (`report-delivery#RD6`),
  each researcher's tracked-change or direct mode (page Q13) included. Its outcome is a written
  go/no-go to the owner; nothing is adopted in this chunk.
  - **Candidates:** Wordcraft (`github.com/storytold/wordcraft`; MIT/Apache, Rust/WASM, an MCP
    server, alpha); ONLYOFFICE Docs (AGPL, Word-like, track changes, a JS API); Collabora Online
    (LibreOffice-based, MPL, WOPI). Tiptap is the baseline: the owner finds its UX poor ("I want as
    close to Microsoft Word or LibreOffice as possible") and asks for alternatives.
  - **Criteria:** a Word-like UX; tracked changes and comments; the Lead driving edits (suggestion
    and direct modes); every report number staying a ledger ref through an edit and a DOCX round trip
    (`report-delivery#RD6`); DOCX fidelity against `infrastructure/report_docx`; the licence (AGPL's
    obligations named for a hosted product); EU self-hosting with no outside service.
  - **Evidence:** each candidate run locally on one fictional study context file and one sample
    report, the round trip's ledger refs counted before and after, a screenshot set, the licence
    reading. Zero paid jobs.
  - LO19 and RD6 build against the editor the owner chooses; until then they keep a plain editor
    behind the same edit operations, so the choice changes the surface, not the rules.
""")

# Q20: Brave for Class B
add_chunk("deep-research-web-search", '  - "[ ] 56.',
          '  - "[ ] 57. Brave for Class B queries (owner determination 2026-10-20, Q20): a query written from a design reaches Brave at Class B for every client, CLASSIFIED included; Class A stays refused (Q22 open); recorded as data beside OI-61"')

append("deep-research-web-search", f"""
### After the Class B answer ({SRC})

- **57 (W2, page Q20: (b)). The owner's determination of 2026-10-20**, recorded in the style of
  OI-61 (`licence_determinations.py`): the Brave route may receive **Class B** (design-derived)
  queries for **every client, CLASSIFIED included**.
  - It changes MVP-27 (amended 2026-10-19) for Class B: a CLASSIFIED client's design-derived queries
    no longer leave its web tracks parked. A query takes the class of what it was written from
    (`deep_research/classification.py`, never lowered by keywords); Brave admits B and C, and the
    route's admitted classes come from the recorded determination, not from code defaults.
  - **Class A stays refused** on Brave (client notes, approved knowledge, a client's sources, by
    `material_rules`) until page Q22 is answered. **Search operators** (`site:`, `filetype:`,
    `intitle:`) are page Q23, open; nothing here adds them. The owner's note: "maybe even class A,
    depends how the query is constructed. I like to implement google search hacking into the
    workflows, to create highly specific and reputable sources".
  - Chunk 53's OPEN posture is unchanged: OPEN still lowers an OPEN client's queries to Class C.
    What changes is the CLASSIFIED path: its edited design no longer needs an operator record to run
    its web tracks when every query it sends is Class B or C; a query from Class A material is
    refused by name and sends nothing.
  - Cost, stated plainly: Brave is NON_EU and keeps logs up to 90 days, so a CLASSIFIED client's
    design wording (names included) can reach it. The determination is the guard, and it is recorded.
  - ADR 0008 (residency and classes) and ADR 0032 (#512) record the route's admitted classes; both
    change with this (Doc follow-up).
  - Tests: a CLASSIFIED client's design-derived query reaches the recorded Brave double at Class B; a
    query built from a Class A knowledge item is refused before anything is sent; the determination
    record is the only source of Brave's admitted classes (removing it refuses Class B); an OPEN
    client's behaviour is unchanged.
  - The Lead's lookup (`lead-orchestration#LO20`, chunk 56) stays OPEN-only (page Q18) unless the
    owner decides otherwise.
""")

# contracts: wave rows
C = R / ".planning/mvp-execution-contracts.md"
anchor = "| `research-lead-workbench#24` | POST |"
edit(C, [(anchor,
          "| `research-lead-workbench#33` | W1 | owner, page Q19: the editor spike before LO19 and RD6 build their surface |\n"
          "| `deep-research-web-search#57` | W2 | owner determination 2026-10-20, page Q20: with chunk 53 (E12) |\n"
          + anchor)])

# master plan
M = PL / "mvp-master-plan.md"
edit(M, [
    ("| — | The editor for tracked-change and direct Lead edits (page Q13): the owner names Wordcraft (`github.com/storytold/wordcraft`, open-source Rust/WASM, MCP server, alpha); whether AIA adopts it is being asked | the owner | `lead-orchestration#LO19`, `report-delivery#RD6` |\n"
     "| — | Brave for Class B queries too (page Q16's note): a CLASSIFIED client's design queries to Brave; being confirmed | the owner | `deep-research-web-search#53` |\n",
     "| — | The editor's go/no-go after the spike (page Q19): Wordcraft, ONLYOFFICE Docs or Collabora Online, against Tiptap | the owner | `research-lead-workbench#33`, `lead-orchestration#LO19`, `report-delivery#RD6` |\n"
     "| — | Class A in Brave queries (page Q22): refused until answered | the owner | `deep-research-web-search#57` |\n"
     "| — | Search operators (`site:`, `filetype:`, `intitle:`) in queries (page Q23) | the owner | `deep-research-web-search#57` |\n"),
    ("### Open: signing does not answer these",
     "### The owner's answers relayed at 21:41 UTC (page Q19 to Q21)\n\n"
     "Relayed by the coordinator from the PM status page; recorded in\n"
     "[`answers-2026-10-20.md`](../evidence/scope-freeze/answers-2026-10-20.md) (fifth table).\n\n"
     "| Page | Answer | Chunks |\n|---|---|---|\n"
     "| Q19 | Evaluate before adopting: a W1 spike compares Wordcraft, ONLYOFFICE Docs and Collabora Online against Tiptap, a go/no-go to the owner | `research-lead-workbench#33` |\n"
     "| Q20 | The owner's determination: Brave may receive Class B (design-derived) queries for every client, CLASSIFIED included; Class A stays refused (Q22), operators open (Q23) | `deep-research-web-search#57` |\n"
     "| Q21 | The coordinator keeps merging reviewed, green PRs | — (no plan edit) |\n\n"
     "### Open: signing does not answer these"),
])

A = R / ".planning/evidence/scope-freeze/answers-2026-10-20.md"
t = A.read_text(encoding="utf-8").rstrip("\n")
t += """

## Page Q19 to Q21

Relayed by the coordinator at 21:41 UTC; the planning session did not read the page itself. The
owner's notes are quoted as relayed.

| Page id | Question | Choice | Answer |
|---|---|---|---|
| Q19 | Adopt Wordcraft as the editor | a | Evaluate first: a spike compares Wordcraft, ONLYOFFICE Docs and Collabora Online against Tiptap. "maybe suggest alternatives, maybe tiptap, but even that had a terrible UX; I want as close to Microsoft Word or LibreOffice as possible" |
| Q20 | Brave for Class B queries | b | Brave may receive Class B (design-derived) queries for every client, CLASSIFIED included; the owner's determination of 2026-10-20. "maybe even class A, depends how the query is constructed. I like to implement google search hacking into the workflows, to create highly specific and reputable sources" (follow-ups Q22, Q23) |
| Q21 | Merge authority | a | The coordinator keeps merging reviewed, green PRs |
"""
A.write_text(t + "\n", encoding="utf-8")
