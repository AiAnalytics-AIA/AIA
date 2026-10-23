// @vitest-environment jsdom
// The settings control panel against a fake AIA API: the signed-in token is what
// reaches the API, every setting says how it is controlled, "not configured" and
// "costs hidden" never read as zero, a change goes through the API and the
// panel re-reads, and a refusal is shown as the API gave it.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { loadConfig, resetConfigCache } from "@/lib/auth";
import { SettingsPage } from "../GlobalPages";
import { ControlPanel } from "./ControlPanel";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace }), usePathname: () => "/app/settings" }));

const item = (key: string, value: unknown, control: string, source: string, unit: string | null = null) => ({ key, value, control, source, unit });

// The shape of GET /api/v1/settings's ai_runtime (schemas/settings.py NativeRuntime).
const AI_RUNTIME = {
  providers: [{ id: "aws_bedrock", label: "Amazon Bedrock", paid: true, use: "NATIVE" }],
  credential: "INSTANCE_ROLE",
  switch: "AIA_AI_RUNTIME_ENABLED",
  activities: [
    {
      key: "respondent_fieldwork", step_kind: "research_fieldwork", capabilities: ["SIMULATION"],
      versions: [{ name: "generator", value: "aia-ai-respondent-1" }, { name: "prompt", value: "aia.respondent.block@1" }],
      switches: ["AIA_AI_RUNTIME_ENABLED"], actions: [],
    },
    {
      key: "design_agents", step_kind: "research_agent", capabilities: ["RESEARCH_REASONING", "CRITIC"],
      versions: [{ name: "harness", value: "aia-research-harness-1" }],
      switches: ["AIA_AI_RUNTIME_ENABLED", "AIA_AI_RESEARCH_AGENTS_ENABLED"], actions: ["analyze_brief", "critique_design"],
    },
  ],
  unused_capabilities: ["FAST_EXTRACTION", "REPORT_WRITING", "EMBEDDING"],
};

const DOC = (mayAdminister = true) => ({
  organization_id: "ORG-1",
  your_role: mayAdminister ? "OWNER" : "MEMBER",
  may_administer: mayAdminister,
  groups: [
    ...(mayAdminister
      ? [{ key: "deployment", items: [item("env", "develop", "DEPLOYMENT", "AIA_ENV"), item("database_backend", null, "DEPLOYMENT", "DATABASE_URL")] }]
      : []),
    { key: "deep_research", items: [
      item("deep_research_settings", null, "API", "PUT /api/v1/deep-research/settings/{key}/approval"),
      item("deep_research_public_sources_only", true, "INVARIANT", "docs/architecture/adr/0017-deep-research-external-retrieval.md"),
    ] },
    { key: "access", items: [
      item("members", null, "API", "POST /api/v1/members"),
      item("membership_is_access", true, "INVARIANT", "docs/architecture/adr/0019-two-roles-and-human-ai-gates.md"),
    ] },
    { key: "studies", items: [
      item("study_budget", null, "API", "PUT /api/v1/studies/{study_id}/budget", "USD"),
      item("no_spend_past_budget", true, "INVARIANT", "ARCHITECTURE.md §10"),
    ] },
    { key: "approvals", items: [item("self_approval", null, "API", "PUT /api/v1/self-approval")] },
    { key: "ai", items: [item("configuration_is_not_verification", true, "INVARIANT", "ARCHITECTURE.md §2")] },
    { key: "ai_history", items: [
      item("project_default_provider", "claude_code_subscription", "CODE", "aia_core.domain.providers:DEFAULT_PROVIDER"),
      item("default_project_max_api_cost", 10, "CODE", "aia_core.domain.providers:DEFAULT_MAX_API_COST_USD", "USD"),
      item("project_max_api_cost", null, "API", "PATCH /api/v1/studies/{study_id}/projects/{project_id}", "USD"),
    ] },
    { key: "brand_new", items: [item("something_new", 3, "CODE", "aia_core.domain.x:NEW")] },
  ],
  ai_runtime: AI_RUNTIME,
  vocabularies: {
    organization_roles: ["OWNER", "ADMIN", "MEMBER"],
    scope_roles: [{ role: "RESEARCHER", permissions: ["VIEW_STUDY", "MANAGE_STUDY_BUDGET"] }],
    permissions: ["VIEW_STUDY", "MANAGE_STUDY_BUDGET"],
    client_statuses: ["ACTIVE", "DORMANT", "ARCHIVED"],
    study_statuses: ["DRAFT", "ACTIVE"],
    providers: [
      { id: "aws_bedrock", label: "Amazon Bedrock", paid: true, use: "NATIVE" },
      { id: "claude_code_subscription", label: "Claude Code", paid: false, use: "HISTORICAL" },
    ],
    provider_policies: ["CLAUDE_CODE_ONLY"],
    model_capabilities: ["CRITIC"],
    data_classes: ["CLASS_C_INTERNAL"],
    research_stages: [{ id: "BRIEF", label: "Zadání" }],
    simulation_stages: [{ id: "BRIEF", label: "Kontext" }],
  },
});

const STUDY = (id: string, name: string) => ({
  study_id: id, client_id: "CLI-a", slug: id.toLowerCase(), name, kind: "RESEARCH", status: "ACTIVE", accepts_work: true,
  your_role: null, budget_usd: null, spent_usd: null, remaining_usd: null,
});

// /config as the web server answers it (app/config/route.ts): develop's state by
// default, fieldwork switched on and design jobs off.
const CONFIG = (ai: Record<string, unknown> = {}) => ({
  cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", apiBase: "", build: { sha: null },
  aiRuntime: {
    enabled: true, researchAgentsEnabled: false, provider: "aws_bedrock", region: "eu-central-1",
    model: "eu.anthropic.claude-sonnet-4-5-20250929-v1:0", approvedFor: "CLASS_C_INTERNAL", approvedClasses: ["CLASS_C_INTERNAL"],
    switches: { AIA_AI_RUNTIME_ENABLED: true, AIA_AI_RESEARCH_AGENTS_ENABLED: false },
    ...ai,
  },
});

type Call = { method: string; url: string; body: unknown; headers: Record<string, string> };
let calls: Call[] = [];
function api(overrides: Record<string, (body: unknown) => unknown> = {}, mayAdminister = true) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ method, url: u, body, headers: (init?.headers ?? {}) as Record<string, string> });
      const routes: Record<string, (b: unknown) => unknown> = {
        "GET /config": () => CONFIG(),
        "GET /api/v1/workspace/me": () => ({ user_id: "USR-1", email: "owner@example.test", organization_role: mayAdminister ? "OWNER" : "MEMBER", may_administer: mayAdminister }),
        "GET /api/v1/settings": () => DOC(mayAdminister),
        "GET /api/v1/members": () => [{ user_id: "USR-1", email: "owner@example.test", display_name: "", is_active: true, organization_role: "OWNER" }],
        "GET /api/v1/clients": () => [{ client_id: "CLI-a", slug: "a", name: "Klient A", status: "ACTIVE", reference: "", study_count: 2, created_at: null }],
        "GET /api/v1/studies": () => [STUDY("STU-1", "Vnímání značky"), STUDY("STU-2", "Cizí studie")],
        "GET /api/v1/studies/STU-1": () => ({ ...STUDY("STU-1", "Vnímání značky"), budget_usd: 500, spent_usd: 0, remaining_usd: 500 }),
        "GET /api/v1/studies/STU-2": () => new Response('{"code":"not_found","message":"No such resource."}', { status: 404 }),
        "GET /api/v1/self-approval": () => ({ organization: null, clients: [], studies: [] }),
        "GET /api/v1/access-audit": () => [{ event_id: 1, action: "CLIENT_GRANT", client_id: "CLI-a", study_id: null, subject_user_id: "USR-1", actor_id: "USR-1", role: "LEAD", reason: "self_grant", payload: {}, created_at: null }],
        "PUT /api/v1/self-approval": () => ({ allowed: true, source: "organization" }),
        "GET /api/v1/settings/researcher-spend": () => ({ period: "this_month", start: "", end: "", everyone: mayAdminister, currency: "USD", people: [] }),
        ...overrides,
      };
      const answer = routes[`${method} ${u.split("?")[0]}`]?.(body) ?? {};
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
}
const called = (method: string, path: string) => calls.filter((c) => c.method === method && c.url.split("?")[0] === path);

// Every API request reads /config through loadConfig(), which keeps the page's read. Each
// test starts and ends with that cache empty, so its requests read its own stub and never
// a read an earlier test left (CLAUDE.md §7; OI-76 is the same trap in the research tests).
beforeEach(() => {
  resetConfigCache();
  // Each example opens Settings afresh; another example's selected hash is not its input.
  // Most control tests start on the AI tab; the actual Settings landing opens Methodology.
  window.history.replaceState(null, "", "/app/settings#ai");
  replace.mockReset();
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "owner@example.test", subject: "s" }));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  resetConfigCache();
  sessionStorage.clear();
});

