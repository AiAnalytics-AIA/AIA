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
const LIMITS_PATH = "/api/v1/studies/STU-1/research/limits";
const TOPICS_PATH = "/api/v1/studies/STU-1/research/persona-topics";
const OWN_PATH = "/api/v1/studies/STU-1/population/materializations";
/** The server's mapping (persona_topics.dimension_topic), for the ids these tests choose. */
const TOPICS: Record<string, string | null> = { media: "media", cena: "cena", zdravi: "zdravi", ekologie: "eko", "KNI-ai": null };
/** The readiness limits in force, as the server answers them (RQC9): the preset's 20-10 000. */
const LIMITS = { methodology_version: "aia-readiness-1", version: null, sample_size: { min: 20, max: 10000 } };
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
/** The working copy the server wrote on an accept (ADR 0026 decision 6). */
let writes: { content: Record<string, unknown>; analysis: unknown }[] = [];
/** AIA, answering by path: the working content, the study's context and proposals, the native jobs. */
function aiaStub(project: Record<string, unknown>, over: Record<string, (b: unknown) => unknown> = {}) {
  calls = [];
  const ws = workspaceFixture(project, { analysis: null });
  saves = ws.saves;
  writes = ws.writes;
  const native = nativeAgentFixture((_action, baseline) => ({ project: baseline, proposal: { ...SUGGESTION, new_dimension_suggestions: SUGGESTION.new_dimension_suggestions.map((s) => ({ ...s, evidence_needed: [s.evidence_needed] })) }, dimensions: [], new_dimension_suggestions: SUGGESTION.new_dimension_suggestions }), over, ws.write);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ url: u, body });
      const answers: Record<string, (b: unknown) => unknown> = {
        [CONTEXT_PATH]: () => CONTEXT,
        [LIMITS_PATH]: () => LIMITS,
        [TOPICS_PATH]: () => ({ items: new URL(u, "http://x").searchParams.getAll("dimension").map((d) => ({ dimension: d, topic: d in TOPICS ? TOPICS[d] : null })) }),
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
const savedWith = (reason: string) => waitFor(() => expect(lastSave()?.reason).toBe(reason));
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
    // Studio v3: the fixed base is the first, pinned row of the selection.
    expect(await screen.findByText("Sociodemografie · vždy zapnuto")).toBeTruthy();
    // No approval yet: nothing is chosen, and the recommended set is offered, never drawn as
    // chosen (OI-54, owner 2026-10-18: the classic refilled an empty approval as it drew).
    expect(screen.getByText("Zatím není vybraná žádná volitelná dimenze.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Odebrat dimenzi Zdraví" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Odebrat dimenzi Média a informační chování" })).toBeNull();
    // The client's approved dimension arrives after the screen draws; other kinds do not.
    const row = await screen.findByRole("button", { name: /Vztah k AI/ });
    expect(row.textContent).toContain("Znalosti klienta");
    expect(screen.queryByRole("button", { name: /Není dimenze/ })).toBeNull();
    expect(screen.getByRole("button", { name: /^Zdraví/ }).textContent).toContain("doporučeno pro tento projekt");
    // Recommended dimensions and the catalogue are two groups of the checklist.
    expect(screen.getByRole("heading", { name: "Doporučeno pro tento projekt" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Katalog systému" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Hledat dimenzi"), { target: { value: "znalosti" } });
    expect(screen.queryByRole("button", { name: /^Zdraví/ })).toBeNull();
    fireEvent.change(screen.getByLabelText("Hledat dimenzi"), { target: { value: "žádná taková" } });
    expect(screen.getByText(/Hledání nic nenašlo/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Hledat dimenzi"), { target: { value: "AI" } });
    expect(screen.getByRole("button", { name: /Vztah k AI/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Další · kontrola" })).toBeTruthy();
    noUnitCalls();
  });

  it("names each chosen dimension's persona topic as the server maps it, an unmatched one said (DIM2)", async () => {
    aiaStub({ ...PLANNED, persona_dimensions: { approved: ["ekologie", "KNI-ai"] } });
    const { container } = render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    const eco = await waitFor(() => {
      const el = container.querySelector('[data-aia="dimension:ekologie"]');
      expect(el?.textContent).toContain("téma persony: eko");
      return el as HTMLElement;
    });
    expect(eco.textContent).toContain("Ekologie");
    const own = container.querySelector('[data-aia="dimension:KNI-ai"]') as HTMLElement;
    await waitFor(() => expect(own.textContent).toContain("bez tématu persony"));
    expect(own.textContent).toContain("Znalosti klienta");
    expect(calls.some((c) => c.url.startsWith(`${TOPICS_PATH}?dimension=ekologie&dimension=KNI-ai`))).toBe(true);
    noUnitCalls();
  });

  it("lists the client's own dimensions this study materialized, each with its state and outcome (DIM4)", async () => {
    const base = { status: "SUCCEEDED", created_at: "2026-10-22T00:00:00Z", finished_at: null, kind: "binary", waiting_reason: null, refusal_reason: null };
    aiaStub(PLANNED, {
      [OWN_PATH]: () => ({
        items: [
          { ...base, run_id: "RUN-a", dimension_id: "pije_kavu_rano", step_status: "SUCCEEDED", child: { version_id: "v+c1", label: "Pije kávu ráno", target: 0.4, achieved: 0.31, target_met: false } },
          { ...base, run_id: "RUN-b", dimension_id: "jezdi_vlakem", status: "RUNNING", step_status: "AWAITING_BUDGET", waiting_reason: "budget_exceeded", child: null },
        ],
      }),
    });
    const { container } = render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    const done = await waitFor(() => {
      const el = container.querySelector('[data-aia="own_dimension:RUN-a"]');
      expect(el).not.toBeNull();
      return el as HTMLElement;
    });
    expect(done.textContent).toContain("pije_kavu_rano");
    expect(done.textContent).toContain("cíl 40 %, dosaženo 31 % · cíl nedosažen");
    const waiting = container.querySelector('[data-aia="own_dimension:RUN-b"]') as HTMLElement;
    expect(waiting.textContent).toContain("Čeká na rozpočet");
    expect(waiting.textContent).toContain("překročil rozpočet studie");
    expect(screen.getByRole("link", { name: /Populace běhu/ }).getAttribute("href")).toBe(stagePath("run"));
    noUnitCalls();
  });

  it("without any materialization from this study the section says so, and still leads to the run's population", async () => {
    aiaStub(PLANNED, { [OWN_PATH]: () => ({ items: [] }) });
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    expect(await screen.findByText(/žádná dimenze klienta nematerializovala/)).toBeTruthy();
    // The Run stage offers the client's children from every study, so the way there stays.
    expect(screen.getByRole("link", { name: /Populace běhu/ }).getAttribute("href")).toBe(stagePath("run"));
  });

  it("a topic the server did not answer is never shown as matched", async () => {
    aiaStub({ ...PLANNED, persona_dimensions: { approved: ["ekologie"] } }, { [TOPICS_PATH]: () => new Response("{}", { status: 500 }) });
    const { container } = render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    expect(await screen.findByText(/Témata persony se nepodařilo načíst/)).toBeTruthy();
    expect(container.querySelector('[data-aia="dimension:ekologie"]')?.textContent).toContain("téma persony neověřeno");
  });

  it("without the client's knowledge the catalogue is the system's own", async () => {
    aiaStub(PLANNED, { [CONTEXT_PATH]: () => new Response("{}", { status: 500 }) });
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    expect(await screen.findByRole("button", { name: /^Politické postoje/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Vztah k AI/ })).toBeNull();
  });

  it("adds and removes a dimension; removing the last leaves none chosen, and the recommended set is one click (OI-54)", async () => {
    aiaStub({ ...PLANNED, persona_dimensions: { approved: ["cena"] } });
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /^Politické postoje/ }));
    await savedWith("dimension_catalog_add");
    expect(lastSave().content.persona_dimensions.approved).toEqual(["cena", "politika"]);
    fireEvent.click(screen.getByRole("button", { name: "Odebrat dimenzi Politické postoje" }));
    fireEvent.click(screen.getByRole("button", { name: "Odebrat dimenzi Cena / value for money" }));
    await savedWith("dimension_catalog_remove");
    expect(lastSave().content.persona_dimensions.approved).toEqual([]);
    // Empty stays empty on screen (the classic drew the refill at once, and the next change saved it).
    expect(screen.queryByRole("button", { name: "Odebrat dimenzi Zdraví" })).toBeNull();
    expect(screen.getByText("Zatím není vybraná žádná volitelná dimenze.")).toBeTruthy();
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
    // The server wrote the accepted proposal into the working copy (ADR 0026 decision 6).
    await waitFor(() => expect(writes).toHaveLength(1));
    // Existing researcher choices survive; unsupported dimensions are proposals.
    expect((writes[0].content.persona_dimensions as { approved: string[] }).approved).toEqual(["cena"]);
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
    // The input clears on the render after the request resolves, not with the toast.
    await waitFor(() => expect((input as HTMLInputElement).value).toBe(""));
    await savedWith("requested_dimension_1793");
    // The save carries what was chosen (none), never the recommended set as if chosen.
    expect(lastSave().content).toMatchObject({ requested_dimensions: [{ label: "Vztah k AI ve zdravotnictví", proposal_id: "KNP-1", status: "needs_evidence" }], persona_dimensions: { approved: [] } });
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

  it("the sample is one stepper: a press steps by 50 and saves, and below the recommendation says so (DIM3)", async () => {
    aiaStub(PLANNED);
    const { container } = render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    const n = (await screen.findByRole("spinbutton", { name: "Počet respondentů" })) as HTMLInputElement;
    // One control for n: no slider, no preset list beside it (audit B1).
    expect(screen.queryByRole("slider")).toBeNull();
    expect(screen.queryByRole("button", { name: "800" })).toBeNull();
    expect(container.querySelector('[data-aia="sample:n"]')?.contains(n)).toBe(true);
    expect(screen.getByRole("button", { name: "Použít doporučené N=300" })).toBeTruthy();
    expect(screen.getByText(/20–10\s000/)).toBeTruthy(); // the server's valid n, stated at the field
    fireEvent.click(screen.getByRole("button", { name: /Zvýšit/ }));
    await savedWith("sample_n_1789");
    expect(lastSave().content.n).toBe(350);
    expect(screen.getByText(/^\d+ dimenzí · N=350$/)).toBeTruthy(); // the dock's note
    const stepped = screen.getByRole("spinbutton", { name: "Počet respondentů" });
    expect(stepped).not.toBe(n); // a new stored n redraws the field (key)
    fireEvent.change(stepped, { target: { value: "100" } });
    fireEvent.blur(stepped);
    await waitFor(() => expect(lastSave().content.n).toBe(100));
    expect(await screen.findByText(/Pod doporučeným N=300/)).toBeTruthy();
  });

  it("the sample: a value outside the server's valid n is refused and said, never clamped (IA-1)", async () => {
    aiaStub(PLANNED);
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    const n = (await screen.findByRole("spinbutton", { name: "Počet respondentů" })) as HTMLInputElement;
    // The classic stored 50 for a typed 10 without a word; nothing is stored now.
    for (const typed of ["19", "10001", "", "250,5"]) {
      fireEvent.change(n, { target: { value: typed } });
      fireEvent.blur(n);
      expect((await screen.findByRole("alert")).textContent).toMatch(/neuloženo/);
      expect(n.value).toBe(typed);
    }
    expect(saves).toEqual([]);
    expect(n.getAttribute("aria-invalid")).toBe("true");
    // The bound itself is valid: both ends are included, as readiness reads them.
    fireEvent.change(n, { target: { value: "20" } });
    fireEvent.blur(n);
    await savedWith("sample_n_1789");
    expect(lastSave().content.n).toBe(20);
    expect(screen.queryByRole("alert")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Použít doporučené N=300" }));
    await savedWith("sample_recommended_1789");
    expect(lastSave().content.n).toBe(300);
  }, 20_000);

  it("the sample: a narrower range in force bounds the stepper and disables the recommendation it does not admit", async () => {
    aiaStub(PLANNED, { [LIMITS_PATH]: () => ({ ...LIMITS, version: 2, sample_size: { min: 500, max: 1000 } }) });
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    const n = (await screen.findByRole("spinbutton", { name: "Počet respondentů" })) as HTMLInputElement;
    expect(n.getAttribute("aria-valuemin")).toBe("500");
    expect(n.getAttribute("aria-valuemax")).toBe("1000");
    expect((screen.getByRole("button", { name: "Použít doporučené N=300" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(n, { target: { value: "1500" } });
    fireEvent.blur(n);
    // The refusal at the field, and the stored n (PLANNED's 300) said to be outside the range.
    await waitFor(() => expect(screen.getAllByRole("alert").map((a) => a.textContent?.replace(/\s/g, " "))).toEqual([
      "Musí být 500–1 000; neuloženo.",
      "Uložené N=300 je mimo platný rozsah 500–1 000; spuštění ho odmítne. Zvolte jiné N.",
    ]));
    expect(saves).toEqual([]);
  }, 20_000);

  it("the sample: a refused draft does not outlive a change to n made beside it", async () => {
    aiaStub({ ...PLANNED, n: 500 });
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    const n = (await screen.findByRole("spinbutton", { name: "Počet respondentů" })) as HTMLInputElement;
    fireEvent.change(n, { target: { value: "19" } });
    fireEvent.blur(n);
    expect((await screen.findByRole("alert")).textContent).toMatch(/neuloženo/);
    fireEvent.click(screen.getByRole("button", { name: "Použít doporučené N=300" }));
    await savedWith("sample_recommended_1789");
    const after = screen.getByRole("spinbutton", { name: "Počet respondentů" }) as HTMLInputElement;
    expect(after.value).toBe("300");
    expect(after.getAttribute("aria-invalid")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    expect((screen.getByRole("button", { name: "Použít doporučené N=300" }) as HTMLButtonElement).disabled).toBe(true);
  }, 20_000);

  it("the sample: the heading names no n but the stored one, so the recommendation is never read as it", async () => {
    aiaStub({ ...PLANNED, n: 600 });
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    const card = (await screen.findByRole("heading", { name: "Vzorek" })).closest("section") as HTMLElement;
    await waitFor(() => expect(within(card).getByRole("spinbutton", { name: "Počet respondentů" }).getAttribute("aria-valuenow")).toBe("600"));
    expect(within(card).queryByText("N=300")).toBeNull();
    expect(within(card).getByRole("button", { name: "Použít doporučené N=300" })).toBeTruthy();
  }, 20_000);

  it("the sample: a stored n the limits in force no longer admit is said, not shown as fine", async () => {
    aiaStub({ ...PLANNED, n: 300 }, { [LIMITS_PATH]: () => ({ ...LIMITS, version: 2, sample_size: { min: 500, max: 1000 } }) });
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    expect((await screen.findByRole("alert")).textContent?.replace(/\s/g, " ")).toBe("Uložené N=300 je mimo platný rozsah 500–1 000; spuštění ho odmítne. Zvolte jiné N.");
    expect(saves).toEqual([]);
  }, 20_000);

  it("the sample: with the range unread there is no field to type into, and the screen says why", async () => {
    aiaStub(PLANNED, { [LIMITS_PATH]: () => new Response("{}", { status: 500 }) });
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    const alert = (await screen.findByRole("alert")).textContent;
    expect(alert).toContain("Uloženo N=300.");
    expect(alert).toContain("Rozsah vzorku se nepodařilo načíst");
    expect(screen.queryByRole("spinbutton")).toBeNull();
    expect((screen.getByRole("button", { name: "Použít doporučené N=300" }) as HTMLButtonElement).disabled).toBe(true);
    expect(saves).toEqual([]);
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
    expect(lastSave().content).toMatchObject({ persona_mode: "calibrated", persona_dimensions: { approved: [] } });
    noUnitCalls();
  }, 20_000);
});
