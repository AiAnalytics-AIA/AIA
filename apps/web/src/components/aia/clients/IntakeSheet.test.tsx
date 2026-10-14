// @vitest-environment jsdom
// The intake sheet (client-workspace C7b) against a fake AIA API: opened from Přidat podklady
// or by files dropped on the client's page; each file kept and read, its row in words; a
// table as a dataset or a document with its personal columns named; pasted text; one item
// per file, filed in the chosen folder and labels. Every write is checked by its request.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ClientValue } from "./ClientContext";
import { KnowledgeArea } from "./KnowledgeArea";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/app/clients/CLI-a/knowledge",
  useRouter: () => ({ push, replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(window.location.search),
}));

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

const ALL = ["APPROVE_CLIENT_KNOWLEDGE", "CREATE_STUDY", "PROPOSE_CLIENT_KNOWLEDGE", "VIEW_CLIENT", "VIEW_CLIENT_KNOWLEDGE"];
const CLIENT = { client_id: "CLI-a", name: "Klient A", slug: "klient-a", status: "ACTIVE", your_role: "RESEARCHER", permissions: ALL, counts: { research: 0, simulations: 0, pending_proposals: 0, datasets: 0 } };
const PDF = "SRC-aaaaaaaaaaaaaaaa";
const XLSX = "SRC-bbbbbbbbbbbbbbbb";

const source = (id: string, filename: string, extra: Record<string, unknown> = {}) => ({
  source_id: id, sha256: "a".repeat(64), size_bytes: 2048, media_type: "application/pdf", family: "DOCUMENT", filename,
  outcome: "READ", reason: null, reader: "pdf/1", characters: 1200, segments: 2,
  occurrences: [{ occurrence_id: "SOC-1", filename, origin: "upload", added_by: "USR-1", added_at: "2026-10-14T08:00:00Z" }],
  created_at: "2026-10-14T08:00:00Z", created: true, ...extra,
});
const TABLE_DETAIL = {
  ...source(XLSX, "odpovedi.xlsx", { family: "DATASET", segments: 5 }),
  reading: {
    outcome: "READ", reader: "xlsx/1", reason: null, segments: [], notes: [],
    dataset: {
      more_sheets: false,
      sheets: [{ name: "Odpovědi", header_row: 1, rows: 4, truncated: false, columns: [
        { index: 0, letter: "A", header: "Věk", kind: "NUMBER", filled: 4, distinct: 4, distinct_capped: false, personal: null, sample: ["34"] },
        { index: 1, letter: "B", header: "E-mail", kind: "TEXT", filled: 4, distinct: 4, distinct_capped: false, personal: "email_header", sample: [] },
      ] }],
    },
  },
};

type Call = { method: string; url: string; body: unknown };
let calls: Call[] = [];
let proposalStatus = "APPROVED";
function api(overrides: Record<string, (body: unknown) => unknown> = {}) {
  calls = [];
  let item = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url).split("?")[0];
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ method, url: u, body });
      const k = "/api/v1/clients/CLI-a/knowledge";
      const routes: Record<string, (b: unknown) => unknown> = {
        "GET /config": () => ({ cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", apiBase: "", build: { sha: null } }),
        "GET /api/v1/clients/CLI-a": () => CLIENT,
        [`GET ${k}`]: () => [],
        [`GET ${k}/folders`]: () => [{ folder_id: "KNF-1", name: "Minulé výzkumy", item_count: 0 }, { folder_id: "KNF-2", name: "Zákazníci", item_count: 0 }],
        [`GET ${k}/labels`]: () => [{ label_id: "KNL-1", name: "2025", colour: "BLUE", item_count: 0 }],
        [`GET ${k}/proposals`]: () => [],
        [`PUT ${k}/placement`]: () => [],
        [`POST ${k}/proposals`]: (b) => ({ proposal_id: `KNP-${item}`, status: proposalStatus, item_id: proposalStatus === "APPROVED" ? `KNW-${item++}` : null, ...(b as object) }),
        "POST /api/v1/clients/CLI-a/sources": (b) => {
          const name = (b as { filename: string }).filename;
          if (name.endsWith(".key")) return new Response(JSON.stringify({ code: "unsupported_format", message: "no" }), { status: 422 });
          if (name.endsWith(".xlsx")) return source(XLSX, name, { family: "DATASET", segments: 5 });
          return source(PDF, name);
        },
        [`GET /api/v1/clients/CLI-a/sources/${XLSX}`]: () => TABLE_DETAIL,
        ...overrides,
      };
      const answer = (await routes[`${method} ${u}`]?.(body)) ?? {};
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
}
const sent = (method: string, path: string) => calls.filter((c) => c.method === method && c.url === `/api/v1/clients/CLI-a${path}`);
const file = (name: string, text = "%PDF-1.7") => new File([text], name);

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "a@example.test", subject: "s" }));
  proposalStatus = "APPROVED";
  push.mockReset();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const open = () =>
  render(
    <ClientValue client={CLIENT}>
      <KnowledgeArea />
    </ClientValue>,
  );
