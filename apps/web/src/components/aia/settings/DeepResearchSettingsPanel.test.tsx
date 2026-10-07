// @vitest-environment jsdom
// The Deep Research tab against a fake of its route (ADR 0022): what is in force and where
// it comes from, what live still needs, and an administrator proposing, approving and
// withdrawing -- a proposal is not in force until approved. The fake keeps real state and
// refuses as the API does; every refusal is shown as the API gave it.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DrSetting, DrSettingApproval, DrSettingDetail, DrSettingValue, DrSettingVersion } from "@/lib/api";
import { resetConfigCache } from "@/lib/auth";
import { DeepResearchSettingsPanel, showValue } from "./DeepResearchSettingsPanel";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/app/settings" }));

const RETENTION = "retention.snapshots";
const CRAWL = "budgets.allowance.exhaustive.crawl_pages";
const DENYLIST = "extraction.denylist";
const REGISTER = "sources.reputation_register";

const base = (key: string, group: string, type: string, extra: Partial<DrSetting>): DrSetting => ({
  key, group, type, label: `${key} (catalogue)`, unit: "", minimum: null, maximum: null,
  lower_only: false, required_for_live: false, method: false, default: null, default_source: "",
  value: null, origin: "proposed_default", version: null, approved_by: null, approved_at: null,
  version_count: 0, latest_number: null, ...extra,
});
const CATALOGUE: DrSetting[] = [
  base(CRAWL, "budgets", "integer", { unit: "per run", minimum: 0, lower_only: true, method: true, default: 1000, value: 1000 }),
  base(RETENTION, "retention", "days", { unit: "days", minimum: 1, maximum: 3650, required_for_live: true }),
  base(REGISTER, "sources", "status", { required_for_live: true, method: true, default: "proposed", value: "proposed" }),
  base(DENYLIST, "extraction", "host_list", { method: true, default: [], value: [] }),
];

type Backend = { versions: Record<string, DrSettingVersion[]>; approvals: Record<string, DrSettingApproval[]> };
let backend: Backend;
let calls: { method: string; url: string; body: Record<string, unknown> | null }[] = [];

function inForce(s: DrSetting): DrSetting {
  const last = backend.approvals[s.key].at(-1);
  const v = last && last.version_number !== null ? backend.versions[s.key].find((x) => x.version_number === last.version_number) : undefined;
  const list = backend.versions[s.key];
  const stats = { version_count: list.length, latest_number: list.at(-1)?.version_number ?? null };
  return v && last
    ? { ...s, ...stats, value: v.value, origin: "approved", version: v.version_number, approved_by: last.approved_by, approved_at: last.approved_at }
    : { ...s, ...stats, value: s.default, origin: "proposed_default", version: null, approved_by: null, approved_at: null };
}
const missing = () =>
  CATALOGUE.map(inForce).filter((s) => s.required_for_live && (s.origin !== "approved" || (s.type === "status" && s.value !== "approved"))).map((s) => s.key);

function fakeApi(mayAdminister = true, refuse: Record<string, Response> = {}) {
  backend = { versions: Object.fromEntries(CATALOGUE.map((s) => [s.key, []])), approvals: Object.fromEntries(CATALOGUE.map((s) => [s.key, []])) };
  calls = [];
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url).split("?")[0];
    const method = init?.method ?? "GET";
    const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null;
    calls.push({ method, url: u, body });
    const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
    if (u === "/config") return json({ apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", build: { sha: null } });
    if (refuse[`${method} ${u}`]) return refuse[`${method} ${u}`];
    if (method === "GET" && u === "/api/v1/deep-research/settings") {
      return json({ catalogue_version: "aia-dr-settings-catalogue-1", may_administer: mayAdminister, missing_for_live: missing(), settings: CATALOGUE.map(inForce) });
    }
    const m = u.match(/^\/api\/v1\/deep-research\/settings\/([^/]+)(\/versions|\/approval)?$/);
    const s = m && CATALOGUE.find((x) => x.key === decodeURIComponent(m[1]));
    if (!m || !s) return json({ code: "unknown_setting", message: "no such setting" }, 404);
    if (method === "GET") {
      const detail: DrSettingDetail = { ...inForce(s), versions: [...backend.versions[s.key]].reverse(), history: [...backend.approvals[s.key]].reverse() };
      return json(detail);
    }
    if (!mayAdminister) return json({ code: "insufficient_role", message: "Changing Deep Research settings requires an organization OWNER or ADMIN." }, 403);
    if (method === "POST" && m[2] === "/versions") {
      const list = backend.versions[s.key];
      const v: DrSettingVersion = {
        version_number: list.length + 1, value: body?.value as DrSettingValue, value_sha256: "x",
        source_url: String(body?.source_url ?? ""), note: String(body?.note ?? ""), created_by: "USR-1", created_at: new Date().toISOString(),
      };
      list.push(v);
      return json(v, 201);
    }
    if (method === "PUT" && m[2] === "/approval") {
      const n = body?.version_number as number | null;
      if (n !== null && !backend.versions[s.key].some((v) => v.version_number === n)) return json({ code: "unknown_version", message: "no such version" }, 404);
      const list = backend.approvals[s.key];
      list.push({ approval_id: list.length + 1, version_number: n, approved_by: "USR-1", reason: String(body?.reason ?? ""), approved_at: new Date().toISOString() });
      return json(inForce(s));
    }
    return json({}, 404);
  }));
}
const called = (method: string, url: string) => calls.filter((c) => c.method === method && c.url === url);
const row = (key: string) =>
  waitFor(() => {
    const el = document.querySelector(`[data-dr-setting="${key}"]`) as HTMLElement | null;
    if (!el) throw new Error(`no row ${key}`);
    return el;
  });
