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
import { StudyList } from "./clients/StudyList";
import { SettingsPage } from "./GlobalPages";
import { ResearchStage, ResearchStudy } from "./ResearchStudy";

let path = "/app/clients";
const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => path,
  useRouter: () => ({ push, replace }),
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
        "GET /api/v1/clients/CLI-a/knowledge": () => [{ item_id: "KNW-1", kind: "SOURCE", title: "Výroční zpráva", summary: "", content: {}, revision: 1, modified_at: null }],
        "GET /api/v1/clients/CLI-a/knowledge/proposals": () => PROPOSALS,
        "POST /api/v1/clients/CLI-a/knowledge/proposals/KNP-1/decision": () => ({ ...PROPOSALS[0], status: "APPROVED" }),
        "POST /api/v1/clients/CLI-a/knowledge/proposals": (b) => ({ ...PROPOSALS[1], title: (b as { title: string }).title }),
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

  it("offers no new client to someone who may not administer", async () => {
    api({ "GET /api/v1/workspace/me": () => ({ user_id: "USR-3", email: null, organization_role: "MEMBER", may_administer: false }) });
    render(<ClientDirectory />);
    await screen.findByText("Klient A");
    expect(screen.queryByRole("button", { name: "Nový klient" })).toBeNull();
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
    ]);
    const research = (await screen.findByText("Vnímání značky")).closest("a")!;
    expect(research.getAttribute("href")).toBe("/app/clients/CLI-a/research/STU-1/questionnaire");
    expect(within(research).getByText("Výzkum · Dotazník")).toBeTruthy();
    expect(screen.getByText("Cenové scénáře").closest("a")!.getAttribute("href")).toBe("/app/clients/CLI-a/simulations/STU-2");
    expect(screen.getByText("Revize znalostí 7", { exact: false })).toBeTruthy();
    expect(screen.getByText("Značka působí spolehlivě")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Nový výzkum" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Nová simulace" })).toBeTruthy();
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

  it("keeps the client's knowledge its own: layers said, approval by someone other than the proposer", async () => {
    path = "/app/clients/CLI-a/knowledge";
    api();
    render(inClient("CLI-a", <KnowledgeArea />));
    expect(await screen.findByText("Společenská inteligence AIA")).toBeTruthy();
    expect(screen.getByText("Znalosti klienta", { selector: "div" })).toBeTruthy();
    expect(await screen.findByText("Výroční zpráva")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Čekající aktualizace" }));
    const theirs = (await screen.findByText("Značka působí spolehlivě")).closest("li")!;
    const mine = screen.getByText("Můj pojem").closest("li")!;
    expect(within(mine).queryByRole("button", { name: "Schválit" })).toBeNull();
    expect(within(mine).getByText(/schválit ho musí někdo jiný/)).toBeTruthy();
    fireEvent.click(within(theirs).getByRole("button", { name: "Schválit" }));
    await waitFor(() => expect(called("POST", "/api/v1/clients/CLI-a/knowledge/proposals/KNP-1/decision")[0].body).toEqual({ approve: true, note: "" }));
  });
});

describe("a research, re-homed under its client", () => {
  it("loads the study's working content from AIA by the study alone (ADR 0018)", async () => {
    path = "/app/clients/CLI-a/research/STU-1/questionnaire";
    api();
    render(inClient("CLI-a", <ResearchStudy studyId="STU-1"><ResearchStage slug="questionnaire" /></ResearchStudy>));
    expect(await screen.findByRole("heading", { level: 1, name: "3. Dotazník" }, { timeout: 4000 })).toBeTruthy();
    expect(called("GET", "/api/v1/studies/STU-1/workspace/content")).toHaveLength(1);
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
  it("says the owner/admin restriction is temporary", async () => {
    path = "/app/settings";
    api();
    render(<SettingsPage />);
    expect(await screen.findByText(/Novou aplikaci teď mohou otevřít jen vlastníci a správci/)).toBeTruthy();
    expect(await screen.findByText("Role v organizaci: vlastník")).toBeTruthy();
  });
});


describe("Bedrock settings", () => {
  it("shows fictional fieldwork configuration and no legacy credential controls", async () => {
    path = "/app/settings";
    api({ "GET /config": () => ({ apiBase: "", aiRuntime: {
      enabled: true, provider: "aws_bedrock", region: "eu-central-1",
      model: "eu.anthropic.claude-sonnet-4-5-20250929-v1:0", approvedFor: "CLASS_C_INTERNAL",
    } }) });
    render(<SettingsPage />);
    expect(await screen.findByText(/AI odpovědi respondentů jsou povolené pouze/)).toBeTruthy();
    expect(screen.getByText("Výchozí oblast: eu-central-1")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Claude Code" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Obecné nastavení" })).toBeNull();
    expect(screen.queryByLabelText("ANTHROPIC_API_KEY")).toBeNull();
    expect(screen.getByText(/AI návrhové kroky jsou v tomto prostředí vypnuté/)).toBeTruthy();
    expect(called("POST", "/api/settings/ai_check")).toEqual([]);
  });
  it("says a switch the worker refuses is invalid, never off or on", async () => {
    path = "/app/settings";
    api({ "GET /config": () => ({ apiBase: "", aiRuntime: {
      enabled: null, provider: "aws_bedrock", region: null, model: null, approvedFor: null,
    } }) });
    render(<SettingsPage />);
    expect(await screen.findByText(/má neplatnou hodnotu; worker se s ní nespustí/)).toBeTruthy();
    expect(screen.queryByText("AI odpovědi respondentů jsou vypnuté.")).toBeNull();
    expect(screen.queryByText(/AI odpovědi respondentů jsou povolené pouze/)).toBeNull();
  });
  it("reports an absent configuration as unknown rather than connected", async () => {
    path = "/app/settings";
    api();
    render(<SettingsPage />);
    expect(await screen.findByText("Stav konfigurace AI se nepodařilo načíst.")).toBeTruthy();
    expect(screen.queryByText(/AI odpovědi respondentů jsou povolené pouze/)).toBeNull();
  });
});
