// Sociomapa's own part of the Lead contract (artifact-sociomap SOC1): the map's elements the Lead can
// name, the display operations it may run on the map, and the refusal of anything that would change
// it. The contract itself -- view operations, target kinds, starts, hand-offs -- is ARTIFACTS.sociomap
// (lib/workbench-artifacts.ts); this file never redeclares it. A target names its battery, since a
// run maps every tracked set and an object id alone does not say which map is meant:
// `object:<battery>/<object>`, `pair:<battery>/<a>~<b>` (agreed with the integration coordinator,
// 2026-10-21). The map is the run's frozen artifact: an operation only changes the picture. Pure.

import { ARTIFACTS, VIEW_FILTERS, aiaId, allowsView, parseAiaId } from "@/lib/workbench-artifacts";

export const SOCIOMAP = ARTIFACTS.sociomap;

/** The canonical V2 prototype's interaction contract for the map (fixture.ts CONTRACTS.sociomap). */
export const SOCIOMAP_INTERACTION = {
  readable: ["objekty, výšky, dvojice (r, n, interval, stav), shoda"],
  visual: ["select(object)", "select(pair)", "view.filter (jen zobrazení)"],
  domain: ["research.request(INTERPRETATION_RESEARCH, pair)", "methodology.version (správce)"],
  revision: "zmrazený artefakt mapy",
  refusals: SOCIOMAP.refusals,
} as const;

// ---------------------------------------------------------------- targets

export type MapTarget =
  | { kind: "object"; battery: string; object: string }
  | { kind: "pair"; battery: string; a: string; b: string };

// A part of a target: the registry's id grammar less the separators the map's ids use itself.
const PART = /^[A-Za-z0-9_.\-:]{1,80}$/;
const fits = (...parts: string[]) => parts.every((p) => PART.test(p));

/** An object's `data-aia` id on a battery's map; null for an id outside the grammar (the element
 *  then carries none, rather than a guessed one). */
export function objectTarget(battery: string, object: string): string | null {
  if (!fits(battery, object)) return null;
  try { return aiaId("object", `${battery}/${object}`); } catch { return null; }
}

/** A pair's `data-aia` id: its two objects in the map's own order (`pairKey`), so one pair has one
 *  id whichever end was clicked; null for an id outside the grammar or a pair of one object. */
export function pairTarget(battery: string, a: string, b: string): string | null {
  if (a === b || !fits(battery, a, b)) return null;
  const [x, y] = [a, b].sort();
  try { return aiaId("pair", `${battery}/${x}~${y}`); } catch { return null; }
}

/** A map target read back; null for anything not the map's, or not in its form. */
export function readTarget(target: string): MapTarget | null {
  const parsed = parseAiaId(target);
  if (!parsed || parsed.stage !== "sociomap") return null;
  const slash = parsed.id.indexOf("/");
  if (slash < 1) return null;
  const battery = parsed.id.slice(0, slash), rest = parsed.id.slice(slash + 1);
  if (parsed.kind === "object") return fits(battery, rest) ? { kind: "object", battery, object: rest } : null;
  if (parsed.kind !== "pair") return null;
  const ends = rest.split("~");
  if (ends.length !== 2 || ends[0] === ends[1] || !fits(battery, ...ends)) return null;
  const [a, b] = [...ends].sort();
  return { kind: "pair", battery, a, b };
}

/** The batteries of a run's maps, as a screen holds them: enough to put a target in words. */
export type MapBattery = { battery_id: string; title: string; objects: readonly { id: string; label: string }[] };

/** A map target in words for the "Vidí" chip and the @ menu; null when the run has no such element. */
export function targetWords(target: string, batteries: readonly MapBattery[]): string | null {
  const t = readTarget(target);
  const battery = t && batteries.find((b) => b.battery_id === t.battery);
  if (!t || !battery) return null;
  const label = (id: string) => battery.objects.find((o) => o.id === id)?.label ?? null;
  if (t.kind === "object") {
    const name = label(t.object);
    return name === null ? null : `${battery.title}: ${name}`;
  }
  const a = label(t.a), b = label(t.b);
  return a === null || b === null ? null : `${battery.title}: ${a} – ${b}`;
}

// ---------------------------------------------------------------- display operations

/** Each display filter's values; `battery` takes any battery the run mapped. Display only. */
export const FILTER_VALUES = {
  view: ["top", "relief"],
  labels: ["on", "off"],
  hide_weak: ["on", "off"],
  mode: ["objects", "respondents"],
  battery: null,
} as const satisfies Record<string, readonly string[] | null>;
export type MapFilter = keyof typeof FILTER_VALUES;

export type MapOp =
  | { op: "open_stage" }
  | { op: "focus" | "select" | "inspect"; target: MapTarget }
  | { op: "filter"; name: MapFilter; value: string };

export type MapRefusal = {
  refused: "writes_the_map" | "not_a_map_op" | "unknown_filter" | "unknown_value" | "unknown_target";
  op: string;
  words: string;
};

const METODIKA = "Mapa je zmrazený výsledek běhu a Vedoucí na ní mění jen zobrazení; metodiku mění správce v Nastavení → Metodika a nový běh.";

/**
 * A Lead operation on the map, checked against the contract: what the row allows, in the form the map
 * reads, on an element this run has (`batteries`: the run's battery ids). Everything else is refused
 * by name -- above all anything that would move an object, change a threshold or recompute (D-40:
 * no node drag), which the frozen map never takes from the Lead.
 */
export function readMapOp(input: unknown, batteries: readonly string[]): MapOp | MapRefusal {
  const raw = (typeof input === "object" && input !== null ? input : {}) as Record<string, unknown>;
  const op = typeof raw.op === "string" ? raw.op : "";
  const refuse = (refused: MapRefusal["refused"], words: string): MapRefusal => ({ refused, op, words });
  if (!allowsView("sociomap", op)) {
    return refuse(op && WRITES.test(op) ? "writes_the_map" : "not_a_map_op", `„${op || "?"}“ není operace zobrazení mapy. ${METODIKA}`);
  }
  if (op === "open_stage") return { op };
  if (op === "filter") {
    const name = raw.name, value = raw.value;
    if (typeof name !== "string" || !(VIEW_FILTERS.sociomap ?? []).includes(name) || !Object.hasOwn(FILTER_VALUES, name)) {
      return refuse("unknown_filter", `Filtr „${String(name)}“ mapa nezná.`);
    }
    const allowed = FILTER_VALUES[name as MapFilter];
    const ok = typeof value === "string" && (allowed === null ? batteries.includes(value) : (allowed as readonly string[]).includes(value));
    return ok ? { op, name: name as MapFilter, value: value as string } : refuse("unknown_value", `Filtr „${name}“ nemá hodnotu „${String(value)}“.`);
  }
  const target = typeof raw.target === "string" ? readTarget(raw.target) : null;
  if (!target || !batteries.includes(target.battery)) return refuse("unknown_target", `Mapa tohoto běhu prvek „${String(raw.target)}“ nemá.`);
  return { op: op as "focus" | "select" | "inspect", target };
}

/** Names that would change the map rather than its picture: refused by name, never tried. */
const WRITES = /^(move|drag|set|edit|update|recompute|rerun|delete|remove|add|rename|change|approve|write)(_|$)/;

export const isRefusal = (r: MapOp | MapRefusal): r is MapRefusal => "refused" in r;
