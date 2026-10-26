// Stav systému's Prostředí a verze (settings-redesign F21, prototype v99): what this deployment runs,
// read from what AIA already serves -- the settings document's deployment and population groups,
// the population registry, the API's build (GET /health) and the web's own (/config) -- and the
// diagnostics a person copies from it. No version number: AIA_VERSION is set by no deployment, so
// the settings document's "version" is the code's default, a stamped guess (review of #975).
// Pure. A value a read did not give is unknown, never a guess; nothing secret is ever named here,
// because only these named, non-secret values are read.

import type { PopulationRegistry, SettingsDocument } from "./api";

/** One line of Prostředí a verze: its label key and its value, null when no read gave it. */
export type EnvRow = { key: EnvKey; value: string | null };
export type EnvKey = "environment" | "build" | "api_build" | "database" | "sign_in" | "live" | "static" | "field_rules";

/** The rows in v99's order. */
export const ENV_KEYS: readonly EnvKey[] = ["environment", "build", "api_build", "database", "sign_in", "live", "static", "field_rules"];

/** A list the answer carries, or none: an answer of another shape is read as unread, never thrown on. */
const list = <T,>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);

/** A settings document item's value as text; a value that is not a plain one is not shown. */
function item(doc: SettingsDocument | null, group: string, key: string): string | null {
  const groups = list<SettingsDocument["groups"][number]>(doc?.groups);
  const found = list<{ key: string; value: unknown }>(groups.find((g) => g?.key === group)?.items).find((i) => i?.key === key);
  const v = found?.value;
  if (v === null || v === undefined) return null;
  if (typeof v === "string") return v.trim() || null;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  return null;
}

/** A commit as its first seven characters; anything but a non-empty string is unknown. */
const sha = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v.trim().slice(0, 7) : null);

/** The API's build from a GET /health answer of any shape: its build.sha, or unknown. */
export function healthBuild(health: unknown): string | null {
  const build = health && typeof health === "object" ? (health as { build?: unknown }).build : null;
  return build && typeof build === "object" ? sha((build as { sha?: unknown }).sha) : null;
}

/** The current version of the population of this kind, by its registry label; null when unread. */
function current(registry: PopulationRegistry | null, kind: "LIVE" | "STATIC"): string | null {
  const record = list<PopulationRegistry["populations"][number]>(registry?.populations).find((p) => p?.kind === kind);
  if (!record || typeof record.current_version_id !== "string") return null;
  const version = list<PopulationRegistry["versions"][number]>(registry?.versions).find((v) => v?.version_id === record.current_version_id);
  return (typeof version?.label === "string" && version.label) || record.current_version_id;
}

/**
 * The rows from what was read. `sign_in` is the identity provider; `build` the commit the web client
 * runs (/config) and `api_build` the commit the API process runs (GET /health's build.sha), each its
 * first seven characters, unknown when the process was not told.
 */
export function environmentRows(doc: SettingsDocument | null, registry: PopulationRegistry | null, webBuild: string | null, apiBuild: string | null = null): EnvRow[] {
  const provider = item(doc, "deployment", "identity_provider");
  const value: Record<EnvKey, string | null> = {
    environment: item(doc, "deployment", "env"),
    build: sha(webBuild),
    api_build: sha(apiBuild),
    database: item(doc, "deployment", "database_backend"),
    sign_in: provider,
    live: current(registry, "LIVE"),
    static: current(registry, "STATIC"),
    field_rules: item(doc, "population", "field_policy_version"),
  };
  return ENV_KEYS.map((key) => ({ key, value: value[key] }));
}

/**
 * The text "Kopírovat diagnostiku" copies: each row as "label: value", unknown said as such, then
 * how many readiness checks are ready when the smoke run was read. Only the rows above and the
 * counts: no token, no address, no e-mail.
 */
export function diagnosticsText(rows: EnvRow[], label: (key: EnvKey) => string, unknown: string, ready: { ready: number; total: number } | null, readyLabel: string): string {
  const lines = rows.map((r) => `${label(r.key)}: ${r.value ?? unknown}`);
  lines.push(`${readyLabel}: ${ready ? `${ready.ready}/${ready.total}` : unknown}`);
  return lines.join("\n");
}
