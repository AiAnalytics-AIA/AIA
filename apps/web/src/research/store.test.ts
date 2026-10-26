import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, type WorkingContent, type WorkingOpsSave, type WorkingSave } from "@/lib/api";
import { applyEdit, type WorkingEdit } from "@/lib/lead";
import { type Json, type ResearchProject, type Template, defaultsMerge } from "./model";
import { withItemIds } from "./item-ids";
import { t, tv } from "@/i18n/t";
import { type Analysis, FlushIncomplete, MAX_FLUSH_ROUNDS, ResearchStore, type ResearchState, SAVE_DEBOUNCE_MS, canonical, loadResearch, newResearch, originNotice, readWorkingContent, saveReason, submitWorkingDesign } from "./store";

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

  it("puts back a refused change to a locked Sociomap input and saves the person's other changes", async () => {
    const declared = { ...newResearch(TEMPLATE).project, sections: [{ id: "set_a", type: "object_battery", objects: ["A"], context_objects: ["A"] }] } as ResearchProject;
    const touchesSet = (b: Body) => JSON.stringify(b.content.sections) !== JSON.stringify(declared.sections);
    const { bodies, save } = aia((b, n) => (touchesSet(b) ? new ApiError(409, "sociomap_input_locked", "locked", null, { current_revision: 2 }) : saved(2 + n)));
    const store = new ResearchStore({ ...newResearch(TEMPLATE), project: declared, revision: 2, save: { kind: "saved" } }, "STU-1", { save });
    store.update(({ project }) => ({ project: { ...project, goal: "mine", sections: [{ id: "set_a", type: "object_battery", objects: ["A", "B"], context_objects: ["A"] }] } }));
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(store.get().save).toEqual({ kind: "locked", reverted: true });
    expect(store.get().project).toMatchObject({ goal: "mine", sections: declared.sections });
    // The rest saves on its own, with the locked set as AIA holds it: nothing waits on a click.
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(bodies).toHaveLength(2);
    expect(bodies[1].content).toMatchObject({ goal: "mine", sections: declared.sections });
    expect(store.get().save).toEqual({ kind: "saved" });
  });

  it("sends nothing more when a refused locked change cannot be put back", async () => {
    const { bodies, save } = aia(() => new ApiError(409, "sociomap_input_locked", "locked", null, { current_revision: 2 }));
    // Nothing was saved from this copy, so there is nothing to put back.
    const store = new ResearchStore(newResearch(TEMPLATE), "STU-1", { save });
    store.update(({ project }) => ({ project: { ...project, goal: "mine" } }));
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(store.get().save).toEqual({ kind: "locked", reverted: false });
    store.update(({ project }) => ({ project: { ...project, goal: "again" } }));
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS * 2);
    expect(bodies).toHaveLength(1);
    await expect(store.flush()).rejects.toMatchObject({ code: "sociomap_input_locked" });
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

  // F-STORE-1: AIA as it answers a save: a base that is not its current revision is stale.
  function server(start: number, during?: (n: number) => void) {
    let current = start;
    return aia((body, n) => {
      if (body.base_revision !== current) return new ApiError(409, "stale_revision", "saved elsewhere", null, { current_revision: current });
      current += 1;
      const revision = current;
      during?.(n);
      return new Promise<WorkingSave>((r) => setTimeout(() => r(saved(revision)), 100));
    });
  }

  it("serialises the saves of callers waiting behind one: each names the revision the one before returned", async () => {
    let store: ResearchStore | null = null;
    const edit = (goal: string) => store!.update(({ project }) => ({ project: { ...project, goal } }));
    // An edit lands while the second save is in flight: one of the two waiters saves it.
    const { bodies, save } = server(3, (n) => n === 2 && edit("c"));
    store = new ResearchStore({ ...newResearch(TEMPLATE), revision: 3, save: { kind: "saved" } }, "STU-1", { save });
    edit("a");
    const first = store.flush();
    edit("b");
    const waiters = [store.flush(), store.flush()];
    await vi.advanceTimersByTimeAsync(1000);
    await Promise.all([first, ...waiters]);
    expect(bodies.map((b) => [b.content.goal, b.base_revision])).toEqual([["a", 3], ["b", 4], ["c", 5]]);
    expect(store.get()).toMatchObject({ revision: 6, save: { kind: "saved" } });
    expect(store.get().project.goal).toBe("c");
  });

  it("saves an edit made during the flight in the same flush, which resolves only once it is saved", async () => {
    const { bodies, save } = server(3);
    const store = new ResearchStore({ ...newResearch(TEMPLATE), revision: 3, save: { kind: "saved" } }, "STU-1", { save });
    store.update(({ project }) => ({ project: { ...project, goal: "first" } }));
    let done = false;
    const flushed = store.flush("run").then(() => (done = true));
    await vi.advanceTimersByTimeAsync(50);
    store.update(({ project }) => ({ project: { ...project, goal: "second" } }));
    await vi.advanceTimersByTimeAsync(60);
    // The first save has answered, the second is in flight: not saved yet, so not resolved.
    expect(done).toBe(false);
    expect(store.get().save.kind).toBe("saving");
    await vi.advanceTimersByTimeAsync(100);
    await flushed;
    expect(bodies.map((b) => [b.content.goal, b.base_revision, b.reason])).toEqual([["first", 3, "run"], ["second", 4, "run"]]);
    expect(store.get()).toMatchObject({ revision: 5, save: { kind: "saved" } });
    // Nothing is sent again: the copy is saved.
    await store.flush();
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS * 2);
    expect(bodies).toHaveLength(2);
  });

  it("says when the copy kept changing through every round, and keeps the change waiting for its save", async () => {
    let store: ResearchStore | null = null;
    let editing = true;
    const { bodies, save } = server(3, (n) => editing && store!.update(({ project }) => ({ project: { ...project, goal: `edit ${n}` } })));
    store = new ResearchStore({ ...newResearch(TEMPLATE), revision: 3, save: { kind: "saved" } }, "STU-1", { save });
    store.update(({ project }) => ({ project: { ...project, goal: "edit 0" } }));
    const flushed = store.flush();
    const outcome = expect(flushed).rejects.toBeInstanceOf(FlushIncomplete);
    await vi.advanceTimersByTimeAsync(100 * MAX_FLUSH_ROUNDS);
    await outcome;
    expect(bodies.map((b) => b.base_revision)).toEqual(Array.from({ length: MAX_FLUSH_ROUNDS }, (_, i) => 3 + i));
    expect(store.get().save.kind).toBe("pending");
    expect(store.get().project.goal).toBe(`edit ${MAX_FLUSH_ROUNDS}`);
    // The waiting change is not dropped: its debounced save sends it.
    editing = false;
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS + 100);
    expect(bodies.at(-1)).toMatchObject({ base_revision: 3 + MAX_FLUSH_ROUNDS, content: { goal: `edit ${MAX_FLUSH_ROUNDS}` } });
    expect(store.get().save.kind).toBe("saved");
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

  it("says a change it could not save when let go while the person stays, never dropping it in silence", async () => {
    // The study closed under the store: the save of what was typed is refused.
    const { save } = aia(() => new ApiError(403, "study_closed", "closed", null));
    const store = new ResearchStore({ ...newResearch(TEMPLATE), revision: 2, save: { kind: "saved" } }, "STU-1", { save });
    store.update(({ project }) => ({ project: { ...project, goal: "Rozepsáno" } }));
    const refused: unknown[] = [];
    store.dispose((e) => refused.push(e));
    await vi.advanceTimersByTimeAsync(0);
    expect(refused).toHaveLength(1);
    expect((refused[0] as ApiError).code).toBe("study_closed");
    // A change already refused before the store was let go is said too.
    const again: unknown[] = [];
    const closed = new ResearchStore({ ...newResearch(TEMPLATE), revision: 2, save: { kind: "closed" } }, "STU-1", { save });
    closed.dispose((e) => again.push(e));
    await vi.advanceTimersByTimeAsync(0);
    expect(again).toHaveLength(1);
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

describe("edits saved as the vocabulary's operations (working-copy-edit-ops WCE3a, behind AIA_WEB_EDIT_OPS)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  type OpsBody = { ops: WorkingEdit[]; base_revision: number | null; reason: string };
  const atRevision = (revision = 2): ResearchState => ({ ...newResearch(TEMPLATE), revision, save: { kind: "saved" } });
  /** AIA applying each batch as the server does (the same rules: lib/lead.ts applyEdit, held to edit_ops.py). */
  function aiaOps(from: ResearchState, answer?: (body: OpsBody, n: number) => Error | Promise<never> | null, decorate: (p: Record<string, unknown>) => Record<string, unknown> = (p) => p) {
    let copy: { project: ResearchProject; analysis: Analysis | null } = { project: from.project, analysis: from.analysis };
    let revision = from.revision ?? 0;
    const batches: OpsBody[] = [];
    const applyOps = vi.fn(async (_studyId: string, body: OpsBody): Promise<WorkingOpsSave> => {
      batches.push(body);
      const refused = answer?.(body, batches.length);
      if (refused instanceof Error) throw refused;
      if (refused) return refused;
      for (const e of body.ops) {
        const r = applyEdit(copy, e);
        if ("refused" in r) throw new ApiError(409, "edit_refused", "refused", null, { refused: { 0: r.reason } });
        copy = r.content;
      }
      revision += 1;
      return { ...saved(revision), content: decorate(copy.project as unknown as Record<string, unknown>), analysis: copy.analysis };
    });
    return { batches, applyOps };
  }
  const title = (value: string): WorkingEdit => ({ op: "set_text", field: "title", value, why: "person" });
  const objective = (value: string): WorkingEdit => ({ op: "list_add", list: "plan.objectives", value, why: "person" });

  it("sends a stage's edits as one batch from the revision it holds, a field typed key by key as one edit", async () => {
    const start = atRevision();
    const { batches, applyOps } = aiaOps(start);
    const { bodies, save } = aia(() => saved(9));
    const store = new ResearchStore(start, "STU-1", { save, applyOps, editOps: true });
    expect(store.apply([title("A")], { reason: "brief" })).toBeNull();
    expect(store.apply([title("Al")], { reason: "brief" })).toBeNull();
    expect(store.apply([objective("Poznat")], { reason: "brief_objective_add" })).toBeNull();
    // Shown at once, as any change is.
    expect(store.get().project.title).toBe("Al");
    expect(store.get().save.kind).toBe("pending");
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(bodies).toHaveLength(0);
    expect(batches).toEqual([{ ops: [title("Al"), objective("Poznat")], base_revision: 2, reason: "brief_objective_add" }]);
    expect(store.get()).toMatchObject({ revision: 3, save: { kind: "saved" } });
  });

  it("keeps AIA's copy after a batch: the ids it gave what the batch added", async () => {
    const start = atRevision();
    const { applyOps } = aiaOps(start, undefined, (p) => ({ ...p, research_plan: { ...(p.research_plan as object), objective_ids: [{ id: "OBJ_server", bound: "Poznat" }] } }));
    const store = new ResearchStore(start, "STU-1", { save: aia(() => saved(9)).save, applyOps, editOps: true });
    store.apply([objective("Poznat")]);
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect((store.get().project.research_plan as Record<string, unknown>).objective_ids).toEqual([{ id: "OBJ_server", bound: "Poznat" }]);
    // What a submit names is exactly what AIA stores.
    expect(store.get().completed).toBe(false);
  });

  it("changes nothing for an edit that does not apply, and says why", () => {
    const store = new ResearchStore(atRevision(), "STU-1", { editOps: true });
    const before = store.get();
    expect(store.apply([title("A"), { op: "list_remove", list: "plan.objectives", old: "Žádný", why: "person" }])).toBe("unknown_item");
    expect(store.get()).toBe(before);
  });

  it("off, changes the copy the same way and saves it whole", async () => {
    const { applyOps } = aiaOps(atRevision());
    const { bodies, save } = aia(() => saved(3));
    const store = new ResearchStore(atRevision(), "STU-1", { save, applyOps });
    store.apply([title("A")]);
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(applyOps).not.toHaveBeenCalled();
    expect(bodies.map((b) => [b.content.title, b.base_revision])).toEqual([["A", 2]]);
  });

  it("saves the copy whole when a change outside the vocabulary waits beside the edits", async () => {
    const { applyOps } = aiaOps(atRevision());
    const { bodies, save } = aia(() => saved(3));
    const store = new ResearchStore(atRevision(), "STU-1", { save, applyOps, editOps: true });
    store.apply([title("A")]);
    store.update(({ project }) => ({ project: { ...project, problem_types: ["x"] } }));
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(applyOps).not.toHaveBeenCalled();
    expect(bodies.map((b) => [b.content.title, b.content.problem_types])).toEqual([["A", ["x"]]]);
    // Saved whole once, the edits after it go as operations again.
    store.apply([title("B")]);
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(applyOps).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["did not take the batch whole", new ApiError(409, "edit_refused", "refused", null, { refused: { 0: "unknown_item" } })],
    ["cannot carry it in the vocabulary", new ApiError(422, "validation_error", "too long", null)],
  ])("saves the copy whole when AIA %s", async (_why, refusal) => {
    const { batches, applyOps } = aiaOps(atRevision(), () => refusal);
    const { bodies, save } = aia(() => saved(3));
    const store = new ResearchStore(atRevision(), "STU-1", { save, applyOps, editOps: true });
    store.apply([title("A")]);
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(batches).toHaveLength(1);
    expect(bodies.map((b) => [b.content.title, b.base_revision])).toEqual([["A", 2]]);
    expect(store.get()).toMatchObject({ revision: 3, save: { kind: "saved" } });
  });

  it("applies edits made during a batch's flight again on AIA's copy and sends them next, from its revision", async () => {
    let release: () => void = () => {};
    const start = atRevision();
    const { batches, applyOps } = aiaOps({ ...start, project: { ...start.project, title: "A" } as ResearchProject, revision: 3 });
    // The first batch is held, then answered as AIA would answer it, with a mark of its own.
    let first = true;
    const held = vi.fn(async (studyId: string, body: OpsBody) => {
      if (!first) return applyOps(studyId, body);
      first = false;
      await new Promise<void>((r) => (release = r));
      return { ...saved(3), content: { ...(start.project as unknown as Record<string, unknown>), title: "A", server_mark: true }, analysis: null };
    });
    const store = new ResearchStore(start, "STU-1", { save: aia(() => saved(9)).save, applyOps: held, editOps: true });
    store.apply([title("A")]);
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    store.apply([objective("Poznat")]);
    release();
    await vi.advanceTimersByTimeAsync(0);
    // AIA's copy, with the edit made meanwhile on it, still owed.
    expect(store.get().project).toMatchObject({ title: "A", server_mark: true, research_plan: { objectives: ["Poznat"] } });
    expect(store.get()).toMatchObject({ revision: 3, save: { kind: "pending" } });
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(held).toHaveBeenCalledTimes(2);
    expect(batches.at(-1)).toMatchObject({ ops: [objective("Poznat")], base_revision: 3 });
  });

  it("saves the copy whole after a batch refused for a locked input, never the edits it put back", async () => {
    // A reworded research question whose link follows onto a declared rating question (the WCE8 edge):
    // AIA refuses the batch as locked, and the store puts the question back.
    const declared = {
      ...newResearch(TEMPLATE).project,
      research_plan: { ...newResearch(TEMPLATE).project.research_plan, research_questions: ["Kdo kupuje?"] },
      sections: [{ id: "s", type: "questions", questions: [{ id: "q1", text: "Jak často?", typ: "skala", skala: [1, 5], sociomap_rating: true, research_questions: ["Kdo kupuje?"] }] }],
    } as unknown as ResearchProject;
    const [project] = withItemIds(declared as unknown as Record<string, Json>, null);
    const start: ResearchState = { ...atRevision(), project: project as unknown as ResearchProject };
    const { applyOps } = aiaOps(start, () => new ApiError(409, "sociomap_input_locked", "locked", null, { current_revision: 2 }));
    const { bodies, save } = aia(() => saved(3));
    const store = new ResearchStore(start, "STU-1", { save, applyOps, editOps: true, itemIds: true });
    store.apply([{ op: "list_replace", list: "plan.research_questions", old: "Kdo kupuje?", value: "Kdo kupuje kávu?" }]);
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(store.get().save).toEqual({ kind: "locked", reverted: true });
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    // What is on screen now differs from AIA's copy by the reword alone, and goes whole.
    expect(applyOps).toHaveBeenCalledTimes(1);
    expect(bodies).toHaveLength(1);
  });

  it("settles ids after each edit made during a flight, so a reword beside an add keeps its links", async () => {
    const linked = {
      ...newResearch(TEMPLATE).project,
      research_plan: { ...newResearch(TEMPLATE).project.research_plan, research_questions: ["Kdo kupuje?"] },
      sections: [{ id: "s", type: "questions", questions: [{ id: "q1", text: "Jak často?", typ: "skala", skala: [1, 5], research_questions: ["Kdo kupuje?"] }] }],
    } as unknown as Record<string, Json>;
    const [project] = withItemIds(linked, null);
    const start: ResearchState = { ...atRevision(), project: project as unknown as ResearchProject };
    let release: () => void = () => {};
    const held = vi.fn(async () => {
      await new Promise<void>((r) => (release = r));
      return { ...saved(3), content: { ...(start.project as unknown as Record<string, unknown>), title: "A" }, analysis: null };
    });
    const store = new ResearchStore(start, "STU-1", { save: aia(() => saved(9)).save, applyOps: held, editOps: true, itemIds: true });
    store.apply([title("A")]);
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    store.apply([{ op: "list_replace", list: "plan.research_questions", old: "Kdo kupuje?", value: "Kdo kupuje kávu?" }]);
    store.apply([{ op: "list_add", list: "plan.research_questions", value: "Kde?" }]);
    release();
    await vi.advanceTimersByTimeAsync(0);
    const q = (store.get().project.sections as unknown as { questions: { research_questions: string[] }[] }[])[0]!.questions[0]!;
    expect(q.research_questions).toEqual(["Kdo kupuje kávu?"]);
  });

  it("keeps a failed batch owed and sends it again, before anything made since", async () => {
    let fail = true;
    const start = atRevision();
    const { batches, applyOps } = aiaOps(start, () => (fail ? new ApiError(500, "http_500", "Disk plný.", null) : null));
    const store = new ResearchStore(start, "STU-1", { save: aia(() => saved(9)).save, applyOps, editOps: true });
    store.apply([title("A")]);
    await vi.advanceTimersByTimeAsync(SAVE_DEBOUNCE_MS);
    expect(store.get().save).toEqual({ kind: "failed", message: "Disk plný." });
    store.apply([objective("Poznat")]);
    fail = false;
    await store.flush();
    expect(batches.at(-1)).toMatchObject({ ops: [title("A"), objective("Poznat")], base_revision: 2 });
    expect(store.get()).toMatchObject({ revision: 3, save: { kind: "saved" } });
  });
});
