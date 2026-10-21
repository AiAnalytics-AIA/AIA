// The signed-off methodology's map (aia-sociomap-5 and the versions edited from it) as the AIA
// panel reads it (plan sociomap-5-web, chunk 1).
//
// The worker computed everything: the objects' ruler positions and relative hill heights, the
// frame of the terrain grid, every respondent's position and placement, the density of the
// clearly placed respondents and the taste segments. This module only reads the stored artifact
// into what the panel renderer draws; it never computes or adjusts a methodological number. An
// object nobody rated is not on the map (not in `object_ids`) and is only listed; a respondent
// not placed has no position.

import type { BatteryWithMaps, Frame, ObjectMapArtifact } from "./object-map-view";

/** The estimator only the signed-off methodology declares: its maps are drawn as the panel draws them. */
export const SIGNED_OFF_ESTIMATOR = "baseline_corrected_pearson";

export type Placement = "PLACED" | "FADED" | "NOT_PLACED";

/** The spec's respondent map section (aia-sociomap-5). */
export type SignedOffRespondentSpec = {
  chance_level: number;
  min_ratings: number;
  informative_min_objects: number;
  density_sigma: number;
};

export type SegmentProfile = {
  likes: string[]; // object ids
  dislikes: string[];
  difference: number[];
  standard_error: number[];
  p_value: number[];
  distinctive: boolean[];
};

/** The taste segments of a mapped set. Per-respondent columns are null unless the decision is SEGMENTS. */
export type StoredSegments = {
  decision: "SEGMENTS" | "NONE" | "BORDERLINE";
  reason: "TOO_FEW_RESPONDENTS" | "TOO_FEW_OBJECTS" | "NO_CLEAR_SEGMENTS" | "NOT_ABOVE_SHUFFLED" | "NOT_STABLE" | null;
  k: number;
  k_fit: number | null;
  gain: number | null;
  null_gain_max: number | null;
  margins: (number | null)[] | null;
  mean_margin: number | null;
  votes: number | null;
  maps: number | null;
  shares: number[];
  separation: number | null;
  distinct: boolean | null;
  profiles: SegmentProfile[];
  label: number[] | null;
  membership: (number | null)[] | null;
  coloured: boolean[] | null;
  hint: { k: number; shares: number[]; profiles: SegmentProfile[] } | null;
};

/** The respondent map of a mapped set, one entry per respondent in `respondent_ids` order. */
export type SignedOffRespondents = {
  status: "computed";
  x: (number | null)[];
  y: (number | null)[];
  placement: Placement[];
  misfit: (number | null)[];
  p_value: (number | null)[];
  counts: Record<Placement, number>;
  informative: boolean;
  min_objects: number;
  density: {
    parameters: { grid_resolution: number; half_extent: number; sigma: number; centre: [number, number] };
    height: number[][];
  };
  segments?: StoredSegments;
};

/** Whether the map was computed by the signed-off methodology, whatever name the run pinned it under. */
export function isSignedOffMap(map: ObjectMapArtifact): boolean {
  return map.spec.relation.estimator === SIGNED_OFF_ESTIMATOR;
}

/** The square the stored terrain grid covers (its centre and half-width, ruler units): the frame the
 *  panel fits over the objects with a known pair. Null without a computed terrain. */
export function storedFrame(map: ObjectMapArtifact): Frame | null {
  if (map.terrain.status !== "computed") return null;
  const { centre, half_extent: half } = map.terrain.parameters;
  return { cx: centre?.[0] ?? 0, cy: centre?.[1] ?? 0, half };
}

export type PanelObject = {
  id: string;
  label: string;
  x: number;
  y: number;
  height: number | null; // the mean rating on the declared 0-1 scale, as stored
  relative: number | null; // the hill's relative height in [floor, 1], as stored
};

/** The mapped objects in the artifact's order, at their ruler positions, labelled from the battery. */
export function panelObjects(battery: BatteryWithMaps, map: ObjectMapArtifact): PanelObject[] {
  if (!map.layout) return [];
  const label = new Map(battery.objects.map((o) => [o.id, o.label]));
  return map.object_ids.map((id, k) => ({
    id,
    label: label.get(id) ?? id,
    x: map.layout!.points[k][0],
    y: map.layout!.points[k][1],
    height: map.heights.values[k],
    relative: map.heights.relative?.[k] ?? null,
  }));
}

