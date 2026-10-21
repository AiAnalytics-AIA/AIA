import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, type WorkingContent, type WorkingSave } from "@/lib/api";
import { type ResearchProject, type Template, defaultsMerge } from "./model";
import { t, tv } from "@/i18n/t";
import { ResearchStore, SAVE_DEBOUNCE_MS, canonical, loadResearch, newResearch, originNotice, readWorkingContent, saveReason, submitWorkingDesign } from "./store";

const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/research/fixtures/empty-project.json"), "utf8"));
const TEMPLATE: Template = { empty_project: EMPTY };

const content = (over: Partial<WorkingContent> = {}): WorkingContent => ({
  study_id: "STU-1", state: "NATIVE", revision: 7, revision_id: "REV-7", content: { title: "Alfa" }, analysis: { objectives: ["a"] },
  template: EMPTY, saved_at: null, saved_by: null, can_edit: true, lineage: {}, ...over,
});

type Body = { content: Record<string, unknown>; analysis: unknown; base_revision: number | null; reason: string };
function aia(answer: (body: Body, n: number) => WorkingSave | Promise<WorkingSave> | Error) {
  const bodies: Body[] = [];
  const save = vi.fn(async (_studyId: string, sent: { content: unknown; analysis: unknown; base_revision: number | null; reason: string }): Promise<WorkingSave> => {
    const body = sent as Body;
    bodies.push(body);
    const r = await answer(body, bodies.length);
    if (r instanceof Error) throw r;
    return r;
  });
  return { bodies, save };
}
const saved = (revision: number): WorkingSave => ({ study_id: "STU-1", state: "NATIVE", revision, revision_id: `REV-${revision}`, deduplicated: false });

describe("loadResearch", () => {
  it("completes the stored project with the template, and keeps its revision and analysis", async () => {
    const read = vi.fn(async () => content());
    const r = await loadResearch("STU-1", read);
    expect(read).toHaveBeenCalledWith("STU-1");
    if (r.kind !== "research") throw new Error(r.kind);
    expect(r.state).toMatchObject({ revision: 7, analysis: { objectives: ["a"] }, save: { kind: "saved" } });
    // AIA stamps no provider on load: its model route is its own configuration (ADR 0010, 0018).
    expect(r.state.project).toEqual(defaultsMerge({ title: "Alfa" }, TEMPLATE));
    expect(r.template).toEqual(TEMPLATE);
  });

  it("starts a new study from the template, unsaved", () => {
    const r = readWorkingContent(content({ state: "EMPTY", revision: null, revision_id: null, content: null, analysis: null }));
    if (r.kind !== "research") throw new Error(r.kind);
    expect(r.state).toEqual(newResearch(TEMPLATE));
    expect(r.state.save.kind).toBe("new");
  });

  it("names content that waits for migration, or was lost, instead of showing an empty document", () => {
    expect(readWorkingContent(content({ state: "AWAITING_MIGRATION", content: null }))).toEqual({ kind: "awaiting_migration" });
    const lost = readWorkingContent(content({ state: "UNRECOVERABLE", content: null, lineage: { outcome: "missing" } }));
    expect(lost).toEqual({ kind: "unrecoverable", template: TEMPLATE, canEdit: true, lineage: { outcome: "missing" } });
  });

  it("says where migrated content came from when the person needs to know", () => {
    // Recovered content is the last submitted design, not the last save.
    const recovered = readWorkingContent(content({ state: "RECOVERED", revision: 1, lineage: { outcome: "recovered", design_revision: 3 } }));
    if (recovered.kind !== "research") throw new Error(recovered.kind);
    expect(recovered.origin).toBe(tv("research.recoveredFrom", { revision: 3 }));
    expect(recovered.state.revision).toBe(1);
    expect(originNotice("RECOVERED", {})).toBe(t("research.recovered"));
    // Migrated content says so only when some of the brief's files did not come over.
    expect(originNotice("MIGRATED", { files_missing: ["ATT-1"], files_mismatched: ["ATT-2", "ATT-3"] })).toBe(
      tv("research.migratedFilesLeft", { count: 3 }),
    );
    expect(originNotice("MIGRATED", { files_missing: [], files_mismatched: [] })).toBeNull();
    const native = readWorkingContent(content());
    expect(native.kind === "research" && native.origin).toBe(null);
  });
});

