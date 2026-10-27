# Krokovač (Stepper)

A bounded number with − and +: 32 px, radius 6, 1 px `border-strong`; the value in mono 12, at least 72 px wide. Shift steps ×10. The bounds come from the server; a value outside them is refused, never clamped.

**Use** for sample size, budgets, thresholds and methodology parameters. Money values carry their unit after the number.

**Replaces** `ui/Stepper.tsx:17` value cell (sans 14 → mono 12, width 72). Function kept: `lib/number-input.ts`.
