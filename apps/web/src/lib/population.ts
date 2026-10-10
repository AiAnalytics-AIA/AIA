// How the population registry reads on Společenská inteligence (population-operations P2).
// Read-only: nothing here, and nothing on the page, can import, establish or promote.

import type { PopulationRegistry, PopulationVersion } from "./api";

export type RegistrySummary = {
  /** The version the LIVE population points at now, or null: no LIVE yet. */
  live: PopulationVersion | null;
  /** The version the STATIC reference is pinned to, or null. */
  reference: PopulationVersion | null;
  /** Registered, never bound to a population: build inputs and candidates. */
  candidates: number;
  /** Newest first: what a person reads first is the latest move. */
  history: PopulationRegistry["history"];
};

export function summarize(registry: PopulationRegistry): RegistrySummary {
  const byId = new Map(registry.versions.map((v) => [v.version_id, v]));
  const pointedBy = (kind: "STATIC" | "LIVE") => {
    const p = registry.populations.find((x) => x.kind === kind);
    return p ? (byId.get(p.current_version_id) ?? null) : null;
  };
  return {
    live: pointedBy("LIVE"),
    reference: pointedBy("STATIC"),
    candidates: registry.versions.filter((v) => v.status === "REGISTERED").length,
    history: [...registry.history].sort((a, b) => b.promoted_at.localeCompare(a.promoted_at)),
  };
}

/** A content hash as a person compares it: the first twelve characters. */
export function shortSha(sha: string): string {
  return sha.slice(0, 12);
}

/** A version's label by id, or the id itself when the registry does not list it. */
export function labelOf(registry: PopulationRegistry, versionId: string | null): string {
  if (!versionId) return "—";
  return registry.versions.find((v) => v.version_id === versionId)?.label ?? versionId;
}
