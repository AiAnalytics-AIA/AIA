"""Apply the scope freeze (2026-10-20) to the child plans: new chunks in front matter, one body section each."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
PLANS = ROOT / ".planning/plans"
SRC = ("Source: the owner's answers of 2026-10-20 "
       "(`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from "
       "`decision-list.md`), applied by freeze step 4; the proposals they settle are in "
       "`proposed-edits.md`.")

P = {}

P["signed-off-sociomap-method"] = (
    [
        "8. aia-sociomap-5 the only method of new runs: the code's default pins -5 by its own name, -1 to -4 leave every product path (run pins, Metodika presets and in-force, the web, the report), Metodika's in force is -5 (D-13)",
        "9. The report draws -5: object-map figure from heights.relative and the terrain method, objects_not_placed listed, credibility in place of Stress-1, the respondent-map and taste-segment figures (D-13)",
        "10. Methodology is edited only by the methodologist: storing and activating a methodology version needs the methodologist's permission (D-14; its exact form is open, master § The scope baseline, Q4)",
    ],
    """
**New chunks.**

- **8 (W1).** The product owner's D-13: "make aia 5 the only version … get rid of any functionality
  of the old ones. maps are drawn according to the current 5." A new run pins `aia-sociomap-5` by its
  own name (not `+e<n>`), at its spec fingerprint, alone: `default_methods()` stops returning `-1` and
  `-3` (`domain/research_sociomap.py:323-330 @ 854c209`). Metodika's `in_force` becomes `-5`, its
  presets offer `-5` only, and an edit starts from the version in force (today `presets[0]`, `-4`:
  `MethodologyVersions.tsx:79-86 @ 854c209`; its test `MethodologyVersions.test.tsx:258` changes with
  it). The worker image's `NUMBA_CACHE_DIR` and library versions are recorded with each map (packet
  E-6). Tests: a new run pins exactly `aia-sociomap-5` at `8b0b4864…`; no product path offers `-1` to
  `-4`; `require_client_facing` passes for a `-5` map once the register entry exists and refuses
  `-5+e1`. **Open, recorded in the master plan's baseline:** when the switch merges relative to the
  methodology owner's register entry (Q1), what a stored `-1`/`-3` run shows once the old drawing is
  gone (Q2), and whether the old engine code and its golden fixtures are deleted or kept as reference
  (Q3). The register entry itself is the methodology owner's (packet MQ-01).
- **9 (W2, before E15).** The report's map chapter and figures for `-5`: z from `heights.relative`,
  the caption from the terrain method, `objects_not_placed` listed (today dropped:
  `object_map_figure.py:39, 64-104 @ 854c209`), credibility in place of Stress-1
  (`report_maps.py:215-220`), and the respondent-map and taste-segment figures
  (`segment-maps-and-drilldown#9`). How the report re-derives a `-5` map follows MQ-04 (E-7).
- **10 (W1).** D-14: "only the mathematician can edit the methodology." Storing and activating a
  methodology version (today OWNER or ADMIN, ADR 0023) needs the methodologist's permission. Its
  form (a member mark an OWNER grants, whether activation is included, or a named account) is open
  (baseline Q4); the chunk builds the permission check and its refusal, and changes ADR 0023's role
  table in its PR's Doc follow-up.

**Measurement before MQ-06** (packet E-9): a `-5` map with respondents and segments on the develop
worker image at 1,500, 5,000 and 20,000 respondents, recorded in this plan before the methodology
owner answers MQ-06.
""",
)

P["deep-research-web-search"] = (
    ["51a. A run's routes on its record: by_route in CoverageLedger (sent, succeeded, refused) and composed_routes from the plan artifact (G67)"],
    """
**New chunk.**

- **51a (W1, E12).** No response names the routes a run used (`coverage.py:42-56, 102-125 @ 854c209`),
  which chunk 51's test, I-R and AC-11 require. `by_route` in `CoverageLedger` and `composed_routes`
  read from the plan artifact; a reused track counts under its original run. Test: a recorded run
  through `public-web-fetch`, one connector and the Wayback lookup lists exactly those route ids.

**Existing chunks, changed by the owner's answers.**

- **53 (D-10).** One refusal behaviour: a run refused for an unclassified design or an unapproved
  live setting **fails** as a terminal failure worded by its cause, retryable under fresh pins after
  the approval; no "Pokračovat v běhu" on it. The chunk's contradictory "still parks" test line is
  replaced; AC-11's negative case and I-R read "refused whole, retryable".
