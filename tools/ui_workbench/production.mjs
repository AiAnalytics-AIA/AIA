// The latency budgets of a timed journey are measured on a production build: `next dev` compiles on
// demand and runs dev-only checks, so on it a timed interaction measures the dev server (2026-10-22).
import { existsSync, readFileSync, readlinkSync } from "node:fs";
import { join } from "node:path";

/** An interaction: from the person's action to the screen that answers it. */
export const INTERACTION_BUDGET_MS = 400;
/** The cold first open of a research stage, from navigation start (Q78 (c), product owner 2026-10-22). */
export const COLD_OPEN_BUDGET_MS = 800;

/** Exits unless the workbench's web client is running as a production build (`up --production`). */
export function requireProductionBuild(repo, base) {
  const home = join(repo, "tmp/ui-workbench");
  const local = ["127.0.0.1:8780", "localhost:8780"].includes(new URL(base).host);
  let web = null;
  try {
    const pid = JSON.parse(readFileSync(join(home, "state.json"), "utf8")).web;
    // The standalone server renames its process (next-server); where it runs from does not change.
    web = readlinkSync(`/proc/${pid}/cwd`);
  } catch { /* no state, or the process is gone */ }
  if (local && existsSync(join(home, "production")) && web?.endsWith("apps/web/.next/standalone")) return;
  console.error("This journey times interactions; run it on the workbench's production build: python3 tools/ui_workbench/workbench.py down && python3 tools/ui_workbench/workbench.py up --production");
  process.exit(2);
}
