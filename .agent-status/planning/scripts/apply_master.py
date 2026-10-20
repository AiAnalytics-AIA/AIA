import sys
from pathlib import Path

p = Path(sys.argv[1]) / ".planning/plans/mvp-master-plan.md"
s = p.read_text(encoding="utf-8")


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:80])
    s = s.replace(old, new)


# front matter: the signature chunk
rep('  - "[x] MP15. Execution dependencies, partial wave checks and the owner decision packet reconciled; implementation remains open"\n',
    '  - "[x] MP15. Execution dependencies, partial wave checks and the owner decision packet reconciled; implementation remains open"\n'
    '  - "[ ] MP16. The scope baseline signed by the owner (§ The scope baseline); its open items answered or carried, each answer applied to the plans it moves"\n')

BASELINE = r'''
## The scope baseline (2026-10-20), for the owner's signature

**Status: not signed.** The scope freeze (the owner, 2026-10-20, about 15:25 UTC) holds every feature
chunk until the owner signs below; security fixes are exempt. The baseline is written against
`develop` @ `47e5536`, from the owner's 48 answers of the same day, recorded word for word in
[`answers-2026-10-20.md`](../evidence/scope-freeze/answers-2026-10-20.md) (decision ids from
[`decision-list.md`](../evidence/scope-freeze/decision-list.md), #516), and the inputs' proposed
edits, consolidated in [`proposed-edits.md`](../evidence/scope-freeze/proposed-edits.md) (#522).
Signing settles **In** and **Out**; it does not answer **Open**, whose items each name who answers and
what waits on them.

### In

**The MVP as already planned.** The goal of §1; the fifteen criteria of `MVP-ACCEPT-2` (AC-01 to
AC-15), as amended below; the core plans of §3.1 with their open chunks and waves
(`mvp-execution-contracts.md`); every settled decision of §11.1.

**Added or settled by the freeze** (D-nn is the decision's id):

| Area | What is in | Chunks |
|---|---|---|
| Money | The four names: Rozpočet klienta, Rozpočet studie (renaming "Strop rozpočtu"), Peněženka, Práh potvrzení (D-01). A plan's approval confirms each step ceiling it showed; a grown ceiling parks (D-02). No raise above the client's wallet ceiling; only the ceiling moves (D-03). A plan finishes the steps tied to its revision when the design moves (D-04). Deep Research charged at its ceiling until M11 (D-05) | `lead-orchestration#LO0`, `lead-orchestration#LO1`, `lead-orchestration#LO4`, `lead-orchestration#LO10` |
| Working copy | Conflicts per field (D-06); an unaccepted change `REJECTED`, `DROPPED_STALE` on conflict (D-07); the lock covers the declared inputs and the sets they rate (D-30); structural auto-accept by a named server path under the person's standing choice, switched per stage on Můj Vedoucí, off by default (D-31) | `working-copy-edit-ops#WCE5`, `working-copy-edit-ops#WCE7`, `working-copy-edit-ops#WCE8`, `working-copy-edit-ops#WCE11` |
| The Lead | Each researcher builds and names their own Lead, never transferred (D-32 to D-34); Deep Research from the Lead (D-12); stopping a turn and an approved plan (D-18); conversation controls (D-38); streaming, a file from the composer, unprompted comments as paid turns in the wallet (D-39) | `lead-orchestration#LO5a`, `lead-orchestration#LO17`, `lead-orchestration#LO18`, `research-lead-workbench#29`, `research-lead-workbench#30`, `lead-orchestration#LO11` |
| Sociomap | `aia-sociomap-5` is the only method of new runs; the old methods leave every product path; maps are drawn from `-5` (D-13). Only the methodologist edits methodology (D-14). Matrix and comparison modes (D-42) | `signed-off-sociomap-method#8`, `signed-off-sociomap-method#9`, `signed-off-sociomap-method#10`, `research-lead-workbench#20`, `segment-maps-and-drilldown#11` |
| Evidence and reports | An assumption is supported or contradicted only with an admitted respondent claim (D-16); after a replacement the newer run is read, both named (D-36); results charts and a CSV/XLSX export (D-41); Deep Research context in the client report (MVP-26); stimuli shown to respondents (D-45) | `assumptions-and-open-answer-coding#AOC0`, `run-qc-and-checkpoint#RQC5`, `report-delivery#RD12`, `research-lead-workbench#31`, `report-delivery#RD11`, `working-copy-edit-ops#WCE14`, `run-qc-and-checkpoint#RQC13` |
| Deep Research | A refused run fails, worded by cause, retryable under fresh pins (D-10); the acceptance study cites one known dead URL for the archive (D-11); a run's routes on its record | `deep-research-web-search#53`, `deep-research-web-search#54`, `deep-research-web-search#51a` |
| Client pages and Settings | Posture and wallet ceiling on Profil → Pravidla (D-17); the data contract accepted in the Brief drawer, the Data tab read-only (D-37); delete: a client by an admin, a source by a researcher, knowledge retired (D-29); deactivating a member (D-27); a cross-client portfolio, project memory over approved reports, an organization's monthly spend (D-47); Simulace hidden (MVP-31); no paid start outside the Lead over HTTP (D-15) | `client-knowledge-lifecycle#K11`, `client-data-in-analysis#10`, `study-data-lifecycle#SDL3`, `study-data-lifecycle#SDL4b`, `two-roles-human-ai-gates#8`, `client-knowledge-lifecycle#K9`, `client-knowledge-lifecycle#K10`, `develop-spend-attribution#6`, `client-knowledge-lifecycle#K12`, `system-prompts-settings#14` |
| Acceptance | AC-14 reads typed settings plus a composition digest on each run (D-09); AC-01's 404 is for another organization (ADR 0019); accessibility (axe) and performance budgets are release gates (D-48) | `lead-orchestration#LO12c`, `mvp-acceptance-harness#14`, `mvp-acceptance-harness#10`, `mvp-acceptance-harness#18` |
| Production and release | Egress blocks private and metadata ranges only (D-19); the proposed sizes (D-20); tagged inference profiles (D-21); production starts empty, bootstrapped by an operator command (D-22); an external security review (D-23); per-member rate limits (D-24); RPO 24 h, RTO 4 h (D-25); GlitchTip for errors (D-26); terms, privacy notice, client DPA and the panel-licence confirmation before the first client (D-28) | `production-environment#PE4`, `production-environment#PE7`, `production-environment#PE10`, `production-environment#PE11`, `architecture-enforcement#12`, `production-environment#PE9a`, `production-environment#PE9b` |
| Proposals | The ADRs 0028 to 0038 (#512) as Proposed; the owner's yes to amend ADR 0026 and ADR 0008 as each is accepted, including the "frozen retrieval" wording (D-08) | `mvp-master-plan#MP5` |

### Out

- Map node drag as a stored view override; camera-only operations satisfy AC-09 (D-40).
- A locked attention-check question (D-43); MVP-24's QC warnings stay.
- The question chain: the Brief's decisions, expected answers and done-when (D-44).
- Known-truth anchors, an instrument library, schedules and pause, "society insights" (D-46).
- Handing a Lead over, a departure trigger, and an admin reading another researcher's Lead files
  (D-32 to D-34); ADR 0030 is narrowed to the Lead's own file history.
- `aia-sociomap-1` to `-4` in any product path (D-13); what a stored older run shows is Q2 below.
- Export of a client's data and erasing one person as features: an operator procedure in the
  runbook for about ten users (D-29).
- As before the freeze: Simulation (§3.2 `simulation-studio`), the Class B search route (§3.3),
  SOMECS (`sociomapping-engine`), the holdout validation and client-facing analysis prose
  (`panel-grounded-respondents`), and every POST row of §3.2.

### Open: signing does not answer these

| # | Question | Who answers | Waits on it |
|---|---|---|---|
| Q1 | When the switch to `-5` merges: as soon as it is built (every `-5` map internal until the methodology owner's register entry; no map reaches a client meanwhile), or only together with the entry. Recommended: as soon as built; no real client receives a report before production | the owner | `signed-off-sociomap-method#8` |
| Q2 | What a stored `-1`/`-3` run shows once the old drawing is gone: its data with "an older method's map; run again", a "recompute with `-5`" action as a new linked map, or deletion. Recommended: the first; every stored run on develop is fictional | the owner | `signed-off-sociomap-method#8`, `research-lead-workbench#20` |
| Q3 | Whether "get rid of the old ones" deletes the old engine code and its golden fixtures F1-F9, or removes it from every product path and keeps it as tested reference. Recommended: the second now, deletion once `-5` has golden fixtures of its own | the owner | `signed-off-sociomap-method#8` |
| Q4 | The form of "only the mathematician edits the methodology": a methodologist mark an OWNER grants (held today by A. Bahbouh) gating storing and activating, the same with activation left to OWNER/ADMIN, or one named account. Recommended: the first | the owner | `signed-off-sociomap-method#10` |
| Q5 | Whether a study has one assigned lead researcher an admin can change ("an admin can change the research lead"), whose Lead prepares the plans that spend the study's wallet while others' Leads may chat and propose, or no assignment. Today none exists | the owner | `lead-orchestration#LO4`, `lead-orchestration#LO11` |
| Q6 | The Lead's document editing and web search (D-35, "edit the documents as they see fit … a web search … like ChatGPT or Claude"): whether every number in an edited report stays an admitted ledger ref (ADR 0035, AC-13), and whether the Lead's search runs through `RetrievalGate` under the client's posture with quotes cited as external context (ADR 0017, ADR 0021) or as a provider's own browsing. Recommended: the number rule kept, the search through `RetrievalGate`; either needs an ADR | the owner | `report-delivery#RD6`, a Lead lookup chunk not yet written |
| Q7 | Whether production gets an uptime probe (GlitchTip's own monitors) and a named recipient, beside GlitchTip's errors | the owner | `production-environment#PE9b` |
| Q8 | Whether Metodika's comparison shows `-5`'s credibility, respondent map and segments in the MVP (packet E-5); under D-14 the methodologist is its only user | the owner | `signed-off-sociomap-method#10` |
| — | Production's new domain name (D-20: "i will be changing to a new domain") | the owner | `production-environment#PE1`, Cognito callbacks |
| — | The performance budget values for `mvp-acceptance-harness#18` (D-48); planning proposes them in that chunk's PR, the owner approves | the owner | `mvp-acceptance-harness#18` |
| — | The methodology owner's decisions MQ-01 to MQ-24, MQ-01 (the `-5` register entry) first | A. Bahbouh | `mvp-methodology-packet.md` (#510); §11.4 |
| — | The Deep Research evaluation tasks and thresholds (MVPQ-06, rest) | the owner | `deep-research-web-search#27` |
| — | The scope overrides S2 to S5, only if wanted (§11.3) | the owner | §11.3 |
| — | Each ADR 0028 to 0038 accepted (the owner; A. Bahbouh on the method parts) | the owner | `mvp-master-plan#MP5` |

### Signature

Signed: ______________________ (Nigel Blount, product owner)   Date: ____________

'''
anchor = "## 2. The three failures this plan exists to prevent"
rep(anchor, BASELINE.lstrip("\n") + anchor)