/** The labels of the set's objects nobody rated: not on the map, listed beside it ("Neumístěno"). */
export function objectsNotPlaced(battery: BatteryWithMaps, map: ObjectMapArtifact): string[] {
  const label = new Map(battery.objects.map((o) => [o.id, o.label]));
  return (map.objects_not_placed ?? []).map((id) => label.get(id) ?? id);
}

/** The stored respondent map, or null when none was computed (not mappable, or another method). */
export function storedRespondents(map: ObjectMapArtifact): SignedOffRespondents | null {
  return map.respondents?.status === "computed" ? map.respondents : null;
}

export type PanelRespondent = {
  id: string;
  x: number;
  y: number;
  placement: "PLACED" | "FADED";
  segmented: boolean; // the set shows segments: a dot not coloured is then grey, otherwise white
  segment: number; // the respondent's segment; -1 without one (no segments shown, or too few ratings for one)
  coloured: boolean; // drawn in its segment's colour: clearly placed, membership >= the declared level
};

/** The respondents the map draws: every PLACED or FADED one at its stored position, with its segment
 *  only when the set shows segments (as the panel's `_placement`). NOT_PLACED respondents have none. */
export function panelRespondents(map: ObjectMapArtifact): PanelRespondent[] {
  const r = storedRespondents(map);
  if (!r) return [];
  const seg = r.segments?.decision === "SEGMENTS" ? r.segments : null;
  const out: PanelRespondent[] = [];
  (map.respondent_ids ?? []).forEach((id, k) => {
    const x = r.x[k], y = r.y[k], placement = r.placement[k];
    if (x === null || y === null || placement === "NOT_PLACED") return;
    out.push({ id, x, y, placement, segmented: seg !== null, segment: seg?.label?.[k] ?? -1, coloured: seg?.coloured?.[k] ?? false });
  });
  return out;
}

export type SegmentLegend = {
  decision: StoredSegments["decision"];
  reason: StoredSegments["reason"];
  distinct: boolean | null;
  minRatings: number; // the declared ratings a slope needs: a set with fewer objects gets no segments
  // per shown segment, or the borderline hint's likely split: share and the objects rated above / below the rest
  segments: { share: number; likes: string[]; dislikes: string[] }[];
};

/** What the respondent map's segment legend says, the object ids named by the battery's labels. */
export function segmentLegend(battery: BatteryWithMaps, map: ObjectMapArtifact): SegmentLegend | null {
  const seg = storedRespondents(map)?.segments;
  if (!seg) return null;
  const label = new Map(battery.objects.map((o) => [o.id, o.label]));
  const named = (ids: string[]) => ids.map((id) => label.get(id) ?? id);
  const source = seg.decision === "BORDERLINE" ? seg.hint : seg.decision === "SEGMENTS" ? seg : null;
  return {
    decision: seg.decision,
    reason: seg.reason,
    distinct: seg.distinct,
    minRatings: map.spec.segments?.min_ratings ?? 5,
    segments: (source?.shares ?? []).map((share, g) => ({
      share,
      likes: named(source?.profiles[g]?.likes ?? []),
      dislikes: named(source?.profiles[g]?.dislikes ?? []),
    })),
  };
}

export type RespondentNote = { objects: number; minObjects: number; minRatings: number; placeable: boolean };

/** The panel's note under a respondent map: fewer mapped objects than the declared minimum (the map
 *  still exists, only indicative), or fewer than the ratings a respondent needs (nobody can be placed;
 *  an edited version may declare more ratings than objects). Null when neither holds. */
export function respondentNote(map: ObjectMapArtifact): RespondentNote | null {
  const r = storedRespondents(map);
  if (!r) return null;
  const objects = map.object_ids.length;
  const minRatings = map.spec.respondent_map?.min_ratings ?? 3;
  const placeable = objects >= minRatings;
  if (r.informative && placeable) return null;
  return { objects, minObjects: r.min_objects, minRatings, placeable };
}

export type ObjectDetail = {
  id: string;
  label: string;
  primary: boolean;
  height: number | null; // the mean rating on the declared 0-1 scale, as stored
  connectedness: number | null; // 0-100
  alignment: number | null; // null when it says nothing (see below)
  relations: { id: string; label: string; r: number }[]; // the 5 strongest reliable, by |r|
  basis: number | null; // a secondary object only: its strongest reliable |r| to a PRIMARY object
};

