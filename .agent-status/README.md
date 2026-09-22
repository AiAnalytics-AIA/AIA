# Agent status coordination

A communication bus between concurrent Claude Code agents, the human, and ChatGPT
as the coordinating/review layer.

## Rules

- **This branch is never merged.** Not into `main`, not into a feature branch,
  not into a release branch. No PR is opened from it. It is disposable
  infrastructure, not product history.
- **One file per agent**, named `.agent-status/<AGENT_ID>.md`. An agent writes
  only its own file and never modifies another's.
- **No shared mutable index.** There is deliberately no `LATEST.md` and no
  timestamp index — they would generate merge conflicts for no benefit. This
  directory listing *is* the registry.
- **Each file is current state, not a diary.** It is rewritten each turn, not
  appended to.
- **Observed state only.** "CI not run yet" rather than "CI should pass"; a
  command's actual result rather than "tests pass".
- **No secrets.** No keys, tokens, credentials, cookies, raw confidential
  datasets or unnecessary PII. Sensitive results are summarised, never pasted.

The repository itself remains the durable source of truth: `ARCHITECTURE.md`,
`CLAUDE.md`, `AGENTS.md` and `.planning/` are unaffected by anything here.
