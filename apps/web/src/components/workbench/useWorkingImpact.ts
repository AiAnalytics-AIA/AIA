"use client";

// The working copy's impact per stage for the stage track (working-copy-edit-ops WCE7d): read from
// GET …/research/impact each time the copy's saved revision or the base moves. The last answer stays
// while the next is read, so the marks do not flicker on every save; another base drops it at once.
import { useEffect, useState } from "react";

import { research, type WorkingImpact } from "@/lib/api";
import type { ImpactBase } from "@/lib/working-impact";

export function useWorkingImpact(studyId: string, revision: number | null, base: ImpactBase | null): WorkingImpact | null {
  const [read, setRead] = useState<{ key: string; impact: WorkingImpact | null } | null>(null);
  const baseKey = base ? (base.id ?? "") : null;
  useEffect(() => {
    if (revision === null || baseKey === null) return;
    let live = true;
    const key = baseKey;
    research.workingImpact(studyId, revision, key || undefined).then(
      (impact) => live && setRead({ key, impact }),
      // A study with no Design Revision yet (404 design_revision), or any failure: nothing to say.
      () => live && setRead({ key, impact: null }),
    );
    return () => {
      live = false;
    };
  }, [studyId, revision, baseKey]);
  if (revision === null || baseKey === null || !read || read.key !== baseKey) return null;
  return read.impact;
}