# §3.1 / §3.2: signed-off-sociomap-method becomes core
rep("| `production-environment` | S3 | I-5 | operator items (§11.5) |\n",
    "| `production-environment` | S3 | I-5 | operator items (§11.5) |\n"
    "| `signed-off-sociomap-method` | S2 and the methodology owner | I-2 | the owner's D-13 (`-5` the only method); the methodology owner's register entry (MQ-01) before a `-5` map reaches a client |\n")
start = s.index("| `signed-off-sociomap-method` | SUPPORT (S2, the methodology owner)")
end = s.index("\n", start) + 1
s = s[:start] + s[end:]
rep("the SOMECS engine depends on the method owner's exports and decisions; the MVP uses `aia-sociomap-3`",
    "the SOMECS engine depends on the method owner's exports and decisions; the MVP uses `aia-sociomap-5` (MVPQ-13, D-13)")

# §3.4
rep("| AC-01 | `mvp-acceptance-harness#5`, `lead-orchestration#LO11` |",
    "| AC-01 | `mvp-acceptance-harness#5`, `mvp-acceptance-harness#14`, `lead-orchestration#LO11` |")
rep("`lead-orchestration#LO15`, `research-lead-workbench#26`, `research-lead-workbench#27` |",
    "`lead-orchestration#LO15`, `research-lead-workbench#26`, `research-lead-workbench#27`, `lead-orchestration#LO5a`, `lead-orchestration#LO17` |")
