# Deep Research fan-out — tracks across workers, polite hosts, bounded model calls

**State:** built on recorded doubles, off by default (`AIA_DEEP_RESEARCH_FAN_OUT`). Plan
[`deep-research-web-search.md`](../../.planning/plans/deep-research-web-search.md) chunk 21:
*"Tracks run concurrently across worker processes; a per-host politeness scheduler shared by
every fetcher in a run; a model concurrency limiter below the account's quota. Tests: 50 tracks
never exceed either limit; every interrupted track recovers."* The parent contract is
[deep-research.md](deep-research.md); the queue is [ADR 0002](adr/0002-postgresql-authoritative-store.md)
(PostgreSQL is the only shared state: no Redis, no SQS).

## 1. What changes, and what does not

Off (the default), nothing changes: the `investigate` step researches every track one after
another in one attempt, byte for byte as before. On, the same tracks are researched by the same
code, each in a step of its own that any worker may claim, and two shared limits bound what all
those workers do together. Fan-out changes **how** a run is executed, never **what** it finds:

* no fingerprint, version, plan or artifact shape depends on the switch, so a run planned with it
  off may be investigated with it on and the other way round, and a later pass reuses tracks
  stored either way;
* every guarantee a track had is the one it keeps: the tool journal read back before anything is
  sent again, `UNCERTAIN` for a call left in flight, stored turn answers replayed instead of
  re-bought, one reservation per logical model request, `RECOVERY_REQUIRED` for a paid call whose
  outcome is unknown;
* the run-level snapshot cache (chunk 5: a URL captured once in a run is not fetched again) spans
  the run's track steps, not one process.

## 2. Tracks as child steps: hand out, wait, join

**The engine** gains one outcome. An executor may return
`Deferred(children=(ChildStep, ...))` (`aia_worker.executor`): the worker records it with
`WorkflowRepository.defer_attempt`, in one transaction —

1. each child becomes a step of the same run (`RUNNABLE`, the parent's priority, ordinals after
   every existing step), unless a step with its node key exists: the same work handed out again
   names the same child (`child_node_key(prefix, name)`, stable, cut and hashed to fit 64
   characters);
2. the parent depends on every child (`step_dependencies`), its attempt ends `DEFERRED`
   (a new `AttemptStatus`, terminal, holding no lease) and its holds are closed by the one closing
   rule (spend known so far is charged, idle holds are released);
3. the parent is `BLOCKED`; `release_ready_steps` makes it `RUNNABLE` again when every child has
   `SUCCEEDED` — at once when they already have.

`decide_deferral` (domain) is the rule: waiting is not failing, so the attempt is not counted
against `max_attempts` (a lead-planned run waits once per wave); a paid call in flight with no
known outcome makes the parent `RECOVERY_REQUIRED` and starts no child, exactly as a crash at that
moment would; a cancellation that arrived meanwhile cancels the parent and adds nothing. A child
that fails stalls the parent and the run reads `FAILED` or `RECOVERY_REQUIRED` from it, as a
failed upstream step would — the same outcome the sequential step had, since a track that raised
failed the whole `investigate` step. A failed run is claimed no further.

**Deep Research** uses it in `investigate` (the *join*):

