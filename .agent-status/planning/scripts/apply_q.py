import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
PL = ROOT / ".planning/plans"


def edit(path, pairs):
    s = path.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path.name, old[:70], s.count(old))
        s = s.replace(old, new)
    path.write_text(s, encoding="utf-8")


def add_chunks(name, chunks, body):
    f = PL / f"{name}.md"
    lines = f.read_text(encoding="utf-8").split("\n")
    end = lines.index("---", 1)
    lines[end:end] = [f'  - "[ ] {c}"' for c in chunks]
    text = "\n".join(lines).rstrip("\n") + "\n" + body
    f.write_text(text.rstrip("\n") + "\n", encoding="utf-8")


QSRC = ("the owner's answers to the baseline's Q1-Q8, 2026-10-20 19:37-19:46 UTC "
        "(`.planning/evidence/scope-freeze/answers-2026-10-20.md`, second table)")

# ---- signed-off-sociomap-method
edit(PL / "signed-off-sociomap-method.md", [
    ('  - "[ ] 10. Methodology is edited only by the methodologist: storing and activating a methodology version needs the methodologist\'s permission (D-14; its exact form is open, master § The scope baseline, Q4)"',
     '  - "[ ] 10. Methodology is edited only by the methodologist: a Metodik member mark an OWNER grants (held by A. Bahbouh) gates storing and activating methodology versions (D-14, Q4)"\n'
     '  - "[ ] 11. Metodika shows -5 in full: the comparison (MapSummary) carries credibility, the respondent map and taste segments, and the -5 steps are what in force describes (Q8)"'),
    ("""**Open, recorded in the master plan's baseline:** when the switch merges relative to the
  methodology owner's register entry (Q1), what a stored `-1`/`-3` run shows once the old drawing is
  gone (Q2), and whether the old engine code and its golden fixtures are deleted or kept as reference
  (Q3). The register entry itself is the methodology owner's (packet MQ-01).""",
     """**Settled by the owner (Q1-Q3).** It merges **when built**: every `-5` map stays
  `INTERNAL_ONLY`, and no map reaches a client, until the methodology owner's register entry exists
  (packet MQ-01, asked first). A stored `-1`/`-3` run keeps its data and numbers; its map panel says
  "Mapa ze starší metody; spusťte běh znovu" and draws nothing. `-1` to `-4` leave every product
  path, while the old engine and its golden fixtures F1-F9 stay in the code as tested reference
  (their deletion is a later decision, once `-5` has golden fixtures of its own)."""),
    ("""- **10 (W1).** D-14: "only the mathematician can edit the methodology." Storing and activating a
  methodology version (today OWNER or ADMIN, ADR 0023) needs the methodologist's permission. Its
  form (a member mark an OWNER grants, whether activation is included, or a named account) is open
  (baseline Q4); the chunk builds the permission check and its refusal, and changes ADR 0023's role
  table in its PR's Doc follow-up.""",
     """- **10 (W1).** D-14 and Q4: a "Metodik" mark on a member, granted and withdrawn by an OWNER
  (audited), held today by A. Bahbouh, gates **both** storing and activating a methodology version
  (today OWNER or ADMIN, ADR 0023). Any member still reads Metodika and runs check and compare.
  Tests: an ADMIN without the mark is refused by name on store and on activate; the mark's grant and
  withdrawal are audited. ADR 0023's role table changes in its PR's Doc follow-up.
- **11 (W2, after 8).** Q8, against the planning session's recommendation: Metodika's comparison
  shows **all** of `-5`'s outputs. `MapSummary` (`domain/methodology/sociomap_check.py:136 @
  854c209`) carries credibility (split-half share, uncertainty radius), the respondent map
  (placed / faded counts) and taste segments, so an edit of any `-5` parameter shows its effect;
  "v platnosti" describes the `-5` steps ("Věrohodnost mapy", "Respondenti a podpora mapy", S7) and
  the `-3`-only steps are not shown as in force. The comparison runs on the API host: its latency on
  the fixed panels is measured in the chunk's PR (BB1 at about 9 s compiled is the methodology
  owner's figure)."""),
])

