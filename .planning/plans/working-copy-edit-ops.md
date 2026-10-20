---
status: planned
chunks:
  - "[ ] WCE0. The contract: the closed operation set, ids, validation, the lock rule and the text-only marker, with one shared fixture (tests/fixtures/edit_ops/cases.json) read by the Python and the TypeScript tests"
  - "[ ] WCE1. Stable item identity: ids for objectives, research questions, hypotheses, options, battery objects and sections; existing content gets ids on load; `FOCUS_ID` and `design_items` keys use them"
  - "[ ] WCE2. `workspace_edit_ops` (M1) and `apply_edit_ops`: the one writer of the working copy; every other writer becomes a recorded whole-copy operation"
  - "[ ] WCE3a. The web store on the server vocabulary, Brief and Design stages"
  - "[ ] WCE3b. The web store on the server vocabulary, Questionnaire (manual operations, move, remove, reference by stable id)"
  - "[ ] WCE3c. The web store on the server vocabulary, Audience, Dimensions and Sample"
  - "[ ] WCE4. Presence (M2) and the change feed: `study_presence`, `GET changes?since=`, a poll, two sessions"
  - "[ ] WCE5. Item-level merge and a stale rule that a later Design Revision does not defeat"
  - "[ ] WCE6. Per-change accept (M6): `proposal_change_decisions`, one change identity across the three accept routes, a dependency rule for coupled changes, `touched_items` returned to the web; any member with the accept permission may accept a proposal another member's Lead prepared (Q16), the chat text staying private"
  - "[ ] WCE7. Readiness and impact on a working revision: readiness without a submitted Design Revision, "current / changed / re-check" per stage, and accepting a working copy as a revision"
  - "[ ] WCE8. Sociomap declarations: an editor for `sociomap_rating` and `context_objects`, the hard lock and `sociomap_unlock`"
  - "[ ] WCE9. Undo and restore of a person's edit, and a route that reads an old working revision"
  - "[ ] WCE10. The Lead's edit vocabulary widened (Audience, Dimensions, Sample), with a prompt and harness version and an `is_text_edit` ruling per operation"
  - "[ ] WCE11. Auto-apply per stage (MVP-14, D18): the researcher's `auto_accept_text_edits` gains a per-stage structural choice, off by default"
  - "[ ] WCE12. Journey: two researchers, one study, recorded doubles (the I-1 exit)"
---
# Working-copy edit operations, merge and the Sociomap lock

The work that lets two researchers, each with their own Lead, edit one working copy through one server-validated vocabulary, with per-change accept, a merge that is item by item, presence and a hard lock. Written 2026-10-19 from the cohesion traces (`.planning/evidence/mvp-master-traces/trace-1-design.md`); anchors are there.

**Owner: S1.** Takes the gap rows G14, G18, G19, G21, G22, G24 and interfaces I2, I8, I9, I11 of `mvp-master-plan.md` §6.1 and serves AC-02, AC-03, AC-07 and gate I-1.
Every chunk below is **open**; a chunk is built from this file, not from the master plan.

## Decisions this plan carries (settled by the owner; not re-asked)

- One shared edit vocabulary: a person and the Lead use the same server-validated operations (cohesion F11).
- Per-change accept and reject; the unit of acceptance is the revision; identity is a stable id and the number is only a label (F11).
- The manual AI buttons are removed; every AI action goes through the Lead (D15, MVP-8).
- An append-only log of every operation, kept with its study (Q27); presence by polling plus a heartbeat in PostgreSQL, no push service (target architecture §3.2).
- A hard lock on Sociomap inputs with a recorded unlock the Lead can never call (Q15).
- Structural edits may auto-apply per stage, off by default, each one still a working revision and a ledger row marked auto (MVP-14, D18). Text-only is the **default and the only automatic accept until a researcher turns a stage on**; the "text only" sentences in cohesion F11 and the architecture mean that default.

## Chunks

**WCE0. The contract: the closed operation set, ids, validation, the lock rule and the text-only marker, with one shared fixture (tests/fixtures/edit_ops/cases.json) read by the Python and the TypeScript tests**  
Writes `domain/edit_ops.py` and the fixture before any writer changes. Replaces the duplicated rules (`applyLeadEdit` against `apply_edit`; `trace.ts` against `research_trace.py`) with one fixture. Test: both languages pass the same cases. Interfaces I2.

**WCE1. Stable item identity: ids for objectives, research questions, hypotheses, options, battery objects and sections; existing content gets ids on load; `FOCUS_ID` and `design_items` keys use them**  
Today those items are keyed by normalised text (`design_items.py:120-172`), so a reword is a remove and an add, links break and `FOCUS_ID` cannot name them. Test: a reword keeps its research-question links; two people adding different questions to one section do not touch the same key; a section move is an item.

**WCE2. `workspace_edit_ops` (M1) and `apply_edit_ops`: the one writer of the working copy; every other writer becomes a recorded whole-copy operation**  
The PUT, questionnaire import, reuse, the 18.6.6 migration, Design Research accept and the web autosave are the six other writers; none may change a locked item or skip the log. Test: a whole-copy write leaves an op and cannot change a locked item. Interfaces I8.

