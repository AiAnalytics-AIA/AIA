// How the settings page reads AIA's AI runtime: the activities the settings
// document describes (from code), against the switches /config reports (from the
// deployment). It can say a capability is switched on in configuration, off and
// why, invalid, or unknown -- never connected, healthy or verified: nothing on the
// page calls a model, and the worker's acceptance of the rest of its configuration
// is not visible here.
//
// The one rule mirrored from the worker (aia_executors/ai_runtime.py, held there by
// apps/executors/tests/test_settings_presentation.py): the runtime's own switch is
// read first; off, nothing else is read and nothing runs; on, a value the worker
// refuses in any switch stops the whole worker, not just that switch's activity.
// Deep Research's switches are strict (aia_executors/deep_research_runtime.py): read
// whatever the runtime's switch says, and on without a switch named before them by an
// activity that lists them, the worker does not start either.

import type { NativeActivity, NativeRuntime } from "@/lib/api";

/** Each switch by variable name: true, false, or null for a value the worker refuses. */
export type SwitchValues = Record<string, boolean | null>;

export type ActivityState =
  /** Every switch it needs is on in this deployment's configuration. Nothing verified. */
  | { kind: "configured"; switch: null }
  /** The first switch it needs that is off: the reason it does not run. */
  | { kind: "off"; switch: string }
  /** A switch holds a value the worker refuses, or is on without `needs`: the worker does not start. */
  | { kind: "invalid"; switch: string; needs?: string }
  /** The page cannot see a switch it needs (or no configuration at all). */
  | { kind: "unknown"; switch: string | null };

function read(switches: SwitchValues, name: string): boolean | null | undefined {
  return Object.prototype.hasOwnProperty.call(switches, name) ? switches[name] : undefined;
}

/** Where one activity stands, from the switches alone. `null` switches: /config unreadable. */
export function activityState(runtime: NativeRuntime, activity: NativeActivity, switches: SwitchValues | null): ActivityState {
  if (!switches) return { kind: "unknown", switch: null };
  const master = read(switches, runtime.switch);
  if (master === undefined) return { kind: "unknown", switch: runtime.switch };
  if (master === null) return { kind: "invalid", switch: runtime.switch };
  const strict = strictRefusal(runtime, switches);
  if (strict) return strict;
  if (master === false) return { kind: "off", switch: runtime.switch };
  // On: the worker reads every switch, and one it refuses stops it for everyone.
  const named = [...new Set(runtime.activities.flatMap((a) => a.switches))].filter((s) => s !== runtime.switch);
  const refused = named.find((s) => read(switches, s) === null);
  if (refused) return { kind: "invalid", switch: refused };
  for (const name of activity.switches) {
    const value = read(switches, name);
    if (value === undefined) return { kind: "unknown", switch: name };
    if (value === false) return { kind: "off", switch: name };
  }
  return { kind: "configured", switch: null };
}

/** Every switch named before `name` by an activity that lists it: what it needs on. */
export function needsOf(runtime: NativeRuntime, name: string): string[] {
  const needs = runtime.activities.flatMap((a) => (a.switches.includes(name) ? a.switches.slice(0, a.switches.indexOf(name)) : []));
  return [...new Set(needs)];
}

/** A strict switch the worker refuses -- its value, or on without what it needs -- if any. */
function strictRefusal(runtime: NativeRuntime, switches: SwitchValues): ActivityState | null {
  for (const name of runtime.strict_switches ?? []) {
    const value = read(switches, name);
    if (value === null) return { kind: "invalid", switch: name };
    if (value !== true) continue;
    const missing = needsOf(runtime, name).find((need) => read(switches, need) === false);
    if (missing) return { kind: "invalid", switch: name, needs: missing };
  }
  return null;
}

/** The data classes the route is approved for, each known to the vocabulary or not. */
export function approvedClasses(classes: string[], vocabulary: string[]): { id: string; known: boolean }[] {
  return classes.map((id) => ({ id, known: vocabulary.includes(id) }));
}
