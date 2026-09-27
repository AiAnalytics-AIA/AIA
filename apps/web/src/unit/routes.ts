// The unit routes the rebuilt interface calls (ADR 0014), each spelled exactly
// as its row in docs/migration/legacy-route-ledger.json (or its addenda,
// OI-48). Nothing in the web client reaches the unit except through these;
// routes.test.ts fails a route the ledger does not list. When the strangler
// ports one to AIA's API, its entry moves to /api/v1 here and no screen changes.
//
// A route addressed by id is its ledger row (a prefix arm, e.g.
// "POST /api/jobs/") plus the function that builds the path under it; the test
// checks every such path begins with the row's.

export type LedgerRoute = `${"GET" | "POST"} /${string}`;
type Entry = LedgerRoute | { route: LedgerRoute; path: (id: string) => string };

const under = (prefix: string, suffix = "") => (id: string) => `${prefix}${encodeURIComponent(id)}${suffix}`;

export const UNIT_ROUTES = {
  // Projects (A2)
  projects: "GET /api/projects",
  projectsDashboard: "GET /api/projects/dashboard",
  projectAction: "POST /api/projects/history-action",
  projectsTrash: "GET /api/projects/trash",
  demos: "GET /api/demos",
  demoCopy: "POST /api/demos/copy",
  // The shell (A1)
  bootstrap: "GET /api/bootstrap",
  // The research flow (A4) calls none of these any more (ADR 0018): its content,
  // attachments, import, catalogues and AI steps are AIA's. What is left is the
  // unit's own job and workflow plumbing, removed with the rest of src/unit.
  job: "GET /api/job",
  jobCancel: { route: "POST /api/jobs/", path: under("/api/jobs/", "/cancel") },
  workflow: { route: "GET /api/workflows/", path: under("/api/workflows/") },
} as const satisfies Record<string, Entry>;

export type UnitRouteKey = keyof typeof UNIT_ROUTES;
type Keyed<K extends UnitRouteKey> = (typeof UNIT_ROUTES)[K];
/** The keys whose path needs an id. */
export type UnitIdRouteKey = { [K in UnitRouteKey]: Keyed<K> extends { path: unknown } ? K : never }[UnitRouteKey];

export function ledgerRoute(key: UnitRouteKey): LedgerRoute {
  const e: Entry = UNIT_ROUTES[key];
  return typeof e === "string" ? e : e.route;
}

/** The verb and the concrete path for a call; `id` is required exactly for id routes. */
export function resolveRoute(key: UnitRouteKey, id?: string): { verb: "GET" | "POST"; path: string } {
  const e: Entry = UNIT_ROUTES[key];
  const [verb, path] = (typeof e === "string" ? e : e.route).split(" ") as ["GET" | "POST", string];
  if (typeof e === "string") {
    if (id !== undefined) throw new Error(`${key} takes no id`);
    return { verb, path };
  }
  if (!id) throw new Error(`${key} needs an id`);
  return { verb, path: e.path(id) };
}
