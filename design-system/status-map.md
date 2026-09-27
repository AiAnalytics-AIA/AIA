# Status map

Every backend status enum, value by value: its Czech label, the English
meaning, its mark and its colour tokens. The values come from the Python
source at `043b0dd` (the file and line are on each heading). The tones, Czech
labels and glyphs come from the AIA Design System artifact
(`source/artifact/project/components/bundle.js` › `TONE`, `cs.status`,
`StatusGlyph`). The English labels are this package's.
`reference/state-gallery.html` renders every row in both themes.

**Rules** (from `source/artifact/project/guidelines/02-status.md`):

- Shape carries the state. Colour only reinforces it: machine states are
  circles, parked states are squares, recovery is a diamond and inert states
  are dashed.
- `AWAITING_*` means a person owes a decision, so it gets the `you` tone
  (amber). `WAITING_*` means a system owes capacity, so it gets the `world`
  tone (slate). This is the domain's own rule
  (`packages/aia_core/src/aia_core/domain/workflow.py:101` › `WorkflowRunStatus` docstring).
- Amber (`status-you`) means "parked, waiting on a person" and nothing else.
  Done has no green.
- A value that is not in this map renders as **"Neznámý stav: X"** in the
  `fault` tone, never as a neutral default.

## Tones

| Tone | Means | Mark (`StatusGlyph`, 16-unit) | Colour tokens |
|---|---|---|---|
| `running` | The machine is working; nothing is needed from you | ◉ circle with a core | `status-running` on `status-running-wash` |
| `you` | Parked, waiting on a person | ■ solid square, pause bars knocked out | `on-status-you` on solid `status-you`; list row `status-you-wash` + 4px `status-you` rule; inline text `status-you-ink` |
| `world` | Parked, waiting on the world (quota, capacity, a deployment) | □ hollow square with pause bars | `status-world`, dashed border, on `status-world-wash` |
| `fault` | Failed; over, needs diagnosis | ⊗ solid circle, × knocked out | `status-fault` text + border on `status-fault-wash` |
| `recovery` | A metered call may have been billed; outcome unknown | ◆ diamond with ! | `on-status-recovery` on `status-recovery`, `status-recovery-hatch` edge |
| `done` | Done; quiet on purpose, no green | ✓ check in ink | `status-done`, `border` outline, no fill |
| `done-warn` | Done, with reservations to read | ✓ check + small triangle | `status-done`, `border` outline |
| `ready` | Ready or queued | ○ hollow ring | `ink-muted`, `border-strong` outline |
| `inert` | Not started | ◌ dashed circle | `status-inert`, dashed `border` |
| `blocked` | Waiting on a previous step | ◌ dashed circle with a bar | `status-inert`, dashed `border` |
| `invalid` | Reopened by an edit; needs a new run | ↺ dashed return arrow, label struck through | `status-inert`, dashed `border` |
| `cancelled` | Cancelled, archived, released | ⊘ ring with a slash | `status-inert`, dashed `border` |
| `skipped` | Skipped | ◌→ dashed circle with an arrow | `status-inert`, dashed `border` |

## Drift since the artifact

The artifact bound its maps to the enums at `17c0a6b`. At `043b0dd`:

| Enum value | Artifact | Here | Why |
|---|---|---|---|
| `FailureClass.RUNTIME_UNAVAILABLE` (`packages/aia_core/src/aia_core/domain/workflow.py:322`) | absent, so it would render "Neznámý stav" in `fault` | `world`, "Chybí běhové prostředí" | The docstring says "Park until someone deploys what the step needs … Not a failure of the work, and no timer can clear it." It is a park, not a fault. It is not amber, because the researcher cannot clear it: an operator deploys the runtime. **This tone is this package's choice, not the design owner's. Confirm or change it.** |

No other value was added, removed or renamed in these nine enums.

## `StageStatus`

`packages/aia_core/src/aia_core/domain/pipeline.py:63` @ `043b0dd`