describe("the settings control panel", () => {
  it("sends the signed-in token to the API, and no development identity header", async () => {
    api();
    render(<ControlPanel />);
    await screen.findByText("Prostředí");
    const apiCalls = calls.filter((c) => c.url.startsWith("/api/v1/"));
    expect(apiCalls.length).toBeGreaterThan(5);
    for (const c of apiCalls) {
      expect(c.headers.Authorization).toBe("Bearer tok");
      expect(c.headers["X-AIA-Subject"]).toBeUndefined();
    }
  });

  it("says how every setting is controlled, and never shows 'not configured' as a value", async () => {
    api();
    render(<ControlPanel />);
    const env = (await screen.findByText("Prostředí")).closest("[data-setting]") as HTMLElement;
    expect(within(env).getByText("develop")).toBeTruthy();
    expect(env.querySelector("[data-control]")?.getAttribute("data-control")).toBe("DEPLOYMENT");
    const db = screen.getByText("Databáze").closest("[data-setting]") as HTMLElement;
    expect(db.querySelector('[data-value="null"]')?.textContent).toContain("nenastaveno");
    expect(within(db).queryByText("0")).toBeNull();
    const invariant = screen.getAllByText("Žádná útrata nad rozpočet")[0].closest("[data-setting]") as HTMLElement;
    expect(invariant.querySelector("[data-control]")?.getAttribute("data-control")).toBe("INVARIANT");
  });

  it("offers no way to grant access, and says that membership is the access", async () => {
    api();
    render(<ControlPanel />);
    expect((await screen.findAllByText("Členství v organizaci je přístup: každý člen vidí všechny klienty a studie")).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Udělit přístup/)).toBeNull();
    expect(screen.queryByRole("button", { name: /Udělit/ })).toBeNull();
    expect(screen.queryByText(/dokud nedostane grant/)).toBeNull();
    expect(screen.queryByText(/neuděluje přístup k datům klienta/)).toBeNull();
    // A person is added with a role chosen in the row, never with a scope-role picker; OWNER is
    // never offered to someone new.
    fireEvent.click(await screen.findByRole("button", { name: "+ Přidat člena", hidden: true }));
    const role = screen.getByRole("radiogroup", { name: "Role nového člena", hidden: true });
    expect(within(role).getAllByRole("radio", { hidden: true }).map((r) => r.textContent)).toEqual(["správce", "výzkumník"]);
    expect(called("POST", "/api/v1/clients/CLI-a/grants")).toHaveLength(0);
  });

  it("offers an administrator no OWNER to grant and no OWNER row's role to change", async () => {
    // Only an OWNER grants or removes OWNER (the API refuses it, owner_only): an ADMIN is not
    // offered what the server refuses.
    api({
      "GET /api/v1/settings": () => ({ ...DOC(true), your_role: "ADMIN" }),
      "GET /api/v1/members": () => [
        { user_id: "USR-1", email: "owner@example.test", display_name: "", is_active: true, organization_role: "OWNER" },
        { user_id: "USR-2", email: "admin@example.test", display_name: "", is_active: true, organization_role: "ADMIN" },
      ],
    });
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Přístup a schvalování" }));
    const ownerRow = await waitFor(() => document.querySelector('[data-member="USR-1"]') as HTMLElement);
    expect(ownerRow.querySelector('[role="radiogroup"]')).toBeNull();
    expect(screen.getByText("Roli vlastníka mění jen vlastník.")).toBeTruthy();
    const admin = screen.getByRole("radiogroup", { name: "Role: admin@example.test" });
    expect(within(admin).getAllByRole("radio").map((r) => r.textContent)).toEqual(["správce", "výzkumník"]);
  });

  it("offers the organization's only active OWNER no demotion", async () => {
    api();
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Přístup a schvalování" }));
    await waitFor(() => expect(document.querySelector('[data-member="USR-1"]')).toBeTruthy());
    expect(screen.queryByRole("radiogroup", { name: "Role: owner@example.test" })).toBeNull();
    expect(screen.getByText("Jediný aktivní vlastník organizace o roli přijít nemůže.")).toBeTruthy();
  });

  it("says an OWNER refusal in Czech at the member's row, the API's English sentence left out", async () => {
    // The list was read while a second OWNER was still active; the server decides.
    api({
      "GET /api/v1/members": () => [
        { user_id: "USR-1", email: "owner@example.test", display_name: "", is_active: true, organization_role: "OWNER" },
        { user_id: "USR-3", email: "second@example.test", display_name: "", is_active: true, organization_role: "OWNER" },
      ],
      "POST /api/v1/members": () =>
        new Response('{"code":"insufficient_role","message":"The organization\'s last OWNER cannot be demoted or deactivated.","details":{"reason":"last_owner"}}', { status: 403 }),
    });
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Přístup a schvalování" }));
    const roles = await screen.findByRole("radiogroup", { name: "Role: owner@example.test" });
    fireEvent.click(within(roles).getByRole("radio", { name: "výzkumník" }));
    const member = document.querySelector('[data-member="USR-1"]') as HTMLElement;
    expect(await screen.findByText("Poslední aktivní vlastník organizace nemůže přijít o roli ani být deaktivován.")).toBeTruthy();
    expect(member.parentElement?.textContent).not.toMatch(/last OWNER/);
    expect(screen.queryByText(/zapsáno do auditu/)).toBeNull();
  });

  it("still renders a group the page has no panel for", async () => {
    api();
    render(<ControlPanel />);
    const row = (await screen.findByText("something new")).closest("[data-setting]") as HTMLElement;
    expect(within(row).getByText("3")).toBeTruthy();
  });

  it("shows hidden costs as hidden, never as a zero budget", async () => {
    api();
    render(<ControlPanel />);
    const hidden = (await screen.findByText("Cizí studie")).closest("[data-study]") as HTMLElement;
    expect(within(hidden).getByText(/náklady nevidíte/)).toBeTruthy();
    expect(within(hidden).queryByRole("spinbutton", { hidden: true })).toBeNull();
    const visible = screen.getByText("Vnímání značky").closest("[data-study]") as HTMLElement;
    const budget = within(visible).getByRole("spinbutton", { name: "Rozpočet studie Vnímání značky", hidden: true }) as HTMLInputElement;
    expect(budget.value).toMatch(/^500/);
  });

  it("reads each study's spend against its budget, highlights one at 90 %, and points the wallet to the client's rules", async () => {
    api({ "GET /api/v1/studies/STU-1": () => ({ ...STUDY("STU-1", "Vnímání značky"), budget_usd: 100, spent_usd: 92, remaining_usd: 8 }) });
    render(<ControlPanel />);
    const row = (await screen.findByText("Vnímání značky")).closest("[data-study]") as HTMLElement;
    await waitFor(() => expect(row.getAttribute("data-near")).toBe("true"));
    expect(within(row).getByText(/92 % rozpočtu · zbývá 8,00 USD · téměř vyčerpáno/)).toBeTruthy();
    const link = within(row).getByRole("link", { name: "Profil → Pravidla", hidden: true });
    expect(link.getAttribute("href")).toContain("/app/clients/CLI-a/profile");
    expect(screen.getByText("Cizí studie").closest("[data-study]")?.getAttribute("data-near")).toBeNull();
  });

  it("changes the organization's self-approval where it is shown, then re-reads", async () => {
    api();
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Přístup a schvalování" }));
    const org = await screen.findByRole("radiogroup", { name: "Samoschválení organizace" });
    // Nothing stored: Výchozí is chosen, and the default is said in words.
    expect(within(org).getByRole("radio", { name: "Výchozí" }).getAttribute("aria-checked")).toBe("true");
    expect(screen.getByText(/Nenastaveno: platí výchozí pravidlo/)).toBeTruthy();
    fireEvent.click(within(org).getByRole("radio", { name: "Povolit" }));
    await waitFor(() => expect(called("PUT", "/api/v1/self-approval")).toHaveLength(1));
    expect(called("PUT", "/api/v1/self-approval")[0].body).toEqual({ allowed: true });
    await waitFor(() => expect(called("GET", "/api/v1/settings")).toHaveLength(2));
  });

  it("puts self-approval above the clients, and sets a client's status and self-approval in its row", async () => {
    api({ "GET /api/v1/self-approval": () => ({ organization: true, clients: [{ client_id: "CLI-a", allowed: false }], studies: [{ study_id: "STU-1", client_id: "CLI-a", allowed: true }] }) });
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Přístup a schvalování" }));
    const panel = document.getElementById("panel-access") as HTMLElement;
    await within(panel).findByRole("radiogroup", { name: "Samoschválení organizace" });
    const order = [...panel.querySelectorAll("section[id^='set-']")].map((e) => e.id).filter((id) => ["set-members", "set-self-approval", "set-clients"].includes(id));
    expect(order).toEqual(["set-members", "set-self-approval", "set-clients"]);
    const rule = within(panel).getByRole("radiogroup", { name: "Samoschválení studie Vnímání značky" });
    expect(within(rule).getByRole("radio", { name: "Povolit" }).getAttribute("aria-checked")).toBe("true");
    const self = within(panel).getByRole("radiogroup", { name: "Samoschválení klienta Klient A" });
    expect(within(self).getByRole("radio", { name: "Zakázat" }).getAttribute("aria-checked")).toBe("true");
    fireEvent.click(within(self).getByRole("radio", { name: "Dědit" }));
    await waitFor(() => expect(called("PUT", "/api/v1/self-approval")).toHaveLength(1));
    expect(called("PUT", "/api/v1/self-approval")[0].body).toEqual({ allowed: null, client_id: "CLI-a" });
    const status = within(panel).getByRole("radiogroup", { name: "Stav klienta Klient A" });
    fireEvent.click(within(status).getByRole("radio", { name: "Archivovaný" }));
    await waitFor(() => expect(calls.filter((c) => c.method !== "GET" && c.url.includes("/clients/CLI-a"))).toHaveLength(1));
    // The client's data posture and wallet ceiling are read-only here and not in AIA yet.
    const row = panel.querySelector('[data-client="CLI-a"]') as HTMLElement;
    expect(row.parentElement?.querySelector("[data-not-yet]")).toBeTruthy();
    expect(within(panel).getByRole("link", { name: "Změnit v Profil → Pravidla" }).getAttribute("href")).toBe("/app/clients/CLI-a/profile");
  });

  it("sets, clears and adds a study's own self-approval rule, and returns the organization to the default", async () => {
    api({ "GET /api/v1/self-approval": () => ({ organization: false, clients: [], studies: [{ study_id: "STU-1", client_id: "CLI-a", allowed: false }] }) });
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Přístup a schvalování" }));
    const panel = document.getElementById("panel-access") as HTMLElement;
    const org = await within(panel).findByRole("radiogroup", { name: "Samoschválení organizace" });
    fireEvent.click(within(org).getByRole("radio", { name: "Výchozí" }));
    await waitFor(() => expect(called("PUT", "/api/v1/self-approval")).toHaveLength(1));
    expect(called("PUT", "/api/v1/self-approval")[0].body).toEqual({ allowed: null });
    const rule = within(panel).getByRole("radiogroup", { name: "Samoschválení studie Vnímání značky" });
    fireEvent.click(within(rule).getByRole("radio", { name: "Dědit" }));
    await waitFor(() => expect(called("PUT", "/api/v1/self-approval")).toHaveLength(2));
    expect(called("PUT", "/api/v1/self-approval")[1].body).toEqual({ allowed: null, study_id: "STU-1" });
    // A study with no rule of its own is offered for a new one; the study with a rule is not.
    fireEvent.click(within(panel).getByRole("button", { name: "Přidat pravidlo pro studii" }));
    const add = panel.querySelector("[data-add-study-rule]") as HTMLElement;
    const select = within(add).getByRole("combobox", { name: "Vyberte studii…" }) as HTMLSelectElement;
    expect([...select.options].map((o) => o.value)).toEqual(["", "STU-2"]);
    fireEvent.change(select, { target: { value: "STU-2" } });
    fireEvent.click(within(within(add).getByRole("radiogroup", { name: "Pravidlo vybrané studie" })).getByRole("radio", { name: "Zakázat" }));
    await waitFor(() => expect(called("PUT", "/api/v1/self-approval")).toHaveLength(3));
    expect(called("PUT", "/api/v1/self-approval")[2].body).toEqual({ allowed: false, study_id: "STU-2" });
  });

  it("says plainly that the Metodik mark and deactivating a member are not in AIA yet, and explains each role", async () => {
    api();
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Přístup a schvalování" }));
    const panel = document.getElementById("panel-access") as HTMLElement;
    await waitFor(() => expect(panel.querySelector('[data-member="USR-1"]')).toBeTruthy());
    expect(within(panel).queryByRole("switch", { name: /Metodik/ })).toBeNull();
    expect(within(panel).getByText("Deaktivace člena a štítek Metodik v AIA zatím nejsou.")).toBeTruthy();
    expect([...panel.querySelectorAll("[data-role-box]")].map((b) => b.getAttribute("data-role-box"))).toEqual(["OWNER", "ADMIN", "MEMBER", "METODIK"]);
  });

  it("shows the API's refusal as given, at the study's budget", async () => {
    api({
      "PUT /api/v1/studies/STU-1/budget": () =>
        new Response('{"code":"insufficient_role","message":"Your role on this study does not permit that action."}', { status: 403 }),
    });
    render(<ControlPanel />);
    const row = (await screen.findByText("Vnímání značky")).closest("[data-study]") as HTMLElement;
    const budget = await within(row).findByRole("spinbutton", { name: "Rozpočet studie Vnímání značky", hidden: true });
    fireEvent.change(budget, { target: { value: "900" } });
    fireEvent.keyDown(budget, { key: "Enter" });
    expect(await within(row).findByText(/HTTP 403 · insufficient_role: Your role on this study/)).toBeTruthy();
    expect(called("PUT", "/api/v1/studies/STU-1/budget")[0].body).toEqual({ budget_usd: 900 });
  });

  it("does not count a study whose costs it could not read as not near its budget", async () => {
    // STU-2's GET fails (404 in the fake): the tile cannot say 0.
    api({ "GET /api/v1/settings/researcher-spend": () => ({ period: "this_month", start: "", end: "", everyone: true, currency: "USD", people: [] }) });
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Studie a rozpočty" }));
    const tile = (await within(panelOf("Studie a rozpočty")).findByText("Téměř vyčerpané rozpočty")).parentElement as HTMLElement;
    await waitFor(() => expect(tile.textContent).toContain("neznámo"));
    expect(tile.textContent).toContain("u 1 nevíme");
    expect(tile.textContent).not.toMatch(/rozpočty0/);
  });

  it("keeps a saved budget in its field while the re-read has not caught up", async () => {
    // The re-read answers the old budget: the field must not fall back to it after the PUT's yes.
    api({ "PUT /api/v1/studies/STU-1/budget": () => ({ ...STUDY("STU-1", "Vnímání značky"), budget_usd: 900, spent_usd: 0, remaining_usd: 900 }) });
    render(<ControlPanel />);
    const row = (await screen.findByText("Vnímání značky")).closest("[data-study]") as HTMLElement;
    const budget = await within(row).findByRole("spinbutton", { name: "Rozpočet studie Vnímání značky", hidden: true }) as HTMLInputElement;
    fireEvent.change(budget, { target: { value: "900" } });
    fireEvent.keyDown(budget, { key: "Enter" });
    await waitFor(() => expect(called("PUT", "/api/v1/studies/STU-1/budget")).toHaveLength(1));
    await waitFor(() => expect(called("GET", "/api/v1/studies/STU-1").length).toBeGreaterThan(1));
    expect(budget.value).toMatch(/^900/);
  });

  it("sets a study's confirmation threshold by its stepper, and Nikdy clears it", async () => {
    api({ "GET /api/v1/studies/STU-1": () => ({ ...STUDY("STU-1", "Vnímání značky"), budget_usd: 500, spent_usd: 0, remaining_usd: 500, spend_confirm_usd: 50 }) });
    render(<ControlPanel />);
    const row = (await screen.findByText("Vnímání značky")).closest("[data-study]") as HTMLElement;
    const threshold = await within(row).findByRole("spinbutton", { name: "Práh potvrzení studie Vnímání značky", hidden: true });
    fireEvent.change(threshold, { target: { value: "5" } });
    fireEvent.keyDown(threshold, { key: "Enter" });
    expect(called("PUT", "/api/v1/studies/STU-1/spend-confirm")).toEqual([]);
    fireEvent.change(threshold, { target: { value: "60" } });
    fireEvent.keyDown(threshold, { key: "Enter" });
    await waitFor(() => expect(called("PUT", "/api/v1/studies/STU-1/spend-confirm")).toHaveLength(1));
    fireEvent.click(within(row).getByRole("button", { name: "Nikdy", hidden: true }));
    await waitFor(() => expect(called("PUT", "/api/v1/studies/STU-1/spend-confirm")).toHaveLength(2));
    const bodies = called("PUT", "/api/v1/studies/STU-1/spend-confirm").map((c) => c.body);
    expect(bodies[0]).toMatchObject({ limit_usd: 60 });
    expect(Object.values(bodies[1] as object)).toContain(null);
  });

  it("does not ask a member for the self-approval levels or the audit", async () => {
    api({}, false);
    render(<ControlPanel />);
    expect(await screen.findByText(/Samoschválení nastavuje a vidí jen vlastník nebo správce/)).toBeTruthy();
    expect(screen.queryByText("Prostředí")).toBeNull();
    expect(called("GET", "/api/v1/self-approval")).toEqual([]);
    expect(called("GET", "/api/v1/access-audit")).toEqual([]);
  });

  it("says so when the API does not return a settings document", async () => {
    api({ "GET /api/v1/settings": () => ({}) });
    render(<ControlPanel />);
    expect(await screen.findByText("API nevrátilo dokument nastavení.")).toBeTruthy();
  });

  it("sends a signed-out person to sign in", async () => {
    sessionStorage.clear();
    api();
    render(<ControlPanel />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith(expect.stringMatching(/^\/login\?next=/)));
  });
});