- **54 and `mvp-acceptance-harness#11` (D-11).** The acceptance study cites one known dead URL, so a
  real run meets the archive and the run's record names `archive_lookup` / `archive_fetch`.
- **Deep Research from the Lead (D-12)** is `lead-orchestration#LO5a`; its ceiling is chunk 55's.
- **The Lead's own web search** (D-35) is not this plan's until the owner answers baseline Q6.
""",
)

P["lead-orchestration"] = (
    [
        "LO5a. Deep Research from the Lead: a plan-step kind and a typed chat start, priced by deep-research-web-search 55's ceiling (D-12)",
        "LO12c. The composition digest stored on each run and served over HTTP (D-09; the record #513 called MP6b)",
        "LO17. Stopping the Lead: cancel a running turn, withdraw an approved plan (the current step finishes or is cancelled, nothing after it starts), with the workbench build line (D-18)",
        "LO18. The Lead's turns stream, take a file from the composer, and comment unprompted after the researcher pauses editing, each such comment a paid turn inside the wallet (D-39)",
    ],
    """
**New chunks.**

- **LO5a (W1, in E26 with E12).** D-12: Deep Research starts as a plan-step kind and as a typed chat
  start, with `deep-research-web-search#55`'s ceiling; `research-lead-workbench#26` keeps no Deep
  Research button as an exception. I22 names it. Test: after #26, at 1440 and 390 px, Deep Research is
  startable through the Lead only.
- **LO12c (W1, after LO12b).** D-09: AC-14 is reworded to typed settings plus a composition digest
  (AI runtime, model binding, switches) stored on each run and returned by
  `GET …/research/runs/{id}`. Test: the digest is present over HTTP; a worker on malformed settings
  exits non-zero by name.
- **LO17 (W1).** D-18: Esc during a turn stops it ("Zastaveno vámi. Nic nebylo přijato za vás.");
  "Zastavit plán" on a running plan's card. Tests: a cancelled turn applies nothing and its
  reservation settles; a withdrawn plan starts no further step.
- **LO18 (W3).** D-39, IN: streaming text (ADR 0026 left streaming "not decided"; this answer decides
  it), a file from the composer kept as the client's source or the brief's attachment by the existing
  paths, and unprompted comments after a pause, **each a paid turn charged to the wallet, shown as
  such**. Needs an ADR 0026 amendment in its PR. Test: an unprompted comment never fires when the
  wallet cannot cover a turn.

**Existing chunks, changed by the owner's answers.**

- **LO0 (D-01).** The money names: Rozpočet klienta (`clients.budget_usd`), Rozpočet studie
  (`budget_usd`; Settings' "Strop rozpočtu" is renamed), Peněženka (the wallet), Práh potvrzení
  (`spend_confirm_usd`), written once in the copy module.
- **LO1 (D-03, D-05).** A raise above the client's wallet ceiling is refused, naming who can raise
  the ceiling (OWNER or ADMIN on Profil → Pravidla, `client-knowledge-lifecycle#K11`); there is no
  approver queue. A Deep Research run is charged at its ceiling until migration M11 reconciles tool
  spend.
- **LO3 / LO10 (D-04).** On a Design Revision move a plan finishes the steps tied to its immutable
  revision and stops only the steps that would start from the working copy.
- **LO4 / LO9a (D-02).** The card shows each step's ceiling against the threshold; the plan's approval
  records a confirmation for each shown ceiling; a step whose ceiling grew since parks. AC-04 follows.
- **LO11 (D-32, D-33, D-34).** Each researcher has their own Lead, built and named by them (free
  text), never transferred: the handover, the departure trigger and an admin's reading of another
  researcher's Lead files are **out**. LO11 keeps the Lead's file history (readable, restorable
  revisions) and F14's learning rules. Whether a study has one assigned lead researcher an admin can
  change ("an admin can change the research lead") is open (baseline Q5). ADR 0030 is narrowed in its
  own PR accordingly.
- **LO12a (D-10).** Every API error in Czech with a no-leak test and a native copy review; the words
  for a refused Deep Research run (terminal, by cause).
""",
)

P["research-lead-workbench"] = (
    [
        "29. Conversation controls: older-message paging (with its route), copy, edit and resend, ArrowUp to edit the last message, send-now and edit for a queued message (D-38)",
        "30. The conversation's UI for LO18: streamed text, a file from the composer, unprompted comments marked as paid turns (D-39)",
        "31. Results: charts on the result views and a CSV/XLSX export of the per-question tables from admitted claims (report-delivery RD12) (D-41)",
    ],
    """
**New chunks.** 29 (W2), 30 (W3, with `lead-orchestration#LO18`), 31 (W3, with
`report-delivery#RD12`). D-38, D-39 and D-41 were answered **in** whole.

**Existing chunks, changed by the owner's answers.**

- **20 (D-13).** The map views draw `aia-sociomap-5` only: the method named, relative-height terraces,
  the credibility banner, split-half share and uncertainty circles, "Neumístěno", the respondent map
  and taste segments, following `ui_app.html`'s drawing (packet E-3, the owner's standing rule). The
  `-1`/`-3` drawing leaves the product; what a stored older run shows is baseline Q2.
