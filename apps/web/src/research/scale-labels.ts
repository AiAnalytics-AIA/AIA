/**
 * A scale's range and its verbal labels, the pure part of the scale editor (input-interactions
 * chunk 3b). The labels are the two ends or one per point, low to high: the rule the server
 * compiles (`research_design._scale_labels`). The server never refuses a design for its labels:
 * any that break the rule (another length, a blank, repeated or over-long label) it leaves out
 * and readiness warns (`scale_labels_ignored`). Here, at the field, the editor refuses them
 * (`labelProblem`), so a person never saves labels that would be left out. Nothing here
 * guesses a label.
 */

/** The longest label one point may carry; the server's `SCALE_LABEL_MAX`. */
export const SCALE_LABEL_MAX = 60;

/** The owner's presets (Q32 a, 2026-10-20); anything else is "Vlastní". */
export const SCALE_PRESETS: readonly (readonly [number, number])[] = [
  [1, 5],
  [1, 7],
  [0, 10],
  [1, 10],
];

export type Scale = readonly [number, number];

/** How many points a scale has, both ends included. */
export function points(scale: Scale): number {
  return scale[1] - scale[0] + 1;
}

/** The preset a scale is, or `null` for "Vlastní". */
export function presetOf(scale: Scale): Scale | null {
  return SCALE_PRESETS.find(([low, high]) => low === scale[0] && high === scale[1]) ?? null;
}

/** Whether the labels describe every point (not just the two ends). */
export function everyPointLabelled(labels: readonly string[], scale: Scale): boolean {
  return points(scale) > 2 && labels.length === points(scale);
}

/** "Popsat každý bod": an ends-only scale as one field per point, prefilled with the two ends
 * and the inner points empty for the person to fill. Already per point: unchanged. */
export function describeEveryPoint(labels: readonly string[], scale: Scale): string[] {
  const n = points(scale);
  if (labels.length === n) return [...labels];
  const out = Array.from({ length: n }, () => "");
  out[0] = labels[0] ?? "";
  out[n - 1] = labels[labels.length - 1] ?? "";
  return out;
}

export type Rescaled = {
  /** The labels the new range keeps. */
  labels: string[];
  /** How many inner labels were cleared: what the undo toast counts ("Odstraněno 8 popisků
   * bodů – Vrátit"); 0 when nothing was lost. */
  cleared: number;
};

/**
 * The labels a scale keeps when its range changes. Two ends stay two ends. A fully labelled
 * scale keeps every label only when the number of points is unchanged (1-5 to 0-4 shifts
 * them); otherwise the two end labels stay and every inner label is cleared, counted for the
 * undo. Labels are never redistributed over a different number of points.
 */
export function rescaleLabels(labels: readonly string[], from: Scale, to: Scale): Rescaled {
  if (!everyPointLabelled(labels, from) || points(from) === points(to)) {
    return { labels: [...labels], cleared: 0 };
  }
  const inner = labels.slice(1, -1).filter((label) => label.trim() !== "").length;
  return { labels: [labels[0], labels[labels.length - 1]], cleared: inner };
}

/** Why the labels cannot be compiled, in the words the editor shows at the field; `null` when
 * they can. The server's rule: labels this refuses, the server leaves out with a warning. */
export function labelProblem(labels: readonly string[], scale: Scale): string | null {
  const trimmed = labels.map((label) => label.trim());
  if (trimmed.every((label) => label === "")) return null;
  if (trimmed.length !== 2 && trimmed.length !== points(scale)) {
    return `Škála má ${points(scale)} bodů: popište oba konce, nebo každý bod.`;
  }
  if (trimmed.some((label) => label === "")) return "Popisek bodu škály nesmí být prázdný.";
  const folded = trimmed.map((label) => label.toLocaleLowerCase("cs"));
  if (new Set(folded).size !== folded.length) return "Dva body škály nesmí mít stejný popisek.";
  if (trimmed.some((label) => label.length > SCALE_LABEL_MAX)) {
    return `Popisek bodu škály smí mít nejvýše ${SCALE_LABEL_MAX} znaků.`;
  }
  return null;
}

