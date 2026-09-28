# StatusChip

Renders any domain status as a glyph plus a label in its tone.

**The consumer provides:** `kind` (one of the bound enums: `StageStatus`, `WorkflowRunStatus`, `StepRunStatus`, `AttemptStatus`, `ReservationStatus`, `StudyStatus`, `ClientStatus`, `ProjectStatus`, `FailureClass`), `value` (the raw enum value from the server), optional `small`, optional `children` to override the label text.

**Use:** Use it everywhere a status is shown: rows, headers, dialogs. It maps a value to an appearance; it never decides what the status is.

**Don't:** Never pass a tone directly — there is no `tone` prop, on purpose. An unknown value renders “Neznámý stav: X” in the fault tone. Never hide the label to save space; the chip wraps instead.
