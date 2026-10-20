# pm-coordinator — the AIA PM session

Current state, rewritten each update. Observed state only. No secrets.
Updated: 2026-10-20 ~15:00 UTC by session_019bYPVpsShVq3LCtWDT5Kr8 ("AIA PM: coordinator").

## Mandate (from Nigel, 2026-10-20)
- This session is the PM for every AIA session. Other sessions are workers.
- It may steer sessions directly (act, then tell Nigel), start sessions for chunks the master plan
  schedules in the current wave, and merge any green PR it has reviewed (merge commit, expectedHeadSha).
- Context rule: when a session reaches ~70% of its context, have it write a handoff, start a
  successor seeded with that handoff, and archive the old one. The same applies to this session:
  its successor starts from this file.
- **Not yet authorized:** the W0 build lanes (S1/S2/S3, mvp-development-plan.md §2-3). Nigel said
  "not yet" at 13:4x UTC; wait for his go.
- AWS writes are Nigel's: the infra session proposes, Nigel approves (master plan §8).

## Sessions
| Session | Title | Role | State |
|---|---|---|---|
| session_01Y7frLAETBEYvez3sW7FbGF | AIA planning: master plan + docs PRs | planner/worker; Nigel also chats with it directly | ~68% context; task: wallet rename PR (chore/wallet-rename, built on #508); due for rotation after that |
| session_01End3azGdHNr1MtxRjUqqZ8 | AIA design: MVP workbench artifact | design artifact https://claude.ai/artifact/JrWZXosJtKVLckHhArngeV | idle; renamed Obálka→Peněženka |
| session_01LBR1SyjXK8uYR5VdBjGAEJ | AIA infra audit | read-only AWS audit (env "AIA infra", view-only IAM user aia-claude-infra, SigV4 proxy secret; plan with -lock=false) | running since 14:53 |
| session_01RrejghM5i8fKCMZVsVrnpV | AIA #504 review (done, merged) | — | archived |

## PRs (AiAnalytics-AIA/AIA)
- Merged today: #506 (owner answers), #504 (aia-sociomap-5, 18d59ea6), #507 (cross-check dispositions, 854c2092).
- Closed: #505 (superseded by #506; its commits already in develop).
- #508 docs follow-ups of #499-#507 (head 9d7e3c5c): reviewed and approved. **Merge only after develop CI
  run 39438021422 on 854c2092 has finished and dispatched the deploy**: a docs-only push cancels the
  in-progress run and skips the deploy (that's how the 18d59ea6 run got cancelled).
- Coming: chore/wallet-rename (planning session).

## Decisions recorded today (Nigel)
- X1 build segment evidence; X8 build questionnaire routing end to end; X10 remove Settings' draft test (#507).
- The spending "envelope" is renamed "wallet" in code and plans; Czech UI "Peněženka". It is not built yet;
  only the plans change. The Sociomap terrain envelope, Deep Research's orchestration envelope and the
  error-tracking envelope are different things and keep their names.

## Open items
- Verify the first deploy carrying numpy/scipy/numba (854c2092) and the site's health.
- Process hazard (unconfirmed): with fast successive merges to develop, a code change can merge without
  being deployed. Not yet investigated.
- Optional for Nigel: archive the spare empty "AIA infra" environment in the Artchain s.r.o. org; root MFA.