// ---------------------------------------------------------------- what powers AIA

// Technical details on for the whole page, as the switch keeps them for the session.
const technicalOn = () => sessionStorage.setItem("aia.settings.technical", "1");
const card = (key: string) => document.querySelector(`[data-activity="${key}"]`) as HTMLElement;
const section = (id: string) => document.getElementById(`set-${id}`) as HTMLElement;
// Everything the browser asked for besides AIA's API and its own /config: a unit
// route, a provider probe or a test call would show up here.
const elsewhere = () => calls.filter((c) => !c.url.startsWith("/api/v1/") && c.url !== "/config");
// Claims a configuration display must never make. "Neověřeno" (not verified) is
// what it must say instead, so only a positive "ověřeno" counts.
const OVERCLAIM = /připojen|funkční spojení|spojení funguje|(?<!ne)ověřen[oaáý]|healthy|connected|\bverified\b/i;
const LOGIN = /přihlaste se|zadejte (api )?klíč|api klíč se zadává|subscription login|ANTHROPIC_API_KEY/i;

describe("the reference", () => {
  it("shows a value found by search in a group with its own panel, its source alone behind technical details", async () => {
    const doc = DOC();
    doc.groups = [...doc.groups, { key: "workflow", items: [item("lease_seconds", 60, "CODE", "aia_core.domain.workflow:LEASE_SECONDS", "s")] }];
    api({ "GET /api/v1/settings": () => doc });
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Reference" }));
    const panel = panelOf("Reference");
    fireEvent.change(await within(panel).findByRole("searchbox", { name: "Hledat technickou hodnotu" }), { target: { value: "lease" } });
    const row = await waitFor(() => { const r = panel.querySelector('[data-setting="lease_seconds"]') as HTMLElement | null; if (!r) throw new Error("no row"); return r; });
    // The row is shown with technical details off; only its source waits for them.
    expect(row.closest("[hidden]")).toBeNull();
    expect(within(row).queryByText("aia_core.domain.workflow:LEASE_SECONDS")).toBeNull();
  });
});

