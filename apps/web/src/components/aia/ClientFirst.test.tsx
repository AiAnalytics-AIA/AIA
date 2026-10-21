// @vitest-environment jsdom
// The client-first shell (ADR 0015) against a fake AIA API: the directory, one
// client's workspace and its areas, a research re-homed under its client, and the
// rules that keep scope honest -- 404 outside it, a study only under its own
// client, the working content only from the study's binding.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ClientDirectory } from "./clients/ClientDirectory";
import { ClientProvider } from "./clients/ClientContext";
import { ClientOverview } from "./clients/ClientOverview";
import { KnowledgeArea } from "./clients/KnowledgeArea";
import { ProfileArea } from "./clients/ProfileArea";
import { StudyList } from "./clients/StudyList";
import { SettingsPage } from "./GlobalPages";
import { ResearchStage, ResearchStudy } from "./ResearchStudy";

let path = "/app/clients";
const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => path,
  useRouter: () => ({ push, replace }),
  useSearchParams: () => new URLSearchParams(window.location.search),
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
}));

const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/research/fixtures/empty-project.json"), "utf8"));
const A = { client_id: "CLI-a", name: "Klient A", slug: "klient-a", status: "ACTIVE", your_role: "LEAD", permissions: ["APPROVE_CLIENT_KNOWLEDGE", "CREATE_STUDY", "PROPOSE_CLIENT_KNOWLEDGE", "VIEW_CLIENT", "VIEW_CLIENT_KNOWLEDGE"] };
const study = (id: string, name: string, kind: "RESEARCH" | "SIMULATION", extra: Record<string, unknown> = {}) => ({
  study_id: id, client_id: "CLI-a", name, slug: id.toLowerCase(), kind, status: "ACTIVE", accepts_work: true,
  last_stage: null, has_working_content: false, created_at: null, modified_at: "2026-09-24T10:00:00Z", ...extra,
});
const STUDIES = [
  study("STU-1", "Vnímání značky", "RESEARCH", { last_stage: "questionnaire", has_working_content: true }),
  study("STU-2", "Cenové scénáře", "SIMULATION"),
];
const PROPOSALS = [
  { proposal_id: "KNP-1", origin: "STUDY", study_id: "STU-1", study_name: "Vnímání značky", item_id: null, kind: "FINDING", title: "Značka působí spolehlivě", summary: "", status: "PROPOSED", proposed_by: "USR-2", proposed_at: null, decided_by: null, decided_at: null, decision_note: "", revision: null, yours: false },
  { proposal_id: "KNP-2", origin: "CLIENT", study_id: null, study_name: null, item_id: null, kind: "TERM", title: "Můj pojem", summary: "", status: "PROPOSED", proposed_by: "USR-1", proposed_at: null, decided_by: null, decided_at: null, decision_note: "", revision: null, yours: true },
];

