// The unit routes the rebuilt interface calls (ADR 0014), each spelled exactly
// as its row in docs/migration/legacy-route-ledger.json. Nothing in the web
// client reaches the unit except through these; routes.test.ts fails a route
// the ledger does not list. When the strangler ports one to AIA's API, its entry
// moves to /api/v1 here and no screen changes.

export const UNIT_ROUTES = {
  projects: "GET /api/projects",
  projectsDashboard: "GET /api/projects/dashboard",
  projectAction: "POST /api/projects/history-action",
  projectsTrash: "GET /api/projects/trash",
  demos: "GET /api/demos",
  bootstrap: "GET /api/bootstrap",
  claudeCodeStatus: "GET /api/providers/claude-code/status",
  demoCopy: "POST /api/demos/copy",
} as const;

export type UnitRouteKey = keyof typeof UNIT_ROUTES;
export type UnitRoute = (typeof UNIT_ROUTES)[UnitRouteKey];

export function splitRoute(route: UnitRoute): { verb: "GET" | "POST"; path: string } {
  const [verb, path] = route.split(" ") as ["GET" | "POST", string];
  return { verb, path };
}
