import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import vm from "node:vm";
import { describe, expect, it, vi } from "vitest";
import { JSDOM } from "jsdom";

import { DIMENSION_RESEARCH_KEY, applyHandoff, classicHref, returnPath } from "./interface-handoff";
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
    expect(classicHref()).toBe("/classic");
    expect(classicHref({ open: "PRJ-DEMO-1" })).toBe("/classic#aia:open=PRJ-DEMO-1");
    expect(classicHref({ start: "simulation" })).toBe("/classic#aia:start=simulation");
    expect(classicHref({ go: "projects" })).toBe("/classic#aia:go=projects");
    expect(classicHref({ open: "PRJ-1", step: "questionnaire" })).toBe("/classic#aia:open=PRJ-1@questionnaire");
    expect(classicHref({ open: "PRJ-1", step: "Bad Step" })).toBe("/classic");
  });
  it("never builds an instruction from an id the script would refuse", () => {
    expect(classicHref({ open: "x'); alert(1)//" })).toBe("/classic");
  });
});

// The script itself, in a bare context standing in for the classic page.
function page(hash: string, stage = "ready", stash: Record<string, string> = {}) {
  const calls: string[] = [];
  const timers: (() => void)[] = [];
  const listeners: Record<string, () => void> = {};
  const stored = new Map<string, string>(Object.entries(stash));
  // The one element the script adds: a stand-in body that records what it appends.
  type El = { id: string; className: string; textContent: string; href: string; children: El[]; attrs: Record<string, string>; appendChild: (c: El) => void; setAttribute: (k: string, v: string) => void };
  const element = (): El => {
    const el: El = { id: "", className: "", textContent: "", href: "", children: [], attrs: {}, appendChild: (c) => void el.children.push(c), setAttribute: (k, v) => void (el.attrs[k] = v) };
    return el;
  };
  const body = element();
  const document = {
    body,
    createElement: () => element(),
    getElementById: (id: string) => body.children.find((c) => c.id === id) ?? null,
  };
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
    openDimensionResearch1793: (label: string) => calls.push(`dimension:${label}`),
    sessionStorage: {
      getItem: (k: string) => stored.get(k) ?? null,
      setItem: (k: string, v: string) => void stored.set(k, v),
      removeItem: (k: string) => void stored.delete(k),
    },
  };
  const ctx = vm.createContext({ window: win, document, setTimeout: (f: () => void) => timers.push(f), console });
  vm.runInContext(script, ctx);
  return { calls, win, listeners, body, tick: () => timers.splice(0).forEach((f) => f()) };
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

  it("says on the classic page that it is the classic interface, and leads back to where the person was", () => {
    const p = page("", "ready", { "aia:return": "/app/clients/CLI-1/research/STU-1/run" });
    const [bar] = p.body.children;
    expect(bar.id).toBe("aia-return-bar");
    expect(bar.children.map((c) => c.textContent)).toEqual(["Klasické rozhraní 18.6.6 · dočasně", "Zpět do AIA"]);
    expect(bar.children[1].href).toBe("/app/clients/CLI-1/research/STU-1/run");
    // Once only, however often a hand-off arrives on the same page.
    (p.win.location as { hash: string }).hash = "#aia:go=data";
    p.listeners.hashchange();
    expect(p.body.children.length).toBe(1);
  });

  it("leads back only to an AIA page, else to the client directory", () => {
    for (const bad of ["https://evil.example/app", "/app/../login", "javascript:alert(1)", "/studies", "//app"]) {
      expect(page("", "ready", { "aia:return": bad }).body.children[0].children[1].href, bad).toBe("/app/clients");
    }
    expect(page("").body.children[0].children[1].href).toBe("/app/clients");
    expect(returnPath("/app/clients/CLI-1?x=1")).toBe("/app/clients/CLI-1?x=1");
    expect(returnPath("/app/../x")).toBeNull();
    expect(returnPath("https://x/app")).toBeNull();
  });

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

  it("opens Deep Research for a proposed dimension with the label left in session storage, once", () => {
    const p = page("");
    const store = p.win.sessionStorage as { setItem: (k: string, v: string) => void; getItem: (k: string) => string | null };
    store.setItem(DIMENSION_RESEARCH_KEY, "Vztah k AI ve zdravotnictví");
    (p.win.location as { hash: string }).hash = "#aia:dimension=research";
    p.listeners.hashchange();
    expect(p.calls).toEqual(["replaceState", "dimension:Vztah k AI ve zdravotnictví"]);
    expect(store.getItem(DIMENSION_RESEARCH_KEY)).toBeNull();
    // Without a label nothing is opened.
    (p.win.location as { hash: string }).hash = "#aia:dimension=research";
    p.listeners.hashchange();
    expect(p.calls).toEqual(["replaceState", "dimension:Vztah k AI ve zdravotnictví", "replaceState"]);
    expect(classicHref({ dimension: "research" })).toBe("/classic#aia:dimension=research");
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


describe("product-only connection retirement", () => {
  function classic() {
    const dom = new JSDOM(`<body>
      <div id="keyState">Claude Code CHECK</div><div id="claudeState">CLAUDE</div>
      <button onclick="go('settings')">Claude Code</button>
      <button onclick="go('settings')">Nastavení</button>
      <button onclick="continueClaudeApi1790()">Pokračovat přes Claude API</button>
      <select onchange="setInlineAIProvider(this.value)"><option>Claude Code</option></select>
      <div class="hubState1783"><div>Claude Code CHECK</div><div>Research OS READY</div></div>
    </body>`);
    const go = vi.fn(), assign = vi.fn();
    const win = {
      NPC_BOOT_STAGE: "ready", go,
      location: { hash: "", pathname: "/classic", search: "", assign },
      addEventListener: vi.fn(), sessionStorage: { getItem: () => null },
      MutationObserver: dom.window.MutationObserver, alert: vi.fn(),
      renderSettings: vi.fn(), ensureClaudeReady1776: vi.fn(),
    };
    vm.runInContext(script, vm.createContext({ window: win, document: dom.window.document, console, setTimeout }));
    return { dom, win, go, assign };
  }
  it("redirects settings and keeps unrelated classic navigation working", () => {
    const { dom, win, go, assign } = classic();
    win.go("settings");
    expect(assign).toHaveBeenCalledWith("/app/settings");
    expect(go).not.toHaveBeenCalled();
    win.go("projects");
    expect(go).toHaveBeenCalledWith("projects");
    win.renderSettings();
    expect(assign).toHaveBeenCalledTimes(2);
    dom.window.close();
  });
  it("removes old connection controls and statuses, including later renders", async () => {
    const { dom, win } = classic();
    const doc = dom.window.document;
    expect((doc.querySelector("#keyState") as HTMLElement).hidden).toBe(true);
    expect([...doc.querySelectorAll("button")].filter((el) => !el.hidden).map((el) => el.textContent)).toEqual(["Nastavení"]);
    expect((doc.querySelector("select") as HTMLElement).hidden).toBe(true);
    expect([...doc.querySelectorAll(".hubState1783 > div")].filter((el) => !(el as HTMLElement).hidden).map((el) => el.textContent)).toEqual(["Research OS READY"]);
    const late = doc.createElement("button");
    late.setAttribute("onclick", "setupClaudeCode()");
    doc.body.appendChild(late);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(late.hidden).toBe(true);
    await expect(win.ensureClaudeReady1776()).resolves.toBe(false);
    expect(win.alert).toHaveBeenCalledWith(expect.stringContaining("nejsou převedeny do AIA"));
    dom.window.close();
  });
});
