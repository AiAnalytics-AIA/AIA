# status.json schema

All strings are plain text (the renderer escapes them). Unknown values: `null`, never a guess.

```
{
  "generated_at": "2026-10-20T18:40:00Z",        // ISO 8601 UTC
  "develop_sha": "7878bad7",                      // short sha of origin/develop
  "headline": "one sentence",
  "needs_nigel": [{
    "id": "N1",                                   // referenced by unblocks / blocked_by / after
    "title": "short imperative",
    "why": "why only Nigel can do it",
    "example": "a worked example of the answer or action",
    "recommendation": "the recommended option and why",
    "unblocks": ["step or session ids"],          // ranking key: more = higher
    "where": "session id, title or URL where he acts"
  }],
  "sessions": [{
    "id": "session_...",
    "title": "AIA infra audit",
    "category": "Planning | Scope inputs | Infra | Security/CI | Docs | Design | PM",
    "state": "working | waiting-on-nigel | waiting-on-review | waiting-on-other-session | done | blocked",
    "doing": "one sentence",
    "plan": {"path": ".planning/plans/x.md", "chunk": "current chunk text", "done": 2, "total": 5},  // or null
    "prs": [{"num": 519, "title": "...", "state": "open | draft | merged | closed", "ci": "green | red | pending | none"}],
    "needs": "what it needs from Nigel, or null",
    "blocked_by": ["ids of needs_nigel items, sessions or steps"],
    "next": "next step",
    "context_pct": 42,                            // number or null; amber >= 60, red >= 70
    "last_update": "2026-10-20T18:31:00Z",
    "reply": "received | no reply",
    "explainers": [{                              // optional; embedded in the card
      "title": "How the freeze check works",
      "function": "tools/master_check.py:check_register",
      "html": "<!doctype html>...",               // self-contained, < 40 KB; build_status.py loads it from
                                                  // explainers/<session-id>/<slug>.html
      "height": 360,                              // optional, px (160-900; default 360)
      "source_url": null                          // optional; only when present, an "Open full size" link
    }]
  }],
  "workstreams": [{
    "id": "domain",
    "title": "Domain move",
    "steps": [{"id": "d1", "title": "...", "status": "done | active | waiting | blocked | todo",
               "owner": "who", "depends_on": ["step ids, any workstream"]}]   // steps listed in order
  }],
  "next_actions": [{"id": "A1", "who": "Nigel | session title", "what": "...", "after": ["ids"]}],  // ordered
  "recent": [{"when": "2026-10-20T18:25:00Z", "what": "..."}],                // last 24 h
  "questions": [{                                 // open decisions, answered on the page (questions.py Q)
    "id": "Q1",                                   // also the db doc id: letters, digits, _ - . ~ : @ +
    "title": "...", "context": "...", "example": "a practical example",
    "options": [{"key": "a", "label": "...", "detail": "..."}],
    "rec": "a",                                   // key of the recommended option
    "rationale": "why we recommend it",
    "unblocks": ["ids or plain labels"], "where": "Answer here"
  }],
  "decided": [{"id": "Q1", "title": "...", "choice": "a", "choice_label": "...", "note": "...",
               "at": "2026-10-20T19:40:00Z"}]     // retired questions, shown compactly
}
```

## What the page writes (the artifact's `db`)

Published with `capabilities: {"db": {}, "user": {}}` (default rules: Contributors and up write).

- `answers/<question id>`: `{choice, option_label, note, at (ISO), title, by?}` -- `by` is the viewer's
  opaque `user.id()`, present only when the user capability gives one. One doc per question,
  last write wins (a "Change" overwrites it).
- `actions/<needs_nigel id>`: `{done: true|false, at, title, by?}` -- the "I've done this" toggle.

Explainers are embedded as `<iframe sandbox="allow-scripts" srcdoc=...>` (no allow-same-origin), so
their code cannot reach the page or its db. There is one artifact only: explainers have no artifact of
their own. Untested against claude.ai's live CSP: if a published page shows them blank, say so to Nigel;
the card falls back to a link only when `source_url` is present.

`category` may also be given as `role`. Ids are free-form but unique across `needs_nigel`, workstream
steps and `next_actions`, so any `unblocks` / `depends_on` / `after` / `blocked_by` entry resolves; the
renderer shows an unresolved id as a plain chip.