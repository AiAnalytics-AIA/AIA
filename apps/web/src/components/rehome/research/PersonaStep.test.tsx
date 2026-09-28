// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DIMENSION_RESEARCH_KEY } from "@/lib/interface-handoff";
import { AGENTS_PATH, NATIVE_JOB_WAIT, NATIVE_TEST_TIMEOUT_MS, PARK_MESSAGE, approveProposal, nativeAgentFixture } from "./test-native-agents";
import { resetBootCache } from "@/unit/boot";
import { resetAudienceCatalog } from "@/unit/research/audience";
import { REQUEST_AI_DONE, REQUEST_DONE, REQUEST_EMPTY } from "@/unit/research/persona";
import { ResearchScreen } from "./ResearchScreen";
import { TEST_FRAME, stagePath } from "./test-frame";

// Native jobs need more than vitest's 5 s under CI load (test-native-agents.ts).
vi.setConfig({ testTimeout: NATIVE_TEST_TIMEOUT_MS });

const push = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/dimensions", useRouter: () => ({ push, replace: vi.fn() }) }));

const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/unit/research/fixtures/empty-project.json"), "utf8"));
const BOOT = {
  empty_project: EMPTY,
  ai_provider: "claude_code_subscription",
  panel: { version: "v17.1.2" },
  edition: { version: "18.6.6", claude_code_enabled: true },
  data_library: { active_dimensions: { vztah_k_ai: { label: "Vztah k AI" } } },
};
const CATALOG = {
  filterable_count: 3,
  categories: [{ id: "demography", label: "Demografie", filterable_count: 3 }, { id: "research_only", label: "Research-only", filterable_count: 0 }],
  factors: [],
};
const SUGGESTION = {
  dimensions: ["cena", "Úplně nová věc"],
  new_dimension_suggestions: [{ label: "Důvěra v AI", why: "Mění ochotu", evidence_needed: "průzkum", suggested_predictors: ["vek"], source_strategy: "document" }],
};

type Call = { url: string; body: Record<string, unknown> | null };
let calls: Call[] = [];
function unitStub(project: Record<string, unknown>, over: Record<string, (b: unknown) => unknown> = {}) {
  calls = [];
  const native = nativeAgentFixture((_action, baseline) => ({ project: baseline, proposal: { ...SUGGESTION, new_dimension_suggestions: SUGGESTION.new_dimension_suggestions.map((s) => ({ ...s, evidence_needed: [s.evidence_needed] })) }, dimensions: [], new_dimension_suggestions: SUGGESTION.new_dimension_suggestions }), over);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ url: u, body });
      const answers: Record<string, (b: unknown) => unknown> = {
        "/api/bootstrap": () => BOOT,
        "/api/projects/load": () => ({ project_id: "PRJ-1", revision: 3, project_type: "research", project, analysis: null }),
        "/api/projects/save": () => ({ project_id: "PRJ-1", revision: 4 }),
        "/api/providers/claude-code/status": () => ({ ok: true }),
        "/api/audience/dimensions": () => CATALOG,
        "/api/persona/suggest": () => ({ job_id: "JOB-S" }),
        "/api/job": () => ({ state: "done", result: SUGGESTION }),
        "/api/library/dimension/request": () => ({ dimension_id: "DIM-1", proposal_id: "PROP-1" }),
        "/api/library": () => ({ summary: { active_dimensions: { vztah_k_ai: { label: "Vztah k AI" }, nova: { label: "Nová z knihovny" } } } }),
        ...over,
      };
      const answer = native(u.split("?")[0], init?.method ?? "GET", body) ?? answers[u.split("?")[0]]?.(body) ?? {};
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
}
const posted = (path: string) => calls.filter((c) => c.url.split("?")[0] === path && (!path.startsWith("/api/v1/") || c.body !== null));
type Saved = { project: Record<string, unknown> & { persona_dimensions: { approved: string[] } }; reason: string };
const lastSave = () => posted("/api/projects/save").at(-1)?.body as Saved;
const savedWith = (reason: string) => waitFor(() => expect(lastSave()?.reason).toBe(reason), { timeout: 4000 });
const PLANNED = { research_plan: { recommended_topics: ["zdraví", "média"] } };

