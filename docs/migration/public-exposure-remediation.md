# Public exposure of reference material — findings and remediation

## Decision D5 — RESOLVED, 2026-09-22

**`AiAnalytics-AIA/AIA` must not remain public. It is to be made PRIVATE.**
Frozen product/security decision, taken by the data owner, on these grounds:

- legacy and reference filenames already expose real client and company
  associations;
- the repository contains reference-derived inventory material;
- the production codebase is not intended for public distribution;
- future architecture, client configuration and migration metadata must not be
  publicly visible.

**History is NOT to be rewritten.** Making the repository private lowers the
urgency of a rewrite to the point where preserving history is the better trade.
Existing commits stay unless a later legal or data-owner review determines they
must be expunged. §4 below is retained as the costed procedure **should that
review ever call for it** — it is no longer the recommendation.

**The cleanup is still required.** Private is not a substitute for any of it:
remove `aia-reference-rebuild-package/`, remove `.agent-status/` from `main`, keep
the exposure guard, and keep detailed reference material only in
`AiAnalytics-AIA/AIA-reference`. Private is a setting somebody can change back,
and it is not need-to-know — every collaborator, CI log and future fork still sees
whatever is committed.

> **APPLIED and verified: the repository is PRIVATE** as of
> **2026-09-22T20:21:38Z**, confirmed against the GitHub API at 20:22:17Z —
> `private: true`, `visibility: private`, `forks_count: 0`.
>
> It was applied by a human, not by this session: the agent proxy refuses
> repository settings writes (`403 Repository settings writes are not permitted
> through this proxy`). Re-verification command is in §8.

**Status of the rest of this document:** the current-tree removals and the
guard are implemented. D4 — which legacy identifiers name real clients — remains
open, and now applies to whether they should remain even in a private repository.

`AiAnalytics-AIA/AIA` is **public**. The legacy NPC Panel reference is client
work, and its *filenames alone* name real companies and engagements. A filename
is disclosure even when the file it names is absent — which is the situation
here: no reference content was committed, but a per-file inventory of it was.

`AiAnalytics-AIA/AIA-reference` is private and is now authoritative for all
detailed legacy interpretation, so the detailed package no longer needs to exist
here at all.

## 1. Exact commits containing the package

| | |
| --- | --- |
| Commit | `c5057ebe3a5884c7d89080a4f6b6fc52f83255c9` |
| Subject | *Establish the reference rebuild package from the one record we still hold* |
| Authored | 2026-09-22T10:53:40+00:00 |
| Reachable from `main` | **yes** |
| Merged to `main` via | PR #5 (`claude/amazing-cerf-1lhmze`) |
| Added | 20 files, 24,081 lines under `aia-reference-rebuild-package/` |

It is the **only** commit that adds or modifies that directory. That matters for
any rewrite: the blast radius is one commit, not a scattered series.

A second, smaller exposure was found while scoping this one:

| | |
| --- | --- |
| Path | `.agent-status/` |
| Commits | `9153c1f`, `d1e9ff3` (both on `main`) |
| Problem | Its own `README.md` states *"This branch is never merged… It is disposable infrastructure, not product history."* It was merged anyway |

## 2. Exact sensitive filename scope

Two of the twenty package files carry client-identifying names; the other
eighteen are prose ledgers and tooling.

| File | Lines carrying client/brand tokens |
| --- | --- |
| `aia-reference-rebuild-package/reference-file-inventory.json` | 896 |
| `aia-reference-rebuild-package/reference-file-inventory.csv` | 413 |

Neither contains file *contents*: the inventory was built in MANIFEST mode and
records `contents not read` against every row. The disclosure is the **name set**
— which engagements exist, and what they were called.

### The tokens

Counted across the 1,324 paths in `docs/migration/reference-manifest.json`:

| Token | Occurrences | Assessment |
| --- | --- | --- |
| `NOVA` | 97 | ambiguous |
| `STREAMIO` | 63 | ambiguous |
| `SPARK` | 63 | ambiguous |
| `MESTO` | 63 | ambiguous (Czech for "city") |
| `VOLBA` | 59 | ambiguous (Czech for "choice") |
| `BANK` | 59 | ambiguous |
| `AURORA` | 59 | ambiguous |
| `MMC` | 38 | **looks like a real company** |
| `GEMO` | 34 | **a real Czech company** |
| `TARIFF` / `REBRAND` / `RAILMOVE` / `NEXORA` | 33 each | ambiguous |

**Which of these name real clients is a data-owner decision, not an engineering
one.** `GEMO` is named in the reference tag and archive filename as a delivered
patch, so it is a real engagement. The rest are consistent with either real
clients or fictional demo brands, and this document deliberately does not guess.
The CI guard ships with the confidently-identifying subset and a comment saying
the data owner maintains the list.

### The exposure is not confined to the package

`docs/migration/reference-manifest.json` is on `main` already and carries the
same path set:

| | |
| --- | --- |
| Manifest paths matching any brand token | **446 of 1,324** |
| …under `demo_library/` | **431 (97%)** |
| …at the repository root | 8 |
| …under `_npc_update_backup/` | 5 |
| …under `docs/` | 2 |

**Removing `aia-reference-rebuild-package/` alone therefore does not remove the
client-identifying filenames from this repository.** That is the most important
finding here, and it is not in the original brief.

## 3. Is current-tree removal operationally sufficient?

**For stopping the bleeding: yes.** Nothing in product code, CI or tests imports
or reads `aia-reference-rebuild-package/` — verified by search. It can be deleted
with no functional consequence, and this change deletes it.

**For the disclosure already made: no**, on two counts.

1. The commit remains in public history and is fetchable by anyone who has, or
   makes, a clone or fork.
2. `docs/migration/reference-manifest.json` still carries 446 of the same names
   in the current tree, so even a perfect history rewrite of the package commit
   would leave the majority of the exposure in place.

### Proposed manifest reduction — not implemented here

The manifest can be reduced to a small non-sensitive artifact that still serves
CI, because the sensitive paths and the paths CI needs barely overlap:

| Consumer | Needs | Affected by excluding `demo_library/` + `_npc_update_backup/`? |
| --- | --- | --- |
| `test_module_inventory.py` | migration modules | **No.** It already excludes `demo_library` as non-migration surface |
| `test_sociomap_parity.py` | hashes for 4 root modules | **No.** All four are at the repository root |
| `reference_manifest.py verify` | tree ↔ manifest comparison | Only if `scan()` gets the same exclusion, which is a two-line change |

Excluding those two directories removes **436 of the 446** matches while leaving
every current consumer working. The residual 10 — mostly root-level
`GEMO_REPUTACNI_SCENARE_*` and `MMC_GEMO_FIX_*` artifacts — need the data owner's
classification before anyone decides whether to drop, keep or hash-only them.

This is **not** done in this change for two reasons: it would collide with PR #7,
which is still open against the same file, and the residual set needs a decision
this repository cannot make. Recommended sequencing is in §6.

## 4. History rewrite — procedure, if the human chooses it

**Not performed. Not recommended as a first step.** Recorded so the decision can
be made on facts.

### Recommendation — superseded by D5

**Retained for the record. The data owner has since chosen to make the repository
private and to preserve history**, which is the outcome this section argued for
over a rewrite. Do not read what follows as an open question.

The original reasoning, which D5 accepted:

- The content disclosed is a *file-name inventory*, not client data, credentials
  or research output. Nothing here is a secret that can be rotated, which is the
  usual argument for urgency.
- The repository is public and may already have been cloned, forked, or indexed
  by third-party mirrors and code-search services. **A rewrite cannot retract
  what has been fetched**, and cannot touch a fork. It reduces future exposure,
  it does not undo past exposure.