# ---- lead-orchestration
add_chunks("lead-orchestration", [
    "LO19. A study's context file: a Markdown file per study, built by code from the study's shared state and refreshed on every change, read by every researcher's Lead in that study as its study layer (Q5)",
    "LO20. Hledat na webu: the Lead's governed web search through RetrievalGate, several results with inline citations in the turn, OPEN clients only, each search charged to the wallet (Q6)",
], f"""
### After the baseline's questions ({QSRC})

- **LO11 (Q5): no study assignment.** Every researcher's own Lead works in every study they open; an
  admin assigns nothing. The owner: "opening a study, just shows their own agent within that studies
  artifacts, and now their ai agent can interact with the artifacts of that study and control the
  functions and valves in them … he carries his own files, but also the context of each study
  session." The open study-assignment question is closed.
- **LO19 (W2, after LO8 and `working-copy-edit-ops#WCE4`).** The owner: "maybe we need to have an md
  file attached to each study session so the researchers ai can get the context of the study, this
  should be updated regularly within each study." Proposed shape, pending the one question sent to
  the owner (who may write its prose part):
  - **What it holds.** The study's shared state, never any researcher's private turns: the brief and
    research questions, each stage's state, the Design Revision head and what changed since the
    last one (from the operation log), runs and their states, approved results and report state, the
    decisions in the approval ledger (accepted and refused changes, approvals, spend confirmations),
    and open items. Each line names its source (revision, run, ledger row).
  - **Who writes it.** Code, as a deterministic projection of that state (no model call, no cost);
    rebuilt on every working-copy revision, run event and ledger decision, so it is always current.
  - **Its class.** The highest class of what it holds by `material_rules.py`: Class B for a design,
    Class A when it carries approved client knowledge; it is sent only to a route approved for that
    class.
  - **How it fits ADR 0026.** It becomes the content of `freeze_context`'s existing `study` layer
    (`domain/research_lead.py:782-829 @ 47e5536`) with a byte budget of its own inside the 96 KB;
    when over budget the oldest history lines go first, and the omission is named. It feeds the
    frozen context, never replaces it: each turn freezes the file's version it read, so a turn stays
    reproducible.
  - **Where it shows.** Readable in the study (the Lead pane's "Kontext studie"), with its version.
  - Tests: two researchers' Leads read the same file; no private turn text appears in it; a run event
    rebuilds it; a turn records the file version it read.
- **LO20 (W3, after `deep-research-web-search#56`).** Q6, with the owner's note: "i really want to
  preserve a good UX here, and not have limited results." The Lead calls Hledat na webu as a tool:
  code sends the query through `RetrievalGate` (posture, class, egress, metering, journal) as a
  single-track lookup (`deep-research-web-search#56`): several search results at once (a list of
  titles, snippets and links), the top pages fetched and captured in parallel, and the Lead's answer
  cites each claim inline with its link and quote, labelled "externí zdroj", never respondent
  evidence. No extra click: the results stream into the turn. OPEN clients only; for a CLASSIFIED
  client the Lead says it may not search and why. Each search and fetch is charged to the wallet and
  shown with its cost. A captured page can be added to Client Knowledge by the existing "Ověřeno,
  přidat zdroj". **Needs an ADR first** (a new ADR after 0038 for the Lead's lookup tool, and ADR
  0017's scope widened to it); the chunk's PR carries it Proposed.
""")

# ---- deep-research-web-search
add_chunks("deep-research-web-search", [
    "56. A quick single-track lookup for the Lead's Hledat na webu: several search hits and parallel fetches of the top pages through RetrievalGate, captured snapshots, per-call cost against the wallet, OPEN posture only (Q6)",
], f"""
### After the baseline's questions ({QSRC})

- **56 (W3).** Q6: the retrieval half of `lead-orchestration#LO20`. A lookup is one track, not a
  run: one query (or a few the Lead writes), the route's hits returned together (a page of results
  per query, the route's own page size), the top pages fetched in parallel with the existing per-host pacing, each captured as
  a content-addressed snapshot so a quote can be grounded, everything journaled and metered as
  chunk 47's coverage counts it. It reuses the engine's retrieval and grounding unchanged (ADR 0021:
  the engine stays frozen; this is a new caller, not a change to the run's steps). Latency target:
  first results to the Lead within the route's own response time, measured in the PR. Tests: a
  CLASSIFIED client's lookup sends nothing; a lookup's spend is held against the wallet before it
  leaves; a quote not in a captured snapshot is refused.
""")

# ---- research-lead-workbench
add_chunks("research-lead-workbench", [
    "32. The Lead pane's web results: inline citations with links and quotes, the result list as it arrives, each search's cost, and Kontext studie (the study's context file) readable with its version (Q5, Q6)",
], f"""
### After the baseline's questions ({QSRC})

- **32 (W3, with `lead-orchestration#LO19` and `#LO20`).** The UI half: a search's results appear in
  the turn as they come (no click to open them), each claim with its inline citation, a captured page
  one click from "Ověřeno, přidat zdroj"; the study's context file is readable from the pane.
""")

# ---- report-delivery RD6
edit(PL / "report-delivery.md", [
    ("""- **RD6.** D-35's answer ("the lead agent can help change" the documents, joining paragraphs, copy)
  widens what a report edit may do; how far, and whether the number rule still binds it, is
  baseline Q6. Until answered, RD6 is built to ADR 0035 with merging allowed (refs unioned).""",
     """- **RD6 (D-35, Q6).** The Lead edits a report as the researcher asks: rewrite, merge or split
  paragraphs, move sections (the client report's chapters included), copy edits. **Every number stays
  an admitted ledger ref**: a merge unions the refs, a split divides them, and no typed number is
  accepted. The exact edited version is what a person approves. ADR 0035 is amended in this chunk's PR
  (ref-set equality per paragraph becomes "every number a ref"; `section_move` allowed on every
  chapter)."""),
])

# ---- production-environment PE9b
edit(PL / "production-environment.md", [
    ("""- **PE9b (D-26).** GlitchTip already runs for errors (the owner, "i have glitchtip implemented");
  an uptime probe and a named on-call recipient are open (baseline Q7).""",
     """- **PE9b (D-26, Q7).** GlitchTip already runs for errors (the owner, "i have glitchtip
  implemented"). Production adds a GlitchTip uptime monitor on its `/health`, alerting Nigel Blount
  by e-mail (its threshold set and stated in the chunk's PR); no other service."""),
])
print("ok")