rep("`assumptions-and-open-answer-coding#AOC8`, `assumptions-and-open-answer-coding#AOC9` |",
    "`assumptions-and-open-answer-coding#AOC8`, `assumptions-and-open-answer-coding#AOC9`, `evidence-integrity#5`, `segment-maps-and-drilldown#10` |")
rep("`research-lead-workbench#20`, `working-copy-edit-ops#WCE8`, `mvp-acceptance-harness#10` |",
    "`research-lead-workbench#20`, `working-copy-edit-ops#WCE8`, `mvp-acceptance-harness#10`, `signed-off-sociomap-method#8`, `signed-off-sociomap-method#9` |")
rep("`deep-research-web-search#27`, `mvp-acceptance-harness#11` |",
    "`deep-research-web-search#27`, `mvp-acceptance-harness#11`, `deep-research-web-search#36`, `deep-research-web-search#37`, `deep-research-web-search#51a` |")
rep("`research-integrity-report#6`, `report-delivery#RD9`, `report-delivery#RD10` |",
    "`research-integrity-report#6`, `report-delivery#RD9`, `report-delivery#RD10`, `report-delivery#RD11`, `signed-off-sociomap-method#8`, `signed-off-sociomap-method#9` |")
rep("| AC-14 | `mvp-master-plan#MP6`, `mvp-acceptance-harness#5` |",
    "| AC-14 | `mvp-master-plan#MP6`, `mvp-acceptance-harness#5`, `lead-orchestration#LO12c`, `mvp-acceptance-harness#14` |")