- Making the repository **private** — if that is acceptable — removes the
  exposure immediately and completely for anything not already copied, at a far
  lower cost than a rewrite, and can be done while the classification question is
  settled. **This is the option that was chosen.**

### Procedure, if a later review ever requires a rewrite

Requires: every open PR merged or closed, every collaborator notified, and a
maintenance window in which nobody pushes.

```bash
# 0. A full mirror backup, kept offline until the rewrite is confirmed good.
git clone --mirror https://github.com/AiAnalytics-AIA/AIA.git AIA-backup.git

# 1. Rewrite with git-filter-repo (NOT filter-branch, which is slow and
#    error-prone, and NOT BFG if paths need regex matching).
pip install git-filter-repo
git clone --mirror https://github.com/AiAnalytics-AIA/AIA.git AIA-rewrite.git
cd AIA-rewrite.git
git filter-repo --invert-paths \
    --path aia-reference-rebuild-package/ \
    --path .agent-status/

# 2. If the manifest is also to be scrubbed, it must be REWRITTEN rather than
#    removed -- it is a live CI dependency. Use --blob-callback, and regenerate
#    from the archive afterwards so the tip is correct and complete.

# 3. Verify BEFORE pushing: the paths are gone from every commit, the tip tree
#    is byte-identical to the intended state, and the suite passes on it.
git log --all --oneline -- aia-reference-rebuild-package .agent-status   # empty
git log --oneline | head

# 4. Push. Requires branch protection temporarily lifted on main.
git push --force --mirror

# 5. Ask GitHub Support to expunge stale refs and cached views; a force-push
#    does not remove commits still reachable from pull-request refs
#    (refs/pull/*), which remain readable through the API.

# 6. Every collaborator re-clones. A pull onto an old clone reintroduces the
#    removed commits.
```

**Step 5 is the one people forget.** GitHub retains PR head commits under
`refs/pull/*` independently of branches; a mirror force-push does not delete
them, and they stay fetchable until GitHub garbage-collects them on request.

## 5. Consequences for open branches, PRs and tags

Measured at the time of writing.

