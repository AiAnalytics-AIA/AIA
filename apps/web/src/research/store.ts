// One research study's working content, loaded and saved in AIA (ADR 0018):
// GET /api/v1/studies/{id}/workspace/content, PUT to save. The flow is the
// classic interface's (openProject1785 @450866, scheduleServerSave @440078) --
// change at once, save after 1.8 s of quiet, flush before a run -- with two
// differences the unit never had. The save state is part of the store, so a
// screen can say "Neuloženo" and offer a retry. And every save names the revision
// it was edited from: when someone else saved in between, the API refuses it
// (409 stale_revision) and the store says so, instead of overwriting their work.

import { t, tv } from "@/i18n/t";
import { ApiError, type ContentState, type DesignRevision, type WorkingContent, research, workspace } from "@/lib/api";
import { type Json, type ResearchProject, type Template, defaultsMerge } from "./model";

export const SAVE_DEBOUNCE_MS = 1800;

export type SaveState =
  /** Never saved, and nothing to save yet: a new study before its first change. */
  | { kind: "new" }
  | { kind: "saved" }
  | { kind: "pending" }
  | { kind: "saving" }
  | { kind: "failed"; message: string }
  /** Saved elsewhere since this copy was loaded: reload before editing on. */
  | { kind: "conflict"; current: number | null }
  /** Content that may not change here: a closed study, or a person who may only read. Nothing is saved. */
  | { kind: "readonly" }
  /** The study was closed after this copy was loaded: a change made here was refused, never saved. */
  | { kind: "closed" };

export type Analysis = { [k: string]: Json };

export type ResearchState = {
  /** The revision this copy is at: null until the study's first save. */
  revision: number | null;
  project: ResearchProject;
  analysis: Analysis | null;
  save: SaveState;
  /** Increments whenever a change invalidates the technical check (save(reason, true)). */
  checkEpoch: number;
  /**
   * True when this copy is not byte for byte the revision it names: the template's defaults
   * completed what AIA stored (`defaultsMerge`) and nothing has been saved since. Nothing is lost
   * and no save is shown as owed -- but a Design Revision must be exactly a stored revision
   * (ADR 0026 decision 5), so `submitWorkingDesign` saves such a copy before it submits.
   */
  completed?: boolean;
};

/** A document as AIA fingerprints it: key order does not matter, array order does. */
export function canonical(value: unknown): string {
  const normalize = (v: unknown): unknown => Array.isArray(v) ? v.map(normalize)
    : v && typeof v === "object" ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)).map(([k, x]) => [k, normalize(x)])) : v;
  return JSON.stringify(normalize(value));
}

export type LoadResult =
  | { kind: "research"; state: ResearchState; template: Template; contentState: ContentState; canEdit: boolean; origin: string | null }
  /** Bound to 18.6.6 before ADR 0018; the migration has not brought the content over yet. */
  | { kind: "awaiting_migration" }
  /** The 18.6.6 content was gone and nothing recoverable existed; a person may start again. */
  | { kind: "unrecoverable"; template: Template; canEdit: boolean; lineage: Record<string, unknown> };

const isRecord = (x: unknown): x is Record<string, unknown> => typeof x === "object" && x !== null && !Array.isArray(x);

export function templateOf(r: Pick<WorkingContent, "template">): Template {
  if (!isRecord(r.template)) throw new Error("Neočekávaná odpověď AIA: chybí šablona výzkumu");
  return { empty_project: r.template as Template["empty_project"] };
}

/** A new study from the template, not yet saved (resetProject). */
export function newResearch(template: Template): ResearchState {
  return { revision: null, project: defaultsMerge({}, template), analysis: null, save: { kind: "new" }, checkEpoch: 0 };
}

/**
 * What the stages say about content the 18.6.6 migration brought (ADR 0018), or null.
 * Recovered content is the study's last submitted design, not its last save, and a
 * person must know that before they build on it; migrated content says so only when
 * some of the brief's files did not come over (each is marked in the brief too).
 */
export function originNotice(state: ContentState, lineage: Record<string, unknown>): string | null {
  if (state === "RECOVERED") {
    const revision = lineage.design_revision;
    return typeof revision === "number" ? tv("research.recoveredFrom", { revision }) : t("research.recovered");
  }
  if (state === "MIGRATED") {
    const count = (key: string) => (Array.isArray(lineage[key]) ? (lineage[key] as unknown[]).length : 0);
    const left = count("files_missing") + count("files_mismatched");
    return left ? tv("research.migratedFilesLeft", { count: left }) : null;
  }
  return null;
}

