// Vzorek's part of the Lead's artifact contract (plan artifact-sample SMP1): the elements on the
// screen the Lead can name, each built with aiaId, so the screen never spells the grammar itself.
// The row itself (view operations, starts, inputs, hand-off, report sections, refusals) is
// ARTIFACTS.sample in lib/workbench-artifacts.ts. Pure.

import { aiaId } from "../workbench-artifacts";

/** The screen's numbered sections, in V2's order (SampleStages.tsx SampleArt). */
export const SAMPLE_SECTIONS = ["size", "forecast", "respondents", "ready"] as const;
export type SampleSection = (typeof SAMPLE_SECTIONS)[number];

/** The support forecast's items: the donors the run will draw, and what the questionnaire will answer. */
export const FORECAST_ITEMS = ["support", "outlook"] as const;
export type ForecastItem = (typeof FORECAST_ITEMS)[number];

/** Every `data-aia` id Vzorek carries (artifact-sample §4: `sample:<id>`). */
export const sampleAia = {
  section: (s: SampleSection) => aiaId("sample", s),
  /** The sample size, as Dimenze sets it. */
  n: () => aiaId("sample", "n"),
  /** One quota cell of the panel's composition (SMP2; the cell as the server names it). */
  quota: (cell: string) => aiaId("sample", `quota:${cell}`),
  forecast: (item: ForecastItem) => aiaId("sample", `forecast:${item}`),
  /** One readiness check, by the server's check id (SMP4; V2's `sample.ready.<id>`). */
  ready: (check: string) => aiaId("sample", `ready:${check}`),
  /** One persona source the server lists (SMP5), read only here. */
  respondents: (source: string) => aiaId("sample", `respondents:${source}`),
};
