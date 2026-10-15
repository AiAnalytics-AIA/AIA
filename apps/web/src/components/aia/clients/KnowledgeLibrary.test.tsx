// @vitest-environment jsdom
// The client's knowledge library (client-workspace C4) against a fake AIA API: views,
// folders and labels; ticked items moved and labelled together; the open item edited into
// a new revision, filed and unlabelled; the history it carries. Every write is checked by
// the request it sends.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ClientValue } from "./ClientContext";
import { KnowledgeArea } from "./KnowledgeArea";

vi.mock("next/navigation", () => ({
  usePathname: () => "/app/clients/CLI-a/knowledge",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(window.location.search),
}));

const ALL = ["APPROVE_CLIENT_KNOWLEDGE", "CREATE_STUDY", "PROPOSE_CLIENT_KNOWLEDGE", "VIEW_CLIENT", "VIEW_CLIENT_KNOWLEDGE"];
const CLIENT = { client_id: "CLI-a", name: "Klient A", slug: "klient-a", status: "ACTIVE", your_role: "RESEARCHER", permissions: ALL, counts: { research: 1, simulations: 0, pending_proposals: 3, datasets: 0 } };

const item = (id: string, title: string, extra: Record<string, unknown> = {}) => ({
  item_id: id, kind: "FACT", title, summary: "", content: {}, revision: 1, modified_at: "2026-10-01T10:00:00Z", folder_id: null, label_ids: [], ...extra,
});
const ITEMS = [
  item("KNW-1", "Hlavní konkurenti", { kind: "ENTITY", revision: 2, folder_id: "KNF-1", label_ids: ["KNL-1"], summary: "Dva hlavní.", content: { aliases: ["Konkurent A"] } }),
  item("KNW-2", "Výroční zpráva", { kind: "SOURCE" }),
  item("KNW-3", "Pobočky se zmenší", { modified_at: "2024-03-01T10:00:00Z" }),
];
const FOLDERS = [{ folder_id: "KNF-1", name: "Trh a konkurence", item_count: 1 }];
const LABELS = [{ label_id: "KNL-1", name: "retail", colour: "GREEN", item_count: 1 }, { label_id: "KNL-2", name: "ověřit", colour: "ORANGE", item_count: 0 }];
const REVISIONS = [
  { revision: 1, context_revision: 3, title: "Konkurenti", summary: "", provenance: { origin: "STUDY" }, approved_by: "USR-1", approved_at: "2026-08-01T10:00:00Z" },
  { revision: 2, context_revision: 7, title: "Hlavní konkurenti", summary: "Dva hlavní.", provenance: { origin: "CLIENT", authored: "person" }, approved_by: "USR-1", approved_at: "2026-10-01T10:00:00Z" },
];

type Call = { method: string; url: string; body: unknown };
let calls: Call[] = [];
function api(overrides: Record<string, (body: unknown, url: string) => unknown> = {}) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ method, url: u, body });
      const base = "/api/v1/clients/CLI-a/knowledge";
      const routes: Record<string, (b: unknown, url: string) => unknown> = {
        "GET /config": () => ({ cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", apiBase: "", build: { sha: null } }),
        [`GET ${base}`]: (_b, url) => {
          const folder = new URL(url, "http://x").searchParams.get("folder");
          return folder ? ITEMS.filter((i) => (folder === "unfiled" ? !i.folder_id : i.folder_id === folder)) : ITEMS;
        },
        [`GET ${base}/folders`]: () => FOLDERS,
        [`GET ${base}/labels`]: () => LABELS,
        [`GET ${base}/items/KNW-1/revisions`]: () => REVISIONS,
        [`PUT ${base}/placement`]: () => [],
        [`POST ${base}/folders`]: () => ({ folder_id: "KNF-2", name: "Nová", item_count: 0 }),
        [`POST ${base}/proposals`]: (b) => ({ proposal_id: "KNP-9", status: "APPROVED", ...(b as object) }),
        [`GET ${base}/proposals`]: () => [],
        "GET /api/v1/clients/CLI-a": () => CLIENT,
        ...overrides,
      };
      const answer = routes[`${method} ${u.split("?")[0]}`]?.(body, u) ?? {};
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
}
const sent = (method: string, path: string) => calls.filter((c) => c.method === method && c.url.split("?")[0] === `/api/v1/clients/CLI-a/knowledge${path}`);

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "a@example.test", subject: "s" }));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const open = (client: typeof CLIENT = CLIENT) =>
  render(
    <ClientValue client={client}>
      <KnowledgeArea />
    </ClientValue>,
  );
