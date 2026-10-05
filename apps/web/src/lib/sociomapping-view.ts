// The experimental Sociomapping as a person reads it (plan sociomapping-engine I4).
//
// The worker computed everything: positions, fit, relations, heights. This module only
// decides how the stored artifact is shown -- which points, at what height, in which colour
// band, through which camera -- and never computes or adjusts a methodological number. What
// the artifact does not hold (a surface between objects, respondents on the map) is not
// drawn; what it holds undefined stays undefined.

export const SOCIOMAPPING_VERSION = "aia-research-sociomapping-1";

export type Limitation = { code: string; detail: string; question: string | null };

export type SociomappingStart = {
  label: string;
  start_accuracy: number | null;
  final_accuracy: number | null;
  branch: string;
  sweeps: number;
};

export type SociomappingLayout = {
  element_ids: string[];
  positions: [number, number][];
  unplaced: { element_id: string; reason: string }[];
  accuracy: {
    overall: number | null;
    overall_undefined: string | null;
    per_point: (number | null)[];
    per_point_undefined: (string | null)[];
    mean_per_point: number | null;
    ordered_pairs: number;
    undefined_pairs: number;
    evaluator: string;
  };
  starts: SociomappingStart[];
  chosen_start: number;
  baseline_classical_mds: number | null;
  relations_fingerprint: string;
  frame: string;
  rules: string[];
};

export type SociomappingBattery = {
  battery_id: string;
  title: string;
  objects: { id: string; label: string }[];
  rating_scale: [number, number];
  scale_labels?: [string, string];
  status: "MAPPED" | "NOT_MAPPED";
  reason: string | null;
  support: {
    respondents_total: number;
    respondents_complete: number;
    respondents_excluded: number;
    missing_by_object: Record<string, number>;
    weighting: string;
  };
  relations?: {
    scale: string;
    matrix: (number | null)[][];
    undefined: [string, string, string][];
    negative_pairs: [string, string, number][];
    support: number;
    rules: string[];
    fingerprint: string;
  };
  heights?: { kind: string; on_scale: number[]; rules: string[]; input_fingerprint: string };
  coherences?: { available: boolean; written?: string; reason?: string; rules?: string[] };
  layout: SociomappingLayout | null;
  limitations: Limitation[];
  rules?: string[];
};

export type SociomappingResult = {
  sociomapping_version: string;
  method: { name: string; status: string; evaluator: string; parameters: Record<string, unknown>; description: string };
  method_status: string;
  client_facing: false;
  data_origin: string | null;
  synthetic_data: boolean;
  batteries: SociomappingBattery[];
  note: string | null;
  inputs?: { specification_fingerprint?: string; dataset_sha256?: string };
};

/** The stored result, or why it cannot be shown: an unknown version or a status that is not experimental. */
export function readResult(payload: unknown): { ok: true; result: SociomappingResult } | { ok: false; reason: "missing" | "version" | "status" } {
  const body = (payload as { sociomapping?: SociomappingResult } | null)?.sociomapping;
  if (!body) return { ok: false, reason: "missing" };
  if (body.sociomapping_version !== SOCIOMAPPING_VERSION) return { ok: false, reason: "version" };
  if (body.method_status !== "EXPERIMENTAL_AIA" || body.client_facing !== false) return { ok: false, reason: "status" };
  return { ok: true, result: body };
}

export type MapPoint = {
  id: string;
  label: string;
  x: number;
  y: number;
  height: number; // on the set's scale, as stored
  share: number; // the height's place on the scale, 0..1, for drawing only
  band: number; // 0..6, the sequential palette step
  fit: number | null;
};

export function heightBand(value: number, low: number, high: number): number {
  if (high <= low) return 3;
  const share = Math.min(1, Math.max(0, (value - low) / (high - low)));
  return Math.min(6, Math.floor(share * 7));
}

/** The placed objects, in the layout's order, with their stored height and per-point fit. */
export function mapPoints(battery: SociomappingBattery): MapPoint[] {
  const layout = battery.layout;
  if (!layout || !battery.heights) return [];
  const label = new Map(battery.objects.map((o) => [o.id, o.label]));
  const index = new Map(battery.objects.map((o, i) => [o.id, i]));
  const [low, high] = battery.rating_scale;
  return layout.element_ids.map((id, k) => {
    const height = battery.heights!.on_scale[index.get(id)!];
    return {
      id,
      label: label.get(id) ?? id,
      x: layout.positions[k][0],
      y: layout.positions[k][1],
      height,
      share: high > low ? Math.min(1, Math.max(0, (height - low) / (high - low))) : 0.5,
      band: heightBand(height, low, high),
      fit: layout.accuracy.per_point[k],
    };
  });
}

export type Camera = { yaw: number; pitch: number; zoom: number };
export const TOP_VIEW: Camera = { yaw: 0, pitch: 0, zoom: 1 };
export const DEFAULT_3D: Camera = { yaw: -0.6, pitch: 0.95, zoom: 1 };
export const VIEW = { width: 640, height: 480, cx: 320, cy: 250, scale: 330, lift: 0.45 };

