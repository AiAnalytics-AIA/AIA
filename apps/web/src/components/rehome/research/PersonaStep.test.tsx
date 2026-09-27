// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AGENTS_PATH, NATIVE_JOB_WAIT, NATIVE_TEST_TIMEOUT_MS, PARK_MESSAGE, approveProposal, nativeAgentFixture } from "./test-native-agents";
import { PROPOSAL_AI_DONE, PROPOSAL_DONE, REQUEST_EMPTY } from "@/research/persona";
import { ResearchScreen } from "./ResearchScreen";
import { type SavedBody, workspaceFixture } from "./test-workspace";
import { TEST_FRAME, stagePath } from "./test-frame";

// Native jobs need more than vitest's 5 s under CI load (test-native-agents.ts).
vi.setConfig({ testTimeout: NATIVE_TEST_TIMEOUT_MS });

const push = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/dimensions", useRouter: () => ({ push, replace: vi.fn() }) }));

const SUGGESTION = {
  dimensions: ["cena", "Úplně nová věc"],
  new_dimension_suggestions: [{ label: "Důvěra v AI", why: "Mění ochotu", evidence_needed: "průzkum", suggested_predictors: ["vek"], source_strategy: "document" }],
};
const CONTEXT_PATH = "/api/v1/studies/STU-1/context";
const PROPOSALS_PATH = "/api/v1/studies/STU-1/knowledge-proposals";
/** The study's inherited context: the client's approved knowledge, a dimension among it. */
const CONTEXT = {
  client_id: "CLI-1",
  shared: {},
  client: [
    { item_id: "KNI-ai", kind: "DIMENSION", title: "Vztah k AI", summary: "", content: {}, revision: 1, modified_at: null },
    { item_id: "KNI-fact", kind: "FACT", title: "Není dimenze", summary: "", content: {}, revision: 1, modified_at: null },
  ],
};

type Call = { url: string; body: Record<string, unknown> | null };
let calls: Call[] = [];
let saves: SavedBody[] = [];
/** AIA, answering by path: the working content, the study's context and proposals, the native jobs. */
function aiaStub(project: Record<string, unknown>, over: Record<string, (b: unknown) => unknown> = {}) {
  calls = [];
  const ws = workspaceFixture(project, { analysis: null });
  saves = ws.saves;
  const native = nativeAgentFixture((_action, baseline) => ({ project: baseline, proposal: { ...SUGGESTION, new_dimension_suggestions: SUGGESTION.new_dimension_suggestions.map((s) => ({ ...s, evidence_needed: [s.evidence_needed] })) }, dimensions: [], new_dimension_suggestions: SUGGESTION.new_dimension_suggestions }), over);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ url: u, body });
      const answers: Record<string, (b: unknown) => unknown> = {
        [CONTEXT_PATH]: () => CONTEXT,
        [PROPOSALS_PATH]: (b) => ({ proposal_id: "KNP-1", origin: "STUDY", status: "PROPOSED", title: (b as { title: string }).title }),
        ...over,
      };
      const answer = native(u.split("?")[0], init?.method ?? "GET", body) ?? ws.answer(u.split("?")[0], init?.method ?? "GET", body) ?? answers[u.split("?")[0]]?.(body);
      if (answer === undefined) return new Response(JSON.stringify({ code: "not_found", message: "No such resource." }), { status: 404 });
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
}
const posted = (path: string) => calls.filter((c) => c.url.split("?")[0] === path && (!path.startsWith("/api/v1/") || c.body !== null));
type Saved = { content: Record<string, unknown> & { persona_dimensions: { approved: string[] } }; reason: string };
const lastSave = () => saves.at(-1) as unknown as Saved;
const savedWith = (reason: string) => waitFor(() => expect(lastSave()?.reason).toBe(reason), { timeout: 4000 });
const PLANNED = { research_plan: { recommended_topics: ["zdraví", "média"] } };
/** Nothing the Dimenze step does reaches the 18.6.6 unit (ADR 0018). */
const noUnitCalls = () => expect(calls.filter((c) => !c.url.startsWith("/api/v1/") && c.url !== "/config").map((c) => c.url)).toEqual([]);

