// @vitest-environment jsdom
// The settings control panel against a fake AIA API: the signed-in token is what
// reaches the API, every setting says how it is controlled, "not configured" and
// "costs hidden" never read as zero, a change goes through the API and the
// panel re-reads, and a refusal is shown as the API gave it.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ControlPanel } from "./ControlPanel";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace }), usePathname: () => "/app/settings" }));

const item = (key: string, value: unknown, control: string, source: string, unit: string | null = null) => ({ key, value, control, source, unit });

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
      item("default_project_max_api_cost", 10, "CODE", "aia_core.domain.providers:DEFAULT_MAX_API_COST_USD", "USD"),
      item("no_spend_past_budget", true, "INVARIANT", "ARCHITECTURE.md §10"),
    ] },
    { key: "approvals", items: [item("self_approval", null, "API", "PUT /api/v1/self-approval")] },
    { key: "brand_new", items: [item("something_new", 3, "CODE", "aia_core.domain.x:NEW")] },
  ],
  vocabularies: {
    organization_roles: ["OWNER", "ADMIN", "MEMBER"],
    scope_roles: [{ role: "VIEWER", permissions: ["VIEW_STUDY"] }, { role: "LEAD", permissions: ["VIEW_STUDY", "MANAGE_STUDY_BUDGET"] }],
    permissions: ["VIEW_STUDY", "MANAGE_STUDY_BUDGET"],
    client_statuses: ["ACTIVE", "DORMANT", "ARCHIVED"],
    study_statuses: ["DRAFT", "ACTIVE"],
    providers: [{ id: "anthropic", label: "Claude API", paid: true }],
    provider_policies: ["CLAUDE_API_ONLY"],
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
        "GET /config": () => ({ cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", apiBase: "", build: { sha: null } }),
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

beforeEach(() => {
  replace.mockReset();
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "owner@example.test", subject: "s" }));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
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
