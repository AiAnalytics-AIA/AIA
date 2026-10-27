// @vitest-environment jsdom
// The client's knowledge library (client-workspace C4) against a fake AIA API: views,
// folders and labels; ticked items moved and labelled together; the open item edited into
// a new revision, filed and unlabelled; the history it carries. Every write is checked by
// the request it sends.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";

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
          const params = new URL(url, "http://x").searchParams;
          const folder = params.get("folder");
          const label = params.get("label");
          return ITEMS.filter((i) => !folder || (folder === "unfiled" ? !i.folder_id : i.folder_id === folder)).filter((i) => !label || (i.label_ids as string[]).includes(label));
        },
        [`GET ${base}/folders`]: () => FOLDERS,
        [`GET ${base}/labels`]: () => LABELS,
        [`GET ${base}/items/KNW-1/revisions`]: () => REVISIONS,
        [`PUT ${base}/placement`]: () => [],
        [`POST ${base}/folders`]: (b) => ({ folder_id: "KNF-2", item_count: 0, ...(b as object) }),
        [`PUT ${base}/folders/KNF-1`]: (b) => ({ folder_id: "KNF-1", item_count: 1, ...(b as object) }),
        [`DELETE ${base}/folders/KNF-1`]: () => new Response(null, { status: 204 }),
        [`POST ${base}/labels`]: (b) => ({ label_id: "KNL-9", item_count: 0, ...(b as object) }),
        [`PUT ${base}/labels/KNL-1`]: (b) => ({ ...LABELS[0], ...(b as object) }),
        [`PUT ${base}/labels/KNL-2`]: (b) => ({ ...LABELS[1], ...(b as object) }),
        [`DELETE ${base}/labels/KNL-1`]: () => new Response(null, { status: 204 }),
        [`POST ${base}/proposals`]: (b) => ({ proposal_id: "KNP-9", status: "APPROVED", ...(b as object) }),
        [`GET ${base}/proposals`]: () => [],
        "GET /api/v1/clients/CLI-a": () => CLIENT,
        ...overrides,
      };
      // A route may answer later (a promise), as a slow server does.
      const answer = (await routes[`${method} ${u.split("?")[0]}`]?.(body, u)) ?? {};
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
const navEl = () => screen.getByRole("navigation", { name: "Pohledy, složky a štítky" });
const nav = () => within(navEl());
const table = () => screen.getByRole("table", { name: "Znalosti klienta" });
const BASE = "/api/v1/clients/CLI-a/knowledge";
/** Opens the menu button `menu` inside `where` and chooses `item` from it. */
const choose = (where: HTMLElement, menu: string, item: string) => {
  fireEvent.click(within(where).getByRole("button", { name: menu }));
  fireEvent.click(within(within(where).getByRole("menu", { name: menu })).getByRole("menuitem", { name: item }));
};

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
    const region = screen.getByRole("region", { name: "Hromadné úpravy vybraných znalostí" });
    const bar = within(region);
    expect(bar.getByText("Vybráno: 2")).toBeTruthy();
    // Filing is a menu, never a select that files on change (input-interactions I3, audit D11).
    expect(bar.queryByRole("combobox")).toBeNull();
    choose(region, "Přesunout do složky", "Trh a konkurence");
    await waitFor(() => expect(sent("PUT", "/placement")[0].body).toEqual({ item_ids: ["KNW-2", "KNW-3"], folder_id: "KNF-1" }));
    choose(region, "Přidat štítek", "ověřit");
    await waitFor(() => expect(sent("PUT", "/placement")[1].body).toEqual({ item_ids: ["KNW-2", "KNW-3"], add_labels: ["KNL-2"] }));
    choose(region, "Odebrat štítek", "retail");
    await waitFor(() => expect(sent("PUT", "/placement")[2].body).toEqual({ item_ids: ["KNW-2", "KNW-3"], remove_labels: ["KNL-1"] }));
    choose(region, "Přesunout do složky", "Bez složky");
    await waitFor(() => expect(sent("PUT", "/placement")[3].body).toEqual({ item_ids: ["KNW-2", "KNW-3"], folder_id: null }));
  });

  it("files nothing while the arrows move through a bulk menu; Enter files the one reached (audit IA-6)", async () => {
    api();
    open();
    await screen.findByText("Hlavní konkurenti");
    fireEvent.click(screen.getByRole("checkbox", { name: "Vybrat Výroční zpráva" }));
    const bar = within(screen.getByRole("region", { name: "Hromadné úpravy vybraných znalostí" }));
    const move = bar.getByRole("button", { name: "Přesunout do složky" });
    fireEvent.keyDown(move, { key: "ArrowDown" });
    const items = within(bar.getByRole("menu", { name: "Přesunout do složky" })).getAllByRole("menuitem");
    await waitFor(() => expect(document.activeElement).toBe(items[0]));
    fireEvent.keyDown(items[0], { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[1]);
    expect(sent("PUT", "/placement")).toHaveLength(0);
    // Enter on a menu item is the button's own click.
    fireEvent.click(items[1]);
    await waitFor(() => expect(sent("PUT", "/placement")[0].body).toEqual({ item_ids: ["KNW-2"], folder_id: null }));
    expect(document.activeElement).toBe(move);
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

    // Its folder and labels are filed by menu (audit D13): the folder it is in is offered, not chosen.
    const aside = screen.getByRole("complementary", { name: "Otevřená znalost" });
    expect(within(panel.getByRole("group", { name: "Složka" })).getByText("Trh a konkurence")).toBeTruthy();
    fireEvent.click(panel.getByRole("button", { name: "Změnit složku" }));
    expect((panel.getByRole("menuitem", { name: "Trh a konkurence" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(panel.getByRole("button", { name: "Změnit složku" }));
    choose(aside, "Změnit složku", "Bez složky");
    await waitFor(() => expect(sent("PUT", "/placement")[0].body).toEqual({ item_ids: ["KNW-1"], folder_id: null }));
    fireEvent.click(panel.getByRole("button", { name: "Odebrat štítek retail" }));
    await waitFor(() => expect(sent("PUT", "/placement")[1].body).toEqual({ item_ids: ["KNW-1"], remove_labels: ["KNL-1"] }));
    // "Přidat štítek" offers only the labels it does not carry.
    fireEvent.click(panel.getByRole("button", { name: "Přidat štítek" }));
    expect(panel.queryByRole("menuitem", { name: "retail" })).toBeNull();
    fireEvent.click(panel.getByRole("menuitem", { name: "ověřit" }));
    await waitFor(() => expect(sent("PUT", "/placement")[2].body).toEqual({ item_ids: ["KNW-1"], add_labels: ["KNL-2"] }));
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
    // A second click while the decision is on its way sends nothing (the buttons wait).
    const approve = await screen.findByRole("button", { name: "Schválit" });
    fireEvent.click(approve);
    fireEvent.click(approve);
    expect(await screen.findByText(/návrh vychází z revize 1, nyní platí revize 2/)).toBeTruthy();
    const decisions = () => sent("POST", "/proposals/KNP-5/decision").map((c) => c.body);
    expect(decisions()).toEqual([{ approve: true, note: "" }]);
    fireEvent.click(screen.getByRole("button", { name: "Schválit místo revize 2" }));
    await waitFor(() => expect(decisions()[1]).toEqual({ approve: true, note: "", reviewed_revision: 2 }));
    window.history.replaceState(null, "", "/");
  });

  it("creates a folder in the folder list, no dialog, and says at the row when the name is taken", async () => {
    api();
    open();
    await screen.findByText("Hlavní konkurenti");
    await nav().findByRole("button", { name: /^Trh a konkurence/ });
    fireEvent.click(nav().getByRole("button", { name: "Nová složka" }));
    // input-interactions I5 (audit D1): a row where the folder will appear, never a modal prompt.
    expect(screen.queryByRole("dialog")).toBeNull();
    const row = nav().getByRole("textbox", { name: "Nová složka" });
    fireEvent.change(row, { target: { value: "  Interní   pravidla " } });
    fireEvent.keyDown(row, { key: "Enter" });
    await waitFor(() => expect(sent("POST", "/folders")[0].body).toEqual({ name: "Interní pravidla" }));
    // The next empty row opens for the next folder.
    await waitFor(() => expect((nav().getByRole("textbox", { name: "Nová složka" }) as HTMLInputElement).value).toBe(""));

    // A name the list already has, case and spacing aside, is said at the row as it is typed and never sent.
    fireEvent.change(nav().getByRole("textbox", { name: "Nová složka" }), { target: { value: "trh a  KONKURENCE" } });
    expect(nav().getByRole("alert").textContent).toBe("„Trh a konkurence“ už existuje.");
    fireEvent.keyDown(nav().getByRole("textbox", { name: "Nová složka" }), { key: "Enter" });
    expect(sent("POST", "/folders")).toHaveLength(1);
    cleanup();

    // The server's refusal (a folder made meanwhile elsewhere) is said at the same row, the name kept.
    api({
      "POST /api/v1/clients/CLI-a/knowledge/folders": () =>
        new Response(JSON.stringify({ code: "name_taken", message: "This client already has a folder by that name." }), { status: 409 }),
    });
    open();
    await screen.findByText("Hlavní konkurenti");
    fireEvent.click(nav().getByRole("button", { name: "Nová složka" }));
    const again = nav().getByRole("textbox", { name: "Nová složka" });
    fireEvent.change(again, { target: { value: "Archiv" } });
    fireEvent.keyDown(again, { key: "Enter" });
    expect((await nav().findByRole("alert")).textContent).toBe("Takový název už u tohoto klienta je.");
    expect((nav().getByRole("textbox", { name: "Nová složka" }) as HTMLInputElement).value).toBe("Archiv");
    // Esc leaves the row and gives "+ Nová složka" back.
    fireEvent.keyDown(nav().getByRole("textbox", { name: "Nová složka" }), { key: "Escape" });
    expect(nav().getByRole("button", { name: "Nová složka" })).toBeTruthy();
  });

  it("moves focus into the opened item, and Esc closes it and returns to its row (design system v3)", async () => {
    api();
    open({ ...CLIENT, permissions: ["VIEW_CLIENT", "VIEW_CLIENT_KNOWLEDGE"] });
    await screen.findByText("Hlavní konkurenti");
    const row = screen.getByRole("button", { name: /Hlavní konkurenti/ });
    fireEvent.click(row);
    const aside = await screen.findByRole("complementary", { name: "Otevřená znalost" });
    await waitFor(() => expect(document.activeElement?.id).toBe("kn-open"));
    fireEvent.keyDown(document.activeElement!, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("complementary", { name: "Otevřená znalost" })).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("button", { name: /Hlavní konkurenti/ })));
    expect(aside.isConnected).toBe(false);
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
    expect(within(panel.getByRole("group", { name: "Složka" })).getByText("Trh a konkurence")).toBeTruthy();
    expect(panel.queryByRole("button", { name: "Změnit složku" })).toBeNull();
    expect(panel.queryByRole("button", { name: "Přidat štítek" })).toBeNull();
    // Nothing in the side panel renames, recolours or deletes for a reader either.
    expect(nav().queryByRole("button", { name: /^Akce / })).toBeNull();
    expect(nav().queryByRole("button", { name: /^Barva štítku/ })).toBeNull();
    expect(nav().queryByRole("button", { name: "Nový štítek" })).toBeNull();
  });

  it("asks the API once the typing pauses, never letter by letter (audit D9, IA-4)", async () => {
    api();
    open();
    await screen.findByText("Hlavní konkurenti");
    const search = screen.getByRole("searchbox", { name: "Hledat ve znalostech" });
    const asked = () => sent("GET", "").filter((c) => new URL(c.url, "http://x").searchParams.has("q"));
    for (const typed of ["s", "se", "seg", "segm"]) fireEvent.change(search, { target: { value: typed } });
    expect(asked()).toHaveLength(0);
    await waitFor(() => expect(asked()).toHaveLength(1));
    expect(new URL(asked()[0].url, "http://x").searchParams.get("q")).toBe("segm");
    // Spaces alone change nothing that is asked.
    fireEvent.change(search, { target: { value: "segm  " } });
    await new Promise((r) => setTimeout(r, 400));
    expect(asked()).toHaveLength(1);
  });
});

// ---- folders and labels in the list (input-interactions chunk 2, audit D1-D7) -------------

describe("folders and labels, organized where they are listed", () => {
  it("renames a folder in place from its menu: Enter saves, no dialog, focus back on the row", async () => {
    // A frame may run before React commits the row's return (a loaded machine): run every frame
    // callback at once, the earliest it could, so focus cannot depend on that ordering.
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      cb(0);
      return 0;
    });
    api();
    open();
    await nav().findByRole("button", { name: "Trh a konkurence 1" });
    choose(navEl(), "Akce složky Trh a konkurence", "Přejmenovat");
    expect(screen.queryByRole("dialog")).toBeNull();
    const field = nav().getByRole("textbox", { name: "Název složky" }) as HTMLInputElement;
    expect(field.value).toBe("Trh a konkurence");
    await waitFor(() => expect(document.activeElement).toBe(field));
    fireEvent.change(field, { target: { value: "Trh  a soupeři " } });
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(() => expect(sent("PUT", "/folders/KNF-1")[0].body).toEqual({ name: "Trh a soupeři" }));
    // The row is back, under its new name, and focus with it.
    const row = await nav().findByRole("button", { name: /^Trh a soupeři/ });
    await waitFor(() => expect(document.activeElement).toBe(row));
  });

  it("opens a folder's name on F2; Esc restores it and sends nothing; a taken name is said at the field", async () => {
    api({ [`GET ${BASE}/folders`]: () => [...FOLDERS, { folder_id: "KNF-2", name: "Archiv", item_count: 0 }] });
    open();
    const row = await nav().findByRole("button", { name: "Trh a konkurence 1" });
    fireEvent.keyDown(row, { key: "F2" });
    const field = nav().getByRole("textbox", { name: "Název složky" });
    fireEvent.change(field, { target: { value: "archiv" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(nav().getByText("„Archiv“ už existuje.")).toBeTruthy();
    expect(field.getAttribute("aria-invalid")).toBe("true");
    fireEvent.keyDown(field, { key: "Escape" });
    const back = await nav().findByRole("button", { name: "Trh a konkurence 1" });
    await waitFor(() => expect(document.activeElement).toBe(back));
    expect(sent("PUT", "/folders/KNF-1")).toHaveLength(0);
  });

  it("keeps a rename the server refused at its field, Neuloženo – Zkusit znovu, until it goes", async () => {
    let refuse = true;
    api({
      [`PUT ${BASE}/folders/KNF-1`]: (b) =>
        refuse ? new Response(JSON.stringify({ code: "boom", message: "x" }), { status: 500 }) : { folder_id: "KNF-1", item_count: 1, ...(b as object) },
    });
    open();
    fireEvent.keyDown(await nav().findByRole("button", { name: "Trh a konkurence 1" }), { key: "F2" });
    const field = nav().getByRole("textbox", { name: "Název složky" });
    fireEvent.change(field, { target: { value: "Konkurence" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(await nav().findByText(/^Neuloženo/)).toBeTruthy();
    expect(nav().getByText("Konkurence")).toBeTruthy();
    refuse = false;
    fireEvent.click(nav().getByRole("button", { name: "Zkusit znovu" }));
    await nav().findByRole("button", { name: /^Konkurence/ });
    expect(sent("PUT", "/folders/KNF-1").map((c) => c.body)).toEqual([{ name: "Konkurence" }, { name: "Konkurence" }]);
  });

  it("renames a label on F2 and recolours it by its swatch; the arrows only move (audit D5, D6)", async () => {
    api();
    open();
    const retail = await nav().findByRole("button", { name: "retail 1" });
    fireEvent.keyDown(retail, { key: "F2" });
    const field = nav().getByRole("textbox", { name: "Název štítku" });
    fireEvent.change(field, { target: { value: "maloobchod" } });
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(() => expect(sent("PUT", "/labels/KNL-1")[0].body).toEqual({ name: "maloobchod" }));

    const swatch = await nav().findByRole("button", { name: "Barva štítku ověřit: Oranžová" });
    fireEvent.click(swatch);
    const list = nav().getByRole("listbox", { name: "Barva štítku ověřit" });
    const orange = within(list).getByRole("option", { name: "Oranžová" });
    await waitFor(() => expect(document.activeElement).toBe(orange));
    fireEvent.keyDown(orange, { key: "ArrowRight" });
    expect(sent("PUT", "/labels/KNL-2")).toHaveLength(0);
    fireEvent.click(within(list).getByRole("option", { name: "Modrá" }));
    await waitFor(() => expect(sent("PUT", "/labels/KNL-2")[0].body).toEqual({ colour: "BLUE" }));
    expect(nav().queryByRole("listbox")).toBeNull();
  });

  it("leaves focus where the person moved it while a rename was still saving", async () => {
    // A slow save: the field closes and the row would take focus back when the answer comes, after
    // the person has already opened another label's colours (once a CI flake in "renames a label on
    // F2 and recolours it by its swatch").
    let answer!: () => void;
    const saved = new Promise<void>((resolve) => { answer = resolve; });
    onTestFinished(() => answer());
    api({ "PUT /api/v1/clients/CLI-a/knowledge/labels/KNL-1": async (b) => { await saved; return { ...LABELS[0], ...(b as object) }; } });
    open();
    const retail = await nav().findByRole("button", { name: "retail 1" });
    fireEvent.keyDown(retail, { key: "F2" });
    const field = nav().getByRole("textbox", { name: "Název štítku" });
    fireEvent.change(field, { target: { value: "maloobchod" } });
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(() => expect(sent("PUT", "/labels/KNL-1")).toHaveLength(1));

    fireEvent.click(await nav().findByRole("button", { name: "Barva štítku ověřit: Oranžová" }));
    const orange = within(nav().getByRole("listbox", { name: "Barva štítku ověřit" })).getByRole("option", { name: "Oranžová" });
    await waitFor(() => expect(document.activeElement).toBe(orange));
    answer();
    await nav().findByRole("button", { name: /^maloobchod/ });
    expect(document.activeElement).toBe(orange);
  });

  it("creates a label in the list in the colour its swatch shows, the first one unused by default (audit D4)", async () => {
    api();
    open();
    await nav().findByRole("button", { name: "retail 1" });
    fireEvent.click(nav().getByRole("button", { name: "Nový štítek" }));
    const row = nav().getByRole("textbox", { name: "Nový štítek" });
    // GREEN and ORANGE are taken: the row starts on BLUE.
    expect(nav().getByRole("button", { name: "Barva nového štítku: Modrá" })).toBeTruthy();
    fireEvent.change(row, { target: { value: "priorita" } });
    fireEvent.keyDown(row, { key: "Enter" });
    await waitFor(() => expect(sent("POST", "/labels")[0].body).toEqual({ name: "priorita", colour: "BLUE" }));

    // A swatch chosen in the row is the colour it is made in; moving to the swatch keeps the row open.
    const next = nav().getByRole("textbox", { name: "Nový štítek" });
    fireEvent.change(next, { target: { value: "  " } });
    const pickColour = nav().getByRole("button", { name: /^Barva nového štítku/ });
    fireEvent.blur(next, { relatedTarget: pickColour });
    fireEvent.click(pickColour);
    fireEvent.click(nav().getByRole("option", { name: "Fialová" }));
    const still = nav().getByRole("textbox", { name: "Nový štítek" });
    fireEvent.change(still, { target: { value: "k ověření" } });
    fireEvent.keyDown(still, { key: "Enter" });
    await waitFor(() => expect(sent("POST", "/labels")[1].body).toEqual({ name: "k ověření", colour: "VIOLET" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("deletes a folder at once and Vrátit makes it again with its items filed back (audit D3)", async () => {
    api();
    open();
    await nav().findByRole("button", { name: "Trh a konkurence 1" });
    choose(navEl(), "Akce složky Trh a konkurence", "Smazat složku");
    // Its items are read first, then it goes: no confirmation, no dialog.
    await waitFor(() => expect(sent("DELETE", "/folders/KNF-1")).toHaveLength(1));
    expect(sent("GET", "").some((c) => c.url.includes("folder=KNF-1"))).toBe(true);
    expect(screen.queryByRole("dialog")).toBeNull();
    const toast = (await screen.findByText("Složka „Trh a konkurence“ smazána")).closest<HTMLElement>('[role="status"]')!;
    fireEvent.click(within(toast).getByRole("button", { name: "Vrátit" }));
    await waitFor(() => expect(sent("PUT", "/placement")[0]?.body).toEqual({ item_ids: ["KNW-1"], folder_id: "KNF-2" }));
    expect(sent("POST", "/folders")[0].body).toEqual({ name: "Trh a konkurence" });
    expect(screen.queryByText(/smazána/)).toBeNull();
  });

  it("deletes a label at once and Vrátit makes it again, in its colour, on its items (audit D7)", async () => {
    api();
    open();
    await nav().findByRole("button", { name: "retail 1" });
    choose(navEl(), "Akce štítku retail", "Smazat štítek");
    await waitFor(() => expect(sent("DELETE", "/labels/KNL-1")).toHaveLength(1));
    expect(sent("GET", "").some((c) => c.url.includes("label=KNL-1"))).toBe(true);
    fireEvent.click(await screen.findByRole("button", { name: "Vrátit" }));
    await waitFor(() => expect(sent("PUT", "/placement")[0]?.body).toEqual({ item_ids: ["KNW-1"], add_labels: ["KNL-9"] }));
    expect(sent("POST", "/labels")[0].body).toEqual({ name: "retail", colour: "GREEN" });
  });

  it("asks at the row, naming what goes, when the items filed there could not all be read", async () => {
    // The API counts five; the read returns one (filed meanwhile, or another's write): undo could not be whole.
    api({ [`GET ${BASE}/folders`]: () => [{ ...FOLDERS[0], item_count: 5 }] });
    open();
    await nav().findByRole("button", { name: "Trh a konkurence 5" });
    choose(navEl(), "Akce složky Trh a konkurence", "Smazat složku");
    const ask = await nav().findByRole("alertdialog");
    expect(ask.textContent).toContain("Smazat složku „Trh a konkurence“? Jejích 5 znalostí zůstane, jen bez složky. Smazání nepůjde vrátit.");
    expect(sent("DELETE", "/folders/KNF-1")).toHaveLength(0);
    // The safe choice has the focus; Ponechat leaves it all as it was.
    expect(document.activeElement).toBe(within(ask).getByRole("button", { name: "Ponechat" }));
    fireEvent.click(within(ask).getByRole("button", { name: "Ponechat" }));
    expect(nav().queryByRole("alertdialog")).toBeNull();
    choose(navEl(), "Akce složky Trh a konkurence", "Smazat složku");
    fireEvent.click(within(await nav().findByRole("alertdialog")).getByRole("button", { name: "Smazat" }));
    await waitFor(() => expect(sent("DELETE", "/folders/KNF-1")).toHaveLength(1));
    expect(screen.queryByRole("button", { name: "Vrátit" })).toBeNull();
  });
});

// ---- a document's file (client-workspace C7a) -------------------------------------------

const SRC = "SRC-0123456789abcdef";
const NEWER = "SRC-fedcba9876543210";
const source = (id: string, filename: string, extra: Record<string, unknown> = {}) => ({
  source_id: id, sha256: "a".repeat(64), size_bytes: 2048, media_type: "application/pdf", family: "DOCUMENT", filename,
  outcome: "READ", reason: null, reader: "pdf/1", characters: 1200, segments: 2,
  occurrences: [{ occurrence_id: "SOC-1", filename, origin: "upload", added_by: "USR-1", added_at: "2026-10-14T08:00:00Z" }],
  created_at: "2026-10-14T08:00:00Z", internal: null, ...extra,
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

describe("a source marked Interní dokument", () => {
  const MARK = { by: "USR-1", at: "2026-10-19T08:00:00Z" };
  const docItem = item("KNW-4", "Brief", { kind: "DOCUMENT", content: { source_id: SRC } });

  it("is marked and unmarked from the open item, saying what it does, who marked it and when", async () => {
    let internal: typeof MARK | null = null;
    api({
      "GET /api/v1/clients/CLI-a/knowledge": () => [...ITEMS, docItem],
      "GET /api/v1/clients/CLI-a/knowledge/items/KNW-4/revisions": () => [],
      "GET /api/v1/workspace/me": () => ({ user_id: "USR-1", email: null, organization_role: "MEMBER", may_administer: false }),
      [`GET ${SOURCES}/${SRC}`]: () => ({ ...detail(SRC, "Metodika.pdf"), internal }),
      [`PUT ${SOURCES}/${SRC}/internal`]: (b) => {
        internal = (b as { internal: boolean }).internal ? MARK : null;
        return { ...source(SRC, "Metodika.pdf"), internal };
      },
    });
    open();
    fireEvent.click(await screen.findByRole("button", { name: /Brief/ }));
    const panel = within(await screen.findByRole("complementary", { name: "Otevřená znalost" }));
    const toggle = (await panel.findByRole("button", { name: "Interní dokument" })) as HTMLButtonElement;
    // The toggle says what it does, beside it and as its description.
    expect(toggle.getAttribute("aria-pressed")).toBe("false");
    const what = "Interní dokument AIA bez údajů klienta; smí jít i širší trasou AI";
    expect(panel.getByText(what)).toBeTruthy();
    expect(document.getElementById(toggle.getAttribute("aria-describedby") ?? "")?.textContent).toBe(what);
    expect(panel.queryByText(/Označeno/)).toBeNull();
    // An unmarked source shows no marker, so it asks nobody's identity (Codex on #487).
    expect(calls.some((c) => c.url.endsWith("/workspace/me"))).toBe(false);

    fireEvent.click(toggle);
    await waitFor(() => expect(toggle.getAttribute("aria-pressed")).toBe("true"));
    // Who marked it is read once the mark is shown.
    expect(await panel.findByText(/Označeno .* · vámi/)).toBeTruthy();
    const puts = () => calls.filter((c) => c.method === "PUT" && c.url.endsWith(`/sources/${SRC}/internal`));
    expect(puts()[0].body).toEqual({ internal: true });

    fireEvent.click(toggle);
    await waitFor(() => expect(toggle.getAttribute("aria-pressed")).toBe("false"));
    expect(panel.queryByText(/Označeno/)).toBeNull();
    expect(puts()[1].body).toEqual({ internal: false });
  });

  it("shows who marked it to a person who may not change it, with no toggle", async () => {
    api({
      "GET /api/v1/clients/CLI-a/knowledge": () => [...ITEMS, docItem],
      "GET /api/v1/clients/CLI-a/knowledge/items/KNW-4/revisions": () => [],
      [`GET ${SOURCES}/${SRC}`]: () => ({ ...detail(SRC, "Metodika.pdf"), internal: { ...MARK, by: "USR-2" } }),
    });
    open({ ...CLIENT, permissions: ["VIEW_CLIENT", "VIEW_CLIENT_KNOWLEDGE"] });
    fireEvent.click(await screen.findByRole("button", { name: /Brief/ }));
    const panel = within(await screen.findByRole("complementary", { name: "Otevřená znalost" }));
    expect(await panel.findByText(/Označeno .* · uživatelem USR-2/)).toBeTruthy();
    expect(panel.getByText("Interní dokument")).toBeTruthy();
    expect(panel.queryByRole("button", { name: "Interní dokument" })).toBeNull();
    expect(calls.some((c) => c.method === "PUT" && c.url.endsWith("/internal"))).toBe(false);
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
    expect(await panel.findByText("AI navrhla 2 návrhy. Čekají v Ke schválení.")).toBeTruthy();
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
