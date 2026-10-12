// @vitest-environment jsdom
// What a population version is made of, on Společenská inteligence (population-operations
// P7d): it opens on LIVE, shows the weights, blocks and the adopted subpanels with 18.6.6's
// counts labelled as 18.6.6's, lists every field with what it may serve, and says plainly
// when the version keeps no dictionary -- calling no subpanel usable then.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t, tv } from "@/i18n/t";
import type { PopulationCharacteristics, PopulationFieldUse, PopulationRegistry } from "@/lib/api";
import { PopulationCharacteristicsSection } from "./PopulationCharacteristics";

vi.mock("next/navigation", () => ({ usePathname: () => "/app", useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const C = "aia.intelligence.population.characteristics";

const version = (id: string, label: string, status: PopulationRegistry["versions"][number]["status"]) => ({
  version_id: id, label, content_sha256: "a".repeat(64), row_count: 6, column_count: 4, parent_version_id: null, status,
  runtime_eligible: status !== "REGISTERED", companions_attached: true, imported_at: "2026-10-11T09:00:00Z",
  imported_by: "USR-operator", provenance: "fictional",
});

const registry: PopulationRegistry = {
  dataset_id: "cz_synthetic_population",
  contract_id: "c",
  versions: [version("DSV-static", "v_1", "STATIC_REFERENCE"), version("DSV-live", "v_4", "LIVE_CURRENT")],
  populations: [
    { population_id: "CZ_STATIC_REFERENCE", kind: "STATIC", current_version_id: "DSV-static", established_at: "", established_by: "" },
    { population_id: "CZ_LIVE", kind: "LIVE", current_version_id: "DSV-live", established_at: "", established_by: "" },
  ],
  history: [],
};

const answer = (u: PopulationFieldUse, allowed: boolean, reason: string, obligations: string[] = []) => ({ use: u, allowed, reason, obligations });

const subpanel = (key: string, name: string, usable: boolean | null, reason: string | null) => ({
  key, name, description: "fictional", filter: { field: "vek", minimum: 18, maximum: 29, equals: null },
  focus_domains: [], status: "ready", support_tier: "ROBUST",
  measured_by_18_6_6: { rows: 2785, weighted_population: 1340427, unique_core_donors: 983, effective_core_donors: 687.4, max_core_reuse: 12 },
  usable, reason,
});

const kept: PopulationCharacteristics = {
  version_id: "DSV-live",
  label: "v_4",
  dictionary_sha256: "b".repeat(64),
  dictionary_kept: true,
  weights: [
    { role: "default_current", column: "vaha_strukturalni_2025", is_default: true, expected_total: 8956290.3618, tolerance: 2 },
    { role: "party_2021_aggregate", column: "vaha_strana_2021_benchmark", is_default: false, expected_total: null, tolerance: null },
  ],
  blocks: [{ block: "population_anchor", fields: 1 }, { block: "provenance", fields: 1 }],
  fields: [
    {
      field: "vek", block: "population_anchor", source: "Census 2021", evidence_status: "POPULATION_ANCHOR", provenance_class: "OBSERVED",
      production_grade: "A", recommended_use: "PERSONA_OR_ANALYSIS_WITH_SCOPE", description: "Věk respondenta", persona_eligible: true,
      is_weight: false, derived: false,
      uses: [answer("AUDIENCE_FILTERING", true, "internal_use", ["DISCLOSE_SCOPE"]), answer("WEIGHTING", false, "not_a_weight_column")],
    },
    {
      field: "panel_row_id", block: "provenance", source: "build", evidence_status: "PROVENANCE_OR_CORE", provenance_class: "PROVENANCE",
      production_grade: "T", recommended_use: "AUDIT_ONLY", description: "Identifikátor řádku", persona_eligible: false,
      is_weight: false, derived: false, uses: [answer("AUDIENCE_FILTERING", false, "audit_only")],
    },
  ],
  subpanels: [subpanel("young_18_29", "Mladí 18–29", true, null), subpanel("students", "Studenti", false, "unknown_field")],
  subpanels_measured_on: "17.1.2",
  subpanels_measured_under_weight: "vaha_strukturalni_2025",
  subpanel_note: "Donor support je autoritativní.",
};

let answers: Record<string, PopulationCharacteristics> = {};
let urls: string[] = [];
beforeEach(() => {
  urls = [];
  answers = { "DSV-live": kept, "DSV-static": { ...kept, version_id: "DSV-static", label: "v_1", dictionary_kept: false, blocks: [], fields: [], subpanels: kept.subpanels.map((s) => ({ ...s, usable: null, reason: null })) } };
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "a@example.test" }));
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL) => {
      const u = String(url);
      urls.push(u);
      if (u === "/config") return new Response(JSON.stringify({ apiBase: "", aiRuntime: null }));
      const m = /^\/api\/v1\/population\/versions\/([^/]+)\/characteristics$/.exec(u);
      if (m) return new Response(JSON.stringify(answers[decodeURIComponent(m[1])]));
      return new Response("{}", { status: 404 });
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("a population version's characteristics", () => {
  it("opens on LIVE and shows weights, blocks, subpanels and fields", async () => {
    render(<PopulationCharacteristicsSection registry={registry} />);
    expect(await screen.findByText(t(`${C}.weightRole.default_current`))).toBeTruthy();
    expect(urls).toContain("/api/v1/population/versions/DSV-live/characteristics");
    expect(screen.getByText(t(`${C}.noTotal`))).toBeTruthy();
    expect(screen.getByText("Mladí 18–29")).toBeTruthy();
    // 18.6.6's counts, said as 18.6.6's.
    expect(screen.getAllByText(/^18\.6\.6: 2\s785 řádků/).length).toBe(2);
    const students = screen.getByText("Studenti").closest("li") as HTMLElement;
    expect(within(students).getByText(t(`${C}.usability.unusable`))).toBeTruthy();
    expect(within(students).getByText(t(`${C}.reason.unknown_field`))).toBeTruthy();
    expect(screen.getByText(tv(`${C}.shown`, { n: 2, total: 2 }))).toBeTruthy();
  });

  it("finds a field and says what it may serve", async () => {
    render(<PopulationCharacteristicsSection registry={registry} />);
    const search = await screen.findByLabelText(t(`${C}.search`));
    fireEvent.change(search, { target: { value: "věk" } });
    expect(screen.getByText(tv(`${C}.shown`, { n: 1, total: 2 }))).toBeTruthy();
    const vek = screen.getByText("vek").closest("li") as HTMLElement;
    expect(within(vek).getByText(t(`${C}.use.AUDIENCE_FILTERING`))).toBeTruthy();
    expect(within(vek).getByText(t(`${C}.obligation.DISCLOSE_SCOPE`))).toBeTruthy();
    expect(within(vek).getByText(t(`${C}.reason.not_a_weight_column`))).toBeTruthy();
  });

  it("says a version keeps no dictionary and calls no subpanel usable", async () => {
    render(<PopulationCharacteristicsSection registry={registry} />);
    await screen.findByText(t(`${C}.weightRole.default_current`));
    fireEvent.change(screen.getByLabelText(t(`${C}.version`)), { target: { value: "DSV-static" } });
    expect(await screen.findByText(t(`${C}.notKept`))).toBeTruthy();
    expect(screen.queryByText(t(`${C}.usability.usable`))).toBeNull();
    expect(screen.getAllByText(t(`${C}.usability.unknown`)).length).toBe(2);
    expect(screen.queryByLabelText(t(`${C}.search`))).toBeNull();
  });
});
