// What a person (or the Lead) has changed in how the signed-off map is shown, against how it opens
// (artifact-sociomap SOC3): the display filter bar names each change and says what did not change.
// A display choice never reaches the computation: the positions, heights, relations and the map's
// credibility are the run's frozen artifact whatever is shown. Pure.

export type MapView = "objects" | "respondents";
export type MapNorm = "range" | "absolute";
export type MapRelations = "top" | "selected" | "all";

/** The display choices of the `-5` panel's toolbar. */
export type MapDisplay = { map: MapView; norm: MapNorm; relations: MapRelations };

/** How the map opens: the objects, Relativní, Top vztahy (the panel's own opening). */
export const OPENING_DISPLAY: MapDisplay = { map: "objects", norm: "range", relations: "top" };

export type DisplayChange =
  | { key: "map"; value: MapView }
  | { key: "norm"; value: MapNorm }
  | { key: "relations"; value: MapRelations };

/**
 * The choices that differ from the opening, in the toolbar's order. On the respondent map the panel
 * offers neither Normalizace nor Vztahy, so only the map itself is a change there.
 */
export function displayChanges(d: MapDisplay): DisplayChange[] {
  const out: DisplayChange[] = [];
  if (d.map !== OPENING_DISPLAY.map) out.push({ key: "map", value: d.map });
  if (d.map === "respondents") return out;
  if (d.norm !== OPENING_DISPLAY.norm) out.push({ key: "norm", value: d.norm });
  if (d.relations !== OPENING_DISPLAY.relations) out.push({ key: "relations", value: d.relations });
  return out;
}

/** The four kinds of content around a map (the V2 prototype's legend), in the order they are read. */
export const MAP_REGISTERS = ["computed", "display", "interpretation", "external"] as const;
export type MapRegister = (typeof MAP_REGISTERS)[number];

/** The least the map's stage is drawn at: below it a map says nothing, and full screen is the way to read it. */
export const STAGE_MIN = 120;

/**
 * The map's stage height in px (artifact-sociomap, #637): the panel's 700 where there is room; never
 * more than the pane leaves under the toolbar (`pane` the visible height of what scrolls the panel,
 * `above` the toolbar and the filter bar over the stage), so the toolbar and the whole map are seen
 * together; and on a narrow stage not much taller than wide, since the map is drawn at the scale of
 * its shorter side. Whole pixels, rounded down so it still fits. Measured, never a guess of the chrome around it, which differs by layout.
 */
export function stageHeight(pane: number, above: number, width: number): number {
  return Math.floor(Math.max(STAGE_MIN, Math.min(700, pane - above, Math.max(360, 1.1 * width))));
}
