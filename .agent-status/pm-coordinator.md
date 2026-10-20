# pm-coordinator — the AIA PM session

Current state. Observed state only. No secrets.
Updated: 2026-10-20 ~17:25 UTC by session_01YEVg53K5fKSGUfcKPTdrRk ("AIA PM: coordinator 2"), successor of
session_019bYPVpsShVq3LCtWDT5Kr8 (archived 16:35 at 73% context). Nigel talks to this session. Tools: .agent-status/pm-coordinator/tools/ (README there).

## Mandate (Nigel, 2026-10-20)
- PM for every AIA session; others are workers. Steer directly (act, then tell Nigel); start sessions only for chunks the plan
  schedules or Nigel approves; merge any green PR I've reviewed (merge commit, expectedHeadSha).
- Context rule: ~70% -> handoff in .agent-status/<role>.md, successor seeded from it, archive the old one (a session Nigel chats
  with: after its current task). Run an hourly sweep (create your own trigger; the old one fired into the old session).
- **SCOPE FREEZE** (~15:25): no MVP feature code until Nigel signs a dated scope baseline. Security/infra fixes he approves are OK.
  W0 lanes (S1/S2/S3) NOT started.
- AWS writes are Nigel's (infra session proposes). A relayed message is not Nigel's permission for a commit in another session
  (the infra session correctly waits for Nigel's own "commit and push").
- Nigel's style (restated 17:30): ALWAYS ask via AskUserQuestion, each with context, a worked example and WHY the recommended option; PDFs for documents; he decides fast with recommendations.
- Merge hazard: a docs-only push to develop cancels an in-progress develop CI run (and its deploy dispatch). deploy-develop has
  cancel-in-progress false. Don't merge docs while a code CI run on develop is pending.
- This container can't reach aia-develop.art-chain.io (proxy 403); deploy evidence = workflow smoke + infra session (CloudWatch).

## Decisions recorded today (Nigel) — don't re-ask
17:30: host user_data -> (a) lifecycle ignore_changes (infra session prepares; Nigel's own commit-and-push); Google IdP -> Nigel runs the
read-only check first; budgets:ListTagsForResource -> Nigel adds it; hourly sweep -> NO SWEEP (stay event-driven; don't ask again).
X1 segment evidence; X8 routing end to end; X10 remove Settings draft test; spending "envelope" -> **wallet**, Czech **Peněženka**
(#511); **MVP ships aia-sociomap-5** (MVPQ-13), -5 is CANONICAL (the old formula audit stands only where -5 is silent; packet fixed
in #510 @ 798d87a); CI fails on high/critical vulns; npm gate = all deps + ONE dated exception (GHSA-vfj7-8cjw-p6xm, expires
2026-11-20, matched by GHSA id); infra read policy terraform-plan-read: ATTACHED 17:14 by Nigel (account 311141567391; his CloudShell was first in
another account, which has only user openclaw-cornelius); disk fix: ONLY the Dockerfile dependency layer (not retention, not 75% alarm).

## Sessions
| Session | Title | State |
|---|---|---|
| session_01RxUnHwTXGVFYjwzfpKi9kT | AIA planning 2 | owns #511 (wallet) and #516 (decision list); waits for Aram's answers, then freeze step 4 part 2 (apply + baseline). Nigel chats here. |
| session_015hqQ6KEtJb864UHuU74ypp | AIA scope 2: methodology packet | #510 @ 798d87a, holding (Nigel reviewing; send to Arigamaru only on his go) |
| session_01Qg43kRfsZ97FjA8XenP28x | AIA scope 3: MVP ADR drafts | #512 (0028-0038), holding |
| session_01EWprA36RBr7HAF58DTxTNn | AIA scope 1b: reverse scope audit | #513, holding |
| session_01Hv8Phz319H6u3HLQ2BgF6C | AIA scope 1c: client pages + Settings | #514, holding |
| session_01FskpgUny4pDAMYFBLvAj4S | AIA scope 1a: cross-check 5-7 | #515, holding |
| session_01QzemVrHfQp8jsVEqXb9W6x | AIA fix: Next.js 16.4 security | #509 MERGED (f2b0b928); now building fix/npm-audit-blocking (the dated-exception gate) as a draft PR |
| session_01LBR1SyjXK8uYR5VdBjGAEJ | AIA infra audit | env "AIA infra" (personal; can't start sessions there). Waiting: Nigel attaches terraform-plan-read -> re-run full plan. versions.tf fix (>=1.10 + commit .terraform.lock.hcl) prepared, waits for Nigel's own "commit and push" in that session. Import cmd for errors DNS record recorded. |
| session_01AXkfBjA7hUPZipWXSoHzEc | AIA fix: Docker dependency layer | started 16:22; plan file + Dockerfile split + equivalence proof; draft PR |
| session_01End3azGdHNr1MtxRjUqqZ8 | AIA design: MVP workbench artifact | idle; https://claude.ai/artifact/JrWZXosJtKVLckHhArngeV |
| session_01YEVg53K5fKSGUfcKPTdrRk | AIA PM: coordinator 2 | THIS session. Subscribed #510, #512-#515, #518. All workers told of the change 16:33. |
| archived | AIA PM: coordinator (019bYP…), AIA planning (old), AIA #504 review | |

## PRs (AiAnalytics-AIA/AIA)
- Merged today: #504, #506, #507, #508 (86ec0cdd), #509 (f2b0b928). Closed: #505.
- MERGED 17:2x by coordinator 2: #511 wallet (125db46d) and #518 npm gate (47e55368). develop CI for #509 (run 39454751130) had
  stalled 30+ min in "Domain tests on SQLite"; #518's CI was green on top of f2b0b928, so it was cancelled by the merges. WATCH: the
  develop run on 47e55368 must pass and dispatch a deploy (carries #509 + #511 + #518). If its SQLite step stalls again -> real hang.
  Doc follow-ups (overview MVP-13/MVP-3 wallet; ARCHITECTURE §8 npm + pip-audit blocking) handed to planning 2 for the next docs PR.
- #510, #512, #513, #514, #515, #516: freeze inputs, docs-only drafts. Merge after Nigel signs the baseline (or earlier as
  evidence with his OK).
- #519 versions.tf + lock file (infra, b37833b): reviewed OK; merge when green, after #520.
- #520 docs follow-ups of #509/#511/#518 (planning 2): review; merge only after develop CI on 47e55368 dispatched its deploy.
- #521 host user_data ignore_changes (infra; Nigel said commit-and-push): review, merge when green.
- Google IdP fix prepared on fix/terraform-google-idp (infra), NOT committed: needs Nigel's own "commit and push" again.
- Coming: Docker layer PR (01AXkf...).

## Artifacts
- AIA Scope Decisions (for Aram to answer #516's 48): https://claude.ai/artifact/WdXcN8nQnQX3rW36hF8iVd. db collection "answers",
  doc per D-01..D-48 {choice, text, option_text, by, at, title}. Read with ArtifactData list. ALL 48 ANSWERED by Nigel (u_lDmchBNgQRXZ1nH5Fyv9hQ);
  handed verbatim to planning 2 at ~17:35 for step 4 part 2 (+ part 1b consolidation). Watch: D-13 (-5 ONLY, remove old methods), D-14
  (only the mathematician edits methodology), D-20 (new prod domain, TBD), D-35 (Lead edits docs freely + Lead web search = NEW SCOPE,
  collides with ADR 0017/0021: to be put to Nigel as a question). Planning sends new questions to the coordinator, not to Nigel. Nigel must share it
  with Aram (interact/edit). When answered: hand to planning 2 for step 4 part 2.
- PDFs sent to Nigel: methodology packet + engineering companion (@ 798d87a), decision list (@ c7d5bbe). Rebuild with tools/.
- MVP plan page https://claude.ai/artifact/RAYF6NZ1ctrAxo8qEYFWqR (generator .agent-status/planning/plan-page/).

## Infra facts (read-only audit)
- Full plan 17:15 @ f2b0b928: 1 add, 3 change, 0 destroy. Remaining denial: budgets:ListTagsForResource (add to
  TerraformRefreshBudgetAndCognito). Items put to Nigel 17:20: (2) aws_instance.host user_data drift since c4ba7032 (09-23) - an
  untargeted apply STOPS/STARTS the host; options (a) lifecycle ignore_changes=[user_data] (recommended) or (b) planned window;
  (3) github_deploy policy diff = side effect of (2); (4) HYPOTHESIS: Cognito Google IdP drops authorize_url ?hd=art-chain.io, so the
  Workspace domain restriction may never have applied; Nigel's read-only check: describe-identity-provider ... authorize_url.
- Deploy 854c2092 healthy (CPU back to ~10%, mem 31.6%, alarms OK). -5 not yet exercised under load.
- Disk: sawtooth, not a leak — ~1 GB per deploy kept 48 h by image_retention.py; troughs ~53%; deploys refused at 85% (= alarm).
- Next terraform apply fails until: terraform import 'aws_route53_record.errors[0]' Z0491946PNRJDOXB1EWV_errors.aia-develop.art-chain.io_A
- CI runs no Terraform step although infra/develop/README.md says fmt -check runs (for PE3).

## Open items
- QUESTIONS TO PUT TO NIGEL (interactive, context+example+why) when he's back (~19:30): from planning 2 at 17:35 - Q1 timing of the
  -5 switch (rec: merge when built), Q2 stored -1/-3 maps (rec: keep data, panel says rerun), Q3 product-only vs delete old engine
  code (rec: product only now), Q4 D-14 permission (rec: 'Metodik' member mark, store+activate), Q5 assigned lead researcher per study
  (rec: one assigned, only its Lead spends the wallet), Q6 D-35 report edits (rec: free edits, numbers stay ledger refs) + Lead web
  search (rec: 'Hledat na webu' via RetrievalGate, OPEN clients, cited), Q7 uptime probe (rec: GlitchTip monitor + named recipient);
  plus C-2 Metodika comparison of -5 outputs (rec: not in MVP). Full wording in planning 2's 17:35 message / its plan files.
  Nigel 17:40: "ask me the questions later" - hold until he asks. Also 2 sanity checks: D-33 read as 'no admin reading of another's
  Lead files' (out); D-38 taken IN in full.
- PRs from planning 2: #522 part 1b (consolidated edits), #523 part 2 = THE SCOPE BASELINE (master plan § The scope baseline, MP16
  signing, answers-2026-10-20.md, 20 child plans). Merge order #516 -> #522 -> #523, all only after Nigel signs. master_check ok.
- No hourly sweep (Nigel 17:30). Event-driven only; check session context when woken.
- Dependabot 112 alerts mostly main (618 commits behind develop) + legacy/; suggest a develop->main release sometime.
- Optional for Nigel: "Security and dependency scan" as a required check; archive the spare "AIA infra" env (Artchain s.r.o. org);
  root MFA.
- make ui-capture crashes in the cloud image (capture.mjs ESM import of CJS playwright; #514 F-1).
