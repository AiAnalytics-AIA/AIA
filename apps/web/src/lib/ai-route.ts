// The AI route as the newest worker start composed it (lead-orchestration LO12b), read from GET
// /settings/ai-route: for each data class whether that route carries it, by the gateway's own
// checks (the API's ai_route_reach.class_reach), or which refusal it meets. Read only; a record
// says what the newest worker start composed, never that a worker runs now.

export type AiRouteClass = { data_class: "A" | "B" | "C"; refusal: string | null; advisory: boolean };

export type AiRoute = {
  recorded: boolean;
  worker: string | null;
  build_sha: string | null;
  composed_at: string | null;
  runtime: boolean | null;
  route_id: string | null;
  study_lead: string | null;
  classes: AiRouteClass[];
  lead_refusal: string | null;
};

/** One class's line: carried, carried only under advisory gates, or refused with its code. */
export type ClassLine = { letter: "A" | "B" | "C"; kind: "carried" | "advisory" | "refused"; code: string | null };

export function classLines(route: AiRoute): ClassLine[] {
  if (!route.recorded) return [];
  return route.classes.map((c) => ({
    letter: c.data_class,
    kind: c.refusal !== null ? "refused" : c.advisory ? "advisory" : "carried",
    code: c.refusal,
  }));
}