/** What a load of the study's working content means for its stages. */
export function readWorkingContent(r: WorkingContent): LoadResult {
  if (r.state === "AWAITING_MIGRATION") return { kind: "awaiting_migration" };
  const template = templateOf(r);
  if (r.state === "UNRECOVERABLE") return { kind: "unrecoverable", template, canEdit: r.can_edit, lineage: r.lineage || {} };
  const origin = originNotice(r.state, r.lineage || {});
  if (r.state === "EMPTY" || !r.content) {
    return { kind: "research", state: newResearch(template), template, contentState: r.state, canEdit: r.can_edit, origin };
  }
  const project = defaultsMerge(r.content, template);
  return {
    kind: "research",
    template,
    contentState: r.state,
    canEdit: r.can_edit,
    origin,
    state: {
      revision: r.revision,
      project,
      analysis: isRecord(r.analysis) ? (r.analysis as Analysis) : null,
      save: { kind: "saved" },
      checkEpoch: 0,
      completed: canonical(project) !== canonical(r.content),
    },
  };
}

/** GET the study's working content and read it. `read` is injected in tests. */
export async function loadResearch(studyId: string, read: (studyId: string) => Promise<WorkingContent> = workspace.content): Promise<LoadResult> {
  return readWorkingContent(await read(studyId));
}

type SaveContent = typeof workspace.saveContent;

type Listener = () => void;

/**
 * The live working content of one study. `update` applies a change at once and
 * saves after SAVE_DEBOUNCE_MS of quiet, as the classic autosave does; `flush`
 * saves now (before a run starts, before leaving).
 */
export class ResearchStore {
  private state: ResearchState;
  private listeners = new Set<Listener>();
  private timer: ReturnType<typeof setTimeout> | null = null;
  private reason = "autosave";
  private inflight: Promise<void> | null = null;

  constructor(
    initial: ResearchState,
    private readonly studyId: string,
    private readonly opts: { onSaved?: (revision: number) => void; save?: SaveContent; readOnly?: boolean } = {},
  ) {
    this.state = opts.readOnly ? { ...initial, save: { kind: "readonly" } } : initial;
  }

  get = (): ResearchState => this.state;

  subscribe = (l: Listener): (() => void) => {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  };

  private set(next: ResearchState) {
    this.state = next;
    for (const l of this.listeners) l();
  }

  /** True once the study's content exists in AIA (its first save has happened). */
  get saved(): boolean {
    return this.state.revision !== null;
  }

