// One research project, loaded and saved the way the classic interface does it
// (openProject1785 @450866, scheduleServerSave @440078), with one difference:
// the classic save failure only reached the console. Here the save state is
// part of the store, so a screen can say "Neuloženo" and offer a retry.

import { UnitError, unit } from "../client";
import type { BootInfo } from "../boot";
import { type Json, type ResearchProject, defaultsMerge } from "./model";

export const SAVE_DEBOUNCE_MS = 1800;

export type SaveState =
  | { kind: "saved" }
  | { kind: "pending" }
  | { kind: "saving" }
  | { kind: "failed"; message: string };

export type Analysis = { [k: string]: Json };

export type ResearchState = {
  projectId: string | null;
  parentProjectId: string | null;
  revision: number | null;
  preferredProvider: string | null;
  project: ResearchProject;
  analysis: Analysis | null;
  save: SaveState;
  /** Increments whenever a change invalidates the technical check (save(reason, true)). */
  checkEpoch: number;
};

export type LoadResult =
  | { kind: "research"; state: ResearchState }
  | { kind: "demo" }
  | { kind: "simulation" };

const isRecord = (x: unknown): x is Record<string, unknown> => typeof x === "object" && x !== null && !Array.isArray(x);

/** POST /api/projects/load, then what openProject1785 does with a research project. */
export async function loadResearch(projectId: string, boot: BootInfo, fetchImpl?: typeof fetch): Promise<LoadResult> {
  const r = await unit("projectLoad", { body: { project_id: projectId }, timeoutMs: 30_000, fetchImpl });
  if (!isRecord(r)) throw new UnitError("Neočekávaná odpověď backendu: projekt", null);
  if (r.is_demo) return { kind: "demo" };
  if (r.project_type === "simulation") return { kind: "simulation" };
  const project = defaultsMerge(r.project, boot);
  const preferred = typeof r.preferred_provider === "string" ? r.preferred_provider : null;
  project.run_policy = { ...project.run_policy, provider: preferred || "claude_code_subscription", allow_provider_fallback: false };
  return {
    kind: "research",
    state: {
      projectId: typeof r.project_id === "string" ? r.project_id : projectId,
      parentProjectId: typeof r.parent_project_id === "string" ? r.parent_project_id : null,
      revision: typeof r.revision === "number" ? r.revision : null,
      preferredProvider: preferred,
      project,
      analysis: isRecord(r.analysis) ? (r.analysis as Analysis) : null,
      save: { kind: "saved" },
      checkEpoch: 0,
    },
  };
}

/** A new research project from the unit's template, not yet saved (resetProject). */
export function newResearch(boot: BootInfo): ResearchState {
  return {
    projectId: null,
    parentProjectId: null,
    revision: null,
    preferredProvider: null,
    project: defaultsMerge({}, boot),
    analysis: null,
    save: { kind: "saved" },
    checkEpoch: 0,
  };
}

type Listener = () => void;

/**
 * The live project of one screen tree. `update` applies a change at once and
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
    private readonly boot: BootInfo,
    private readonly opts: { fetchImpl?: typeof fetch; onIdAssigned?: (id: string) => void } = {},
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

  /** save(reason, invalidateCheck): change the project (and optionally the analysis), then autosave. */
  update(
    change: (s: { project: ResearchProject; analysis: Analysis | null }) => { project: ResearchProject; analysis?: Analysis | null },
    { reason = "autosave", invalidateCheck = true }: { reason?: string; invalidateCheck?: boolean } = {},
  ): void {
    const r = change({ project: this.state.project, analysis: this.state.analysis });
    this.set({
      ...this.state,
      project: r.project,
      analysis: r.analysis === undefined ? this.state.analysis : r.analysis,
      save: { kind: "pending" },
      checkEpoch: invalidateCheck ? this.state.checkEpoch + 1 : this.state.checkEpoch,
    });
    this.reason = reason;
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.autosave(), SAVE_DEBOUNCE_MS);
  }

  /** A debounced save: its failure is shown through `save`, not thrown. */
  private autosave(): void {
    this.flush().catch(() => {});
  }

  /** Save now, with the classic body; resolves when the unit has answered. */
  async flush(reason?: string): Promise<void> {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.inflight) await this.inflight;
    const s = this.state;
    const body = {
      project_id: s.projectId,
      parent_project_id: s.parentProjectId,
      project_type: "research",
      project: s.project,
      analysis: s.analysis,
      panel_version: this.boot.panelVersion,
      reason: reason ?? this.reason,
    };
    this.set({ ...this.state, save: { kind: "saving" } });
    this.inflight = (async () => {
      try {
        const r = (await unit("projectSave", { body, timeoutMs: 30_000, fetchImpl: this.opts.fetchImpl })) as {
          project_id?: unknown;
          revision?: unknown;
        };
        const id = typeof r.project_id === "string" && r.project_id ? r.project_id : this.state.projectId;
        const assigned = !this.state.projectId && id;
        this.set({
          ...this.state,
          projectId: id,
          revision: typeof r.revision === "number" ? r.revision : this.state.revision,
          // A change made while this save was in flight is still unsaved.
          save: this.state.project === s.project && this.state.analysis === s.analysis ? { kind: "saved" } : { kind: "pending" },
        });
        if (assigned && id) this.opts.onIdAssigned?.(id);
        if (this.state.save.kind === "pending" && !this.timer) {
          this.timer = setTimeout(() => this.autosave(), SAVE_DEBOUNCE_MS);
        }
      } catch (e) {
        this.set({ ...this.state, save: { kind: "failed", message: e instanceof Error ? e.message : String(e) } });
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

  dispose(): void {
    if (this.timer) clearTimeout(this.timer);
    this.listeners.clear();
  }
}