describe("ResearchStore", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("saves once, 1.8 s after the last change, naming the revision it was edited from", async () => {
    const { bodies, save } = aia(() => saved(1));
    const revisions: number[] = [];
    const store = new ResearchStore(newResearch(TEMPLATE), "STU-1", { save, onSaved: (r) => revisions.push(r) });
    // A new study is not "saved": it has never been, and nothing is sent until it changes.
    expect(store.get().save.kind).toBe("new");
    store.update(({ project }) => ({ project: { ...project, goal: "a" } }), { reason: "brief" });
    await vi.advanceTimersByTimeAsync(1000);
    store.update(({ project }) => ({ project: { ...project, goal: "ab" } }), { reason: "brief" });
    expect(store.get().save.kind).toBe("pending");
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS - 1);
    expect(bodies).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(1);
    expect(bodies).toHaveLength(1);
    expect(save.mock.calls[0][0]).toBe("STU-1");
    expect(Object.keys(bodies[0])).toEqual(["content", "analysis", "base_revision", "reason"]);
    expect(bodies[0]).toMatchObject({ base_revision: null, reason: "brief", content: { goal: "ab" } });
    expect(store.get()).toMatchObject({ revision: 1, save: { kind: "saved" } });
    expect(store.saved).toBe(true);
    expect(revisions).toEqual([1]);
  });

  it("shows a failed save instead of hiding it, and saves again on flush", async () => {
    let fail = true;
    const { save } = aia(() => (fail ? new ApiError(500, "http_500", "Disk plný.", null) : saved(3)));
    const store = new ResearchStore({ ...newResearch(TEMPLATE), revision: 2 }, "STU-1", { save });
    store.update(({ project }) => ({ project: { ...project, goal: "x" } }));
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(store.get().save).toEqual({ kind: "failed", message: "Disk plný." });
    fail = false;
    await store.flush("retry");
    expect(store.get()).toMatchObject({ revision: 3, save: { kind: "saved" } });
  });

  it("stops saving over a newer revision saved elsewhere, and says which one it is", async () => {
    const { bodies, save } = aia(() => new ApiError(409, "stale_revision", "saved elsewhere", null, { current_revision: 5 }));
    const store = new ResearchStore({ ...newResearch(TEMPLATE), revision: 2 }, "STU-1", { save });
    store.update(({ project }) => ({ project: { ...project, goal: "mine" } }));
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(store.get().save).toEqual({ kind: "conflict", current: 5 });
    // Further edits stay in the page; nothing is sent until the study is reloaded.
    store.update(({ project }) => ({ project: { ...project, goal: "mine again" } }));
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS * 2);
    expect(bodies).toHaveLength(1);
    await expect(store.flush()).rejects.toMatchObject({ code: "stale_revision" });
    expect(bodies).toHaveLength(1);
  });

  it("never changes or saves content that may not change here, and says it is read-only", async () => {
    const { bodies, save } = aia(() => saved(9));
    const loaded = { ...newResearch(TEMPLATE), revision: 4 };
    const store = new ResearchStore(loaded, "STU-1", { save, readOnly: true });
    expect(store.get().save).toEqual({ kind: "readonly" });
    store.update(({ project }) => ({ project: { ...project, goal: "edited" } }));
    expect(store.get().project).toBe(loaded.project);
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS * 2);
    await store.flush("run");
    expect(bodies).toHaveLength(0);
    expect(store.get()).toMatchObject({ revision: 4, save: { kind: "readonly" } });
  });

  it("stops saving a study closed after it was opened, and never offers a retry that cannot succeed", async () => {
    const closed = new ApiError(403, "study_closed", "The study no longer accepts changes.", null, { reason: "study_closed" });
    const { bodies, save } = aia(() => closed);
    const store = new ResearchStore({ ...newResearch(TEMPLATE), revision: 2 }, "STU-1", { save });
    store.update(({ project }) => ({ project: { ...project, goal: "late" } }));
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(store.get().save).toEqual({ kind: "closed" });
    store.update(({ project }) => ({ project: { ...project, goal: "later" } }));
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS * 2);
    expect(bodies).toHaveLength(1);
    await expect(store.flush()).rejects.toMatchObject({ code: "study_closed" });
    expect(bodies).toHaveLength(1);
  });

  it("keeps a change made during a save pending, and saves it after from the new revision", async () => {
    let release: () => void = () => {};
    const { bodies, save } = aia((_b, n) => (n === 1 ? new Promise<WorkingSave>((r) => (release = () => r(saved(1)))) : saved(2)));
    const store = new ResearchStore(newResearch(TEMPLATE), "STU-1", { save });
    store.update(({ project }) => ({ project: { ...project, goal: "first" } }));
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    store.update(({ project }) => ({ project: { ...project, goal: "second" } }));
    release();
    await vi.advanceTimersByTimeAsync(0);
    expect(store.get().save.kind).toBe("pending");
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(bodies.map((b) => [b.content.goal, b.base_revision])).toEqual([["first", null], ["second", 1]]);
    expect(store.get()).toMatchObject({ revision: 2, save: { kind: "saved" } });
  });

  it("saves a change still waiting for its debounce when the person leaves the study", async () => {
    const { bodies, save } = aia(() => saved(3));
    const store = new ResearchStore({ ...newResearch(TEMPLATE), revision: 2 }, "STU-1", { save });
    store.update(({ project }) => ({ project: { ...project, ui_state: { ...project.ui_state, questionnaire_path: "choose" } } }), { reason: "questionnaire_path" });
    store.dispose();
    await vi.advanceTimersByTimeAsync(0);
    expect(bodies.map((b) => [b.reason, b.base_revision])).toEqual([["questionnaire_path", 2]]);
    // The debounce does not save it a second time.
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS * 2);
    expect(bodies).toHaveLength(1);
  });

  it("leaves nothing to save when nothing changed", async () => {
    const { bodies, save } = aia(() => saved(1));
    const store = new ResearchStore({ ...newResearch(TEMPLATE), revision: 2, save: { kind: "saved" } }, "STU-1", { save });
    store.dispose();
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS * 2);
    expect(bodies).toHaveLength(0);
  });

  it("counts the changes that invalidate the technical check, and not the others", () => {
    const store = new ResearchStore(newResearch(TEMPLATE), "STU-1", { save: aia(() => saved(1)).save });
    store.update(({ project }) => ({ project }), { invalidateCheck: false });
    store.update(({ project }) => ({ project }));
    expect(store.get().checkEpoch).toBe(1);
    store.dispose();
  });
});