const nav = () => within(screen.getByRole("navigation", { name: "Pohledy, složky a štítky" }));
const table = () => screen.getByRole("table", { name: "Znalosti klienta" });

describe("the knowledge library", () => {
  it("lists the client's knowledge with where each item is filed", async () => {
    api();
    open();
    await screen.findByText("Hlavní konkurenti");
    const row = screen.getByText("Hlavní konkurenti").closest("tr")!;
    expect(within(row).getByText("Trh a konkurence")).toBeTruthy();
    expect(within(row).getByText("retail")).toBeTruthy();
    expect(within(screen.getByText("Výroční zpráva").closest("tr")!).getByText("Bez složky")).toBeTruthy();
    // The views, the client's folders with their counts, and what waits on a person.
    expect(nav().getByRole("button", { name: "Trh a konkurence 1" })).toBeTruthy();
    expect(nav().getByRole("button", { name: "Ke schválení 3" })).toBeTruthy();
    expect(screen.getByText(/AI ani studie je nevidí/)).toBeTruthy();
  });

  it("asks the API for one folder's items, for items in none, and with a label", async () => {
    api();
    open();
    await screen.findByText("Hlavní konkurenti");
    fireEvent.click(nav().getByRole("button", { name: "Trh a konkurence 1" }));
    await waitFor(() => expect(within(table()).queryByText("Výroční zpráva")).toBeNull());
    expect(screen.getByRole("heading", { level: 2, name: "Trh a konkurence" })).toBeTruthy();
    expect(sent("GET", "").at(-1)!.url).toContain("folder=KNF-1");
    fireEvent.click(nav().getByRole("button", { name: "Bez složky" }));
    await waitFor(() => expect(sent("GET", "").at(-1)!.url).toContain("folder=unfiled"));
    fireEvent.click(nav().getByRole("button", { name: /^retail/ }));
    await waitFor(() => expect(sent("GET", "").at(-1)!.url).toMatch(/folder=unfiled.*label=KNL-1|label=KNL-1.*folder=unfiled/));
    expect(screen.getByText("Jen se štítkem")).toBeTruthy();
  });

  it("shows what has not changed for a year, from the dates the API gave", async () => {
    api();
    open();
    await screen.findByText("Hlavní konkurenti");
    fireEvent.click(nav().getByRole("button", { name: "Starší než rok" }));
    await waitFor(() => expect(within(table()).queryByText("Hlavní konkurenti")).toBeNull());
    expect(within(table()).getByText("Pobočky se zmenší")).toBeTruthy();
  });

  it("moves and labels ticked items together, and takes them out of a folder", async () => {
    api();
    open();
    await screen.findByText("Hlavní konkurenti");
    fireEvent.click(screen.getByRole("checkbox", { name: "Vybrat Výroční zpráva" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Vybrat Pobočky se zmenší" }));
    const bar = within(screen.getByRole("region", { name: "Hromadné úpravy vybraných znalostí" }));
    expect(bar.getByText("Vybráno: 2")).toBeTruthy();
    fireEvent.change(bar.getByRole("combobox", { name: "Přesunout do složky…" }), { target: { value: "KNF-1" } });
    await waitFor(() => expect(sent("PUT", "/placement")[0].body).toEqual({ item_ids: ["KNW-2", "KNW-3"], folder_id: "KNF-1" }));
    fireEvent.change(bar.getByRole("combobox", { name: "Přidat štítek…" }), { target: { value: "KNL-2" } });
    await waitFor(() => expect(sent("PUT", "/placement")[1].body).toEqual({ item_ids: ["KNW-2", "KNW-3"], add_labels: ["KNL-2"] }));
    fireEvent.change(bar.getByRole("combobox", { name: "Přesunout do složky…" }), { target: { value: "none" } });
    await waitFor(() => expect(sent("PUT", "/placement")[2].body).toEqual({ item_ids: ["KNW-2", "KNW-3"], folder_id: null }));
  });

  it("opens an item beside the list: its history, an edit as a new revision, its folder and labels", async () => {
    api();
    open();
    fireEvent.click(await screen.findByRole("button", { name: /Hlavní konkurenti/ }));
    const panel = within(await screen.findByRole("complementary", { name: "Otevřená znalost" }));
    expect(await panel.findByText("Konkurenti")).toBeTruthy();
    expect(panel.getByText(/ze studie/)).toBeTruthy();
    expect(panel.getByText(/napsal člověk/)).toBeTruthy();

    const save = panel.getByRole("button", { name: "Uložit jako revizi 3" });
    expect((save as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(panel.getByRole("textbox", { name: "Název" }), { target: { value: "Hlavní konkurenti v retailu" } });
    fireEvent.click(save);
    await waitFor(() =>
      expect(sent("POST", "/proposals")[0].body).toEqual({ kind: "ENTITY", title: "Hlavní konkurenti v retailu", summary: "Dva hlavní.", content: { aliases: ["Konkurent A"] }, item_id: "KNW-1", base_revision: 2 }),
    );

    fireEvent.change(panel.getByRole("combobox", { name: "Složka" }), { target: { value: "none" } });
    await waitFor(() => expect(sent("PUT", "/placement")[0].body).toEqual({ item_ids: ["KNW-1"], folder_id: null }));
    fireEvent.click(panel.getByRole("button", { name: "Odebrat štítek retail" }));
    await waitFor(() => expect(sent("PUT", "/placement")[1].body).toEqual({ item_ids: ["KNW-1"], remove_labels: ["KNL-1"] }));
  });

  it("says an edit waits when the client asked for independent review", async () => {
    api({ "POST /api/v1/clients/CLI-a/knowledge/proposals": (b) => ({ proposal_id: "KNP-9", status: "PROPOSED", ...(b as object) }) });
    open();
    fireEvent.click(await screen.findByRole("button", { name: /Hlavní konkurenti/ }));
    const panel = within(await screen.findByRole("complementary", { name: "Otevřená znalost" }));
    fireEvent.change(panel.getByRole("textbox", { name: "Shrnutí" }), { target: { value: "Tři hlavní." } });
    fireEvent.click(panel.getByRole("button", { name: "Uložit jako revizi 3" }));
    expect(await screen.findByText("Úprava čeká na schválení někým jiným.")).toBeTruthy();
  });

  it("says an edit was not saved when the item moved on since it was opened (F-K1)", async () => {
    api({
      "POST /api/v1/clients/CLI-a/knowledge/proposals": () =>
        new Response(
          JSON.stringify({ code: "knowledge_proposal_stale", message: "x", details: { item_id: "KNW-1", base_revision: 2, current_revision: 3 } }),
          { status: 409 },
        ),
    });
    open();
    fireEvent.click(await screen.findByRole("button", { name: /Hlavní konkurenti/ }));
    const panel = within(await screen.findByRole("complementary", { name: "Otevřená znalost" }));
    fireEvent.change(panel.getByRole("textbox", { name: "Shrnutí" }), { target: { value: "Tři hlavní." } });
    fireEvent.click(panel.getByRole("button", { name: "Uložit jako revizi 3" }));
    expect(await screen.findByText(/Položka se mezitím změnila \(nyní revize 3\)/)).toBeTruthy();
  });

  it("asks before approving an edit of an older revision, and approves it over the current one only when asked (F-K1)", async () => {
    const pending = { proposal_id: "KNP-5", origin: "STUDY", study_id: "STU-1", study_name: "Studie", item_id: "KNW-1", kind: "ENTITY", title: "Konkurenti: tři", summary: "", status: "PROPOSED", proposed_by: "USR-2", proposed_at: "2026-10-01T10:00:00Z", decided_by: null, decided_at: null, decision_note: "", revision: null, base_revision: 1, yours: false };
    api({
      "GET /api/v1/clients/CLI-a/knowledge/proposals": () => [pending],
      "POST /api/v1/clients/CLI-a/knowledge/proposals/KNP-5/decision": (b) =>
        (b as { reviewed_revision?: number }).reviewed_revision === 2
          ? { ...pending, status: "APPROVED", revision: 3 }
          : new Response(
              JSON.stringify({ code: "knowledge_proposal_stale", message: "x", details: { item_id: "KNW-1", base_revision: 1, current_revision: 2 } }),
              { status: 409 },
            ),
    });
    window.history.replaceState(null, "", "/app/clients/CLI-a/knowledge?view=review");
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Schválit" }));
    expect(await screen.findByText(/návrh vychází z revize 1, nyní platí revize 2/)).toBeTruthy();
    const decisions = () => sent("POST", "/proposals/KNP-5/decision").map((c) => c.body);
    expect(decisions()).toEqual([{ approve: true, note: "" }]);
    fireEvent.click(screen.getByRole("button", { name: "Schválit místo revize 2" }));
    await waitFor(() => expect(decisions()[1]).toEqual({ approve: true, note: "", reviewed_revision: 2 }));
    window.history.replaceState(null, "", "/");
  });

  it("creates a folder, and says so in Czech when the name is taken", async () => {
    api();
    open();
    await screen.findByText("Hlavní konkurenti");
    fireEvent.click(nav().getByRole("button", { name: "Nová složka" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "Interní pravidla" } });
    fireEvent.submit(dialog.querySelector("form")!);
    await waitFor(() => expect(sent("POST", "/folders")[0].body).toEqual({ name: "Interní pravidla" }));
    cleanup();

    api({
      "POST /api/v1/clients/CLI-a/knowledge/folders": () =>
        new Response(JSON.stringify({ code: "name_taken", message: "This client already has a folder by that name." }), { status: 409 }),
    });
    open();
    await screen.findByText("Hlavní konkurenti");
    fireEvent.click(nav().getByRole("button", { name: "Nová složka" }));
    const again = await screen.findByRole("dialog");
    fireEvent.change(within(again).getByRole("textbox"), { target: { value: "trh a konkurence" } });
    fireEvent.submit(again.querySelector("form")!);
    expect(await screen.findByText("Takový název už u tohoto klienta je.")).toBeTruthy();
  });

  it("offers a reader without the right to propose nothing that would write", async () => {
    api();
    open({ ...CLIENT, permissions: ["VIEW_CLIENT", "VIEW_CLIENT_KNOWLEDGE"] });
    await screen.findByText("Hlavní konkurenti");
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(nav().queryByRole("button", { name: "Nová složka" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Napsat znalost" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Přidat podklady" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Hlavní konkurenti/ }));
    const panel = within(await screen.findByRole("complementary", { name: "Otevřená znalost" }));
    expect(panel.queryByRole("textbox")).toBeNull();
    expect((panel.getByRole("combobox", { name: "Složka" }) as HTMLSelectElement).disabled).toBe(true);
  });
});

// ---- a document's file (client-workspace C7a) -------------------------------------------

const SRC = "SRC-0123456789abcdef";
const NEWER = "SRC-fedcba9876543210";
const source = (id: string, filename: string, extra: Record<string, unknown> = {}) => ({
  source_id: id, sha256: "a".repeat(64), size_bytes: 2048, media_type: "application/pdf", family: "DOCUMENT", filename,
  outcome: "READ", reason: null, reader: "pdf/1", characters: 1200, segments: 2,
  occurrences: [{ occurrence_id: "SOC-1", filename, origin: "upload", added_by: "USR-1", added_at: "2026-10-14T08:00:00Z" }],
  created_at: "2026-10-14T08:00:00Z", ...extra,
});
const detail = (id: string, filename: string) => ({
  ...source(id, filename),
  reading: {
    outcome: "READ", reader: "pdf/1", reason: null, notes: [], dataset: null,
    segments: [{ locator: { page: 1 }, text: "Cílová skupina: lidé 18–65 let." }, { locator: { page: 2 }, text: "Závěr." }],
  },
});
const SOURCES = "/api/v1/clients/CLI-a/sources";
// jsdom's Blob has no arrayBuffer() (every current browser has); read it through FileReader. AGENTS.md § jsdom.
if (!Blob.prototype.arrayBuffer) {
  Blob.prototype.arrayBuffer = function (this: Blob) {
    return new Promise<ArrayBuffer>((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result as ArrayBuffer);
      r.onerror = () => reject(r.error);
      r.readAsArrayBuffer(this);
    });
  };
}
const pick = (label: string, name: string) =>
  fireEvent.change(screen.getByLabelText(label, { selector: "input" }), { target: { files: [new File(["%PDF-1.7"], name, { type: "application/pdf" })] } });

describe("a document's file", () => {
  it("comes through the intake sheet: the form for a document points there instead of taking a file", async () => {
    api();
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Napsat znalost" }));
    const form = within(screen.getByRole("region", { name: "Napsat znalost klienta" }));
    // A fact takes no file; a document is told where its file goes.
    expect(form.queryByText(/Soubor přidáte přes Přidat podklady/)).toBeNull();
    fireEvent.change(form.getByRole("combobox", { name: "Druh" }), { target: { value: "DOCUMENT" } });
    expect(form.getByText(/Soubor přidáte přes Přidat podklady/)).toBeTruthy();
    expect(form.queryByLabelText("Vybrat soubor", { selector: "input" })).toBeNull();
    fireEvent.click(form.getByRole("button", { name: "Přidat podklady" }));
    expect(screen.getByRole("dialog", { name: "Přidat podklady · Klient A" })).toBeTruthy();
  });

  it("shows on the open item with what was read, and a replacement is saved as the next revision", async () => {
    const doc = item("KNW-4", "Brief", { kind: "DOCUMENT", content: { source_id: SRC, note: "od klienta" } });
    api({
      "GET /api/v1/clients/CLI-a/knowledge": () => [...ITEMS, doc],
      "GET /api/v1/clients/CLI-a/knowledge/items/KNW-4/revisions": () => [],
      [`GET ${SOURCES}/${SRC}`]: () => detail(SRC, "Brief.pdf"),
      [`GET ${SOURCES}/${NEWER}`]: () => detail(NEWER, "Brief v2.pdf"),
      [`POST ${SOURCES}`]: () => new Response(JSON.stringify({ ...source(NEWER, "Brief v2.pdf"), created: true }), { status: 201 }),
    });
    open();
    fireEvent.click(await screen.findByRole("button", { name: /Brief/ }));
    const panel = within(await screen.findByRole("complementary", { name: "Otevřená znalost" }));
    expect(await panel.findByText("Brief.pdf")).toBeTruthy();
    expect(panel.getByText("2 kB", { exact: false })).toBeTruthy();
    expect(panel.getByText("Cílová skupina: lidé 18–65 let.")).toBeTruthy();
    expect(panel.getByText("str. 1")).toBeTruthy();

    const save = panel.getByRole("button", { name: "Uložit jako revizi 2" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    pick("Nahradit soubor", "Brief v2.pdf");
    expect(await panel.findByText("Brief v2.pdf")).toBeTruthy();
    expect(panel.getByText("Soubor se uloží jako nová revize.")).toBeTruthy();
    fireEvent.click(save);
    await waitFor(() =>
      expect(sent("POST", "/proposals")[0].body).toEqual({
        kind: "DOCUMENT", title: "Brief", summary: "", content: { note: "od klienta", source_id: NEWER }, item_id: "KNW-4", base_revision: 1,
      }),
    );
  });
});

// ---- AI proposals from a document (lifecycle K2d5) -------------------------------------

const MAY_RUN = { ...CLIENT, permissions: [...ALL, "RUN_CLIENT_WORK", "MANAGE_CLIENT_BUDGET"] };
const proposalsRun = (extra: Record<string, unknown> = {}) => ({
  run_id: "RUN-1", source_id: SRC, reading_sha256: "b".repeat(64), status: "RUNNING", step_status: "RUNNABLE",
  reason: null, current: true, created_at: null, finished_at: null, output: {}, created: true, restartable: false, ...extra,
});
const docItem = item("KNW-4", "Brief", { kind: "DOCUMENT", content: { source_id: SRC } });
const openDoc = async (client: typeof CLIENT, routes: Record<string, (body: unknown, url: string) => unknown>) => {
  api({
    "GET /api/v1/clients/CLI-a/knowledge": () => [...ITEMS, docItem],
    "GET /api/v1/clients/CLI-a/knowledge/items/KNW-4/revisions": () => [],
    [`GET ${SOURCES}/${SRC}`]: () => detail(SRC, "Brief.pdf"),
    ...routes,
  });
  open(client);
  fireEvent.click(await screen.findByRole("button", { name: /Brief/ }));
  return within(await screen.findByRole("complementary", { name: "Otevřená znalost" }));
};

describe("AI proposals from a document", () => {
  it("are asked for from the open item, paid by the client, followed until they wait in Ke schválení", async () => {
    let run: Record<string, unknown> | null = null;
    const panel = await openDoc(MAY_RUN, {
      // The fake answers {} for a missing value; the API answers null when nobody has asked.
      [`GET ${SOURCES}/${SRC}/proposals`]: () => run ?? new Response("null", { status: 200 }),
      [`POST ${SOURCES}/${SRC}/proposals`]: () => (run = proposalsRun()),
    });
    const ask = (await panel.findByRole("button", { name: "Navrhnout znalosti" })) as HTMLButtonElement;
    // The AI colour, and the title says who pays: the client, never a study.
    expect(ask.title).toBe("Spustí AI úlohu na pozadí · platí se z rozpočtu klienta");
    expect(panel.getByText(/Nic se nestane znalostí, dokud to člověk nepřijme/)).toBeTruthy();
    fireEvent.click(ask);
    expect(await panel.findByText("Návrhy čekají ve frontě.")).toBeTruthy();
    expect(panel.queryByRole("button", { name: /Navrhnout/ })).toBeNull();

    // Read again while it moves; done, it says where the proposals wait.
    run = proposalsRun({ status: "COMPLETED", step_status: "SUCCEEDED", output: { batches: 1, proposed: 2, dropped: { quote_not_found: 1 } } });
    expect(await panel.findByText("AI navrhla 2 návrhy. Čekají v Ke schválení.", {}, { timeout: 4000 })).toBeTruthy();
    expect(panel.getByText("Zahozeno bez doložené citace: 1.")).toBeTruthy();
    expect(panel.getByRole("link", { name: "Otevřít Ke schválení" }).getAttribute("href")).toBe("/app/clients/CLI-a/knowledge?view=review");
    expect(calls.filter((c) => c.method === "POST" && c.url.endsWith(`/sources/${SRC}/proposals`))).toHaveLength(1);
  });

  it("waits for the client's budget and lets a person who may set it raise it", async () => {
    let run: Record<string, unknown> = proposalsRun({ step_status: "AWAITING_BUDGET", reason: "budget_exceeded" });
    const panel = await openDoc(MAY_RUN, {
      [`GET ${SOURCES}/${SRC}/proposals`]: () => run,
      "POST /api/v1/clients/CLI-a/work/runs/RUN-1/steps/extract/budget": () => {
        run = proposalsRun({ step_status: "RUNNING" });
        return { run_id: "RUN-1", status: "RUNNING", steps: [{ node_key: "extract", status: "RUNNABLE" }] };
      },
    });
    expect(await panel.findByText(/Čeká na rozpočet klienta/)).toBeTruthy();
    fireEvent.change(panel.getByRole("textbox", { name: "Nový rozpočet klienta (USD)" }), { target: { value: "5" } });
    fireEvent.click(panel.getByRole("button", { name: "Zvýšit rozpočet a pokračovat" }));
    expect(await panel.findByText("AI čte dokument a navrhuje znalosti…")).toBeTruthy();
    expect(calls.find((c) => c.url.endsWith("/work/runs/RUN-1/steps/extract/budget"))?.body).toEqual({ budget_usd: 5, note: "" });
  });

  it("says why a run waits, and offers nothing to a person who may not run the client's work", async () => {
    const panel = await openDoc(CLIENT, {
      [`GET ${SOURCES}/${SRC}/proposals`]: () => proposalsRun({ step_status: "WAITING_PROVIDER", reason: "client_source_proposals_unconfigured" }),
    });
    expect(await panel.findByText("Čeká: AI návrhy z podkladů nejsou v tomto prostředí zapnuté.")).toBeTruthy();
    expect(panel.queryByRole("button", { name: /Navrhnout/ })).toBeNull();
    expect(panel.queryByRole("textbox", { name: /rozpočet/ })).toBeNull();
  });

  it("is not offered for a table", async () => {
    const panel = await openDoc(MAY_RUN, {
      [`GET ${SOURCES}/${SRC}`]: () => ({ ...detail(SRC, "odpovedi.xlsx"), family: "DATASET" }),
      [`GET ${SOURCES}/${SRC}/proposals`]: () => new Response("null", { status: 200 }),
    });
    expect(await panel.findByText("odpovedi.xlsx")).toBeTruthy();
    expect(panel.queryByRole("button", { name: "Navrhnout znalosti" })).toBeNull();
    expect(calls.some((c) => c.url.endsWith("/proposals") && c.url.includes("/sources/"))).toBe(false);
  });

  it("reach Ke schválení with the quote they rest on and where it stands in the document", async () => {
    const pending = {
      proposal_id: "KNP-7", origin: "CLIENT", study_id: null, study_name: null, item_id: null, kind: "FINDING", title: "Znalost značky 41 %",
      summary: "", status: "PROPOSED", proposed_by: "USR-1", proposed_at: "2026-10-15T10:00:00Z", decided_by: null, decided_at: null,
      decision_note: "", revision: null, base_revision: null, yours: true, source_id: null,
      from_source: { source_id: SRC, run_id: "RUN-1", quote: "Značku zná 41 % dospělých", locator: { page: 2 } },
    };
    api({
      "GET /api/v1/clients/CLI-a/knowledge/proposals": () => [pending],
      [`GET ${SOURCES}/${SRC}`]: () => detail(SRC, "Brief.pdf"),
    });
    window.history.replaceState(null, "", "/app/clients/CLI-a/knowledge?view=review");
    open();
    expect(await screen.findByText("„Značku zná 41 % dospělých“")).toBeTruthy();
    expect(screen.getByText("Citace · str. 2")).toBeTruthy();
    expect(screen.getByText(/Navrhla AI z dokumentu/)).toBeTruthy();
    expect(await screen.findByText("Brief.pdf")).toBeTruthy();
    // The AI's words, not the starter's: no "Váš návrh".
    expect(screen.queryByText("Váš návrh")).toBeNull();
    window.history.replaceState(null, "", "/");
  });
});
