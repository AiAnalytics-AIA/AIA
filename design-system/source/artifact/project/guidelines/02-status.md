# Status — the full matrix

The domain distinguishes five things a researcher must tell apart across a room. Each is a **tone**, and each tone has a shape, a fill treatment and a label. Colour reinforces the shape; it never carries the state alone (see the greyscale proof in *Accessibility*).

| Tone | Means | Shape | Treatment | Why it looks like this |
|---|---|---|---|---|
| `running` | The machine is working; nothing is needed from you | ◉ circle with a core | `status-running` on `status-running-wash`, a 2px live edge | Same hue as `signal`: the live edge of a measurement. It is calm because running needs no action. |
| `you` | Parked, waiting on a person. It will sit here until someone acts | ■ solid square with pause-bar holes | **Solid** `status-you` fill, label in `on-status-you` (≥ 7:1), a 4px amber rule on list rows | The state that costs the business days, so it is the loudest thing on any screen. Amber is used for nothing else. |
| `world` | Parked, waiting on the world: provider quota or capacity. You may act; you do not have to | □ hollow square with pause bars | Dashed `status-world` border on `status-world-wash` | Same *parked* shape as `you`, so it never reads as running, but hollow and slate, so it never reads as yours. |
| `fault` | Failed. It is over and needs diagnosis | ⊗ solid circle with a knocked-out × | `status-fault` text and border on `status-fault-wash` | A machine state (circle family) that ended. Red appears only with the × and a label. |
| `recovery` | A metered call may have been billed and its outcome is unknown | ◆ diamond with ! | **Inverse** block (`status-recovery` / `on-status-recovery`) with a hatched `status-recovery-hatch` edge | Rarest and most serious. It must not look like a retry button: it is a decision about money that may already be spent. |

The quieter tones are `done` (✓ in ink — there is no green), `done-warn` (✓ with a small triangle; read the reservations), `ready` (a hollow ring), `inert` and `blocked` (dashed circles), `invalid` (a dashed return arrow plus a struck-through label: reopened by an edit), `cancelled` and `skipped`.

## Two failure modes this prevents

- **A parked stage that looks failed** causes panic and a support call. `you` and `world` share the *parked* square; `fault` is a circle.
- **A parked stage that looks like it is running** produces a week of silent nothing. `running` has no square and no amber; `you` has no circle.

## The mapping, enum by enum

Every map is total over its domain enum (`packages/aia_core/src/aia_core/domain/*.py` @ 17c0a6b). `AIA.checkTotality()` returns the missing keys; the state gallery shows its result. In `apps/web` the same maps are typed `satisfies Record<Enum, Tone>`, so a new domain value fails `tsc --noEmit`.

| Enum | `you` | `world` | `running` | `fault` | `recovery` | quiet |
|---|---|---|---|---|---|---|
| `StageStatus` | WAITING_USER, WAITING_CREDITS | WAITING_CAPACITY | RUNNING | FAILED | — | NOT_STARTED (inert), READY, DONE, DONE_WITH_WARNINGS, INVALIDATED |
| `WorkflowRunStatus` | AWAITING_GATE, AWAITING_BUDGET | WAITING_PROVIDER, WAITING_CAPACITY | RUNNING | FAILED | RECOVERY_REQUIRED | PENDING (ready), COMPLETED, CANCELLED |
| `StepRunStatus` | AWAITING_GATE, AWAITING_BUDGET | WAITING_PROVIDER, WAITING_CAPACITY | RUNNING | FAILED | RECOVERY_REQUIRED | BLOCKED, RUNNABLE, SUCCEEDED, CANCELLED, SKIPPED |
| `AttemptStatus` | — | — | CLAIMED, EXECUTING | FAILED, EXPIRED | — | PENDING, SUCCEEDED, ABANDONED |
| `ReservationStatus` | — | — | RESERVED | — | SETTLED_UNCERTAIN | SETTLED, RELEASED |
| `StudyStatus` | IN_REVIEW | — | — | — | — | DRAFT, ACTIVE, DELIVERED, ARCHIVED, CANCELLED |
| `ClientStatus` | — | — | — | — | — | ACTIVE, DORMANT, ARCHIVED |
| `ProjectStatus` | — | WAITING | RUNNING | FAILED | — | DRAFT, READY_TO_CONTINUE, COMPLETED, ARCHIVED, TRASHED |
| `FailureClass` | BUDGET_EXCEEDED, APPROVAL_REQUIRED | TRANSPORT, PROVIDER_CAPACITY, TRANSIENT, QUOTA | — | AUTHENTICATION, PERMISSION, MISSING_CONFIGURATION, MODEL_UNAVAILABLE, SCHEMA_VIOLATION, MAX_TURNS, SDK_OUTDATED, UNKNOWN | — | CANCELLED |

`AWAITING_*` means a person owes a decision and `WAITING_*` means a system owes capacity. That is the domain's own rule (`workflow.py` `WorkflowRunStatus` docstring @ 17c0a6b), and the tones follow it exactly. `WAITING_PROVIDER` and `WAITING_CAPACITY` share a tone but never a label, and the provider wait always shows its `runnable_after` time.

## Amber is personal on Portfolio

A `you` tone in a list means "a person owes this". Portfolio fills the row amber only when the server says the pending decision is assignable to the viewer (for example, they hold `APPROVE_BUDGET` for an `AWAITING_BUDGET`). For everyone else the chip keeps its label and the row stays plain. The component renders what the server computed; it does not decide who owes what.

## No fake progress

`RunTimeline` shows real elapsed time, the heartbeat age, the current step, what it is waiting on, the attempt number, and real counts ("2 / 5 kroků hotovo · 1 běží · 2 ve frontě"). It never shows a percentage, never shows an indeterminate shimmer, and never shows a spinner that implies something is imminent.