describe("saveReason", () => {
  it("keeps the classic reasons and never sends one the API would refuse", () => {
    expect(saveReason("ai_analysis_1780")).toBe("ai_analysis_1780");
    expect(saveReason("native_ai_proposal_accepted")).toBe("native_ai_proposal_accepted");
    expect(saveReason("Něco jiného")).toBe("autosave");
    expect(saveReason("")).toBe("autosave");
  });
});

describe("submitWorkingDesign (ADR 0026 decision 5)", () => {
  const submitted = () => vi.fn(async (_s: string, content: unknown, stage: string, revision: number) => ({ revision_id: "REV-D", content, stage, revision }) as never);

  it("saves a copy the template completed on load before submitting it, so the design is a stored revision", async () => {
    // Content AIA wrote itself (the template, a fixture, a migration) is not a fixpoint of defaultsMerge.
    const stored = structuredClone(EMPTY) as Record<string, unknown>;
    const loaded = readWorkingContent(content({ content: stored, revision: 3 }));
    if (loaded.kind !== "research") throw new Error("not research");
    expect(canonical(loaded.state.project)).not.toBe(canonical(stored));
    expect(loaded.state.save).toEqual({ kind: "saved" });
    expect(loaded.state.completed).toBe(true);
    const { bodies, save } = aia(() => saved(4));
    const store = new ResearchStore(loaded.state, "STU-1", { save });
    const submit = submitted();
    await submitWorkingDesign(store, "STU-1", "run", submit);
    expect(bodies).toHaveLength(1);
    expect(bodies[0].base_revision).toBe(3);
    expect(canonical(bodies[0].content)).toBe(canonical(loaded.state.project));
    // The design names the revision that save wrote, and is exactly what it stored.
    expect(submit).toHaveBeenCalledExactlyOnceWith("STU-1", loaded.state.project, "run", 4);
    expect(store.get().completed).toBe(false);
  });

  it("submits a copy AIA holds exactly as it is without saving it again", async () => {
    const stored = defaultsMerge({ title: "Alfa" }, TEMPLATE) as unknown as Record<string, unknown>;
    const loaded = readWorkingContent(content({ content: stored, revision: 3 }));
    if (loaded.kind !== "research") throw new Error("not research");
    expect(loaded.state.completed).toBe(false);
    const { bodies, save } = aia(() => saved(4));
    const submit = submitted();
    await submitWorkingDesign(new ResearchStore(loaded.state, "STU-1", { save }), "STU-1", "run", submit);
    expect(bodies).toHaveLength(0);
    expect(submit).toHaveBeenCalledExactlyOnceWith("STU-1", loaded.state.project, "run", 3);
  });
});

