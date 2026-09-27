# RunTimeline

Honest progress: real elapsed time, heartbeat, real counts, the current step and what it waits on.

**The consumer provides:** `status` (WorkflowRunStatus), `runId`, `elapsed` (seconds), `heartbeat` (seconds since last), `waitingOn`, `steps` [`{name, status, elapsed?, attempt?, detail?}`].

**Use:** Use it on stage pages and in the run log.

**Don't:** No percentages, spinners, shimmer or estimated completion. If the heartbeat is stale, show its age; do not hide it.
