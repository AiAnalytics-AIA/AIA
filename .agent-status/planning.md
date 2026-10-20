# planning — AIA planning session (master plan, decisions, docs PRs)

Current state, rewritten each update. Observed state only. No secrets.

**Handoff.** Written 2026-10-20 ~21:45 UTC by session_01RxUnHwTXGVFYjwzfpKi9kT ("AIA planning 2"), at
73% context, for "AIA planning 3".

**Reporting line.** The session works under coordinator 3, session_01MycSLqSRMw4g32SZwa9s7G (it was
coordinator 2, session_01YEVg53K5fKSGUfcKPTdrRk, before that). Nigel may also talk to the session
directly.

## Role

The session is the planner for the MVP plan. It:
- writes docs-only PRs;
- applies the owner's answers to the plan files;
- cross-checks the plans against the code.

It does not:
- start sessions or workflows;
- merge (the coordinator merges);
- ask Nigel directly. The coordinator asks him on the PM status page (`/pmstatus`) and relays the
  answers.

## Open PRs (all docs-only, ready for review, green; merge in this order, after Nigel signs MP16)

| PR | Branch | Head | What it is |
|---|---|---|---|
| #516 | `chore/scope-decision-list` | `c7d5bbe` | The 48 freeze decisions. Codex raised 3 threads, all answered and resolved. Kept as the text Nigel answered against: don't edit it |
| #522 | `chore/scope-proposed-edits` | `049413c` | Part 1b: 102 proposed edits, deduplicated and tagged. Written before the answers. Codex found nothing. Its S-13 wording on segments is superseded by #523 |
| #523 | `chore/scope-baseline` | `1ba4bc0` | Part 2: master § The scope baseline (In / Out / answers tables / Open / signature line), MP16, 20+ child plans, waves, and `.planning/evidence/scope-freeze/answers-2026-10-20.md` (four tables: D-01..48, Q1-8, page Q10-12, page Q13-18) |

