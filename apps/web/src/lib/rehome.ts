// The rebuilt interface's kill switch (ADR 0014). Off unless the environment
// says "true" or "1": a missing or misspelt value leaves /app answering 404,
// never half-on. The develop compose switches it on.

export const REHOME_SWITCH = "AIA_INTERFACE_REHOME_ENABLED";

export function rehomeEnabledFrom(value: string | undefined): boolean {
  const v = value?.trim().toLowerCase();
  return v === "true" || v === "1";
}