type Call = { method: string; url: string; body: unknown };
let calls: Call[] = [];
function api(overrides: Record<string, (body: unknown) => unknown> = {}) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ method, url: u, body });
      const key = `${method} ${u.split("?")[0]}`;
      const routes: Record<string, (b: unknown) => unknown> = {
        "GET /config": () => ({ cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", apiBase: "", build: { sha: null } }),
        "GET /api/v1/workspace/me": () => ({ user_id: "USR-1", email: "a@example.test", organization_role: "OWNER", may_administer: true }),
        "GET /api/v1/workspace/clients": () => [{ client_id: "CLI-a", name: "Klient A", slug: "klient-a", your_role: "LEAD", active_count: 2, study_count: 2, recent: STUDIES, modified_at: null }],
        "POST /api/v1/workspace/clients": () => ({ ...A, client_id: "CLI-new", name: "Nový" }),
        "GET /api/v1/clients/CLI-a": () => A,
        "GET /api/v1/clients/CLI-b": () => new Response('{"code":"not_found","message":"No such resource."}', { status: 404 }),
        "GET /api/v1/clients/CLI-a/overview": () => ({
          client: A, active: STUDIES, previous_count: 3, recent_outputs: [],
          knowledge: { context_revision: 7, items_by_kind: { SOURCE: 2, FACT: 1, TERM: 4, DIMENSION: 1 }, pending_proposals: 1, last_approved_at: null },
          pending: [PROPOSALS[0]],
        }),
        "GET /api/v1/clients/CLI-a/studies": () => {
          const kind = new URL(u, "http://x").searchParams.get("kind");
          return kind ? STUDIES.filter((s) => s.kind === kind) : STUDIES;
        },
        "POST /api/v1/clients/CLI-a/studies": (b) => study("STU-9", String((b as { name: string }).name), (b as { kind: "RESEARCH" }).kind),
        "GET /api/v1/clients/CLI-a/knowledge": () => [{ item_id: "KNW-1", kind: "SOURCE", title: "Výroční zpráva", summary: "", content: {}, revision: 1, modified_at: null, folder_id: null, label_ids: [] }],
        "GET /api/v1/clients/CLI-a/knowledge/folders": () => [],
        "GET /api/v1/clients/CLI-a/knowledge/labels": () => [],
        "GET /api/v1/clients/CLI-a/knowledge/items/KNW-1/revisions": () => [],
        "GET /api/v1/clients/CLI-a/knowledge/proposals": () => PROPOSALS,
        "POST /api/v1/clients/CLI-a/knowledge/proposals/KNP-1/decision": () => ({ ...PROPOSALS[0], status: "APPROVED" }),
        "POST /api/v1/clients/CLI-a/knowledge/proposals": (b) => ({ ...PROPOSALS[1], ...(b as { kind: string; title: string }), status: "APPROVED", revision: 1 }),
        "GET /api/v1/studies/STU-1/workspace": () => ({ study: STUDIES[0], client_name: "Klient A", your_role: "LEAD", can_edit: true, content_state: "NATIVE" }),
        "GET /api/v1/studies/STU-X/workspace": () => ({ study: { ...STUDIES[0], study_id: "STU-X", client_id: "CLI-other" }, client_name: "Jiný", your_role: "LEAD", can_edit: true, content_state: "NATIVE" }),
        "PUT /api/v1/studies/STU-1/workspace/stage": () => new Response(null, { status: 204 }),
        "GET /api/v1/studies/STU-1/workspace/content": () => ({ study_id: "STU-1", state: "NATIVE", revision: 3, revision_id: "REV-3", content: { title: "Vnímání značky" }, analysis: null, template: EMPTY, saved_at: null, saved_by: null, can_edit: true, lineage: {} }),
        ...overrides,
      };
      const answer = routes[key]?.(body) ?? {};
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
}
const called = (method: string, prefix: string) => calls.filter((c) => c.method === method && c.url.startsWith(prefix));

beforeEach(() => {
  // jsdom has no <dialog> behaviour.
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
  push.mockReset();
  replace.mockReset();
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "a@example.test", subject: "s" }));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const inClient = (clientId: string, node: ReactNode) => <ClientProvider clientId={clientId}>{node}</ClientProvider>;

describe("Klienti", () => {
  it("is the first decision: the clients you work for, and nothing else", async () => {
    api();
    render(<ClientDirectory />);
    expect(await screen.findByRole("heading", { level: 1, name: "Klienti" })).toBeTruthy();
    const card = (await screen.findByText("Klient A")).closest("a")!;
    expect(card.getAttribute("href")).toBe("/app/clients/CLI-a");
    expect(within(card).getByText("2 aktivní práce")).toBeTruthy();
    // No stage, questionnaire or agent on the first screen.
    expect(screen.queryByText(/Dotazník|Audience|Dimenze|Agent/)).toBeNull();
  });

  it("finds clients by their name or recent study and distinguishes no match from an empty organization", async () => {
    api();
    render(<ClientDirectory />);
    await screen.findByText("Klient A");
    const search = screen.getByRole("searchbox", { name: "Hledat klienta nebo studii" });
    fireEvent.change(search, { target: { value: "značky" } });
    expect(screen.getByText("Klient A")).toBeTruthy();
    fireEvent.change(search, { target: { value: "not-found" } });
    expect(screen.queryByText("Klient A")).toBeNull();
    expect(screen.getByText(/Žádný klient ani jeho nedávná studie/)).toBeTruthy();
    fireEvent.change(search, { target: { value: "KLIENT A" } });
    expect(screen.getByText("Klient A")).toBeTruthy();
    expect(called("POST", "/api/v1/workspace/clients")).toHaveLength(0);
  });

  it("lets an administrator start a client and opens it", async () => {
    api();
    render(<ClientDirectory />);
    fireEvent.click(await screen.findByRole("button", { name: "Nový klient" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "Nový" } });
    fireEvent.submit(dialog.querySelector("form")!);
    await waitFor(() => expect(push).toHaveBeenCalledWith("/app/clients/CLI-new"));
    expect(called("POST", "/api/v1/workspace/clients")[0].body).toEqual({ name: "Nový" });
  });

  it("offers a new client to a researcher who may not administer (ADR 0019)", async () => {
    api({ "GET /api/v1/workspace/me": () => ({ user_id: "USR-3", email: null, organization_role: "MEMBER", may_administer: false }) });
    render(<ClientDirectory />);
    await screen.findByText("Klient A");
    fireEvent.click(screen.getByRole("button", { name: "Nový klient" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "Nový" } });
    fireEvent.submit(dialog.querySelector("form")!);
    await waitFor(() => expect(push).toHaveBeenCalledWith("/app/clients/CLI-new"));
  });
});

