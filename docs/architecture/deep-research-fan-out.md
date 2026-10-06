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

`HostPacer` (`infrastructure/host_pacing.py`) is the seam: `turn(host, interval_s)` holds the
host for one request and lets it start once the host is free and its interval has passed since
the end of the previous request to it. Two implementations:

* `LocalHostPacer` — the in-process rule chunk 5 shipped, moved out of `PublicHttpsTransport`
  unchanged (still the transport's default; its tests pass unedited).
* `SharedHostPacer` (`infrastructure/fan_out_coordination.py`) — one row per host in
  `host_politeness` (`next_allowed_at`, `holder_token`, `held_until`). A turn takes the host in a
  short transaction (the row locked `FOR UPDATE` on PostgreSQL; the take itself a conditional
  `UPDATE` checked by `rowcount` on both engines) or learns how long to wait; the request is sent
  outside any transaction; the release sets `next_allowed_at = end + interval` and clears the
  holder. One request at a time per host, the interval measured from the end of the last
  request — chunk 5's rule — across every process.

**Keyed by host, not by (run, host).** A site's crawl delay and our minimum interval are owed by
AIA's user agent, which every run shares: two runs keyed apart would together request a host
twice as often as its robots.txt allows. One row per host makes the deployment one polite client.
The cost is that a run waits behind another on a host both use; that is the politeness, not a
defect. Rows are host names and instants only — no run, study or client — and rows idle for a
day are pruned when a turn is taken.

**Bounded.** While another request holds the host the taker polls, doubling from `poll_s`
(50 ms) to `max_poll_s` (0.5 s); while the host's interval runs it sleeps exactly the remainder.
A turn waits at most `max_wait_s` (60 s: twice the longest crawl delay a transport accepts,
`max_crawl_delay_s` = 30 s); a wait that would pass it is refused at once, before anything is
sent (`FetchRefused`, `host_wait_exceeded`), and the fetch is journaled as a failure that sent
nothing. A process that dies holding a host leaves `held_until` (120 s, above the transport's
connect and read timeouts) to lapse. `robots.txt` requests are paced by the same turn. Instants
are each process's UTC clock; on develop every worker runs on one host.

`PublicHttpsTransport(pacer=...)` takes either pacer; `PacedTransport(inner, pacer, interval_s)`
puts any other `FetchTransport` behind one at a fixed interval. With fan-out on, the composition
paces the Wikipedia route's pinned transport through the shared pacer at the public transport's
minimum interval (1 s; before, one process asked it serially and nothing paced it).

## 4. Model calls below the account's quota

`ModelSlots` (`infrastructure/fan_out_coordination.py`) is a counting semaphore in PostgreSQL:
`model_concurrency_slots`, one row per `(pool, slot)` for slots `0 … limit-1`, each free or held by
`(holder_attempt_id, holder_token)`. `StepModelCaller(limiter=...)` holds one slot around each
logical request — the reservation, the call, its one schema repair and the settlement — taken
before the reservation, so a request waiting for a slot holds no budget.

* **Acquire** reads the pool's slots below the limit, unlocked, and claims the first free one with
  a conditional `UPDATE` (`rowcount` = 1). Two takers of one row queue on it for one short commit;
  the second's `WHERE`, re-evaluated against the committed row, sends it to the next slot. (The
  first version locked the scan `FOR UPDATE SKIP LOCKED`, so one taker held every row of the pool
  and every other taker found none and slept a poll.) A slot is free when it has no holder **or
  its holder attempt no longer holds its lease** (status not `CLAIMED`/`EXECUTING`, or
  `lease_until` passed): a slot expires with the lease of the attempt that took it, so a killed
  worker's slots come back when the reconciler could recover its step, with no heartbeat of their
  own. This is the one read here of `step_attempts` across studies, and it reads only liveness.
  One attempt may hold several slots (a triage burst).
* **Release** clears the slot if the token is still the caller's.
* **Waiting** polls, doubling from `poll_s` (50 ms) to `max_poll_s` (1 s), checkpointing between
  polls (a cancelled or stopping step stops waiting, holding nothing); past `max_wait_s` (120 s)
  the request fails `PROVIDER_CAPACITY` (`model_concurrency_wait`) before anything is reserved or
  sent, and the step parks `WAITING_CAPACITY` — no attempt consumed — to be resumed by the sweep.
  Lowering the limit takes effect at once: slots at or above it are never taken.

