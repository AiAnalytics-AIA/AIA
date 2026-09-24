import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { describe, expect, it } from "vitest";

// The screen ledger (ADR 0014) must list every screen the classic interface's
// router knows, so no screen can be forgotten by the rebuild. The routes come
// from ui_app.html itself, the same parse the workbench capture uses.
//
// Read at run time, never imported: the web image is built from apps/web alone,
// and `next build` type-checks every file tsconfig includes.
type Screen = { id: string; classic: { route?: string }; area: string; status: string; react_path: string | null };
type Ledger = { areas: Record<string, string>; statuses: Record<string, string>; screens: Screen[] };
type Parse = { routes: string[]; aliases: Record<string, string> };

const repo = join(process.cwd(), "../..");
const html = readFileSync(join(repo, "legacy/npc-panel-18.6.6/app/ui_app.html"), "utf8");
const ledger = JSON.parse(readFileSync(join(repo, "docs/migration/interface-screens.json"), "utf8")) as Ledger;
const capture = (await import(pathToFileURL(join(repo, "tools/ui_workbench/capture.mjs")).href)) as {
  routesFrom: (html: string) => Parse;
};
const { routes, aliases } = capture.routesFrom(html);

describe("the interface screen ledger", () => {
  it("parses the router the classic interface ships", () => {
    for (const r of ["home", "projects", "brief", "results", "sim_run", "settings", "visualization"]) {
      expect(routes).toContain(r);
    }
    expect(aliases).toMatchObject({ demo: "home", sociomap: "visualization" });
  });

  it("lists every route, once", () => {
    const listed = ledger.screens.flatMap((s) => (s.classic.route ? [s.classic.route] : []));
    expect(new Set(listed).size).toBe(listed.length);
    expect([...listed].sort()).toEqual([...routes].sort());
  });

  it("gives every screen a known area and status, and a React path once it is not CLASSIC", () => {
    for (const s of ledger.screens) {
      expect(Object.keys(ledger.areas), s.id).toContain(s.area);
      expect(Object.keys(ledger.statuses), s.id).toContain(s.status);
      if (s.status !== "CLASSIC") expect(s.react_path, s.id).toMatch(/^\/app(\/|$)/);
    }
  });
});