| Value | Line | Czech | English | Tone | Mark | Colour tokens |
|---|---|---|---|---|---|---|
| `NOT_STARTED` | 71 | Nezahájeno | Not started | `inert` | ◌ dashed circle | `status-inert`, dashed `border` |
| `READY` | 72 | Připraveno | Ready | `ready` | ○ hollow ring | `ink-muted`, `border-strong` outline |
| `RUNNING` | 73 | Běží | Running | `running` | ◉ circle with a core | `status-running` on `status-running-wash` |
| `WAITING_USER` | 74 | Čeká na vás | Waiting on you | `you` | ■ solid square, pause bars knocked out | `on-status-you` on solid `status-you`; list row `status-you-wash` + 4px `status-you` rule; inline text `status-you-ink` |
| `WAITING_CREDITS` | 75 | Čeká na kredity | Waiting on credits | `you` | ■ solid square, pause bars knocked out | `on-status-you` on solid `status-you`; list row `status-you-wash` + 4px `status-you` rule; inline text `status-you-ink` |
| `WAITING_CAPACITY` | 76 | Čeká na kapacitu | Waiting on capacity | `world` | □ hollow square with pause bars | `status-world`, dashed border, on `status-world-wash` |
| `DONE` | 77 | Hotovo | Done | `done` | ✓ check in ink | `status-done`, `border` outline, no fill |
| `DONE_WITH_WARNINGS` | 78 | Hotovo s výhradami | Done with reservations | `done-warn` | ✓ check + small triangle | `status-done`, `border` outline |
| `INVALIDATED` | 79 | Zneplatněno | Invalidated | `invalid` | ↺ dashed return arrow, label struck through | `status-inert`, dashed `border` |
| `FAILED` | 80 | Selhalo | Failed | `fault` | ⊗ solid circle, × knocked out | `status-fault` text + border on `status-fault-wash` |

## `WorkflowRunStatus`

`packages/aia_core/src/aia_core/domain/workflow.py:101` @ `043b0dd`

| Value | Line | Czech | English | Tone | Mark | Colour tokens |
|---|---|---|---|---|---|---|
| `PENDING` | 127 | Ve frontě | Queued | `ready` | ○ hollow ring | `ink-muted`, `border-strong` outline |
| `RUNNING` | 128 | Běží | Running | `running` | ◉ circle with a core | `status-running` on `status-running-wash` |
| `AWAITING_GATE` | 129 | Čeká na schválení | Awaiting approval | `you` | ■ solid square, pause bars knocked out | `on-status-you` on solid `status-you`; list row `status-you-wash` + 4px `status-you` rule; inline text `status-you-ink` |
| `AWAITING_BUDGET` | 130 | Čeká na rozpočet | Awaiting budget | `you` | ■ solid square, pause bars knocked out | `on-status-you` on solid `status-you`; list row `status-you-wash` + 4px `status-you` rule; inline text `status-you-ink` |
| `WAITING_PROVIDER` | 131 | Čeká na poskytovatele | Waiting on provider | `world` | □ hollow square with pause bars | `status-world`, dashed border, on `status-world-wash` |
| `WAITING_CAPACITY` | 132 | Čeká na kapacitu | Waiting on capacity | `world` | □ hollow square with pause bars | `status-world`, dashed border, on `status-world-wash` |
| `RECOVERY_REQUIRED` | 133 | Vyžaduje rozhodnutí | Decision required | `recovery` | ◆ diamond with ! | `on-status-recovery` on `status-recovery`, `status-recovery-hatch` edge |
| `COMPLETED` | 134 | Dokončeno | Completed | `done` | ✓ check in ink | `status-done`, `border` outline, no fill |
| `FAILED` | 135 | Selhalo | Failed | `fault` | ⊗ solid circle, × knocked out | `status-fault` text + border on `status-fault-wash` |
| `CANCELLED` | 136 | Zrušeno | Cancelled | `cancelled` | ⊘ ring with a slash | `status-inert`, dashed `border` |

## `StepRunStatus`

`packages/aia_core/src/aia_core/domain/workflow.py:169` @ `043b0dd`