i = s.index("| AC-15 | ")
j = s.index("\n", i)
assert s[i:j].endswith("`production-environment#PE7` |")
s = s[:j - 2] + ", `mvp-acceptance-harness#16`, `run-qc-and-checkpoint#RQC12` |" + s[j:]

# §4: the Deep Research lead switch
rep("| ADR 0022 approvals on Nastavení → Deep Research |",
    "| `aia_deep_research_lead=true` (needs agent-directed mode) | the run's sources kept as a dataset, AC-11 (`deep-research-web-search#36`, `#37` are marked by the lead: `deep_research_runtime.py:459-461`); default false | operator | the run's plan records `versions.lead` |\n"
    "| ADR 0022 approvals on Nastavení → Deep Research |")

# §6.1: G58-G78
G = '''
**From the scope freeze's cross-check of tracks 5-7 (2026-10-20, #515)**

| # | Gap | Chunks |
|---|---|---|
| G58 | **The shipped method, `aia-sociomap-5`, can be neither pinned nor approved.** A new run pins `-1` + `-3` (`research_sociomap.py:323-330 @ 854c209`); a stored version is always `<base>+e<n>` (`pins.py:84-95`, `versions.py:71-75`); the register approves `-3` only (`sociomap_register.py:51-69`). D-13 makes `-5` the only method | `signed-off-sociomap-method#8` |
| G59 | **AC-09's respondent and segment maps are scheduled on the contract-3 route**, building what `-5` already stores (`models_v3.py:424-557`); E14, E29, E30, E31 are `-3`-shaped | `segment-maps-and-drilldown#1`, `segment-maps-and-drilldown#2`, `sociomap-formula-corrections#3` |
| G60 | **The report's map figure misdraws a `-5` map**: nodes at `heights.values` over a relative terrain, a fixed caption, `objects_not_placed` dropped (`object_map_figure.py:39, 64-104`; the figure is a hypothesis, not rendered) | `signed-off-sociomap-method#9`, `segment-maps-and-drilldown#9` |
| G61 | **AC-08's authority and RELIGION clauses are missing from its row**, and chunk 5's test cannot hold over `instrument:` fields (`policy.py:310-311`) | `evidence-integrity#5`, `segment-maps-and-drilldown#10` |
| G62 | **`evidence-integrity#1` sat in W3 (E20), after its W1 consumer 9a (E32)**; moved to E32 by the freeze | `evidence-integrity#1`, `mvp-master-plan#MP8` |
| G63 | **RD0's "no number without an admitted claim" has no number classes**: the client report's fixed text has design and method numbers (`client_report.py:194`, `report_design.py:62-68, 122-124, 141`) | `report-delivery#RD0` |
| G64 | **The "Interní dokument" gate has nothing to read**: the frozen `KnowledgeSource` carries no mark (`contracts.py:206-225`) | `report-delivery#RD0`, `client-knowledge-lifecycle#K8` |
| G65 | **AC-15's per-number provenance walk has no chunk** | `mvp-acceptance-harness#16` |
| G66 | **A client-report approval is answered on the wire as internal** (`research.py:2500-2506`, `review.py:46-50`) | `report-delivery#RD3` |
| G67 | **No response names the routes a run used** (`coverage.py:42-56, 102-125`) | `deep-research-web-search#51a` |
| G68 | **A run refused for its class or approval parks as `ai_runtime_unavailable`**, with a Resume that parks it again (`plan.py:127-137, 166-174`; `workflow.py:601-607`); D-10: it fails | `deep-research-web-search#53`, `lead-orchestration#LO12a` |
| G69 | **From W1 to W4 Deep Research had no Lead start**; D-12 | `lead-orchestration#LO5a`, `research-lead-workbench#26` |
| G70 | **The required archive route is reached only by chance** (`archive.py:159-188`); D-11 | `deep-research-web-search#54`, `mvp-acceptance-harness#11` |
| G71 | **AC-11's dataset clause needs `AIA_DEEP_RESEARCH_LEAD`** (`deep_research_runtime.py:459-461`), which §4 did not name | `mvp-master-plan#MP6`, `deep-research-web-search#36`, `deep-research-web-search#37` |
| G72 | **AOC2 names no producer**: subjects are QUESTION, OBJECT or CROSS only (`contracts.py:138-144`) | `assumptions-and-open-answer-coding#AOC2` |
| G73 | **AC-01's "another client's user gets 404" contradicts ADR 0019** (`scope.py:244-247`, `test_scope_isolation.py:209`) | `mvp-acceptance-harness#14` |
| G74 | **AC-14 had no subject**: no edition file by design (`module-inventory.md:321`), no configuration recorded on a run; D-09 | `mvp-acceptance-harness#14`, `lead-orchestration#LO12c` |
| G75 | **`parity_status.py` ties the acceptance verdict to parity readiness** (`:375-378`) | `mvp-acceptance-harness#17` |
| G76 | **The study cannot be provisioned over HTTP**: no route creates the organization or its owner (`scope_repository.py:103`) | `mvp-acceptance-harness#3`, `production-environment#PE10` |
| G77 | **No tier-A projection of each criterion is written**; the record is per criterion, not per tier | `mvp-acceptance-harness#6`, `mvp-acceptance-harness#14` |
| G78 | **Weight identity is recorded but not served over HTTP** (`research.py:375-388`) | `run-qc-and-checkpoint#RQC12` |
'''
anchor = "\n### 6.2 Statements that are wrong or stale"
rep(anchor, "\n" + G.strip("\n") + "\n" + anchor)

