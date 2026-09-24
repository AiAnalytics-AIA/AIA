// GET /api/bootstrap, read once per page: the unit's edition, its empty project
// template, its default provider and panel version, and the catalogues later
// steps read (audiences, subpanels). ~100 KB; the classic interface reads it on
// every load too.

import { unit } from "./client";
import type { Boot } from "./research/model";

export type BootInfo = Boot & { panelVersion: string; raw: Record<string, unknown> };

const isRecord = (x: unknown): x is Record<string, unknown> => typeof x === "object" && x !== null && !Array.isArray(x);

export function parseBoot(x: unknown): BootInfo {
  if (!isRecord(x) || !isRecord(x.empty_project)) throw new Error("Neočekávaná odpověď backendu: bootstrap bez empty_project");
  const panel = isRecord(x.panel) ? x.panel : {};
  return {
    empty_project: x.empty_project as Boot["empty_project"],
    ai_provider: typeof x.ai_provider === "string" ? x.ai_provider : undefined,
    panelVersion: typeof panel.version === "string" ? panel.version : "",
    raw: x,
  };
}

let cached: Promise<BootInfo> | null = null;

/** The page's one read of the bootstrap; a failure is not cached, so a retry reads again. */
export function loadBoot(fetchImpl?: typeof fetch): Promise<BootInfo> {
  cached ??= unit("bootstrap", { fetchImpl })
    .then(parseBoot)
    .catch((e: unknown) => {
      cached = null;
      throw e;
    });
  return cached;
}

/** Tests only. */
export function resetBootCache(): void {
  cached = null;
}
