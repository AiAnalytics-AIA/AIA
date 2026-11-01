"use client";

// Vzorek's readiness (plan artifact-sample SMP3-SMP5): the server's checks, support forecast,
// question outlook and persona sources for the design as it stands.
//
// Read on the working revision the person sees (working-copy-edit-ops WCE7b), never on a submitted
// Design Revision: a visit submits nothing, so it cannot move the design head and stale another
// stage's pending proposal (WCE5). An editor's change still waiting for its save is saved first, so
// the readiness is the copy's as shown; nothing else is written; a copy whose save was refused
// (someone saved a newer one) is never read. It is read again whenever the working revision moves (a Lead's set_n accepted, a
// save from the hidden Dimenze screen), the previous answer kept on screen meanwhile.

import { useEffect, useState } from "react";

import { research, type WorkingReadiness } from "@/lib/api";
import { CONFLICT_MESSAGE, type ResearchStore } from "@/research/store";
import { errorText } from "@/lib/error-words";

export type SampleReadiness =
  | { kind: "loading" }
  | { kind: "failed"; message: string }
  /** No working revision to read readiness on: a study whose content was never saved. */
  | { kind: "none" }
  | { kind: "ready"; revision: number; readiness: WorkingReadiness };

type Deps = { readiness: (studyId: string, workingRevision: number) => Promise<WorkingReadiness> };

/** A change the person made that is not saved yet. */
const WAITING: ReadonlySet<string> = new Set(["pending", "saving", "failed"]);

const DEPS: Deps = { readiness: (studyId, revision) => research.workingReadiness(studyId, revision) };

/** One read: the working revision the readiness is on, and the readiness. */
export async function loadSampleReadiness(store: ResearchStore, studyId: string, canEdit: boolean, deps: Deps = DEPS): Promise<SampleReadiness> {
  const save = store.get().save.kind;
  if (save === "conflict") return { kind: "failed", message: CONFLICT_MESSAGE };
  // Only the person's own change still waiting is saved (a save, never a Design Revision), so the
  // answer is the copy's as shown. A new study nobody has touched, or a copy the template completed
  // on load, is read as stored: a visit writes nothing it was not already owed.
  if (canEdit && WAITING.has(save)) {
    try {
      await store.flush();
    } catch (e) {
      if (store.get().save.kind === "conflict") return { kind: "failed", message: CONFLICT_MESSAGE };
      throw e;
    }
  }
  const revision = store.get().revision;
  if (revision === null) return { kind: "none" };
  return { kind: "ready", revision, readiness: await deps.readiness(studyId, revision) };
}

/** `revision`: the working revision on screen; a new one reads readiness again. */
export function useSampleReadiness(store: ResearchStore, studyId: string, canEdit: boolean, revision: number | null): SampleReadiness {
  const [state, setState] = useState<SampleReadiness>({ kind: "loading" });
  useEffect(() => {
    let live = true;
    loadSampleReadiness(store, studyId, canEdit).then(
      (s) => live && setState(s),
      (e: unknown) => live && setState({ kind: "failed", message: errorText(e) }),
    );
    return () => {
      live = false;
    };
  }, [store, studyId, canEdit, revision]);
  return state;
}
