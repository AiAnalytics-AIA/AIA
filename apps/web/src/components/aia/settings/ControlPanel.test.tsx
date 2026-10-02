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
    scope_roles: [{ role: "VIEWER", permissions: ["VIEW_STUDY"] }, { role: "LEAD", permissions: ["VIEW_STUDY", "MANAGE_STUDY_BUDGET"] }],
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

  it("still renders a group the page has no panel for", async () => {
    api();
    render(<ControlPanel />);
    const row = (await screen.findByText("aia.settings.panel.items.something_new")).closest("[data-setting]") as HTMLElement;
    expect(within(row).getByText("3")).toBeTruthy();
  });

  it("shows hidden costs as hidden, never as a zero budget", async () => {
    api();
    render(<ControlPanel />);
    const hidden = (await screen.findByText("Cizí studie")).closest("[data-study]") as HTMLElement;
    expect(within(hidden).getByText(/náklady nevidíte/)).toBeTruthy();
    const visible = screen.getByText("Vnímání značky").closest("[data-study]") as HTMLElement;
    expect(within(visible).getAllByText("500").length).toBeGreaterThan(0);
  });

  it("changes the organization's self-approval through the API, then re-reads", async () => {
    api();
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Přístup a schvalování" }));
    const org = (await screen.findByText("Organizace")).closest("[data-level]") as HTMLElement;
    fireEvent.change(within(org).getByLabelText("Změnit na…"), { target: { value: "allow" } });
    fireEvent.click(within(org).getByRole("button", { name: "Uložit" }));
    await waitFor(() => expect(called("PUT", "/api/v1/self-approval")).toHaveLength(1));
    expect(called("PUT", "/api/v1/self-approval")[0].body).toEqual({ allowed: true });
    await waitFor(() => expect(called("GET", "/api/v1/settings")).toHaveLength(2));
  });

  it("shows the API's refusal as given", async () => {
    api({
      "PUT /api/v1/studies/STU-1/budget": () =>
        new Response('{"code":"insufficient_role","message":"Your role on this study does not permit that action."}', { status: 403 }),
    });
    render(<ControlPanel />);
    const study = (await screen.findByText("Vnímání značky")).closest("[data-study]") as HTMLElement;
    fireEvent.change(within(study).getByLabelText("Strop rozpočtu"), { target: { value: "900" } });
    fireEvent.submit(within(study).getByLabelText("Strop rozpočtu").closest("form") as HTMLFormElement);
    expect(await within(study).findByText(/HTTP 403 · insufficient_role: Your role on this study/)).toBeTruthy();
    expect(called("PUT", "/api/v1/studies/STU-1/budget")[0].body).toEqual({ budget_usd: 900 });
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

const card = (key: string) => document.querySelector(`[data-activity="${key}"]`) as HTMLElement;
const section = (id: string) => document.getElementById(`set-${id}`) as HTMLElement;
// Everything the browser asked for besides AIA's API and its own /config: a unit
// route, a provider probe or a test call would show up here.
const elsewhere = () => calls.filter((c) => !c.url.startsWith("/api/v1/") && c.url !== "/config");
// Claims a configuration display must never make. "Neověřeno" (not verified) is
// what it must say instead, so only a positive "ověřeno" counts.
const OVERCLAIM = /připojen|funkční spojení|spojení funguje|(?<!ne)ověřen[oaáý]|healthy|connected|\bverified\b/i;
const LOGIN = /přihlaste se|zadejte (api )?klíč|api klíč se zadává|subscription login|ANTHROPIC_API_KEY/i;

describe("what powers AIA", () => {
  it("fieldwork on and design off: Bedrock, one switched on in configuration, one off by its own switch", async () => {
    api();
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork")).toBeTruthy());
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
    expect(within(design).getByText(/Přepínač AIA_AI_RESEARCH_AGENTS_ENABLED je v tomto nasazení vypnutý\. AI návrh se nespustí/)).toBeTruthy();
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

  it("the runtime off: says which switch and what happens, and never suggests a login", async () => {
    api({ "GET /config": () => CONFIG({ enabled: false, switches: { AIA_AI_RUNTIME_ENABLED: false, AIA_AI_RESEARCH_AGENTS_ENABLED: true } }) });
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork").getAttribute("data-state")).toBe("off"));
    expect(card("design_agents").getAttribute("data-state")).toBe("off");
    const fieldwork = card("respondent_fieldwork");
    expect(within(fieldwork).getByText(/Přepínač AIA_AI_RUNTIME_ENABLED je v tomto nasazení vypnutý\. Běh výzkumu počká u sběru dat \(ai_runtime_unavailable\) a modelu se nic neodešle\./)).toBeTruthy();
    // The design switch being on changes nothing while the runtime is off, and the reason says so.
    expect(within(card("design_agents")).getByText(/AIA_AI_RUNTIME_ENABLED je v tomto nasazení vypnutý/)).toBeTruthy();
    const ai = section("ai");
    expect(within(ai).queryByText("Zapnuto v konfiguraci")).toBeNull();
    expect(within(ai.querySelector("[data-config]") as HTMLElement).getByText("vypnuto")).toBeTruthy();
    expect(ai.textContent).not.toMatch(OVERCLAIM);
    expect(ai.textContent).not.toMatch(LOGIN);
    expect(within(ai).getByText(/Žádné přihlášení ani API klíč neexistuje/)).toBeTruthy();
    expect(elsewhere()).toEqual([]);
  });

  it("a value the worker refuses: invalid, never off or on -- in the design switch it stops fieldwork too", async () => {
    api({ "GET /config": () => CONFIG({ enabled: null, switches: { AIA_AI_RUNTIME_ENABLED: null, AIA_AI_RESEARCH_AGENTS_ENABLED: false } }) });
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork").getAttribute("data-state")).toBe("invalid"));
    expect(within(card("respondent_fieldwork")).getByText(/AIA_AI_RUNTIME_ENABLED má hodnotu, kterou worker odmítne: worker se nespustí/)).toBeTruthy();
    expect(within(section("ai")).queryByText("Vypnuto")).toBeNull();
    expect(within(section("ai")).queryByText("Zapnuto v konfiguraci")).toBeNull();
    cleanup();

    api({ "GET /config": () => CONFIG({ switches: { AIA_AI_RUNTIME_ENABLED: true, AIA_AI_RESEARCH_AGENTS_ENABLED: null } }) });
    render(<ControlPanel />);
    await waitFor(() => expect(card("respondent_fieldwork").getAttribute("data-state")).toBe("invalid"));
    expect(card("design_agents").getAttribute("data-state")).toBe("invalid");
    expect(within(card("respondent_fieldwork")).getByText(/AIA_AI_RESEARCH_AGENTS_ENABLED má hodnotu, kterou worker odmítne/)).toBeTruthy();
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
    const history = await waitFor(() => {
      const found = document.querySelector("[data-history]") as HTMLElement | null;
      if (!found) throw new Error("no history yet");
      return found;
    });
    expect(history.tagName).toBe("DETAILS");
    expect(history.hasAttribute("open")).toBe(false);
    // Each historical id appears, and only inside the collapsed history.
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
    expect(await screen.findByRole("heading", { name: "AI v AIA" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Amazon Bedrock" })).toBeNull();
    // The combined cutover keeps the account card and removes every classic hand-off.
    expect(screen.getByRole("heading", { name: "Účet" })).toBeTruthy();
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

  it("splits the page by what a person came to do, with AI first", async () => {
    api();
    render(<ControlPanel />);
    await screen.findByRole("tablist", { name: "Oddíly nastavení" });
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
      "AI běh", "Systémové prompty", "Přístup a schvalování", "Studie a rozpočty", "Audit", "Reference",
    ]);
    expect(tab("AI běh").getAttribute("aria-selected")).toBe("true");
    expect(panelOf("AI běh").hidden).toBe(false);
    for (const other of ["Systémové prompty", "Přístup a schvalování", "Studie a rozpočty", "Audit", "Reference"]) {
      expect(panelOf(other).hidden).toBe(true);
      expect(tab(other).getAttribute("aria-selected")).toBe("false");
    }
  });

  it("puts each group where its tab says, and the read-only material under Reference", async () => {
    api();
    render(<ControlPanel />);
    await screen.findByRole("tablist");
    expect(panelOf("AI běh").contains(section("ai"))).toBe(true);
    expect(panelOf("Přístup a schvalování").contains(section("approvals"))).toBe(true);
    expect(panelOf("Přístup a schvalování").contains(section("roles"))).toBe(true);
    expect(panelOf("Studie a rozpočty").contains(section("studies"))).toBe(true);
    expect(panelOf("Audit").contains(section("audit"))).toBe(true);
    const reference = panelOf("Reference");
    for (const id of ["deployment", "invariants"]) expect(reference.contains(section(id))).toBe(true);
    // A group the page has no tab for lands in Reference rather than disappearing.
    expect(within(reference).getByText("aia.settings.panel.items.something_new")).toBeTruthy();
  });

  it("shows one panel at a time and keeps the others' state when switching back", async () => {
    api();
    render(<ControlPanel />);
    fireEvent.click(await screen.findByRole("tab", { name: "Přístup a schvalování" }));
    expect(panelOf("Přístup a schvalování").hidden).toBe(false);
    expect(panelOf("AI běh").hidden).toBe(true);
    const choose = () => within(panelOf("Přístup a schvalování")).getAllByLabelText("Změnit na…")[0] as HTMLSelectElement;
    fireEvent.change(choose(), { target: { value: "allow" } });
    fireEvent.click(tab("Audit"));
    fireEvent.click(tab("Přístup a schvalování"));
    // Looking at another tab did not throw away the choice that was not saved yet.
    expect(choose().value).toBe("allow");
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
    fireEvent.keyDown(tab("AI běh"), { key: "ArrowRight" });
    expect(tab("Systémové prompty").getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(tab("Systémové prompty"), { key: "ArrowLeft" });
    fireEvent.keyDown(tab("AI běh"), { key: "ArrowLeft" });
    expect(tab("Reference").getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(tab("Reference"), { key: "Home" });
    expect(tab("AI běh").getAttribute("aria-selected")).toBe("true");
    // Only the selected tab is in the tab order.
    expect(tab("AI běh").tabIndex).toBe(0);
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
});