| Ref | Contains `c5057eb` | Consequence of a rewrite |
| --- | --- | --- |
| `main` | yes | Rewritten; every clone must be re-cloned |
| `migration/reference-repository-link` (PR #7) | yes | Rebased or recreated; PR likely must be reopened |
| `fix/spent-usd-lost-update` (PR #8) | yes | Same |
| `coordination/agent-status` | separate lineage | Unaffected, but it is the branch `.agent-status` belongs on |
| `claude/amazing-cerf-1lhmze` | yes | Stale; delete or recreate |
| Tags | none exist in this repository | No impact |

Additional consequences:

- **Every commit SHA after the rewrite point changes.** Every anchor of the form
  `file:line @ SHA` in `.planning/overview.md`, `docs/migration/status.md` and
  the ADRs becomes dangling and must be re-pointed.
- **Open PRs may show as fully rewritten**, losing inline review threads.
- **Forks are unaffected and keep the content.** A fork cannot be rewritten by
  this organization.

**Order under D5:** make the repository private first, then land the current-tree
removal. Both are cheap and reversible, and neither forecloses a rewrite if a
later legal or data-owner review requires one.

## 6. Sequencing under D5

1. **Blocking, human** — set visibility to private, and verify it per §8. Nothing
   below depends on it, but the exposure stays open until it is done.
2. **Now** — this change: delete the package, delete `.agent-status/`, add the
   blocking CI guard, point the docs at the private reference repository.
3. **Data owner (D4)** — classify the ambiguous tokens in §2. Are `NOVA`,
   `STREAMIO`, `AURORA`, `NEXORA`, `RAILMOVE`, `MESTO`, `VOLBA` real clients or
   demo brands? Now also: should the confirmed ones remain even in a private
   repository? Everything downstream depends on this answer.
4. **After PR #7 merges** — reduce `reference-manifest.json` per §3, with the
   matching `scan()` exclusion, and extend the guard's token list to whatever
   step 3 confirms.
5. **Not scheduled** — history rewrite. Preserved unless a legal or data-owner
   review requires expunging commits.

## 7. What the guard enforces

`tools/exposure_check.sh`, blocking in CI and in `make check`:

| Rule | Prevents |
| --- | --- |
| No detailed reference inventories | `reference-file-inventory*`, `reference-snapshot*`, any `aia-reference-rebuild-package/` |
| No raw reference assets by shape | `.zip`, `.7z`, `.sqlite`, `.db`, `.parquet`, `.csv.gz`, `npc-panel*` |
| **No file whose contents are a reference file** | Any of the 1,324 manifest files, **committed under any name**, matched by SHA256 |
| **No uncompressed reference datasets** | `.csv`/`.json`/`.tsv` named for population, panel, calibration, donor, respondent, segment, registry, targets, weights, census, PIAAC or ISSP |
| No client-identifying filenames | The token list, **case-insensitively**, with exceptions named per file |
| No client-identifying names in contents | The same tokens inside committed files, **including test trees** |
| No `.agent-status/` | Agent coordination state reaching product history |

Four of these exist because a review of the first version demonstrated the
bypasses: an uncompressed dataset under its original generic name, client
material under `packages/**/tests/`, and a lowercase `gemo`. Each was reproduced
against the guard, which reported 5/5 passing, before being closed.

The hash rule is the load-bearing one. It does not guess from names: the manifest
records the SHA256 of every canonical reference file, so a tracked file hashing to
one of them **is** that file, whatever it was renamed to. Matching by *path* was
rejected — `README.md` and `pyproject.toml` exist in both trees, so a path rule
would flag this repository's own files while content matching cannot.

It checks the working tree, which is what a PR adds. **It cannot scrub history**,
and nothing in this change pretends otherwise.

The guard survives D5 deliberately. Private is a setting that can be changed
back, and a control removed because it looked unnecessary is not there when it
becomes necessary again.

## 8. Public surface at the moment of the decision

Captured from the GitHub API at **2026-09-22T20:17:03Z**, immediately before the
visibility change was attempted:

| Surface | State | Consequence |
| --- | --- | --- |
| Forks | **0** | Nothing to chase. A fork would have kept the content regardless of visibility |
| Network / subscribers | **0** / **0** | No downstream copies via GitHub |
| Stars / watchers | **0** / **0** | No signal that anyone found it |
| Releases | **0** | No published assets |
| Tags | **0** | No downloadable archives |
| GitHub Pages | `has_pages: false` | No site served from the repository |
| Downloads | `has_downloads: false` | — |
| Repository created | 2026-02-11T12:59:18Z | Public window: ~7 months |

**This is the best case available.** Nobody forked, starred or watched it, and no
release or Pages site distributed anything. What cannot be ruled out is anonymous
cloning and third-party indexing by code-search crawlers, which leave no trace in
the API. That residual is the reason the cleanup proceeds anyway.

### Verifying the visibility change

```bash
gh api repos/AiAnalytics-AIA/AIA --jq '{visibility, private, forks_count}'
# {"visibility":"private","private":true,"forks_count":0}   ← confirmed 2026-09-22T20:22:17Z
```

**Applied 2026-09-22T20:21:38Z** (the repository's `updated_at` at the moment the
setting changed). It was performed by a human: the agent proxy in this
environment refuses repository settings writes, so no agent session can make or
revert it. If it ever needs reapplying:

**Settings → General → Danger Zone → Change repository visibility → Make private**

The two surfaces named above closed with it. The `openapi` workflow artifacts and
the workflow logs are now readable only by people with repository access.

**What going private did not do.** It does not retract the ~7 months of public
availability. Anonymous clones and third-party code-search indexing leave no API
trace, so the residual cannot be measured — only bounded by the zero forks, stars
and watchers recorded above. That residual is why the cleanup in this document
proceeds regardless, and why D4 still matters.