// ---- The editor's pure part (input-interactions 3b2) ----------------------------------------

/**
 * The ends a "Vlastní" range may take: whole numbers, `SCALE_END_MIN` <= low < high <=
 * `SCALE_END_MAX`. The domain's bound for a scale an agent proposes
 * (`aia_core/domain/research_agents.py` `QuestionItem` / `BatterySection`: `0 <= low < high <= 100`);
 * the compiler itself asks only two whole numbers, low < high (`research_design._scale`).
 */
export const SCALE_END_MIN = 0;
export const SCALE_END_MAX = 100;

/**
 * The most points "Každý bod" offers to describe: the presets' largest (0-10). A wider scale
 * keeps its two ends; one already labelled point by point is shown and edited as it is.
 */
export const DESCRIBED_POINTS_MAX = 11;

/** A range in words, as the chips and the notes write it ("0–10"). */
export function rangeWords(scale: Scale): string {
  return `${scale[0]}–${scale[1]}`;
}

/** The two steppers' bounds for "Vlastní": each end bounded by the other, never equal to it. */
export function endBounds(scale: Scale): { low: { min: number; max: number }; high: { min: number; max: number } } {
  return {
    low: { min: SCALE_END_MIN, max: Math.min(scale[1] - 1, SCALE_END_MAX - 1) },
    high: { min: Math.max(scale[0] + 1, SCALE_END_MIN + 1), max: SCALE_END_MAX },
  };
}

/**
 * A stored range as the editor reads it: two whole numbers in bounds, low < high; `null`
 * otherwise (a decimal, a reversed or an out-of-bounds range the old fields let through, IA-2),
 * never rounded or swapped into one.
 */
export function readRange(raw: readonly unknown[] | undefined): Scale | null {
  if (!raw || raw.length !== 2) return null;
  const [low, high] = raw;
  if (typeof low !== "number" || typeof high !== "number") return null;
  if (!Number.isInteger(low) || !Number.isInteger(high)) return null;
  if (low < SCALE_END_MIN || high > SCALE_END_MAX || low >= high) return null;
  return [low, high];
}

export type LabelMode = "ends" | "points";

/** How the labels are drawn: one field per point when they describe every point, else the ends. */
export function labelMode(labels: readonly string[], scale: Scale): LabelMode {
  return everyPointLabelled(labels, scale) ? "points" : "ends";
}

/** The two ends as shown: the first label and the last, whatever the list's length. */
export function shownEnds(labels: readonly string[]): [string, string] {
  return [labels[0] ?? "", labels.length > 1 ? labels[labels.length - 1] : ""];
}

/** One end written: the labels become exactly the two ends (a list of another length is put right). */
export function withEnd(labels: readonly string[], end: 0 | 1, value: string): string[] {
  const [low, high] = shownEnds(labels);
  return end === 0 ? [value, high] : [low, value];
}

/** One point's label written; the other points are kept as they are. */
export function withPoint(labels: readonly string[], index: number, value: string): string[] {
  return labels.map((label, i) => (i === index ? value : label));
}

/**
 * "Jen konce": a scale labelled point by point back to its two ends. The inner labels are
 * cleared and counted for the undo, as a range change counts them.
 */
export function endsOnly(labels: readonly string[], scale: Scale): Rescaled {
  if (!everyPointLabelled(labels, scale)) return { labels: [...labels], cleared: 0 };
  const inner = labels.slice(1, -1).filter((label) => label.trim() !== "").length;
  return { labels: [labels[0], labels[labels.length - 1]], cleared: inner };
}

/** Whether `value` repeats another point's label (case-folded, as the server compares). */
export function repeatsAnother(labels: readonly string[], index: number, value: string): boolean {
  const folded = value.trim().toLocaleLowerCase("cs");
  if (!folded) return false;
  return labels.some((label, i) => i !== index && label.trim().toLocaleLowerCase("cs") === folded);
}

