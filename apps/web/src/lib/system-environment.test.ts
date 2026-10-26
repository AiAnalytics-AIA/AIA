import { describe, expect, it } from "vitest";

import type { PopulationRegistry, SettingsDocument } from "./api";
import { ENV_KEYS, diagnosticsText, environmentRows } from "./system-environment";

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
    const rows = environmentRows(DOC, REGISTRY, "a1c4e9f0123456789");
    expect(rows.map((r) => r.key)).toEqual([...ENV_KEYS]);
    expect(Object.fromEntries(rows.map((r) => [r.key, r.value]))).toEqual({
      environment: "develop", build: "a1c4e9f", api_version: "0.42.0", database: "postgresql", sign_in: "cognito",
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

  it("copies only the rows and the readiness count, unknown in words, nothing else", () => {
    const rows = environmentRows(DOC, null, null);
    const text = diagnosticsText(rows, (k) => k, "nezjištěno", { ready: 7, total: 9 }, "Připraveno");
    expect(text.split("\n")).toEqual([
      "environment: develop", "build: nezjištěno", "api_version: 0.42.0", "database: postgresql", "sign_in: cognito",
      "live: nezjištěno", "static: nezjištěno", "field_rules: v17", "Připraveno: 7/9",
    ]);
    expect(diagnosticsText(rows, (k) => k, "?", null, "Připraveno").endsWith("Připraveno: ?")).toBe(true);
    // A list value (the CORS origins) is not one of the rows: never copied.
    expect(text).not.toContain("https://a");
  });
});