| Value | Line | Czech | English | Tone | Mark | Colour tokens |
|---|---|---|---|---|---|---|
| `BLOCKED` | 176 | Čeká na předchozí krok | Waiting on previous step | `blocked` | ◌ dashed circle with a bar | `status-inert`, dashed `border` |
| `RUNNABLE` | 177 | Připraveno ke spuštění | Ready to run | `ready` | ○ hollow ring | `ink-muted`, `border-strong` outline |
| `RUNNING` | 178 | Běží | Running | `running` | ◉ circle with a core | `status-running` on `status-running-wash` |
| `AWAITING_GATE` | 179 | Čeká na schválení | Awaiting approval | `you` | ■ solid square, pause bars knocked out | `on-status-you` on solid `status-you`; list row `status-you-wash` + 4px `status-you` rule; inline text `status-you-ink` |
| `AWAITING_BUDGET` | 180 | Čeká na rozpočet | Awaiting budget | `you` | ■ solid square, pause bars knocked out | `on-status-you` on solid `status-you`; list row `status-you-wash` + 4px `status-you` rule; inline text `status-you-ink` |
| `WAITING_PROVIDER` | 181 | Čeká na poskytovatele | Waiting on provider | `world` | □ hollow square with pause bars | `status-world`, dashed border, on `status-world-wash` |
| `WAITING_CAPACITY` | 182 | Čeká na kapacitu | Waiting on capacity | `world` | □ hollow square with pause bars | `status-world`, dashed border, on `status-world-wash` |
| `RECOVERY_REQUIRED` | 183 | Vyžaduje rozhodnutí | Decision required | `recovery` | ◆ diamond with ! | `on-status-recovery` on `status-recovery`, `status-recovery-hatch` edge |
| `SUCCEEDED` | 184 | Dokončeno | Completed | `done` | ✓ check in ink | `status-done`, `border` outline, no fill |
| `FAILED` | 185 | Selhalo | Failed | `fault` | ⊗ solid circle, × knocked out | `status-fault` text + border on `status-fault-wash` |
| `CANCELLED` | 186 | Zrušeno | Cancelled | `cancelled` | ⊘ ring with a slash | `status-inert`, dashed `border` |
| `SKIPPED` | 187 | Přeskočeno | Skipped | `skipped` | ◌→ dashed circle with an arrow | `status-inert`, dashed `border` |

## `AttemptStatus`

`packages/aia_core/src/aia_core/domain/workflow.py:234` @ `043b0dd`

| Value | Line | Czech | English | Tone | Mark | Colour tokens |
|---|---|---|---|---|---|---|
| `PENDING` | 242 | Čeká na pracovníka | Waiting for a worker | `ready` | ○ hollow ring | `ink-muted`, `border-strong` outline |
| `CLAIMED` | 243 | Převzato | Claimed | `running` | ◉ circle with a core | `status-running` on `status-running-wash` |
| `EXECUTING` | 244 | Provádí se | Executing | `running` | ◉ circle with a core | `status-running` on `status-running-wash` |
| `SUCCEEDED` | 245 | Úspěch | Succeeded | `done` | ✓ check in ink | `status-done`, `border` outline, no fill |
| `FAILED` | 246 | Selhání | Failed | `fault` | ⊗ solid circle, × knocked out | `status-fault` text + border on `status-fault-wash` |
| `EXPIRED` | 247 | Vypršel pronájem | Lease expired | `fault` | ⊗ solid circle, × knocked out | `status-fault` text + border on `status-fault-wash` |
| `ABANDONED` | 248 | Opuštěno | Abandoned | `cancelled` | ⊘ ring with a slash | `status-inert`, dashed `border` |

## `ReservationStatus`

`packages/aia_core/src/aia_core/domain/workflow.py:283` @ `043b0dd`

| Value | Line | Czech | English | Tone | Mark | Colour tokens |
|---|---|---|---|---|---|---|
| `RESERVED` | 291 | Rezervováno | Reserved | `running` | ◉ circle with a core | `status-running` on `status-running-wash` |
| `SETTLED` | 292 | Vyúčtováno | Settled | `done` | ✓ check in ink | `status-done`, `border` outline, no fill |
| `RELEASED` | 293 | Uvolněno | Released | `cancelled` | ⊘ ring with a slash | `status-inert`, dashed `border` |
| `SETTLED_UNCERTAIN` | 294 | Nejisté vyúčtování | Settled, uncertain | `recovery` | ◆ diamond with ! | `on-status-recovery` on `status-recovery`, `status-recovery-hatch` edge |

## `StudyStatus`

`packages/aia_core/src/aia_core/domain/scope.py:511` @ `043b0dd`

