"use client";

// Vzorek's readiness (plan artifact-sample SMP3-SMP5): the server's checks, support forecast,
// question outlook and persona sources for the design as it stands, read once per visit.
//
// Until readiness can be read on a working revision (working-copy-edit-ops WCE7), it is read on a
// Design Revision, as Spuštění reads it: an editor's working copy is saved and submitted first
// (an unchanged copy answers its existing revision, so a visit adds none), a reader's is the
// latest revision. When WCE7 lands this reads the working revision instead and submits nothing.

import { useEffect, useState } from "react";

import { research, type Readiness } from "@/lib/api";
import { CONFLICT_MESSAGE, submitWorkingDesign, type ResearchStore } from "@/research/store";

export type SampleReadiness =
  | { kind: "loading" }
  | { kind: "failed"; message: string }
  /** No Design Revision to read readiness on: a reader of a study nobody has submitted. */
  | { kind: "none" }
  | { kind: "ready"; revision: number; readiness: Readiness };

type Deps = {
  submit: (store: ResearchStore, studyId: string) => Promise<{ revision_id: string; revision: number }>;
  revisions: (studyId: string) => Promise<{ revision_id: string; revision: number }[]>;
  readiness: (studyId: string, revisionId: string) => Promise<Readiness>;
};

const DEPS: Deps = {
  // Vzorek is the persona step's sample view: its submissions name that stage.
  submit: (store, studyId) => submitWorkingDesign(store, studyId, "persona"),
  revisions: research.revisions,
  readiness: research.readiness,
};

/** One read: the revision the readiness is on, and the readiness. */
export async function loadSampleReadiness(store: ResearchStore, studyId: string, canEdit: boolean, deps: Deps = DEPS): Promise<SampleReadiness> {
  let revision: { revision_id: string; revision: number };
  if (canEdit) {
    try {
      revision = await deps.submit(store, studyId);
    } catch (e) {
      // A copy someone else saved meanwhile never becomes the revision readiness is read on.
      if (store.get().save.kind === "conflict") return { kind: "failed", message: CONFLICT_MESSAGE };
      throw e;
    }
  } else {
    const latest = (await deps.revisions(studyId))[0];
    if (!latest) return { kind: "none" };
    revision = latest;
  }
  return { kind: "ready", revision: revision.revision, readiness: await deps.readiness(studyId, revision.revision_id) };
}

export function useSampleReadiness(store: ResearchStore, studyId: string, canEdit: boolean): SampleReadiness {
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
  }, [store, studyId, canEdit]);
  return state;
}
