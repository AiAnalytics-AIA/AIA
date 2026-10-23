// What the Sociomapa stage says under a signed-off map (artifact-sociomap SOC10): the map's own
// stored numbers, gathered for the sections below it -- what the map shows, its strongest relations,
// the objects, the respondents and their taste segments, how reliable it is. Pure: it reads the
// stored artifact through the panel's readers (object-map-signed-off.ts) and computes nothing
// methodological; a value the map does not store stays null, never a guess.

import { type BatteryWithMaps, type ObjectMapArtifact, originalRating } from "./object-map-view";
import { color66 } from "./object-map-panel";
import { objectDetail, segmentLegend, storedRespondents, type SegmentLegend } from "./object-map-signed-off";

/** The most relations listed under the map; the rest stay on it. */
export const SHOWN_RELATIONS = 6;

export type ExplainedObject = {
  id: string;
  label: string;
  /** The mean rating on the declared scale (the stored 0-1 mean read back); null when not stored. */
  rating: number | null;
  /** 0-100; null when not stored. */
  connectedness: number | null;
  /** The object's hill colour on the map, so a row reads as its place on the map. */
  colour: string;
};

export type ExplainedRelation = { a: ExplainedObject; b: ExplainedObject; r: number; clear: boolean };

export type MapExplanation = {
  scale: [number, number];
  objects: ExplainedObject[]; // ranked by the stored mean, highest first
  unplaced: string[]; // labels of the objects nobody rated
  respondents: number;
  /** The split-half agreement and the threshold it is judged by; null without a score. */
  quality: { value: number; threshold: number } | null;
  weaklyDetermined: boolean;
  pairs: { reliable: number; weak: number; unknown: number; total: number };
  relations: ExplainedRelation[];
  moreRelations: number;
  /** In units of the map's typical distance between objects; null when not computed. */
  uncertainty: number | null;
  placement: { placed: number; faded: number; notPlaced: number } | null;
  segments: SegmentLegend | null;
  /** The share of a respondent's membership that colours their dot (the declared rule). */
  colourMembership: number;
  nMin: number;
};

/** A Czech count's word: 1, 2-4, else. */
export function plural(n: number, one: string, few: string, many: string): string {
  return n === 1 ? one : n >= 2 && n <= 4 ? few : many;
}

export function explainMap(battery: BatteryWithMaps, map: ObjectMapArtifact): MapExplanation {
  const scale: [number, number] = battery.rating_scale ?? [0, 1];
  const ids = map.object_ids;
  const all = ids.map((id, k) => {
    const d = objectDetail(battery, map, k);
    return {
      id,
      label: d.label,
      rating: d.height === null ? null : originalRating(d.height, battery.rating_scale) ?? d.height,
      connectedness: d.connectedness,
      colour: color66(map.heights.relative?.[k] ?? 0.15),
    };
  });
  const clear = map.spec.relation.clear_effect ?? 0.3;
  const reliable: ExplainedRelation[] = [];
  for (let i = 0; i < ids.length; i++) {
    for (let j = i + 1; j < ids.length; j++) {
      const r = map.relations.r[i][j];
      if (r !== null && map.relations.status[i][j] === "reliable") reliable.push({ a: all[i], b: all[j], r, clear: Math.abs(r) >= clear });
    }
  }
  reliable.sort((x, y) => Math.abs(y.r) - Math.abs(x.r));
  const counts = map.status_counts;
  const credibility = map.credibility;
  const label = new Map(battery.objects.map((o) => [o.id, o.label]));
  const people = storedRespondents(map);
  return {
    scale,
    // An object without a stored mean ranks last, never as the lowest rated.
    objects: [...all].sort((x, y) => (y.rating ?? -Infinity) - (x.rating ?? -Infinity)),
    unplaced: (map.objects_not_placed ?? []).map((id) => label.get(id) ?? id),
    respondents: map.support.respondents,
    quality: credibility?.split_half == null ? null : { value: credibility.split_half, threshold: credibility.threshold },
    weaklyDetermined: credibility?.weakly_determined ?? false,
    pairs: { reliable: counts.reliable, weak: counts.weak, unknown: counts.unknown, total: counts.reliable + counts.weak + counts.unknown },
    relations: reliable.slice(0, SHOWN_RELATIONS),
    moreRelations: Math.max(0, reliable.length - SHOWN_RELATIONS),
    uncertainty: credibility?.uncertainty_radius ?? null,
    placement: people ? { placed: people.counts.PLACED, faded: people.counts.FADED, notPlaced: people.counts.NOT_PLACED } : null,
    segments: segmentLegend(battery, map),
    colourMembership: map.spec.segments?.colour_membership ?? 0.8,
    nMin: map.spec.relation.n_min,
  };
}