beforeEach(() => {
  push.mockReset();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Dimenze", () => {
  it("draws the fixed base, the recommended dimensions, and the catalogue with the client's own", async () => {
    aiaStub(PLANNED);
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    expect(await screen.findByRole("heading", { name: "Sociodemografie a reprezentativní výběr" })).toBeTruthy();
    // No approval yet: the recommended set is drawn (OI-54).
    expect(screen.getByRole("button", { name: "Odebrat dimenzi Zdraví" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Odebrat dimenzi Média a informační chování" })).toBeTruthy();
    // The client's approved dimension arrives after the screen draws; other kinds do not.
    const row = await screen.findByRole("button", { name: /Vztah k AI/ });
    expect(row.textContent).toContain("Znalosti klienta");
    expect(screen.queryByRole("button", { name: /Není dimenze/ })).toBeNull();
    expect(screen.getByRole("button", { name: /^Zdraví/ }).textContent).toContain("doporučeno pro tento projekt");
    fireEvent.change(screen.getByLabelText("Hledat dimenzi"), { target: { value: "znalosti" } });
    expect(screen.queryByRole("button", { name: /^Zdraví/ })).toBeNull();
    fireEvent.change(screen.getByLabelText("Hledat dimenzi"), { target: { value: "AI" } });
    expect(screen.getByRole("button", { name: /Vztah k AI/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Další · kontrola" })).toBeTruthy();
    noUnitCalls();
  });

  it("without the client's knowledge the catalogue is the system's own", async () => {
    aiaStub(PLANNED, { [CONTEXT_PATH]: () => new Response("{}", { status: 500 }) });
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    expect(await screen.findByRole("button", { name: /^Politické postoje/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Vztah k AI/ })).toBeNull();
  });

  it("adds and removes a dimension; removing the last brings the recommended back (OI-54)", async () => {
    aiaStub({ ...PLANNED, persona_dimensions: { approved: ["cena"] } });
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /^Politické postoje/ }));
    await savedWith("dimension_catalog_add");
    expect(lastSave().content.persona_dimensions.approved).toEqual(["cena", "politika"]);
    fireEvent.click(screen.getByRole("button", { name: "Odebrat dimenzi Politické postoje" }));
    fireEvent.click(screen.getByRole("button", { name: "Odebrat dimenzi Cena / value for money" }));
    await savedWith("dimension_catalog_remove");
    expect(lastSave().content.persona_dimensions.approved).toEqual([]);
    // The classic draws the refill at once, and the next change saves it.
    expect(screen.getByRole("button", { name: "Odebrat dimenzi Zdraví" })).toBeTruthy();
    expect(screen.queryByText("Zatím není vybraná žádná volitelná dimenze.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Použít doporučené" }));
    await savedWith("persona_autofill");
    expect(lastSave().content.persona_dimensions.approved).toEqual(["zdravi", "media"]);
  }, 20_000);

  it("reviews new dimensions and proposes one to the client's knowledge, never approving it", async () => {
    aiaStub({ ...PLANNED, persona_dimensions: { approved: ["cena"] } });
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    await screen.findByRole("heading", { name: "Faktory panelu v AIA zatím nejsou" });
    fireEvent.click(screen.getByRole("button", { name: "AI doporučí" }));
    await approveProposal();
    expect(await screen.findByRole("heading", { name: "AI navrhuje doplnit nové dimenze" }, NATIVE_JOB_WAIT)).toBeTruthy();
    expect(posted(AGENTS_PATH)[0].body).toMatchObject({ action: "suggest_dimensions" });
    await savedWith("native_ai_proposal_accepted");
    // Existing researcher choices survive; unsupported dimensions are proposals.
    expect(lastSave().content.persona_dimensions.approved).toEqual(["cena"]);
    expect(screen.queryByRole("button", { name: "Odebrat dimenzi uplne_nova_vec" })).toBeNull();
    expect(screen.getByText("Mění ochotu · evidence: průzkum")).toBeTruthy();
    // No Deep Research hand-off: AIA has none, and the card says so.
    expect(screen.queryByRole("button", { name: "Deep Research" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Navrhnout do Znalostí klienta" }));
    expect(await screen.findByText(PROPOSAL_AI_DONE)).toBeTruthy();
    expect(posted(PROPOSALS_PATH)[0].body).toEqual({
      kind: "DIMENSION",
      title: "Důvěra v AI",
      summary: "Mění ochotu",
      content: { source_strategy: "document", spec: { predictors: [{ column: "vek", direction: "positive", strength: 1 }] }, origin: "claude", requested_from: "research_dimensions" },
    });
    expect(screen.getByText("Důvěra v AI · čeká na schválení")).toBeTruthy();
    noUnitCalls();
  }, 20_000);

  it("parks the native job when the governed runtime is unavailable", async () => {
    aiaStub(PLANNED, { "native/job": () => ({ status: "WAITING_PROVIDER", is_terminal: false, needs_attention: true, steps: [{ error_message: PARK_MESSAGE }], run_id: "RUN-A" }) });
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: "AI doporučí" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    noUnitCalls();
  });

  it("requests a dimension the system does not have: refused when empty, proposed, recorded", async () => {
    aiaStub(PLANNED);
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    const input = await screen.findByLabelText("Název dimenze");
    fireEvent.click(screen.getByRole("button", { name: "Přidat jako požadavek" }));
    expect(await screen.findByText(REQUEST_EMPTY)).toBeTruthy();
    fireEvent.change(input, { target: { value: "  Vztah k AI ve zdravotnictví " } });
    fireEvent.click(screen.getByRole("button", { name: "Přidat jako požadavek" }));
    expect(await screen.findByText(PROPOSAL_DONE)).toBeTruthy();
    expect(posted(PROPOSALS_PATH)[0].body).toEqual({
      kind: "DIMENSION",
      title: "Vztah k AI ve zdravotnictví",
      summary: "Požadavek projektu: Vztah k AI ve zdravotnictví",
      content: { source_strategy: "document_or_research", spec: { predictors: [] }, origin: "user", requested_from: "research_dimensions" },
    });
    expect(screen.getByText("Vztah k AI ve zdravotnictví · čeká na schválení")).toBeTruthy();
    expect((input as HTMLInputElement).value).toBe("");
    await savedWith("requested_dimension_1793");
    expect(lastSave().content).toMatchObject({ requested_dimensions: [{ label: "Vztah k AI ve zdravotnictví", proposal_id: "KNP-1", status: "needs_evidence" }], persona_dimensions: { approved: ["zdravi", "media"] } });
    noUnitCalls();
  }, 20_000);

  it("a proposal AIA refuses is shown, and nothing is recorded", async () => {
    aiaStub(PLANNED, { [PROPOSALS_PATH]: () => new Response(JSON.stringify({ code: "forbidden", message: "Your role on this study does not permit proposing knowledge." }), { status: 403 }) });
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    fireEvent.change(await screen.findByLabelText("Název dimenze"), { target: { value: "Nová" } });
    fireEvent.click(screen.getByRole("button", { name: "Přidat jako požadavek" }));
    expect((await screen.findByRole("alert")).textContent).toContain("does not permit proposing knowledge");
    expect(saves).toEqual([]);
  });

  it("the sample: clamped when it is committed, and the recommendation", async () => {
    aiaStub(PLANNED);
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    const n = (await screen.findByLabelText("Počet respondentů")) as HTMLInputElement;
    fireEvent.change(n, { target: { value: "10" } });
    fireEvent.blur(n);
    await savedWith("sample_n_1789");
    expect(lastSave().content.n).toBe(50);
    expect((screen.getByLabelText("Počet respondentů") as HTMLInputElement).value).toBe("50");
    fireEvent.click(screen.getByRole("button", { name: "Použít doporučené N=300" }));
    await savedWith("sample_recommended_1789");
    expect(lastSave().content.n).toBe(300);
  }, 20_000);

  it("goes on calibrated to the run step; the panel's factors say they are not in AIA", async () => {
    aiaStub(PLANNED);
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    const card = (await screen.findByRole("heading", { name: "Faktory panelu v AIA zatím nejsou" })).closest("section") as HTMLElement;
    expect(within(card).getByText(/licencovaného panelu, který AIA zatím nemá nahraný/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Použít faktory pro cílovou populaci" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Další · kontrola" }));
    expect(push).toHaveBeenLastCalledWith(stagePath("run"));
    await savedWith("persona_done_1789");
    expect(lastSave().content).toMatchObject({ persona_mode: "calibrated", persona_dimensions: { approved: ["zdravi", "media"] } });
    noUnitCalls();
  }, 20_000);
});