- **15.** Mount `ItemInspector` (imported only by its own test) and fix provider waits reading as
  inert (`research/lane.ts:134 @ 854c209`).
- **26 (D-12).** No Deep Research button survives as an exception; Deep Research starts through the
  Lead (`lead-orchestration#LO5a`).
- **Map node drag** (D-40) is **out**: camera-only view operations satisfy AC-09.
""",
)

P["report-delivery"] = (
    [
        "RD11. Deep Research context in the client report: accepted findings as cited context in its research-context chapter, labelled external, never respondent evidence (MVP-26)",
        "RD12. Export of a run's per-question tables as CSV and XLSX, every cell an admitted claim for the surface (D-41)",
    ],
    """
**New chunks.** RD11 (W3), already decided by MVP-26 and missing a chunk. RD12 (W3), D-41 in.

**Existing chunks, changed.**

- **RD0 (G63, G64).** Result numbers are ledger refs; design and method facts (the planned n, scale
  ends, filter bounds) are typed blocks fed from the specification and exempt; the validator checks
  every other prose number. The "Interní dokument" mark is read from the frozen `KnowledgeSource`
  (`client-knowledge-lifecycle#K8`), and RD0 checks both deliverables.
- **RD3 (G66).** The approve response and review state carry the report's kind; `internal_only` is
  false for `research_client_docx`.
- **RD6.** D-35's answer ("the lead agent can help change" the documents, joining paragraphs, copy)
  widens what a report edit may do; how far, and whether the number rule still binds it, is
  baseline Q6. Until answered, RD6 is built to ADR 0035 with merging allowed (refs unioned).
""",
)

P["segment-maps-and-drilldown"] = (
    ["11. Sociomapa matrix and comparison modes: two maps side by side, over aia-sociomap-5's maps (D-42)"],
    """
**New chunk.** 11 (W3), D-42 in.

**Existing chunks, changed.** D-13 makes `aia-sociomap-5` the only method: 1-3 build on `-5`'s stored
respondent map and taste segments rather than the contract-3 route (G59); how descriptor segments and
`-5`'s taste segments relate is the methodology owner's (MQ-02, MQ-05), and these chunks wait on it.
9 and 10 name `-5`'s fields; 9's figures are `signed-off-sociomap-method#9`'s.
""",
)

P["working-copy-edit-ops"] = (
    ["WCE14. A stimulus item: content shown to respondents before a question (respondents.context), in the edit vocabulary and the design (D-45)"],
    """
**New chunk.** WCE14 (W2), D-45 in; fieldwork carries it (`run-qc-and-checkpoint#RQC13`).

**Existing chunks, changed by the owner's answers.**

- **WCE0 / WCE5 (D-06).** Conflicts are per `(item_key, field)`.
- **WCE7 / WCE9 (D-07).** An unaccepted change is `REJECTED`; `DROPPED_STALE` when it conflicted.
- **WCE4.** One feed name, `…/workspace/ops?since=`.
- **WCE8 (D-30).** The lock covers the declared inputs and the sets they rate.
- **WCE11 (D-31).** A named server path accepts a structural change under the person's standing
  choice; the switch is per stage on Můj Vedoucí, off by default.