/** What the undo toast says was cleared, in Czech number agreement ("Odstraněno 8 popisků bodů"). */
export function clearedWords(n: number): string {
  if (n === 1) return "Odstraněn 1 popisek bodu";
  if (n >= 2 && n <= 4) return `Odstraněny ${n} popisky bodů`;
  return `Odstraněno ${n} popisků bodů`;
}

// ---- Per-point labels through a rewrite (#559 review) ---------------------------------------

type Rec = Record<string, unknown>;
const isRec = (x: unknown): x is Rec => typeof x === "object" && x !== null && !Array.isArray(x);
const fold = (text: unknown) => String(text ?? "").replace(/\s+/g, " ").trim().toLocaleLowerCase("cs");

/** A question's labels when they are a valid label on every point of its range; else `null`. */
function pointLabelsOf(q: Rec): { scale: Scale; labels: string[] } | null {
  const scale = readRange(Array.isArray(q.skala) ? q.skala : undefined);
  const labels = q.popisky_skaly;
  if (q.typ !== "skala" || !scale || !Array.isArray(labels) || !labels.every((l) => typeof l === "string")) return null;
  if (!everyPointLabelled(labels, scale) || labelProblem(labels, scale) !== null) return null;
  return { scale, labels: [...labels] };
}

type Kept = { q: Rec; scale: Scale; labels: string[] };

/** The stored per-point labels a rewritten question keeps, or `null` (see `keepPointLabels`). */
function keptFor(q: Rec, kept: readonly Kept[]): string[] | null {
  const scale = readRange(Array.isArray(q.skala) ? q.skala : undefined);
  const labels = Array.isArray(q.popisky_skaly) ? q.popisky_skaly : q.popisky_skaly == null ? [] : null;
  if (q.typ !== "skala" || !scale || labels === null || labels.length > 2) return null;
  const same = kept.filter((x) => x.scale[0] === scale[0] && x.scale[1] === scale[1]);
  const tiers: ((x: Kept) => boolean)[] = [
    (x) => q.id != null && x.q.id === q.id,
    (x) => fold(q.text) !== "" && fold(x.q.text) === fold(q.text),
    (x) => labels.length === 2 && fold(labels[0]) === fold(x.labels[0]) && fold(labels[1]) === fold(x.labels[x.labels.length - 1]),
  ];
  for (const tier of tiers) {
    const found = same.filter(tier);
    if (found.length === 1) return [...found[0].labels];
    if (found.length > 1) return null;
  }
  return null;
}

/**
 * A rewritten questionnaire with its scale questions' per-point labels kept. A rewrite whose
 * contract carries a scale's two ends only (the optimiser, an agent's proposal) would otherwise
 * drop the inner labels without a word. A rewritten scale question with at most two labels and
 * the same range as a stored question labelled validly on every point keeps the stored labels,
 * when exactly one such stored question matches it: by id, else by wording, else by its two ends.
 * Anything else stays as the rewrite wrote it. The server keeps them by the same rule
 * (`aia_core/domain/research_design.py` `keep_point_labels`).
 */
export function keepPointLabels<T>(rewritten: readonly T[], stored: unknown): T[] {
  const kept: Kept[] = [];
  for (const s of Array.isArray(stored) ? stored : []) {
    if (!isRec(s) || !Array.isArray(s.questions)) continue;
    for (const q of s.questions) {
      const point = isRec(q) ? pointLabelsOf(q) : null;
      if (point && isRec(q)) kept.push({ q, ...point });
    }
  }
  if (!kept.length) return [...rewritten];
  return rewritten.map((section) => {
    if (!isRec(section) || !Array.isArray(section.questions)) return section;
    let changed = false;
    const questions = section.questions.map((q: unknown) => {
      const labels = isRec(q) ? keptFor(q, kept) : null;
      if (!labels) return q;
      changed = true;
      return { ...(q as Rec), popisky_skaly: labels };
    });
    return changed ? ({ ...section, questions } as T) : section;
  });
}
