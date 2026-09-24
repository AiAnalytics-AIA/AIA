import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import vm from "node:vm";
import { describe, expect, it } from "vitest";

import {
  type DateWindow, type Filters, type ProjectRow, type Sort, type View, VIEWS, ago, cardText, filterProjects,
  jobBadges, providerLabel, stageLabel, statusLabel, statusSentence, statusTone,
} from "./projects";

// The port against the original (ADR 0014; CLAUDE.md, "its functions are
// fixtures"). Every classic function is extracted verbatim from the vendored
// ui_app.html by tools/ui_functions.py and run in a bare `vm` context -- no DOM,
// no network -- on the same synthetic rows, with the same frozen clock.

const repo = join(process.cwd(), "../..");
const show = (name: string) =>
  execFileSync("python3", [join(repo, "tools/ui_functions.py"), "show", name], { encoding: "utf8" });
const html = readFileSync(join(repo, "legacy/npc-panel-18.6.6/app/ui_app.html"), "utf8");
const escapeSource = html.slice(html.indexOf("E=s=>String(s??'')"), html.indexOf("}[c]));", html.indexOf("E=s=>String(s??'')")) + 6);

const NOW = Date.parse("2026-09-20T12:00:00Z");
const LEGACY = [
  "pmMatchesView1810", "pmText1810", "pmDateOk1810", "pmFiltered1810", "statusCzech1790", "stageHuman1797",
  "providerLabel1790", "humanStatusSentence1797", "pmAgo1810", "pmJobBadges1810", "statusChip1796",
  "miniInfo1796", "pmCard1810",
];

function legacyContext() {
  const ctx = vm.createContext({ PM1810: {} });
  // Date.now frozen; `new Date(x)` untouched.
  vm.runInContext(`const __RealDate=Date;Date=class extends __RealDate{static now(){return ${NOW}}};`, ctx);
  vm.runInContext(`const ${escapeSource};`, ctx);
  for (const name of LEGACY) vm.runInContext(show(name), ctx);
  return ctx;
}
const ctx = legacyContext();
const call = <T,>(expr: string, globals: Record<string, unknown> = {}): T => {
  for (const [k, v] of Object.entries(globals)) (ctx as Record<string, unknown>)[k] = v;
  return vm.runInContext(expr, ctx) as T;
};

const day = (n: number) => new Date(NOW - n * 86_400_000).toISOString().slice(0, 19);
const ROWS: ProjectRow[] = [
  { project_id: "PRJ-A", title: "Alfa", project_type: "research", status: "DRAFT", current_stage: "BRIEF", modified_at: day(1), created_at: day(40), progress_pct: 10, tags: ["cena"], revision: 2 },
  { project_id: "PRJ-B", title: "Beta", project_type: "simulation", status: "IN_PROGRESS", current_stage: "WORLDS", modified_at: day(0), created_at: day(3), progress_pct: 55, job_summary: { running: 2, queued: 1 }, preferred_provider: "anthropic" },
  { project_id: "PRJ-C", title: "Čeřen", project_type: "research", status: "WAITING_USER", current_stage: "QUESTIONNAIRE", modified_at: day(12), created_at: day(12), job_summary: { waiting_user: 1 }, pinned: true },
  { project_id: "PRJ-D", title: "delta", status: "WAITING_CREDITS", current_stage: "FIELDWORK", modified_at: day(45), created_at: day(80), job_summary: { waiting_ai: 3, failed: 1 }, preferred_provider: "claude_code" },
  { project_id: "PRJ-E", title: "Echo", status: "COMPLETED_WITH_WARNINGS", current_stage: "DELIVERY", modified_at: day(100), created_at: day(200), progress_pct: 100, archived: true },
  { project_id: "PRJ-F", title: "Foxtrot", status: "READY_TO_CONTINUE", current_stage: "SAMPLE_PLAN", modified_at: day(6), created_at: day(7), last_checkpoint: "AUDIENCE", population: "ČR 18+", client: "Fiktivní zadavatel" },
  { project_id: "PRJ-G", status: "WAITING_CAPACITY", current_stage: "CUSTOM_STEP", created_at: day(2), sample: 800 },
  { project_id: "PRJ-DEMO-1", title: "Ukázka jedna", project_type: "research", status: "COMPLETED", current_stage: "DELIVERY", is_demo: true, study_result: "Varianta B vede.", research_question: "Která varianta?", modified_at: day(400), progress_pct: 100 },
  { project_id: "PRJ-DEMO-2", title: "Ukázka dvě", project_type: "simulation", status: "COMPLETED", is_demo: true, takeaway: "Svět 3 je stabilní.", domain: "Fiktivní trh", modified_at: day(300) },
];

const VIEWS_ALL: View[] = [...VIEWS.map((v) => v.id), "ready"];
const SORTS: Sort[] = ["modified_desc", "created_desc", "title", "progress_desc"];
const DATES: DateWindow[] = ["all", "7", "30", "90"];

