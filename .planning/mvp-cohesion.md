# MVP cohesion — the seams between the plans (2026-10-19)

**What this is.** A cross-track review requested by the product owner on 2026-10-19, after the
MVP was redefined (`overview.md` § MVP roadmap, MVP-1 to MVP-33; `mvp-consolidation.md`;
`docs/migration/mvp-acceptance.md`, `MVP-ACCEPT-2`). `mvp-consolidation.md` classified each plan.
This file looks **between** them: where two decisions contradict, where a criterion has no plan,
and which code several plans edit at once. It is not a backlog. A feature's status stays in its
plan's front-matter (CLAUDE.md §4); where a plan disagrees with this file, the plan wins and this
file is stale.

**Reviewed state.** `origin/develop` @ `085abe0` with #491, #493, #494 and #495 merged in a
scratch tree (all four merge without conflict). Code anchors are `file:line @ 085abe0`; a claim
about a document in one of the four PRs names the PR. An unanchored claim is a **hypothesis** and
is labelled as one.

**Inputs read.** `CLAUDE.md`, `ARCHITECTURE.md` (all of §1-§10), ADR 0026 and 0027, the four PR
bodies, `mvp-consolidation.md`, the overview roadmap, `mvp-acceptance.md`, and the code listed in
each finding. `AGENTS.md` was skimmed by heading only (framework gotchas, no product decisions).
The other ~35 plan files were **not** read in full: findings about them rest on their
front-matter and on file-mention counts (§3), which is a weaker kind of evidence.

---

## 1. Verdict

The tracks are well ordered inside themselves and the decisions MVP-1 to MVP-33 are coherent as a
list. Five of the fifteen acceptance criteria cannot pass as the documents stand, because two
decisions contradict each other or no plan builds the thing (F1-F4, F7). The rest are orphan or
overlap problems that are cheap to fix now and expensive after three agents have built to
different readings.

| # | Finding | Hits | Needs the owner |
|---|---|---|---|
| F1 | Deep Research classification: OI-129 says operator-only and Class C routes; MVP-27 says the full design on a Class B route | AC-11 | decided 2026-10-19: whole design, derived queries may reach Class C routes; the ADR amendment and the mechanism are open |
| F2 | The Sociomap drill-down to one respondent contradicts "aggregate only" and "rows never sent to the browser" | AC-09, AC-13 | decided 2026-10-19: yes, the Lead may read it |
| F3 | Client-reported data (ADR 0027) has no field policy; MVP-29's single authority covers population fields only | AC-08, AC-10 | decided 2026-10-19: later, in the ADR 0027 plan |
| F4 | "The Lead sees everything stored about results" (MVP-15) has no contract, no owner and an unchecked data-class path | AC-02, AC-09 | no |
| F5 | Removing the manual AI buttons (MVP-8) is a UI change; the spend limit and the worker contract are server rules | AC-02, AC-03, AC-04 | no |
| F6 | Decision ids collide (D9 three times, M6 twice) | all | no |
| F7 | Eight pieces of work have no plan (§2) | AC-08..11, AC-15 | no |
| F8 | Nine open plans edit `tables.py`; five edit `ai_runtime.py`, `research_agents.py` and the settings router | all | no |
| F9 | Parity is "information" in the new contract and "blocking on FAIL" in CI | AC (none) | no |
| F10 | The USD 25 acceptance budget has no allocation | AC-04, AC-15 | no |
| F11 | How a person works an artifact by hand and how the Lead points at it (questionnaire first) | AC-02, AC-03 | decided 2026-10-19 |
| F12 | Two people editing one study, each with their own Lead: the designs assume one person and one Lead | AC-02, AC-07 | recommendation made; owner to confirm |
| F13 | Stage meaning and order: unit of acceptance, rail order, paid work without a card, locks | AC-02, AC-04, AC-05 | decided 2026-10-19 |

---

## 2. Findings

### F1. Deep Research cannot run on an edited design under both decisions

**Claim.** The owner decided on 2026-10-19 (OI-129) that Deep Research classifies a design by an
operator's exact-bytes record alone, that its web routes stay Class C only, and that a run on an
edited design parks until an operator classifies those bytes. The same day MVP-27 decided that
live Deep Research uses the full design on a provider approved for Class B. The Research Lead
edits the design continuously (MVP-14).

**Anchor.** `.planning/open-items.md:4121` (OI-129) and `apps/executors/src/aia_executors/deep_research/plan.py:163`
(`classify_material`, the operator's record only) @ `085abe0`; `ARCHITECTURE.md` §4 states both
regimes: Deep Research "operator's exact-bytes classification" and, a few bullets later, "a
respondent request takes its design's class … by the owner's rule (`domain/material_rules.py`)".

**Reproduction.** Hypothesis, not yet run: with a Class B route composed, start Deep Research on a
design edited since the last operator classification; `egress_unclassified_material` parks it
(the message is quoted in OI-129).

**Consequence.** AC-11 ("Design Research runs live on the full design") can only pass if an
operator edits `AIA_AI_MATERIAL_CLASSIFICATIONS` after every design change. The Lead, the design
jobs and the respondents all classify the same design by rule; only Deep Research does not.

**Smallest fix.** Once a Class B route exists, Deep Research classifies a design by
`MaterialRule.DESIGN` (Class B, raised and never lowered by an operator), exactly as
`ai_fieldwork.py` does. The routes' own `approved_for` then decides: the Class C routes (Wikipedia,
Brave) refuse a Class B query, the Class B provider accepts it. OI-129's park stays for a design no
rule can classify.

