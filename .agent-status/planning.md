# planning — AIA planning session (master plan, decisions, docs PRs)

Current state, rewritten each update. Observed state only. No secrets.

**Session.** "AIA planning 4" (session_01MEBT7e3T7FmVqDKXs9Ea18), written 2026-10-26 ~00:50 UTC.
Coordinator: session_01MycSLqSRMw4g32SZwa9s7G (PM coordinator).

## Rules (unchanged)
- Docs-only PRs for shared docs; feature PRs never edit them. Footer on every GitHub post.
- Commit and push only on Nigel's own words in this session. Q49's standing docs permission has lapsed
  (coordinator, 2026-10-25).
- Until Codex's review quota is reliable, a Claude stand-in review on the exact head counts at the
  coordinator's gate (Nigel, 2026-10-25 23:20). A new push needs a fresh review: batch the fixes.

## Merged this session (develop @ bd9699ed after #908)
- #893 audit answers, #894 study-deletion plan + ADR 0043 (Proposed), #896 PE12 (OI-35's cookie
  session, S3, W1).
- #902 CLAUDE.md (66 PRs' follow-ups, -5 gaps, RD0 warnings, document model -6).
- #904 open-items OI-232..OI-246 (F1 = OI-232, editor clock skew = OI-233, ADR 0026 403 gap = OI-241);
  closed OI-78, 200, 207, 220, 234.
- #908 #817's follow-ups (OI-247..OI-250), lead-identity core W3 (Nigel 2026-10-25 ~23:47; S1 / I-1
  proposed), LC5b's wave via #909.

## Open
- #903 (ARCHITECTURE, AGENTS, ADR notes 0018/0020/0022/0024/0026, deep-research.md) @ 9277a097: all
  checks green, Codex clean, mergeable clean; waiting on the coordinator's merge.

## Next
- Nigel's review-page answers (ADR 0041 amendment, SD Q1-Q8, MP3, 5b, S2-S5, ADR 0020-0024
  amendments; https://claude.ai/artifact/7foR2FhvVCL9yge7CLC8y6), relayed by the coordinator.
- Doc follow-ups of PRs merged after #890 (e.g. #895, #901, #891); the inventory method:
  search merged PRs with a "Doc follow-up" heading after the last docs PR.
- Docs follow-ups noted, not applied: `domain/report/client_gate.py`-style code comment at
  routers/research.py:3710-3712 ("No paid start outside the Lead…") needs a feature-PR fix.