const sheet = () => within(screen.getByRole("dialog", { name: "Přidat podklady · Klient A" }));
const pick = (...files: File[]) => fireEvent.change(sheet().getByLabelText("Soubory k přidání"), { target: { files } });

describe("the intake sheet", () => {
  it("keeps and reads each file, asks a table what it is, and makes one filed item per file", async () => {
    api();
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Přidat podklady" }));
    // Links and AI extraction are drawn, not built: nothing can send them.
    expect((sheet().getByRole("button", { name: "Vložit odkaz" }) as HTMLButtonElement).disabled).toBe(true);
    expect((sheet().getByRole("checkbox") as HTMLInputElement).disabled).toBe(true);
    expect(sheet().getAllByText("V AIA zatím není").length).toBeGreaterThan(0);

    pick(file("Zadání výzkumu.pdf"), file("odpovedi.xlsx"), file("prezentace.key"));
    expect(await sheet().findByText(/Přečteno: 2 části/)).toBeTruthy();
    expect(await sheet().findByText("Přečteno: 1 list, 2 sloupce, 4 řádky")).toBeTruthy();
    expect(sheet().getByText(/Sloupec E-mail vypadá jako osobní údaj/)).toBeTruthy();
    expect((await sheet().findByRole("alert")).textContent).toBe("Soubor nelze přečíst: tento formát AIA nepřijímá");
    // One request per file, in order, the name as written.
    expect(sent("POST", "/sources").map((c) => (c.body as { filename: string }).filename)).toEqual(["Zadání výzkumu.pdf", "odpovedi.xlsx", "prezentace.key"]);

    // The table as a document, a title changed, the batch filed in a folder with a label.
    fireEvent.click(within(sheet().getByRole("group", { name: "Uložit odpovedi.xlsx jako" })).getByRole("button", { name: "Dokument" }));
    fireEvent.change(sheet().getByRole("textbox", { name: "Název znalosti pro Zadání výzkumu.pdf" }), { target: { value: "Zadání 2026" } });
    fireEvent.change(sheet().getByRole("combobox", { name: "Složka pro všechny" }), { target: { value: "KNF-1" } });
    fireEvent.change(sheet().getByRole("combobox", { name: "Složka pro odpovedi.xlsx" }), { target: { value: "KNF-2" } });
    fireEvent.change(sheet().getByRole("combobox", { name: "Přidat štítek…" }), { target: { value: "KNL-1" } });
    expect(sheet().getByText("Přidá se 2 dokumenty. 1 soubor nelze přidat.")).toBeTruthy();

    fireEvent.click(sheet().getByRole("button", { name: "Přidat 2 podklady" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(sent("POST", "/knowledge/proposals").map((c) => c.body)).toEqual([
      { kind: "DOCUMENT", title: "Zadání 2026", content: { source_id: PDF } },
      { kind: "DOCUMENT", title: "odpovedi", content: { source_id: XLSX } },
    ]);
    expect(sent("PUT", "/knowledge/placement").map((c) => c.body)).toEqual([
      { item_ids: ["KNW-0"], folder_id: "KNF-1" },
      { item_ids: ["KNW-1"], folder_id: "KNF-2" },
      { item_ids: ["KNW-0", "KNW-1"], add_labels: ["KNL-1"] },
    ]);
  });

  it("waits for a file still being read before it adds anything", async () => {
    let finish: (v: unknown) => void = () => {};
    api({ "POST /api/v1/clients/CLI-a/sources": () => new Promise((resolve) => (finish = resolve)) });
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Přidat podklady" }));
    pick(file("brief.pdf"));
    expect(await sheet().findByText("Ukládám a čtu…")).toBeTruthy();
    const add = sheet().getByRole("button", { name: "Čeká se na čtení…" }) as HTMLButtonElement;
    expect(add.disabled).toBe(true);
    await waitFor(() => expect(sent("POST", "/sources")).toHaveLength(1));
    finish(source(PDF, "brief.pdf"));
    expect(((await sheet().findByRole("button", { name: "Přidat 1 podklad" })) as HTMLButtonElement).disabled).toBe(false);
  });

  it("keeps pasted text as a text file read like the others", async () => {
    api();
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Přidat podklady" }));
    fireEvent.click(sheet().getByRole("button", { name: "Vložit text" }));
    fireEvent.change(sheet().getByRole("textbox", { name: "Název" }), { target: { value: "Poznámky z briefingu" } });
    fireEvent.change(sheet().getByRole("textbox", { name: "Text" }), { target: { value: "Klient chce srovnání." } });
    fireEvent.click(sheet().getByRole("button", { name: "Přidat do seznamu" }));
    await waitFor(() => expect(sent("POST", "/sources")).toHaveLength(1));
    const body = sent("POST", "/sources")[0].body as { filename: string; data_b64: string };
    expect(body.filename).toBe("Poznámky z briefingu.txt");
    expect(new TextDecoder().decode(Uint8Array.from(atob(body.data_b64), (c) => c.charCodeAt(0)))).toBe("Klient chce srovnání.");
  });

  it("opens with the files dropped anywhere on the client's page", async () => {
    api();
    open();
    const page = await screen.findByRole("heading", { name: "Klient A" });
    const dataTransfer = { types: ["Files"], files: [file("drop.pdf")] };
    fireEvent.dragOver(page, { dataTransfer });
    fireEvent.drop(page, { dataTransfer });
    expect(await sheet().findByText("drop.pdf", { exact: false })).toBeTruthy();
    await waitFor(() => expect(sent("POST", "/sources")).toHaveLength(1));
  });

  it("holds a table whose columns did not load, and reads them again on Zkusit znovu", async () => {
    let fail = true;
    api({
      [`GET /api/v1/clients/CLI-a/sources/${XLSX}`]: () =>
        fail ? new Response(JSON.stringify({ code: "internal", message: "x" }), { status: 500 }) : TABLE_DETAIL,
    });
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Přidat podklady" }));
    pick(file("odpovedi.xlsx"));
    expect(await sheet().findByText(/sloupce se nepodařilo načíst/)).toBeTruthy();
    expect((sheet().getByRole("button", { name: "Přidat 0 podkladů" }) as HTMLButtonElement).disabled).toBe(true);
    fail = false;
    fireEvent.click(sheet().getByRole("button", { name: "Zkusit znovu odpovedi.xlsx" }));
    expect(await sheet().findByText(/Sloupec E-mail vypadá jako osobní údaj/)).toBeTruthy();
    expect((sheet().getByRole("button", { name: "Přidat 1 podklad" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("files items made before a failed placement on the next try, without making them again", async () => {
    let fail = true;
    api({
      "PUT /api/v1/clients/CLI-a/knowledge/placement": () =>
        fail ? new Response(JSON.stringify({ code: "internal", message: "Výpadek" }), { status: 500 }) : [],
    });
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Přidat podklady" }));
    await sheet().findByRole("option", { name: "Minulé výzkumy" });
    fireEvent.change(sheet().getByRole("combobox", { name: "Složka pro všechny" }), { target: { value: "KNF-1" } });
    pick(file("a.pdf"));
    fireEvent.click(await sheet().findByRole("button", { name: "Přidat 1 podklad" }));
    expect(await sheet().findByText(/nepodařilo se je zařadit/)).toBeTruthy();
    fail = false;
    fireEvent.click(sheet().getByRole("button", { name: "Dokončit zařazení" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(sent("POST", "/knowledge/proposals")).toHaveLength(1);
    expect(sent("PUT", "/knowledge/placement").map((c) => c.body)).toEqual([
      { item_ids: ["KNW-0"], folder_id: "KNF-1" },
      { item_ids: ["KNW-0"], folder_id: "KNF-1" },
    ]);
  });

  it("holds every control still while the batch is being sent", async () => {
    let finish: (v: unknown) => void = () => {};
    api({ "POST /api/v1/clients/CLI-a/knowledge/proposals": (b) => new Promise((resolve) => (finish = () => resolve({ proposal_id: "KNP-0", status: "APPROVED", item_id: "KNW-0", ...(b as object) }))) });
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Přidat podklady" }));
    pick(file("a.pdf"));
    fireEvent.click(await sheet().findByRole("button", { name: "Přidat 1 podklad" }));
    await waitFor(() => expect(sent("POST", "/knowledge/proposals")).toHaveLength(1));
    const still = (name: string | RegExp, role = "button") => (sheet().getByRole(role, { name }) as HTMLButtonElement).disabled;
    expect(still("Přidávám…")).toBe(true);
    expect(still("Vybrat soubory")).toBe(true);
    expect(still("Vložit text")).toBe(true);
    expect(still("Zavřít")).toBe(true);
    expect(still("Zrušit")).toBe(true);
    expect(still("Odebrat a.pdf")).toBe(true);
    expect(still("Název znalosti pro a.pdf", "textbox")).toBe(true);
    expect(still("Složka pro a.pdf", "combobox")).toBe(true);
    expect(still("Složka pro všechny", "combobox")).toBe(true);
    // Esc does not close it either.
    fireEvent(screen.getByRole("dialog"), new Event("cancel", { cancelable: true }));
    expect(screen.queryByRole("dialog")).not.toBeNull();
    finish(null);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("says that items wait for someone else when the client asked for review, and files nothing yet", async () => {
    proposalStatus = "PROPOSED";
    api();
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Přidat podklady" }));
    fireEvent.change(sheet().getByRole("combobox", { name: "Složka pro všechny" }), { target: { value: "KNF-1" } });
    pick(file("brief.pdf"));
    fireEvent.click(await sheet().findByRole("button", { name: "Přidat 1 podklad" }));
    expect(await sheet().findByText(/čekají na schválení někým jiným/)).toBeTruthy();
    expect(sent("PUT", "/knowledge/placement")).toEqual([]);
  });
});