| Value | Line | Czech | English | Tone | Mark | Colour tokens |
|---|---|---|---|---|---|---|
| `DRAFT` | 514 | Koncept | Draft | `inert` | ◌ dashed circle | `status-inert`, dashed `border` |
| `ACTIVE` | 515 | Aktivní | Active | `ready` | ○ hollow ring | `ink-muted`, `border-strong` outline |
| `IN_REVIEW` | 516 | V revizi | In review | `you` | ■ solid square, pause bars knocked out | `on-status-you` on solid `status-you`; list row `status-you-wash` + 4px `status-you` rule; inline text `status-you-ink` |
| `DELIVERED` | 517 | Předáno | Delivered | `done` | ✓ check in ink | `status-done`, `border` outline, no fill |
| `ARCHIVED` | 518 | Archivováno | Archived | `cancelled` | ⊘ ring with a slash | `status-inert`, dashed `border` |
| `CANCELLED` | 519 | Zrušeno | Cancelled | `cancelled` | ⊘ ring with a slash | `status-inert`, dashed `border` |

## `ClientStatus`

`packages/aia_core/src/aia_core/domain/scope.py:491` @ `043b0dd`

| Value | Line | Czech | English | Tone | Mark | Colour tokens |
|---|---|---|---|---|---|---|
| `ACTIVE` | 494 | Aktivní | Active | `ready` | ○ hollow ring | `ink-muted`, `border-strong` outline |
| `DORMANT` | 495 | Neaktivní | Dormant | `inert` | ◌ dashed circle | `status-inert`, dashed `border` |
| `ARCHIVED` | 496 | Archivováno | Archived | `cancelled` | ⊘ ring with a slash | `status-inert`, dashed `border` |

## `ProjectStatus`

`packages/aia_core/src/aia_core/domain/project.py:56` @ `043b0dd`

| Value | Line | Czech | English | Tone | Mark | Colour tokens |
|---|---|---|---|---|---|---|
| `DRAFT` | 59 | Koncept | Draft | `inert` | ◌ dashed circle | `status-inert`, dashed `border` |
| `READY_TO_CONTINUE` | 60 | Připraveno pokračovat | Ready to continue | `ready` | ○ hollow ring | `ink-muted`, `border-strong` outline |
| `RUNNING` | 61 | Běží | Running | `running` | ◉ circle with a core | `status-running` on `status-running-wash` |
| `WAITING` | 62 | Čeká | Waiting | `world` | □ hollow square with pause bars | `status-world`, dashed border, on `status-world-wash` |
| `COMPLETED` | 63 | Dokončeno | Completed | `done` | ✓ check in ink | `status-done`, `border` outline, no fill |
| `FAILED` | 64 | Selhalo | Failed | `fault` | ⊗ solid circle, × knocked out | `status-fault` text + border on `status-fault-wash` |
| `ARCHIVED` | 65 | Archivováno | Archived | `cancelled` | ⊘ ring with a slash | `status-inert`, dashed `border` |
| `TRASHED` | 66 | V koši | In trash | `cancelled` | ⊘ ring with a slash | `status-inert`, dashed `border` |

## `FailureClass`

`packages/aia_core/src/aia_core/domain/workflow.py:302` @ `043b0dd`

