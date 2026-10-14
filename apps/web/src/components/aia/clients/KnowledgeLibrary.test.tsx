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
    expect(screen.queryByRole("button", { name: "Přidat znalost" })).toBeNull();
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
  it("is stored as the client's source when picked, and the new item names it", async () => {
    api({
      [`POST ${SOURCES}`]: () => new Response(JSON.stringify({ ...source(SRC, "Zadání výzkumu.pdf"), created: true }), { status: 201 }),
      [`GET ${SOURCES}/${SRC}`]: () => detail(SRC, "Zadání výzkumu.pdf"),
    });
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Přidat znalost" }));
    const form = within(screen.getByRole("region", { name: "Přidat znalost klienta" }));
    // A fact takes no file; a document does.
    expect(form.queryByRole("group", { name: "Soubor" })).toBeNull();
    fireEvent.change(form.getByRole("combobox", { name: "Druh" }), { target: { value: "DOCUMENT" } });
    pick("Vybrat soubor", "Zadání výzkumu.pdf");

    expect(await form.findByText("Uloženo jako zdroj klienta.")).toBeTruthy();
    expect(await form.findByText(/Přečteno: 2 části, 1.200 znaků/)).toBeTruthy();
    const upload = calls.find((c) => c.method === "POST" && c.url === SOURCES)!;
    expect((upload.body as { filename: string }).filename).toBe("Zadání výzkumu.pdf");
    expect((upload.body as { data_b64: string }).data_b64).toBe(btoa("%PDF-1.7"));
    // The title follows the file's name, as written.
    expect((form.getByRole("textbox", { name: "Název" }) as HTMLInputElement).value).toBe("Zadání výzkumu");

    fireEvent.click(form.getByRole("button", { name: "Přidat znalost" }));
    await waitFor(() =>
      expect(sent("POST", "/proposals")[0].body).toEqual({ kind: "DOCUMENT", title: "Zadání výzkumu", summary: "", content: { source_id: SRC } }),
    );
  });

  it("says by name why a file was not kept, and sends no item with it", async () => {
    api({
      [`POST ${SOURCES}`]: () => new Response(JSON.stringify({ code: "unsupported_format", message: "AIA does not take 'x.exe'" }), { status: 422 }),
    });
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Přidat znalost" }));
    const form = within(screen.getByRole("region", { name: "Přidat znalost klienta" }));
    fireEvent.change(form.getByRole("combobox", { name: "Druh" }), { target: { value: "SOURCE" } });
    pick("Vybrat soubor", "x.exe");
    expect((await form.findByRole("alert")).textContent).toBe("Soubor nelze přečíst: tento formát AIA nepřijímá");
    expect(form.queryByRole("group", { name: "Soubor" })?.querySelector("[data-source]")).toBeNull();
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
