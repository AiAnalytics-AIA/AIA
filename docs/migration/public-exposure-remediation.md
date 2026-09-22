# Public exposure of reference material — findings and remediation

**Status:** proposal. The current-tree removals and the CI guard are implemented
in this change. **No history has been rewritten**, and none will be without
explicit human approval.

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

### Recommendation

**Rotate the assumption, not the history — unless the data owner confirms these
are real client names under a confidentiality obligation.** If they do, rewrite,
and accept the costs in §5. The reasoning:

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
  settled.

### Procedure, if approved

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
  `file:line @ SHA` in `.planning/PROGRESS.md`, `docs/migration/status.md` and
  the ADRs becomes dangling and must be re-pointed.
- **Open PRs may show as fully rewritten**, losing inline review threads.
- **Forks are unaffected and keep the content.** A fork cannot be rewritten by
  this organization.

**Recommended order regardless of the rewrite decision:** land the current-tree
removal first. It is cheap, reversible and stops further exposure, and it does
not foreclose a rewrite later.

## 6. Proposed sequencing

1. **Now** — this change: delete the package, delete `.agent-status/`, add the
   blocking CI guard, point the docs at the private reference repository.
2. **Data owner** — classify the ambiguous tokens in §2. Are `NOVA`, `STREAMIO`,
   `AURORA`, `NEXORA`, `RAILMOVE`, `MESTO`, `VOLBA` real clients or demo brands?
   Everything downstream depends on this answer.
3. **After PR #7 merges** — reduce `reference-manifest.json` per §3, with the
   matching `scan()` exclusion, and extend the guard's token list to whatever
   step 2 confirms.
4. **Human decision** — private repository, history rewrite, or accept, informed
   by §4.

## 7. What the guard enforces

`tools/exposure_check.sh`, blocking in CI and in `make check`:

| Rule | Prevents |
| --- | --- |
| No detailed reference inventories | `reference-file-inventory*`, `reference-snapshot*`, any `aia-reference-rebuild-package/` |
| No raw reference assets | `.zip`, `.7z`, `.sqlite`, `.db`, `.parquet`, `.csv.gz`, `npc-panel*` |
| No client-identifying filenames | The confidently-identifying token list, with exceptions named explicitly |
| No client-identifying names in contents | The same tokens inside committed files |
| No `.agent-status/` | Agent coordination state reaching product history |

It checks the working tree, which is what a PR adds. **It cannot scrub history**,
and nothing in this change pretends otherwise.
