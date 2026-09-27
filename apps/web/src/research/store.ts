// One research study's working content, loaded and saved in AIA (ADR 0018):
// GET /api/v1/studies/{id}/workspace/content, PUT to save. The flow is the
// classic interface's (openProject1785 @450866, scheduleServerSave @440078) --
// change at once, save after 1.8 s of quiet, flush before a run -- with two
// differences the unit never had. The save state is part of the store, so a
// screen can say "Neuloženo" and offer a retry. And every save names the revision
// it was edited from: when someone else saved in between, the API refuses it
// (409 stale_revision) and the store says so, instead of overwriting their work.

import { ApiError, type ContentState, type WorkingContent, workspace } from "@/lib/api";
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
  | { kind: "conflict"; current: number | null };

export type Analysis = { [k: string]: Json };

export type ResearchState = {
  /** The revision this copy is at: null until the study's first save. */
  revision: number | null;
  project: ResearchProject;
  analysis: Analysis | null;
  save: SaveState;
  /** Increments whenever a change invalidates the technical check (save(reason, true)). */
  checkEpoch: number;
};

export type LoadResult =
  | { kind: "research"; state: ResearchState; template: Template; contentState: ContentState; canEdit: boolean }
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

/** What a load of the study's working content means for its stages. */
export function readWorkingContent(r: WorkingContent): LoadResult {
  if (r.state === "AWAITING_MIGRATION") return { kind: "awaiting_migration" };
  const template = templateOf(r);
  if (r.state === "UNRECOVERABLE") return { kind: "unrecoverable", template, canEdit: r.can_edit, lineage: r.lineage || {} };
  if (r.state === "EMPTY" || !r.content) {
    return { kind: "research", state: newResearch(template), template, contentState: r.state, canEdit: r.can_edit };
  }
  return {
    kind: "research",
    template,
    contentState: r.state,
    canEdit: r.can_edit,
    state: {
      revision: r.revision,
      project: defaultsMerge(r.content, template),
      analysis: isRecord(r.analysis) ? (r.analysis as Analysis) : null,
      save: { kind: "saved" },
      checkEpoch: 0,
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
    private readonly opts: { onSaved?: (revision: number) => void; save?: SaveContent } = {},
  ) {
    this.state = initial;
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
    const r = change({ project: this.state.project, analysis: this.state.analysis });
    const blocked = this.state.save.kind === "conflict";
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
    if (s.save.kind === "conflict") throw new ApiError(409, "stale_revision", CONFLICT_MESSAGE, null);
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

/** The API's save reason: the classic reasons are already this shape; anything else is `autosave`. */
export function saveReason(reason: string): string {
  return /^[a-z0-9_:.-]{1,64}$/.test(reason) ? reason : "autosave";
}
