# pm-coordinator — the AIA PM session

Current state, rewritten each update. Observed state only. No secrets.
Updated: 2026-10-20 ~15:40 UTC by session_019bYPVpsShVq3LCtWDT5Kr8 ("AIA PM: coordinator").

## Mandate (from Nigel, 2026-10-20)
- This session is the PM for every AIA session. Other sessions are workers.
- It may steer sessions directly (act, then tell Nigel), start sessions for chunks the master plan
  schedules in the current wave, and merge any green PR it has reviewed (merge commit, expectedHeadSha).
- Context rule: when a session reaches ~70% of its context, have it write a handoff, start a
  successor seeded with that handoff, and archive the old one. The same applies to this session:
  its successor starts from this file.
- **SCOPE FREEZE (Nigel, 15:2x UTC):** no feature code until Nigel signs a dated scope baseline in the
  master plan. Steps: 1 complete cross-check + reverse scope audit + client/Settings impact; 2 methodology
  packet for Arigamaru; 3 Proposed ADRs; 4 freeze baseline (only step 4 edits mvp-master-plan.md; the
  others write their own new files and propose edits in PR bodies). Security fixes may proceed (Nigel: keep
  the Next.js upgrade). W0 lanes stay unstarted.
- AWS writes are Nigel's: the infra session proposes, Nigel approves (master plan §8).

## Sessions
| Session | Title | Role | State |
|---|---|---|---|
| session_01Y7frLAETBEYvez3sW7FbGF | AIA planning: master plan + docs PRs | — | **archived** 15:37 at 75% context; handoff .agent-status/planning.md, plan-page generator .agent-status/planning/plan-page/ |
| session_01RxUnHwTXGVFYjwzfpKi9kT | AIA planning 2: master plan + docs PRs | planner; owns #511; does freeze step 4 when asked; Nigel chats here now | starting |
| session_01End3azGdHNr1MtxRjUqqZ8 | AIA design: MVP workbench artifact | design artifact https://claude.ai/artifact/JrWZXosJtKVLckHhArngeV | idle; renamed Obálka→Peněženka |
| session_01LBR1SyjXK8uYR5VdBjGAEJ | AIA infra audit | read-only AWS audit (env "AIA infra", view-only IAM user aia-claude-infra, SigV4 proxy secret; plan with -lock=false) | running since 14:53 |
| session_01QzemVrHfQp8jsVEqXb9W6x | AIA fix: Next.js 16.4 security upgrade | next 16.4.x + make CI audits blocking (2 commits, one PR) | running |
| session_01FskpgUny4pDAMYFBLvAj4S | AIA scope 1a: cross-check tracks 5-7 | evidence, Deep Research, acceptance -> .planning/evidence/scope-freeze/crosscheck-tracks-5-7.md | running |
| session_01EWprA36RBr7HAF58DTxTNn | AIA scope 1b: reverse scope audit | product/V2/18.6.6 -> plan -> .planning/evidence/scope-freeze/reverse-scope-audit.md | running |
| session_01Hv8Phz319H6u3HLQ2BgF6C | AIA scope 1c: client pages + Settings impact | -> .planning/evidence/scope-freeze/client-and-settings-impact.md | running |
| session_015hqQ6KEtJb864UHuU74ypp | AIA scope 2: methodology packet for Arigamaru | -> .planning/mvp-methodology-packet.md (incl. -3 vs -5 for the MVP) | running |
| session_01Qg43kRfsZ97FjA8XenP28x | AIA scope 3: MVP ADR drafts | ADR 0028+ Proposed (wallet terminology) | running |
| session_01RrejghM5i8fKCMZVsVrnpV | AIA #504 review (done, merged) | — | archived |

## PRs (AiAnalytics-AIA/AIA)
- Merged today: #506 (owner answers), #504 (aia-sociomap-5, 18d59ea6), #507 (cross-check dispositions, 854c2092).
- Closed: #505 (superseded by #506; its commits already in develop).
- #508 docs follow-ups of #499-#507 (head 9d7e3c5c): reviewed and approved. **Merge only after develop CI
  run 39438021422 on 854c2092 has finished and dispatched the deploy**: a docs-only push cancels the
  in-progress run and skips the deploy (that's how the 18d59ea6 run got cancelled).
- #508 merged 86ec0cdd (after Codex's 3 fixes). #510 methodology packet (draft, being reworked for -5). #511 wallet
  rename (reviewed OK: only the money envelope renamed; merge when CI green). #509 Next.js (npm gate decision pending).
- Deploy develop run 39449232101 (854c2092, first with numpy/scipy/numba) started 15:31; verify result.

## Decisions recorded today (Nigel)
- X1 build segment evidence; X8 build questionnaire routing end to end; X10 remove Settings' draft test (#507).
- The spending "envelope" is renamed "wallet" in code and plans; Czech UI "Peněženka". It is not built yet;
  only the plans change. The Sociomap terrain envelope, Deep Research's orchestration envelope and the
  error-tracking envelope are different things and keep their names.

- **The MVP ships `aia-sociomap-5`** (Nigel, 2026-10-20, ~15:35 UTC), not -3. Passed to scope sessions 1a, 1b,
  1c, 2 (packet: what must be true for -5 to ship) and 3 (a new ADR). Needs: register approval of -5
  (INTERNAL_ONLY now), the web drawing -5, report figures for -5, runs pinning -5, reconciling MVPQ-03's
  descriptor segments with -5's taste segments.
- #508: Codex found 3 valid issues (P1 ARCHITECTURE.md OPEN-posture text lets design go to Class C model
  routes; P2 autopilot "out" unqualified; P2 MVP-8 says V3). Planning session fixing; re-review then merge
  after the 854c2092 deploy.
- #509 (Next 16.4.2 + blocking pip-audit): npm gate decision pending with Nigel (braces GHSA-vfj7-8cjw-p6xm,
  dev-only, no fix exists). Options: block all with one dated exception (recommended) / prod only / advisory.

## Open items
- Dependabot: develop's real exposure was apps/web npm (next 16.3.6 etc., 8 high); Python 0/88 vulnerable; the
  112 alerts are mostly main (618 commits behind develop) + legacy/. CI audits were `|| true` (advisory).
- Optional for Nigel: add "Security and dependency scan" to required checks in branch protection.
- Verify the first deploy carrying numpy/scipy/numba (854c2092) and the site's health.
- Process hazard (unconfirmed): with fast successive merges to develop, a code change can merge without
  being deployed. Not yet investigated.
- Optional for Nigel: archive the spare empty "AIA infra" environment in the Artchain s.r.o. org; root MFA.