  /** save(reason, invalidateCheck): change the project (and optionally the analysis), then autosave. */
  update(
    change: (s: { project: ResearchProject; analysis: Analysis | null }) => { project: ResearchProject; analysis?: Analysis | null },
    { reason = "autosave", invalidateCheck = true }: { reason?: string; invalidateCheck?: boolean } = {},
  ): void {
    // Content that may not change here is never changed, so nothing on screen reads as edited.
    if (this.opts.readOnly) return;
    const r = change({ project: this.state.project, analysis: this.state.analysis });
    const blocked = this.state.save.kind === "conflict" || this.state.save.kind === "closed";
    this.set({
      ...this.state,
      project: r.project,
      analysis: r.analysis === undefined ? this.state.analysis : r.analysis,
      // A copy that lost a conflict is not saved again until it is reloaded.
      save: blocked ? this.state.save : { kind: "pending" },
      checkEpoch: invalidateCheck ? this.state.checkEpoch + 1 : this.state.checkEpoch,
    });
    this.reason = reason;
    if (blocked) return;
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.autosave(), SAVE_DEBOUNCE_MS);
  }

  /** A debounced save: its failure is shown through `save`, not thrown. */
  private autosave(): void {
    this.flush().catch(() => {});
  }

  /** Save now; resolves when AIA has answered. A conflict is thrown, and kept in `save`. */
  async flush(reason?: string): Promise<void> {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.inflight) await this.inflight;
    const s = this.state;
    if (this.opts.readOnly) return;
    if (s.save.kind === "conflict") throw new ApiError(409, "stale_revision", CONFLICT_MESSAGE, null);
    if (s.save.kind === "closed") throw new ApiError(403, "study_closed", CLOSED_MESSAGE, null);
    const body = {
      content: s.project,
      analysis: s.analysis,
      base_revision: s.revision,
      reason: saveReason(reason ?? this.reason),
    };
    this.set({ ...this.state, save: { kind: "saving" } });
    this.inflight = (async () => {
      try {
        const r = await (this.opts.save ?? workspace.saveContent)(this.studyId, body);
        this.set({
          ...this.state,
          revision: r.revision,
          // What was sent is now stored as it is: no longer only the template's completion.
          completed: this.state.project === s.project ? false : this.state.completed,
          // A change made while this save was in flight is still unsaved.
          save: this.state.project === s.project && this.state.analysis === s.analysis ? { kind: "saved" } : { kind: "pending" },
        });
        this.opts.onSaved?.(r.revision);
        if (this.state.save.kind === "pending" && !this.timer) {
          this.timer = setTimeout(() => this.autosave(), SAVE_DEBOUNCE_MS);
        }
      } catch (e) {
        if (e instanceof ApiError && e.status === 409 && e.code === "stale_revision") {
          const current = typeof e.details.current_revision === "number" ? e.details.current_revision : null;
          this.set({ ...this.state, save: { kind: "conflict", current } });
        } else if (e instanceof ApiError && e.code === "study_closed") {
          // Closed by someone else while this copy was open: a retry can never succeed.
          this.set({ ...this.state, save: { kind: "closed" } });
        } else {
          this.set({ ...this.state, save: { kind: "failed", message: e instanceof Error ? e.message : String(e) } });
        }
        throw e;
      } finally {
        this.inflight = null;
      }
    })();
    await this.inflight;
  }

  /** Replace the project and analysis with what an AI step returned (no autosave of its own). */
  replace(next: { project?: ResearchProject; analysis?: Analysis | null }): void {
    this.set({
      ...this.state,
      project: next.project ?? this.state.project,
      analysis: next.analysis === undefined ? this.state.analysis : next.analysis,
    });
  }

  /**
   * AIA holds a newer revision (`current`) than this copy, and this copy holds a change of its
   * own: keep the change on screen, save nothing over the newer one, and say so -- the person
   * reloads, after copying what they typed. The same state a refused save leaves.
   */
  conflict(current: number | null): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    this.set({ ...this.state, save: { kind: "conflict", current } });
  }

  /**
   * Read the working copy again from AIA and replace this copy with it: after the server wrote it
   * (an accepted proposal, ADR 0026 decision 6), or after a conflict. A change still waiting for
   * its save is dropped, so the caller flushes first when it means to keep one.
   */
  async reload(read: (studyId: string) => Promise<WorkingContent> = workspace.content): Promise<void> {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.inflight) await this.inflight.catch(() => {});
    const loaded = readWorkingContent(await read(this.studyId));
    if (loaded.kind !== "research") throw new Error("Pracovní obsah studie se nepodařilo znovu načíst.");
    this.set({
      ...loaded.state,
      save: this.opts.readOnly ? { kind: "readonly" } : loaded.state.save,
      checkEpoch: this.state.checkEpoch + 1,
    });
  }

  /**
   * The person left the study: a change still waiting for its debounced save is
   * saved now (flush clears the timer) rather than dropped. Nothing is listening
   * any more, so if that save fails, no one is told; the next load shows the last
   * revision AIA stored.
   */
  dispose(): void {
    this.listeners.clear();
    if (this.timer || this.state.save.kind === "pending") this.flush().catch(() => {});
  }
}

export const CONFLICT_MESSAGE = "Obsah studie mezitím uložil někdo jiný. Načtěte ho znovu, než budete pokračovat.";
export const CLOSED_MESSAGE = "Studie je uzavřená a změny nepřijímá. Načtěte ji znovu.";

/** The API's save reason: the classic reasons are already this shape; anything else is `autosave`. */
export function saveReason(reason: string): string {
  return /^[a-z0-9_:.-]{1,64}$/.test(reason) ? reason : "autosave";
}

/**
 * Submit the design this copy holds as a Design Revision, naming the working revision it is
 * (ADR 0026 decision 5): saved first, so the revision named is exactly what is submitted. A change
 * typed while the save was in flight is saved too before anything is submitted.
 */
export async function submitWorkingDesign(
  store: ResearchStore,
  studyId: string,
  sourceStage: string,
  submit: typeof research.submitDesign = research.submitDesign,
): Promise<DesignRevision> {
  // A copy AIA already holds as it is needs no save: its revision is what is submitted. One the
  // template completed on load is not what AIA holds, so it is saved first (its own revision).
  const owed = () => store.get().revision === null || store.get().save.kind !== "saved" || !!store.get().completed;
  for (let i = 0; i < 2 && owed(); i++) {
    await store.flush(sourceStage === "run" ? "run" : undefined);
  }
  const s = store.get();
  if (s.revision === null) throw new Error("Pracovní obsah studie ještě není uložený.");
  return submit(studyId, s.project, sourceStage, s.revision);
}