describe("a client's workspace", () => {
  it("cannot be opened outside your scope: a 404 says there is nothing here", async () => {
    path = "/app/clients/CLI-b";
    api();
    render(inClient("CLI-b", <ClientOverview />));
    expect(await screen.findByRole("heading", { name: "Tady nic není" })).toBeTruthy();
    expect(called("GET", "/api/v1/clients/CLI-b/overview")).toEqual([]);
  });

  it("says whose workspace it is, and lets the researcher continue their work", async () => {
    path = "/app/clients/CLI-a";
    api();
    render(inClient("CLI-a", <ClientOverview />));
    expect(await screen.findByRole("heading", { level: 1, name: "Klient A" })).toBeTruthy();
    const crumbs = within(screen.getByRole("navigation", { name: "Kde jste" })).getAllByRole("listitem");
    expect(crumbs.map((c) => c.textContent?.replace("/", "").trim())).toEqual(["Klienti", "Klient A"]);
    const tabs = within(screen.getByRole("navigation", { name: "Oblasti klienta" })).getAllByRole("link");
    expect(tabs.map((a) => [a.textContent, a.getAttribute("href")])).toEqual([
      ["Přehled", "/app/clients/CLI-a"],
      ["Výzkumy", "/app/clients/CLI-a/research"],
      ["Simulace", "/app/clients/CLI-a/simulations"],
      ["Znalosti", "/app/clients/CLI-a/knowledge"],
      ["Data", "/app/clients/CLI-a/data"],
      ["Profil", "/app/clients/CLI-a/profile"],
    ]);
    const research = (await screen.findByText("Vnímání značky")).closest("a")!;
    expect(research.getAttribute("href")).toBe("/app/clients/CLI-a/research/STU-1/questionnaire");
    expect(within(research).getByText("Výzkum · Dotazník")).toBeTruthy();
    expect(screen.getByText("Cenové scénáře").closest("a")!.getAttribute("href")).toBe("/app/clients/CLI-a/simulations/STU-2");
    expect(screen.getByText("Revize znalostí 7", { exact: false })).toBeTruthy();
    // The context counts by section, each named in words (a missing string would show its key).
    for (const name of ["Zdroje", "Znalosti", "Dimenze", "Audience"]) expect(screen.getByText(name, { selector: "dt" })).toBeTruthy();
    expect(screen.getByText("Značka působí spolehlivě")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Nový výzkum" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Nová simulace" })).toBeTruthy();
  });

  it("counts on its tabs what is open and what waits on a person, and says it in words", async () => {
    path = "/app/clients/CLI-a";
    api({ "GET /api/v1/clients/CLI-a": () => ({ ...A, counts: { research: 3, simulations: 1, pending_proposals: 2, datasets: 0 } }) });
    render(inClient("CLI-a", <ClientOverview />));
    const tabs = within(await screen.findByRole("navigation", { name: "Oblasti klienta" }));
    expect(tabs.getByRole("link", { name: "Výzkumy, otevřených: 3" })).toBeTruthy();
    expect(tabs.getByRole("link", { name: "Simulace, otevřených: 1" })).toBeTruthy();
    expect(tabs.getByRole("link", { name: "Znalosti, čeká na schválení: 2" })).toBeTruthy();
    // Nothing counted, nothing drawn: no "0" badge on Data, none on Přehled or Profil.
    expect(tabs.getByRole("link", { name: "Data" })).toBeTruthy();
    expect(tabs.getByRole("link", { name: "Profil" })).toBeTruthy();
    // The client's status beside its name.
    expect(within(screen.getByRole("banner")).getByText("Aktivní")).toBeTruthy();
  });

  it("draws no counts when the API sends none: unknown is not zero", async () => {
    path = "/app/clients/CLI-a";
    api({ "GET /api/v1/clients/CLI-a": () => ({ ...A, counts: { research: 3, simulations: 0, pending_proposals: null, datasets: null } }) });
    render(inClient("CLI-a", <ClientOverview />));
    const tabs = within(await screen.findByRole("navigation", { name: "Oblasti klienta" }));
    expect(tabs.getByRole("link", { name: "Znalosti" })).toBeTruthy();
    expect(tabs.getByRole("link", { name: "Data" })).toBeTruthy();
  });

  it("brings material from any area: Přidat podklady opens the intake sheet there", async () => {
    path = "/app/clients/CLI-a";
    api();
    render(inClient("CLI-a", <ClientOverview />));
    fireEvent.click(await screen.findByRole("button", { name: "Přidat podklady" }));
    expect(screen.getByRole("dialog", { name: "Přidat podklady · Klient A" })).toBeTruthy();
    expect(push).not.toHaveBeenCalled();
  });

  it("writes knowledge on Znalosti, also when another page asked for the form", async () => {
    path = "/app/clients/CLI-a/knowledge";
    window.history.pushState({}, "", "/app/clients/CLI-a/knowledge?add=1");
    api();
    render(inClient("CLI-a", <KnowledgeArea />));
    const form = (await screen.findByRole("heading", { name: "Napsat znalost klienta" })).closest("section")!;
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/app/clients/CLI-a/knowledge"));
    window.history.pushState({}, "", "/");
    // What is added re-reads the client, so the tabs' counts follow.
    fireEvent.change(within(form).getAllByRole("textbox")[0], { target: { value: "Výroční zpráva 2026" } });
    fireEvent.click(within(form).getByRole("button", { name: "Uložit znalost" }));
    await waitFor(() => expect(called("GET", "/api/v1/clients/CLI-a").filter((c) => c.url.endsWith("/CLI-a"))).toHaveLength(2));
  });

  it("does not offer to add knowledge to a person who may not", async () => {
    path = "/app/clients/CLI-a";
    api({ "GET /api/v1/clients/CLI-a": () => ({ ...A, permissions: ["CREATE_STUDY", "VIEW_CLIENT"] }) });
    render(inClient("CLI-a", <ClientOverview />));
    expect(await screen.findByRole("button", { name: "Nový výzkum" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Přidat podklady" })).toBeNull();
  });

  const EDITOR = { ...A, permissions: [...A.permissions, "EDIT_CLIENT_PROFILE"], self_approval_allowed: true, self_approval_source: "default" };
  const PROFILE = {
    short_code: "KA", industry: "Bankovnictví", market: "Česko", description: "",
    contacts: [{ contact_id: "CON-1", client_id: "CLI-a", name: "Jana Nová", role: "Marketing", email: "jana@klient.test", receives_reports: true }],
    history: [{ action: "CLIENT_CONTACT_ADDED", actor_id: "USR-1", at: "2026-10-12T10:00:00Z", fields: [], contact_name: "Jana Nová" }],
  };
  const profileApi = (extra: Record<string, (body: unknown) => unknown> = {}) =>
    api({
      "GET /api/v1/clients/CLI-a": () => EDITOR,
      "GET /api/v1/clients/CLI-a/profile": () => PROFILE,
      "PUT /api/v1/clients/CLI-a/profile": (b) => ({ ...PROFILE, ...(b as object) }),
      "POST /api/v1/clients/CLI-a/contacts": (b) => ({ contact_id: "CON-2", client_id: "CLI-a", ...(b as object) }),
      "DELETE /api/v1/clients/CLI-a/contacts/CON-1": () => new Response(null, { status: 204 }),
      "GET /api/v1/clients/CLI-a/knowledge": () => [
        { item_id: "KNW-5", kind: "ENTITY", title: "Konkurent B", summary: "", content: { role: "competitor" }, revision: 1, modified_at: null, folder_id: null, label_ids: [] },
        { item_id: "KNW-1", kind: "SOURCE", title: "Výroční zpráva", summary: "", content: {}, revision: 1, modified_at: null, folder_id: null, label_ids: [] },
      ],
      ...extra,
    });

  it("shows the client record on Profil and saves its details on the client", async () => {
    path = "/app/clients/CLI-a/profile";
    profileApi();
    render(inClient("CLI-a", <ProfileArea />));
    const record = (await screen.findByRole("heading", { name: "Klient" })).closest("section")!;
    expect(within(record).getByText("Klient A")).toBeTruthy();
    expect(within(record).getByText("Aktivní")).toBeTruthy();
    const tab = within(screen.getByRole("navigation", { name: "Oblasti klienta" })).getByRole("link", { name: "Profil" });
    expect(tab.getAttribute("aria-current")).toBe("page");

    const details = (await screen.findByRole("heading", { name: "Základní údaje" })).closest("form")!;
    const industry = within(details).getByRole("textbox", { name: "Odvětví" }) as HTMLInputElement;
    expect(industry.value).toBe("Bankovnictví");
    const save = within(details).getByRole("button", { name: "Uložit profil" }) as HTMLButtonElement;
    // Nothing changed, nothing to save.
    expect(save.disabled).toBe(true);
    fireEvent.change(industry, { target: { value: "Pojišťovnictví" } });
    fireEvent.click(save);
    await waitFor(() => expect(called("PUT", "/api/v1/clients/CLI-a/profile")).toHaveLength(1));
    expect(called("PUT", "/api/v1/clients/CLI-a/profile")[0].body).toEqual({ short_code: "KA", industry: "Pojišťovnictví", market: "Česko", description: "" });
    // The history names the contact, and what the profile changed re-reads it.
    expect(screen.getByText("Přidán kontakt Jana Nová")).toBeTruthy();
    await waitFor(() => expect(called("GET", "/api/v1/clients/CLI-a/profile")).toHaveLength(2));
  });

  it("adds and removes a contact, and adds a competitor as the client's knowledge", async () => {
    path = "/app/clients/CLI-a/profile";
    profileApi();
    render(inClient("CLI-a", <ProfileArea />));
    const contacts = (await screen.findByRole("heading", { name: "Kontakty" })).closest("section")!;
    expect(within(contacts).getByText("jana@klient.test")).toBeTruthy();
    fireEvent.click(within(contacts).getByRole("button", { name: "Přidat kontakt" }));
    fireEvent.change(within(contacts).getByRole("textbox", { name: "Jméno" }), { target: { value: "Petr" } });
    fireEvent.click(within(contacts).getByRole("checkbox", { name: "Dostává výsledky" }));
    fireEvent.click(within(contacts).getByRole("button", { name: "Uložit kontakt" }));
    await waitFor(() => expect(called("POST", "/api/v1/clients/CLI-a/contacts")).toHaveLength(1));
    expect(called("POST", "/api/v1/clients/CLI-a/contacts")[0].body).toEqual({ name: "Petr", role: "", email: "", receives_reports: true });
    fireEvent.click(within(contacts).getByRole("button", { name: "Odebrat kontakt Jana Nová" }));
    await waitFor(() => expect(called("DELETE", "/api/v1/clients/CLI-a/contacts/CON-1")).toHaveLength(1));

    const entities = screen.getByRole("heading", { name: "Značky a konkurenti" }).closest("section")!;
    expect(await within(entities).findByText("Konkurent B")).toBeTruthy();
    // A source is not an entity.
    expect(within(entities).queryByText("Výroční zpráva")).toBeNull();
    fireEvent.change(within(entities).getByRole("textbox", { name: "Název" }), { target: { value: "Naše značka" } });
    fireEvent.change(within(entities).getByRole("combobox", { name: "Druh" }), { target: { value: "own_brand" } });
    fireEvent.click(within(entities).getByRole("button", { name: "Přidat do Znalostí" }));
    await waitFor(() => expect(called("POST", "/api/v1/clients/CLI-a/knowledge/proposals")).toHaveLength(1));
    expect(called("POST", "/api/v1/clients/CLI-a/knowledge/proposals")[0].body).toMatchObject({ kind: "ENTITY", title: "Naše značka", content: { role: "own_brand" } });
  });

  it("offers the self-approval switch to an administrator and turns it off for this client", async () => {
    path = "/app/clients/CLI-a/profile";
    profileApi({ "PUT /api/v1/self-approval": () => ({}) });
    render(inClient("CLI-a", <ProfileArea />));
    const sw = await screen.findByRole("switch", { name: /Vlastní schvalování znalostí/ });
    expect(sw.getAttribute("aria-checked")).toBe("true");
    fireEvent.click(sw);
    await waitFor(() => expect(calls.some((c) => c.method !== "GET" && c.url.includes("self-approval"))).toBe(true));
    expect(calls.find((c) => c.method !== "GET" && c.url.includes("self-approval"))!.body).toEqual({ allowed: false, client_id: "CLI-a" });
  });

  it("shows the client's own budget on Profil and sets it, apart from its studies'", async () => {
    path = "/app/clients/CLI-a/profile";
    let budget = { budget_usd: 0, spent_usd: 0, reserved_usd: 0, available_usd: 0 };
    profileApi({
      "GET /api/v1/clients/CLI-a": () => ({ ...EDITOR, permissions: [...EDITOR.permissions, "VIEW_CLIENT_COSTS", "MANAGE_CLIENT_BUDGET"] }),
      "GET /api/v1/clients/CLI-a/budget": () => budget,
      "PUT /api/v1/clients/CLI-a/budget": (b) => {
        const v = (b as { budget_usd: number }).budget_usd;
        budget = { budget_usd: v, spent_usd: 0, reserved_usd: 0, available_usd: v };
        return budget;
      },
    });
    render(inClient("CLI-a", <ProfileArea />));
    const card = (await screen.findByRole("heading", { name: "Rozpočet klienta" })).closest("section")!;
    expect(await within(card).findByText(/práce AI na klientovi počká/)).toBeTruthy();
    expect(within(card).getByText(/Rozpočty studií jsou zvlášť/)).toBeTruthy();
    fireEvent.click(within(card).getByRole("button", { name: "Nastavit rozpočet" }));
    fireEvent.change(within(card).getByRole("spinbutton", { name: "Rozpočet v USD" }), { target: { value: "25.5" } });
    fireEvent.click(within(card).getByRole("button", { name: "Uložit rozpočet" }));
    await waitFor(() => expect(called("PUT", "/api/v1/clients/CLI-a/budget")).toHaveLength(1));
    expect(called("PUT", "/api/v1/clients/CLI-a/budget")[0].body).toEqual({ budget_usd: 25.5 });
    expect(await within(card).findAllByText(/25,50\sUSD/)).toHaveLength(2);
    expect(within(card).queryByText(/počká/)).toBeNull();
  });

  it("shows no budget to a person who may not see the client's costs", async () => {
    path = "/app/clients/CLI-a/profile";
    profileApi();
    render(inClient("CLI-a", <ProfileArea />));
    await screen.findByRole("heading", { name: "Základní údaje" });
    expect(screen.queryByRole("heading", { name: "Rozpočet klienta" })).toBeNull();
    expect(called("GET", "/api/v1/clients/CLI-a/budget")).toHaveLength(0);
  });

  it("shows the profile read-only to a person who may not change it", async () => {
    path = "/app/clients/CLI-a/profile";
    profileApi({ "GET /api/v1/clients/CLI-a": () => A, "GET /api/v1/workspace/me": () => ({ user_id: "USR-2", email: "b@example.test", organization_role: "MEMBER", may_administer: false }) });
    render(inClient("CLI-a", <ProfileArea />));
    const details = (await screen.findByRole("heading", { name: "Základní údaje" })).closest("form")!;
    expect((within(details).getByRole("textbox", { name: "Odvětví" }) as HTMLInputElement).readOnly).toBe(true);
    expect(screen.queryByRole("button", { name: "Uložit profil" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Přidat kontakt" })).toBeNull();
    expect(screen.queryByRole("switch")).toBeNull();
    expect(screen.getByText("Pravidlo mění správce organizace.")).toBeTruthy();
  });

  it("shows a client's research as a table: archived out of the default view, what each brought, two orders", async () => {
    path = "/app/clients/CLI-a/research";
    const k = (approved: number, proposed: number) => ({ approved, proposed, rejected: 0 });
    api({
      "GET /api/v1/clients/CLI-a/studies": () => [
        study("STU-1", "Vnímání značky", "RESEARCH", { last_stage: "questionnaire", has_working_content: true, modified_at: "2026-10-10T10:00:00Z", knowledge: k(2, 1) }),
        study("STU-3", "Archivní brand", "RESEARCH", { status: "ARCHIVED", modified_at: "2026-01-01T10:00:00Z", knowledge: k(0, 0) }),
        study("STU-4", "Cena účtů", "RESEARCH", { status: "IN_REVIEW", modified_at: "2026-09-01T10:00:00Z", knowledge: k(0, 0) }),
      ],
    });
    render(inClient("CLI-a", <StudyList kind="RESEARCH" />));
    const table = await screen.findByRole("table", { name: "Výzkumy" });
    // Re-read the table each time: an empty filter unmounts it.
    const names = () => within(screen.getByRole("table", { name: "Výzkumy" })).getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0].querySelector("a span span")!.textContent);
    expect(names()).toEqual(["Vnímání značky", "Cena účtů"]);
    const first = within(table).getAllByRole("row")[1];
    expect(within(first).getByText("přijato: 2")).toBeTruthy();
    expect(within(first).getByText("čeká: 1")).toBeTruthy();
    expect(within(first).getByRole("link").getAttribute("href")).toBe("/app/clients/CLI-a/research/STU-1/questionnaire");

    const filters = screen.getByRole("group", { name: "Stav studií" });
    expect(within(filters).getByRole("button", { name: "Aktuální 2" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(within(filters).getByRole("button", { name: "Archiv 1" }));
    expect(names()).toEqual(["Archivní brand"]);
    fireEvent.click(within(filters).getByRole("button", { name: "Ke kontrole 1" }));
    expect(names()).toEqual(["Cena účtů"]);
    fireEvent.click(within(filters).getByRole("button", { name: "Předané 0" }));
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getByText("Zatím nic předaného.")).toBeTruthy();

    fireEvent.click(within(filters).getByRole("button", { name: "Aktuální 2" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Řadit" }), { target: { value: "name" } });
    expect(names()).toEqual(["Cena účtů", "Vnímání značky"]);
  });

  it("leaves out what a study brought when the API does not say", async () => {
    path = "/app/clients/CLI-a/simulations";
    api();
    render(inClient("CLI-a", <StudyList kind="SIMULATION" />));
    const table = await screen.findByRole("table", { name: "Simulace" });
    expect(within(table).queryByRole("columnheader", { name: "Přineslo do znalostí" })).toBeNull();
    expect(within(table).getByText("Cenové scénáře")).toBeTruthy();
  });

  it("opens on what waits on a person, then what changed and what in the knowledge wants attention", async () => {
    path = "/app/clients/CLI-a";
    api({
      "GET /api/v1/clients/CLI-a/overview": () => ({
        client: A,
        active: [...STUDIES, study("STU-5", "Firemní klienti", "RESEARCH", { status: "IN_REVIEW", has_working_content: true, last_stage: "results" })],
        previous_count: 0,
        recent_outputs: [],
        knowledge: { context_revision: 9, items_by_kind: { FACT: 3 }, pending_proposals: 5, last_approved_at: null, stale_items: 2, unfiled_items: 4 },
        pending: [PROPOSALS[0], PROPOSALS[1]],
        recent_changes: [
          { item_id: "KNW-1", title: "Hlavní konkurenti", revision: 3, origin: "PERSON", at: null },
          { item_id: "KNW-2", title: "Mladší kupci řeší cenu", revision: 1, origin: "STUDY", at: null },
        ],
      }),
    });
    render(inClient("CLI-a", <ClientOverview />));
    const yours = (await screen.findByRole("heading", { name: "Čeká na vás" })).closest("section")!;
    expect(within(yours).getByText("Návrhy znalostí ke schválení: 5")).toBeTruthy();
    expect(within(yours).getByText(/Značka působí spolehlivě · Můj pojem/)).toBeTruthy();
    expect(within(yours).getByRole("link", { name: "Projít" }).getAttribute("href")).toBe("/app/clients/CLI-a/knowledge?view=review");
    expect(within(yours).getByText("Firemní klienti").closest("a")!.getAttribute("href")).toBe("/app/clients/CLI-a/research/STU-5/results");

    const changes = screen.getByRole("heading", { name: "Poslední změny znalostí" }).closest("section")!;
    expect(within(changes).getByText("napsal člověk · revize 3")).toBeTruthy();
    expect(within(changes).getByText("ze studie · revize 1")).toBeTruthy();

    const context = screen.getByRole("heading", { name: "Kontext klienta" }).closest("section")!;
    expect(within(context).getByRole("link", { name: "Neměněno déle než rok: 2" }).getAttribute("href")).toBe("/app/clients/CLI-a/knowledge?view=old");
    expect(within(context).getByRole("link", { name: "Bez složky: 4" }).getAttribute("href")).toBe("/app/clients/CLI-a/knowledge?view=unfiled");
  });

  it("says when nothing waits on a person", async () => {
    path = "/app/clients/CLI-a";
    api({
      "GET /api/v1/clients/CLI-a/overview": () => ({
        client: A, active: [], previous_count: 0, recent_outputs: [],
        knowledge: { context_revision: 0, items_by_kind: {}, pending_proposals: 0, last_approved_at: null, stale_items: 0, unfiled_items: 0 },
        pending: [], recent_changes: [],
      }),
    });
    render(inClient("CLI-a", <ClientOverview />));
    expect(await screen.findByText("Nic nečeká na vaše rozhodnutí.")).toBeTruthy();
    expect(screen.getByText("Zatím se ve znalostech nic nezměnilo.")).toBeTruthy();
    expect(screen.getByText("Vše je v některé složce a nic není starší než rok.")).toBeTruthy();
  });

  it("opens Znalosti on the view a link names, and forgets it once read", async () => {
    path = "/app/clients/CLI-a/knowledge";
    window.history.pushState({}, "", "/app/clients/CLI-a/knowledge?view=review");
    api();
    render(inClient("CLI-a", <KnowledgeArea />));
    expect(await screen.findByText("Značka působí spolehlivě")).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Ke schválení/ }).getAttribute("aria-pressed")).toBe("true");
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/app/clients/CLI-a/knowledge"));
    window.history.pushState({}, "", "/");
  });

  it("lists the client's research only, and starts a new one under the client", async () => {
    path = "/app/clients/CLI-a/research";
    api();
    render(inClient("CLI-a", <StudyList kind="RESEARCH" />));
    expect(await screen.findByText("Vnímání značky")).toBeTruthy();
    expect(screen.queryByText("Cenové scénáře")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Nový výzkum" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "Brand 2027" } });
    fireEvent.submit(dialog.querySelector("form")!);
    await waitFor(() => expect(push).toHaveBeenCalledWith("/app/clients/CLI-a/research/STU-9/brief"));
    expect(called("POST", "/api/v1/clients/CLI-a/studies")[0].body).toEqual({ name: "Brand 2027", kind: "RESEARCH" });
  });

  it("keeps the client's knowledge its own: a study's finding accepted by a person, even the one who offered it", async () => {
    path = "/app/clients/CLI-a/knowledge";
    api();
    render(inClient("CLI-a", <KnowledgeArea />));
    expect(await screen.findByText("Výroční zpráva")).toBeTruthy();
    // Studio v3: the "Odkud znalosti pocházejí" strip is gone; the subtitle says where knowledge comes from.
    expect(screen.queryByRole("region", { name: "Odkud znalosti pocházejí" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Ke schválení" }));
    const theirs = (await screen.findByText("Značka působí spolehlivě")).closest("li")!;
    const mine = screen.getByText("Můj pojem").closest("li")!;
    // ADR 0019: no approval between people, so the proposer may accept their own. The API
    // still refuses where the client turned self-approval off, and the page shows why.
    expect(within(mine).getByRole("button", { name: "Schválit" })).toBeTruthy();
    expect(within(mine).getByText("Váš návrh")).toBeTruthy();
    fireEvent.click(within(theirs).getByRole("button", { name: "Schválit" }));
    await waitFor(() => expect(called("POST", "/api/v1/clients/CLI-a/knowledge/proposals/KNP-1/decision")[0].body).toEqual({ approve: true, note: "" }));
  });

  it("lists a source a person adds at once, with nothing left to approve", async () => {
    path = "/app/clients/CLI-a/knowledge";
    api();
    render(inClient("CLI-a", <KnowledgeArea />));
    fireEvent.click(await screen.findByRole("button", { name: "Napsat znalost" }));
    const form = screen.getByRole("heading", { name: "Napsat znalost klienta" }).closest("section")!;
    fireEvent.change(within(form).getByRole("combobox"), { target: { value: "SOURCE" } });
    fireEvent.change(within(form).getAllByRole("textbox")[0], { target: { value: "Starbucks výroční zpráva" } });
    fireEvent.click(within(form).getByRole("button", { name: "Uložit znalost" }));
    await waitFor(() => expect(called("POST", "/api/v1/clients/CLI-a/knowledge/proposals")[0].body).toMatchObject({ kind: "SOURCE", title: "Starbucks výroční zpráva" }));
    // It lands among the sources, not in the queue of things waiting for someone.
    await waitFor(() => expect(screen.getByRole("button", { name: "Zdroje a dokumenty" }).getAttribute("aria-pressed")).toBe("true"));
    expect(screen.queryByRole("button", { name: "Schválit" })).toBeNull();
  });
});

describe("a research, re-homed under its client", () => {
  it("loads the study's working content from AIA by the study alone (ADR 0018)", async () => {
    path = "/app/clients/CLI-a/research/STU-1/questionnaire";
    api();
    render(inClient("CLI-a", <ResearchStudy studyId="STU-1"><ResearchStage slug="questionnaire" /></ResearchStudy>));
    expect(await screen.findByRole("heading", { level: 1, name: "Dotazník" })).toBeTruthy();
    // The heading comes from the study's frame; the content is a request of its own, issued
    // after the token and /config are read, so it is awaited rather than counted at once.
    await waitFor(() => expect(called("GET", "/api/v1/studies/STU-1/workspace/content")).toHaveLength(1));
    // Nothing reaches the 18.6.6 unit's project store any more.
    expect(calls.filter((c) => c.url.startsWith("/api/projects"))).toEqual([]);
    const crumbs = within(screen.getByRole("navigation", { name: "Kde jste" })).getAllByRole("listitem");
    expect(crumbs.map((c) => c.textContent?.replace("/", "").trim())).toEqual(["Klienti", "Klient A", "Výzkumy", "Vnímání značky", "Dotazník"]);
    await waitFor(() => expect(called("PUT", "/api/v1/studies/STU-1/workspace/stage")[0].body).toEqual({ stage: "questionnaire" }));
  });

  it("does not open another client's study under this client's URL", async () => {
    path = "/app/clients/CLI-a/research/STU-X/brief";
    api();
    render(inClient("CLI-a", <ResearchStudy studyId="STU-X"><ResearchStage slug="brief" /></ResearchStudy>));
    expect(await screen.findByRole("heading", { name: "Tady nic není" })).toBeTruthy();
    expect(called("GET", "/api/v1/studies/STU-X/workspace/content")).toEqual([]);
  });

  it("finds nothing by a unit project id in the study's place", async () => {
    path = "/app/clients/CLI-a/research/PRJ-bound/brief";
    api({
      "GET /api/v1/studies/PRJ-bound/workspace": () =>
        new Response('{"code":"validation_error","message":"The request body or parameters are invalid."}', { status: 422 }),
    });
    render(inClient("CLI-a", <ResearchStudy studyId="PRJ-bound"><ResearchStage slug="brief" /></ResearchStudy>));
    expect(await screen.findByRole("heading", { name: "Tady nic není" })).toBeTruthy();
    expect(screen.queryByText(/parameters are invalid/)).toBeNull();
    expect(called("GET", "/api/v1/studies/PRJ-bound/workspace/content")).toEqual([]);
  });
});

describe("Nastavení", () => {
  it("says who may open AIA and that grants decide what they see (ADR 0018)", async () => {
    path = "/app/settings";
    api();
    render(<SettingsPage />);
    expect(await screen.findByText(/AIA otevře každý aktivní člen organizace/)).toBeTruthy();
    expect(screen.queryByText(/jen vlastníci a správci/)).toBeNull();
    expect(await screen.findByText("Role v organizaci: vlastník")).toBeTruthy();
  });
});

// What Settings says about AI -- configured, off and why, invalid, unknown, never
// connected -- is tested with the panel that says it: settings/ControlPanel.test.tsx.
