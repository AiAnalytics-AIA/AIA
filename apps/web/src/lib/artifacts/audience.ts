// Cílová skupina's contract with the Research Lead, as data (artifact-audience AUD1): what on the
// audience the Lead can name, and how the screen marks it. The stage's row in the shared registry
// (lib/workbench-artifacts.ts ARTIFACTS.audience) says which view operations and target kinds it
// has; this file says which `audience:` targets exist for a given study, so focusSelector
// (lib/lead.ts) and the person's "@" (targetOfElement) find exactly one element for each. A target
// this file does not name is refused, never guessed. Pure.

import { filterChips } from "@/research/audience";
import type { ResearchProject } from "@/research/model";
import { ARTIFACTS, ID_SOURCE, type ViewOpKind, aiaId, parseAiaId } from "../workbench-artifacts";

/** Cílová skupina's view operations: its row in the registry, never a copy. */
export const AUDIENCE_VIEW_OPS: readonly ViewOpKind[] = ARTIFACTS.audience.view_ops;

/** The screen's fixed parts: the description, the filters (or the note that says why there are
 * none) and the feasibility preview. */
export const AUDIENCE_PARTS = ["definition", "filters", "preview"] as const;
export type AudiencePart = (typeof AUDIENCE_PARTS)[number];

/** A target on Cílová skupina, read: a part, a stored filter by its factor, or a built-in subpanel. */
export type AudienceTarget = { kind: "part"; part: AudiencePart } | { kind: "filter"; factor: string } | { kind: "subpanel"; key: string };

/** The `data-aia` of a fixed part: `audience:definition`, `audience:filters`, `audience:preview`. */
export function audiencePartAia(part: AudiencePart): string {
  return aiaId("audience", part);
}

const ID = new RegExp(ID_SOURCE);

/** `id` under `prefix`, or null when it falls outside the registry's grammar: such an element is
 * left unmarked rather than breaking the screen; the Lead cannot name what has no id. */
function marked(prefix: "filter" | "subpanel", id: string): string | null {
  return id && ID.test(`${prefix}:${id}`) ? aiaId("audience", `${prefix}:${id}`) : null;
}

/**
 * The `data-aia` of a stored filter: `audience:filter:<factor>`, by the factor's catalogue id as
 * the stored `audience.filters` keys it. The screen puts it on the filter's chip under "Vybrané
 * filtry", which every stored filter has whatever category, search or 80-factor cut the editor
 * shows. Null for an id outside the grammar.
 */
export function audienceFilterAia(factor: string): string | null {
  return marked("filter", factor);
}

/** The `data-aia` of a built-in subpanel's card: `audience:subpanel:<key>`. Null outside the grammar. */
export function audienceSubpanelAia(key: string): string | null {
  return marked("subpanel", key);
}

/** The factors the study has stored a filter on, in their stored order: one chip each, read as the
 * screen reads them (filterChips), so the contract and the screen cannot disagree. */
export function storedFilterFactors(project: ResearchProject): string[] {
  return filterChips(project, null).map((c) => c.id);
}

/**
 * An `audience:` id read without the study: a part this file names, a filter or a subpanel by its
 * id, or null for anything else (another kind, an unknown part, an empty filter or subpanel). For a
 * label; whether the study has the element is audienceTarget's.
 */
export function parseAudienceId(target: string): AudienceTarget | null {
  const parsed = parseAiaId(target);
  if (!parsed || parsed.kind !== "audience") return null;
  const { id } = parsed;
  if ((AUDIENCE_PARTS as readonly string[]).includes(id)) return { kind: "part", part: id as AudiencePart };
  if (id.startsWith("filter:") && id.length > "filter:".length) return { kind: "filter", factor: id.slice("filter:".length) };
  if (id.startsWith("subpanel:") && id.length > "subpanel:".length) return { kind: "subpanel", key: id.slice("subpanel:".length) };
  return null;
}

/**
 * A Lead target Cílová skupina carries for this study, or null: a part, a filter on a factor the
 * study has stored and a subpanel the catalogue offers. Anything else -- a factor with no stored
 * filter (it has no element), a subpanel the catalogue does not list, whatever parseAudienceId
 * refuses -- is refused rather than mapped to something near it.
 */
export function audienceTarget(target: string, project: ResearchProject, subpanels: readonly string[]): AudienceTarget | null {
  const t = parseAudienceId(target);
  if (t?.kind === "filter") return storedFilterFactors(project).includes(t.factor) ? t : null;
  if (t?.kind === "subpanel") return subpanels.includes(t.key) ? t : null;
  return t;
}

/** What the screen draws beyond the description and the filters: the preview, once the population's
 * catalogue is read; the subpanels' keys, in the Speciální skupiny view only (else none). */
export type AudienceView = { preview: boolean; subpanels: readonly string[] };

/**
 * Every target Cílová skupina shows for `project` in `view`: the description, the filters (or the
 * note that says why there are none), each stored filter, the preview and the subpanels when
 * drawn. An id outside the grammar has no element and is left out.
 */
export function audienceTargets(project: ResearchProject, view: AudienceView): string[] {
  const parts: AudiencePart[] = view.preview ? ["definition", "filters", "preview"] : ["definition", "filters"];
  const optional = [...storedFilterFactors(project).map(audienceFilterAia), ...view.subpanels.map(audienceSubpanelAia)];
  return [...parts.map(audiencePartAia), ...optional.filter((id): id is string => id !== null)];
}