**The limit is configured, never guessed.** `AIA_DEEP_RESEARCH_MODEL_CONCURRENCY` is required when
fan-out is on (the worker refuses to start without it). It must sit below the account's Bedrock
quota for the route's model; chunk 1's quota request decides it. **Proposed (pending that
request): 4.** The pool is the route (`bedrock:<AIA_AI_ROUTE_ID>`), so every worker calling one
route shares one limit, whichever runs or studies its requests belong to.

**Triage reuses the seam** (`application/deep_research_triage.py`). The runner's
`ConcurrencyLimiter` is the async shape of the same bound: `SharedSlotLimiter` puts each send in
one of the deployment's slots (taken and given back on a worker thread, never on the event loop),
and `CombinedLimiter` holds a slot of each limiter it combines, so
`CombinedLimiter(SemaphoreLimiter(n), SharedSlotLimiter(slots, ...))` bounds a burst per run and
across the deployment. The caller then must not take a slot of its own for the same send
(`StepModelCaller` without a limiter). Triage is not composed into a step yet (chunk 23).

## 5. The switch and the composition

| key | meaning |
| --- | --- |
| `AIA_DEEP_RESEARCH_FAN_OUT` | `true`: tracks in steps of their own, the shared pacer and the model slots; unset or `false`: one step, as before. Read strictly; needs `AIA_DEEP_RESEARCH_ENABLED` |
| `AIA_DEEP_RESEARCH_MODEL_CONCURRENCY` | required with fan-out, refused without it: model requests in flight across every worker on the route (1–256). No default; proposed 4 |

With fan-out on, the composition (`deep_research_runtime.py`) builds a small engine of its own
from the worker's `DATABASE_URL` (two connections, four overflow; an in-memory database is
refused) for the pacer and the slots, which are not study data and are written outside any
attempt's fenced transaction; the runtime carries the slots (`model_slots`) and the transports
carry the pacer. Off, nothing reads either table. The `deep_research_investigate_track` kind is
registered in every composition, so a worker deployed with the switch off still finishes the
tracks a fanned-out join handed out, and the join, released later, finds them stored.

## 6. Measured

A measurement harness (kept out of the repository; the method is here and in the commit that
adds the fan-out) runs one Deep Research run over the synthetic world of `apps/executors/tests/fan_out_world.py` —
N recorded web tracks, each one search, one page and one investigator request, plus the planner,
one verifier batch per track and the synthesizer — in process, against PostgreSQL 16 on the
development machine, with worker threads (`poll_seconds` 0.2), the recorded agents answering
after an injected latency and every page after a fetch latency. Statements are counted on the
engine, the harness's own polling excluded; "working" excludes the idle workers' empty claims.

24 tracks; model requests answer after 1.0 s, pages after 0.2 s (2026-10-06):

| Run | Workers | Model slots | Investigation | Verify | End to end | Statements per track (working) |
| --- | --- | --- | --- | --- | --- | --- |
| switch off | 1 | -- | 31.5 s | 25.3 s | 59.5 s | 115.8 |
| switch on | 1 | 4 | 32.8 s | 25.5 s | 61.0 s | 179.3 |
| switch on | 4 | 4 | 9.4 s | 25.5 s | 37.6 s | 180.9 |
| switch on | 4 | 2 | 16.4 s | 25.7 s | 44.7 s | 193.7 |

* **Time.** Four workers investigate 3.4x faster (31.5 s to 9.4 s); the run is 1.58x faster end
  to end, because the verify step (25 s here) is still one step (§ 7). A pool of 2 holds the
  investigation to 16.4 s: the limit, not the workers, bounds it. With one worker the switch costs
  1.3 s on 31.5 s (a claim, a plan read and a completion per track).
* **Database load.** A track in a step of its own costs 64 more statements than one inside the
  sequential step (179 against 116: its claim and scope, its plan read through the run, its
  journal read back, its completion, two model-slot round trips per request). Four workers also
  poll for work when idle: 429 statements over the run at `poll_seconds` 0.2 (the production
  default is 2 s). A full pool adds slot polling, backed off: 194 per track with 2 slots.
