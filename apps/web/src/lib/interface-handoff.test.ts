import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import vm from "node:vm";
import { describe, expect, it } from "vitest";

import { applyHandoff, classicHref } from "./interface-handoff";
import { sha256Hex } from "./interface-skin";

const repo = join(process.cwd(), "../..");
const script = readFileSync(join(process.cwd(), "public/skin/handoff.js"), "utf8");

describe("applyHandoff", () => {
  const doc = Buffer.from("<html><head></head><body><p>x</p></body></html>");
  const sha = sha256Hex(doc);
  it("adds one script before the last </body> of the pinned document", () => {
    const r = applyHandoff(doc, sha, { enabled: true, version: "v1", pinnedSha256: sha });
    expect(r.outcome).toBe("added");
    expect(r.body.toString()).toBe('<html><head></head><body><p>x</p><script src="/skin/handoff.js?v=v1" data-aia-handoff="ADR-0014"></script></body></html>');
  });
  it("changes nothing when off or unpinned", () => {
    expect(applyHandoff(doc, sha, { enabled: false, version: null, pinnedSha256: sha })).toEqual({ outcome: "bypassed-disabled", body: doc });
    expect(applyHandoff(doc, sha, { enabled: true, version: null }).outcome).toBe("bypassed-hash-mismatch");
  });
});

describe("classicHref", () => {
  it("carries one instruction in the fragment", () => {
    expect(classicHref()).toBe("/");
    expect(classicHref({ open: "PRJ-DEMO-1" })).toBe("/#aia:open=PRJ-DEMO-1");
    expect(classicHref({ start: "simulation" })).toBe("/#aia:start=simulation");
    expect(classicHref({ go: "projects" })).toBe("/#aia:go=projects");
    expect(classicHref({ open: "PRJ-1", step: "questionnaire" })).toBe("/#aia:open=PRJ-1@questionnaire");
    expect(classicHref({ open: "PRJ-1", step: "Bad Step" })).toBe("/");
  });
  it("never builds an instruction from an id the script would refuse", () => {
    expect(classicHref({ open: "x'); alert(1)//" })).toBe("/");
  });
});

// The script itself, in a bare context standing in for the classic page.
function page(hash: string, stage = "ready") {
  const calls: string[] = [];
  const timers: (() => void)[] = [];
  const listeners: Record<string, () => void> = {};
  const win: Record<string, unknown> = {
    addEventListener: (type: string, f: () => void) => (listeners[type] = f),
    NPC_BOOT_STAGE: stage,
    location: { hash, pathname: "/", search: "" },
    history: { replaceState: () => calls.push("replaceState") },
    // As the classic one does: it ends on the project overview.
    openProject1785: (id: string) => {
      calls.push(`open:${id}`);
      (win.go as (r: string) => void)("project_overview");
    },
    startProductionResearch: () => calls.push("start:research"),
    startSimulationProduct1773: () => calls.push("start:simulation"),
    go: (r: string) => calls.push(`go:${r}`),
    switchProduct1776: (k: string) => calls.push(`switch:${k}`),
    openAssistant1791: () => calls.push("assistant"),
    createSupportBundle: (job: string) => calls.push(`support:${job}`),
  };
  const ctx = vm.createContext({ window: win, setTimeout: (f: () => void) => timers.push(f), console });
  vm.runInContext(script, ctx);
  return { calls, win, listeners, tick: () => timers.splice(0).forEach((f) => f()) };
}

describe("handoff.js", () => {
  it.each([
    ["#aia:open=PRJ-DEMO-COMPLETE-01", "open:PRJ-DEMO-COMPLETE-01", "go:project_overview"],
    ["#aia:start=research", "start:research"],
    ["#aia:start=simulation", "start:simulation"],
    ["#aia:go=projects", "go:projects"],
    ["#aia:switch=library", "switch:library"],
    ["#aia:assistant=open", "assistant"],
    ["#aia:support=bundle", "support:"],
  ])("%s calls the classic function once boot is ready", (hash, ...expected) => {
    expect(page(hash).calls).toEqual(["replaceState", ...expected]);
  });

  it.each([["#aia:go=renderHome"], ["#aia:start=anything"], ["#aia:switch=home"], ["#aia:assistant=close"], ["#aia:open=a b"], ["#aia:eval=x"], ["#projects"], [""]])(
    "ignores %j",
    (hash) => {
      expect(page(hash).calls.filter((c) => c !== "replaceState")).toEqual([]);
    },
  );

  it("waits for the boot to finish", () => {
    const p = page("#aia:open=PRJ-1", "bootstrap data");
    expect(p.calls).toEqual([]);
    p.tick();
    expect(p.calls).toEqual([]);
    p.win.NPC_BOOT_STAGE = "ready";
    p.tick();
    expect(p.calls).toEqual(["replaceState", "open:PRJ-1", "go:project_overview"]);
  });

  it("opens a project on a step instead of its overview, for a step the router knows", async () => {
    const p = page("#aia:open=PRJ-1@questionnaire");
    const go = p.win.go;
    await new Promise((r) => setTimeout(r, 0));
    // The overview is never drawn: it would paint over the step a moment later.
    expect(p.calls).toEqual(["replaceState", "open:PRJ-1", "go:questionnaire"]);
    expect(p.win.go).toBe(go);
    // A step the router does not know: the fragment is cleared, nothing is opened.
    const q = page("#aia:open=PRJ-1@render_home");
    await new Promise((r) => setTimeout(r, 0));
    expect(q.calls).toEqual(["replaceState"]);
    // Not the pattern at all: ignored before anything runs.
    const r = page("#aia:open=PRJ-1@renderHome");
    await new Promise((res) => setTimeout(res, 0));
    expect(r.calls).toEqual([]);
  });

  it("still lands on the step when opening never reaches the overview, and restores go", async () => {
    const p = page("");
    const go = p.win.go;
    p.win.openProject1785 = (id: string) => p.calls.push(`open:${id}`);
    (p.win.location as { hash: string }).hash = "#aia:open=PRJ-2@plan";
    p.listeners.hashchange();
    await new Promise((r) => setTimeout(r, 0));
    expect(p.calls).toEqual(["replaceState", "open:PRJ-2", "go:plan"]);
    expect(p.win.go).toBe(go);
  });

  it("acts on a hand-off link followed from the classic page itself", () => {
    const p = page("");
    (p.win.location as { hash: string }).hash = "#aia:go=data";
    p.listeners.hashchange();
    expect(p.calls).toEqual(["replaceState", "go:data"]);
  });

  it("allows exactly the routes the classic router knows", async () => {
    const html = readFileSync(join(repo, "legacy/npc-panel-18.6.6/app/ui_app.html"), "utf8");
    const capture = (await import(pathToFileURL(join(repo, "tools/ui_workbench/capture.mjs")).href)) as {
      routesFrom: (h: string) => { routes: string[] };
    };
    const listed = JSON.parse(script.match(/var ROUTES = (\[[\s\S]*?\]);/)![1].replace(/,\s*\]/, "]")) as string[];
    expect([...listed].sort()).toEqual([...capture.routesFrom(html).routes].sort());
  });
});