| Value | Line | Czech | English | Tone | Mark | Colour tokens |
|---|---|---|---|---|---|---|
| `TRANSPORT` | 313 | Síťová chyba | Network error | `world` | □ hollow square with pause bars | `status-world`, dashed border, on `status-world-wash` |
| `PROVIDER_CAPACITY` | 314 | Přetížený poskytovatel | Provider overloaded | `world` | □ hollow square with pause bars | `status-world`, dashed border, on `status-world-wash` |
| `TRANSIENT` | 315 | Přechodná chyba | Transient error | `world` | □ hollow square with pause bars | `status-world`, dashed border, on `status-world-wash` |
| `QUOTA` | 318 | Vyčerpaná kvóta | Quota exhausted | `world` | □ hollow square with pause bars | `status-world`, dashed border, on `status-world-wash` |
| `RUNTIME_UNAVAILABLE` ¹ | 322 | Chybí běhové prostředí | Runtime unavailable | `world` | □ hollow square with pause bars | `status-world`, dashed border, on `status-world-wash` |
| `BUDGET_EXCEEDED` | 325 | Překročený rozpočet | Budget exceeded | `you` | ■ solid square, pause bars knocked out | `on-status-you` on solid `status-you`; list row `status-you-wash` + 4px `status-you` rule; inline text `status-you-ink` |
| `APPROVAL_REQUIRED` | 326 | Vyžaduje schválení | Approval required | `you` | ■ solid square, pause bars knocked out | `on-status-you` on solid `status-you`; list row `status-you-wash` + 4px `status-you` rule; inline text `status-you-ink` |
| `AUTHENTICATION` | 329 | Selhalo ověření | Authentication failed | `fault` | ⊗ solid circle, × knocked out | `status-fault` text + border on `status-fault-wash` |
| `PERMISSION` | 330 | Chybí oprávnění | Permission missing | `fault` | ⊗ solid circle, × knocked out | `status-fault` text + border on `status-fault-wash` |
| `MISSING_CONFIGURATION` | 331 | Chybí konfigurace | Configuration missing | `fault` | ⊗ solid circle, × knocked out | `status-fault` text + border on `status-fault-wash` |
| `MODEL_UNAVAILABLE` | 332 | Model nedostupný | Model unavailable | `fault` | ⊗ solid circle, × knocked out | `status-fault` text + border on `status-fault-wash` |
| `SCHEMA_VIOLATION` | 333 | Neplatná struktura výstupu | Invalid output structure | `fault` | ⊗ solid circle, × knocked out | `status-fault` text + border on `status-fault-wash` |
| `MAX_TURNS` | 334 | Vyčerpán počet kroků | Turn limit reached | `fault` | ⊗ solid circle, × knocked out | `status-fault` text + border on `status-fault-wash` |
| `SDK_OUTDATED` | 335 | Zastaralé SDK | SDK outdated | `fault` | ⊗ solid circle, × knocked out | `status-fault` text + border on `status-fault-wash` |
| `CANCELLED` | 336 | Zrušeno | Cancelled | `cancelled` | ⊘ ring with a slash | `status-inert`, dashed `border` |
| `UNKNOWN` | 337 | Neznámá příčina | Unknown cause | `fault` | ⊗ solid circle, × knocked out | `status-fault` text + border on `status-fault-wash` |

¹ Not in the artifact; see *Drift since the artifact*.

## Evidence roles

The domain does not yet publish an evidence-role enum (artifact open item 1;
`docs/product/README.md` names three roles followed by "…"). These are the
artifact's five grades. Any role not listed renders as the unknown grade.

| Role | Czech | English | Mark | Value treatment | Colour token |
|---|---|---|---|---|---|
| `MEASURED_JOINT` | Měřeno | Measured on the same person | ■ solid square | plain | `evidence-mark` |
| `CALIBRATED_CORE` | Kalibrované jádro | Calibrated core | ▣ solid square in a frame | plain | `evidence-mark` |
| `MODELED_BEHAVIOR_PRIOR` | Modelováno | Modelled from a behavioural prior | □ hollow square | dotted underline; "modelováno" in the sentence | `evidence-mark` |
| `EXTERNAL_HOLDOUT_PENDING` | Validace čeká | External holdout pending | ⬚ dotted square | dotted underline + "neval." tag | `evidence-mark` |
| *unknown / missing* | Role neznámá | Unknown role: do not read as measured | **?** | dashed underline | `evidence-mark` |

Marks are always drawn as vector shapes, never as characters: none of the
shipped fonts has U+25A1, U+25A3 or U+2B1A.

## Null states

| State | Czech | English | Mark | Colour token |
|---|---|---|---|---|
| value | Hodnota | Value | the figure, right-aligned, tabular | `ink` |
| zero | Nula | Zero: we looked, and the answer is zero | `0` / `0,0 %` | `ink` |
| not available | chybí | Not available: never looked, or the answer did not arrive | boxed "chybí", weight 600, 135° hatch | `null-mark` |
| suppressed | potlačeno | Suppressed: we have it but withhold it, and always say why (n < 30, no permission) | solid redaction bar + lock | `suppressed-fill` |
| loading | Načítá se | Loading; becomes "chybí" + "Načíst znovu" after 10 s | dotted baseline at the expected width | `ink-faint` |
