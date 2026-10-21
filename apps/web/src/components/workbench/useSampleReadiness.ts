"use client";

// Vzorek's readiness (plan artifact-sample SMP3-SMP5): the server's checks, support forecast,
// question outlook and persona sources for the design as it stands.
//
// Read on the working revision the person sees (working-copy-edit-ops WCE7b), never on a submitted
// Design Revision: a visit submits nothing, so it cannot move the design head and stale another
// stage's pending proposal (WCE5). An editor's change still waiting for its save is saved first, so
// the readiness is the copy's as shown; a copy whose save was refused (someone saved a newer one)
// is never read. It is read again whenever the working revision moves (a Lead's set_n accepted, a
// save from the hidden Dimenze screen), the previous answer kept on screen meanwhile.

import { useEffect, useState } from "react";

import { research, type WorkingReadiness } from "@/lib/api";
import { CONFLICT_MESSAGE, type ResearchStore } from "@/research/store";

export type SampleReadiness =
  | { kind: "loading" }
  | { kind: "failed"; message: string }
  /** No working revision to read readiness on: a study whose content was never saved. */
  | { kind: "none" }
  | { kind: "ready"; revision: number; readiness: WorkingReadiness };

type Deps = { readiness: (studyId: string, workingRevision: number) => Promise<WorkingReadiness> };

const DEPS: Deps = { readiness: (studyId, revision) => research.workingReadiness(studyId, revision) };

/** One read: the working revision the readiness is on, and the readiness. */
export async function loadSampleReadiness(store: ResearchStore, studyId: string, canEdit: boolean, deps: Deps = DEPS): Promise<SampleReadiness> {
  if (canEdit) {
    try {
      // A save, never a Design Revision: what is waiting is saved so the answer is the copy's.
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
      (e: unknown) => live && setState({ kind: "failed", message: e instanceof Error ? e.message : String(e) }),
    );
    return () => {
      live = false;
    };
  }, [store, studyId, canEdit, revision]);
  return state;
}
