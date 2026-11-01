# The AIA Build Map

One page for the MVP build: every plan by page and enabler, its progress, how the plans reference each other, the
research stages' inputs and outputs, the build sequence by wave, what must be switched on, and the open questions.
It is published as a claude.ai artifact; this directory is what builds it.

```bash
git fetch origin develop && git worktree add --detach /tmp/bm-develop origin/develop
python3 tools/build_map/build.py /tmp/bm-develop /tmp/build-map.html
```

Then publish `/tmp/build-map.html` to the Build Map's artifact URL, so the link stays the same. Rebuild after every
merge that changes a plan.

## What it reads

**Live, from the develop checkout:**
- every plan's front matter (status and chunks);
- `mvp-master-plan.md` §3 (core / outside / after the MVP) and §4 (the activation matrix);
- `.planning/mvp-execution-contracts.md` (the cross-plan groups, waves and every open chunk's wave);
- every plan's references to other plans;
- the open PRs, through `gh api` (shown as unknown without it).

**Hand-kept, beside the script:**

| File | Holds | Update when |
|---|---|---|
| `curated.json` | Categories (epics), which plan sits in which, stage purposes, the board's queue, proposed chunks, the open questions, the agile mapping | A plan is added, a question is answered or asked, the queue moves |
| `develop_state.json` | Develop's state from the infra audit: each switch and resource, MATCH / PARTIAL / MISSING, with evidence | A new audit, or a switch is thrown |
| `stagemap.json` | Each research stage's hand-offs, what is built and the backend and frontend gaps, at its develop sha | The stages are mapped again |
| `page.tpl.html` | The page; `build.py` puts the data where `/*__DATA__*/null` stands | The layout changes |

The script exits naming any open plan that `curated.json` does not place in a category, so a new plan cannot go
missing from the map.
