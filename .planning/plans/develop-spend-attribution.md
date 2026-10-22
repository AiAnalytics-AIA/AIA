---
status: in-progress
chunks:
  - "[ ] 1. Terraform: an application inference profile, tagged Environment=develop, for every live model the acceptance run uses (main, the Lead's, the light model)"
  - "[ ] 2. IAM and the model policy follow the profiles; the cost-allocation tag is activated (a billing action)"
  - "[ ] 3. A reconciliation: AIA's usage ledger against the AWS cost record for the tag over a window"
  - "[ ] 4. The runbook states the check, its lag and its tolerance"
  - "[x] 5a. The worker accepts what the plan creates (W0): a tagged profile ARN or an `eu.` id, decided as a model identity versus an invocation target; and the statement "no Environment tag" corrected"
  - "[ ] 5b. The reconciliation's lines (W3): model usage, tool and search spend, open reservations and uncertain calls, each separate, after `deep-research` 4; billing lag recorded, never zero"
  - "[ ] 6. An organization's monthly spend, read-only for OWNER and ADMIN in Settings: model, Brave and other tool spend across clients, from the content-free rows MVPQ-07 keeps (D-47)"
  - "[x] 7. Per-researcher spend (Q40): an actor user id on every ai_usage_events, budget_reservations and tool-spend row, booked to whoever approved or started the paid work; a per-person aggregate route (OWNER/ADMIN see everyone, a researcher only themself); Settings → Studie a rozpočty \"Útrata podle výzkumníka\" (the Settings prototype, round 5); after lead-orchestration LO1's wallet holds"
---
# Spend proven twice: AIA's ledger and an AWS cost record