# §6.2: stale statements from #515 §4
rep('| `class-b-search-route.md:61` "mandatory" | the plan | deferred | fixed in #500 |\n',
    '| `class-b-search-route.md:61` "mandatory" | the plan | deferred | fixed in #500 |\n'
    '| "The MVP uses `aia-sociomap-3`" | §3.2 (`sociomapping-engine` row) | the owner chose `-5` (MVPQ-13), the only method (D-13) | corrected by the freeze |\n'
    '| #504 "open" | `mvp-owner-decisions.md:69-71` | merged as `18d59ea` | the owner packet, with MVPQ-13 |\n'
    '| "The built ones first (AC-01, 06, 07, 12, 14)" | `mvp-acceptance-harness.md:8` (chunk 5) | only AC-12 has an existing path | `mvp-acceptance-harness#5` |\n'
    '| `sociomapping.core`: `-3` "INTERNAL_ONLY while D6 is open"; `project.memory` NOT_STARTED | `parity-matrix.json:3485`, `:2573` | approved 2026-10-13; built and tested | `mvp-acceptance-harness#17` (a full-suite PR) |\n'
    '| E30 "the map figure carries Stress-1" | `mvp-execution-contracts.md` E30 | `-5` computes no Stress-1 | noted in the contracts by the freeze |\n')

