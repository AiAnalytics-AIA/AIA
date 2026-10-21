/**
 * A scale's range and its verbal labels, the pure part of the scale editor (input-interactions
 * chunk 3b). The labels are the two ends or one per point, low to high: the rule the server
 * compiles (`research_design._scale_labels`: any other length is `scale_labels_mismatch`, a
 * blank, repeated or over-long label `scale_label_invalid`). Nothing here guesses a label.
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
 * they can. The server's rule, so a refusal there is never a surprise here. */
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
