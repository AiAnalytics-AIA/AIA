// @vitest-environment jsdom
// The Deep Research tab against a fake of its route (ADR 0022): what is in force and where
// it comes from, what live still needs, and an administrator proposing, approving and
// withdrawing -- a proposal is not in force until approved. The fake keeps real state and
// refuses as the API does; every refusal is shown as the API gave it.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import type { DrSetting, DrSettingApproval, DrSettingDetail, DrSettingValue, DrSettingVersion } from "@/lib/api";
import { resetConfigCache } from "@/lib/auth";
import { researchPolicyHelp } from "./settings-guide";
import { DeepResearchSettingsPanel, showValue } from "./DeepResearchSettingsPanel";
import { TechnicalProvider } from "./technical";

// jsdom has <dialog> without showModal/close: the modal's open state, as a browser sets it.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) { this.removeAttribute("open"); };
});

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

type Backend = { versions: Record<string, DrSettingVersion[]>; approvals: Record<string, DrSettingApproval[]>; declines: Record<string, Record<number, NonNullable<DrSettingVersion["decline"]>>>; withStates: boolean };
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
  backend = { versions: Object.fromEntries(CATALOGUE.map((s) => [s.key, []])), approvals: Object.fromEntries(CATALOGUE.map((s) => [s.key, []])), declines: Object.fromEntries(CATALOGUE.map((s) => [s.key, {}])), withStates: false };
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
    const m = u.match(/^\/api\/v1\/deep-research\/settings\/([^/]+)(\/versions|\/approval|\/versions\/\d+\/withdrawal)?$/);
    const s = m && CATALOGUE.find((x) => x.key === decodeURIComponent(m[1]));
    if (!m || !s) return json({ code: "unknown_setting", message: "no such setting" }, 404);
    // As #841 answers: each version's state and decline, read from the logs (only when the test asks).
    const stated = (v: DrSettingVersion): DrSettingVersion => {
      if (!backend.withStates) return v;
      const decline = backend.declines[s.key][v.version_number] ?? null;
      const approvals = backend.approvals[s.key];
      const state = decline ? decline.kind : approvals.at(-1)?.version_number === v.version_number ? "IN_FORCE"
        : approvals.some((a) => a.version_number === v.version_number) ? "APPROVED_BEFORE" : "PENDING";
      return { ...v, state, decline };
    };
    const w = u.match(/\/versions\/(\d+)\/withdrawal$/);
    if (method === "POST" && w) {
      if (!String(body?.reason ?? "").trim()) return json({ code: "request_invalid", message: "reason required" }, 422);
      const n = Number(w[1]);
      const v = backend.versions[s.key].find((x) => x.version_number === n);
      if (!v) return json({ code: "unknown_version", message: "no such version" }, 404);
      backend.declines[s.key][n] = { kind: "WITHDRAWN", by: "USR-1", reason: String(body?.reason), at: new Date().toISOString() };
      return json(stated(v));
    }
    if (method === "GET") {
      const detail: DrSettingDetail = { ...inForce(s), versions: [...backend.versions[s.key]].reverse().map(stated), history: [...backend.approvals[s.key]].reverse() };
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
  // As a person does: the rule's group first, then its row.
  const group = (await row(key)).closest("[data-dr-group]")?.getAttribute("data-dr-group");
  fireEvent.click(document.querySelector(`[data-dr-group-link="${group}"]`) as HTMLElement);
  fireEvent.click(within(await row(key)).getByRole("button", { name: /^(Upravit|Historie)$/ }));
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
    // The page's Czech name, the code's default in force and so labelled; the key is a
    // technical detail, shown only when the page's switch is on.
    expect(within(crawl).getByText("Exhaustive: procházené stránky")).toBeTruthy();
    expect(within(crawl).queryByText(CRAWL)).toBeNull();
    expect(crawl.querySelector("[data-value]")?.textContent).toBe(showValue("integer", 1000));
    const inForceCell = (r: HTMLElement) => r.querySelector("[data-value]")?.closest("td") as HTMLElement;
    expect(within(inForceCell(crawl)).getByText("na běh")).toBeTruthy();
    expect(crawl.querySelector("[data-origin]")?.textContent).toBe("Navržená výchozí");
    expect(within(crawl).getByText("jen snížit")).toBeTruthy();
    expect(within(crawl).getByText("mění metodu")).toBeTruthy();
    // The code holds no retention: it reads as unknown, never as zero days.
    const retention = await row(RETENTION);
    expect(retention.querySelector("[data-value]")?.textContent).toBe("neznámé");
    expect(within(inForceCell(retention)).queryByText("dní")).toBeNull();
    expect((await row(DENYLIST)).querySelector("[data-value]")?.textContent).toBe("prázdný seznam");
  });

  it("shows the catalogue keys only with technical details on", async () => {
    fakeApi();
    render(<TechnicalProvider on><DeepResearchSettingsPanel people={people} /></TechnicalProvider>);
    expect(within(await row(CRAWL)).getByText(CRAWL)).toBeTruthy();
    expect(screen.getByText("Katalog aia-dr-settings-catalogue-1")).toBeTruthy();
  });

  it("opens on one group and switches groups without losing an unsaved proposal", async () => {
    fakeApi();
    render(<DeepResearchSettingsPanel people={people} />);
    const budgets = (await row(CRAWL)).closest("[data-dr-group]") as HTMLElement;
    const retention = (await row(RETENTION)).closest("[data-dr-group]") as HTMLElement;
    expect(budgets.hidden).toBe(false);
    expect(retention.hidden).toBe(true);
    // The group list says what waits in each group: retention has one rule live needs.
    expect(document.querySelector('[data-dr-group-link="retention"]')?.textContent).toBe("Uchovávání1");
    const form = (await openDetail(CRAWL)).querySelector("[data-dr-propose]") as HTMLElement;
    fireEvent.change(within(form).getByLabelText("Hodnota"), { target: { value: "500" } });
    fireEvent.click(document.querySelector('[data-dr-group-link="retention"]') as HTMLElement);
    expect(budgets.hidden).toBe(true);
    expect(retention.hidden).toBe(false);
    fireEvent.click(document.querySelector('[data-dr-group-link="budgets"]') as HTMLElement);
    expect((within(form).getByLabelText("Hodnota") as HTMLInputElement).value).toBe("500");
  });

  it("says in one line what live still needs, and shows exactly those rules on request", async () => {
    fakeApi();
    render(<DeepResearchSettingsPanel people={people} />);
    const readiness = await waitFor(() => {
      const el = document.querySelector("[data-live-readiness]") as HTMLElement | null;
      if (!el) throw new Error("no readiness line");
      return el;
    });
    expect(readiness.textContent).toContain("pravidla čekající na schválení: 2.");
    expect(readiness.querySelector("details")).toBeNull();
    fireEvent.click(within(readiness).getByRole("button", { name: "Zobrazit jen tato pravidla" }));
    const shown = [...document.querySelectorAll<HTMLElement>("[data-dr-setting]")].filter((r) => !r.hidden && !(r.closest("[data-dr-group]") as HTMLElement).hidden);
    expect(shown.map((r) => r.getAttribute("data-dr-setting"))).toEqual([RETENTION, REGISTER]);
    expect(within(shown[0]).getByText("Zachycené stránky uchovávat")).toBeTruthy();
    fireEvent.click(within(readiness).getByRole("button", { name: "Zobrazit všechna pravidla" }));
    expect((document.querySelector('[data-dr-group="budgets"]') as HTMLElement).hidden).toBe(false);
  });

  it("proposes a value that is not in force until approved, then withdraws it", async () => {
    fakeApi();
    render(<DeepResearchSettingsPanel people={people} />);
    const detail = await openDetail(RETENTION);
    const form = detail.querySelector("[data-dr-propose]") as HTMLElement;
    fireEvent.change(within(form).getByLabelText("Hodnota"), { target: { value: "90" } });
    fireEvent.change(within(form).getByLabelText("Zdroj (https URL, nepovinné)"), { target: { value: "https://example.org/retention" } });
    fireEvent.click(within(form).getByRole("button", { name: "Uložit návrh" }));
    await screen.findByText("Uloženo jako verze 1. Neplatí, dokud ji někdo neschválí.");
    expect(called("POST", `/api/v1/deep-research/settings/${RETENTION}/versions`)[0].body).toEqual({ value: 90, source_url: "https://example.org/retention", note: "" });
    // Proposed is not in force, and the change now waits on its approval.
    await waitFor(async () => expect((await row(RETENTION)).querySelector("[data-origin]")?.textContent).toBe("Navržená výchozí"));
    await waitFor(() => expect(document.querySelector('[data-dr-flow] [data-state="now"]')?.textContent).toBe("2Schválit"));

    fireEvent.click(await screen.findByRole("button", { name: "Schválit verzi 1" }));
    const approve = document.querySelector("[data-dr-approve]") as HTMLElement;
    fireEvent.change(within(approve).getByLabelText("Důvod (nepovinný)"), { target: { value: "podepsáno" } });
    // Confirmable once the dialog has read what the approval changes.
    await waitFor(() => expect((within(approve).getByRole("button", { name: "Schválit" }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(within(approve).getByRole("button", { name: "Schválit" }));
    await screen.findByText("Hotovo. Platí pro běhy zařazené od teď.");
    expect(called("PUT", `/api/v1/deep-research/settings/${RETENTION}/approval`)[0].body).toEqual({ version_number: 1, reason: "podepsáno" });
    await waitFor(async () => {
      const r = await row(RETENTION);
      expect(r.querySelector("[data-origin]")?.textContent).toBe("Schváleno");
      expect(r.querySelector("[data-value]")?.textContent).toBe("90");
    });
    await waitFor(() => expect(document.querySelector(`[data-missing="${RETENTION}"]`)).toBeNull());
    await waitFor(() => expect(document.querySelector('[data-dr-flow] [data-state="now"]')).toBeNull());

    fireEvent.click(await screen.findByRole("button", { name: "Vrátit na výchozí" }));
    const back = document.querySelector("[data-dr-approve]") as HTMLElement;
    await waitFor(() => expect((within(back).getByRole("button", { name: "Vrátit na výchozí" }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(within(back).getByRole("button", { name: "Vrátit na výchozí" }));
    await waitFor(() => expect(called("PUT", `/api/v1/deep-research/settings/${RETENTION}/approval`)).toHaveLength(2));
    expect(called("PUT", `/api/v1/deep-research/settings/${RETENTION}/approval`)[1].body).toEqual({ version_number: null, reason: "" });
    await waitFor(async () => expect((await row(RETENTION)).querySelector("[data-origin]")?.textContent).toBe("Navržená výchozí"));
    const history = await waitFor(() => {
      const items = document.querySelectorAll("[data-dr-approval]");
      if (items.length !== 2) throw new Error("history not re-read");
      return [...items].map((e) => e.textContent ?? "");
    });
    expect(history[0]).toMatch(/^vráceno na výchozí/);
    expect(history[1]).toMatch(/^Verze 1 · owner@example\.test/);
    // Withdrawn to the default, version 1 is earlier, not a proposal waiting for approval.
    await new Promise((r) => setTimeout(r, 50));
    expect((await row(RETENTION)).getAttribute("data-pending")).toBeNull();
    expect((await row(RETENTION)).className).not.toContain("bg-status-you-wash");
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
    expect(detail.querySelector("[data-dr-flow]")).toBeNull();
  });

  it("draws the board: who decides, Dosah and the posture pointed to where they live, the code's protections", async () => {
    fakeApi();
    render(<DeepResearchSettingsPanel people={people} />);
    await row(RETENTION);
    // Who reads and who decides is the tab head's (ControlPanel), said once there.
    expect(screen.queryByText("Vy: navrhujete a schvalujete")).toBeNull();
    // No reach route in this deployment (a 404): not in AIA yet, never an empty "nothing reachable".
    const reach = document.querySelector("[data-dr-reach]") as HTMLElement;
    expect(await within(reach).findByText("V AIA zatím není")).toBeTruthy();
    const posture = document.querySelector("[data-dr-posture]") as HTMLElement;
    expect(within(posture).getByRole("link", { name: "Přístup a schvalování" }).getAttribute("href")).toBe("/app/settings#access");
    const prot = document.querySelector("[data-dr-protections]") as HTMLElement;
    expect(within(prot).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "respektuje robots.txt", "žádné přihlášení ani paywall", "žádné osobní údaje", "jen veřejné zdroje", "každé zjištění doložené citací",
    ]);
  });

  const REACH = (recorded: boolean) => new Response(JSON.stringify({
    recorded, worker: recorded ? "worker-1" : null, build_sha: recorded ? "abc1234def" : null, composed_at: recorded ? new Date().toISOString() : null,
    agent_directed: recorded ? false : null, class_gates: recorded ? "enforce" : null, data_class: null, missing_for_live: [RETENTION],
    routes: recorded ? [
      { route: "brave-web-search", kind: "search", state: "waiting", reason: "settings_unapproved", detail: "the organization has not approved every setting live needs", classes: ["C"], priced: true, zone: "NON_EU", missing_settings: [RETENTION], class_advisory: false },
      { route: "wikipedia-public-web_search", kind: "search", state: "active", reason: null, detail: null, classes: ["C"], priced: false, zone: "EU", missing_settings: [], class_advisory: false },
      { route: "common-crawl-athena-index", kind: "index", state: "built", reason: "common_crawl_off", detail: "AIA_DEEP_RESEARCH_COMMON_CRAWL is not true", classes: [], priced: false, zone: null, missing_settings: [], class_advisory: false },
    ] : [],
  }), { status: 200 });

  it("reads Dosah from the worker's record, waiting first in coral for an administrator, each reason in Czech", async () => {
    fakeApi(true, { "GET /api/v1/settings/deep-research/reach": REACH(true) });
    render(<DeepResearchSettingsPanel people={people} />);
    const brave = await waitFor(() => {
      const el = document.querySelector('[data-reach-route="brave-web-search"]') as HTMLElement | null;
      if (!el) throw new Error("no reach yet");
      return el;
    });
    const reach = document.querySelector("[data-dr-reach]") as HTMLElement;
    expect(within(reach).getByText("1 z 3 tras aktivní")).toBeTruthy();
    expect([...reach.querySelectorAll("[data-reach-route]")].map((r) => r.getAttribute("data-reach-state"))).toEqual(["waiting", "active", "built"]);
    expect(brave.className).toContain("bg-status-you-wash");
    expect(within(brave).getByText("Brave Search")).toBeTruthy();
    expect(within(brave).getByText(/Placená trasa se nezapne, dokud organizace neschválí pravidla/)).toBeTruthy();
    expect(within(brave).getByText("zpracování mimo EU")).toBeTruthy();
    // The server's English detail is a technical one, not the reason a person reads.
    expect(within(brave).queryByText(/has not approved/)).toBeNull();
    expect(within(reach.querySelector('[data-reach-route="common-crawl-athena-index"]') as HTMLElement).getByText("Common Crawl je v nasazení vypnutý.")).toBeTruthy();
  });

  it("says no worker has recorded Dosah yet, never that a route is reachable, and keeps a waiting route neutral for a member", async () => {
    fakeApi(true, { "GET /api/v1/settings/deep-research/reach": REACH(false) });
    render(<DeepResearchSettingsPanel people={people} />);
    await waitFor(() => expect(document.querySelector("[data-reach-unrecorded]")).toBeTruthy());
    expect(document.querySelector("[data-reach-route]")).toBeNull();
    cleanup();
    fakeApi(false, { "GET /api/v1/settings/deep-research/reach": REACH(true) });
    render(<DeepResearchSettingsPanel people={people} />);
    const brave = await waitFor(() => {
      const el = document.querySelector('[data-reach-route="brave-web-search"]') as HTMLElement | null;
      if (!el) throw new Error("no reach yet");
      return el;
    });
    expect(brave.className).not.toContain("bg-status-you-wash");
  });

  it("proposes in the rule's Návrh cell, highlights the waiting proposal, and approves it through a modal", async () => {
    fakeApi();
    render(<DeepResearchSettingsPanel people={people} />);
    await row(RETENTION);
    fireEvent.click(document.querySelector('[data-dr-group-link="retention"]') as HTMLElement);
    const r = await row(RETENTION);
    const field = within(r).getByRole("spinbutton", { name: /^Návrh:/ });
    fireEvent.change(field, { target: { value: "90" } });
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(() => expect(called("POST", `/api/v1/deep-research/settings/${RETENTION}/versions`)).toHaveLength(1));
    expect(called("POST", `/api/v1/deep-research/settings/${RETENTION}/versions`)[0].body).toEqual({ value: 90, source_url: "", note: "" });
    await waitFor(async () => expect((await row(RETENTION)).getAttribute("data-pending")).toBe("1"));
    const pending = await row(RETENTION);
    expect(pending.className).toContain("bg-status-you-wash");
    await waitFor(() => expect(pending.querySelector("[data-pending-value]")?.textContent).toContain("90"));
    expect(within(pending).getByRole("button", { name: "Stáhnout návrh" })).toBeTruthy();
    // Nothing is in force until approved.
    expect(pending.querySelector("[data-origin]")?.textContent).toBe("Navržená výchozí");
    fireEvent.click(within(pending).getByRole("button", { name: "Schválit" }));
    const dialog = await waitFor(() => {
      const el = document.querySelector("[data-dr-approve]") as HTMLElement | null;
      if (!el?.textContent?.includes("90 dní")) throw new Error("no dialog yet");
      return el;
    });
    expect(within(dialog).getByText("neznámé")).toBeTruthy();
    expect(within(dialog).getByText(/zařazené od teď/)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "Schválit" }));
    await waitFor(() => expect(called("PUT", `/api/v1/deep-research/settings/${RETENTION}/approval`)).toHaveLength(1));
    expect(called("PUT", `/api/v1/deep-research/settings/${RETENTION}/approval`)[0].body).toEqual({ version_number: 1, reason: "" });
    await waitFor(async () => expect((await row(RETENTION)).getAttribute("data-pending")).toBeNull());
    expect((await row(RETENTION)).querySelector("[data-value]")?.textContent).toBe("90");
  });

  it("withdraws a waiting proposal with a reason through a modal; the version stays, marked, and is not approvable", async () => {
    fakeApi();
    backend.withStates = true;
    render(<DeepResearchSettingsPanel people={people} />);
    await row(RETENTION);
    fireEvent.click(document.querySelector('[data-dr-group-link="retention"]') as HTMLElement);
    const field = within(await row(RETENTION)).getByRole("spinbutton", { name: /^Návrh:/ });
    fireEvent.change(field, { target: { value: "90" } });
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(async () => expect((await row(RETENTION)).getAttribute("data-pending")).toBe("1"));
    fireEvent.click(within(await row(RETENTION)).getByRole("button", { name: "Stáhnout návrh" }));
    const dialog = document.querySelector("[data-dr-withdraw]") as HTMLElement;
    expect(within(dialog).getByText("90 dní")).toBeTruthy();
    // A reason is required: nothing is sent without one.
    fireEvent.click(within(dialog).getByRole("button", { name: "Stáhnout návrh" }));
    expect(within(dialog).getByRole("alert").textContent).toBe("Napište důvod stažení.");
    expect(calls.filter((c) => c.url.endsWith("/withdrawal"))).toEqual([]);
    fireEvent.change(within(dialog).getByLabelText("Důvod (povinný)"), { target: { value: "špatná hodnota" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Stáhnout návrh" }));
    await waitFor(() => expect(called("POST", `/api/v1/deep-research/settings/${RETENTION}/versions/1/withdrawal`)).toHaveLength(1));
    expect(called("POST", `/api/v1/deep-research/settings/${RETENTION}/versions/1/withdrawal`)[0].body).toEqual({ reason: "špatná hodnota" });
    await waitFor(async () => expect((await row(RETENTION)).getAttribute("data-pending")).toBeNull());
    const detail = await openDetail(RETENTION);
    await waitFor(() => expect(detail.querySelector('[data-declined="WITHDRAWN"]')?.textContent).toContain("špatná hodnota"));
    expect(within(detail).queryByRole("button", { name: "Schválit verzi 1" })).toBeNull();
  });

  it("does not call a proposal an approval passed over waiting, though the server still says PENDING", async () => {
    fakeApi();
    backend.withStates = true;
    const at = (d: string) => `2026-10-${d}T10:00:00.000Z`;
    const version = (n: number, value: number, d: string): DrSettingVersion => ({ version_number: n, value, value_sha256: "x", source_url: "", note: "", created_by: "USR-1", created_at: at(d) });
    // v1 and v2 proposed, v2 approved, v3 proposed and withdrawn: v1 is PENDING to the server, but no proposal waits.
    backend.versions[RETENTION] = [version(1, 90, "01"), version(2, 120, "02"), version(3, 150, "04")];
    backend.approvals[RETENTION] = [{ approval_id: 1, version_number: 2, approved_by: "USR-1", reason: "", approved_at: at("03") }];
    backend.declines[RETENTION] = { 3: { kind: "WITHDRAWN", by: "USR-1", reason: "ne", at: at("05") } };
    render(<DeepResearchSettingsPanel people={people} />);
    await row(RETENTION);
    await new Promise((r) => setTimeout(r, 50));
    expect((await row(RETENTION)).getAttribute("data-pending")).toBeNull();
  });

  it("does not show a declined or passed-over newest version as waiting at step 2 of the detail", async () => {
    fakeApi();
    backend.withStates = true;
    const at = (d: string) => `2026-10-${d}T10:00:00.000Z`;
    const version = (n: number, value: number, d: string): DrSettingVersion => ({ version_number: n, value, value_sha256: "x", source_url: "", note: "", created_by: "USR-1", created_at: at(d) });
    backend.versions[RETENTION] = [version(1, 90, "01"), version(2, 120, "02"), version(3, 150, "04")];
    backend.approvals[RETENTION] = [{ approval_id: 1, version_number: 2, approved_by: "USR-1", reason: "", approved_at: at("03") }];
    backend.declines[RETENTION] = { 3: { kind: "DECLINED", by: "USR-1", reason: "ne", at: at("05") } };
    render(<DeepResearchSettingsPanel people={people} />);
    const detail = await openDetail(RETENTION);
    await waitFor(() => expect(detail.querySelector("[data-dr-flow]")).toBeTruthy());
    await waitFor(() => expect(detail.querySelector('[data-declined="DECLINED"]')).toBeTruthy());
    const steps = [...detail.querySelectorAll("[data-dr-flow] li")].map((li) => li.getAttribute("data-state"));
    expect(steps[1]).not.toBe("now");
  });

  it("keeps the approval's confirm disabled until the comparison is read, and says a failed read", async () => {
    fakeApi();
    render(<DeepResearchSettingsPanel people={people} />);
    await row(RETENTION);
    fireEvent.click(document.querySelector('[data-dr-group-link="retention"]') as HTMLElement);
    const field = within(await row(RETENTION)).getByRole("spinbutton", { name: /^Návrh:/ });
    fireEvent.change(field, { target: { value: "90" } });
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(async () => expect((await row(RETENTION)).getAttribute("data-pending")).toBe("1"));
    // From here the rule's own read is slow, then refused.
    const real = globalThis.fetch;
    let mode: "slow" | "fail" = "slow";
    vi.stubGlobal("fetch", vi.fn((url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url).split("?")[0];
      if ((init?.method ?? "GET") === "GET" && u === `/api/v1/deep-research/settings/${RETENTION}`) {
        return mode === "slow" ? new Promise<Response>(() => {}) : Promise.resolve(new Response(JSON.stringify({ code: "internal", message: "Boom" }), { status: 500 }));
      }
      return real(url, init);
    }));
    fireEvent.click(within(await row(RETENTION)).getByRole("button", { name: "Schválit" }));
    let dialog = await waitFor(() => { const el = document.querySelector("[data-dr-approve]") as HTMLElement | null; if (!el) throw new Error("no dialog"); return el; });
    expect((within(dialog).getByRole("button", { name: "Schválit" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(within(dialog).getByRole("button", { name: "Zrušit" }));
    mode = "fail";
    fireEvent.click(within(await row(RETENTION)).getByRole("button", { name: "Schválit" }));
    dialog = await waitFor(() => { const el = document.querySelector("[data-dr-approve]") as HTMLElement | null; if (!el?.querySelector("[role=alert]")) throw new Error("no failure yet"); return el; });
    expect(within(dialog).getByRole("alert").textContent).toMatch(/Boom/);
    const confirm = within(dialog).getByRole("button", { name: "Schválit" }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    fireEvent.click(confirm);
    expect(called("PUT", `/api/v1/deep-research/settings/${RETENTION}/approval`)).toEqual([]);
  });

  it("refuses at the field a number outside a rule's bounds, a lower-only cap above its default included, and sends nothing", async () => {
    fakeApi();
    render(<DeepResearchSettingsPanel people={people} />);
    await row(CRAWL);
    const tryValue = async (key: string, group: string, value: string) => {
      fireEvent.click(document.querySelector(`[data-dr-group-link="${group}"]`) as HTMLElement);
      const field = within(await row(key)).getByRole("spinbutton", { name: /^Návrh:/ });
      fireEvent.change(field, { target: { value } });
      fireEvent.keyDown(field, { key: "Enter" });
      expect(within(await row(key)).getByRole("alert")).toBeTruthy();
      fireEvent.keyDown(field, { key: "Escape" });
    };
    await tryValue(CRAWL, "budgets", "1001");
    await tryValue(RETENTION, "retention", "0");
    await tryValue(RETENTION, "retention", "3651");
    expect(calls.filter((c) => c.method === "POST")).toEqual([]);
  });

  it("shows a member a waiting proposal neutral: coral is for someone who can act on it", async () => {
    fakeApi(false);
    backend.versions[RETENTION] = [{ version_number: 1, value: 90, value_sha256: "x", source_url: "", note: "", created_by: "USR-1", created_at: new Date().toISOString() }];
    render(<DeepResearchSettingsPanel people={people} />);
    await row(RETENTION);
    fireEvent.click(document.querySelector('[data-dr-group-link="retention"]') as HTMLElement);
    await waitFor(async () => expect((await row(RETENTION)).getAttribute("data-pending")).toBe("1"));
    const r = await row(RETENTION);
    expect(r.className).not.toContain("bg-status-you-wash");
    expect(r.querySelector("[data-pending-value] .text-status-you-ink")).toBeNull();
    expect(within(r).queryByRole("button", { name: "Schválit" })).toBeNull();
  });

  it("proposes a status by its choice in place, and offers a member no proposal", async () => {
    fakeApi();
    render(<DeepResearchSettingsPanel people={people} />);
    await row(REGISTER);
    fireEvent.click(document.querySelector('[data-dr-group-link="sources"]') as HTMLElement);
    const chips = within(await row(REGISTER)).getByRole("radiogroup", { name: /^Návrh:/ });
    fireEvent.click(within(chips).getByRole("radio", { name: "schváleno" }));
    await waitFor(() => expect(called("POST", `/api/v1/deep-research/settings/${REGISTER}/versions`)[0]?.body).toEqual({ value: "approved", source_url: "", note: "" }));
    cleanup();
    fakeApi(false);
    render(<DeepResearchSettingsPanel people={people} />);
    const r = await row(RETENTION);
    expect(within(r).queryByRole("spinbutton", { hidden: true })).toBeNull();
    expect(within(r).getByText("žádný návrh")).toBeTruthy();
    expect(screen.getByText(/Hodnoty navrhuje a schvaluje vlastník nebo správce/)).toBeTruthy();
  });

  it("says the API sent no settings rather than drawing an empty tab", async () => {
    fakeApi(true, { "GET /api/v1/deep-research/settings": new Response("{}", { status: 200 }) });
    render(<DeepResearchSettingsPanel people={people} />);
    expect(await screen.findByText("API nevrátilo nastavení Deep Research.")).toBeTruthy();
  });
});

  it("explains and searches policy purpose, preserving and guarding an unfinished proposal", async () => {
    fakeApi(); render(<DeepResearchSettingsPanel people={people} />);
    const detail = await openDetail(CRAWL);
    const form = detail.querySelector("[data-dr-propose]") as HTMLElement;
    fireEvent.change(within(form).getByLabelText("Hodnota"), { target: { value: "777" } });
    fireEvent.change(screen.getByRole("searchbox", { name: "Hledat pravidlo rešerše" }), { target: { value: "uchovávají" } });
    expect((within(form).getByLabelText("Hodnota") as HTMLInputElement).value).toBe("777");
    expect(screen.getByText(/Počet dní, po které se uchovávají zachycené/)).toBeTruthy();
    fireEvent.click(within(await row(CRAWL)).getByRole("button", { name: "Zavřít" }));
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Ponechat" }));
    expect((within(form).getByLabelText("Hodnota") as HTMLInputElement).value).toBe("777");
    fireEvent.click(within(form).getByRole("button", { name: "Vrátit neuložené změny" }));
    fireEvent.change(screen.getByRole("searchbox", { name: "Hledat pravidlo rešerše" }), { target: { value: "no-such-rule" } });
    expect(screen.getByText("Žádné pravidlo neodpovídá hledání.")).toBeTruthy();
    expect(calls.filter((c) => c.method !== "GET")).toEqual([]);
  });

  it("explains exact, agent-limit, budget, connector and extraction policy families without inventing controls", () => {
    expect(researchPolicyHelp("provider.search.storage_and_ai_use_granted", "provider")).toContain("uchovávat výsledky");
    expect(researchPolicyHelp("limits.lead.window_tokens", "limits")).toContain("vstup");
    expect(researchPolicyHelp("limits.verifier.answer_tokens", "limits")).toContain("odpověď");
    expect(researchPolicyHelp("budgets.run_limit.standard", "budgets")).toContain("rozpočet studie");
    expect(researchPolicyHelp("budgets.allowance.deep.connector_calls", "budgets")).toContain("konektorů");
    expect(researchPolicyHelp("extraction.caps.deep.pages_per_host", "extraction")).toContain("jedné domény");
    expect(researchPolicyHelp("future.rule", "future")).toContain("až po schválení");
  });