**Test that would have caught it.** `test_deep_research_journey.py` with an edited design and a
Class B recorded route: the web tracks run without an operator record.

**Owner answer (2026-10-19).** Neither an operator step after each edit nor a Class B-only
route: "Deep Research should take that whole design and use it to find as much relevant data as
possible." The manual operator classification is therefore not wanted. What replaces it is still
open, because of one constraint the answer meets: a Class C route (Wikipedia, Brave, Common
Crawl) may not receive Class B text, and a query's class is never lowered by keywords (ADR 0017).

**Open sub-question.** "As much data as possible" means one of:
(a) several routes approved for Class B under an EU agreement, so every query carries the
design's class; or (b) queries *derived* from the design that may reach Class C routes, which
needs a rule that lowers a derived query's class, an amendment to ADR 0017 and ADR 0008 and a
data-owner decision (the owner's 2026-10-19 OI-129 ruling said no class of its own is made for such
a query). **Owner answer (2026-10-19): (b), derived queries may reach Class C routes.** This reverses
ADR 0017 ("never lowered by keywords") and the owner's own OI-129 ruling of the same day, so three
things come before any code: an amendment to ADR 0017 and ADR 0008; the data owner's confirmation
(the licence and residency gates are the data owner's, not engineering's); and a mechanism enforced
by **code**, never by a prompt or a model's assertion (`ARCHITECTURE.md` §4: a prompt may state a
rule, it is never the only thing enforcing it). Hypothesis for its shape: a
derived query is Class C only when code can **prove** its content comes from a Class C source, by
provenance (a template filled only from terms a person declared public, or a query set a person
saw and marked public), never by a negative text test. A test that finds no client term, named
entity or verbatim design text is not enough: a model can paraphrase a confidential question with
none of those tokens (Codex review of #497, accepted). ADR 0017 decision 2 already says it:
"keywords can only raise a class, so a paraphrase of a client's brief without the names is still the
client's brief" (`docs/architecture/adr/0017-deep-research-external-retrieval.md:161-165 @ 085abe0`);
the amendment must change that sentence, not work around it. Everything else stays Class B. Recorded as
chunk 6 of `class-b-search-route` (#497).

### F2. The respondent drill-down contradicts the evidence rules

**Claim.** MVP-16 puts "filters and drill-down to one respondent's profile and answers" in the
Sociomap artifact. The evidence layer treats a panel answer as `AGGREGATE_ONLY` and
`PERSON_VALUE_MODELED`: "meaningful only in aggregate", "never one person's"
(`packages/aia_core/src/aia_core/domain/evidence/instrument.py:31, 43` @ `085abe0`).
`ARCHITECTURE.md` §4: "Respondent rows are never sent to the browser; the Sociomap artifact is
served only with `EDIT_STUDY`".

**Consequence.** Either the drill-down breaks the rule, or it is built as an unmarked exception
that the next reader removes as a bug. It also reaches the client report if "approved map
snapshots" (MVP-2) are drawn from the same view.

**Smallest fix.** Write the exception once, in `ARCHITECTURE.md` §4 (docs PR) and in the workbench
plan's chunk 20: the drill-down is a read-only **internal** display of the run's stored dataset,
served by one named route under `EDIT_STUDY`, labelled modelled, never an `AdmittedClaim`, never in
a client export (approved snapshots carry maps only, by the register), with its own API test.

**Related.** The straight-liner worker (MVP-12) must be computed by code (run QC, MVP-24); the
model sees only the flags, never rows. Replacing a flagged respondent changes the run's dataset and
so its identity: say whether that is a new run or a recorded exclusion (hypothesis: a new run).

**Test that would have caught it.** An API test that the drill-down route is absent from the
client-report path and answers 403 without `EDIT_STUDY`.

**Owner decision (2026-10-19).** Yes: the researcher may drill down to one respondent, and **the
Lead may read it**. Consequences, each a test: the exception above holds and the drill-down is
never exported; one respondent's modelled answers derive from the panel, so the Lead's route must
be the one the licence determination approves (`bedrock-eu-primary`, OI-61) or the gateway refuses
it (the F4 data-class test); the Lead says "modelled" whenever it quotes one respondent.

### F3. Client-reported data has no field policy

**Claim.** ADR 0027 (#494) adds the origin `CLIENT_REPORTED`, a fourth `origin_kind`, a data
contract and a "client-reported" grade. It says numbers pass "field policy, support, interval and
tier" but gives no policy for a client's columns. MVP-29 makes the population contract's 115
client-measurable fields the one authority; a client's dataset columns are not population fields.
Today `instrument.py` refuses any origin but the simulated and `MODELLED_AI_PANEL` ones (`-1`,
`-2`).

**Anchor.** `domain/fieldwork.py:88` (`CLIENT_ADMISSIBLE_ORIGINS`) and `:152` ("no fourth kind"),
`domain/evidence/instrument.py:112-121` @ `085abe0`; ADR 0027 §Consequences (#494).

**Consequence.** The first client-data number meets a gate that has no rule for it and refuses it
(fail closed, correct), so AC-10 cannot pass, and whoever builds it invents the policy.

**Smallest fix.** Add to ADR 0027, before it is accepted, a decision: a contract-accepted column's
policy comes from the **data contract** a person accepted (use, unit, period, rights), compiled by
code into a third instrument policy (`aia-instrument-evidence-3`, client-reported, not
`AGGREGATE_ONLY` for aggregates the client already aggregated). MVP-29 then reads: one authority
*per evidence source*, the population contract for panel respondents, the data contract for a
client's data. Also state one rule for personal columns: K2c **masks** them in the preview,
the analysis copy **drops** them, no model sees either (ADR 0027 decision 3 and
`domain/client_datasets.py:70, 144` @ `085abe0`).

**Test that would have caught it.** `test_every_origin_is_decided_once` extended, plus a gate test:
a `CLIENT_REPORTED` number with no accepted contract is refused by name.

**Owner decision (2026-10-19).** Decide later, in the ADR 0027 plan. The gap stays recorded here and
in that plan's first chunk; no client-data number may be built to admission before it is settled.
The contract-as-policy fix above is the recommendation, not adopted.

### F4. "The Lead sees all results" has no contract

**Claim.** MVP-15 and `mvp-consolidation.md` §6.2 size the Lead's results layer "M, design first".
No plan chunk carries it: the workbench plan's chunk 20 reads "re-layout" for Results and "asking
the Lead about an object or pair" for the Sociomap (#491). Today the Lead's context holds a run's
id, status and design revision only (`application/research_lead.py:858-891`, per
`mvp-consolidation.md` §6.1).

**Why it is a cohesion problem, not a task.** The layer reads from three tracks: C (maps, pair
statuses), D (client-reported results, once ADR 0027 lands) and E (admitted claims, module texts,
report drafts). It is also classified: ADR 0026 classifies the design and message as material, and
panel-derived aggregates carry a licence lineage that only `bedrock-eu-primary` may receive (OI-61,
`ARCHITECTURE.md` §4). The Lead has its own model since #488 (`AIA_AI_RESEARCH_LEAD_MODEL_ID`).
Whether that profile is the route the licence determination names is **unverified** (hypothesis).

**Smallest fix.** One contract, written before chunks 20 and 21:
`ResultsContext` = admitted claims only (each with `origin_kind`), map pair statuses, module texts
as unapproved text, report draft ids, bounded and classified before any model reads them. Track B
owns the type; C, D and E each supply a provider function. Add a chunk "Lead results context" to
`research-lead-workbench.md` before 20, and a data-class test: the Lead's configured route is
refused panel-derived lineage unless it is the approved route.

**Test that would have caught it.** `lead_contract` already refuses a number the context lacks;
add one that a client-reported number is shown to the Lead only through its admitted claim.

**Owner decision (2026-10-19): adopted.** Added as chunks to `research-lead-workbench.md` once #491
merges (that file is also #491's): "the Lead's results context" before chunk 20, owned by the
workbench track, with C, D and E supplying providers.

### F5. A removed button is not an enforced rule

**Claim.** MVP-8 removes the manual AI buttons "artifact by artifact" and routes every AI action
through the Lead; MVP-13 approves a paid job one card at a time. `research-lead-workbench` F1
records that `ResearchAgentJobs.start` reads no spend limit while the Lead's approve path does
(`application/research_lead.py:678-760`, per `mvp-consolidation.md` §6). The API route stays after
the button goes.

**Consequence.** Until the last artifact lands the start route is reachable around the Lead, and
AC-02 ("no manual AI button") passes as a UI observation while a direct call still skips the card
and the limit.

**Smallest fix.** Put the spend-limit check inside `ResearchAgentJobs.start` now (it is F1, a fix
not a decision), and make the Lead's approve path its only caller by an import-contract or route
test. Then the buttons' removal is cosmetic and order-independent.

**Related: the worker contract.** MVP-12 (eleven workers), MVP-32 (every prompt editable and
pinned), the card kinds of chunk 23 and Settings' `ai_runtime` document each describe a worker
separately. Define the row once in `domain/research_agents.py`: id, closed task, context layer,
data-class rule, capability, reservation, prompt id and pin, switch, card kind, result kind.
Chunk 11 builds the command registry; make this its first deliverable, so the three new workers
(map interpreter, report writer, straight-liner check) are rows, not three designs.

**Owner decision (2026-10-19): adopted, both halves.** The spend-limit check in
`ResearchAgentJobs.start` is a fix, not a decision, and is the first code to take; the worker row is
chunk 11's first deliverable. Neither is started: no code is written in #496 or #497.

### F6. Decision ids collide

**Claim.** `D9` means three things: `overview.md` *Decisions needed* has two rows labelled D9 (who
publishes the model catalog; whether Simulation is in the MVP), and `research-lead-workbench.md`
adds a third (the navigator stays at the top, #491). `M6` is both "report depth tiers"
(`mvp-consolidation.md`) and "the fit level below which a map is not delivered"
(`sociomap-formula-corrections.md`). MVP-1 says "also resolves D9"; a reader of the workbench
plan will not know which.

**Smallest fix.** Plan-local ids are written `<plan>#D9`; the overview's ids keep their `PROGRESS`
prefix (already the convention for D6 and D11); the consolidation's `M1-M8` are retired in its
prose now that MVP-1 to MVP-10 record the answers. One sentence in CLAUDE.md §4 (docs PR).

**Owner decision (2026-10-19): adopted.**

### F7. Eight pieces of work have no plan

| Decision | What is missing | Track | Natural home |
|---|---|---|---|
| MVP-23 findings cite admitted evidence | A plan; the stricter rule against `evidence-backed-analysis` (9/9, done) | E | new plan, or one chunk in `research-integrity-report` |
| MVP-24 run QC as warnings | A plan; pairs with the straight-liner worker (F2) | E | with MVP-23 |
| MVP-29 one field-policy authority | A plan; now two authorities by source (F3) | E | with MVP-23 |
| MVP-16/17 segment maps, clustering, filters, drill-down | A plan; the algorithm is the method owner's; **each new map method needs its own Sociomap-register entry** before any client-facing snapshot (`domain/sociomap_register.py`, D6) | C | new plan |
| MVP-19 client data in analysis | The plan ADR 0027's Consequences calls for; its build order is in the ADR | D | new plan after #494 |
| MVP-27 Class B provider | The provider route's code (composed beside Brave), its contract and processing agreement | F | `deep-research-web-search` |
| MVP-30 AWS inference profile and tag | One Terraform + IAM + model-policy change | A | `infra/develop` plan |
| MVP-ACCEPT-2 tier A | The harness: recorded doubles behind the gateway and the retrieval gate for the Lead, every worker, respondents, analysis and Deep Research, driven over HTTP | A | new plan |

An orphan decision is where silos start: its work gets done inside whichever plan is nearest, in
that plan's idiom. Create the plans before the tracks start, as CLAUDE.md §4 already requires.

### F8. Shared surfaces

File-mention counts across open plans (a proxy, hypothesis for how often each is edited):

| Surface | Open plans naming it | Proposed surface owner |
|---|---|---|
| `infrastructure/tables.py` (and so migrations) | 9: `architecture-enforcement`, `client-budget`, `client-workspace`, `complete-study-report`, `panel-grounded-respondents`, `productization-coherence`, `research-integrity-report`, `system-prompts-settings`, `two-roles-human-ai-gates` | the track whose PR is first; **a migration lane** (below) |
| `aia_executors/ai_runtime.py` | 5 | B (worker registry, F5) |
| `domain/research_agents.py` | 5 | B |
| `routers/settings.py` | 5 | B |
| `domain/fieldwork.py`, `domain/evidence/` | 3 (`complete-study-report`, `panel-grounded-respondents`, `sociomap-formula-corrections`) | C; **D's ADR 0027 changes land here too**: hand-off, not a second edit |
| `application/client_report.py` | 3 | E |
| `domain/research_lead.py`, `lib/lead.ts`, `Workbench.tsx` | 1 each (`research-lead-workbench`) | B; C, D, E supply providers, never edit it |

The roadmap's "one owner per track, no two agents edit the same plan" covers plan files, not code.
Two rules close the gap:

- **A surface has one owner.** A track needing a change in another track's surface opens it as a
  small PR the surface's owner reviews first, and names it in its plan.
- **Migration lane.** `migrations/versions` has a single head today
  (`20261019_57eaa96a5538_lead_auto_accept_text_edits.py` @ `085abe0`). A PR with a migration says
  its `down_revision` in the description, is rebased on `develop` immediately before merge, and the
  owner merges migration PRs one at a time. A commit on this branch already had to chain one
  migration after another ("Chain the auto-accept migration after the internal-mark one").

**Owner decision (2026-10-19): both rules adopted** (docs PR).

### F9. Parity: information or blocking?

**Claim.** #495 makes parity information (MVP-21, every `release_blocker.blocking` false).
`tools/parity_status.py` still exits 1 when any capability is `FAIL` (`:30` @ `085abe0`) and
`ARCHITECTURE.md` §8 lists it "blocking on `FAIL`".

**Resolution, not a decision.** Both are right if stated: a failing parity test fails the PR like
any test (CLAUDE.md §5: never loosened to get green), and an intentional departure from 18.6.6 is
recorded as such. What MVP-21 removes is parity as a **release criterion**. Add that sentence to
§8's row in #495's doc follow-up.

**Owner decision (2026-10-19): adopted.**

### F10. The budget

**Claim.** MVP-20 fixes the acceptance study at USD 25. The run includes n = 300 AI respondents,
the Lead's turns, up to eleven workers, eight analysis modules with repairs, live Deep Research on
the full design and the report. `domain/run_cost.py` bounds fieldwork and analysis only
(CLAUDE.md §2 map); Deep Research has its own pinned allowance. Nothing allocates the USD 25.
**Smallest fix:** a table in the acceptance plan's first chunk: each category's ceiling, summed,
and checked against 25 before the recorded run. If the sum exceeds 25, the owner chooses a smaller
n or a larger budget, before the build, not after tier B.

### F11. Working an artifact by hand, and pointing at it (the questionnaire first)

**Read from.** The V2 prototype's source (`prototypes/research-lead-v2/src/components/Composer.tsx`,
`components/ui.tsx` `Item`, `ChangeBlock`; #491), production's pointing code
(`apps/web/src/lib/lead.ts` `focusSelector`, `targetOfElement`; `Workbench.tsx` picking) and the
production questionnaire (`apps/web/src/research/questionnaire.ts`, `QuestionnaireStep.tsx`), all
@ `085abe0`. The V3 questionnaire frame is text only, so its behaviour is inferred. Anything not
checked in code is labelled a hypothesis.

**How it works.** *Pointing:* V2 opens a list of the current stage's items (up to eight, filtered
by id or text) after `@`; production arms click-to-pick and takes the nearest element with a known
id (`qedit_`, `qblock_`, `brief-`, `plan-`); either gives one chip on the message. The Lead's focus
kinds are `question`, `section`, `brief` and `plan`. *Editing by hand:* V2 has a pencil with an
inline edit saved to the working copy, move up and down, remove, add, and a lock; an edited item
says "your edit, not yet in a revision". Production has the fuller editor (type, options, routing
condition, scale, blocks, tracked sets, comparisons). *The Lead* can add, edit (text, options) and
remove a question, set N, and open or focus (`domain/research_lead.py:252-296`).

**What was not thought through.** Pointing reaches a whole question or block only, never a tracked
set, option, routing condition, scale, comparison, proposal change or coverage pill; the `@` list
covers the current stage, so Results cannot point at Q14; one reference per message cannot say
"merge Q21 and Q22". A pointer carries no revision, so Q8 is ambiguous while a proposal is pending.
Manual edits run through client code (`research/questionnaire.ts`) and the Lead through server
operations, with different powers (the Lead cannot move, merge or edit routing, scales, blocks or
sets) and a lock rule living only in the prototype (hypothesis: production has none). A proposal is
accepted whole; V2's change blocks have no controls. A manual edit has no undo. An auto-accepted Lead
edit can land while a person has an unsaved inline edit open. Removing or moving a question gives no
warning about routing, dimension use or Sociomap declarations. The "Build with AI" and "Optimise
with AI" buttons contradict MVP-8. The lock text says a change "requires a new revision of the map's
methodology", which confuses the design with the method version.

**Checked.** Production question ids are stable: `Q_<time><random>`, not renumbered on removal
(`research/questionnaire.ts:144, 186-196 @ 085abe0`); the displayed number is the position. A pointer
that carries the id therefore survives a removal. The Lead's *written* replies do not: "Q9" in prose
cannot be relabelled after items move.

**Owner decisions (2026-10-19), all four recommended options except the buttons:**

1. **One shared edit vocabulary, validated on the server.** A person's edits and the Lead's call
   the same operations, so a lock, the text-only rule and validation are written once. The Lead
   gains the missing operations (move, merge, section and set edits, routing, scale). The automatic
   accept stays the Lead's, text edits only (MVP-14, ADR 0026).
2. **Per-change accept and reject** inside a proposal. A stale change is flagged and can be
   dropped or asked again. Needs the accept route to take a subset (`accept_into_working_copy`
   already merges item by item, `domain/design_items.py`). *Open:* whether an unaccepted change
   stays pending or is dismissed when the rest is accepted; default dismissed, the proposal marked
   accepted in part.
3. **A stable id, with the number only a label.** A pointer carries the id and the revision it was
   made on. *Consequence the decision does not yet cover:* the Lead's prose must cite a question by
   a chip that renders the current number ("Q9, now Q7"), not by typing the number.
4. **The AI buttons are removed** from the questionnaire artifact (MVP-8): a person types a
   request, or uses the chat. Removal is for each artifact as its V3 version lands.

The rules apply to every artifact, not the questionnaire alone: a stable id, one shared edit
vocabulary, per-change accept, a pointer with a revision.

### F12. Two people, one study, two Leads

**Claim.** None of the four designs shows more than one person. The V3 boards say "one session for
the life of this study" and show one researcher. Production already differs: a researcher's Lead
conversation is theirs alone, "nobody reads another's turns, even on the same Study"
(`infrastructure/study_lead_repository.py:1-6 @ 085abe0`, ADR 0026 decision 8), while the working
copy is one per study and a save naming a stale base revision is refused whole
(`infrastructure/study_workspace_repository.py:234-271 @ 085abe0`, `stale_revision`).

**Consequence.** Two researchers editing different questions at once: the second autosave is refused
and the person is told, though nothing overlaps (hypothesis: the web does not merge on a refusal;
not checked). Each Lead's proposals go stale when the other person accepts a revision. Neither Lead
knows what the other person changed. Who may accept a proposal another person's Lead prepared is
undefined.

**Recommended shape** (owner to confirm; alternatives considered below):

1. **One working copy per study** (the source of truth), **one Lead conversation per person**, as
   built. A shared chat would interleave two people's requests, blur who approved a paid job, and
   conflict with each researcher's own notes and "Sees" context.
2. **Item-level merge, not whole-copy refusal.** With the shared edit vocabulary (F11) a manual save
   is a set of operations applied on the server to the latest working copy; a conflict exists only
   where the same item and field changed since the base, and is shown on that item.
3. **Presence, advisory only.** Who else is in the study and which artifact or element they have open
   or are editing ("Jana edits Q8"). It informs; it never blocks.
4. **An attributed change feed to each Lead.** The Lead's context includes working-copy changes made
   by other people since its last turn, each with its author, so it does not propose over them.
5. **Proposals belong to the study, not to a conversation.** Visible to everyone in the artifact as
   change blocks labelled with who asked; any member with `APPROVE_GATE` may accept, subject to the
   scope's self-approval rule; the item-level stale rule already protects overlap
   (`application/proposal_accept.py`). A revision names its author.
6. **Spend is the study's.** Approval cards go to the person whose Lead prepared the job, and the
   ledger names them; the budget and any envelope (F13) are shared.

**Alternatives.** *One shared Lead:* simpler, but the accountability and privacy problems above.
*One editor at a time (a lock per study or per stage):* safe and cheap, and it makes collaboration
impossible. *Real-time co-editing of the working copy:* heavy, and at odds with revisions and
gates.

**Test that would have caught it.** Two sessions on one study edit different questions in turn: both
edits survive; the same question: the second sees a conflict on that question only.

**Owner answer (2026-10-19).** Each researcher goes into the study with **their own agent**, which
develops over time; that confirms points 1 and 6. The rest of the shape (item-level merge, presence,
change feed, proposals visible to the study) was not objected to and stands as the recommendation;
who may accept another person's proposal is still open (any permitted member, as recommended, unless
told otherwise). The requirement that the agent evolve is F14.

### F13. Stage meaning, order, paid work and locks

**Owner decisions (2026-10-19):**

1. **The revision is the unit of acceptance.** Accepting always creates a whole revision. Each stage
   shows "unchanged since the accepted revision", "changed since" or "proposal waiting"; the rail
   count becomes "stages current with revision n". A reopened stage shows "re-check" and clears when
   its content is confirmed unchanged on the next accept. The designs' "3 of 11 accepted" is
   replaced.
2. **Order: Results, Sociomap, Analysis, Report.** Matches the engine, the Fieldwork step list and
   the scenario; the V3 rail's Analysis-before-Sociomap is dropped.
3. **A per-study envelope** for paid work: the Lead may start workers and Deep Research inside an
   allowance the owner approves, each job logged, stopping at the cap. **This supersedes MVP-13**
   ("a card at a time, no standing budget"). **Answers (2026-10-19):** the **researcher sets it, up to a
   ceiling the organisation owner sets for the client**, recorded in the approval ledger; the
   study's spend limit stays the hard stop. **Everything is inside it, the fieldwork run included**,
   but a run starts under a **plan card the researcher approves once** (the steps and the cost
   ceiling), after which the Lead runs those steps; it is not a Lead-initiated run on its own.
   This pulls a plan-scoped part of the autopilot into the MVP (MVP-3 had put "continue until you
   need me" after it) and needs the **orchestration-scope ADR** before any code: the Lead holds no
   `APPROVE_GATE` (`domain/scope.py:202-213`, per `mvp-consolidation.md` §6.2), so the person's
   approval is of the envelope and the plan, and each started job carries a ledger row naming the
   plan. Budget lift, report approval and an unlock stay human-only (commands refuse the Lead). *Open:*
   whether a plain chat request ("start fieldwork") also starts a run without a plan card (recommended:
   yes, asking is authorising); expiry; whether a priced Deep Research route is inside (ADR 0022
   requires approved settings for it; ADR 0019 gate 2 requires confirmation when a run's ceiling
   reaches the spend limit, which stays).
4. **A hard lock with a recorded unlock.** Set 1 and the Sociomap rating question are blocked until
   the person chooses "Unlock for this revision", which warns that the map changes and writes an
   approval-ledger row. The Lead can never unlock. The lock text stops saying "methodology
   revision".

### F14. Each researcher's own Lead: how it develops, and who can see it

**What exists.** Each researcher has their own Lead: a name, a SOUL (working style, at most 2,000
characters), a USER file (what it knows of how this researcher works) and notes (at most 300
characters each, personal or one client's), all with revisions. The Lead changes them **only through
`self_update`, when the researcher asks in chat** (`domain/research_lead.py:18-21, 384-412 @
085abe0`). The Lead's own files and personal notes are Class C; client-scoped notes are Class A. So
nothing prompts either side to update them: left as built, a Lead barely evolves.

**Owner decisions (2026-10-19):**

1. **The Lead proposes updates; the researcher approves each.** After a correction or a repeated
   preference it prepares a "Remember this" card; the researcher accepts, edits or refuses. It also
   offers a periodic review ("here is what I have learned about how you work"). Nothing changes
   without a yes, and every change is a revision that can be rolled back. This extends
   `self_update` from "on request" to "proposed".
2. **An organisation admin can read a researcher's Lead (files and notes) and hand it on.** This
   weakens the privacy ADR 0026 decision 8 gives each researcher ("nobody reads another's turns");
   it needs its own permission (an organisation OWNER or ADMIN, not the one Researcher role of ADR
   0019) and an amendment to ADR 0026. *Open:* the conversation **turns** (this decision names files
   and notes only; recommended: they stay private); what "hand it on" means (a copy for the successor
   with personal notes removed, or a reassignment); and that a handed-on personal note may contain a
   departed person's details.

**Rules to write down.** What may be learned (style, working preferences) and what may not (client
facts belong in a client-scoped note, Class A, visible only in that client's studies). A bound on
what a proposal may add. A test that no client name or number reaches a personal (Class C) file.

### F15. Who answers in fieldwork

**Owner decision (2026-10-19): population-built respondents by default; invented respondents only for
tests and demos.** A study's respondents are AI personas built from the Czech population dataset
(origin `MODELLED_AI_PANEL`, labelled modelled, able to reach the client report under the owner's
2026-10-13 lift). The V3 boards draw only the invented path (`SYNTHETIC_AI_FICTIONAL`), so the
Fieldwork start screen, the Audience population panel ("does not read it") and the report cover
(`kalibrované jádro`) are redrawn for the MVP path: who answers and the origin label are on every
screen, and a screen never claims a population was read when it was not.

### F16. Money on screen

**Owner decision (2026-10-19): two meters, the rest on click.** The header shows "Study: spent of
spend limit", with the envelope's remaining allowance **inside** it (the envelope is a slice of the
spend limit, F13). A run or a job shows its own ceiling where the person approves it. The client's
budget, the Deep Research allowance and the Lead's own turn costs are in a details drawer. Lead turns
and workers all count toward the study's spend. The designs' four unlabelled numbers
("Research 0,97/3,00", "study 1,12/12,00", "spend limit 5,00", "run ceiling 4,80") and the Fieldwork
panel's "Rozpočet studie", which shows the run ceiling, are replaced. *Open:* the Czech name of each
meter, written once with `domain/report/copy.py`'s discipline, so no screen invents its own.

### F17. Report delivery and approval

**Owner decision (2026-10-19): separate approvals, a second person for the client report.** The
internal report is approved by any permitted member. The client report and each map snapshot are
approved separately by a reviewer other than the person who produced them. DOCX and PDF become
available only after approval. The Report artifact gains an Approve and Export panel showing what is
approved and by whom.

**Consequences not yet covered.** (1) Today report approval requires independence only where the
scope's self-approval policy says so (`application/report_approval.py:4`). The decision asks for a
second person on a client report: **unconditionally**, whatever a client's setting? Recommended: yes,
for anything client-facing (the acceptance study has self-approval off anyway). (2) **Map snapshot
approval does not exist**: the register approves a *method* (`domain/sociomap_register.py`) and the PNG
snapshot is internal; an approved snapshot is a new approvable object. It belongs in
`two-roles-human-ai-gates` 5b.4, which has no chunk for it. (3) A snapshot of a respondent or segment
map needs that method registered first (`segment-maps-and-drilldown` chunk 4).

### F18. Straight-liners: no pause

**Owner decision (2026-10-19): no pause; a warning, then the worker proposes.** The run goes on to
aggregation. Run QC flags straight-liners as a warning (MVP-24). The straight-liner worker (MVP-12)
proposes keep or replace afterwards; **replace starts a new linked run with its own identity**. The
designs' decision card between fieldwork and aggregation is dropped. The map leaves unplaceable
respondents out and says "197 of 200 placed": that line **needs respondent placement**
(`sociomap-formula-corrections` chunk 3, not built), so until then it is not shown (hypothesis: the
object map today uses pair statistics, not placed respondents).

### F19. Client data inside a study

**Owner decision (2026-10-19): in the study, in Brief materials and Dimensions.** The Brief's
Materials picks a dataset from the client's sources (the existing source picker) and opens the data
contract in a drawer; accepting it is the person's recorded act (`client-data-in-analysis` chunk 2).
An own dimension shows a status chip (waiting for approval, building, ready) with a link to the
client's review queue, and becomes selectable for the next run when ready. *Open:* after approval,
does the build start by itself or on a click? Today a person starts a materialization from a study
(`POST /studies/{id}/population/materializations`) and it is a run with a cost; recommended: a click,
inside the envelope.

---

## 3. The acceptance criteria, traced to work

Every criterion needs an owner and every chunk a criterion. `●` the chunk exists in a plan; `○`
built, needs only the release run; `✗` no plan (F7).

| AC | Passes when | Built by | State |
|---|---|---|---|
| 01 identity, scope, 404 | `ScopeResolver`, ADR 0019 | done | ○ |
| 02 workbench, Lead, approvals | `research-lead-workbench` 11-16, 23; F5 server rule | B | ● + F5 |
| 03 workers, prompts pinned | workbench 11; `system-prompts-settings` 7; worker row (F5) | B | ● + F5 |
| 04 cost shown, parks at limit | `research.py` ceiling, budget park; Audience artifact 22 | done + B 22 | ○ / ● |
| 05 respondents from LIVE | `audience-catalogue-cpu` 4, `complete-study-report` B6 (operator flag) | C | ● |
| 06 worker killed, no loss | `run-recovery-and-truth` | done | ○ |
| 07 impact preview | `pipeline.py` impact | done | ○ |
| 08 admitted, findings cite, QC warns | MVP-23, 24, 29 | E | ✗ |
| 09 three maps, filters, drill-down | `sociomap-formula-corrections` 3, 4d; segments, register entries, F2 | C, B | ● / ✗ |
| 10 client data in and used | `client-knowledge-lifecycle` K2e-K7, `client-workspace` C6-C9, ADR 0027 build, F3 | D | ● / ✗ |
| 11 Deep Research live, full design | provider route, F1, `deep-research-web-search` 1 to 27, 37 | F | ✗ / ● |
| 12 project memory | PM-1 | done | ○ |
| 13 reports and approved exports | `research-integrity-report` 6-8, `two-roles-human-ai-gates` 5b.4, report-writer worker | E, B | ● |
| 14 typed config | `Settings.validate_for_production` | done | ○ |
| 15 provenance, spend reconciles | `research-integrity-report`; MVP-30 Terraform | E, A | ● / ✗ |

Five criteria rest on `✗` rows (08, 09, 10, 11, 15). **Those five plans are the critical path to
tier A.**

---

## 4. Integration milestones

The roadmap orders chunks inside tracks; nothing says when two tracks must meet. Five
cross-track gates, each with an observable test, ordered by dependency. The target is the owner's
(MVP-11, end of Q1 2027). **No gate dates yet (owner, 2026-10-19):** the gates are ordered, not
dated, until the provider contract and the method owner have owners.

| Gate | Meets | Observable | Needs |
|---|---|---|---|
| **I-1 Lead drives a study** | B 11-16, 18, 19 + C `audience-catalogue-cpu` 4, B6 + D CB5 + A harness skeleton | Brief to Sample worked through the Lead on recorded doubles, tier A, one criterion (AC-02) passing | worker row, F5 server rule |
| **I-2 Results are seen** | C I0-I5, respondent map + B results context (F4), 20 | The Lead explains a map pair from admitted evidence; drill-down internal only (F2) | F2, F4 decided |
| **I-3 Evidence is complete** | E MVP-23/24/29 + D ADR 0027 build + B 21 | A client dataset beside the modelled results, graded client-reported; every finding cites a claim | F3 decided, plans created |
| **I-4 Deep Research live** | F provider route + F1 + `deep-research-web-search` 1, 27, 37 | A live run on the full design, quotes grounded, one-click source into knowledge | provider contracted (owner) |
| **I-5 Acceptance** | all | Tier A blocking in CI, then tier B once on develop within USD 25 | F10 allocation |

---

## 5. What the owner decides to finalise this

| Q | Decision | Recommended |
|---|---|---|
| Q1 | F1: **decided 2026-10-19: Deep Research uses the whole design, no operator step, and queries derived from it may reach Class C routes.** Open prerequisites only: the ADR 0017 / 0008 amendment, the data owner's confirmation, and a provenance-based mechanism (not a text test) | decided; prerequisites open |
| Q2 | F2: **decided 2026-10-19: yes, internal, the Lead may read it, never exported** | decided |
| Q3 | F3: **decided 2026-10-19: later, in the ADR 0027 plan** (recommendation: the accepted data contract is the policy source) | decided |
| Q4 | F7: **decided 2026-10-19: write the missing plans** (six files cover the eight pieces of work, see #497). Track owners are chat sessions, probably Opus 5.5; name each session when its track starts | decided; names open |
| Q5 | The provider contract (MVP-27, owner) and the method owner's 0b answers, clustering algorithm and register entries: **no dates yet (2026-10-19)**; I-2 and I-4 stay undated until each has an owner | open |
| Q6 | F4 and F5: the Lead's results context and the worker row | **adopted 2026-10-19** |
| Q7 | F6, F8, F9: id namespaces, surface owners and migration lane, parity wording | **adopted 2026-10-19** |
| Q8 | F11: one shared server-validated edit vocabulary for a person and the Lead | **decided 2026-10-19** |
| Q9 | F11: per-change accept and reject inside a proposal | **decided 2026-10-19** |
| Q10 | F11: a stable id, the number a label, a pointer carrying the revision | **decided 2026-10-19** |
| Q11 | F11: the questionnaire's AI buttons removed (MVP-8) | **decided 2026-10-19** |
| Q12 | F13: the revision is the unit of acceptance; a stage is current, changed or re-check | **decided 2026-10-19** |
| Q13 | F13: stage order Results, Sociomap, Analysis, Report | **decided 2026-10-19** |
| Q14 | F13: a per-study envelope for paid work, superseding MVP-13: set by the researcher up to a client/organisation ceiling; everything inside it, a run through a plan card approved once | **decided 2026-10-19; orchestration-scope ADR first; expiry and chat-started runs open** |
| Q15 | F13: a hard lock on Sociomap inputs with a recorded unlock | **decided 2026-10-19** |
| Q16 | F12: two people on one study: each researcher goes in with their own agent; one working copy; item-level merge, presence, shared proposals | **per-person agent decided 2026-10-19**; the rest stands as recommended |
| Q17 | F15: population-built respondents by default, invented ones for tests only | **decided 2026-10-19** |
| Q18 | F14: the Lead proposes updates to its own files, the researcher approves each | **decided 2026-10-19** |
| Q19 | F14: an organisation admin can read a researcher's Lead files and hand them on; turns and hand-over rules open | **decided 2026-10-19; amends ADR 0026 decision 8** |
| Q20 | F16: two meters in the header, the rest on click; the envelope is a slice of the spend limit | **decided 2026-10-19** |
| Q21 | F17: separate approvals, a second person for the client report and each map snapshot, exports after approval | **decided 2026-10-19; unconditional second person and snapshot approval open** |
| Q22 | F18: no pause after fieldwork; a QC warning, the worker proposes, replace is a new linked run | **decided 2026-10-19** |
| Q23 | F19: client datasets and own dimensions are handled in Brief materials and Dimensions | **decided 2026-10-19; whether the build starts by itself open** |

## 6. Follow-ups for a docs PR

- `ARCHITECTURE.md` §4: the drill-down exception (F2); the Deep Research classification regime if
  Q1 is yes (F1); §8's parity row (F9). One sentence on the origin set when ADR 0027 is accepted.
- `CLAUDE.md` §2: `parity-matrix.json` "blockers" wording (#495's follow-up); the V3 prototype
  note (#491's); §4: the id-namespace rule (F6); the surface-owner and migration-lane rules (F8).
- `overview.md`: MVP-27 beside OI-129; the five integration gates (§4); track owners when named;
  MVP-20 "now MVP-ACCEPT-2" (#495's follow-up).
- ADR 0027: the contract-as-policy decision (F3) before acceptance; ADR 0026: the Lead's results
  context and the worker row (F4, F5).
- Plans: the front-matter chunks for F4, F5 and F7.
- `research-lead-workbench.md`, once #491 merges: chunk 16 (a pointer with id and revision, any
  element, several references), chunk 17 (the questionnaire's manual operations, per-change accept,
  the AI buttons removed) and a chunk for the shared edit vocabulary (F11); ADR 0026 (the Lead's
  edit vocabulary widened, per-change accept) and `ARCHITECTURE.md` §4 (a person and the Lead share
  one set of server-validated edits).
- `overview.md`: MVP-13 superseded by the per-study envelope (F13) and MVP-3 amended (a plan-scoped part
  of the autopilot is in the MVP); an **orchestration-scope ADR** (the Lead's plan card, the
  envelope, what each started job records) before chunk 24 or any envelope code; ADR 0026 decision 8
  amended for an admin's read of Lead files and the proposed updates (F14); the Fieldwork, Audience and
  report-cover screens redrawn for population-built respondents (F15); the header's two meters (F16); the Report artifact's
  Approve and Export panel and a chunk for map-snapshot approval in `two-roles-human-ai-gates` 5b.4
  (F17); the straight-liner decision card dropped (F18); client data and the own-dimension chip in the
  Brief and Dimensions artifacts (F19).