Track A of the MVP roadmap (`overview.md` § MVP roadmap, #493). Written 2026-10-19 from MVP-30 and
`mvp-cohesion.md` F7 (#496). **Owner: a chat session for chunks 1 and 3; chunk 2's tag
activation is the account owner's.**

## Decisions this plan carries

MVP-30: spend is proven by AIA's ledger **and** an AWS application inference profile tagged
`Environment=develop` (AR-3; one Terraform + IAM + model-policy change). `MVP-ACCEPT-2` AC-15:
spend reconciles to AIA's usage ledger within USD 0.01 and agrees with the develop-tagged AWS
cost record.

## What exists

- Terraform grants the instance role invoke on two inference profiles by id, the main model and the
  Lead's own (`infra/develop/main.tf:34, 39 @ 085abe0`, `var.bedrock_lead_model_id`,
  `var.bedrock_model_id`); the operator procedure is in `infra/develop/README.md:65-66` and
  `deploy/develop/README.md:502` (`aws bedrock get-inference-profile`).
- ~~The only tags in `infra/develop/main.tf` are `Name` and `Snapshot` on compute and volumes: no
  `Environment` tag, so no AWS cost can be filtered to develop today (grep, `main.tf:443-527`).~~
  **Corrected (5a, 2026-10-21):** every resource the provider creates carries `Environment =
  "develop"` through its `default_tags` (`infra/develop/versions.tf:33-42 @ 9bbc5019`), and the
  monthly budget already filters on it (`TagKeyValue` `user:Environment$develop`,
  `infra/develop/main.tf:600-610 @ 9bbc5019`). What is missing is a *Bedrock* resource the tag can
  sit on: model calls through a system inference profile carry no resource tag, which chunk 1's
  application inference profiles supply. Whether the tag is activated for cost allocation is
  chunk 2's billing action and is not visible in Terraform.
- AIA's append-only usage ledger (`infrastructure/ai_usage_repository.py`) records every call's
  cost as priced from the model catalogue, not as AWS billed it.

## Chunks

1. **Profiles.** Application inference profiles over the system EU profiles for **every live
   model the acceptance run can call**, each tagged `Environment=develop`: the main model, the
   Lead's model and, when live Deep Research enables it, the light model that serves
   `RESEARCH_TRIAGE` through its own profile (`LightModelSettings`,
   `apps/executors/src/aia_executors/ai_runtime.py:187 @ 085abe0`, marked *Proposed* there). A
   model left untagged still enters AIA's ledger but not the tagged AWS cost, so chunk 3's
   reconciliation would disagree by design. Their ARNs replace the ids in the settings the worker
   reads (`AIA_BEDROCK_*`, `AIA_AI_RESEARCH_LEAD_MODEL_ID`, the light model's). One Terraform
   change. List the models in use from the registry, not from memory.
2. **IAM and policy.** The role's invoke grants point at every application profile above; the model
   policy's profile ids follow (`ModelRegistry` fails closed on an unknown id, so a mismatch
   refuses before a call). The `Environment` cost-allocation tag is activated in billing: a human
   action, named in the runbook, not Terraform.
3. **Reconciliation.** A read-only command (under `tools/` or `aia_executors/smoke.py`) that sums
   the ledger over a window and reads the tagged AWS cost for the same window, printing both and
   the difference. Test the arithmetic on recorded figures; the live read is an operator's.
4. **Runbook.** In `deploy/develop/README.md` (docs PR): how to run the check and what it proves.

## Risks stated, not assumed

- **Hypothesis: "within USD 0.01" may be unreachable.** AWS cost data lags (a day, by AWS's own
  documentation, unverified here) and rounds its own way, and the ledger prices from AIA's
  catalogue. If the live check differs by more than a cent for reasons of rounding or lag, chunk 3
  reports the difference and the owner sets the tolerance. Do not loosen the criterion to pass it.
- Changing the profiles changes the model route; the licence determination names
  `bedrock-eu-primary` (OI-61). Confirm the application profile is the same route in the
  determination's terms before chunk 1 merges.

## Depends on / feeds

Independent of the other tracks until tier B. Feeds AC-15 and the budget table in
`mvp-acceptance-harness` chunk 1.

## Doc follow-up

`deploy/develop/README.md` (runbook), `infra/develop/README.md` (the tag and the profiles).

## Added by the master plan (2026-10-19)

**5a.** The worker refuses a model id that is not an `eu.` profile id (`ai_runtime.py:254, 516`), so the
ARNs chunk 1 creates would stop the worker at start; and the plan's "no Environment tag" is wrong
(`infra/develop/versions.tf:34-40`, `main.tf:597-607` set one). Tool spend (Brave, Athena) is not in the
usage ledger, so AC-15 as written reconciles model spend only: `deep-research` 4 ("tool usage in the
ledger") is the chunk that closes that and is scheduled with this plan (**5b** is the reconciliation
that reads it). Gap G9.


## Execution prerequisite (2026-10-20)

Chunk 5a's semantic-model-id versus invocation-target contract is W0, before chunks 1-2
configure profiles. Implement compatibility before passing an application-profile ARN to a
validator requiring `eu.` ids; do not loosen arbitrary model identity. Reuse the same contract in
production PE7 before PE1's live model configuration. Chunks 5b, 3 and 4 are final reconciliation (5b W3, 3-4 W5):
model usage to its ledger within AC-15's USD 0.01, tool/search separately, tagged AWS billing in
its stated window with lag and a stated billing tolerance. Unknown billing is never zero.

## Migration (lane M9, only if needed)

If 5a finds the model fields cannot carry the application inference profile, the lane's **M9**
(`ai_usage_events.inference_profile_arn`) is added under 5a, **W0**, after lane M3 and before 1-2 configure profiles; if they can, M9 is
removed from the lane in the same PR. Gap G43.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

**New chunk.** 6 (W3), D-47 in. **5b** gains the infrastructure-charges line.

## 5a delivered (2026-10-21, E03)

**Decision: a model's identity and its invocation target are two values** (`domain/model_invocation.py`).
The identity is the `eu.` profile id each `…MODEL_ID` key carries today: the catalogue prices it, the
policy binds a capability to it, the request profile is declared for it, the licence determination's
route carries it and every usage-ledger row records it. Its validation is unchanged and not loosened
(an ARN given as `AIA_BEDROCK_MODEL_ID` is still refused, `test_a_wrong_target_stops_the_worker_by_name`).
The invocation target is what the Converse URL names: unset, the identity itself (today's
behaviour, byte for byte); set, an application inference profile ARN
(`arn:aws:bedrock:<region>:<account>:application-inference-profile/<id>`) in the route's own EU region.
Keys: `AIA_BEDROCK_INVOCATION_TARGET` (the route model), `AIA_AI_RESEARCH_LEAD_INVOCATION_TARGET`
(the Lead's own model), and `LightModelSettings.invocation_target` (the light model, which has no
keys yet). Each is checked at worker start by name; two models may not share one target; the
adapter (`BedrockConverseAdapter(invocation_target=)`) puts it in the URL as one percent-encoded
segment, which is exactly the URL botocore serialises for the same ARN
(`test_the_url_is_the_one_botocore_serialises_for_the_same_arn`, offline). Compose passes both keys to
the worker alone, empty by default; `env.example` names them.

Why this shape: chunk 1's ARNs carry no model name, so an ARN as the identity would break pricing,
the policy and the ledger at once; a second value leaves all of them on the id they already use. The
pair is asserted by configuration: whether a profile really copies the identity's system profile is a
fact in AWS (`aws bedrock get-inference-profile`), which the operator checks when setting it (chunk
2's runbook); the worker makes no AWS call to find out. A kill switch is the unset key.

**Lane M9 is not needed** (`ai_usage_events.inference_profile_arn`): the model fields carry the
identity, which is what a row is priced by, and chunk 3's reconciliation compares the ledger's total
with the AWS cost record filtered by the `Environment` tag over the same window, so it needs no
per-row ARN. The target in force is configuration, which the worker's composition record
(`lead-orchestration` LO12b, the digest on each run in LO12c) is the place to record. If chunk 3 finds
it must attribute per profile, M9 comes back with that evidence.

Tests: `packages/aia_core/tests/test_model_invocation.py`,
`apps/executors/tests/test_ai_runtime_invocation_target.py`,
`test_an_invocation_target_reaches_the_worker_alone_and_unset_changes_nothing`
(`test_develop_host_configuration.py`). Production PE7 reuses the same contract before PE1.

### Doc follow-up (5a)

- `mvp-development-plan.md` lane table: remove row M9 (5a found the model fields carry the
  identity; no `inference_profile_arn` column), or mark it "not needed, 5a".
- `CLAUDE.md` map, `ai_runtime.py`: "each `…MODEL_ID` is the model's identity; the optional
  `AIA_BEDROCK_INVOCATION_TARGET` / `AIA_AI_RESEARCH_LEAD_INVOCATION_TARGET` is the application
  inference profile ARN its calls go through (`domain/model_invocation.py`)"; and the domain list:
  "`model_invocation.py` A model's identity versus its invocation target (5a)".
- `deploy/develop/README.md` § The Research Lead's own model and the AI runtime section: the two
  optional keys, set in SSM once chunk 1's profiles exist.

## Per-researcher spend (chunk 7, 2026-10-21)

**Decision Q40 (Nigel, the product owner, 11:42 UTC, 2026-10-21): spend is attributed per researcher.**
A charge is booked to whoever approves or starts the paid work. OWNER and ADMIN see everyone's; a
researcher sees only their own.

**What exists** (`origin/develop @ 095a3e68`).

- `ai_usage_events.actor_id` is non-null (`packages/aia_core/src/aia_core/infrastructure/tables.py:1956`),
  copied from the egress decision's issued `StudyContext` (`:1940-1942`). A model call runs in the
  worker, whose scope `ScopeResolver` issues against a held lease, so whether `actor_id` names the person
  who started the run or the worker's own identity is **a hypothesis to settle first**, with a test. If it
  is the worker's, it is not the attribution Q40 asks for, and is not reused for it.
- `budget_reservations` (`tables.py:1629`) has no person column. `study_wallet_raises.raised_by`
  (`:1717`) names who raised a cap, not who spent. `approval_decisions.approver_user_id` (`:1871`) and
  `workflow_gates.decided_by_user_id` (`:1808`) name who approved, per decision.
- Tool spend (Brave, Athena) is held through `reserve_tool_budget` on the same reservations and enters
  a ledger only with `deep-research` 4 (chunk 5b above).

**The chunk.**

1. **Who pays.** One rule in the application layer: the person is the approver of the card, plan or
   budget lift that let the work start (`approval_decisions.approver_user_id`), else the person who
   started it (a typed chat start, Spuštění's Start, a direct start). Never a model, never the worker;
   a row with no such person stores null and is listed as "nepřiřazeno", never booked to someone by
   guess (CLAUDE.md § 8).
2. **The column.** An actor user id (`charged_to_user_id`, nullable) on `ai_usage_events`,
   `budget_reservations` and the tool-spend rows, set at reservation from the run's recorded starter
   and copied to each usage row; never from a request body or a model's output. One migration (its lane
   in the master plan's migration list), with a round-trip and an isolation test. Rows written before
   it stay null; nothing is backfilled by inference.
3. **The holds.** The wallet's quote and charge (`lead-orchestration` LO1, `study_wallet_charges`, one per
   run) carry the same person, so a researcher's total and the wallet agree. **Depends on LO1's wallet
   holds** being the path every paid start takes.
4. **The route.** A per-person aggregate, read-only: by researcher, by month, model and tool spend
   separate, open holds named apart and uncertain calls never counted as zero (5b's rules). OWNER and
   ADMIN read every member of the organization; a researcher reads only their own row, enforced in the
   query, not by filtering a full list.
5. **The screen.** Settings → Studie a rozpočty, "Útrata podle výzkumníka", following the Settings
   prototype's round 5: one row per researcher, the month's total and its parts; a researcher sees
   themself only.

**Tests.** The payer rule per start path (card, plan, typed start, Spuštění's Start, budget lift);
unknown stays null; a researcher's read refused for another person; the aggregate equals the sum of
the rows within USD 0.01; open holds and uncertain calls listed apart.

### Doc follow-up (chunk 7)

- `mvp-master-plan.md` and `mvp-execution-contracts.md`: a register row and a wave for
  `develop-spend-attribution#7` (after LO1; with chunk 6, W3), and the migration in the lane table.
  `tools/master_check.py` fails ("open chunk … has no wave") until they land.
- `mvp-owner-decisions.md`: Q40 as answered.
- `CLAUDE.md` § 2: the new column and route when chunk 7 lands.

## Chunk 7 delivered (2026-10-21, Sprint 5, Q49)

**The hypothesis, settled: `ai_usage_events.actor_id` is not the person Q40 asks for.** It is the
egress decision's actor (`application/model_gateway.py:855 @ 25f26232`), and a worker's scope
names as actor the run's `triggered_by`, else the lease identity `worker:<worker_id>`
(`application/scope.py:359` and `:388 @ 25f26232`); `triggered_by` is whoever's scope created the
run (`infrastructure/workflow_repository.py:546 @ 25f26232`); and a resolution row's actor is the
person who resolved it (`infrastructure/ai_usage_repository.py:289 @ 25f26232`). So it is the
starter (never an approver, a budget lifter or a card's approver), falls back to a non-person
string, and moves on a resolution. Test:
`test_the_ledgers_actor_is_the_runs_starter_or_the_worker_never_the_payer`. It is left as it is
(it records the scope that wrote the row) and not reused.

**The rule** (`domain/spend_attribution.py` `charged_to`), over facts read from the approval
ledger and the run (`infrastructure/workflow_repository.py` `charged_to_for_run`, there because
that module is one of the ledger's two readers, `make layer_check`):

1. the latest **budget lift** of the run (`budget`, decision `lift`, the run's `run_id`): a lift
   approves the run's further paid work, so the holds made after it are the lifter's;
2. the **one person whose approval started it**: `spend`, `answerability`, `chat_start`,
   `plan_step` rows naming the run in `run_id`, and the Lead card (`lead_job_request`) whose
   comment names it as `agent_run_id`, parsed, never matched as text alone. Two different
   approvers: booked to nobody, not to one of them;
3. else the run's **starter** (`triggered_by`) when it is a member of the run's organization; a
   worker id or an unknown id is no person;
4. else null, listed as "Nepřiřazeno".

Every start path today reaches it unchanged: a person's own start (Spuštění's Start, a retry, an
analysis retry, a Deep Research or Interpretation Research start, a Lead turn, the client's own
work) creates the run under that person's scope, so rule 3 names them; a spend confirmation or an
answerability acknowledgement names its person by rule 2; a Lead card's agent job by rule 2; a
budget lift by rule 1. LO5's typed chat start and LO3's plan step have no writer yet; their ledger
rows are the wallet charge's authority (LO1), so a wallet-charged run's holds are booked to the
same person as its charge, and a researcher's total and the wallet agree by construction (test:
`test_a_wallet_start_books_its_decisions_approver`, both subjects).

**The columns** (migration `568761e1c719`, down revision `60ccc9ff42cf`, one head):
`charged_to_user_id` (nullable) on `budget_reservations` (every hold: a model call's and a priced
tool call's, `reserve_tool_budget`, which are the tool-spend rows until `deep-research` 4) and on
`ai_usage_events`; indexes `ix_reservations_charged_to`, `ix_usage_charged_to`,
`ix_usage_reservation`. A hold takes its person in `WorkflowRepository._reserve`, under the lease,
never from a request body or a model; a usage row copies its hold's at append
(`AIUsageRepository._charged_to`), so a call, its hold and its resolution always name one person;
a call with no hold (a subscription runtime) takes the run's by the same rule. **No column on
`study_wallet_charges`**: a charge names its authorising ledger row by a NOT NULL foreign key, whose
`approver_user_id` is the person exactly; a copy would be a second source of one value.

**The backfill takes only what the ledger names**: a past hold is booked to the latest lift of its
run written no later than the hold, else the one approver of its run's start rows above, else
stays null; `triggered_by` is not the ledger and is not used for past rows. A past usage row takes
its hold's person. Measured on a fresh PostgreSQL 16: `alembic upgrade head`, `downgrade -1`,
`upgrade head` clean; `alembic.autogenerate.compare_metadata` against the models: 0 differences.
The downgrade drops both columns and the indexes.

**The route**: `GET /api/v1/settings/researcher-spend?period=this_month|last_month|year_to_date`
(`routers/researcher_spend.py`, `application/researcher_spend.py`,
`infrastructure/researcher_spend_repository.py`). Per person: model spend (the usage ledger,
compensations included, by `occurred_at`), spend outside the ledger (holds settled in the period
that no usage row names: tool calls), the holds open **now** (whatever the period), uncertain calls
(a model call dispatched in the period with no resolution and no known outcome, and a tool hold
settled uncertain), the study count; by activity (`lead`, `fieldwork`, `analysis_report`,
`deep_research`, `other`: agent jobs, client documents, validation) and by study. Months are UTC.
OWNER and ADMIN read every member (a member with no rows at a known zero), anyone booked who has
left, and the unattributed row; anyone else reads only rows booked to themself, **in the query**
(`ResearcherSpendRepository._booked`), never a full list filtered afterwards.

**The card**: Settings → Studie a rozpočty, "Útrata podle výzkumníka"
(`components/aia/settings/ResearcherSpendCard.tsx`, pure part `lib/researcher-spend.ts`): the three
periods, one row per person with the total, its parts (an activity at a known zero left out), the
held amount and the study count; a row opens to its studies; the organization's total for an
administrator. A total with an uncertain call carries "?" and says how many calls have no known
price; a total that is zero only because nothing is known reads "neznámá", never 0,00 USD. The
Settings prototype (round 5) could not be read from this session; the card follows the plan's
description above.

Tests: `packages/aia_core/tests/test_spend_attribution.py` (the rule; the activities held to the
workflow constants; the periods; the fold: model, outside the ledger, reserved, uncertain, parts
summing to the whole; the hypothesis; the payer per path: own start, spend confirmation, Lead
card, chat start and plan step, two approvers, a non-member starter, a budget lift before and
after; the usage row and its resolution; the read for an administrator and for a researcher, the
researcher's rows checked before any fold; last month; the aggregate equal to the rows within
USD 0.01; the backfill; the DDL round trip on PostgreSQL),
`apps/api/tests/test_researcher_spend_api.py` (owner sees everyone and the unattributed; a
researcher sees only themself; the periods; 401),
`apps/web/src/lib/researcher-spend.test.ts`,
`apps/web/src/components/aia/settings/ResearcherSpendCard.test.tsx`, and a ControlPanel test that
the card is on the tab.

### Findings (chunk 7)

- **F-SA7-1. Tool spend is identified by absence.** "Outside the ledger" is a settled hold no
  usage row names: today that is exactly the priced tool calls, but a model hold settled without
  its ledger row would be counted there too (as real spend, never lost). Anchor:
  `infrastructure/researcher_spend_repository.py` `holds` (`in_ledger`) @ this PR. Closes when
  `deep-research` 4 gives tool calls their own ledger and 5b reads it.
- **F-SA7-2. A budget lift books the rest of the run to the lifter.** Read from "approves" in Q40;
  a lift by someone other than the starter moves the run's later holds to them. If the owner reads
  Q40 as "the starter keeps the run", the change is rule 1's removal in `charged_to` and its test.

### Doc follow-up (chunk 7, replaces the list above)

- `mvp-master-plan.md` / `mvp-execution-contracts.md`: `develop-spend-attribution#7` done; the
  migration `568761e1c719` in the lane table after M4 (`60ccc9ff42cf`).
- `mvp-owner-decisions.md`: Q40 as answered and delivered here.
- `CLAUDE.md` § 2, `routers/`: "settings (…) `GET /settings/researcher-spend?period=`: each
  person's spend (Q40), everyone for OWNER/ADMIN, the caller's own otherwise, in the query";
  `domain/`: "`spend_attribution.py` Who a charge is booked to (Q40: the budget lift, else the
  one start approver, else the starter, else null) and the per-person fold"; `application/`:
  "`researcher_spend.py` the per-person report"; `infrastructure/`: "`researcher_spend_repository.py`
  per-person spend rows, scoped in the query"; the `workflow_repository.py` line: "`charged_to_for_run`:
  the person a hold is booked to"; `tables.py` / the ledger line: "`charged_to_user_id` on
  `budget_reservations` and `ai_usage_events`, never `actor_id`"; web: "settings/ResearcherSpendCard
  (Útrata podle výzkumníka, on Studie a rozpočty; lib/researcher-spend.ts)".
- `AGENTS.md` (SQLAlchemy): a `select` of more than ten columns types its rows as a variadic tuple,
  so `for (a, b, …) in rows` fails `mypy --strict` ("Variadic tuple unpacking requires a star
  target"); read such rows through `row._mapping[Column]` instead.