The baseline links `decision-list.md` (#516) and `proposed-edits.md` (#522). That is why #523 merges
last.

## Applied in #523

- **The 48 answers** (D-01 to D-48).
- **Q1-Q8:**
  - Q1-Q3: `-5` is the only method of new runs. It merges when built and stays internal until
    MQ-01. Old runs show "Mapa ze starší metody; spusťte běh znovu". The old engine and fixtures
    stay as reference.
  - Q4: the Metodik mark gates storing and activating methodology versions.
  - Q5: no study assignment, plus the study context file (LO19).
  - Q6: free report edits with every number still a ledger ref, and "Hledat na webu" (LO20, DR#56,
    RLW#32; needs a new ADR).
  - Q7: a GlitchTip uptime monitor alerting Nigel.
  - Q8: Metodika's full `-5` comparison (`signed-off#11`).
- **Page Q10:** LO19 also carries "Poznámky ke studii", which any researcher's Lead proposes and a
  person accepts.
- **Page Q11:** assumption statuses are UNTESTED, SUPPORTED, CONTRADICTED and RETIRED. Scope 3
  (session_01Qg43kRfsZ97FjA8XenP28x) was told that ADR 0033 drops UNVERIFIED.
- **Page Q12, the stage handoff:**
  - new LO9d: each stage worker's declared inputs;
  - AOC3: hypotheses reach the analysis payload;
  - WCE7: a map of what each stage reads, and staleness on pending proposals;
  - LO7: a pending-proposals layer in the Lead's context;
  - LO6: its test covers a job started through `approve_request`.
- **Page Q13-Q18:**
  - Q13: tracked-change suggestions (the default) or direct, undoable Lead edits, per researcher.
  - Q14: a departed member's Lead is sealed, then deleted at the 30-day retention end.
  - Q15: the production hostname is `app.ai-analytics.ai`.
  - Q16: Brave serves OPEN clients at release.
  - Q17: an old-method retry is refused with a link to a new `-5` run; approved old-method reports
    stay downloadable.
  - Q18: a Lead lookup needs no card; at most 3 queries, 5 pages and 2 lookups per turn, with a
    wallet hold, OPEN clients only.
- **Codex's findings:**
  - LO11, E16 and G17 no longer require a handover or an admin read.
  - WCE5 and E06 compare conflicts per `(item_key, field)`.
- **The coordinator's findings:**
  - segments stay defined by descriptors (MVPQ-03), `-5` is only the engine, and chunk 10 waits on
    nothing (MVPQ-04);
  - G75 is folded into `mvp-acceptance-harness#3` (chunk 17 removed);
  - posture belongs to `deep-research-web-search#53`, K11 holds the wallet ceiling only, and I15
    is corrected. The Settings prototype session (session_01Ku9CwQRUsBdPUbqWy6zYj7) was told.
  - The `-5` web layers and the report figure point at Aram's #517 and its `sociomap-5-web` plan
    (his own lane). RLW#20 hosts the panel, and `signed-off#9` keeps the chapter text.
  - The WCE4 feed is named `workspace/ops?since=`.
- **`master_check`:** ok at `1ba4bc0` (263 chunks with a wave, 0 unscheduled). `progress --check`:
  105 of 105.

## To apply first (planning 3): Nigel's answers Q19-Q21 (relayed by coordinator 3, 21:41 UTC)

None of these is in #523 yet. Apply them to #523 (head `1ba4bc0`), which closes Open items Q19 and
Q20 there.

- **Q19 (a): evaluate the editor before adopting one.** Add a W1 spike chunk, best placed in
  `research-lead-workbench` with a wave row, comparing Word- or LibreOffice-like editors for the
  study context file and reports.
  - The candidates:
    - Wordcraft (MIT/Apache, Rust/WASM, MCP server, alpha);
    - ONLYOFFICE Docs (AGPL, Word-like, track changes, JS API);
    - Collabora Online (LibreOffice-based, MPL, WOPI).
  - Tiptap is the baseline Nigel dislikes. His note: "maybe suggest alternatives, maybe tiptap, but
    even that had a terrible UX; I want as close to Microsoft Word or LibreOffice as possible".
  - The criteria: a Word-like UX; tracked changes and comments; the Lead driving the edits; ledger
    refs surviving a round trip; DOCX fidelity; the licence; EU self-hosting.
  - The outcome is a go/no-go to Nigel.
  - Replace the baseline's "editor: Wordcraft?" Open row with this chunk.
- **Q20 (b): Brave may receive Class B (design-derived) queries for every client, CLASSIFIED
  included.**
  - Record it as the owner's determination of 2026-10-20, in the style of OI-61, in
    `deep-research-web-search#53` and the baseline. It changes MVP-27's "CLASSIFIED tracks stay
    parked" for Class B queries.
  - His note: "maybe even class A, depends how the query is constructed. I like to implement google
    search hacking into the workflows, to create highly specific and reputable sources".
  - Class A stays refused until page Q22 is answered. Search operators (site:, filetype:, intitle:)
    are page Q23. Mark both Open.
  - This touches the ADR 0032 / ADR 0008 class rule: note it in the Doc follow-up, and tell scope 3
    (session_01Qg43kRfsZ97FjA8XenP28x) that ADR 0032 changes.
- **Q21 (a): the coordinator keeps merging reviewed, green PRs.** No plan edit is needed.

## Still open (in the baseline's Open table, or due next)

- **Page Q19:** the editor for Lead edits. Nigel named Wordcraft (github.com/storytold/wordcraft);
  the coordinator is asking whether AIA adopts it.
- **Page Q20:** Brave for Class B queries too. Until it is confirmed, CLASSIFIED clients' web tracks
  stay parked.
- **The MP16 signature.** The ticks on the status page are **not** the signature; the coordinator
  gets an explicit one. When it comes, record it on the baseline's signature line (a one-line docs
  commit in #523, or after merge as decided).
- **The input-interactions plan.** Session session_01BmmpzanxvKFquk44nLP4qu ("AIA design: input
  interactions audit") will propose `.planning/plans/input-interactions.md`. Fold it into #523, or
  into a follow-up if #523 has merged:
  - a §3 row;
  - waves in the contracts;
  - the ownership overlap with settings, client-workspace and research-lead-workbench.
- **The §3 row for `sociomap-5-web` when #517 merges** (suggested: core, S2 plus the methodology
  owner, I-2). Until then, never reference `sociomap-5-web#N` in backticks: master_check fails on a
  plan that is not on develop.
- **Still open from before:** the performance budget values (`mvp-acceptance-harness#18`), MQ-01 to
  MQ-24 (Aram, packet #510), MVPQ-06's evaluation thresholds, S2-S5, and accepting ADRs 0028-0038
  (#512) plus a new ADR for the Lead's lookup.

## Merged today from these sessions

- #511, the wallet rename (`125db46d`).
- #520, the doc follow-ups of #509, #511 and #518.

## Only this session knows

- **Where the answers come from.** The 48 D-answers came from artifact
  https://claude.ai/artifact/WdXcN8nQnQX3rW36hF8iVd, collection `answers`, every one by user
  `u_lDmchBNgQRXZ1nH5Fyv9hQ` (no display name is returned). Read them with `ArtifactData list`. The
  later Q answers were relayed by the coordinator from the `/pmstatus` page; the session never read
  that page itself.
- **The scripts used** for #523 are in this session's scratchpad (`apply_plans.py`,
  `apply_master.py`, `apply_q*.py`). Copies are in `.agent-status/planning/scripts/` on this branch (one-off, already applied; for reference). The pattern: insert
  front-matter lines before the closing `---`, append a "### After …" section to the plan body, and
  add wave rows to the contracts' "Every other open chunk" table before the
  `research-lead-workbench#24` row.
- **Every new open chunk of a core plan needs a wave row**, or master_check fails.
- **No embedded double quotes** inside a front-matter chunk string.
- **Docs-only PRs** run only the Documentation checks.
- **Don't push a docs-only change to develop while develop is deploying.**
- **`.agent-status` pushes** to this branch can 403 or reject non-fast-forward. Pull with rebase,
  then retry.