- **WCE1** gains no decision, expected-answer or done-when kinds: the question chain is **out** (D-44).
""",
)

P["run-qc-and-checkpoint"] = (
    [
        "RQC12. Weight identity over HTTP: weight_role and weight_column in the run's population note and in the report's method section (G78)",
        "RQC13. Fieldwork shows a question's stimulus to each respondent before the question, recorded in the answer's provenance (D-45)",
    ],
    """
**New chunks.** RQC12 (W1). RQC13 (W2, after `working-copy-edit-ops#WCE14`); a stimulus changes the
respondent's input, so its prompt part is pinned with the run like the rest of the respondent system.

**Existing chunks, changed.**

- **RQC4 / RQC5 (D-36).** After a replacement the report and the Lead read the newer run and name
  both.
- **RQC9.** The valid-n authority is the organization's readiness methodology in force, not a code
  constant.
- The attention check (D-43) is **out**.
""",
)

P["mvp-acceptance-harness"] = (
    [
        "16. The per-number provenance walk for AC-15: every ledger ref of both reports resolves to its model binding, prompt pin, population version and weight role (G65)",
        "17. The acceptance verdict computed from its own JUnit, path parity beside it and never in it; parity-matrix project.memory corrected (G75)",
        "18. Performance budgets as a release gate: page and API latency budgets per journey (D-48; the numbers are open)",
    ],
    """
**New chunks.** 16 (W3), 17 (W0, E01), 18 (W4; D-48 in, its budget values open in the baseline).

**Existing chunks, changed.**

- **3 (G76).** A declared operator bootstrap (`aia_executors.seed`, or production's
  `production-environment#PE10`), named in the record; everything after it over HTTP, the worker as a
  subprocess; an import-linter contract that `tests/acceptance` imports no application or
  infrastructure module.
- **5.** Its front matter's "the built ones first (AC-01, 06, 07, 12, 14)": only AC-12 is an existing
  path. Its wave: W5 (E24) governs.
- **6 (G77).** The record is per criterion per tier; each criterion carries its tier-A and tier-B
  projection, AC-15's AWS clause included.
- **10 (D-48).** Axe in every browser journey: a serious or critical violation fails it.
- **11 (D-11).** The acceptance study cites one known dead URL.
- **14.** AC-01 reads "a user of another organization gets 404, not 403, on every study route"
  (ADR 0019; G73). AC-14 reads "typed settings refuse a malformed value by name; each run records its
  composition digest" (D-09, `lead-orchestration#LO12c`). The three 18.6.6 ledgers are refreshed and
  the L-04 / L-29 contradiction removed.
""",
)

P["client-knowledge-lifecycle"] = (
    [
        "K9. A cross-client what-needs-me portfolio: every study waiting for the signed-in researcher, across clients (D-47)",
        "K10. Project memory searches approved reports too, beside designs (D-47)",
        "K11. Profil → Pravidla: the client's data posture and wallet ceiling, set by an OWNER or ADMIN, listed read-only in Settings (D-17)",
        "K12. The Simulace tab and its new-simulation button hidden until simulation is built (MVP-31)",
    ],
    """