describe("filterProjects is pmFiltered1810", () => {
  const cases: Filters[] = [];
  for (const view of VIEWS_ALL) for (const sort of SORTS) for (const date of DATES) {
    cases.push({ view, sort, date, q: "", status: "all", provider: "all", stage: "all" });
  }
  cases.push(
    { view: "all", sort: "title", date: "all", q: "  CENA ", status: "all", provider: "all", stage: "all" },
    { view: "all", sort: "modified_desc", date: "all", q: "ukázka", status: "all", provider: "all", stage: "all" },
    { view: "all", sort: "modified_desc", date: "all", q: "", status: "WAITING_USER", provider: "all", stage: "all" },
    { view: "all", sort: "modified_desc", date: "all", q: "", status: "all", provider: "anthropic", stage: "all" },
    { view: "all", sort: "modified_desc", date: "30", q: "", status: "all", provider: "all", stage: "FIELDWORK" },
  );

  it.each(cases.map((f) => [JSON.stringify(f), f] as const))("%s", (_, f) => {
    const legacy = call<ProjectRow[]>("pmFiltered1810()", { PM1810: { ...f, rows: ROWS } }).map((x) => x.project_id);
    expect(filterProjects(ROWS, f, NOW).map((x) => x.project_id)).toEqual(legacy);
  });
});

describe("labels are the classic ones", () => {
  const statuses = ["DRAFT", "IN_PROGRESS", "WAITING_USER", "WAITING_CREDITS", "WAITING_CAPACITY", "READY_TO_CONTINUE",
    "COMPLETED", "COMPLETED_WITH_WARNINGS", "ARCHIVED", "FAILED", "RUNNING", "SOMETHING_NEW", "", undefined];
  const stages = ["BRIEF", "brief", "DEEP_RESEARCH", "DELIVERY", "WORLDS", "INTERPRETATION", "CUSTOM_STEP", "", undefined,
    "zatím bez checkpointu"];

  it("statusLabel = statusCzech1790", () => {
    for (const s of statuses) expect(statusLabel(s), String(s)).toBe(call("statusCzech1790(__s)", { __s: s }));
  });
  it("stageLabel = stageHuman1797", () => {
    for (const s of stages) expect(stageLabel(s), String(s)).toBe(call("stageHuman1797(__s)", { __s: s }));
  });
  it("providerLabel = providerLabel1790", () => {
    for (const p of ["anthropic", "claude_code", undefined]) expect(providerLabel(p)).toBe(call("providerLabel1790(__s)", { __s: p }));
  });
  it("statusSentence = humanStatusSentence1797", () => {
    for (const r of ROWS) expect(statusSentence(r), r.project_id).toBe(call("humanStatusSentence1797(__r)", { __r: r }));
  });
  it("ago = pmAgo1810", () => {
    for (const s of [undefined, "", day(0), day(1), day(2), day(30), day(31), day(365)]) {
      expect(ago(s, NOW), String(s)).toBe(call("pmAgo1810(__s)", { __s: s }));
    }
  });
  // Which classic class each tone replaces. Three tones share "warn": 18.6.6
  // does not tell running from waiting-on-you from waiting-on-the-world.
  it("statusTone refines statusChip1796's class, never contradicts it", () => {
    const cls = { done: "ok", running: "warn", you: "warn", world: "warn", fault: "bad", neutral: "" } as const;
    for (const s of statuses) {
      const chip = call<string>("statusChip1796(__s)", { __s: s });
      expect(chip, String(s)).toContain(`class="chip ${cls[statusTone(s)]}"`);
    }
  });
  it("jobBadges is pmJobBadges1810, as data", () => {
    const cls = { done: "ok", running: "ok", you: "warn", world: "warn", fault: "bad", neutral: "" } as const;
    for (const r of ROWS) {
      const legacy = call<string>("pmJobBadges1810(__r)", { __r: r });
      const mine = jobBadges(r).map((b) => `<span class="chip${cls[b.tone] ? " " + cls[b.tone] : ""}">${b.label}</span>`).join("");
      expect(mine, r.project_id).toBe(legacy);
    }
  });
});

describe("cardText carries every text pmCard1810 prints", () => {
  const escape = (s: string) => call<string>("E(__s)", { __s: s });
  it.each(ROWS.map((r) => [r.project_id, r] as const))("%s", (_, r) => {
    const card = call<string>("pmCard1810(__r)", { __r: r });
    const t = cardText(r);
    for (const key of ["kind", "title", "questionLabel", "question", "resultLabel", "result", "population", "client"] as const) {
      expect(card, key).toContain(escape(t[key]));
    }
    if (!r.is_demo) {
      expect(card).toContain(escape(t.safePoint));
      expect(card).toContain(`width:${t.progress}%`);
    }
  });
});
