---
status: done
chunks:
  - "[x] 1. Add protected pre-deployment image retention and disk gates"
  - "[x] 2. Verify safety, rollback history and refusal paths"
  - "[x] 3. Integrate, deploy and verify on the live host"
---
# Prevent the develop host filling with release images

User authorizes automatic retention before deployments, protection of container-used/current/recent rollback images, a disk check before downloads, and preservation of CloudWatch alerting. Incident: 258 obsolete tagged images consumed the 77 GiB root volume; approved cleanup reduced usage from 100% to 56%. The existing `docker image prune` removed only dangling images and ran after the pull, so it could not prevent this failure.

Policy: remove only full-SHA tagged api/worker/web images in this deployment's registry, older than 48 hours, unused by any container. Preserve incoming/current SHA and the four latest distinct successful releases (current plus three rollback releases), recorded atomically only after smoke succeeds. Protect abbreviated operator SHA prefixes conservatively. Unknown/shared/untagged/reference images stay. No force deletion, containers, volumes, backups, registry images or research files are removed. Inventory/history errors refuse cleanup. The deploy's host lock serializes manual and CI deployments.

After cleanup, check root, Docker storage, containerd storage and deployment filesystems: at least 8 GiB available and usage at or below 85%, before ECR login/pull, backup, migration or replacement. CloudWatch alarm configuration stays in force. Dry-run is the standalone default; deploy explicitly applies the authorized policy. No disk resize or new recurring Codex automation.

Validation: selection safety, corrupt history/inventory, failed image removal, low-space rejection, successful-history retention and failed-smoke history invariants. Executable deploy harness must prove disk refusal never reaches pull/migration/service replacement. Required CI and real host dry-run plus observed live deployment are the release gates. Shared project-map instructions follow in a separate docs PR; the deploy runbook is updated with the code.

Local verification: 46 deployment-focused tests pass, including executable shell → Python → Docker-double orchestration, low-space/removal refusals before ECR pull/migration, protected history, failed-smoke history, shared aliases, conservative history warm-up and default dry-run. Standalone helper passes strict mypy, lint and formatting; shell syntax, 119 layer and 7 exposure rules pass. Full local make verify reached frontend type checking, then npm attempted to fetch missing dependencies in this fresh checkout and was refused by the restricted network; no frontend or domain code changes. Full CI remains required. The existing disk alarm is enabled at 85% and reports OK after the approved cleanup.

Real host dry-run: temporary helper and a temporary ledger of four verified successful deployment receipts; no --apply, zero deletions. Live image inventory parsed and preserved five container-referenced images; root has 34.1 GiB available / 55.4% used. Public live SHA 400fa241 matches the most recent successful deployment. The CloudWatch alarm reports OK with actions still enabled. SSM dry-run receipt af6eb99e-9641-4a4b-b934-ea6cebab1ed7.

## Integrated release verification

PR #347 merged the retention helper and pre-download gates. PR #349 repaired
the pre-existing combined SQLite fixture-import blocker without changing any
scenario or assertion. Full merged-base CI [38302006413](https://github.com/AiAnalytics-AIA/AIA/actions/runs/38302006413)
passed at `78dbae622c8dca4fb69dfbca6074085e9adc4bb8`, including the combined SQLite
suite. The deployment runbook and shared documentation landed in PR #350.

Successful live deployment [38316829545](https://github.com/AiAnalytics-AIA/AIA/actions/runs/38316829545)
at `dbb0c704d61506f137eec682165e863ffc141a23` reported at 2026-10-12 22:31:38 UTC:
`image retention: apply; 6 obsolete images; 5 container-referenced images protected`.
The disk preflight reported 35.0 GiB available / 54.2% used before downloads.
Its final smoke reported all checks passed for that SHA; successful history was
recorded afterward. This verifies automatic cleanup on a real deployment,
in addition to the refusal and selection tests above.

SSM receipt `2e7b49bd-e2fd-4e90-91cd-4d8a2b207921` subsequently confirmed the 77 GiB
root volume at 56% used / 35 GiB free, no deployment lock holder, and the four
retained successful releases `dbb0c704`, `78dbae62`, `400fa241`, `d44e178a`.
The later `33959ec3` workflow failed because another deployment held the lock;
its presence in the public version endpoint is not a successful smoke receipt.
No lock file was deleted and no unverified release was inserted into history.
