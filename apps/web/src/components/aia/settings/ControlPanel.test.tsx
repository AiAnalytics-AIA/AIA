// @vitest-environment jsdom
// The settings control panel against a fake AIA API: the signed-in token is what
// reaches the API, every setting says how it is controlled, "not configured" and
// "costs hidden" never read as zero, a change goes through the API and the
// panel re-reads, and a refusal is shown as the API gave it.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { cs } from "@/i18n/cs";
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
      // A route may answer with a promise, so a test can hold one read open.
      const answer = (await routes[`${method} ${u.split("?")[0]}`]?.(body)) ?? {};
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

// The technical value "Prostředí" as its reference row: the Environment card (F21) on the same tab
// says "Prostředí" too, in a <dt>, so a bare text query finds two.
const referenceEnv = (root: HTMLElement) => waitFor(() => {
  const row = within(root).getAllByText("Prostředí").map((e) => e.closest("tr[data-setting]")).find((r) => r !== null);
  expect(row).toBeTruthy();
  return row as HTMLElement;
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
    await openSection("Přístup a schvalování");
    const ownerRow = await waitFor(() => document.querySelector('[data-member="USR-1"]') as HTMLElement);
    expect(ownerRow.querySelector('[role="radiogroup"]')).toBeNull();
    expect(screen.getByText("Roli vlastníka mění jen vlastník.")).toBeTruthy();
    const admin = screen.getByRole("radiogroup", { name: "Role: admin@example.test" });
    expect(within(admin).getAllByRole("radio").map((r) => r.textContent)).toEqual(["správce", "výzkumník"]);
  });

  it("offers the organization's only active OWNER no demotion", async () => {
    api();
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
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
    await openSection("Přístup a schvalování");
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
    // "92 % · ⚠" to the eye, the whole sentence to a screen reader; grey, never the fault's colour.
    expect(row.querySelector("[data-spend-line]")?.textContent).toBe("92 % rozpočtu · zbývá 8,00 USD · téměř vyčerpáno");
    expect(row.querySelector("[data-spend-line] svg")).not.toBeNull(); // the warning is Phosphor's icon, not a glyph
    expect(row.className).toContain("bg-surface-sunken");
    expect(row.className).not.toMatch(/status-(you|fault)/);
    // Named with its client, so a list of links never reads "Pravidla" six times.
    const link = within(row).getByRole("link", { name: "Pravidla klienta Klient A", hidden: true });
    expect(link.getAttribute("title")).toBe("Profil → Pravidla klienta");
    expect(link.className).toContain("min-h-11");
    // The status is read here, not chosen (fidelity F7): its word and glyph, no picker.
    expect(within(row).getByText("Aktivní")).toBeTruthy();
    expect(within(row).queryByRole("radiogroup", { hidden: true })).toBeNull();
    // The table's six columns, the money ones by their D-01 names.
    const table = row.closest("table") as HTMLElement;
    expect(within(table).getAllByRole("columnheader", { hidden: true }).map((h) => h.textContent)).toEqual(["Studie", "Stav", "Utraceno", "Rozpočet studie (USD)ⓘ", "Práh potvrzení (USD)ⓘ", "Peněženkaⓘ"]);
    expect(link.getAttribute("href")).toContain("/app/clients/CLI-a/profile");
    expect(screen.getByText("Cizí studie").closest("[data-study]")?.getAttribute("data-near")).toBeNull();
  });

  it("explains the four money names under the table, opened by a button, the client's budget included", async () => {
    api();
    render(<ControlPanel />);
    await screen.findByText("Vnímání značky");
    const names = document.querySelector("[data-money-names]") as HTMLElement;
    const open = screen.getByRole("button", { name: /Co znamenají částky/, hidden: true });
    expect(names.hidden).toBe(true);
    fireEvent.click(open);
    expect(open.getAttribute("aria-expanded")).toBe("true");
    expect([...names.querySelectorAll("dt")].map((d) => d.textContent)).toEqual(["Rozpočet klienta", "Rozpočet studie", "Peněženka", "Práh potvrzení"]);
    expect(names.textContent).toContain("Od 10 USD, nejvýš rozpočet studie.");
  });

  it("filters the studies by client and opens what each money column is from its ⓘ, a real button (F16)", async () => {
    api({
      "GET /api/v1/studies": () => [STUDY("STU-1", "Vnímání značky"), { ...STUDY("STU-2", "Cizí studie"), client_id: "CLI-b" }],
      "GET /api/v1/clients": () => [
        { client_id: "CLI-a", slug: "a", name: "Klient A", status: "ACTIVE", reference: "", study_count: 1, created_at: null },
        { client_id: "CLI-b", slug: "b", name: "Klient B", status: "ACTIVE", reference: "", study_count: 1, created_at: null },
      ],
    });
    render(<ControlPanel />);
    await screen.findByText("Vnímání značky");
    const filter = document.querySelector("[data-client-filter]") as HTMLSelectElement;
    expect([...filter.options].map((o) => o.textContent)).toEqual(["Všichni klienti (2)", "Klient A (1)", "Klient B (1)"]);
    const row = (id: string) => document.querySelector(`[data-study="${id}"]`) as HTMLElement;
    fireEvent.change(filter, { target: { value: "CLI-b" } });
    expect(row("STU-1").hidden).toBe(true);
    expect(row("STU-2").hidden).toBe(false);
    // The filter and the search together; a hidden row keeps what was typed in it (it is not unmounted).
    fireEvent.change(screen.getByRole("searchbox", { name: "Hledat studii nebo klienta", hidden: true }), { target: { value: "Vnímání" } });
    expect(row("STU-2").hidden).toBe(true);
    fireEvent.change(filter, { target: { value: "" } });
    expect(row("STU-1").hidden).toBe(false);
    // Each money column's ⓘ is a button that opens the four names; the paragraph under the table is gone.
    const names = document.querySelector("[data-money-names]") as HTMLElement;
    const info = screen.getByRole("button", { name: "Co je Práh potvrzení", hidden: true });
    expect(info.getAttribute("aria-controls")).toBe("set-studies-money");
    fireEvent.click(info);
    expect(names.hidden).toBe(false);
    expect(names.textContent).toContain("Rozpočet studie smí měnit každý výzkumník");
    expect(screen.getByRole("heading", { level: 2, name: /^Studie/, hidden: true })).toBeTruthy();
  });

  it("never hides a study by a client filter that has no control left, and reads an unserved remainder as unknown (review of #966)", async () => {
    api({ "GET /api/v1/studies/STU-1": () => ({ ...STUDY("STU-1", "Vnímání značky"), budget_usd: 100, spent_usd: 40, remaining_usd: null }) });
    render(<ControlPanel />);
    await screen.findByText("Vnímání značky");
    // Both studies are one client's: no filter is drawn, and none hides a row.
    expect(document.querySelector("[data-client-filter]")).toBeNull();
    expect((document.querySelector('[data-study="STU-1"]') as HTMLElement).hidden).toBe(false);
    // The server gave no remainder: the line says unknown, never 60 USD worked out in the browser.
    const line = document.querySelector('[data-study="STU-1"] [data-spend-line]') as HTMLElement;
    expect(line.textContent).toContain("zbývá: nezjištěno");
    expect(line.textContent).not.toMatch(/60/);
  });

  it("draws no spend for a study whose spend is unknown, never a 0 beside its budget", async () => {
    api({ "GET /api/v1/studies/STU-1": () => ({ ...STUDY("STU-1", "Vnímání značky"), budget_usd: 100, spent_usd: null, remaining_usd: null }) });
    render(<ControlPanel />);
    const row = (await screen.findByText("Vnímání značky")).closest("[data-study]") as HTMLElement;
    await waitFor(() => expect(within(row).getByText(/náklady nevidíte/)).toBeTruthy());
    expect(row.querySelector("[data-spend-line]")).toBeNull();
  });

  it("changes the organization's self-approval where it is shown, then re-reads", async () => {
    api();
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
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
    api({
      "GET /api/v1/self-approval": () => ({ organization: true, clients: [{ client_id: "CLI-a", allowed: false }], studies: [{ study_id: "STU-1", client_id: "CLI-a", allowed: true }] }),
      "GET /api/v1/settings/client-rules": () => new Response('{"code":"http_404","message":"Not Found"}', { status: 404 }),
    });
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
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

  it("reads each client's data posture and wallet ceiling, an unset posture as CLASSIFIED and no client ceiling as the study budget still applying, never 0", async () => {
    api({
      "GET /api/v1/clients": () => [
        { client_id: "CLI-a", slug: "a", name: "Klient A", status: "ACTIVE", reference: "", study_count: 2, created_at: null },
        { client_id: "CLI-b", slug: "b", name: "Klient B", status: "ACTIVE", reference: "", study_count: 0, created_at: null },
        { client_id: "CLI-c", slug: "c", name: "Klient C", status: "ACTIVE", reference: "", study_count: 0, created_at: null },
      ],
      "GET /api/v1/settings/client-rules": () => [
        { client_id: "CLI-a", name: "Klient A", data_posture: "OPEN", effective_posture: "OPEN", wallet_ceiling_usd: 60, set_by: "USR-1", set_at: null },
        { client_id: "CLI-b", name: "Klient B", data_posture: null, effective_posture: "CLASSIFIED", wallet_ceiling_usd: null, set_by: null, set_at: null },
      ],
    });
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    const panel = document.getElementById("panel-access") as HTMLElement;
    const rules = async (id: string) => waitFor(() => {
      const cell = panel.querySelector(`[data-client="${id}"] [data-client-rules]`) as HTMLElement | null;
      if (!cell || cell.getAttribute("data-client-rules") === "loading") throw new Error("not read");
      return cell;
    });
    const a = await rules("CLI-a");
    expect(a.getAttribute("data-client-rules")).toBe("read");
    expect(within(a).getByText("OPEN")).toBeTruthy();
    expect(a.textContent?.replace(/\s/g, " ")).toContain("60,00 USD");
    const b = await rules("CLI-b");
    expect(within(b).getByText("CLASSIFIED")).toBeTruthy();
    expect(within(b).getByText("nenastaveno, platí CLASSIFIED")).toBeTruthy();
    // No client ceiling is not an uncapped wallet: the study budget still bounds it (ADR 0028).
    expect(within(b).getByText("bez stropu klienta (platí rozpočet studie)")).toBeTruthy();
    expect(within(b).queryByText("bez stropu")).toBeNull();
    expect(b.textContent).not.toMatch(/\b0,00\b/);
    // A client the list does not answer for is unknown: never OPEN, never "bez stropu".
    const c = await rules("CLI-c");
    expect(c.getAttribute("data-client-rules")).toBe("unknown");
    expect(within(c).getByText("nezjištěno")).toBeTruthy();
    expect(c.textContent).not.toMatch(/OPEN|bez stropu/);
    expect(panel.querySelector("[data-client] [data-not-yet]")).toBeNull();
    // Read-only here: no control changes them, the profile does.
    expect(a.querySelector("button, input, [role=radio]")).toBeNull();
    expect(within(panel).getAllByRole("link", { name: "Změnit v Profil → Pravidla" })).toHaveLength(3);
  });

  it("says once when the client rules could not be read, and reads every row unknown, never not-in-AIA or open", async () => {
    for (const answer of [
      () => new Response('{"code":"internal","message":"Boom"}', { status: 500 }),
      () => new Response('{"code":"not_found","message":"No such organization."}', { status: 404 }),
      () => ({ rules: "not a list" }),
    ]) {
      api({ "GET /api/v1/settings/client-rules": answer });
      render(<ControlPanel />);
      await openSection("Přístup a schvalování");
      const panel = document.getElementById("panel-access") as HTMLElement;
      const card = panel.querySelector("#set-clients") as HTMLElement;
      await waitFor(() => expect(card.querySelector('[data-client-rules="unknown"]')).toBeTruthy());
      expect(within(card).getAllByRole("alert")).toHaveLength(1);
      expect(card.querySelector("[data-not-yet]")).toBeNull();
      expect([...card.querySelectorAll("[data-client-rules]")].every((e) => e.getAttribute("data-client-rules") === "unknown")).toBe(true);
      expect(card.textContent).not.toMatch(/OPEN|bez stropu/);
      cleanup();
    }
  });

  it("grants the Metodik mark as an OWNER, with Vrátit, and an administrator only reads it", async () => {
    const team = () => [
      { user_id: "USR-1", email: "owner@example.test", display_name: "Petr", is_active: true, organization_role: "OWNER", methodologist: false },
      { user_id: "USR-2", email: "jana@example.test", display_name: "Jana", is_active: true, organization_role: "MEMBER", methodologist: false },
      { user_id: "USR-3", email: "lucie@example.test", display_name: "Lucie", is_active: false, organization_role: "MEMBER", methodologist: true, deactivated_at: "2026-10-20T10:00:00Z", lead_sealed_at: "2026-10-20T10:00:00Z", lead_erase_after: "2026-11-19T10:00:00Z" },
    ];
    api({ "GET /api/v1/members": team });
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    const panel = document.getElementById("panel-access") as HTMLElement;
    const jana = await waitFor(() => panel.querySelector('[data-member="USR-2"]') as HTMLElement);
    const mark = within(jana.parentElement as HTMLElement).getByRole("switch", { name: "Štítek Metodik: jana@example.test" });
    fireEvent.click(mark);
    await waitFor(() => expect(called("PUT", "/api/v1/members/USR-2/methodologist")).toHaveLength(1));
    expect(called("PUT", "/api/v1/members/USR-2/methodologist")[0].body).toEqual({ methodologist: true });
    fireEvent.click(await screen.findByRole("button", { name: "Vrátit" }));
    await waitFor(() => expect(called("PUT", "/api/v1/members/USR-2/methodologist")).toHaveLength(2));
    expect(called("PUT", "/api/v1/members/USR-2/methodologist")[1].body).toEqual({ methodologist: false });
    // A deactivated member's mark is not changed here.
    expect((within(panel).getByRole("switch", { name: "Štítek Metodik: lucie@example.test" }) as HTMLButtonElement).disabled).toBe(true);
    expect(within(panel).getByText("1 Metodik")).toBeTruthy();
    cleanup();
    // An administrator who is not an OWNER reads the mark: the API refuses them (owner_only).
    api({ "GET /api/v1/members": team, "GET /api/v1/settings": () => ({ ...DOC(true), your_role: "ADMIN" }) });
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    const switches = await waitFor(() => { const all = screen.getAllByRole("switch", { name: /^Štítek Metodik:/ }); if (all.length < 3) throw new Error("not yet"); return all; });
    expect(switches.every((sw) => (sw as HTMLButtonElement).disabled)).toBe(true);
    expect(screen.getAllByText("Přiděluje jen vlastník.").length).toBeGreaterThan(0);
  });

  it("deactivates a member with Vrátit, says their Lead is sealed until it is erased, and restores them", async () => {
    api({
      "GET /api/v1/members": () => [
        { user_id: "USR-1", email: "owner@example.test", display_name: "Petr", is_active: true, organization_role: "OWNER", methodologist: false },
        { user_id: "USR-2", email: "jana@example.test", display_name: "Jana", is_active: true, organization_role: "MEMBER", methodologist: false },
        { user_id: "USR-3", email: "lucie@example.test", display_name: "Lucie", is_active: false, organization_role: "MEMBER", methodologist: false, deactivated_at: "2026-10-20T10:00:00Z", lead_sealed_at: "2026-10-20T10:00:00Z", lead_erase_after: "2026-11-19T10:00:00Z" },
      ],
      "POST /api/v1/members/USR-2/deactivate": () => new Response(JSON.stringify({ code: "insufficient_role", message: "The organization's last OWNER cannot be demoted or deactivated.", details: { reason: "last_owner" } }), { status: 403 }),
    });
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    const panel = document.getElementById("panel-access") as HTMLElement;
    await waitFor(() => expect(panel.querySelector('[data-member="USR-3"]')).toBeTruthy());
    // Your own row offers no deactivation: you would lock yourself out.
    const jana = await within(panel).findByRole("button", { name: "Deaktivovat jana@example.test" });
    expect(within(panel).queryByRole("button", { name: "Deaktivovat owner@example.test" })).toBeNull();
    // A refusal is said in the row.
    fireEvent.click(jana);
    expect(await within(panel).findByText("Poslední aktivní vlastník organizace nemůže přijít o roli ani být deaktivován.")).toBeTruthy();
    // The deactivated member: their Lead sealed, its erasure dated, and Obnovit.
    const lucie = panel.querySelector('[data-member="USR-3"]') as HTMLElement;
    expect(lucie.getAttribute("data-deactivated")).toBe("true");
    const sealed = panel.querySelector('[data-lead-sealed="USR-3"]') as HTMLElement;
    expect(sealed.textContent).toMatch(/Vedoucí zapečetěn/);
    expect(sealed.textContent).toMatch(/19\. 11\. 2026/);
    fireEvent.click(within(panel).getByRole("button", { name: "Obnovit lucie@example.test" }));
    await waitFor(() => expect(called("POST", "/api/v1/members/USR-3/reactivate")).toHaveLength(1));
  });

  it("claims no sealed Lead the API does not report, and offers an administrator no Obnovit on an OWNER", async () => {
    api({
      "GET /api/v1/settings": () => ({ ...DOC(true), your_role: "ADMIN" }),
      "GET /api/v1/members": () => [
        { user_id: "USR-1", email: "owner@example.test", display_name: "Petr", is_active: true, organization_role: "ADMIN", methodologist: false },
        { user_id: "USR-4", email: "eva@example.test", display_name: "Eva", is_active: false, organization_role: "OWNER", methodologist: false, deactivated_at: "2026-10-20T10:00:00Z", lead_sealed_at: null, lead_erase_after: null },
        { user_id: "USR-5", email: "ota@example.test", display_name: "Ota", is_active: false, organization_role: "MEMBER", methodologist: false, deactivated_at: "2026-10-20T10:00:00Z", lead_sealed_at: null, lead_erase_after: null },
      ],
    });
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    const panel = document.getElementById("panel-access") as HTMLElement;
    await waitFor(() => expect(panel.querySelector('[data-member="USR-5"]')).toBeTruthy());
    expect(panel.querySelector("[data-lead-sealed]")).toBeNull();
    expect(panel.textContent).not.toMatch(/zapečetěn:/);
    expect(panel.querySelector('[data-lead-none="USR-5"]')?.textContent).toMatch(/žádný zapečetěný/);
    const restoreOwner = within(panel).getByRole("button", { name: "Obnovit eva@example.test" }) as HTMLButtonElement;
    expect(restoreOwner.disabled).toBe(true);
    fireEvent.click(restoreOwner);
    expect(called("POST", "/api/v1/members/USR-4/reactivate")).toEqual([]);
    expect((within(panel).getByRole("button", { name: "Obnovit ota@example.test" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("says the Lead is sealed on deactivation only when the answer says so", async () => {
    api({
      "GET /api/v1/members": () => [
        { user_id: "USR-1", email: "owner@example.test", display_name: "Petr", is_active: true, organization_role: "OWNER", methodologist: false },
        { user_id: "USR-2", email: "jana@example.test", display_name: "Jana", is_active: true, organization_role: "MEMBER", methodologist: false },
      ],
      "POST /api/v1/members/USR-2/deactivate": () => ({ user_id: "USR-2", email: "jana@example.test", display_name: "Jana", is_active: false, organization_role: "MEMBER", methodologist: false, deactivated_at: "2026-10-23T04:00:00Z", lead_sealed_at: null, lead_erase_after: null }),
    });
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    fireEvent.click(await screen.findByRole("button", { name: "Deaktivovat jana@example.test" }));
    expect(await screen.findByText("Jana: deaktivace hotova. Nepřihlásí se, studie zůstávají.")).toBeTruthy();
    expect(screen.queryByText(/Vedoucí je zapečetěn/)).toBeNull();
  });

  it("knows your own row by your user id, not by the token's e-mail (review of #859)", async () => {
    // The token names another e-mail (or none) under the same subject; /workspace/me says USR-1.
    sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "", subject: "s" }));
    api({
      "GET /api/v1/members": () => [
        { user_id: "USR-1", email: "owner@example.test", display_name: "Petr", is_active: true, organization_role: "OWNER", methodologist: false },
        { user_id: "USR-2", email: "jana@example.test", display_name: "Jana", is_active: true, organization_role: "MEMBER", methodologist: false },
      ],
    });
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    const panel = document.getElementById("panel-access") as HTMLElement;
    expect(await within(panel).findByRole("button", { name: "Deaktivovat jana@example.test" })).toBeTruthy();
    expect(within(panel).queryByRole("button", { name: "Deaktivovat owner@example.test" })).toBeNull();
  });

  it("offers no deactivation while who you are is unread, since any row could be yours", async () => {
    api({
      "GET /api/v1/workspace/me": () => new Response('{"code":"internal","message":"x"}', { status: 500 }),
      "GET /api/v1/members": () => [
        { user_id: "USR-1", email: "owner@example.test", display_name: "Petr", is_active: true, organization_role: "OWNER", methodologist: false },
        { user_id: "USR-2", email: "jana@example.test", display_name: "Jana", is_active: true, organization_role: "MEMBER", methodologist: false },
      ],
    });
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    const panel = document.getElementById("panel-access") as HTMLElement;
    await waitFor(() => expect(panel.querySelector('[data-member="USR-2"]')).toBeTruthy());
    await waitFor(() => expect(called("GET", "/api/v1/workspace/me").length).toBeGreaterThan(0));
    expect(within(panel).queryByRole("button", { name: /^Deaktivovat/ })).toBeNull();
  });

  it("draws the new member's row in step with the table's six columns, Naposledy among them (review of #859, F9)", async () => {
    api();
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    const panel = document.getElementById("panel-access") as HTMLElement;
    fireEvent.click(await within(panel).findByRole("button", { name: "+ Přidat člena" }));
    const table = within(panel).getByRole("table", { name: "Členové" });
    const columns = table.querySelectorAll('[role="columnheader"]').length;
    expect(columns).toBe(6);
    expect([...table.querySelectorAll('[role="columnheader"]')].map((h) => h.textContent)).toContain("Naposledy");
    const row = table.querySelector("[data-member-new]") as HTMLElement;
    // The note spans Naposledy and Stav, as the prototype's: the row still fills every column once.
    const spans = [...row.querySelectorAll(':scope > [role="cell"]')].reduce((n, c) => n + (c.classList.contains("col-span-2") ? 2 : 1), 0);
    expect(spans).toBe(columns);
    // The add and cancel buttons sit in the last, the action column.
    expect(within(row.lastElementChild as HTMLElement).getByRole("button", { name: "Zrušit" })).toBeTruthy();
  });

  it("says when each member was last active, never as a date for one who never was, unknown when not served (F9, F19)", async () => {
    const recent = new Date(Date.now() - 3 * 3_600_000).toISOString();
    api({
      "GET /api/v1/members": () => [
        { user_id: "USR-1", email: "owner@example.test", display_name: "Petr", is_active: true, organization_role: "OWNER", methodologist: false, last_seen_at: recent },
        { user_id: "USR-2", email: "jana@example.test", display_name: "Jana", is_active: true, organization_role: "MEMBER", methodologist: false, last_seen_at: null },
        // An API from before F19 does not serve the field: unknown, never "nikdy".
        { user_id: "USR-3", email: "eva@example.test", display_name: "Eva", is_active: true, organization_role: "MEMBER", methodologist: false },
      ],
    });
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    const panel = document.getElementById("panel-access") as HTMLElement;
    await waitFor(() => expect(panel.querySelector('[data-member="USR-3"]')).toBeTruthy());
    const seen = (id: string) => panel.querySelector(`[data-member="${id}"] [data-last-seen]`) as HTMLElement;
    expect(seen("USR-1").getAttribute("data-last-seen")).toBe(recent);
    expect(seen("USR-1").textContent).toBe("před 3 h");
    expect(seen("USR-1").getAttribute("title")).toBeTruthy();
    expect(seen("USR-2").textContent).toBe("nikdy");
    expect(seen("USR-3").getAttribute("data-last-seen")).toBe("unknown");
    expect(seen("USR-3").textContent).toBe("nezjištěno");
  });

  it("shows a member no Naposledy column: the API serves it to an administrator alone (F19)", async () => {
    api({}, false);
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    const table = await within(document.getElementById("panel-access") as HTMLElement).findByRole("table", { name: "Členové" });
    expect([...table.querySelectorAll('[role="columnheader"]')].map((h) => h.textContent)).not.toContain("Naposledy");
    expect(table.querySelector("[data-last-seen]")).toBeNull();
  });

  it("explains each card behind its ⓘ, a button a keyboard or touch opens, not text on the page (F9)", async () => {
    api();
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    const panel = document.getElementById("panel-access") as HTMLElement;
    await within(panel).findByRole("table", { name: "Členové" });
    for (const [label, id] of [["Jak se mění členové", "members-about"], ["Co která role smí", "members-roles"], ["Co smí štítek Metodik", "members-metodik"], ["Jak funguje samoschválení", "self-approval-about"], ["Co se u klientů mění zde", "clients-about"]] as const) {
      const button = within(panel).getByRole("button", { name: label });
      const text = document.getElementById(id) as HTMLElement;
      expect(button.getAttribute("aria-controls")).toBe(id);
      expect(text.hidden).toBe(true);
      fireEvent.click(button);
      expect(button.getAttribute("aria-expanded")).toBe("true");
      expect(text.hidden).toBe(false);
      fireEvent.click(button);
      expect(text.hidden).toBe(true);
    }
    // The three cards are the tab's h2s, under its h1.
    expect(within(panel).getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual(expect.arrayContaining(["Členové", "Samoschválení", "Klienti"]));
  });

  it("deactivates at once and offers Vrátit, which reactivates", async () => {
    api({
      "GET /api/v1/members": () => [
        { user_id: "USR-1", email: "owner@example.test", display_name: "Petr", is_active: true, organization_role: "OWNER", methodologist: false },
        { user_id: "USR-2", email: "jana@example.test", display_name: "Jana", is_active: true, organization_role: "MEMBER", methodologist: false },
      ],
      "POST /api/v1/members/USR-2/deactivate": () => ({ user_id: "USR-2", email: "jana@example.test", display_name: "Jana", is_active: false, organization_role: "MEMBER", methodologist: false, deactivated_at: "2026-10-23T04:00:00Z", lead_sealed_at: "2026-10-23T04:00:00Z", lead_erase_after: "2026-11-22T04:00:00Z" }),
    });
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    fireEvent.click(await screen.findByRole("button", { name: "Deaktivovat jana@example.test" }));
    await waitFor(() => expect(called("POST", "/api/v1/members/USR-2/deactivate")).toHaveLength(1));
    expect(await screen.findByText(/Vedoucí je zapečetěn/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Vrátit" }));
    await waitFor(() => expect(called("POST", "/api/v1/members/USR-2/reactivate")).toHaveLength(1));
  });

  it("sets, clears and adds a study's own self-approval rule, and returns the organization to the default", async () => {
    api({ "GET /api/v1/self-approval": () => ({ organization: false, clients: [], studies: [{ study_id: "STU-1", client_id: "CLI-a", allowed: false }] }) });
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
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

  it("offers the Metodik mark and deactivation in each row, no longer says they are not in AIA, and explains each role", async () => {
    api();
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    const panel = document.getElementById("panel-access") as HTMLElement;
    await waitFor(() => expect(panel.querySelector('[data-member="USR-1"]')).toBeTruthy());
    expect(within(panel).getByRole("switch", { name: "Štítek Metodik: owner@example.test" })).toBeTruthy();
    expect(within(panel).queryByText(/v AIA zatím nejsou/)).toBeNull();
    expect(panel.querySelector("[data-member] [data-not-yet]")).toBeNull();
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
    await openSection("Studie a rozpočty");
    const tile = (await within(panelOf("Studie a rozpočty")).findByText("Téměř vyčerpané")).parentElement as HTMLElement;
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

describe("Stav systému's technical values (once Reference, F17)", () => {
  it("shows a value found by search in a group with its own panel, its source alone behind technical details", async () => {
    const doc = DOC();
    doc.groups = [...doc.groups, { key: "workflow", items: [item("lease_seconds", 60, "CODE", "aia_core.domain.workflow:LEASE_SECONDS", "s")] }];
    api({ "GET /api/v1/settings": () => doc });
    render(<ControlPanel />);
    await openSection("Stav systému");
    const panel = panelOf("Stav systému");
    fireEvent.change(await within(panel).findByRole("searchbox", { name: "Hledat technickou hodnotu" }), { target: { value: "lease" } });
    const row = await waitFor(() => { const r = panel.querySelector('[data-setting="lease_seconds"]') as HTMLElement | null; if (!r) throw new Error("no row"); return r; });
    // The row is shown with technical details off; only its source waits for them.
    expect(row.closest("[hidden]")).toBeNull();
    expect(within(row).queryByText("aia_core.domain.workflow:LEASE_SECONDS")).toBeNull();
  });

  it("drops what is not the system's state, the evidence thresholds and the simulation constants, and keeps their invariants", async () => {
    // Nigel, 25 Oct 2026: "merge Reference into it, drop what is irrelevant". The thresholds a run
    // applies are Metodika's (Práh zobrazení); Simulace is hidden for the MVP.
    const doc = DOC();
    doc.groups = [...doc.groups,
      { key: "evidence", items: [item("min_cell", 30, "CODE", "aia_core.domain.evidence:REFERENCE_THRESHOLDS", "n"), item("no_invented_certainty", true, "INVARIANT", "ARCHITECTURE.md §10")] },
      { key: "simulation", items: [item("default_spec_seed", 7, "CODE", "aia_core.domain.simulation:DEFAULT_SPEC_SEED"), item("no_visualisation_mutation", true, "INVARIANT", "ARCHITECTURE.md §10")] },
    ];
    api({ "GET /api/v1/settings": () => doc });
    render(<ControlPanel />);
    await openSection("Stav systému");
    const panel = panelOf("Stav systému");
    await referenceEnv(panel);
    for (const key of ["min_cell", "default_spec_seed"]) expect(document.querySelector(`[data-setting="${key}"]`)).toBeNull();
    for (const id of ["evidence", "simulation"]) expect(section(id)).toBeNull();
    // Not taken for a group the page does not know either.
    expect(panel.querySelector('[data-reference-category="evidence"], [data-reference-category="simulation"]')).toBeNull();
    for (const key of ["no_invented_certainty", "no_visualisation_mutation"]) expect(section("invariants").querySelector(`[data-setting="${key}"]`)).toBeTruthy();
    expect(within(panel).getByText(/Prahy podpory jsou v Metodice → Práh zobrazení/)).toBeTruthy();
    // The pointer names the card as Metodika draws it, from the same copy, so the two cannot drift
    // apart (review of #933: it named a card Metodika did not have before F15).
    expect(cs.aia.settings.methodology.name.support).toBe("Práh zobrazení");
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
    await waitFor(() => expect(isOpen("AI běh")).toBe(true));
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
    await waitFor(() => expect(isOpen("AI běh")).toBe(true));
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
    // Who changes it is said once, in the tab's head (prototype v51), not again in the section.
    expect(within(panelOf("AI běh").querySelector("[data-tab-chips]") as HTMLElement).getByText("Spravuje nasazení · jen ke čtení")).toBeTruthy();
    expect(within(section("ai")).queryByText("Spravuje nasazení · jen ke čtení")).toBeNull();
    expect(within(section("ai").querySelector("[data-config]") as HTMLElement).getByText("oblast v EU: data zůstávají v EU")).toBeTruthy();
  });

  it("draws the route as tiles and the activities as v99's four columns, each explanation behind its ⓘ (F11)", async () => {
    api();
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork")).toBeTruthy());
    const ai = section("ai");
    const route = ai.querySelector("[data-config]") as HTMLElement;
    // The region by its city beside its code; the classes as letters, each named for a reader.
    expect(within(route).getByText("eu-central-1")).toBeTruthy();
    expect(route.querySelector("[data-region-city]")?.textContent).toBe("Frankfurt");
    const classes = route.querySelector("[data-approved-classes]") as HTMLElement;
    expect([...classes.querySelectorAll("[data-class] [aria-hidden='true']")].map((c) => c.textContent)).toEqual(["C"]);
    expect(within(classes).getByText(/interní materiál bez informací o klientovi/)).toBeTruthy();
    // Činnost, Stav, Přepínač, Model: the reason under the activity, not a column of its own.
    expect(within(ai).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Schopnost", "Stav", "Přepínač (operátor)", "Model"]);
    expect(card("design_agents").querySelector("td:first-child [data-reason]")).toBeTruthy();
    for (const [label, id] of [["Co pohání AI a kdo trasu mění", "ai-route-about"], ["Co znamená zapnuto", "ai-acts-about"]] as const) {
      const button = within(ai).getByRole("button", { name: label });
      expect(button.getAttribute("aria-controls")).toBe(id);
      expect((document.getElementById(id) as HTMLElement).hidden).toBe(true);
      fireEvent.click(button);
      expect((document.getElementById(id) as HTMLElement).hidden).toBe(false);
    }
    // The deploy's smoke test is a link to Stav systému. It makes no model call, and the link says so.
    const smoke = within(ai).getByRole("link", { name: /smoke test/ });
    expect(smoke.getAttribute("href")).toBe("#system");
    expect(smoke.getAttribute("title")).toMatch(/Model nevolá/);
    // London and Zurich are named eu- by AWS but are not in the EU (review of #961).
    expect(within(route).getByText("oblast v EU: data zůstávají v EU")).toBeTruthy();
  });

  it("reads London and Zurich as outside the EU, though AWS names them eu- (review of #961)", async () => {
    for (const [region, city] of [["eu-west-2", "Londýn"], ["eu-central-2", "Curych"]] as const) {
      api({ "GET /config": () => CONFIG({ region }) });
      render(<ControlPanel />);
      await waitFor(() => expect(card("respondent_fieldwork")).toBeTruthy());
      const route = section("ai").querySelector("[data-config]") as HTMLElement;
      await waitFor(() => expect(route.querySelector("[data-region-city]")?.textContent).toBe(city));
      expect(within(route).getByText("oblast mimo EU")).toBeTruthy();
      expect(within(route).queryByText("oblast v EU: data zůstávají v EU")).toBeNull();
      cleanup();
    }
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
    fireEvent.click(techSwitch());
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
    // No count of what is on or off: every switch is unknown, never "0 zapnuto" (review of #961).
    expect(ai.querySelector('[data-count="on"], [data-count="off"]')).toBeNull();
    expect([...ai.querySelectorAll("[data-count]")].map((c) => c.textContent)).not.toContainEqual(expect.stringMatching(/^0 /));
    expect(ai.querySelector('[data-count="unknown"]')?.textContent).toBe("zapnuto: nezjištěno");
    expect(screen.getByText("Vnímání značky")).toBeTruthy();
    cleanup();

    // A /config without the runtime display is the same: nothing to read a state from,
    // said once.
    api({ "GET /config": () => ({ apiBase: "", build: { sha: null } }) });
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork").getAttribute("data-state")).toBe("unknown"));
    await waitFor(() => expect(isOpen("AI běh")).toBe(true));
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
    fireEvent.click(techSwitch());
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

  it("says when each activity last answered, from the ledger, for an administrator: a fact about the past, never 'works'", async () => {
    const at = new Date(Date.now() - 3 * 3_600_000).toISOString();
    api({ "GET /api/v1/settings/ai-activity": () => ({ activities: [
      { key: "respondent_fieldwork", last_answered: { at, model: "eu.anthropic.claude-sonnet", build: "0123456789abcdef" } },
      { key: "design_agents", last_answered: null },
    ] }) });
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork").querySelector('[data-answered="at"]')).toBeTruthy());
    const line = card("respondent_fieldwork").querySelector('[data-answered="at"]') as HTMLElement;
    expect(line.textContent).toBe("Naposledy odpověděl před 3 h · model eu.anthropic.claude-sonnet · build 0123456");
    expect(line.querySelector("time")?.getAttribute("dateTime")).toBe(at);
    // None recorded is said as such: neither working nor broken.
    expect(card("design_agents").querySelector('[data-answered="none"]')?.textContent).toBe("Zatím žádné zaznamenané odpovězené volání.");
    expect(card("design_agents").getAttribute("data-state")).not.toBe("working");
    expect(section("ai").textContent).not.toMatch(OVERCLAIM);
    expect(called("GET", "/api/v1/settings/ai-activity")).toHaveLength(1);
  });

  it("says the last answers could not be read, and claims none, when the read fails", async () => {
    api({ "GET /api/v1/settings/ai-activity": () => new Response('{"code":"internal","message":"Boom"}', { status: 500 }) });
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork").querySelector('[data-answered="unread"]')?.textContent).toBe("Poslední odpověď se nepodařilo načíst."));
    expect(document.querySelector('[data-answered="at"]')).toBeNull();
  });

  it("asks a member nothing of the last answers and shows none", async () => {
    api({}, false);
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork")).toBeTruthy());
    await new Promise((r) => setTimeout(r, 30));
    expect(called("GET", "/api/v1/settings/ai-activity")).toHaveLength(0);
    expect(document.querySelector("[data-answered]")).toBeNull();
  });

  it("a member reads what powers AIA too, without the deployment group", async () => {
    api({}, false);
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork")).toBeTruthy());
    expect(section("deployment")).toBeNull();
    expect(section("ai")).toBeTruthy();
  });

  it("on the Settings page, the top bar is the breadcrumb, Organizace <name> / Nastavení › <sekce>, and each tab's h1 the one heading", async () => {
    api({ "GET /api/v1/workspace/me": () => ({ user_id: "USR-1", email: "owner@example.test", organization_role: "OWNER", may_administer: true, methodologist: false, organization_name: "Výzkumná agentura Delta" }) });
    render(<SettingsPage />);
    const crumbs = await screen.findByRole("navigation", { name: BREADCRUMBS });
    await waitFor(() => expect(within(crumbs).getByText("Výzkumná agentura Delta")).toBeTruthy());
    // "Nastavení › <sekce>" is the section menu's button, the trail's last step and its current
    // page (prototype v54); the organization is a step on the way, not the page.
    const menu = within(crumbs).getByRole("button", { name: /^Nastavení › AI běh/ });
    expect(menu.getAttribute("aria-haspopup")).toBe("dialog");
    expect(menu.getAttribute("aria-current")).toBe("page");
    expect(crumbs.querySelectorAll("[aria-current]")).toHaveLength(1);
    expect(within(crumbs).getAllByRole("listitem")).toHaveLength(2);
    await sectionsDrawn();
    expect(screen.getAllByRole("heading", { level: 1 }).filter((h) => !h.closest("[hidden]")).map((h) => h.textContent)).toEqual(["AI běh"]);
  });

  it("on the Settings page, who you are is read once and passed to the panel", async () => {
    api({ "GET /api/v1/workspace/me": () => ({ user_id: "USR-1", email: "owner@example.test", organization_role: "OWNER", may_administer: true, methodologist: true }) });
    render(<SettingsPage />);
    await sectionsDrawn();
    await waitFor(() => expect(within(panelOf("Metodika").querySelector("[data-tab-chips]") as HTMLElement).getByText("Vy: Metodik · můžete upravovat")).toBeTruthy());
    expect(called("GET", "/api/v1/workspace/me")).toHaveLength(1);
  });

  it("on the Settings page, your own Metodik mark changed in Přístup changes the Metodika head at once (review of #870)", async () => {
    let marked = false;
    api({
      "GET /api/v1/workspace/me": () => ({ user_id: "USR-1", email: "owner@example.test", organization_role: "OWNER", may_administer: true, methodologist: marked }),
      "GET /api/v1/members": () => [{ user_id: "USR-1", email: "owner@example.test", display_name: "Petr", is_active: true, organization_role: "OWNER", methodologist: marked }],
      "PUT /api/v1/members/USR-1/methodologist": (body) => { marked = (body as { methodologist: boolean }).methodologist; return { user_id: "USR-1", email: "owner@example.test", display_name: "Petr", is_active: true, organization_role: "OWNER", methodologist: marked }; },
    });
    render(<SettingsPage />);
    const head = () => panelOf("Metodika").querySelector("[data-tab-chips]") as HTMLElement;
    await waitFor(() => expect(within(head()).getByText("Upravuje jen Metodik")).toBeTruthy());
    await openSection("Přístup a schvalování");
    fireEvent.click(await within(panelOf("Přístup a schvalování")).findByRole("switch", { name: "Štítek Metodik: owner@example.test" }));
    await waitFor(() => expect(within(head()).getByText("Vy: Metodik · můžete upravovat")).toBeTruthy());
  });

  it("keeps one h1 while the settings load and after a failed read", async () => {
    api({ "GET /api/v1/settings": () => new Response('{"code":"internal","message":"Neznámá chyba."}', { status: 500 }) });
    render(<SettingsPage />);
    expect(screen.getAllByRole("heading", { level: 1 }).map((h) => h.textContent)).toEqual(["Nastavení"]);
    await screen.findByRole("alert");
    expect(screen.getAllByRole("heading", { level: 1 }).map((h) => h.textContent)).toEqual(["Nastavení"]);
  });

  it("on the Settings page, a name the API did not send is left out of the breadcrumb, never guessed", async () => {
    api();
    render(<SettingsPage />);
    await sectionsDrawn();
    const crumbs = screen.getByRole("navigation", { name: BREADCRUMBS });
    expect(within(crumbs).getAllByRole("listitem")).toHaveLength(1);
    expect(crumbs.textContent).not.toContain("Organizace");
    expect(within(crumbs).getByRole("button", { name: /^Nastavení › / })).toBeTruthy();
  });

  it("on the Settings page, AI is one section, and the separate Bedrock card is gone", async () => {
    api();
    render(<SettingsPage />);
    await waitFor(() => expect(isOpen("AI běh")).toBe(true));
    // One section, AI běh, as two flat cards under its head (prototype v99, F11): no group card around them.
    const ai = panelOf("AI běh");
    expect(within(ai).getByRole("heading", { level: 1, name: "AI běh" })).toBeTruthy();
    expect((await within(ai).findAllByRole("heading", { level: 2 })).map((h) => h.textContent)).toEqual(["Trasa modelu", "Činnosti"]);
    expect(screen.queryByRole("heading", { name: "AI v AIA" })).toBeNull();
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

const BREADCRUMBS = "Kde jste";
// A section is its address (#deep_research), chosen in the top bar's menu (prototype v54); the
// panel follows the address, so a test opens one the way a link or the menu does.
const SECTION_IDS: Record<string, string> = {
  "Metodika": "methodology", "Systémové prompty": "prompts", "Deep Research": "deep_research", "AI běh": "ai",
  "Přístup a schvalování": "access", "Studie a rozpočty": "studies", "Audit": "audit", "Stav systému": "system",
  "Správa dat": "data",
};
const panelOf = (name: string) => document.getElementById(`panel-${SECTION_IDS[name]}`) as HTMLElement;
const isOpen = (name: string) => !!panelOf(name) && !panelOf(name).hidden;
const sectionsDrawn = () => waitFor(() => expect(document.querySelector("[data-section]")).toBeTruthy());
async function openSection(name: string) {
  await sectionsDrawn();
  // As the section menu does: the address replaced, its history state kept, the page told.
  act(() => {
    window.history.replaceState(window.history.state, "", `#${SECTION_IDS[name]}`);
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
  await waitFor(() => expect(isOpen(name)).toBe(true));
}
// The page's one technical switch, at the end of the open section's head.
const techSwitch = () => within(document.querySelector("section[data-section]:not([hidden]) [data-technical-switch]") as HTMLElement).getByRole("switch", { name: "Technické údaje" });

describe("the settings tabs", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/app/settings");
  });

  it("draws all nine sections, Reference folded into Stav systému (F17), no tab list of its own (prototype v54), and opens on methodology", async () => {
    api();
    render(<ControlPanel />);
    await sectionsDrawn();
    expect(screen.queryByRole("tablist", { name: "Oddíly nastavení" })).toBeNull();
    expect([...document.querySelectorAll("section[data-section]")].map((x) => x.getAttribute("data-section"))).toEqual([
      "methodology", "prompts", "deep_research", "ai", "access", "studies", "audit", "system", "data",
    ]);
    expect(isOpen("Metodika")).toBe(true);
    for (const other of ["Systémové prompty", "Deep Research", "AI běh", "Přístup a schvalování", "Studie a rozpočty", "Audit", "Stav systému", "Správa dat"]) {
      expect(isOpen(other)).toBe(false);
    }
    // Each section is named by its own h1.
    // The section is named by its title, which its hero (F18) draws as the page's one h1.
    expect(panelOf("Metodika").getAttribute("aria-label")).toBe("Metodika");
    expect(within(panelOf("Metodika")).getByRole("heading", { level: 1 }).textContent).toBe("Metodika");
  });

  it("opens Stav systému and Správa dat as their own tabs, saying plainly what AIA does not have yet", async () => {
    // Their routes not deployed: a 404 each.
    const none = () => new Response('{"code":"http_404","message":"Not Found"}', { status: 404 });
    api({ "GET /api/v1/settings/system-status": none, "GET /api/v1/settings/error-tracking": none, "GET /api/v1/settings/kept-records": none });
    render(<ControlPanel />);
    await sectionsDrawn();
    // Not read until their tab is first opened: opening Settings fires no GlitchTip read (review of #854).
    await screen.findByText("Prostředí");
    for (const route of ["/api/v1/settings/system-status", "/api/v1/settings/error-tracking", "/api/v1/settings/kept-records"]) expect(called("GET", route)).toEqual([]);
    await openSection("Stav systému");
    await waitFor(() => expect(called("GET", "/api/v1/settings/error-tracking")).toHaveLength(1));
    expect(called("GET", "/api/v1/settings/kept-records")).toEqual([]);
    expect(panelOf("Stav systému").hidden).toBe(false);
    expect(within(panelOf("Stav systému")).getByRole("heading", { name: "Připravenost po nasazení" })).toBeTruthy();
    expect(within(panelOf("Stav systému")).getByRole("heading", { name: "Hlášení chyb" })).toBeTruthy();
    expect((await within(panelOf("Stav systému")).findAllByText("V AIA zatím není")).length).toBe(2);
    await openSection("Správa dat");
    expect(within(panelOf("Správa dat")).getByRole("heading", { name: "Smazat klienta" })).toBeTruthy();
    expect(within(panelOf("Správa dat")).getByRole("heading", { name: "Uchovávané záznamy" })).toBeTruthy();
    expect(await within(panelOf("Správa dat")).findByText("V AIA zatím není")).toBeTruthy();
    expect(window.location.hash).toBe("#data");
  });

  it("puts each group where its tab says, and the read-only material in Stav systému", async () => {
    api();
    render(<ControlPanel />);
    await sectionsDrawn();
    expect(panelOf("AI běh").contains(section("ai"))).toBe(true);
    // Přístup's three flat cards (F9), in no group card of their own.
    for (const id of ["members", "self-approval", "clients"]) expect(panelOf("Přístup a schvalování").contains(section(id))).toBe(true);
    expect(section("approvals")).toBeNull();
    expect(section("members").parentElement?.closest("section[id^='set-']")).toBeNull();
    // The role matrix is reference material: drawn only with technical details on.
    expect(section("roles")).toBeNull();
    fireEvent.click(techSwitch());
    expect(panelOf("Přístup a schvalování").contains(section("roles"))).toBe(true);
    expect(panelOf("Studie a rozpočty").contains(section("studies"))).toBe(true);
    expect(panelOf("Audit").contains(section("audit"))).toBe(true);
    const system = panelOf("Stav systému");
    for (const id of ["deployment", "invariants"]) expect(system.contains(section(id))).toBe(true);
    // A group the page has no tab for lands in Stav systému rather than disappearing.
    expect(within(system).getByText("something new")).toBeTruthy();
    // Under it, after the readiness and the error reporting, which wait for the section's first visit.
    expect(system.querySelector("[data-system-readiness]")).toBeNull();
    await openSection("Stav systému");
    const order = [...system.querySelectorAll("[data-system-readiness], [data-system-errors], [data-reference-filters]")].map((n) => n.getAttribute("data-system-readiness") !== null ? "readiness" : n.getAttribute("data-system-errors") !== null ? "errors" : "values");
    expect(order).toEqual(["readiness", "errors", "values"]);
  });

  it("heads each tab as the prototype does: a serif h1, one paragraph, who may change it in chips, and no disclosure", async () => {
    api();
    render(<ControlPanel />);
    await sectionsDrawn();
    await waitFor(() => expect(card("respondent_fieldwork")).toBeTruthy());
    const chips = (name: string) => [...(panelOf(name).querySelector("[data-tab-chips]")?.children ?? [])].map((c) => `${c.textContent}|${c.getAttribute("data-chip-tone")}`);
    for (const name of ["Metodika", "Systémové prompty", "Deep Research", "AI běh", "Přístup a schvalování", "Studie a rozpočty", "Audit", "Stav systému", "Správa dat"]) {
      await openSection(name);
      const head = panelOf(name).querySelector("[data-tab-header]") as HTMLElement;
      expect(within(head).getByRole("heading", { level: 1 }).textContent).toBe(name);
      expect(head.querySelectorAll("p")).toHaveLength(1);
      // The page's one switch sits at the end of the open section's head; no "Platí pro · Mění" line.
      expect(within(head).getAllByRole("switch")).toHaveLength(1);
      expect(head.querySelector("[data-tab-facts]")).toBeNull();
      if (name !== "Metodika") expect(panelOf(name).querySelectorAll("details, summary")).toHaveLength(0);
    }
    expect(techSwitch()).toBeTruthy();
    expect(within(panelOf("Studie a rozpočty").querySelector("[data-tab-header]") as HTMLElement).getByText(/Rozpočty studií a útrata/)).toBeTruthy();
    // An owner, without the Metodik mark (the fake's /workspace/me sends none).
    expect(chips("Metodika")).toEqual(["Čte každý člen|plain", "Upravuje jen Metodik|plain"]);
    expect(chips("Systémové prompty")).toEqual(["Vy: správce · můžete upravovat|you"]);
    expect(chips("Deep Research")).toEqual(["Čte každý člen|plain", "Vy: navrhujete a schvalujete|you"]);
    expect(chips("AI běh")).toEqual(["Spravuje nasazení · jen ke čtení|deployment"]);
    expect(chips("Přístup a schvalování")).toEqual(["Vy: spravujete členy|you"]);
    expect(chips("Studie a rozpočty")).toEqual(["Upravujete|you"]);
    // The pencil is decoration: a screen reader hears "Upravujete" alone.
    // The pencil is Phosphor's, never a typed glyph (no emoji or dingbats as UI).
    expect(panelOf("Studie a rozpočty").querySelector("[data-tab-chips] [aria-hidden='true'] svg")).not.toBeNull();
    expect(chips("Stav systému")).toEqual(["Spravuje nasazení|deployment"]);
    expect(chips("Správa dat")).toEqual(["Jen vlastník nebo správce|plain"]);
    expect(chips("Audit")).toEqual([]);
    // Stav systému names its technical values' groups up front as categories with their counts.
    const cats = panelOf("Stav systému").querySelector("[data-reference-categories]") as HTMLElement;
    expect([...cats.querySelectorAll("[data-reference-category]")].map((b) => b.getAttribute("data-reference-category"))).toContain("invariants");
  });

  it("says in the heads what a member may not change, and names the Metodik mark only for its holder", async () => {
    api({ "GET /api/v1/workspace/me": () => ({ user_id: "USR-1", email: "m@example.test", organization_role: "MEMBER", may_administer: false, methodologist: true }) }, false);
    render(<ControlPanel />);
    await sectionsDrawn();
    const chips = (name: string) => [...(panelOf(name).querySelector("[data-tab-chips]")?.children ?? [])].map((c) => c.textContent);
    await waitFor(() => expect(chips("Metodika")).toEqual(["Čte každý člen", "Vy: Metodik · můžete upravovat"]));
    expect(chips("Systémové prompty")).toEqual(["Upravuje vlastník nebo správce"]);
    // Who decides is said to a member too, as Systémové prompty and Přístup do.
    expect(chips("Deep Research")).toEqual(["Čte každý člen", "Navrhuje a schvaluje vlastník nebo správce"]);
    expect(chips("Přístup a schvalování")).toEqual(["Členy spravuje vlastník nebo správce"]);
  });

  it("claims no Metodik mark when who you are could not be read", async () => {
    api({ "GET /api/v1/workspace/me": () => new Response('{"code":"internal","message":"x"}', { status: 500 }) });
    render(<ControlPanel />);
    await sectionsDrawn();
    const head = panelOf("Metodika").querySelector("[data-tab-chips]") as HTMLElement;
    expect(within(head).getByText("Upravuje jen Metodik")).toBeTruthy();
    expect(within(head).queryByText(/Vy: Metodik/)).toBeNull();
  });

  it("draws Settings' one-of-a-few choices as the prototype's segmented bar (fidelity F3)", async () => {
    api();
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    const access = panelOf("Přístup a schvalování");
    expect((await within(access).findByRole("radiogroup", { name: "Samoschválení organizace" })).getAttribute("data-look")).toBe("segmented");
    await openSection("Audit");
    expect(within(panelOf("Audit")).getByRole("radiogroup", { name: "Období" }).getAttribute("data-look")).toBe("segmented");
    await openSection("Stav systému");
    expect(within(panelOf("Stav systému")).getByRole("radiogroup", { name: "Kdo mění" }).getAttribute("data-look")).toBe("segmented");
  });

  it("reads the technical values as tables by category, filters by category and by who changes a value, and says what each means", async () => {
    api();
    render(<ControlPanel />);
    await openSection("Stav systému");
    const reference = panelOf("Stav systému").querySelector("[data-reference-filters]")?.parentElement as HTMLElement;
    const env = await referenceEnv(reference);
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
    expect(within(reference.querySelector("[data-reference-filters]") as HTMLElement).getByRole("status").textContent).toMatch(/^Zobrazeno \d+ z \d+ hodnot$/);
  });

  it("lists each technical value once, invariants under Invarianty only, and counts each chip under the filters", async () => {
    // An invariant in a reference group (as residency, workflow and evidence carry them).
    const doc = DOC();
    doc.groups = doc.groups.map((g) => (g.key === "deployment" ? { ...g, items: [...g.items, { key: "eu_residency", value: true, control: "INVARIANT" as const, source: "ADR 0008", unit: null }] } : g));
    api({ "GET /api/v1/settings": () => doc });
    render(<ControlPanel />);
    await openSection("Stav systému");
    const reference = panelOf("Stav systému").querySelector("[data-reference-filters]")?.parentElement as HTMLElement;
    await referenceEnv(reference);
    const keys = [...reference.querySelectorAll("tr[data-setting]")].map((r) => r.getAttribute("data-setting"));
    expect(keys.length).toBe(new Set(keys).size);
    const total = Number(/z (\d+) hodnot/.exec(within(reference.querySelector("[data-reference-filters]") as HTMLElement).getByRole("status").textContent ?? "")?.[1]);
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
    await openSection("Přístup a schvalování");
    expect(panelOf("Přístup a schvalování").hidden).toBe(false);
    expect(panelOf("AI běh").hidden).toBe(true);
    fireEvent.click(await within(panelOf("Přístup a schvalování")).findByRole("button", { name: "+ Přidat člena" }));
    const email = () => within(panelOf("Přístup a schvalování")).getByLabelText("E-mail nového člena") as HTMLInputElement;
    fireEvent.change(email(), { target: { value: "rozepsany@example.test" } });
    await openSection("Audit");
    await openSection("Přístup a schvalování");
    // Looking at another tab did not throw away what was typed and not added yet.
    expect(email().value).toBe("rozepsany@example.test");
  });

  it("opens the tab a link names, and records the one you choose", async () => {
    window.history.replaceState(null, "", "/app/settings#audit");
    api();
    render(<ControlPanel />);
    await sectionsDrawn();
    await waitFor(() => expect(isOpen("Audit")).toBe(true));
    await openSection("Studie a rozpočty");
    expect(window.location.hash).toBe("#studies");
    await openSection("Audit");
    expect(window.location.hash).toBe("#audit");
  });

  it("follows the address when it changes from outside: the back button, a link to another section", async () => {
    api();
    render(<ControlPanel />);
    await openSection("AI běh");
    act(() => {
      window.history.replaceState(null, "", "/app/settings#deep_research");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    await waitFor(() => expect(isOpen("Deep Research")).toBe(true));
    expect(isOpen("AI běh")).toBe(false);
    // An address naming no section opens on Metodika, as the page does.
    act(() => {
      window.history.replaceState(null, "", "/app/settings#nothing");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    await waitFor(() => expect(isOpen("Metodika")).toBe(true));
  });

  it("does not ask for the prompts until the tab is opened, and never for a member", async () => {
    api();
    render(<ControlPanel />);
    await sectionsDrawn();
    expect(called("GET", "/api/v1/system-prompts")).toEqual([]);
    await openSection("Systémové prompty");
    await waitFor(() => expect(called("GET", "/api/v1/system-prompts")).toHaveLength(1));
    cleanup();

    api({}, false);
    render(<ControlPanel />);
    await openSection("Systémové prompty");
    expect(await screen.findByText(/Systémové prompty vidí a upravuje jen vlastník nebo správce/)).toBeTruthy();
    expect(called("GET", "/api/v1/system-prompts")).toEqual([]);
  });

  it("asks for the Deep Research settings only when their tab is opened, for any member", async () => {
    technicalOn();
    api({}, false);
    render(<ControlPanel />);
    await sectionsDrawn();
    expect(called("GET", "/api/v1/deep-research/settings")).toEqual([]);
    await openSection("Deep Research");
    // A member reads them: the API, not the page, decides who may change one.
    await waitFor(() => expect(called("GET", "/api/v1/deep-research/settings")).toHaveLength(1));
    expect(panelOf("Deep Research").contains(section("deep_research"))).toBe(true);
    // The settings document's own group says how the values are set and what no value changes.
    // It is drawn on this tab, not again in Stav systému (whose invariants list holds every rail).
    const group = within(panelOf("Deep Research"));
    expect(group.getByText(/Jen veřejné zdroje: robots.txt platí/)).toBeTruthy();
    expect(group.getByText(/Pravidla Deep Research/)).toBeTruthy();
    expect(within(panelOf("Stav systému")).queryByText(/Pravidla Deep Research/)).toBeNull();
  });
});


it("follows changed settings hashes and preserves the framework's navigation state", async () => {
  api(); render(<ControlPanel />); await sectionsDrawn();
  window.history.replaceState({ __NA: true, marker: "preserve" }, "", "/app/settings");
  await openSection("Audit"); expect(window.history.state).toMatchObject({ __NA: true, marker: "preserve" });
  // An old link to Reference, folded into Stav systému (F17), opens Stav systému.
  window.history.replaceState(window.history.state, "", "/app/settings#reference");
  fireEvent(window, new HashChangeEvent("hashchange"));
  await waitFor(() => expect(isOpen("Stav systému")).toBe(true));
});

 it("explains what a setting does, keeps its technical source optional and formats money for a reader", async () => {
    api({ "GET /api/v1/studies/STU-1": () => ({ ...STUDY("STU-1", "Vnímání značky"), budget_usd: 20, spent_usd: 12.714524700000009, remaining_usd: 7.285475299999991 }) });
    render(<ControlPanel />);
    const env = (await screen.findByText("Prostředí")).closest("[data-setting]")!;
    expect(within(env as HTMLElement).getByText(/Rozlišuje vývojové/)).toBeTruthy();
    // No disclosure: the source is a technical detail, shown for the whole page by one switch.
    expect(env.querySelector("details")).toBeNull();
    expect(env.querySelector("[data-technical]")).toBeNull();
    const toggle = techSwitch();
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    fireEvent.click(toggle);
    expect(env.querySelector("[data-technical]")?.textContent).toBeTruthy();
    expect(sessionStorage.getItem("aia.settings.technical")).toBe("1");
    await openSection("Studie a rozpočty");
    expect(await screen.findByText("12,71 USD")).toBeTruthy();
    expect(screen.getByText(/zbývá 7,29 USD/)).toBeTruthy();
    expect(screen.queryByText("12.714524700000009")).toBeNull();
  });

describe("each page's hero (F18)", () => {
  beforeEach(() => { window.history.replaceState(null, "", "/app/settings"); });
  const figures = (name: string) => [...panelOf(name).querySelectorAll("[data-hero] dl > div")].map((d) => `${d.querySelector("dt")?.textContent}=${d.querySelector("dd")?.textContent}`);

  it("heads Přístup with its group, title, lede and the figures its reads give", async () => {
    api({
      "GET /api/v1/members": () => [
        { user_id: "USR-1", email: "owner@example.test", display_name: "", is_active: true, organization_role: "OWNER", methodologist: true },
        { user_id: "USR-2", email: "b@example.test", display_name: "", is_active: true, organization_role: "RESEARCHER", methodologist: false, deactivated_at: "2026-10-20T10:00:00Z" },
      ],
      "GET /api/v1/self-approval": () => ({ organization: true, clients: [], studies: [] }),
    });
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    await waitFor(() => expect(figures("Přístup a schvalování")).toEqual([
      "Aktivní členové=1", "Deaktivovaní=1", "Metodik=1", "Klienti=1", "Samoschválení v organizaci=povoleno",
    ]));
    const hero = panelOf("Přístup a schvalování").querySelector("[data-hero]") as HTMLElement;
    expect(hero.querySelector("[data-hero-eyebrow]")?.textContent).toBe("Tým a peníze");
    expect(within(hero).getByRole("heading", { level: 1 }).textContent).toBe("Přístup a schvalování");
    // The head keeps its one lede, its chips and the page's one switch.
    expect(hero.querySelectorAll("[data-tab-lede]")).toHaveLength(1);
    expect(hero.querySelector("[data-tab-chips]")).toBeTruthy();
  });

  it("says unknown for a figure whose read failed, never 0, and draws no figures where none are wired", async () => {
    api({ "GET /api/v1/clients": () => new Response('{"code":"http_500","message":"x"}', { status: 500 }) });
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
    await waitFor(() => expect(figures("Přístup a schvalování")).toContain("Klienti=neznámé"));
    expect(panelOf("Přístup a schvalování").querySelector('[data-hero-figure="unknown"]')).toBeTruthy();
    // Metodika's figures are its own panel's, not wired yet: no row, nothing claimed.
    expect(panelOf("Metodika").querySelector("[data-hero] dl")).toBeNull();
  });

  const SMOKE = () => ({ latest: { run_id: "r1", build_sha: "abc", ran_at: new Date().toISOString(), all_ok: false, failed: 1, not_runnable: 0, checks: [
    { check: "Sign-in", status: "ok" }, { check: "Bedrock", status: "FAIL" },
  ] } });
  const WEB_BUILD = () => ({ ...CONFIG(), build: { sha: "a1c4e9f2b7d3" } });

  it("heads Stav systému with the figures its own panel hands up", async () => {
    api({ "GET /api/v1/settings/system-status": SMOKE, "GET /config": WEB_BUILD });
    render(<ControlPanel />);
    await openSection("Stav systému");
    await waitFor(() => expect(figures("Stav systému")).toEqual(["Připraveno=1 / 2", "Prostředí=develop", "Sestava webu=a1c4e9f"]));
  });

  it("hands Stav systému's figures up only once the Environment card has read, never unknown above Načítám", async () => {
    // Review of #1009 (P2): the smoke run answered, /api/v1/health not yet.
    let release: (v: unknown) => void = () => {};
    const health = new Promise((resolve) => { release = resolve; });
    api({ "GET /api/v1/settings/system-status": SMOKE, "GET /config": WEB_BUILD, "GET /api/v1/health": () => health });
    render(<ControlPanel />);
    await openSection("Stav systému");
    const panel = panelOf("Stav systému");
    await waitFor(() => expect(called("GET", "/api/v1/settings/system-status")).toHaveLength(1));
    await waitFor(() => expect(panel.querySelector("[data-copy-diagnostics]")).toBeTruthy());
    expect(within(panel.querySelector("[data-system-environment]") as HTMLElement).getByText("Načítám…")).toBeTruthy();
    expect(panel.querySelector("[data-hero] dl")).toBeNull();
    await act(async () => { release({ status: "ok", build: { sha: null } }); });
    await waitFor(() => expect(figures("Stav systému")).toEqual(["Připraveno=1 / 2", "Prostředí=develop", "Sestava webu=a1c4e9f"]));
  });

  it("says Připraveno unknown when no smoke run is stored, never 0", async () => {
    api({ "GET /api/v1/settings/system-status": () => new Response('{"code":"not_found","message":"No such resource."}', { status: 404 }), "GET /config": WEB_BUILD });
    render(<ControlPanel />);
    await openSection("Stav systému");
    await waitFor(() => expect(figures("Stav systému")).toEqual(["Připraveno=neznámé", "Prostředí=develop", "Sestava webu=a1c4e9f"]));
    expect(panelOf("Stav systému").querySelector('[data-hero-figure="unknown"]')).toBeTruthy();
  });

  it("keeps Stav systému's figures on its own page: another page draws none of them", async () => {
    api({ "GET /api/v1/settings/system-status": SMOKE, "GET /config": WEB_BUILD });
    render(<ControlPanel />);
    await openSection("Stav systému");
    await waitFor(() => expect(figures("Stav systému")[0]).toBe("Připraveno=1 / 2"));
    await openSection("Metodika");
    expect(panelOf("Metodika").querySelector("[data-hero] dl")).toBeNull();
    expect(panelOf("Správa dat").querySelector("[data-hero] dl")).toBeNull();
  });

  it("draws no Stav systému figures for someone who is not an administrator", async () => {
    api({ "GET /api/v1/settings/system-status": SMOKE }, false);
    render(<ControlPanel />);
    await openSection("Stav systému");
    expect(await within(panelOf("Stav systému")).findByText("Stav systému vidí vlastník nebo správce.")).toBeTruthy();
    expect(panelOf("Stav systému").querySelector("[data-hero] dl")).toBeNull();
    expect(called("GET", "/api/v1/settings/system-status")).toHaveLength(0);
  });

  it("counts the audit's week only when the page read it whole", async () => {
    // The newest event is stamped now, not a minute ago: "a minute ago" is yesterday just after
    // Prague's midnight, and the page counts today in Prague's day (review of #983).
    const now = Date.now();
    api({ "GET /api/v1/access-audit": () => [
      { event_id: 2, action: "MEMBER_ADDED", client_id: null, study_id: null, subject_user_id: null, actor_id: "USR-1", role: null, reason: "", payload: {}, created_at: new Date(now).toISOString() },
      { event_id: 1, action: "MEMBER_ADDED", client_id: null, study_id: null, subject_user_id: null, actor_id: "USR-2", role: null, reason: "", payload: {}, created_at: new Date(now - 30 * 86_400_000).toISOString() },
    ] });
    render(<ControlPanel />);
    await openSection("Audit");
    await waitFor(() => expect(figures("Audit").slice(0, 3)).toEqual(["Události · 7 dní=1", "Dnes=1", "Kdo měnil=1"]));
  });

  it("counts Dnes from the panel's newest read, so a reload past Prague's midnight agrees with the audit table", async () => {
    // Settings left open over Prague's midnight (CET, UTC+1): a change reloads the panel, the mounted
    // page stays, and its hero must count the new day as the table does (Codex on #983). Only the
    // clock is faked; the session is stamped on it so it has not expired.
    vi.useFakeTimers({ toFake: ["Date"] });
    try {
      vi.setSystemTime(new Date("2026-10-26T22:30:00Z")); // 23:30 in Prague, 26 October
      sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3 * 86_400_000, email: "owner@example.test", subject: "s" }));
      const entry = (event_id: number, created_at: string) => ({ event_id, action: "MEMBER_ADDED", client_id: null, study_id: null, subject_user_id: null, actor_id: "USR-1", role: null, reason: "", payload: {}, created_at });
      const yesterday = [entry(2, "2026-10-26T22:20:00Z"), entry(1, "2026-10-26T22:10:00Z")];
      let reads = 0;
      api({
        "GET /api/v1/members": () => [
          { user_id: "USR-1", email: "owner@example.test", display_name: "", is_active: true, organization_role: "OWNER" },
          { user_id: "USR-3", email: "second@example.test", display_name: "Druhý", is_active: true, organization_role: "OWNER" },
        ],
        "POST /api/v1/members": (b) => ({ user_id: "USR-3", display_name: "Druhý", is_active: true, ...(b as object), organization_role: "ADMIN" }),
        // The second read is after midnight: one event of the new day beside the two of the old.
        "GET /api/v1/access-audit": () => (++reads === 1 ? yesterday : [entry(3, "2026-10-26T23:05:00Z"), ...yesterday]),
      });
      render(<ControlPanel />);
      await openSection("Audit");
      await waitFor(() => expect(figures("Audit")).toContain("Dnes=2"));
      vi.setSystemTime(new Date("2026-10-26T23:10:00Z")); // 00:10 in Prague, 27 October
      await openSection("Přístup a schvalování");
      const roles = await screen.findByRole("radiogroup", { name: "Role: second@example.test" });
      fireEvent.click(within(roles).getByRole("radio", { name: "správce" }));
      await waitFor(() => expect(called("GET", "/api/v1/access-audit")).toHaveLength(2));
      await openSection("Audit");
      const audit = panelOf("Audit");
      await waitFor(() => expect(within(audit).getByText(/Zobrazeno \d+ z 3 záznamů/)).toBeTruthy());
      fireEvent.click(within(audit).getByRole("radio", { name: "Dnes" }));
      expect(within(audit).getByText("Zobrazeno 1 z 3 záznamů")).toBeTruthy();
      expect(figures("Audit")).toContain("Dnes=1");
    } finally {
      vi.useRealTimers();
    }
  });
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
    await openSection("Přístup a schvalování");
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
    await openSection("Přístup a schvalování");
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
    await openSection("Přístup a schvalování");
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
    await openSection("Přístup a schvalování");
    const mine = await screen.findByRole("radiogroup", { name: "Role: owner@example.test" });
    fireEvent.click(within(mine).getByRole("radio", { name: "správce" }));
    await waitFor(() => expect(called("POST", "/api/v1/members")).toHaveLength(1));
    expect(await screen.findByText(/roli vlastníka vám může vrátit jiný vlastník/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Vrátit/ })).toBeNull();
  });

  it("refuses an address that is not an e-mail at the field, and sends nothing", async () => {
    api();
    render(<ControlPanel />);
    await openSection("Přístup a schvalování");
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
    await openSection("Audit");
    const audit = panelOf("Audit");
    expect(await within(audit).findByText("Návrat metodiky na verzi z kódu", { selector: "strong" })).toBeTruthy();
    expect(within(audit).getByText("Návrat pravidla rešerše na výchozí", { selector: "strong" })).toBeTruthy();
    expect(audit.textContent).not.toMatch(/METHODOLOGY_RESET|methodology reset/);
  });

  it("puts the spend per researcher on Studie a rozpočty, read from its own route", async () => {
    api(); render(<ControlPanel />);
    await openSection("Studie a rozpočty");
    const panel = panelOf("Studie a rozpočty");
    expect(within(panel).getByRole("heading", { name: "Útrata podle výzkumníka" })).toBeTruthy();
    expect(await within(panel).findByText("Za toto období nikdo nic neutratil.")).toBeTruthy();
    expect(called("GET", "/api/v1/settings/researcher-spend")).toHaveLength(1);
  });

  it("filters studies without unmounting their budget drafts and searches the readable audit", async () => {
    api(); render(<ControlPanel />);
    await openSection("Studie a rozpočty");
    const study = document.querySelector('[data-study="STU-1"]') as HTMLElement;
    const budget = await within(study).findByRole("spinbutton", { name: "Rozpočet studie Vnímání značky" }) as HTMLInputElement;
    fireEvent.change(budget, { target: { value: "600" } });
    fireEvent.change(screen.getByRole("searchbox", { name: "Hledat studii nebo klienta" }), { target: { value: "Cizí" } });
    expect(study.hidden).toBe(true);
    fireEvent.change(screen.getByRole("searchbox", { name: "Hledat studii nebo klienta" }), { target: { value: "Vnímání" } });
    expect(budget.value).toBe("600");
    expect(study.hidden).toBe(false);
    await openSection("Audit");
    expect(within(panelOf("Audit")).getByText("Záznam přístupu ke klientovi", { selector: "strong" })).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox", { name: "Typ události v historii" }), { target: { value: "CLIENT_GRANT" } });
    expect(within(panelOf("Audit")).getByText("Zobrazeno 1 z 1 záznamů")).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: "Hledat v historii" }), { target: { value: "no-such-event" } });
    expect(screen.getByText("Žádný záznam neodpovídá hledání.")).toBeTruthy();
    expect(called("PUT", "/api/v1/studies/STU-1/budget")).toEqual([]);
  });
});