describe("conflict", () => {
  it("holds a copy with its own change against a newer revision: nothing saves over it", async () => {
    const { bodies, save } = aia(() => saved(9));
    const loaded = readWorkingContent(content({ content: defaultsMerge({ title: "Alfa" }, TEMPLATE) as unknown as Record<string, unknown> }));
    if (loaded.kind !== "research") throw new Error("not research");
    const store = new ResearchStore(loaded.state, "STU-1", { save });
    store.update(({ project }) => ({ project: { ...project, goal: "Mine" } }));
    store.conflict(8);
    expect(store.get().save).toEqual({ kind: "conflict", current: 8 });
    expect(store.get().project.goal).toBe("Mine");
    await expect(store.flush()).rejects.toBeInstanceOf(ApiError);
    expect(bodies).toHaveLength(0);
  });
});

describe("reload", () => {
  const ready = (save: ReturnType<typeof aia>["save"]) => {
    const loaded = readWorkingContent(content({ content: defaultsMerge({ title: "Alfa" }, TEMPLATE) as unknown as Record<string, unknown> }));
    if (loaded.kind !== "research") throw new Error("not research");
    return new ResearchStore(loaded.state, "STU-1", { save });
  };

  it("replaces the copy with what AIA wrote when nothing changed since the caller's snapshot", async () => {
    const { save } = aia(() => saved(9));
    const store = ready(save);
    const since = store.get();
    const replaced = await store.reload(async () => content({ revision: 8, revision_id: "REV-8", content: { title: "Beta" } }), { since });
    expect(replaced).toBe(true);
    expect(store.get()).toMatchObject({ revision: 8, project: { title: "Beta" }, save: { kind: "saved" } });
  });

  it("keeps a change made after the snapshot: the copy in conflict with AIA's revision, nothing saved", async () => {
    vi.useFakeTimers();
    try {
      const { bodies, save } = aia(() => saved(9));
      const store = ready(save);
      const since = store.get();
      // Typed while AIA answered: the reload must not drop it, nor save it over revision 8.
      store.update(({ project }) => ({ project: { ...project, goal: "Mine" } }));
      const replaced = await store.reload(async () => content({ revision: 8, revision_id: "REV-8", content: { title: "Beta" } }), { since });
      expect(replaced).toBe(false);
      expect(store.get().project).toMatchObject({ title: "Alfa", goal: "Mine" });
      expect(store.get().save).toEqual({ kind: "conflict", current: 8 });
      await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS * 2);
      expect(bodies).toHaveLength(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps a waiting change's save when the read fails", async () => {
    vi.useFakeTimers();
    try {
      const { bodies, save } = aia(() => saved(9));
      const store = ready(save);
      store.update(({ project }) => ({ project: { ...project, goal: "Mine" } }));
      await expect(store.reload(async () => { throw new Error("offline"); })).rejects.toThrow("offline");
      await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS * 2);
      expect(bodies).toHaveLength(1);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("stable item ids (working-copy-edit-ops WCE1, behind AIA_WEB_STABLE_ITEM_IDS)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());
  type Plan = { research_plan: Record<string, unknown>; sections: { questions: Record<string, unknown>[] }[] };
  const plan = { research_questions: ["Jak cena mění zájem?", "Kdo kupuje?"], objectives: ["Zjistit cenovou citlivost"] };
  const sections = [{ id: "sec_a", type: "questions", title: "Úvod", questions: [{ id: "Q1", text: "Kupujete kávu?", typ: "vyber", kategorie: ["Ano", "Ne"], research_questions: ["Kdo kupuje?"] }] }];
  const stored = () => defaultsMerge({ title: "Alfa", research_plan: plan, sections }, TEMPLATE) as unknown as Record<string, unknown>;
  const rqIds = (p: unknown) => (((p as Plan).research_plan.research_question_ids ?? []) as { id: string }[]).map((e) => e.id);
  const asking = (questions: string[]) => ({ project }: { project: ResearchProject }) => ({
    project: { ...project, research_plan: { ...(project as unknown as Plan).research_plan, research_questions: questions } } as ResearchProject,
  });

  it("off, writes no id: what is loaded and saved is what AIA stores", async () => {
    const loaded = readWorkingContent(content({ content: stored() }));
    if (loaded.kind !== "research") throw new Error("not research");
    expect(loaded.state.completed).toBe(false);
    const { bodies, save } = aia(() => saved(8));
    const store = new ResearchStore(loaded.state, "STU-1", { save });
    store.update(asking(["Jak cena mění zájem?", "Kdo si kávu kupuje?"]));
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(JSON.stringify(bodies[0].content)).not.toContain("_ids");
    expect((bodies[0].content as unknown as Plan).sections[0].questions[0].research_questions).toEqual(["Kdo kupuje?"]);
  });

  it("on, gives stored content its ids on load, owed as a save before a submit", () => {
    const loaded = readWorkingContent(content({ content: stored() }), { itemIds: true });
    if (loaded.kind !== "research") throw new Error("not research");
    expect(rqIds(loaded.state.project)).toHaveLength(2);
    expect(loaded.state.completed).toBe(true);
  });

  it("on, keeps a reworded research question's id and carries its links to the new wording", async () => {
    const loaded = readWorkingContent(content({ content: stored() }), { itemIds: true });
    if (loaded.kind !== "research") throw new Error("not research");
    const { bodies, save } = aia(() => saved(8));
    const store = new ResearchStore(loaded.state, "STU-1", { save, itemIds: true });
    const before = rqIds(store.get().project);
    store.update(asking(["Jak cena mění zájem?", "Kdo si kávu kupuje?"]));
    expect(rqIds(store.get().project)).toEqual(before);
    expect((store.get().project as unknown as Plan).sections[0].questions[0].research_questions).toEqual(["Kdo si kávu kupuje?"]);
    // An added question is a new item; the others keep theirs.
    store.update(asking(["Nová?", "Jak cena mění zájem?", "Kdo si kávu kupuje?"]));
    const after = rqIds(store.get().project);
    expect(after.slice(1)).toEqual(before);
    expect(before).not.toContain(after[0]);
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(rqIds(bodies[0].content)).toEqual(after);
  });
});