| The join finds | It does |
| --- | --- |
| a planned track stored (by fingerprint, or this run's own key) | takes it, as before |
| a planned track a gate blocked, or with no plan or retrieval | records it inline: no call is made |
| planned tracks that would make calls (internal, or web with a plan) and are not stored | hands each out as a child `deep_research_investigate_track` step (node key `investigate/<track id>`, payload: the track, fingerprint: the track's) and defers |
| a lead-planned run, wave *n* | its tasks' tracks the same way, wave by wave: hand out the wave's unstored tracks, defer; on the next attempt the wave is stored, the re-plan is asked (or replayed from its stored record) and the next wave handed out |

The **child** (`InvestigateTrackExecutor`) reads the run's plan through the run, re-checks the
composition and that the track is the plan's (or, for a lead task, that its subject is the run's
and the run is lead-planned), builds its own `StepToolMeter.resuming`, `RetrievalGate` and
`StepModelCaller`, and runs the one track with the same `_track` the sequential step uses; the
artifact it stores is the one the join then finds. Its tool journal, model reservations,
checkpoints and recovery are its own step's: a killed child is recovered by the reconciler like
any step, and its next attempt adopts what the dead one journaled (`_earlier_tool_entries` reads
this step's entries only) — a fetch left in flight is closed `UNCERTAIN` and the track ends
`INCOMPLETE` without sending it again; stored turn answers replay without a call.

Why child steps, not a claim table of tracks inside one step: the queue, leases, heartbeats,
fencing, reservations, recovery and the operator's view of a run already exist per step. A second
lease mechanism for "a track inside a step" would duplicate every one of them and the paid-call
rules (#154) with it. A step per track gets them all, and an operator sees each track's state.

**The run-level cache across children.** In agent-directed mode a kept page is also indexed in
the store (`deep_research_url_capture`, run-scoped by its canonical URL, naming the snapshot's
content address); a child asking for a URL the run already captured gets a `CACHED` answer that
sends nothing. Two children that ask for the same URL at the same instant may both send it: the
index is not a lock, and a duplicate capture of a public page is harmless (it dedupes by content
address). The planned mode has no cache, as before.

## 3. Per-host politeness shared by every fetcher

`HostPacer` (`infrastructure/web_retrieval.py`) is the seam: `turn(host, interval_s)` holds the
host for one request and returns once the host is free and its interval has passed since the
end of the previous request to it. Two implementations:

* `LocalHostPacer` — the in-process rule chunk 5 shipped, moved out of `PublicHttpsTransport`
  unchanged (the transport's default; its tests pass unedited).
* `SharedHostPacer` (`infrastructure/fan_out_coordination.py`) — one row per host in
  `deep_research_host_slots` (`next_allowed_at`, `holder_token`, `held_until`). A turn is a short
  transaction: lock the row (`FOR UPDATE` on PostgreSQL; a conditional `UPDATE` checked by
  `rowcount` on both engines), and either take it (holder set, `held_until = now + hold`) or learn
  how long to wait; the request is sent outside any transaction; the release sets
  `next_allowed_at = end + interval` and clears the holder. One request at a time per host, and the
  interval measured from the end of the last request — chunk 5's rule — across every process.

**Keyed by host, not by (run, host).** A site's crawl delay and our minimum interval are owed by
AIA's user agent, which every run shares: two runs keyed apart would together request a host
twice as often as its robots.txt allows. One row per host makes the whole deployment one polite
client. The cost is that a second run waits behind the first on a host both use; that is the
politeness, not a defect. Rows are host names and instants only — no run, study or client — and
rows idle for a day are pruned when a turn is taken.

**Bounded.** A turn waits at most `max_wait_s` (60 s: twice the longest crawl delay a transport
accepts, `max_crawl_delay_s` = 30 s); beyond it the request is refused before anything is sent
(`FetchRefused`, `host_wait_exceeded`), journaled as a failed fetch that sent nothing. A process
that dies holding a host leaves `held_until` (120 s, above the transport's connect and read
timeouts) to lapse. `robots.txt` requests are paced by the same turn. Wait and hold are measured
on each process's UTC clock; on develop every worker runs on one host.

`PublicHttpsTransport(pacer=...)` takes either; `PacedTransport(inner, pacer, interval_s)` wraps
any other `FetchTransport` (the pinned Wikipedia route, a recorded transport in the tests). The
fan-out composition gives every transport it builds the shared pacer.

## 4. Model calls below the account's quota

`ModelSlots` (`infrastructure/fan_out_coordination.py`) is a counting semaphore in PostgreSQL:
`deep_research_model_slots`, one row per `(pool, slot)` for slots `0 … limit-1`, each free or held
by `(holder_attempt_id, holder_token)`. `StepModelCaller(limiter=...)` holds one slot around each
logical request — the reservation, the call, its one schema repair and the settlement — so a
request waiting for a slot holds no budget.

* **Acquire** scans the pool's slots below the limit (`FOR UPDATE SKIP LOCKED` on PostgreSQL) and
  takes the first free one with a conditional `UPDATE` (`rowcount` = 1). A slot is free when it has
  no holder **or its holder attempt no longer holds its lease** (status not `CLAIMED`/`EXECUTING`,
  or `lease_until` passed): a slot expires with the lease of the attempt that took it, so a killed
  worker's slots come back when the reconciler could recover its step, with no heartbeat of their
  own. This is the one read here of `step_attempts` across studies, and it reads only liveness.
* **Release** clears the slot if the token is still the caller's.
* **Waiting** polls (`poll_s`), checkpointing between polls (a cancelled or stopping step stops
  waiting); past `max_wait_s` (120 s) the request fails `PROVIDER_CAPACITY` before anything is
  reserved, and the step parks `WAITING_CAPACITY` (no attempt consumed) and is resumed by the
  sweep. Lowering the limit takes effect at once: slots at or above it are never taken.

**The limit is configured, never guessed.** `AIA_DEEP_RESEARCH_MODEL_CONCURRENCY` is required when
fan-out is on (the worker refuses to start without it). It must sit below the account's Bedrock
quota for the route's model; chunk 1's quota request decides it. **Proposed (pending that
request): 4.** The pool is the route (`bedrock:<AIA_AI_ROUTE_ID>`), so every worker calling one
route shares one limit.

**Triage reuses the seam.** `deep_research_triage.ConcurrencyLimiter` is the async shape of the
same bound; `SharedSlotLimiter` adapts `ModelSlots` to it (acquire and release on a thread, never
on the event loop), and `CombinedLimiter` puts the run's own `SemaphoreLimiter` in front, so a
triage burst is bounded both per run and across the deployment.

## 5. The switch and the composition

| key | meaning |
| --- | --- |
| `AIA_DEEP_RESEARCH_FAN_OUT` | `true`: tracks as child steps, the shared pacer and the model slots; unset or `false`: one step, as before. Needs `AIA_DEEP_RESEARCH_ENABLED` |
| `AIA_DEEP_RESEARCH_MODEL_CONCURRENCY` | required with fan-out: model requests in flight across every worker on the route (integer 1–256). Proposed 4 |

With fan-out on, the composition builds a small engine of its own from `DATABASE_URL` (the
coordination tables are not study data and are written outside any attempt's fenced
transaction) and passes `FanOutCoordination(pacer, slots)` in the runtime. Off, nothing reads
either table. The `deep_research_investigate_track` kind is registered in every composition, so a
worker deployed with the switch off still finishes children a fanned-out join handed out.

## 6. Measured

See the commit that adds the measurement (`apps/executors/tests/test_deep_research_fan_out.py`
records the method). In-process, recorded doubles with injected latency, PostgreSQL 16 on the
development machine:

(filled in by the measurement commit)

## 7. What this does not do

* **Model concurrency inside a track.** A track's own requests are still one at a time; the
  investigator's up-to-five tool actions per turn were already concurrent (chunk 9).
* **A lock on the URL index.** Two tracks asking for one URL at one instant may both fetch it.
* **Clock-independent pacing.** Waits are on each process's clock (one host on develop).
* **Deadlines per step.** A wait is bounded by its own maximum; a step has no deadline to hand it.
