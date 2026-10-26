// @vitest-environment jsdom
// The Metodika area "Původ polí" (methodology-tab V1c) against fakes of its routes: the tables
// as the API serves them (src/lib/fixtures/methodology.json), and a fictional LIVE version's
// characteristics. Counts are the fields', a choice filters them, a field shows the policy's
// own answers; with no LIVE, or no kept dictionary, the counts are unknown, never zero.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetConfigCache } from "@/lib/auth";
import fixture from "@/lib/fixtures/methodology.json";
import { MethodologyPanel } from "./MethodologyPanel";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/app/settings" }));

const answer = (use: string, allowed: boolean, reason: string, obligations: string[] = []) => ({ use, allowed, reason, obligations });
const field = (name: string, description: string, over: Record<string, unknown>) => ({
  field: name, block: "core", source: "fictional", evidence_status: "CANONICAL_CORE", provenance_class: "OBSERVED",
  production_grade: "A", recommended_use: "PERSONA_OR_ANALYSIS_WITH_SCOPE", description, persona_eligible: true,
  is_weight: false, derived: false, materialized: false, uses: [], ...over,
});
const FIELDS = [
  field("vek", "Věk", { uses: [answer("CLIENT_MEASURED_CLAIM", true, "measured_evidence", ["DISCLOSE_SCOPE"])] }),
  field("phq9", "Deprese (PHQ-9)", {
    provenance_class: "CALIBRATED", production_grade: "C",
    recommended_use: "aggregate planning and persona background with modeled-value disclosure",
    uses: [answer("CLIENT_MEASURED_CLAIM", false, "rule_requires_modeled_disclosure"), answer("CLIENT_MODELLED_CLAIM", true, "disclosed_modelled_claim", ["DISCLOSE_MODELLED", "AGGREGATE_ONLY"])],
  }),
  field("donor_id", "Identifikátor dárce", { provenance_class: "PROVENANCE", production_grade: "T", recommended_use: "technical/provenance only", uses: [answer("AUDIENCE_FILTERING", false, "audit_only")] }),
];
const VERSION = { version_id: "v_fiction", label: "fikce 1.0", content_sha256: "a".repeat(64), row_count: 3, column_count: 3, parent_version_id: null, status: "ESTABLISHED", runtime_eligible: true, companions_attached: true, imported_at: "2026-10-01T00:00:00Z", owner_client_id: null };

function fakeApi({ live = true, kept = true }: { live?: boolean; kept?: boolean } = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => {
    const u = String(url).split("?")[0];
    const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
    if (u === "/config") return json({ apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", build: { sha: null } });
    if (u === "/api/v1/methodology") return json(fixture.modules);
    if (u === "/api/v1/methodology/field-policy") return json(fixture.field_policy);
    if (u === "/api/v1/population") return json({ dataset_id: "d", contract_id: "c", versions: [VERSION], populations: live ? [{ population_id: "p", kind: "LIVE", current_version_id: "v_fiction", established_at: "", established_by: "" }] : [], history: [] });
    if (u === "/api/v1/population/versions/v_fiction/characteristics") return json({ version_id: "v_fiction", label: "fikce 1.0", dictionary_sha256: "b".repeat(64), dictionary_kept: kept, weights: [], blocks: [], fields: kept ? FIELDS : [], subpanels: [] });
    const m = u.match(/^\/api\/v1\/methodology\/([^/]+)$/);
    const byPreset = m ? (fixture.details as Record<string, Record<string, unknown>>)[m[1]] : undefined;
    return byPreset ? json(Object.values(byPreset)[0]) : json({ code: "not_found", message: "no" }, 404);
  }));
}

async function openArea() {
  render(<MethodologyPanel />);
  fireEvent.click(await screen.findByRole("button", { name: "Původ polí: k čemu smí sloužit" }));
}

beforeEach(() => {
  resetConfigCache();
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "member@example.test", subject: "s" }));
});
afterEach(() => {
  cleanup();
  resetConfigCache();
  vi.unstubAllGlobals();
});

describe("Původ polí", () => {
  it("counts the in-force fields by origin and says which origins may reach a client as measured", async () => {
    fakeApi();
    await openArea();
    const origin = (name: string) => screen.findByRole("button", { name: new RegExp(`^${name}`) });
    expect((await origin("Změřeno")).textContent).toMatch(/1 polí.*smí jako měření/);
    expect((await origin("Kalibrováno")).textContent).toMatch(/1 polí.*jen jako modelované/);
    expect((await origin("Modelováno")).textContent).toMatch(/0 polí/);
    expect(screen.getByText(/Každé z 3 polí populace fikce 1.0/)).toBeTruthy();
  });

  it("filters the fields by a rule and shows a field's answers as the policy gave them", async () => {
    fakeApi();
    await openArea();
    fireEvent.click(await screen.findByRole("button", { name: /^Jen souhrnně/ }));
    const list = screen.getByRole("list", { name: "Pole populace" });
    expect(within(list).getAllByRole("button").map((b) => b.querySelector("span")?.textContent)).toEqual(["Deprese (PHQ-9)"]);
    const chosen = screen.getByRole("region", { name: "Deprese (PHQ-9)" });
    expect(within(chosen).getByText("Měřené tvrzení pro klienta").nextElementSibling?.textContent).toBe("nesmí");
    expect(chosen.textContent).toMatch(/povinnost: uvést, že je modelované, jen agregovaně/);
    fireEvent.click(screen.getByRole("button", { name: "Zrušit výběr" }));
    expect(within(list).getAllByRole("button")).toHaveLength(3);
  });

  it("says nothing is known, never zero, without a LIVE population or its dictionary", async () => {
    fakeApi({ live: false });
    await openArea();
    expect(await screen.findByText(/Populace v platnosti zatím není/)).toBeTruthy();
    expect((await screen.findByRole("button", { name: /^Změřeno/ })).textContent).toMatch(/nevíme/);
    cleanup();
    fakeApi({ kept: false });
    await openArea();
    expect(await screen.findByText(/Slovník této verze AIA zatím neuchovává/)).toBeTruthy();
    expect((await screen.findByRole("button", { name: /^Změřeno/ })).textContent).toMatch(/nevíme/);
  });
});