**New chunks.** K9 (W3), K10 (W3), K11 (W1, with `deep-research-web-search#53` and
`lead-orchestration#LO1`; part of I15), K12 (W1; #513 proposed `client-workspace#C10`, which is taken).

**Existing chunks, changed.** K8 freezes the "Interní dokument" mark on the frozen `KnowledgeSource`
at enqueue (G64; a bundle-contract change needing ADR 0021's defect note). The fold of
`client-workspace` C6-C9 lands here: C6 → K2f/K3, C8 → `client-data-in-analysis#2/2a/3` with its UI
chunk `client-data-in-analysis#10`, C9 → K6; C7 is closed as superseded by `client-budget`.
""",
)

P["develop-spend-attribution"] = (
    ["6. An organization's monthly spend, read-only for OWNER and ADMIN in Settings: model, Brave and other tool spend across clients, from the content-free rows MVPQ-07 keeps (D-47)"],
    """
**New chunk.** 6 (W3), D-47 in. **5b** gains the infrastructure-charges line.
""",
)

P["production-environment"] = (
    [
        "PE10. An audited operator command that creates the first organization and its owner; production starts empty (D-22)",
        "PE11. An external security review of the production hostname before the first client (D-23)",
    ],
    """
**New chunks.** PE10 (W1), PE11 (W4).

**Existing chunks, changed by the owner's answers.**

- **PE0-PE3 (D-20).** The proposed sizes are accepted (`t3a.large`, `db.t4g.medium`, measured on
  develop first). Production moves to a **new domain**, not yet named: open in the baseline.
- **PE1.** A content security policy.
- **PE4 (D-19).** The proxy blocks private and metadata ranges only; the application's per-hop checks
  are the boundary.
- **PE7 (D-21).** Tagged application inference profiles in production.
- **PE9a (D-25).** RPO 24 h and RTO 4 h, the database and S3 restored together, proved once.
- **PE9b (D-26).** GlitchTip already runs for errors (the owner, "i have glitchtip implemented");
  an uptime probe and a named on-call recipient are open (baseline Q7).
- **The release checklist (D-28).** Terms, a privacy notice, a client DPA and the data owner's
  confirmation that the panel licence covers paid deliverables, all before the first client; the
  first-sign-in notice is the only screen.
""",
)

P["two-roles-human-ai-gates"] = (
    ["8. Deactivating a member from Settings → Přístup: access ends at once, audited (D-27)"],
    """
**New chunk.** 8 (W2), D-27. Membership is the access (ADR 0019), so removal is its only control.
""",
)

P["study-data-lifecycle"] = (
    ["SDL4b. Deleting one client source, its bytes and readings, by any researcher from the source's card (D-29)"],
    """
**New chunk.** SDL4b (W4), D-29.

**Existing chunks, changed.** SDL3 (D-29) gains its entry points: an OWNER or ADMIN deletes a client
from Settings with a typed confirmation; knowledge is retired, never deleted. Export of a client's
data and erasing one person are an operator procedure in the runbook for about ten users. SDL5
(D-25): RPO 24 h, RTO 4 h.
""",
)

P["architecture-enforcement"] = (
    ["12. Per-member rate limits on writes (about 60 per minute, then 429 in Czech) (D-24)"],
    """
**New chunk.** 12 (W3), D-24.
""",
)

P["client-data-in-analysis"] = (
    ["10. The data contract accepted in the study's Brief drawer with its quality report; the Data tab shows the accepted contract read-only (D-37)"],
    """
**New chunk.** 10 (W3, with 2 and 2a), D-37; it replaces `client-workspace` C8's "V AIA zatím není".

**Existing chunks, changed.** 0 (G51): the methodology owner decides a client number's support,
metric and interval (packet MQ-18).
""",
)

P["system-prompts-settings"] = (
    [],
    """
**Existing chunk, changed.** 14 (D-15) also removes `prompt_version` and its two refusals from
`POST …/agent-jobs` (`apps/api/src/aia_api/routers/research.py:2588-2595 @ 854c209`): no paid start
outside the Lead stays reachable over HTTP.
""",
)

P["assumptions-and-open-answer-coding"] = (
    [],
    """
**Existing chunks, changed.** AOC0 / AOC2 (D-16): SUPPORTED and CONTRADICTED need at least one
admitted respondent claim; an external finding is context, labelled. AOC2 names its producer (G72):
an assumption inherits its linked research question's EVIDENCE items, with no engine change.
""",
)

P["evidence-integrity"] = (
    [],
    """
**Existing chunks, changed.** 5 (G61): its test reads "one authority per evidence source", and AC-08's
row names it. 1 moves from E20 to E32 (G62), before its W1 consumer 9a.
""",
)

P["sociomap-formula-corrections"] = (
    [],
    """
**Existing chunks, changed.** D-13 makes `aia-sociomap-5` the only method, so 3 (the respondent map
on the contract-3 route) is superseded by `-5`'s respondent map once the methodology owner confirms
which of this plan's open items `-5` makes moot (packet MQ-05). Until then nothing here is built
against `-3`.
""",
)


def apply(name, chunks, body):
    f = PLANS / f"{name}.md"
    lines = f.read_text(encoding="utf-8").split("\n")
    assert lines[0] == "---"
    end = lines.index("---", 1)
    new = [f'  - "[ ] {c}"' for c in chunks]
    lines[end:end] = new
    text = "\n".join(lines).rstrip("\n") + "\n\n## Scope freeze (2026-10-20)\n\n" + SRC + "\n" + body
    f.write_text(text.rstrip("\n") + "\n", encoding="utf-8")


for name, (chunks, body) in P.items():
    apply(name, chunks, body)
print("applied", len(P))