beforeEach(() => {
  resetBootCache();
  resetAudienceCatalog();
  push.mockReset();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Dimenze", () => {
  it("draws the fixed base, the recommended dimensions, and the catalogue with the library's", async () => {
    unitStub(PLANNED);
    render(<ResearchScreen projectId="PRJ-1" step="persona" frame={TEST_FRAME} />);
    expect(await screen.findByRole("heading", { name: "Sociodemografie a reprezentativní výběr" })).toBeTruthy();
    // No approval yet: the recommended set is drawn (OI-54).
    expect(screen.getByRole("button", { name: "Odebrat dimenzi Zdraví" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Odebrat dimenzi Média a informační chování" })).toBeTruthy();
    const row = screen.getByRole("button", { name: /Vztah k AI/ });
    expect(row.textContent).toContain("Data Library");
    expect(screen.getByRole("button", { name: /^Zdraví/ }).textContent).toContain("doporučeno pro tento projekt");
    fireEvent.change(screen.getByLabelText("Hledat dimenzi"), { target: { value: "knihovna" } });
    expect(screen.queryByRole("button", { name: /^Zdraví/ })).toBeNull();
    fireEvent.change(screen.getByLabelText("Hledat dimenzi"), { target: { value: "AI" } });
    expect(screen.getByRole("button", { name: /Vztah k AI/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Další · kontrola" })).toBeTruthy();
  });

  it("adds and removes a dimension; removing the last brings the recommended back (OI-54)", async () => {
    unitStub({ ...PLANNED, persona_dimensions: { approved: ["cena"] } });
    render(<ResearchScreen projectId="PRJ-1" step="persona" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /^Politické postoje/ }));
    await savedWith("dimension_catalog_add");
    expect(lastSave().project.persona_dimensions.approved).toEqual(["cena", "politika"]);
    fireEvent.click(screen.getByRole("button", { name: "Odebrat dimenzi Politické postoje" }));
    fireEvent.click(screen.getByRole("button", { name: "Odebrat dimenzi Cena / value for money" }));
    await savedWith("dimension_catalog_remove");
    expect(lastSave().project.persona_dimensions.approved).toEqual([]);
    // The classic draws the refill at once, and the next change saves it.
    expect(screen.getByRole("button", { name: "Odebrat dimenzi Zdraví" })).toBeTruthy();
    expect(screen.queryByText("Zatím není vybraná žádná volitelná dimenze.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Použít doporučené" }));
    await savedWith("persona_autofill");
    expect(lastSave().project.persona_dimensions.approved).toEqual(["zdravi", "media"]);
  }, 20_000);

  it("reviews new dimensions without automatically approving them", async () => {
    unitStub({ ...PLANNED, persona_dimensions: { approved: ["cena"] } });
    render(<ResearchScreen projectId="PRJ-1" step="persona" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "Co už panel umí popsat a segmentovat" });
    fireEvent.click(screen.getByRole("button", { name: "AI doporučí" }));
    await approveProposal();
    expect(await screen.findByRole("heading", { name: "AI navrhuje doplnit nové dimenze" }, NATIVE_JOB_WAIT)).toBeTruthy();
    expect(posted(AGENTS_PATH)[0].body).toMatchObject({ action: "suggest_dimensions" });
    expect(posted("/api/persona/suggest")).toEqual([]);
    await savedWith("native_ai_proposal_accepted");
    // Existing researcher choices survive; unsupported dimensions are proposals.
    expect(lastSave().project.persona_dimensions.approved).toEqual(["cena"]);
    expect(screen.queryByRole("button", { name: "Odebrat dimenzi uplne_nova_vec" })).toBeNull();
    expect(screen.getByText("Mění ochotu · evidence: průzkum")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Založit v Data Library" }));
    expect(await screen.findByText(REQUEST_AI_DONE)).toBeTruthy();
    expect(posted("/api/library/dimension/request")[0].body).toMatchObject({ label: "Důvěra v AI", source_strategy: "document", rationale: "Mění ochotu", origin: "claude" });
    expect(screen.getByText("Důvěra v AI · čeká na evidenci")).toBeTruthy();
  }, 20_000);

  it("parks the native job when the governed runtime is unavailable", async () => {
    unitStub(PLANNED, { "native/job": () => ({ status: "WAITING_PROVIDER", is_terminal: false, needs_attention: true, steps: [{ error_message: PARK_MESSAGE }], run_id: "RUN-A" }) });
    render(<ResearchScreen projectId="PRJ-1" step="persona" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "AI doporučí" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(posted("/api/persona/suggest").length).toBe(0);
  });

  it("requests a dimension the system does not have: refused when empty, recorded, the library read again", async () => {
    unitStub(PLANNED);
    render(<ResearchScreen projectId="PRJ-1" step="persona" frame={TEST_FRAME} />);
    const input = await screen.findByLabelText("Název dimenze");
    fireEvent.click(screen.getByRole("button", { name: "Přidat jako požadavek" }));
    expect(await screen.findByText(REQUEST_EMPTY)).toBeTruthy();
    fireEvent.change(input, { target: { value: "  Vztah k AI ve zdravotnictví " } });
    fireEvent.click(screen.getByRole("button", { name: "Přidat jako požadavek" }));
    expect(await screen.findByText(REQUEST_DONE)).toBeTruthy();
    expect(posted("/api/library/dimension/request")[0].body).toEqual({
      label: "Vztah k AI ve zdravotnictví", source_strategy: "document_or_research", rationale: "Požadavek projektu: Vztah k AI ve zdravotnictví", spec: { predictors: [] }, origin: "user",
    });
    expect(["/api/library", "/api/library/system-catalog", "/api/populations", "/api/results-registry?sync=1"].every((u) => calls.some((c) => c.url === u))).toBe(true);
    expect(screen.getByText("Vztah k AI ve zdravotnictví · čeká na evidenci")).toBeTruthy();
    expect((input as HTMLInputElement).value).toBe("");
    // The refreshed library's dimension is in the catalogue now.
    expect(screen.getByRole("button", { name: /Nová z knihovny/ })).toBeTruthy();
    await savedWith("requested_dimension_1793");
    expect(lastSave().project).toMatchObject({ requested_dimensions: [{ label: "Vztah k AI ve zdravotnictví", dimension_id: "DIM-1", status: "needs_evidence" }], persona_dimensions: { approved: ["zdravi", "media"] } });
  }, 20_000);

  it("the sample: clamped when it is committed, and the recommendation", async () => {
    unitStub(PLANNED);
    render(<ResearchScreen projectId="PRJ-1" step="persona" frame={TEST_FRAME} />);
    const n = (await screen.findByLabelText("Počet respondentů")) as HTMLInputElement;
    fireEvent.change(n, { target: { value: "10" } });
    fireEvent.blur(n);
    await savedWith("sample_n_1789");
    expect(lastSave().project.n).toBe(50);
    expect((screen.getByLabelText("Počet respondentů") as HTMLInputElement).value).toBe("50");
    fireEvent.click(screen.getByRole("button", { name: "Použít doporučené N=300" }));
    await savedWith("sample_recommended_1789");
    expect(lastSave().project.n).toBe(300);
  }, 20_000);

  it("goes on calibrated to the run step, and the factors lead back to the audience", async () => {
    unitStub(PLANNED);
    render(<ResearchScreen projectId="PRJ-1" step="persona" frame={TEST_FRAME} />);
    const card = (await screen.findByRole("heading", { name: "Co už panel umí popsat a segmentovat" })).closest("section") as HTMLElement;
    expect(within(card).getByText("Demografie · 3")).toBeTruthy();
    expect(within(card).queryByText(/Research-only/)).toBeNull();
    fireEvent.click(within(card).getByRole("button", { name: "Použít faktory pro cílovou populaci" }));
    expect(push).toHaveBeenLastCalledWith(stagePath("audience"));
    fireEvent.click(screen.getByRole("button", { name: "Další · kontrola" }));
    expect(push).toHaveBeenLastCalledWith(stagePath("run"));
    await savedWith("persona_done_1789");
    expect(lastSave().project).toMatchObject({ persona_mode: "calibrated", persona_dimensions: { approved: ["zdravi", "media"] } });
  }, 20_000);

  it("a catalogue that fails leaves both cards out and is asked for once (OI-57)", async () => {
    unitStub(PLANNED, { "/api/audience/dimensions": () => new Response("{}", { status: 500 }) });
    render(<ResearchScreen projectId="PRJ-1" step="persona" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "Vzorek" });
    await waitFor(() => expect(posted("/api/audience/dimensions").length).toBe(1));
    await new Promise((r) => setTimeout(r, 50));
    expect(posted("/api/audience/dimensions").length).toBe(1);
    expect(screen.queryByRole("heading", { name: "Co už panel umí popsat a segmentovat" })).toBeNull();
  });

  it("Deep Research leaves the label for the classic Data Library and follows the hand-off", async () => {
    unitStub(PLANNED);
    render(<ResearchScreen projectId="PRJ-1" step="persona" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "Co už panel umí popsat a segmentovat" });
    fireEvent.click(screen.getByRole("button", { name: "AI doporučí" }));
    await approveProposal();
    const research = await screen.findByRole("button", { name: "Deep Research" }, { timeout: 4000 });
    const loc = { href: "" };
    const spy = vi.spyOn(window, "location", "get").mockReturnValue(loc as Location);
    fireEvent.click(research);
    spy.mockRestore();
    expect(window.sessionStorage.getItem(DIMENSION_RESEARCH_KEY)).toBe("Důvěra v AI");
    expect(loc.href).toBe("/classic#aia:dimension=research");
  });
});