**WCE3a. The web store on the server vocabulary, Brief and Design stages**  
33 `store.update` sites in 9 files and about 1,900 lines of TypeScript with 18.6.6 parity tests are moved stage by stage; the parity tests stay green at every step.

**WCE3b. The web store on the server vocabulary, Questionnaire (manual operations, move, remove, reference by stable id)**  
Includes the @ pointer carrying id and revision (workbench 16) and the questionnaire import confirmation (an import replaces all sections and drops every research-question link today: it names what it would orphan).

**WCE3c. The web store on the server vocabulary, Audience, Dimensions and Sample**  


**WCE4. Presence (M2) and the change feed: `study_presence`, `GET changes?since=`, a poll, two sessions**  
Test: two sessions edit one study; each sees the other within a poll; a presence row expires without a heartbeat. Gate I-1. The feed also carries each pending proposal (change identity, item, proposer, status) with no chat text, so another member can accept it (`WCE6`, gap G42).

**WCE5. Item-level merge and a stale rule that a later Design Revision does not defeat**  
`proposal_accept.py:117-118` refuses on "head moved" before comparing items, and any job start, rebuild, Lead approval or a visit to the Run stage submits a Design Revision, killing every other pending proposal. The check becomes: stale only when an item the proposal touches changed since its baseline. Test: a revision submitted elsewhere does not stale a proposal on other items; the item-level conflict still does.

**WCE6. Per-change accept (M6): `proposal_change_decisions`, one change identity across the three accept routes, a dependency rule for coupled changes, `touched_items` returned to the web**  
The agent-job accept, Design Research `item_ids` and the Lead `indices` become one mechanism. A research-question reword and the questionnaire links that name it are one dependent group. Every accept writes the working revision **and** submits the Design Revision in one transaction, so the head equals the working copy after any accept (`proposal_accept.py:142-156`); the Lead edit accept (`research_lead.py:592-601`) saves only today and is fixed here. **Shared proposals (Q16, gap G42):** `decide_edits` takes the caller's own completed turn (`research_lead.py:515-518`), so another member cannot accept an edit block its author's Lead prepared. A proposed change becomes an artifact-level item addressed by its change identity (item, operation, base revision, proposer, status) and carried to the others by `WCE4`'s feed **without the turn's chat text**; accepting needs `EDIT_STUDY` and `APPROVE_GATE` and the item-level stale rule, not ownership of the turn. Tests: member B accepts a change member A's Lead prepared without ever reading A's turn; B cannot read A's turn text through the feed; a second accept of the same change keeps the first decision; the ledger names both people. Interfaces I9.

**WCE7. Readiness and impact on a working revision: readiness without a submitted Design Revision, "current / changed / re-check" per stage, and accepting a working copy as a revision**  
Hand edits create no Design Revision today and `impact_preview` has no route for a study, so AC-07 cannot be tested as written. Test: edit the questionnaire after a run; the stages after it read "reopened" and the run says its design is older than the head.

**WCE8. Sociomap declarations: an editor for `sociomap_rating` and `context_objects`, the hard lock and `sociomap_unlock`**  
Nobody can set the declarations (zero web hits), so the lock has no subject. The unlock is a ledger row (`sociomap_unlock`, M3), warns, and cannot be called by the Lead. Test: the whole-copy route cannot change a locked item. Interfaces I11.

**WCE9. Undo and restore of a person's edit, and a route that reads an old working revision**  


**WCE10. The Lead's edit vocabulary widened (Audience, Dimensions, Sample), with a prompt and harness version and an `is_text_edit` ruling per operation**  
Its operations today are `set_text`, `list_*`, `question_*` and `set_n`; `propose_audience` returns prose and `suggest_dimensions` an empty list. The valid n has one authority, the domain readiness limits (`run-qc-and-checkpoint#RQC9`).

**WCE11. Auto-apply per stage (MVP-14, D18): the researcher's `auto_accept_text_edits` gains a per-stage structural choice, off by default**  
Each applied edit is a working revision and a ledger row marked auto, with the undo of WCE9. Test: with a stage on, a structural edit applies when its turn finishes and can be undone; with it off, nothing structural applies without a click.

**WCE12. Journey: two researchers, one study, recorded doubles (the I-1 exit)**  
The second edit merges or conflicts on one item only; a locked item refuses; presence and the feed show. Member B accepts a change member A's Lead prepared without reading A's turn. Adds its steps to `workbench_journey.mjs` and the acceptance harness.

## Open: owner clarifications

- None for the owner. A research-question reword with a dependent questionnaire change is one group, accepted or rejected together, and a split that would leave the copy invalid is refused by the server's validation (`WCE6`); "content from revision n" is computed from where an item last changed, never stored (`WCE7`).


## Execution predecessors (2026-10-20)

WCE0 is the W0 contract for text and structural operations; its text-only marker limits the
default automatic acceptance, not the available manual edit vocabulary. S2 supplies the declared
Sociomap fields before W1 so WCE2 can enforce protected writes from its first implementation.
WCE1-WCE7, WCE10 and WCE12 are W1; WCE8-WCE9 and WCE11 are W2. WCE10 consumes RQC9's
single n authority. The W1 locked-write negative test uses the existing lock contract; WCE8 adds
the complete declaration/unlock editor. WCE11 cannot turn on before WCE9's recorded undo exists.
