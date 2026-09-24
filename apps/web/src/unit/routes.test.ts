import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { UNIT_ROUTES } from "./routes";

// Read at run time: the web image is built from apps/web alone.
const ledger = JSON.parse(
  readFileSync(join(process.cwd(), "../../docs/migration/legacy-route-ledger.json"), "utf8"),
) as { routes: { route: string; status: string }[] };

describe("the unit routes the rebuilt interface calls", () => {
  it("are every one a row of the legacy route ledger", () => {
    const known = new Set(ledger.routes.map((r) => r.route));
    for (const [key, route] of Object.entries(UNIT_ROUTES)) expect(known.has(route), `${key}: ${route}`).toBe(true);
  });

  it("are unit paths, never AIA's own /api/v1 (which would bypass the ledger's state)", () => {
    for (const route of Object.values(UNIT_ROUTES)) expect(route).not.toMatch(/ \/api\/v1\//);
  });
});
