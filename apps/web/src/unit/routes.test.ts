import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { UNIT_ROUTES, type UnitRouteKey, ledgerRoute, resolveRoute } from "./routes";

// Read at run time: the web image is built from apps/web alone.
const ledger = JSON.parse(
  readFileSync(join(process.cwd(), "../../docs/migration/legacy-route-ledger.json"), "utf8"),
) as { routes: { route: string; status: string }[]; addenda: { route: string }[] };

describe("the unit routes the rebuilt interface calls", () => {
  it("are every one a row of the legacy route ledger", () => {
    // A pinned row, or an addendum the reference's parser missed (OI-48).
    const known = new Set([...ledger.routes, ...ledger.addenda].map((r) => r.route));
    for (const key of Object.keys(UNIT_ROUTES) as UnitRouteKey[]) {
      expect(known.has(ledgerRoute(key)), `${key}: ${ledgerRoute(key)}`).toBe(true);
    }
  });

  it("are unit paths, never AIA's own /api/v1 (which would bypass the ledger's state)", () => {
    for (const key of Object.keys(UNIT_ROUTES) as UnitRouteKey[]) expect(ledgerRoute(key)).not.toMatch(/ \/api\/v1\//);
  });

  it("build every id path under its ledger row's prefix, with the id escaped", () => {
    for (const key of Object.keys(UNIT_ROUTES) as UnitRouteKey[]) {
      const e = UNIT_ROUTES[key];
      if (typeof e === "string") continue;
      const prefix = e.route.split(" ")[1];
      const { path } = resolveRoute(key, "JOB 1/x");
      expect(path.startsWith(prefix), key).toBe(true);
      expect(path, key).toContain("JOB%201%2Fx");
    }
    expect(resolveRoute("jobCancel", "J1").path).toBe("/api/jobs/J1/cancel");
    expect(resolveRoute("workflow", "WF-1").path).toBe("/api/workflows/WF-1");
  });

  it("refuse an id where none belongs, and demand one where it does", () => {
    expect(() => resolveRoute("projects", "x")).toThrow();
    expect(() => resolveRoute("workflow")).toThrow();
  });
});
