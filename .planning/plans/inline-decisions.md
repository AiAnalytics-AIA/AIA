---
status: in-progress
chunks:
  - "[x] 1. Ověřeno, přidat zdroj: a person adds a Deep Research source to the client's knowledge with one inline click"
  - "[x] 2. Auto-accept the Lead's text edits: an opt-in per researcher, off by default, recorded in the ledger as auto"
  - "[ ] 3. Tick the plan"
---
# Inline decisions

Two usability decisions of the product owner, 2026-10-19. Both keep ADR 0026's rule: the model
proposes, a person decides. Neither lets a model write anything by itself.

## 1. "Ověřeno, přidat zdroj"

A source Deep Research captured is shown to the researcher with its URL, title and quote: on the
Design Research panel, on the Interpretation Research findings and under each research question's
design evidence. The researcher opens it, reads it, and when it holds, clicks **Ověřeno, přidat
zdroj**. That click is the person's write: a Client Knowledge item of kind `SOURCE`, knowledge at
once (CLAUDE.md, Client Knowledge; ADR 0019 decision 3), through `ClientKnowledgeRepository.add`.

- **Route.** `POST /api/v1/studies/{study_id}/deep-research/runs/{run_id}/sources/{source_ref}/knowledge`
  with `{evidence_id}`. The run is found through the Study, its sealed bundle read and verified,
  and the snapshot (`source_ref`) and the accepted finding citing it (`evidence_id`) must both be
  in it. Nothing the browser sends becomes the item's URL, title or quote: they are the bundle's.
- **What the item carries.** `content`: the URL, the final URL, the title, the quoted passage, the
  snapshot id, the snapshot's text SHA-256, when it was retrieved. `provenance`: the Deep Research
  run, the finding, the snapshot, the person, `verified_by_person: true`.
- **Once per (client, URL).** The client's row is locked, an active `SOURCE` item or a pending
  proposal with the same URL answers `exists` (200) with its id, and nothing is written. The button
  then reads "Už je ve znalostech" and links to the item.
- **Permission.** The Study's `EDIT_STUDY` to read the run, the client's propose and approve
  knowledge permissions to write (`add`). Where self-approval is off for the client, `add` files a
  proposal instead, and the answer says `proposed`.
- **No model adds a source.** Nothing in the worker writes knowledge; the route is a person's.

## 2. Auto-accept the Lead's text edits

ADR 0026: the Lead proposes, a person decides. An explicit standing choice by the researcher is
that decision, so the gate stays the default and the choice is theirs alone.

- `researcher_leads.auto_accept_text_edits` (default false); `PUT /api/v1/lead/preferences`
  sets the caller's own row, audited; `GET /api/v1/lead` carries it.
- **Text edits** are exactly `set_text`, `question_edit` with `text` and no `options`, and
  `list_replace`: wording, never structure or the sample (`domain/research_lead.py`
  `TEXT_EDIT_OPS`, `is_text_edit`).
- Applying stays on the server gate. When a turn completes with the preference on, the web pane
  calls `POST …/lead/turns/{turn_id}/edits` with `decision: "accept"`, the text-edit indices, the
  working revision and `auto: true`. The server refuses `auto` unless the caller's preference is
  on (`auto_accept_off`), refuses any non-text edit in it by index (`not_a_text_edit`), and writes
  `"auto": true` into each ledger row's comment. Structural edits wait as change blocks.
- **Vrátit.** The browser keeps, for the edits it auto-accepted on this page, the wording each
  replaced; Vrátit writes that wording back as the person's own edit of the working copy (the
  normal revision-checked save), and refuses when the text has changed since. The ledger's
  accept stays: decisions are made once, and the revert is a later edit by the person.

## Findings

None yet.

## Doc follow-up

Written in the PR description.
