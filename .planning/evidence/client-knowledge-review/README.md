# Client knowledge audit reproductions

Audited source: develop `67af44e5b9431d6293347b581fde7a34b95ed44c`, 2026-10-08.
Publication base: `4d8f07d934e88a9d15b9da47c78c42a1b01ca019`, which adds PR 194's
documentation follow-ups and changes no runtime code.

Both observed-gap probes passed: 2 tests, zero failures/errors/skips.

1. Create an item, propose an edit, accept a newer human correction, then accept the earlier
   proposal. The earlier content becomes current at revision 3; all three revisions remain.
2. Accept a DIMENSION by title only. Study retrieval returns it with an empty definition payload.

The probe asserts current behavior, not desired regression expectations. Implementation tests
must assert the reviewed target behavior instead. It is audit evidence under `.planning/`,
not part of the application's test suite. It uses existing fictional scope/session fixtures.

## Reproduce in a disposable checkout

Start a scratch checkout at either source SHA above. Copy the probe into its core tests directory
to use that checkout's existing conftest fixtures, then run it:

```sh
cp .planning/evidence/client-knowledge-review/test_client_knowledge_review_probe.py \
  packages/aia_core/tests/test_client_knowledge_review_probe.py
DATABASE_URL='' python -m pytest -q packages/aia_core/tests/test_client_knowledge_review_probe.py
```

At the audited SHA, the new `.planning/` evidence directory is not yet present; copy the probe
from this publication branch into the scratch checkout first. Never commit the copied probe
as a desired behavior test. If the gap has been fixed on a later commit, these observations
may no longer hold, which is the reason the source SHA is recorded.

Recorded environment: Python 3.12.14, isolated runtime with declared development extras,
SQLite, explicit PYTHONPATH selecting the scratch checkout's core/API/worker/executor sources.
No model, source or network calls. JUnit is `reproductions.xml`; the original host identifier
was removed before publication, preserving the testcase results and timings.

This is scoped code evidence, not browser, PostgreSQL contention or deployed acceptance.
The proposal, exact anchors and target behavior are in
[client-knowledge-lifecycle.md](../../plans/client-knowledge-lifecycle.md).
Documents/notes, datasets and web research are all required by the user's confirmed scope.
The publication changes plans/evidence only, with no production change or migration.
