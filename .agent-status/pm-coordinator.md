# pm-coordinator — the AIA PM session

Current state, rewritten each update. Observed state only. No secrets.
Updated: 2026-10-20 ~16:00 UTC by session_019bYPVpsShVq3LCtWDT5Kr8 ("AIA PM: coordinator", ~60% context).
A successor ("AIA PM: coordinator 2") starts from this file.

## Mandate (Nigel, 2026-10-20)
- PM for every AIA session; others are workers. Steer directly (act, then tell Nigel); start sessions only
  for chunks the master plan schedules; merge any green PR I've reviewed (merge commit, expectedHeadSha).
- Context rule: ~70% → handoff in .agent-status/<role>.md, successor seeded from it, archive the old one.
  A session Nigel chats with is rotated only after its current task. Hourly sweep trigger
  trig_01EHrD4yfirNC8CyeybzjztB (:57) does this check.
- **SCOPE FREEZE (Nigel, ~15:25):** no feature code until Nigel signs a dated scope baseline in the master
  plan. Security fixes allowed (he kept the Next.js upgrade). W0 lanes (S1/S2/S3) NOT started.
- AWS writes are Nigel's; the infra session proposes, Nigel approves (master plan §8).
- Nigel prefers: interactive questions, one at a time, each with a worked example; PDFs for documents to
  read (he asked for the methodology packet as two PDFs: methodology vs engineering).

## Decisions recorded today (Nigel) — don't re-ask
- X1 build segment evidence; X8 build questionnaire routing end to end; X10 remove Settings' draft test.
- Spending "envelope" → **wallet** in code/plans; Czech UI **Peněženka** (#511). Other envelopes untouched.
- **The MVP ships `aia-sociomap-5`** (MVPQ-13, ~15:35), hybrid rejected. -5 is INTERNAL_ONLY until
  Arigamaru registers it (MQ-01); runs can't pin it yet (E-1; ADR 0038 proposes the fix).
- CI should fail on high/critical vulnerabilities (#509; npm gate option still pending, see below).

## Sessions
| Session | Title | Role / state |
|---|---|---|
| session_01RxUnHwTXGVFYjwzfpKi9kT | AIA planning 2: master plan + docs PRs | planner; owns #511; building the consolidated DECISION LIST (freeze step 4 part 1), then applies answers + baseline (part 2). Nigel chats here. |
| session_015hqQ6KEtJb864UHuU74ypp | AIA scope 2: methodology packet | #510, holding for Nigel's review |
| session_01Qg43kRfsZ97FjA8XenP28x | AIA scope 3: MVP ADR drafts | #512 (0028-0038), holding |
| session_01EWprA36RBr7HAF58DTxTNn | AIA scope 1b: reverse scope audit | #513, holding |
| session_01Hv8Phz319H6u3HLQ2BgF6C | AIA scope 1c: client pages + Settings impact | #514, holding |
| session_01FskpgUny4pDAMYFBLvAj4S | AIA scope 1a: cross-check tracks 5-7 | #515, holding |
| session_01QzemVrHfQp8jsVEqXb9W6x | AIA fix: Next.js 16.4 security upgrade | #509; waiting on Nigel's npm-gate choice |
| session_01LBR1SyjXK8uYR5VdBjGAEJ | AIA infra audit | env "AIA infra" (personal; I can't start sessions there). View-only IAM user aia-claude-infra via SigV4 proxy secret; plan -lock=false. Was blocked 14:56-16:00 asking to install tools; told yes at 16:00. |
| session_01End3azGdHNr1MtxRjUqqZ8 | AIA design: MVP workbench artifact | idle; https://claude.ai/artifact/JrWZXosJtKVLckHhArngeV |
| archived | AIA planning (old), AIA #504 review | handoff .agent-status/planning.md; plan-page generator .agent-status/planning/plan-page/ |

## PRs (AiAnalytics-AIA/AIA)
- Merged today: #506, #504 (18d59ea6), #507 (854c2092), #508 (86ec0cdd). Closed: #505.
- Deploy develop 39449232101 (854c2092, first with numpy/scipy/numba): SUCCESS 15:38 (host smoke +
  "Confirm from outside" passed). This container can't reach the site (proxy 403).
- #509 Next 16.4.2 + blocking pip-audit: prod npm 0 high; 5 dev-only high = braces GHSA-vfj7-8cjw-p6xm, no fix
  exists. Nigel's choice pending: (1) block all + one dated exception [recommended] (2) prod only (3) npm advisory.
  Nigel did not answer when asked (switched topic). Don't merge until chosen.
- #510 methodology packet (head 188e64c): reviewed by me; PDFs made and sent to Nigel (scratch, rebuild with
  build.py + headless chromium). Not to be sent to Arigamaru until Nigel approves.
- #511 wallet rename (head 8fb59523): reviewed OK (only money envelope renamed); full CI ~50 min; MERGE WHEN GREEN.
- #512 ADRs 0028-0038, #513 reverse audit, #514 client/settings impact, #515 cross-check 5-7: freeze inputs,
  docs-only drafts. Merge after Nigel signs the baseline (or earlier as evidence, with his OK).
- Merge hazard: a docs-only push to develop cancels an in-progress develop CI run (and its deploy dispatch);
  deploy-develop itself has cancel-in-progress: false. Don't merge docs while a code CI run is pending.

## Freeze status
Inputs complete (#510, #512-#515). Key findings: reverse audit 313 rows (49 MISSING, 84 PARTLY); production
operation unplanned; -5 reaches no user (pin, register, web, report); client posture/wallet ceiling/data
contract have no screen; Lead conversation controls unplanned; ~21 new gaps G58-G78. NEXT: planning 2's
decision list → I present it to Nigel → he answers (interactive) → planning 2 applies + baseline → Nigel signs.

## Open items
- Dependabot: develop's real exposure = apps/web npm (fixed in #509); Python 0/88; the 112 alerts are mostly
  main (618 commits behind develop) + legacy/. Suggest a develop→main release sometime.
- Optional for Nigel: add "Security and dependency scan" to required checks; archive the spare empty
  "AIA infra" env in the Artchain s.r.o. org; root MFA.
- make ui-capture crashes in cloud image (capture.mjs imports CJS playwright as ESM; #514 F-1).
