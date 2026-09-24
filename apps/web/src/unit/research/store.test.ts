import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { BootInfo } from "../boot";
import { defaultsMerge } from "./model";
import { ResearchStore, SAVE_DEBOUNCE_MS, loadResearch, newResearch } from "./store";

const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/unit/research/fixtures/empty-project.json"), "utf8"));
const BOOT: BootInfo = { empty_project: EMPTY, ai_provider: "claude_code_subscription", panelVersion: "v17.1.2", raw: {} };

function unitStub(answers: Record<string, (body: unknown) => unknown | Promise<unknown>>) {
  const calls: { url: string; body: Record<string, unknown> }[] = [];
  const fetchImpl = vi.fn<typeof fetch>(async (url, init) => {
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ url: String(url), body });
    const a = answers[String(url)];
    const r = a ? await a(body) : {};
    if (r instanceof Response) return r;
    return new Response(JSON.stringify(r), { status: 200 });
  });
  return { calls, fetchImpl };
}

describe("loadResearch", () => {
  it("normalises the stored project and forces the preferred provider, as openProject1785 does", async () => {
    const { calls, fetchImpl } = unitStub({
      "/api/projects/load": () => ({ project_id: "PRJ-1", revision: 7, parent_project_id: null, project_type: "research", preferred_provider: "anthropic", project: { title: "Alfa" }, analysis: { objectives: ["a"] } }),
    });
    const r = await loadResearch("PRJ-1", BOOT, fetchImpl);
    expect(calls[0]).toEqual({ url: "/api/projects/load", body: { project_id: "PRJ-1" } });
    if (r.kind !== "research") throw new Error(r.kind);
    expect(r.state).toMatchObject({ projectId: "PRJ-1", revision: 7, preferredProvider: "anthropic", analysis: { objectives: ["a"] } });
    const expected = defaultsMerge({ title: "Alfa" }, BOOT);
    expect(r.state.project).toEqual({ ...expected, run_policy: { ...expected.run_policy, provider: "anthropic", allow_provider_fallback: false } });
  });

  it("says when the id is a DEMO or a simulation, which this flow does not open", async () => {
    const demo = unitStub({ "/api/projects/load": () => ({ is_demo: true }) });
    await expect(loadResearch("PRJ-DEMO", BOOT, demo.fetchImpl)).resolves.toEqual({ kind: "demo" });
    const sim = unitStub({ "/api/projects/load": () => ({ project_type: "simulation" }) });
    await expect(loadResearch("SIM-1", BOOT, sim.fetchImpl)).resolves.toEqual({ kind: "simulation" });
  });
});

describe("ResearchStore", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("saves once, 1.8 s after the last change, with the classic body", async () => {
    const { calls, fetchImpl } = unitStub({ "/api/projects/save": () => ({ project_id: "PRJ-9", revision: 1 }) });
    const assigned: string[] = [];
    const store = new ResearchStore(newResearch(BOOT), BOOT, { fetchImpl, onIdAssigned: (id) => assigned.push(id) });
    // A new project is not "saved": it has never been, and nothing is sent until it changes.
    expect(store.get().save.kind).toBe("new");
    store.update(({ project }) => ({ project: { ...project, goal: "a" } }), { reason: "brief" });
    await vi.advanceTimersByTimeAsync(1000);
    store.update(({ project }) => ({ project: { ...project, goal: "ab" } }), { reason: "brief" });
    expect(store.get().save.kind).toBe("pending");
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS - 1);
    expect(calls).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(1);
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("/api/projects/save");
    expect(Object.keys(calls[0].body)).toEqual(["project_id", "parent_project_id", "project_type", "project", "analysis", "panel_version", "reason"]);
    expect(calls[0].body).toMatchObject({ project_id: null, project_type: "research", panel_version: "v17.1.2", reason: "brief", project: { goal: "ab" } });
    expect(store.get()).toMatchObject({ projectId: "PRJ-9", revision: 1, save: { kind: "saved" } });
    expect(assigned).toEqual(["PRJ-9"]);
  });

  it("shows a failed save instead of hiding it, and saves again on flush", async () => {
    let fail = true;
    const { fetchImpl } = unitStub({
      "/api/projects/save": () => (fail ? new Response('{"error":"Disk plný."}', { status: 500 }) : { project_id: "PRJ-1", revision: 3 }),
    });
    const store = new ResearchStore({ ...newResearch(BOOT), projectId: "PRJ-1", revision: 2 }, BOOT, { fetchImpl });
    store.update(({ project }) => ({ project: { ...project, goal: "x" } }));
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(store.get().save).toEqual({ kind: "failed", message: "Disk plný." });
    fail = false;
    await store.flush("retry");
    expect(store.get()).toMatchObject({ revision: 3, save: { kind: "saved" } });
  });

  it("keeps a change made during a save pending, and saves it after", async () => {
    let release: () => void = () => {};
    let n = 0;
    const { calls, fetchImpl } = unitStub({
      "/api/projects/save": () => (++n === 1 ? new Promise((r) => (release = () => r({ project_id: "PRJ-1", revision: 1 }))) : { project_id: "PRJ-1", revision: 2 }),
    });
    const store = new ResearchStore({ ...newResearch(BOOT), projectId: "PRJ-1" }, BOOT, { fetchImpl });
    store.update(({ project }) => ({ project: { ...project, goal: "first" } }));
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    store.update(({ project }) => ({ project: { ...project, goal: "second" } }));
    release();
    await vi.advanceTimersByTimeAsync(0);
    expect(store.get().save.kind).toBe("pending");
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(calls.map((c) => (c.body.project as { goal: string }).goal)).toEqual(["first", "second"]);
    expect(store.get()).toMatchObject({ revision: 2, save: { kind: "saved" } });
  });

  it("counts the changes that invalidate the technical check, and not the others", () => {
    const store = new ResearchStore(newResearch(BOOT), BOOT, { fetchImpl: unitStub({}).fetchImpl });
    store.update(({ project }) => ({ project }), { invalidateCheck: false });
    store.update(({ project }) => ({ project }));
    expect(store.get().checkEpoch).toBe(1);
    store.dispose();
  });
});
