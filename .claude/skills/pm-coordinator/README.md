# pm-coordinator

The AIA PM coordinator's routine, shared by the product owner's two claude.ai accounts so both run the PM role
the same way: the start-of-session checks, the permission rules it applies from CLAUDE.md §5, the merge gate
(`merge_gate.sh`, one PR; `merge_loop.sh`, every pin every 4 minutes for up to 2 hours, state in `$PM_STATE`
outside the repo; `test_merge_gate.sh` its regression test), CI and review handling, delegation, the session sweep it borrows from `pmstatus`, shared
artifact exports through `artifact-sync`, and how it reports. `SKILL.md` is the skill; start there.
