import { describe, expect, it } from "vitest";

import type { PopulationRegistry, SettingsDocument } from "./api";
import { ENV_KEYS, diagnosticsText, environmentRows, healthBuild } from "./system-environment";

const item = (key: string, value: unknown) => ({ key, value, control: "DEPLOYMENT", source: "X", unit: null });
const DOC = {
  groups: [
    { key: "deployment", items: [item("env", "develop"), item("version", "0.42.0"), item("database_backend", "postgresql"), item("identity_provider", "cognito"), item("cors_origins", ["https://a"])] },
    { key: "population", items: [item("field_policy_version", "v17")] },
  ],
} as unknown as SettingsDocument;
const REGISTRY = {
  dataset_id: "cz", contract_id: "c",
  versions: [{ version_id: "cz@sha256:aa", label: "v17_4_0" }, { version_id: "cz@sha256:bb", label: "v17_1_2" }],
  populations: [{ population_id: "cz-live", kind: "LIVE", current_version_id: "cz@sha256:aa" }, { population_id: "cz-static", kind: "STATIC", current_version_id: "cz@sha256:bb" }],
  history: [],
} as unknown as PopulationRegistry;

describe("Prostředí a verze (F21)", () => {
  it("reads every row from what AIA serves, in the prototype's order", () => {
    const rows = environmentRows(DOC, REGISTRY, "a1c4e9f0123456789", "9f8e7d6c5b4a");
    expect(rows.map((r) => r.key)).toEqual([...ENV_KEYS]);
    expect(Object.fromEntries(rows.map((r) => [r.key, r.value]))).toEqual({
      environment: "develop", build: "a1c4e9f", api_build: "9f8e7d6", database: "postgresql", sign_in: "cognito",
      live: "v17_4_0", static: "v17_1_2", field_rules: "v17",
    });
  });

  it("says unknown for every value a read did not give, never a guess", () => {
    const rows = environmentRows(null, null, null);
    expect(rows.every((r) => r.value === null)).toBe(true);
    // A population whose version the registry does not list names its id, not nothing.
    const partial = { ...REGISTRY, versions: [] } as unknown as PopulationRegistry;
    expect(environmentRows(DOC, partial, null).find((r) => r.key === "live")?.value).toBe("cz@sha256:aa");
  });

  it("reads an answer of another shape as unread, never throwing (review of #975)", () => {
    // A /population or /settings answer without its lists (an error body, an older shape).
    const shapeless = { detail: "nope" } as unknown as PopulationRegistry;
    const docless = { groups: [{ key: "deployment" }] } as unknown as SettingsDocument;
    const rows = environmentRows(docless, shapeless, null);
    expect(rows.every((r) => r.value === null)).toBe(true);
    const noVersions = { populations: [{ kind: "LIVE", current_version_id: "cz@sha256:aa" }] } as unknown as PopulationRegistry;
    expect(environmentRows(null, noVersions, null).find((r) => r.key === "live")?.value).toBe("cz@sha256:aa");
    expect(() => environmentRows({} as SettingsDocument, {} as PopulationRegistry, null)).not.toThrow();
  });

  it("reads the API's build from GET /health, a null or missing sha unknown, never the version default (review of #975)", () => {
    expect(healthBuild({ status: "ok", version: "0.1.0", build: { sha: "0123456789abcdef", built_at: null } })).toBe("0123456");
    expect(healthBuild({ status: "ok", version: "0.1.0", build: { sha: null, built_at: null } })).toBeNull();
    expect(healthBuild({ code: "http_404" })).toBeNull();
    expect(healthBuild(null)).toBeNull();
    // The settings document's version (the code's 0.1.0 where no deployment sets it) is no row.
    expect(environmentRows(DOC, null, null).map((r) => r.value)).not.toContain("0.42.0");
  });

  it("copies only the rows and the readiness count, unknown in words, nothing else", () => {
    const rows = environmentRows(DOC, null, null);
    const text = diagnosticsText(rows, (k) => k, "nezjištěno", { ready: 7, total: 9 }, "Připraveno");
    expect(text.split("\n")).toEqual([
      "environment: develop", "build: nezjištěno", "api_build: nezjištěno", "database: postgresql", "sign_in: cognito",
      "live: nezjištěno", "static: nezjištěno", "field_rules: v17", "Připraveno: 7/9",
    ]);
    expect(diagnosticsText(rows, (k) => k, "?", null, "Připraveno").endsWith("Připraveno: ?")).toBe(true);
    // A list value (the CORS origins) is not one of the rows: never copied.
    expect(text).not.toContain("https://a");
  });
});