# §9 production sizing
rep("The hostname, RDS sizing and Bedrock quota are\nstill the owner's and an operator's (`mvp-target-architecture.md` §9).",
    "The proposed sizes are accepted (D-20); production moves to a new domain the owner has\nnot yet named, and the Bedrock quota is an operator's (`mvp-target-architecture.md` §9).")

# §11.1: the freeze answers
rows = '''| The MVP ships `aia-sociomap-5`; it is the only method of new runs, the old methods leave every product path, maps are drawn from `-5` | MVPQ-13 and D-13, owner 2026-10-20 | `signed-off-sociomap-method#8`, `signed-off-sociomap-method#9`, `research-lead-workbench#20` |
| Only the methodologist edits the methodology | D-14, owner 2026-10-20 | `signed-off-sociomap-method#10` |
| The money vocabulary, the plan card's confirmations, ceiling raises, revision moves and Deep Research charging | D-01 to D-05, owner 2026-10-20 | `lead-orchestration#LO0`, `lead-orchestration#LO1`, `lead-orchestration#LO4`, `lead-orchestration#LO10` |
| Conflicts per field; unaccepted changes rejected; the lock's reach; structural auto-accept's actor and switch | D-06, D-07, D-30, D-31, owner 2026-10-20 | `working-copy-edit-ops#WCE5`, `working-copy-edit-ops#WCE7`, `working-copy-edit-ops#WCE8`, `working-copy-edit-ops#WCE11` |
| Yes to amending ADR 0026 and ADR 0008 as each new ADR is accepted | D-08, owner 2026-10-20 | `mvp-master-plan#MP5` |
| The rest of the 48 answers: In, Out and Open in § The scope baseline | owner 2026-10-20 (`answers-2026-10-20.md`) | the chunks that section names |
'''
rep("| The delete path is required before release | MVP-30 | `study-data-lifecycle#SDL1`, `study-data-lifecycle#SDL3` |\n",
    "| The delete path is required before release | MVP-30 | `study-data-lifecycle#SDL1`, `study-data-lifecycle#SDL3` |\n" + rows)
rep("| Each researcher has their own private Lead | F12, Q26 |",
    "| Each researcher has their own private Lead, built and named by them, never transferred | F12, Q26; D-32 to D-34, owner 2026-10-20 |")

# §11.3: S4's pointer
rep("| `deep-research-web-search#54`; contradicts the open posture's intent |",
    "| `deep-research-web-search#53`; contradicts the open posture's intent |")

# §11.4: point at the baseline
rep("These are unanswered choices, not expired questions.\n",
    "These are unanswered choices, not expired questions. The scope freeze's own open questions (Q1 to\nQ8) are in § The scope baseline; the methodology owner's are MQ-01 to MQ-24 in\n[the methodology packet](../mvp-methodology-packet.md) (#510).\n")

# §11.5
rep("The Brave plan and sign-off; the production hostname, Cognito and Google callbacks;",
    "The Brave plan and sign-off; the production domain (new, not yet named: D-20), Cognito and Google callbacks;")

p.write_text(s, encoding="utf-8")
print("ok")