describe("what powers AIA", () => {
  it("names analysis activity and its disabled state in human-readable language", async () => {
    const doc = DOC();
    doc.ai_runtime = { ...AI_RUNTIME, activities: [...AI_RUNTIME.activities, {
      key: "research_analysis", step_kind: "research_analysis", capabilities: ["REPORT_WRITING"],
      versions: [], switches: ["AIA_AI_RUNTIME_ENABLED", "AIA_AI_ANALYSIS_ENABLED"], actions: [],
    }] };
    api({ "GET /api/v1/settings": () => doc, "GET /config": () => CONFIG({ switches: { AIA_AI_RUNTIME_ENABLED: false, AIA_AI_ANALYSIS_ENABLED: false } }) });
    render(<ControlPanel />);
    await waitFor(() => expect(card("research_analysis")).toBeTruthy());
    await waitFor(() => expect(tab("AI běh").getAttribute("aria-selected")).toBe("true"));
    const analysis = card("research_analysis");
    expect(within(analysis).getByRole("heading", { name: "Analýza výsledků výzkumu" })).toBeTruthy();
    expect(within(analysis).getByText(/Dokončená data a mapy zůstanou k dispozici/)).toBeTruthy();
    expect(analysis.textContent).not.toContain("aia.settings.panel.runtime.activity");
  });

  it("fieldwork on and design off: Bedrock, one switched on in configuration, one off by its own switch", async () => {
    technicalOn();
    api();
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork")).toBeTruthy());
    await waitFor(() => expect(tab("AI běh").getAttribute("aria-selected")).toBe("true"));
    const ai = section("ai");
    expect(within(ai).getByText(/AIA volá jazykové modely přes Amazon Bedrock/)).toBeTruthy();
    expect(within(ai).getByText(/nepotřebuje předplatné Claude ani Claude Code/)).toBeTruthy();

    const fieldwork = card("respondent_fieldwork");
    expect(fieldwork.getAttribute("data-state")).toBe("configured");
    expect(within(fieldwork).getByText("Zapnuto v konfiguraci")).toBeTruthy();
    expect(within(fieldwork).getByText(/Neověřeno: tato stránka nevolá model/)).toBeTruthy();
    expect(within(fieldwork).getByText("SIMULATION")).toBeTruthy();
    expect(within(fieldwork).getByText("aia-ai-respondent-1")).toBeTruthy();

    const design = card("design_agents");
    expect(design.getAttribute("data-state")).toBe("off");
    expect(within(design).getByText("Vypnuto")).toBeTruthy();
    expect(within(design).getByText(/^Vypnuto v konfiguraci nasazení\. AI návrh se nespustí/)).toBeTruthy();
    expect(within(design).getByText("Přepínač: AIA_AI_RESEARCH_AGENTS_ENABLED")).toBeTruthy();
    expect(within(design).getByText("aia-research-harness-1")).toBeTruthy();
    expect(within(design).getByText(/rozbor zadání, kritika návrhu/)).toBeTruthy();

    const config = ai.querySelector("[data-config]") as HTMLElement;
    expect(within(config).getByText("eu-central-1")).toBeTruthy();
    expect(within(config).getByText("eu.anthropic.claude-sonnet-4-5-20250929-v1:0")).toBeTruthy();
    expect(within(config).getByText(/interní materiál bez informací o klientovi/)).toBeTruthy();
    expect(within(ai).getByText(/Zatím bez nativního kroku/)).toBeTruthy();
    expect(within(ai).getByRole("note").textContent).toMatch(/^Neověřeno\. Stránka ukazuje kód a konfiguraci nasazení, nikdy spojení/);

    expect(ai.textContent).not.toMatch(OVERCLAIM);
    expect(ai.textContent).not.toMatch(LOGIN);
    expect(screen.queryByRole("textbox", { name: /klíč|key/i })).toBeNull();
    expect(elsewhere()).toEqual([]);
  });

  it("groups the activities by where AI works, counts them, and lists what /config cannot read as unknown, never off", async () => {
    api();
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork")).toBeTruthy());
    const group = (g: string) => section("ai").querySelector(`[data-ai-group="${g}"]`) as HTMLElement;
    expect(within(group("study")).getByText("Návrh studie")).toBeTruthy();
    expect(group("study").querySelector('[data-activity="design_agents"]')).toBeTruthy();
    expect(group("run").querySelector('[data-activity="respondent_fieldwork"]')).toBeTruthy();
    // Listed from the code, its switch not readable here: unknown, never off.
    const personas = card("population_personas");
    expect(personas.getAttribute("data-state")).toBe("unread");
    expect(within(personas).getByText("Stav nevidíme")).toBeTruthy();
    expect(within(personas).getByText("AIA_AI_POPULATION_PERSONAS_ENABLED")).toBeTruthy();
    expect(card("run_qc").getAttribute("data-state")).toBe("not_built");
    expect(within(card("run_qc")).getByText("Nepostaveno")).toBeTruthy();
    expect(group("out").querySelector('[data-activity="report_pdf"]')).toBeTruthy();
    expect(group("client").querySelector('[data-activity="client_source_proposals"]')).toBeTruthy();
    // Fieldwork's own switch column and model, and its words no longer say every respondent is fictional.
    expect(within(card("design_agents")).getByText("AIA_AI_RESEARCH_AGENTS_ENABLED")).toBeTruthy();
    expect(within(card("respondent_fieldwork")).getByText(/fiktivní, nebo z populace/)).toBeTruthy();
    expect(section("ai").querySelector('[data-count="on"]')?.textContent).toBe("1 zapnuto");
    expect(section("ai").querySelector('[data-count="off"]')?.textContent).toBe("1 vypnuto");
    expect(section("ai").querySelector('[data-count="new"]')?.textContent).toBe("2 nové, zatím nepostavené");
    expect(within(section("ai")).getByText("Spravuje nasazení · jen ke čtení")).toBeTruthy();
    expect(within(section("ai").querySelector("[data-config]") as HTMLElement).getByText("oblast v EU: data zůstávají v EU")).toBeTruthy();
  });

  it("keeps an activity the document comes to list in its own group, once, and marks the group headings as row groups", async () => {
    const doc = DOC();
    doc.ai_runtime = { ...AI_RUNTIME, activities: [...AI_RUNTIME.activities, {
      key: "report_pdf", step_kind: "research_report", capabilities: [], versions: [], switches: ["AIA_AI_RUNTIME_ENABLED"], actions: [],
    }] };
    api({ "GET /api/v1/settings": () => doc });
    render(<ControlPanel />);
    await waitFor(() => expect(card("report_pdf")).toBeTruthy());
    expect(section("ai").querySelectorAll('[data-activity="report_pdf"]')).toHaveLength(1);
    expect(section("ai").querySelector('[data-ai-group="out"] [data-activity="report_pdf"]')).toBeTruthy();
    expect(section("ai").querySelector('[data-ai-group="run"] [data-activity="report_pdf"]')).toBeNull();
    for (const th of section("ai").querySelectorAll("[data-ai-group] th")) expect(th.getAttribute("scope")).toBe("rowgroup");
  });

  it("counts as new only what the document does not list yet: an activity it lists is neither new nor drawn twice", async () => {
    const doc = DOC();
    doc.ai_runtime = { ...AI_RUNTIME, activities: [...AI_RUNTIME.activities, {
      key: "run_qc", step_kind: "research_run_qc", capabilities: [], versions: [], switches: ["AIA_RUN_QC_ENABLED"], actions: [],
    }] };
    api({ "GET /api/v1/settings": () => doc });
    render(<ControlPanel />);
    await waitFor(() => expect(card("run_qc")).toBeTruthy());
    expect(section("ai").querySelectorAll('[data-activity="run_qc"]')).toHaveLength(1);
    // lead_plans alone is still the code's list, not built.
    expect(section("ai").querySelector('[data-count="new"]')?.textContent).toBe("1 nové, zatím nepostavené");
  });

  it("names the region's and the approved classes' sources under technical details, as the switch's and the model's", async () => {
    api();
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork")).toBeTruthy());
    const route = section("ai").querySelector("[data-config]") as HTMLElement;
    expect(within(route).queryByText("AIA_BEDROCK_REGION")).toBeNull();
    fireEvent.click(within(panelOf("AI běh")).getByRole("switch", { name: "Technické údaje", hidden: true }));
    for (const source of ["AIA_BEDROCK_REGION", "AIA_AI_ROUTE_APPROVED_FOR", "AIA_BEDROCK_MODEL_ID"]) {
      expect(await within(route).findByText(source)).toBeTruthy();
    }
    // The region's EU reading stays beside its source.
    expect(within(route).getByText("oblast v EU: data zůstávají v EU")).toBeTruthy();
  });

  it("keeps an invalid activity standing out, and says the API reads the personas switch too", async () => {
    api({ "GET /config": () => CONFIG({ switches: { AIA_AI_RUNTIME_ENABLED: null } }) });
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork").getAttribute("data-state")).toBe("invalid"));
    expect(card("respondent_fieldwork").className).not.toContain("text-ink-muted");
    expect(within(card("population_personas")).getByText(/čte API .* i worker/)).toBeTruthy();
  });

  it("the runtime off: says which switch and what happens, and never suggests a login", async () => {
    technicalOn();
    api({ "GET /config": () => CONFIG({ enabled: false, switches: { AIA_AI_RUNTIME_ENABLED: false, AIA_AI_RESEARCH_AGENTS_ENABLED: true } }) });
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork").getAttribute("data-state")).toBe("off"));
    expect(card("design_agents").getAttribute("data-state")).toBe("off");
    const fieldwork = card("respondent_fieldwork");
    expect(within(fieldwork).getByText("Vypnuto v konfiguraci nasazení. Běh výzkumu počká u sběru dat a modelu se nic neodešle.")).toBeTruthy();
    expect(within(fieldwork).getByText("Přepínač: AIA_AI_RUNTIME_ENABLED")).toBeTruthy();
    // The design switch being on changes nothing while the runtime is off, and the reason says so.
    expect(within(card("design_agents")).getByText("Přepínač: AIA_AI_RUNTIME_ENABLED")).toBeTruthy();
    const ai = section("ai");
    expect(within(ai).queryByText("Zapnuto v konfiguraci")).toBeNull();
    expect(within(ai.querySelector("[data-config]") as HTMLElement).getByText("vypnuto")).toBeTruthy();
    expect(ai.textContent).not.toMatch(OVERCLAIM);
    expect(ai.textContent).not.toMatch(LOGIN);
    expect(within(ai).getByText(/Žádné přihlášení ani API klíč neexistuje/)).toBeTruthy();
    expect(elsewhere()).toEqual([]);
  });

  it("a value the worker refuses: invalid, never off or on -- in the design switch it stops fieldwork too", async () => {
    technicalOn();
    api({ "GET /config": () => CONFIG({ enabled: null, switches: { AIA_AI_RUNTIME_ENABLED: null, AIA_AI_RESEARCH_AGENTS_ENABLED: false } }) });
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork").getAttribute("data-state")).toBe("invalid"));
    expect(within(card("respondent_fieldwork")).getByText(/^Konfigurace nasazení má hodnotu, kterou worker odmítne: worker se nespustí/)).toBeTruthy();
    expect(within(card("respondent_fieldwork")).getByText("Přepínač: AIA_AI_RUNTIME_ENABLED")).toBeTruthy();
    expect(within(section("ai")).queryByText("Vypnuto")).toBeNull();
    expect(within(section("ai")).queryByText("Zapnuto v konfiguraci")).toBeNull();
    cleanup();

    api({ "GET /config": () => CONFIG({ switches: { AIA_AI_RUNTIME_ENABLED: true, AIA_AI_RESEARCH_AGENTS_ENABLED: null } }) });
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork").getAttribute("data-state")).toBe("invalid"));
    expect(card("design_agents").getAttribute("data-state")).toBe("invalid");
    expect(within(card("respondent_fieldwork")).getByText("Přepínač: AIA_AI_RESEARCH_AGENTS_ENABLED")).toBeTruthy();
  });

  it("an unreadable configuration: unknown, nothing claimed, and the rest of the panel still renders", async () => {
    // The page read /config when it loaded, and loadConfig() keeps that read for the API.
    // The panel reads /config again for the switches, and that read is the one that fails.
    api();
    await loadConfig();
    api({ "GET /config": () => new Response("upstream", { status: 502 }) });
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork").getAttribute("data-state")).toBe("unknown"));
    expect(card("design_agents").getAttribute("data-state")).toBe("unknown");
    const ai = section("ai");
    expect(within(ai).getByText(/Konfigurace nasazení: nedostupné\./)).toBeTruthy();
    expect(within(ai).getAllByText(/Konfiguraci nasazení se nepodařilo načíst, takže nic netvrdí/).length).toBe(2);
    expect(within(ai).queryByText("Zapnuto v konfiguraci")).toBeNull();
    expect(within(ai).queryByText("Vypnuto")).toBeNull();
    expect(screen.getByText("Vnímání značky")).toBeTruthy();
    cleanup();

    // A /config without the runtime display is the same: nothing to read a state from,
    // said once.
    api({ "GET /config": () => ({ apiBase: "", build: { sha: null } }) });
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork").getAttribute("data-state")).toBe("unknown"));
    await waitFor(() => expect(tab("AI běh").getAttribute("aria-selected")).toBe("true"));
    const alert = within(section("ai")).getByRole("alert");
    expect(alert.textContent).toMatch(/\/config nevrátil přepínače AI\. Konfiguraci nasazení se nepodařilo načíst/);
    expect(alert.textContent?.match(/Konfiguraci nasazení se nepodařilo načíst/g)).toHaveLength(1);
  });

  it("reads approved-for-nothing and an unknown data class as what they are", async () => {
    api({ "GET /config": () => CONFIG({ approvedClasses: [] }) });
    render(<ControlPanel />);
    expect(await screen.findByText(/žádná: trasa nesmí přenést nic, každé volání bude odmítnuto/)).toBeTruthy();
    cleanup();
    api({ "GET /config": () => CONFIG({ approvedClasses: ["CLASS_Z"] }) });
    render(<ControlPanel />);
    expect(await screen.findByText(/neznámá třída; zapnutý worker se s ní nespustí/)).toBeTruthy();
  });

  it("keeps the prototype's identifiers readable, only under history, and offers none of them", async () => {
    api();
    render(<ControlPanel />);
    // The history is reference material: not drawn until technical details are on.
    await waitFor(() => expect(card("respondent_fieldwork")).toBeTruthy());
    expect(document.querySelector("[data-history]")).toBeNull();
    fireEvent.click(within(panelOf("AI běh")).getByRole("switch", { name: "Technické údaje", hidden: true }));
    const history = await waitFor(() => {
      const found = document.querySelector("[data-history]") as HTMLElement | null;
      if (!found) throw new Error("no history yet");
      return found;
    });
    // Each historical id appears, and only inside the history.
    for (const id of ["claude_code_subscription", "CLAUDE_CODE_ONLY"]) {
      const places = screen.getAllByText((_, el) => el?.tagName === "CODE" && el.textContent === id);
      expect(places.length).toBeGreaterThan(0);
      for (const el of places) expect(history.contains(el)).toBe(true);
    }
    expect(within(history).getByText(/Claude Code je dnes jen vývojářský nástroj pro práci na kódu AIA/)).toBeTruthy();
    expect(within(history).getByText(/v záznamech bez ceny za token/)).toBeTruthy();
    // The project's API ceiling is stored by the generic project API; no screen is promised.
    const ceiling = within(history).getByText("Strop placeného API projektu (prototyp)").closest("[data-setting]") as HTMLElement;
    expect(within(ceiling).getByText("ukládá jen obecné API projektů; nativní běhy se tím neřídí")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/obrazovce projektu/);
    // The native provider is never listed as history.
    expect(history.querySelector('[data-provider="aws_bedrock"]')).toBeNull();
  });

  it("a member reads what powers AIA too, without the deployment group", async () => {
    api({}, false);
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork")).toBeTruthy());
    expect(section("deployment")).toBeNull();
    expect(section("ai")).toBeTruthy();
  });

  it("on the Settings page, AI is one section, and the separate Bedrock card is gone", async () => {
    api();
    render(<SettingsPage />);
    await waitFor(() => expect(tab("AI běh").getAttribute("aria-selected")).toBe("true"));
    expect(await screen.findByRole("heading", { name: "AI v AIA" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Amazon Bedrock" })).toBeNull();
    // Account details remain available without interrupting the settings task.
    expect(screen.getByText("Účet").closest("summary")?.textContent).toBe("Účet · owner@example.test");
    expect(screen.queryByRole("heading", { name: "Klasické rozhraní 18.6.6" })).toBeNull();
    expect(document.querySelector('a[href^="/classic"], a[href*="classic-projects"]')).toBeNull();
    expect(screen.queryByRole("link", { name: "Claude Code" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Obecné nastavení" })).toBeNull();
    expect(screen.queryByLabelText("ANTHROPIC_API_KEY")).toBeNull();
    expect(called("POST", "/api/settings/ai_check")).toEqual([]);
    expect(elsewhere()).toEqual([]);
  });
});


// ---------------------------------------------------------------- the tabs

const tab = (name: string) => screen.getByRole("tab", { name });
const panelOf = (name: string) => document.getElementById(tab(name).getAttribute("aria-controls") as string) as HTMLElement;

describe("the settings tabs", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/app/settings");
  });

  it("groups all ten settings tabs by purpose, each with its subtitle and icon, and opens on methodology", async () => {
    api();
    render(<ControlPanel />);
    await screen.findByRole("tablist", { name: "Oddíly nastavení" });
    expect(screen.getAllByRole("tab").map((t) => t.getAttribute("aria-label"))).toEqual([
      "Metodika", "Systémové prompty", "Deep Research", "AI běh", "Přístup a schvalování", "Studie a rozpočty", "Audit", "Stav systému", "Reference", "Správa dat",
    ]);
    expect(screen.getByRole("group", { name: "Nastavení výzkumu" })).toBeTruthy();
    expect(screen.getByRole("group", { name: "Tým a peníze" })).toBeTruthy();
    expect(screen.queryByRole("group", { name: "Tým a útrata" })).toBeNull();
    expect(screen.getByRole("group", { name: "Provoz" })).toBeTruthy();
    // Each tab names what it holds under its title, and carries a decorative icon.
    expect(tab("Metodika").textContent).toContain("Jak se počítají mapy a čísla");
    expect(tab("AI běh").textContent).toContain("Co pohání AI · jen ke čtení");
    expect(tab("Správa dat").textContent).toContain("Smazání klienta, uchovávané záznamy");
    for (const t of screen.getAllByRole("tab")) expect(t.querySelector("svg[aria-hidden='true']")).toBeTruthy();
    expect(tab("Metodika").getAttribute("aria-selected")).toBe("true");
    expect(panelOf("Metodika").hidden).toBe(false);
    for (const other of ["Systémové prompty", "Deep Research", "AI běh", "Přístup a schvalování", "Studie a rozpočty", "Audit", "Stav systému", "Reference", "Správa dat"]) {
      expect(panelOf(other).hidden).toBe(true);
      expect(tab(other).getAttribute("aria-selected")).toBe("false");
    }
  });

  it("opens Stav systému and Správa dat as their own tabs, saying plainly what AIA does not have yet", async () => {
    // Their routes not deployed: a 404 each.
    const none = () => new Response('{"code":"http_404","message":"Not Found"}', { status: 404 });
    api({ "GET /api/v1/settings/system-status": none, "GET /api/v1/settings/error-tracking": none, "GET /api/v1/settings/kept-records": none });
    render(<ControlPanel />);
    await screen.findByRole("tablist");
    fireEvent.click(tab("Stav systému"));
    expect(panelOf("Stav systému").hidden).toBe(false);
    expect(within(panelOf("Stav systému")).getByRole("heading", { name: "Připravenost po nasazení" })).toBeTruthy();
    expect(within(panelOf("Stav systému")).getByRole("heading", { name: "Hlášení chyb" })).toBeTruthy();
    expect((await within(panelOf("Stav systému")).findAllByText("V AIA zatím není")).length).toBe(2);
    fireEvent.click(tab("Správa dat"));
    expect(within(panelOf("Správa dat")).getByRole("heading", { name: "Smazat klienta" })).toBeTruthy();
    expect(within(panelOf("Správa dat")).getByRole("heading", { name: "Uchovávané záznamy" })).toBeTruthy();
    expect(await within(panelOf("Správa dat")).findByText("V AIA zatím není")).toBeTruthy();
    expect(window.location.hash).toBe("#data");
  });

  it("puts each group where its tab says, and the read-only material under Reference", async () => {
    api();
    render(<ControlPanel />);
    await screen.findByRole("tablist");
    expect(panelOf("AI běh").contains(section("ai"))).toBe(true);
    expect(panelOf("Přístup a schvalování").contains(section("approvals"))).toBe(true);
    // The role matrix is reference material: drawn only with technical details on.
    expect(section("roles")).toBeNull();
    fireEvent.click(within(panelOf("Přístup a schvalování")).getByRole("switch", { name: "Technické údaje", hidden: true }));
    expect(panelOf("Přístup a schvalování").contains(section("roles"))).toBe(true);
    expect(panelOf("Studie a rozpočty").contains(section("studies"))).toBe(true);
    expect(panelOf("Audit").contains(section("audit"))).toBe(true);
    const reference = panelOf("Reference");
    for (const id of ["deployment", "invariants"]) expect(reference.contains(section(id))).toBe(true);
    // A group the page has no tab for lands in Reference rather than disappearing.
    expect(within(reference).getByText("something new")).toBeTruthy();
  });

  it("heads each tab with what it is for and its scope, and hides nothing behind a disclosure", async () => {
    api();
    render(<ControlPanel />);
    await screen.findByRole("tablist");
    await waitFor(() => expect(card("respondent_fieldwork")).toBeTruthy());
    for (const name of ["AI běh", "Přístup a schvalování", "Studie a rozpočty", "Audit", "Reference"]) {
      fireEvent.click(tab(name));
      const panel = panelOf(name);
      const facts = panel.querySelector("[data-tab-facts]") as HTMLElement;
      expect(facts.textContent).toMatch(/^Platí pro: .+ · Mění: .+/);
      expect(within(panel).getByRole("switch", { name: "Technické údaje" })).toBeTruthy();
      expect(panel.querySelectorAll("details, summary")).toHaveLength(0);
    }
    // The reference names its groups up front as categories with their counts.
    const cats = panelOf("Reference").querySelector("[data-reference-categories]") as HTMLElement;
    expect([...cats.querySelectorAll("[data-reference-category]")].map((b) => b.getAttribute("data-reference-category"))).toContain("invariants");
  });

  it("reads Reference as tables by category, filters by category and by who changes a value, and says what each means", async () => {
    api();
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Reference" }));
    const reference = panelOf("Reference");
    const env = (await within(reference).findByText("Prostředí")).closest("tr") as HTMLElement;
    expect(env.getAttribute("data-owner")).toBe("deployment");
    expect(within(env).getByText(/Rozlišuje vývojové/)).toBeTruthy();
    expect(within(section("deployment")).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Hodnota", "Nastaveno", "Kdo mění", "Co znamená"]);
    // Only the rules fixed in code.
    fireEvent.click(within(within(reference).getByRole("radiogroup", { name: "Kdo mění" })).getByRole("radio", { name: "Pevné pravidlo" }));
    expect(reference.querySelector('[data-owner="deployment"]')).toBeNull();
    expect(reference.querySelector('[data-owner="fixed"]')).toBeTruthy();
    fireEvent.click(within(within(reference).getByRole("radiogroup", { name: "Kdo mění" })).getByRole("radio", { name: "Vše" }));
    // One category at a time.
    fireEvent.click(reference.querySelector('[data-reference-category="invariants"]') as HTMLElement);
    expect(section("deployment")).toBeNull();
    expect(reference.contains(section("invariants"))).toBe(true);
    expect(within(reference).getByRole("status").textContent).toMatch(/^Zobrazeno \d+ z \d+ hodnot$/);
  });

  it("lists each Reference value once, invariants under Invarianty only, and counts each chip under the filters", async () => {
    // An invariant in a reference group (as residency, workflow and evidence carry them).
    const doc = DOC();
    doc.groups = doc.groups.map((g) => (g.key === "deployment" ? { ...g, items: [...g.items, { key: "eu_residency", value: true, control: "INVARIANT" as const, source: "ADR 0008", unit: null }] } : g));
    api({ "GET /api/v1/settings": () => doc });
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Reference" }));
    const reference = panelOf("Reference");
    await within(reference).findByText("Prostředí");
    const keys = [...reference.querySelectorAll("tr[data-setting]")].map((r) => r.getAttribute("data-setting"));
    expect(keys.length).toBe(new Set(keys).size);
    const total = Number(/z (\d+) hodnot/.exec(within(reference).getByRole("status").textContent ?? "")?.[1]);
    expect(total).toBe(keys.length);
    expect(reference.querySelector('[data-reference-category="all"]')?.textContent).toBe(`Vše${total}`);
    // Under Kdo mění, a chip counts only what its group then shows.
    fireEvent.click(within(within(reference).getByRole("radiogroup", { name: "Kdo mění" })).getByRole("radio", { name: "Spravuje nasazení" }));
    const deployment = reference.querySelector('[data-reference-category="deployment"]')?.textContent ?? "";
    expect(Number(/(\d+)$/.exec(deployment)?.[1])).toBe(section("deployment").querySelectorAll('tr[data-owner="deployment"]').length);
    expect(reference.querySelector('[data-reference-category="invariants"]')?.textContent).toMatch(/0$/);
    // Nothing in the chosen category: said, though other groups still match.
    fireEvent.click(reference.querySelector('[data-reference-category="invariants"]') as HTMLElement);
    expect(within(reference).getByText("Nic neodpovídá výběru.")).toBeTruthy();
  });

  it("shows one panel at a time and keeps the others' state when switching back", async () => {
    api();
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Přístup a schvalování" }));
    expect(panelOf("Přístup a schvalování").hidden).toBe(false);
    expect(panelOf("AI běh").hidden).toBe(true);
    fireEvent.click(await within(panelOf("Přístup a schvalování")).findByRole("button", { name: "+ Přidat člena" }));
    const email = () => within(panelOf("Přístup a schvalování")).getByLabelText("E-mail nového člena") as HTMLInputElement;
    fireEvent.change(email(), { target: { value: "rozepsany@example.test" } });
    fireEvent.click(tab("Audit"));
    fireEvent.click(tab("Přístup a schvalování"));
    // Looking at another tab did not throw away what was typed and not added yet.
    expect(email().value).toBe("rozepsany@example.test");
  });

  it("opens the tab a link names, and records the one you choose", async () => {
    window.history.replaceState(null, "", "/app/settings#reference");
    api();
    render(<ControlPanel />);
    await screen.findByRole("tablist");
    await waitFor(() => expect(tab("Reference").getAttribute("aria-selected")).toBe("true"));
    fireEvent.click(tab("Audit"));
    expect(window.location.hash).toBe("#audit");
  });

  it("moves between tabs with the arrow keys, wrapping at the ends", async () => {
    api();
    render(<ControlPanel />);
    await screen.findByRole("tablist");
    fireEvent.click(tab("AI běh"));
    fireEvent.keyDown(tab("AI běh"), { key: "ArrowRight" });
    expect(tab("Přístup a schvalování").getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(tab("Přístup a schvalování"), { key: "ArrowLeft" });
    fireEvent.keyDown(tab("AI běh"), { key: "ArrowLeft" });
    expect(tab("Deep Research").getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(tab("Deep Research"), { key: "Home" });
    expect(tab("Metodika").getAttribute("aria-selected")).toBe("true");
    // Only the selected tab is in the tab order.
    expect(tab("Metodika").tabIndex).toBe(0);
    expect(tab("Audit").tabIndex).toBe(-1);
  });

  it("does not ask for the prompts until the tab is opened, and never for a member", async () => {
    api();
    render(<ControlPanel />);
    await screen.findByRole("tablist");
    expect(called("GET", "/api/v1/system-prompts")).toEqual([]);
    fireEvent.click(tab("Systémové prompty"));
    await waitFor(() => expect(called("GET", "/api/v1/system-prompts")).toHaveLength(1));
    cleanup();

    api({}, false);
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Systémové prompty" }));
    expect(await screen.findByText(/Systémové prompty vidí a upravuje jen vlastník nebo správce/)).toBeTruthy();
    expect(called("GET", "/api/v1/system-prompts")).toEqual([]);
  });

  it("asks for the Deep Research settings only when their tab is opened, for any member", async () => {
    technicalOn();
    api({}, false);
    render(<ControlPanel />);
    await screen.findByRole("tablist");
    expect(called("GET", "/api/v1/deep-research/settings")).toEqual([]);
    fireEvent.click(tab("Deep Research"));
    // A member reads them: the API, not the page, decides who may change one.
    await waitFor(() => expect(called("GET", "/api/v1/deep-research/settings")).toHaveLength(1));
    expect(panelOf("Deep Research").contains(section("deep_research"))).toBe(true);
    // The settings document's own group says how the values are set and what no value changes.
    // It is drawn on this tab, not again in Reference (whose invariants list holds every rail).
    const group = within(panelOf("Deep Research"));
    expect(group.getByText(/Jen veřejné zdroje: robots.txt platí/)).toBeTruthy();
    expect(group.getByText(/Pravidla Deep Research/)).toBeTruthy();
    expect(within(panelOf("Reference")).queryByText(/Pravidla Deep Research/)).toBeNull();
  });
});


it("follows changed settings hashes and preserves the framework's navigation state", async () => {
  api(); render(<ControlPanel />); await screen.findByRole("tablist");
  window.history.replaceState({ __NA: true, marker: "preserve" }, "", "/app/settings");
  fireEvent.click(tab("Audit")); expect(window.history.state).toMatchObject({ __NA: true, marker: "preserve" });
  window.history.replaceState(window.history.state, "", "/app/settings#reference");
  fireEvent(window, new HashChangeEvent("hashchange"));
  await waitFor(() => expect(tab("Reference").getAttribute("aria-selected")).toBe("true"));
});

 it("explains what a setting does, keeps its technical source optional and formats money for a reader", async () => {
    api({ "GET /api/v1/studies/STU-1": () => ({ ...STUDY("STU-1", "Vnímání značky"), budget_usd: 20, spent_usd: 12.714524700000009, remaining_usd: 7.285475299999991 }) });
    render(<ControlPanel />);
    const env = (await screen.findByText("Prostředí")).closest("[data-setting]")!;
    expect(within(env as HTMLElement).getByText(/Rozlišuje vývojové/)).toBeTruthy();
    // No disclosure: the source is a technical detail, shown for the whole page by one switch.
    expect(env.querySelector("details")).toBeNull();
    expect(env.querySelector("[data-technical]")).toBeNull();
    const toggle = within(panelOf("Reference")).getByRole("switch", { name: "Technické údaje", hidden: true });
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    fireEvent.click(toggle);
    expect(env.querySelector("[data-technical]")?.textContent).toBeTruthy();
    expect(sessionStorage.getItem("aia.settings.technical")).toBe("1");
    fireEvent.click(screen.getByRole("tab", { name: "Studie a rozpočty" }));
    expect(await screen.findByText("12,71 USD")).toBeTruthy();
    expect(screen.getByText(/zbývá 7,29 USD/)).toBeTruthy();
    expect(screen.queryByText("12.714524700000009")).toBeNull();
  });

describe("usable settings controls", () => {
  it("changes a member's role where it is shown, offers Vrátit, and adds a new member as a researcher", async () => {
    api({
      "GET /api/v1/members": () => [
        { user_id: "USR-1", email: "owner@example.test", display_name: "", is_active: true, organization_role: "OWNER" },
        { user_id: "USR-3", email: "second@example.test", display_name: "Druhý", is_active: true, organization_role: "OWNER" },
      ],
      "POST /api/v1/members": (b) => ({ user_id: "USR-9", display_name: "", is_active: true, organization_role: "MEMBER", ...(b as object) }),
    });
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Přístup a schvalování" }));
    const roles = await screen.findByRole("radiogroup", { name: "Role: second@example.test" });
    fireEvent.click(within(roles).getByRole("radio", { name: "správce" }));
    await waitFor(() => expect(called("POST", "/api/v1/members")).toHaveLength(1));
    expect(called("POST", "/api/v1/members")[0].body).toEqual({ email: "second@example.test", display_name: "Druhý", role: "ADMIN" });
    expect(await screen.findByText("Role: Druhý je správce · zapsáno do auditu")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Vrátit/ }));
    await waitFor(() => expect(called("POST", "/api/v1/members")).toHaveLength(2));
    expect(called("POST", "/api/v1/members")[1].body).toEqual({ email: "second@example.test", display_name: "Druhý", role: "OWNER" });
    fireEvent.click(screen.getByRole("button", { name: "+ Přidat člena" }));
    const role = screen.getByRole("radiogroup", { name: "Role nového člena" });
    expect(within(role).getByRole("radio", { name: "výzkumník" }).getAttribute("aria-checked")).toBe("true");
    const email = screen.getByLabelText("E-mail nového člena");
    fireEvent.change(email, { target: { value: "nova@example.test" } });
    fireEvent.keyDown(email, { key: "Enter" });
    await waitFor(() => expect(called("POST", "/api/v1/members")).toHaveLength(3));
    expect(called("POST", "/api/v1/members")[2].body).toEqual({ email: "nova@example.test", display_name: "", role: "MEMBER" });
  });

  it("never writes an old name back when a role is chosen while the new name is still being read", async () => {
    // The membership call writes the name and the role together; the list re-reads after the name.
    let members = [
      { user_id: "USR-1", email: "owner@example.test", display_name: "", is_active: true, organization_role: "OWNER" },
      { user_id: "USR-3", email: "second@example.test", display_name: "", is_active: true, organization_role: "MEMBER" },
    ];
    api({
      "GET /api/v1/members": () => members,
      "POST /api/v1/members": (b) => ({ user_id: "USR-3", is_active: true, ...(b as object) }),
    });
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Přístup a schvalování" }));
    const row = await waitFor(() => document.querySelector('[data-member="USR-3"]') as HTMLElement);
    fireEvent.click(within(row).getByRole("button", { name: /^Upravit: Jméno: second@example.test/ }));
    const field = within(row).getByLabelText("Jméno: second@example.test");
    fireEvent.change(field, { target: { value: "Nové jméno" } });
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(() => expect(called("POST", "/api/v1/members")).toHaveLength(1));
    // The list has not shown the new name yet when the role is chosen.
    fireEvent.click(within(screen.getByRole("radiogroup", { name: "Role: second@example.test" })).getByRole("radio", { name: "správce" }));
    await waitFor(() => expect(called("POST", "/api/v1/members")).toHaveLength(2));
    expect(called("POST", "/api/v1/members")[1].body).toEqual({ email: "second@example.test", display_name: "Nové jméno", role: "ADMIN" });
    members = members.map((m) => (m.user_id === "USR-3" ? { ...m, display_name: "Nové jméno", organization_role: "ADMIN" } : m));
  });

  it("drops a refused name, so a later role change does not send it again", async () => {
    let posts = 0;
    api({
      "GET /api/v1/members": () => [
        { user_id: "USR-1", email: "owner@example.test", display_name: "", is_active: true, organization_role: "OWNER" },
        { user_id: "USR-3", email: "second@example.test", display_name: "Staré", is_active: true, organization_role: "MEMBER" },
      ],
      "POST /api/v1/members": (b) => (++posts === 1
        ? new Response('{"code":"request_invalid","message":"display_name too long"}', { status: 422 })
        : { user_id: "USR-3", is_active: true, ...(b as object) }),
    });
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Přístup a schvalování" }));
    const row = await waitFor(() => document.querySelector('[data-member="USR-3"]') as HTMLElement);
    fireEvent.click(within(row).getByRole("button", { name: /^Upravit: Jméno: second@example.test/ }));
    const field = within(row).getByLabelText("Jméno: second@example.test");
    fireEvent.change(field, { target: { value: "Odmítnuté" } });
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(() => expect(called("POST", "/api/v1/members")).toHaveLength(1));
    // The person reverts the field, then changes the role.
    fireEvent.keyDown(within(row).queryByLabelText("Jméno: second@example.test") ?? field, { key: "Escape" });
    fireEvent.click(within(screen.getByRole("radiogroup", { name: "Role: second@example.test" })).getByRole("radio", { name: "správce" }));
    await waitFor(() => expect(called("POST", "/api/v1/members")).toHaveLength(2));
    expect(called("POST", "/api/v1/members")[1].body).toEqual({ email: "second@example.test", display_name: "Staré", role: "ADMIN" });
  });

  it("offers an owner who steps down no Vrátit, and says another owner restores it", async () => {
    api({
      "GET /api/v1/members": () => [
        { user_id: "USR-1", email: "owner@example.test", display_name: "", is_active: true, organization_role: "OWNER" },
        { user_id: "USR-3", email: "second@example.test", display_name: "Druhý", is_active: true, organization_role: "OWNER" },
      ],
      "POST /api/v1/members": (b) => ({ user_id: "USR-1", display_name: "", is_active: true, ...(b as object) }),
    });
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Přístup a schvalování" }));
    const mine = await screen.findByRole("radiogroup", { name: "Role: owner@example.test" });
    fireEvent.click(within(mine).getByRole("radio", { name: "správce" }));
    await waitFor(() => expect(called("POST", "/api/v1/members")).toHaveLength(1));
    expect(await screen.findByText(/roli vlastníka vám může vrátit jiný vlastník/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Vrátit/ })).toBeNull();
  });

  it("refuses an address that is not an e-mail at the field, and sends nothing", async () => {
    api();
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Přístup a schvalování" }));
    fireEvent.click(await screen.findByRole("button", { name: "+ Přidat člena" }));
    const email = screen.getByLabelText("E-mail nového člena");
    fireEvent.change(email, { target: { value: "alice" } });
    fireEvent.keyDown(email, { key: "Enter" });
    expect(screen.getByText("Zadejte e-mailovou adresu, např. jmeno@organizace.cz.")).toBeTruthy();
    expect(email.getAttribute("aria-invalid")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Přidat" }));
    expect(called("POST", "/api/v1/members")).toEqual([]);
  });

  it("names the methodology and research-policy events in words, their codes only as technical detail", async () => {
    const entry = (event_id: number, action: string) => ({ event_id, action, client_id: null, study_id: null, subject_user_id: null, actor_id: "USR-1", role: null, reason: null, payload: {}, created_at: null });
    api({ "GET /api/v1/access-audit": () => [entry(1, "METHODOLOGY_RESET"), entry(2, "DR_SETTING_WITHDRAWN")] });
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Audit" }));
    const audit = panelOf("Audit");
    expect(await within(audit).findByText("Návrat metodiky na verzi z kódu", { selector: "strong" })).toBeTruthy();
    expect(within(audit).getByText("Návrat pravidla rešerše na výchozí", { selector: "strong" })).toBeTruthy();
    expect(audit.textContent).not.toMatch(/METHODOLOGY_RESET|methodology reset/);
  });

  it("puts the spend per researcher on Studie a rozpočty, read from its own route", async () => {
    api(); render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Studie a rozpočty" }));
    const panel = panelOf("Studie a rozpočty");
    expect(within(panel).getByRole("heading", { name: "Útrata podle výzkumníka" })).toBeTruthy();
    expect(await within(panel).findByText("Za toto období nikdo nic neutratil.")).toBeTruthy();
    expect(called("GET", "/api/v1/settings/researcher-spend")).toHaveLength(1);
  });

  it("filters studies without unmounting their budget drafts and searches the readable audit", async () => {
    api(); render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Studie a rozpočty" }));
    const study = document.querySelector('[data-study="STU-1"]') as HTMLElement;
    const budget = await within(study).findByRole("spinbutton", { name: "Rozpočet studie Vnímání značky" }) as HTMLInputElement;
    fireEvent.change(budget, { target: { value: "600" } });
    fireEvent.change(screen.getByRole("searchbox", { name: "Hledat studii nebo klienta" }), { target: { value: "Cizí" } });
    expect(study.hidden).toBe(true);
    fireEvent.change(screen.getByRole("searchbox", { name: "Hledat studii nebo klienta" }), { target: { value: "Vnímání" } });
    expect(budget.value).toBe("600");
    expect(study.hidden).toBe(false);
    fireEvent.click(screen.getByRole("tab", { name: "Audit" }));
    expect(within(panelOf("Audit")).getByText("Záznam přístupu ke klientovi", { selector: "strong" })).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox", { name: "Typ události v historii" }), { target: { value: "CLIENT_GRANT" } });
    expect(within(panelOf("Audit")).getByText("Zobrazeno 1 z 1 záznamů")).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: "Hledat v historii" }), { target: { value: "no-such-event" } });
    expect(screen.getByText("Žádný záznam neodpovídá hledání.")).toBeTruthy();
    expect(called("PUT", "/api/v1/studies/STU-1/budget")).toEqual([]);
  });
});
