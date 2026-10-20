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
    "reply": "received | no reply"
  }],
  "workstreams": [{
    "id": "domain",
    "title": "Domain move",
    "steps": [{"id": "d1", "title": "...", "status": "done | active | waiting | blocked | todo",
               "owner": "who", "depends_on": ["step ids, any workstream"]}]   // steps listed in order
  }],
  "next_actions": [{"id": "A1", "who": "Nigel | session title", "what": "...", "after": ["ids"]}],  // ordered
  "recent": [{"when": "2026-10-20T18:25:00Z", "what": "..."}]                 // last 24 h
}
```

`category` may also be given as `role`. Ids are free-form but unique across `needs_nigel`, workstream
steps and `next_actions`, so any `unblocks` / `depends_on` / `after` / `blocked_by` entry resolves; the
renderer shows an unresolved id as a plain chip.