/**
 * Map coordinates (0..1 frame) and a height share (0..1) to the screen. From above
 * (`pitch` 0) the picture is the stored layout itself, y up; tilting compresses the ground
 * and raises each point by its height. `depth` orders drawing: far first.
 */
export function project(x: number, y: number, share: number, camera: Camera): { sx: number; sy: number; depth: number } {
  const u = x - 0.5;
  const v = y - 0.5;
  const cos = Math.cos(camera.yaw);
  const sin = Math.sin(camera.yaw);
  const ru = u * cos - v * sin;
  const rv = u * sin + v * cos;
  const s = VIEW.scale * camera.zoom;
  return {
    sx: VIEW.cx + s * ru,
    sy: VIEW.cy - s * (rv * Math.cos(camera.pitch) + VIEW.lift * share * Math.sin(camera.pitch)),
    depth: rv,
  };
}

export function clampCamera(camera: Camera): Camera {
  return {
    yaw: ((camera.yaw % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI),
    pitch: Math.min(1.35, Math.max(0, camera.pitch)),
    zoom: Math.min(2.5, Math.max(0.5, camera.zoom)),
  };
}

/** A stored number in Czech, rounded for display only; an undefined one says so. */
export function num(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "nedefinováno";
  return value.toLocaleString("cs-CZ", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** The object's stored relations to every other object of the set, signed, undefined kept. */
export function relationsOf(battery: SociomappingBattery, id: string): { id: string; label: string; r: number | null; why: string | null }[] {
  if (!battery.relations) return [];
  const ids = battery.objects.map((o) => o.id);
  const row = ids.indexOf(id);
  if (row < 0) return [];
  const why = new Map(battery.relations.undefined.map(([a, b, reason]) => [`${a}|${b}`, reason]));
  return ids
    .map((other, s) => ({
      id: other,
      label: battery.objects[s].label,
      r: battery.relations!.matrix[row][s],
      why: why.get(`${id}|${other}`) ?? null,
    }))
    .filter((entry) => entry.id !== id)
    .sort((a, b) => (b.r ?? -Infinity) - (a.r ?? -Infinity));
}

const LIMITATIONS: Record<string, string> = {
  EXPERIMENTAL_METHOD: "Rozmístění počítá experimentální H-Model AIA. Cílová funkce SOMECS není zdokumentovaná; nejde o ověřenou rekonstrukci SOMECS.",
  NO_RESPONDENT_PLACEMENT: "Respondenti na mapě nejsou: umístění respondentů (STORM) v SOMECS není zdokumentované.",
  NO_HEIGHT_SURFACE: "Výška je jen u objektů; plocha mezi nimi se nedopočítává (interpolace WIND není zdokumentovaná).",
  UNWEIGHTED: "Vztahy i výšky jsou nevážené: žádný zdroj Sociomapu neváží.",
  ADEQUACY_NOT_ASSESSED: "Zda podpora stačí, aby korelace nebo mapa něco znamenaly, posouzeno není.",
  NO_SIGNIFICANCE: "Shoda mapy není testována proti náhodným maticím stejné velikosti.",
  COMPLETE_RESPONDENTS_ONLY: "Ve výpočtu jsou jen respondenti, kteří odpověděli na všechny objekty sady.",
  NEGATIVE_CORRELATIONS_KEPT: "Některé dvojice korelují záporně; zůstávají se znaménkem, mapa je rozmisťuje podle pořadí. Matice 0–1 ani soudržnosti nevznikly.",
  UNPLACED_OBJECTS: "Některé objekty na mapě nejsou, protože nemají žádný definovaný vztah.",
  FEW_OBJECTS: "Na mapě je málo objektů: s několika dvojicemi je přesnost blízká 1 snadno dosažitelná a o struktuře vypovídá málo.",
};

/** "1 objekt", "3 objekty", "5 objektů". */
export function objectsWord(n: number): string {
  if (n === 1) return `${n} objekt`;
  return n >= 2 && n <= 4 ? `${n} objekty` : `${n} objektů`;
}

/**
 * Where each point's label goes, so that labels do not sit on each other: from the top of
 * the picture down, a label that would overlap one already placed moves down a line.
 * Deterministic; it moves labels only, never points.
 */
export function labelOffsets(items: { id: string; sx: number; sy: number }[], line = 15, width = 110): Map<string, number> {
  const placed: { x: number; y: number }[] = [];
  const offsets = new Map<string, number>();
  for (const item of [...items].sort((a, b) => a.sy - b.sy || a.sx - b.sx || a.id.localeCompare(b.id))) {
    let y = item.sy - 8;
    while (placed.some((p) => Math.abs(p.x - item.sx) < width && Math.abs(p.y - y) < line)) y += line;
    placed.push({ x: item.sx, y });
    offsets.set(item.id, y - item.sy);
  }
  return offsets;
}

export function limitationText(item: Limitation): string {
  const words = LIMITATIONS[item.code] ?? item.detail;
  const detail = ["COMPLETE_RESPONDENTS_ONLY", "UNPLACED_OBJECTS", "FEW_OBJECTS"].includes(item.code) ? ` (${item.detail})` : "";
  return item.question ? `${words}${detail} Otevřená otázka ${item.question}.` : `${words}${detail}`;
}
