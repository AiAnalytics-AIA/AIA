// HTTP fixtures for a research stage's working content in AIA (ADR 0018): the
// study's GET/PUT /api/v1/studies/STU-1/workspace/content, answered from memory,
// so a screen test loads a stored project and sees exactly what it saves.

import { readFileSync } from "node:fs";
import { join } from "node:path";

import type { ContentState } from "@/lib/api";

export const CONTENT_PATH = "/api/v1/studies/STU-1/workspace/content";
export const EMPTY_PROJECT: Record<string, unknown> = JSON.parse(
  readFileSync(join(process.cwd(), "src/research/fixtures/empty-project.json"), "utf8"),
);

export type SavedBody = { content: Record<string, unknown>; analysis: unknown; base_revision: number | null; reason: string };

/**
 * The workspace, holding `project` at `revision` (null: a new study). Returns the
 * answer for a path and method, or undefined when the path is not the workspace's.
 * Every save it accepts moves the revision on, as AIA does. `write` is the server's own
 * write of the working copy (an accepted proposal, ADR 0026 decision 6): a later GET -- the
 * stage's reload -- reads it, and `writes` keeps each.
 */
export function workspaceFixture(
  project: Record<string, unknown> | null,
  { revision = 3, analysis = null, state, canEdit = true }: { revision?: number; analysis?: unknown; state?: ContentState; canEdit?: boolean } = {},
) {
  let current = project ? revision : null;
  // What a GET answers: the stored project until the server itself writes the working copy.
  let held = { content: project, analysis, revision: project ? revision : null };
  const saves: SavedBody[] = [];
  const writes: { content: Record<string, unknown>; analysis: unknown }[] = [];
  const write = (content: Record<string, unknown>, next: unknown = held.analysis): number => {
    current = (current ?? 0) + 1;
    held = { content, analysis: next, revision: current };
    writes.push({ content, analysis: next });
    return current;
  };
  const answer = (path: string, method: string, body: unknown): unknown => {
    if (path !== CONTENT_PATH) return undefined;
    if (method === "PUT") {
      const b = body as SavedBody;
      saves.push(b);
      current = (current ?? 0) + 1;
      return { study_id: "STU-1", state: "NATIVE", revision: current, revision_id: `REV-${current}`, deduplicated: false };
    }
    const s: ContentState = state ?? (held.content ? "NATIVE" : "EMPTY");
    return {
      study_id: "STU-1",
      state: s,
      revision: held.revision,
      revision_id: held.revision === null ? null : `REV-${held.revision}`,
      content: held.content,
      analysis: held.analysis,
      template: EMPTY_PROJECT,
      saved_at: null,
      saved_by: null,
      can_edit: canEdit,
      lineage: {},
    };
  };
  return { answer, saves, write, writes, revision: () => current };
}

/** The config and the tab's session every API call needs (lib/api.ts). */
export function signedIn(): void {
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000 }));
}