const people = (id: string | null) => (id === "USR-1" ? "owner@example.test" : (id ?? "—"));
async function openDetail(key: string): Promise<HTMLElement> {
  fireEvent.click(within(await row(key)).getByRole("button", { name: "Detail" }));
  return waitFor(() => {
    const el = document.querySelector(`[data-dr-detail="${key}"]`) as HTMLElement | null;
    if (!el) throw new Error(`no detail ${key}`);
    return el;
  });
}

beforeEach(() => {
  resetConfigCache();
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "owner@example.test", subject: "s" }));
});
afterEach(() => {
  cleanup();
  resetConfigCache();
  vi.unstubAllGlobals();
});

describe("Deep Research settings", () => {
  it("shows every setting in its group with what is in force, and an unknown as unknown", async () => {
    fakeApi();
    render(<DeepResearchSettingsPanel people={people} />);
    const crawl = await row(CRAWL);
    expect(crawl.closest("[data-dr-group]")?.getAttribute("data-dr-group")).toBe("budgets");
    // The page's Czech name, the key beneath it, the code's default in force and so labelled.
    expect(within(crawl).getByText("Exhaustive: procházené stránky")).toBeTruthy();
    expect(within(crawl).getByText(CRAWL)).toBeTruthy();
    expect(crawl.querySelector("[data-value]")?.textContent).toBe(showValue("integer", 1000));
    expect(within(crawl).getByText("na běh")).toBeTruthy();
    expect(crawl.querySelector("[data-origin]")?.textContent).toBe("Navržená výchozí");
    expect(within(crawl).getByText("jen snížit")).toBeTruthy();
    expect(within(crawl).getByText("mění metodu")).toBeTruthy();
    // The code holds no retention: it reads as unknown, never as zero days.
    const retention = await row(RETENTION);
    expect(retention.querySelector("[data-value]")?.textContent).toBe("neznámé");
    expect(within(retention).queryByText("dní")).toBeNull();
    expect((await row(DENYLIST)).querySelector("[data-value]")?.textContent).toBe("prázdný seznam");
  });

  it("lists exactly what live still needs approved, in the catalogue's order", async () => {
    fakeApi();
    render(<DeepResearchSettingsPanel people={people} />);
    const readiness = await waitFor(() => {
      const el = document.querySelector("[data-live-readiness]") as HTMLElement | null;
      if (!el) throw new Error("no readiness list");
      return el;
    });
    await waitFor(() => expect([...readiness.querySelectorAll("[data-missing]")].map((e) => e.getAttribute("data-missing"))).toEqual([RETENTION, REGISTER]));
    expect(within(readiness).getByText("Zachycené stránky uchovávat")).toBeTruthy();
  });

  it("proposes a value that is not in force until approved, then withdraws it", async () => {
    fakeApi();
    render(<DeepResearchSettingsPanel people={people} />);
    const detail = await openDetail(RETENTION);
    const form = detail.querySelector("[data-dr-propose]") as HTMLElement;
    fireEvent.change(within(form).getByLabelText("Hodnota"), { target: { value: "90" } });
    fireEvent.change(within(form).getByLabelText("Zdroj (https URL, nepovinné)"), { target: { value: "https://example.org/retention" } });
    fireEvent.click(within(form).getByRole("button", { name: "Uložit návrh" }));
    await screen.findByText("Uloženo jako e1. Neplatí, dokud ji někdo neschválí.");
    expect(called("POST", `/api/v1/deep-research/settings/${RETENTION}/versions`)[0].body).toEqual({ value: 90, source_url: "https://example.org/retention", note: "" });
    // Proposed is not in force.
    await waitFor(async () => expect((await row(RETENTION)).querySelector("[data-origin]")?.textContent).toBe("Navržená výchozí"));

    fireEvent.click(await screen.findByRole("button", { name: "Schválit e1" }));
    const approve = document.querySelector("[data-dr-approve]") as HTMLElement;
    fireEvent.change(within(approve).getByLabelText("Důvod (nepovinný)"), { target: { value: "podepsáno" } });
    fireEvent.click(within(approve).getByRole("button", { name: "Potvrdit" }));
    await screen.findByText("Hotovo. Platí pro běhy zařazené od teď.");
    expect(called("PUT", `/api/v1/deep-research/settings/${RETENTION}/approval`)[0].body).toEqual({ version_number: 1, reason: "podepsáno" });
    await waitFor(async () => {
      const r = await row(RETENTION);
      expect(r.querySelector("[data-origin]")?.textContent).toBe("Schváleno");
      expect(r.querySelector("[data-value]")?.textContent).toBe("90");
    });
    await waitFor(() => expect(document.querySelector(`[data-missing="${RETENTION}"]`)).toBeNull());

    fireEvent.click(await screen.findByRole("button", { name: "Vrátit na výchozí" }));
    fireEvent.click(within(document.querySelector("[data-dr-approve]") as HTMLElement).getByRole("button", { name: "Potvrdit" }));
    await waitFor(() => expect(called("PUT", `/api/v1/deep-research/settings/${RETENTION}/approval`)).toHaveLength(2));
    expect(called("PUT", `/api/v1/deep-research/settings/${RETENTION}/approval`)[1].body).toEqual({ version_number: null, reason: "" });
    await waitFor(async () => expect((await row(RETENTION)).querySelector("[data-origin]")?.textContent).toBe("Navržená výchozí"));
    const history = await waitFor(() => {
      const items = document.querySelectorAll("[data-dr-approval]");
      if (items.length !== 2) throw new Error("history not re-read");
      return [...items].map((e) => e.textContent ?? "");
    });
    expect(history[0]).toMatch(/^vráceno na výchozí/);
    expect(history[1]).toMatch(/^e1 · owner@example\.test/);
  });

  it("sends a host list as a list, one per line", async () => {
    fakeApi();
    render(<DeepResearchSettingsPanel people={people} />);
    const form = (await openDetail(DENYLIST)).querySelector("[data-dr-propose]") as HTMLElement;
    fireEvent.change(within(form).getByLabelText("Hodnota · Jedna položka na řádek"), { target: { value: "shop.example\n\n a.example \n" } });
    fireEvent.click(within(form).getByRole("button", { name: "Uložit návrh" }));
    await waitFor(() => expect(called("POST", `/api/v1/deep-research/settings/${DENYLIST}/versions`)).toHaveLength(1));
    expect(called("POST", `/api/v1/deep-research/settings/${DENYLIST}/versions`)[0].body?.value).toEqual(["shop.example", "a.example"]);
  });

  it("refuses a value that is not of its type before asking, and shows the API's refusal as given", async () => {
    fakeApi(true, {
      [`POST /api/v1/deep-research/settings/${CRAWL}/versions`]: new Response(
        JSON.stringify({ code: "setting_invalid", message: `${CRAWL}: may only lower the code's cap of 1000` }), { status: 422 },
      ),
    });
    render(<DeepResearchSettingsPanel people={people} />);
    const form = (await openDetail(CRAWL)).querySelector("[data-dr-propose]") as HTMLElement;
    fireEvent.change(within(form).getByLabelText("Hodnota"), { target: { value: "dvě stě" } });
    fireEvent.click(within(form).getByRole("button", { name: "Uložit návrh" }));
    expect(await within(form).findByText("Zadejte celé číslo.")).toBeTruthy();
    expect(called("POST", `/api/v1/deep-research/settings/${CRAWL}/versions`)).toEqual([]);

    fireEvent.change(within(form).getByLabelText("Hodnota"), { target: { value: "5000" } });
    fireEvent.click(within(form).getByRole("button", { name: "Uložit návrh" }));
    const alert = await within(form).findByRole("alert");
    expect(alert.textContent).toContain("HTTP 422 · setting_invalid");
    expect(alert.textContent).toContain("may only lower the code's cap of 1000");
  });

  it("lets a member read what is in force and its history, and offers no change", async () => {
    fakeApi(false);
    render(<DeepResearchSettingsPanel people={people} />);
    expect(await screen.findByText(/Hodnoty navrhuje a schvaluje vlastník nebo správce/)).toBeTruthy();
    const detail = await openDetail(RETENTION);
    expect(within(detail).getByText("Zatím žádná navržená verze.")).toBeTruthy();
    expect(detail.querySelector("[data-dr-propose]")).toBeNull();
    expect(within(detail).queryByRole("button", { name: /Schválit|Vrátit/ })).toBeNull();
  });

  it("says the API sent no settings rather than drawing an empty tab", async () => {
    fakeApi(true, { "GET /api/v1/deep-research/settings": new Response("{}", { status: 200 }) });
    render(<DeepResearchSettingsPanel people={people} />);
    expect(await screen.findByText("API nevrátilo nastavení Deep Research.")).toBeTruthy();
  });
});