/** What the panel's object detail (`objectDetail66`) shows of one mapped object, from the stored map.
 *  The alignment is left out as the panel leaves it out: with each respondent's own mean removed and
 *  every object PRIMARY, the mean signed relation is near zero for every object by construction. */
export function objectDetail(battery: BatteryWithMaps, map: ObjectMapArtifact, k: number): ObjectDetail {
  const label = new Map(battery.objects.map((o) => [o.id, o.label]));
  const ids = map.object_ids, id = ids[k];
  const primary = (j: number) => map.roles[ids[j]] === "primary";
  const score = map.scores?.objects.find((o) => o.id === id);
  const degenerate = map.spec.ratings?.person_normalization === "person_mean_centring" && ids.every((_, j) => primary(j));
  const reliable = ids.flatMap((other, j) => {
    const r = map.relations.r[k][j];
    return j !== k && r !== null && map.relations.status[k][j] === "reliable" ? [{ j, id: other, label: label.get(other) ?? other, r }] : [];
  });
  const toPrimary = reliable.filter((x) => primary(x.j)).map((x) => Math.abs(x.r));
  return {
    id,
    label: label.get(id) ?? id,
    primary: primary(k),
    height: map.heights.values[k],
    connectedness: score?.connectedness == null ? null : 100 * score.connectedness,
    alignment: degenerate ? null : score?.alignment ?? null,
    relations: [...reliable].sort((a, b) => Math.abs(b.r) - Math.abs(a.r)).slice(0, 5).map(({ id: o, label: l, r }) => ({ id: o, label: l, r })),
    basis: primary(k) || !toPrimary.length ? null : Math.max(...toPrimary),
  };
}

export type RelationDetail = {
  a: string;
  b: string;
  r: number | null;
  interval: [number, number] | null;
  n: number | null;
  respondents: number;
  // reliable / weak, or why it is unknown: too few people rated both, or one of them was rated alike by all
  verdict: "reliable" | "weak" | "fewRatings" | "noSpread";
  noiseRule: boolean; // the reliable status also passed the noise rule
  clearFrom: number; // the declared |r~| from which a relation reads "zřetelný"; a map stored before it: 0.3
};

/** The panel's selected-relation block (`relationHtml66`) from the stored pair. The stored map keeps
 *  no p-value and no noise level: those two lines are not shown. */
export function relationDetail(battery: BatteryWithMaps, map: ObjectMapArtifact, i: number, j: number): RelationDetail {
  const label = new Map(battery.objects.map((o) => [o.id, o.label]));
  const rel = map.relations, r = rel.r[i][j], n = rel.n[i][j];
  // Unknown below the status floor; at or above it, unknown only because a column had no spread.
  const verdict = r === null ? ((n ?? 0) < rel.n_min ? "fewRatings" : "noSpread") : rel.status[i][j] === "reliable" ? "reliable" : "weak";
  return {
    a: label.get(map.object_ids[i]) ?? map.object_ids[i],
    b: label.get(map.object_ids[j]) ?? map.object_ids[j],
    r,
    interval: rel.interval?.[i]?.[j] ?? null,
    n,
    respondents: map.support.respondents,
    verdict,
    noiseRule: map.spec.relation.noise_rule?.enabled ?? false,
    clearFrom: map.spec.relation.clear_effect ?? 0.3,
  };
}

export type RespondentDetail = {
  id: string;
  faded: boolean;
  explained: number | null; // % of the differences in the respondent's ratings the map explains
  segment: number | null; // null: the set shows no segments; -1: not clearly in one
};

/** The panel's respondent detail (`personDetail66`) of one placed respondent, from the stored map.
 *  The share explained is rounded as the panel's payload rounds the misfit (4 decimals). */
export function respondentDetail(map: ObjectMapArtifact, id: string): RespondentDetail | null {
  const r = storedRespondents(map);
  const k = (map.respondent_ids ?? []).indexOf(id);
  if (!r || k < 0) return null;
  const misfit = r.misfit[k];
  const seg = r.segments?.decision === "SEGMENTS" ? r.segments : null;
  return {
    id,
    faded: r.placement[k] === "FADED",
    explained: misfit === null ? null : Math.round(100 * (1 - Number(misfit.toFixed(4)))),
    segment: seg ? (seg.coloured?.[k] && (seg.label?.[k] ?? -1) >= 0 ? seg.label![k] : -1) : null,
  };
}