* **Threads, not processes.** The workers share one interpreter; the PostgreSQL suite's four
  worker processes (`test_deep_research_fan_out_processes.py`) are the concurrency proof, these
  the cost.

## 7. What this does not do

* **The verify step.** It still runs every batch in one step, one request after another; at the
  measured latencies it is most of a fanned-out run's remaining time. Handing its batches out is
  the same pattern, not done here.
* **Model concurrency inside a track.** A track's own requests are still one at a time; the
  investigator's up-to-five tool actions per turn were already concurrent (chunk 9).
* **A lock on the URL index.** Two tracks asking for one URL at one instant may both fetch it.
* **Clock-independent pacing.** Waits are on each process's clock (one host on develop).
* **Deadlines per step.** A wait is bounded by its own maximum; a step has no deadline to hand it.
* ~~**The planned mode's rounds are not checkpointed.**~~ Fixed (§ 8): every external outcome of
  a planned round is stored before the next call leaves, and a step that runs again continues.

## 8. Findings

**A planned web track interrupted between rounds sends its first query again and buys its first
round's investigator request again.**
`apps/executors/src/aia_executors/deep_research/investigate.py:419-440 @ f6199d0`: `_web` loops
over the plan's queries from the first on every attempt; the resumed tool meter counts what an
earlier attempt sent against the track's allowance (`:429`) but nothing tells the loop which
queries were sent, and the rounds' investigator answers are not stored. *Reproduced* (2026-10-06,
SQLite, recorded): the planned journey of `test_deep_research_journey.py` with the worker asked to
stop (`Worker.request_stop`, a deploy's `SIGTERM`) as the first web investigator answer returns;
the attempt is released at the next checkpoint and a second worker runs the step again — the
search "trh rostlinných nápojů česko" is sent twice and the round's investigator request is asked
twice, while the allowance, charged for both, keeps the track from its second query.
*Consequence:* after any deploy (or a crash between calls) during a planned investigation, a live
search provider is sent a duplicate query and the model a duplicate paid request, and the track's
coverage shrinks; with fan-out the blast radius is the one track's step, not the investigation.
*Smallest fix:* checkpoint the planned rounds as the agent-directed turns are (each round's
answer stored run-scoped by track, round and request hash; a query the journal shows dispatched
and not answered skipped as `SKIP_EARLIER_ATTEMPT`). *The test that would have caught it:* release
the investigate step after the first round of a planned track, run it again, and assert every
query is searched once and every round's investigator request is asked once.

**Fixed** -- `test_deep_research_planned_recovery.py::test_a_released_planned_track_continues_and_sends_nothing_twice`.
The fix is stronger than the smallest one above, because a planned round's sequence is known in
advance: `_PlannedLog` (`investigate.py`) makes every external outcome durable before the next call
leaves -- the search with its hits **in order** (`PlannedSearch`: the order decides what survives the
dedupe and the fetch allowance, and so what the model is shown), each fetch with the page it
captured (`PlannedFetch`), the round once its fetches resolved (`PlannedRound`), and the
investigator's answer before it is grounded (`PlannedRoundAnswer`). All are run-scoped and none
enters a track's fingerprint. A step that runs again walks the same sequence, reads each record in
place of its call, counts a recorded dispatch against the allowance once (the walk keeps its own
counters: the resumed meter already holds every earlier dispatch), and goes live at the first
record missing. Released after a search, after one of a round's fetches, after a round's answer,
and (fanned out) in a track's own step, the recovered run sends every search, fetch and model
request exactly as often as an uninterrupted run, and stores the same research: tracks, queries,
snapshots and their payload hashes, evidence, stop reasons, counts and allowance. Run-scoped
identities (artifact rows, a run's or a call's id) differ between two independent runs and are not
compared; within the resumed run no artifact row is written twice. Against the code before the fix
the four releases fail on their dispatch counts.

The one window a record cannot close stays fail-closed: an earlier attempt journaled a dispatch
whose outcome no record holds (the call left and its answer was never kept, or the attempt died
between the journal and the record). What came back is not known, so the track ends `INCOMPLETE` /
`TOOL_OUTCOME_UNCERTAIN` and nothing more is sent for it
(`test_a_dispatch_with_no_record_of_its_outcome_ends_the_track_and_sends_nothing_more`). A model
request with no stored answer stays on the call journal's uncertain-call path.
