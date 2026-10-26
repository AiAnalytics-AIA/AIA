// @vitest-environment jsdom
// Stav systému and Správa dat against fakes of #839's and #850's routes: what is read, what is
// unknown (never good), and the client deletion's confirmation, its refusals and what it leaves.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { resetConfigCache } from "@/lib/auth";
import { DataPanel } from "./DataPanel";
import { SystemPanel } from "./SystemPanel";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/app/settings" }));

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) { this.removeAttribute("open"); };
});

let calls: { method: string; url: string; body: unknown }[] = [];
function fake(routes: Record<string, (body: unknown) => Response | unknown>) {
  calls = [];
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url).split("?")[0];
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : null;
    calls.push({ method, url: u, body });
    if (u === "/config") return new Response(JSON.stringify({ apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", build: { sha: null } }));
    const answer = routes[`${method} ${u}`]?.(body);
    // A path no route answers, as the API's error contract says it (observability.py: http_<status>).
    if (answer === undefined) return new Response('{"code":"http_404","message":"Not Found"}', { status: 404 });
    return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
  }));
}
const refuse = (status: number, code: string, message: string, details: Record<string, unknown> = {}) =>
  new Response(JSON.stringify({ code, message, details }), { status });

beforeEach(() => {
  resetConfigCache();
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "owner@example.test", subject: "s" }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); });

describe("Stav systému", () => {
  it("lists the smoke run's checks, the failed ones first in words, and its time and build", async () => {
    fake({
      "GET /api/v1/settings/system-status": () => ({ latest: { run_id: "r1", build_sha: "abc1234def", ran_at: new Date().toISOString(), all_ok: false, failed: 1, not_runnable: 1, checks: [
        { check: "Bedrock fieldwork", status: "FAIL" }, { check: "Population LIVE", status: "NOT_RUNNABLE" }, { check: "Sign-in", status: "ok" },
      ] } }),
      "GET /api/v1/settings/error-tracking": () => ({ configured: false, dashboard_url: null, project: null, project_url: null, alerts: [], uptime: [], uptime_enabled: null, issues_7d: [], error: null }),
    });
    render(<SystemPanel mayAdminister />);
    await waitFor(() => expect(document.querySelectorAll("[data-smoke-check]")).toHaveLength(3));
    expect(screen.getByText("1 z 3 připraveno")).toBeTruthy();
    expect(screen.getByText(/sestava abc1234/)).toBeTruthy();
    const failed = document.querySelector('[data-smoke-check="FAIL"]') as HTMLElement;
    expect(within(failed).getByText("Selhalo")).toBeTruthy();
    expect(within(document.querySelector('[data-smoke-check="NOT_RUNNABLE"]') as HTMLElement).getByText("Nešlo ověřit")).toBeTruthy();
    // Coral says a person is awaited: neither a failure nor an unknown check is coral.
    expect(document.querySelector("[data-system-readiness]")?.innerHTML).not.toMatch(/status-you/);
    // No token yet: said, never as an error.
    expect((await screen.findByText(/GlitchTip zatím nemá čtecí klíč/)).closest("[role=alert]")).toBeNull();
  });

  it("says no smoke run is kept, reads a monitor GlitchTip did not report on as unknown, and uptime off as off", async () => {
    fake({
      "GET /api/v1/settings/system-status": () => ({ latest: null }),
      "GET /api/v1/settings/error-tracking": () => ({
        configured: true, dashboard_url: "https://errors.example.test", project: "aia", project_url: null,
        alerts: [{ name: "Nový problém", quantity: 1, timespan_minutes: 5, recipients: 1 }],
        uptime: [{ name: "/health", is_up: null, last_change: null }], uptime_enabled: true,
        issues_7d: [{ title: "TimeoutError", culprit: "worker", count: 3, last_seen: new Date().toISOString(), url: "https://errors.example.test/i/1" }], error: null,
      }),
    });
    render(<SystemPanel mayAdminister />);
    expect(await screen.findByText(/Žádný smoke test po nasazení zatím nebyl uložen/)).toBeTruthy();
    await waitFor(() => expect(document.querySelector("[data-monitor]")?.getAttribute("data-monitor")).toBe("unknown"));
    expect(screen.getByRole("link", { name: "TimeoutError ↗" }).getAttribute("href")).toBe("https://errors.example.test/i/1");
    expect(screen.getByRole("link", { name: "Otevřít GlitchTip ↗" })).toBeTruthy();
    cleanup();
    fake({
      "GET /api/v1/settings/system-status": () => ({ latest: null }),
      "GET /api/v1/settings/error-tracking": () => ({ configured: true, dashboard_url: null, project: null, project_url: null, alerts: [], uptime: [], uptime_enabled: false, issues_7d: [], error: null }),
    });
    render(<SystemPanel mayAdminister />);
    expect(await screen.findByText("Monitorování dostupnosti je vypnuté.")).toBeTruthy();
  });

  it("says GlitchTip could not be read, never that it has no rules or monitors", async () => {
    fake({
      "GET /api/v1/settings/system-status": () => ({ latest: null }),
      "GET /api/v1/settings/error-tracking": () => ({ configured: true, dashboard_url: null, project: "aia", project_url: null, alerts: [], uptime: [], uptime_enabled: true, issues_7d: [], error: "glitchtip_unreachable" }),
    });
    render(<SystemPanel mayAdminister />);
    expect(await screen.findByText("Pravidla upozornění se nepodařilo načíst.")).toBeTruthy();
    expect(screen.getByText("Monitorování dostupnosti se nepodařilo načíst.")).toBeTruthy();
    expect(screen.getByText("Problémy se nepodařilo načíst.")).toBeTruthy();
    expect(screen.queryByText("Žádné pravidlo upozornění.")).toBeNull();
    cleanup();
    fake({
      "GET /api/v1/settings/system-status": () => ({ latest: null }),
      "GET /api/v1/settings/error-tracking": () => ({ configured: true, dashboard_url: null, project: "aia", project_url: null, alerts: [], uptime: [], uptime_enabled: true, issues_7d: [], error: null }),
    });
    render(<SystemPanel mayAdminister />);
    expect(await screen.findByText(/žádný monitor dostupnosti zatím není nastaven/)).toBeTruthy();
  });

  it("says the server's words when the deployment holds several organizations", async () => {
    const shared = () => refuse(409, "deployment_shared", "Stav nasazení a chyby z GlitchTipu patří celému nasazení.");
    fake({ "GET /api/v1/settings/system-status": shared, "GET /api/v1/settings/error-tracking": shared });
    render(<SystemPanel mayAdminister />);
    expect((await screen.findAllByText("Stav nasazení a chyby z GlitchTipu patří celému nasazení.")).length).toBe(2);
    // A shared deployment is a fact, not a fault (F12): no alert, nothing red.
    expect(screen.queryByRole("alert")).toBeNull();
    const sharedNotes = document.querySelectorAll("[data-deployment-shared]");
    expect(sharedNotes.length).toBe(2);
    for (const n of sharedNotes) expect(n.className).not.toMatch(/status-fault/);
  });
});

const CLIENTS = { ok: true as const, data: [{ client_id: "CLI-a", slug: "a", name: "Kavárny Lípa", status: "ACTIVE", reference: "", study_count: 3, created_at: null }] };
const PREVIEW = {
  client_id: "CLI-a", name: "Kavárny Lípa", status: "ACTIVE",
  deleted: { studies: 3, working_revisions: 4, knowledge_items: 12, sources: 5, files: 9, runs: 2, artifacts: 30 },
  kept: { usage_rows: 400, approval_rows: 7, audit_rows: 80 },
  remains_until_sdl2: { population_children: 1, replaced_source_readings: null },
  confirm_token: "tok-1", expires_at: new Date(Date.now() + 600_000).toISOString(),
};

describe("Správa dat", () => {
  const openDialog = async () => {
    // The client is one segmented bar (prototype v51); nothing is chosen at first.
    const pick = await screen.findByRole("radiogroup", { name: "Klient" });
    expect(within(pick).getAllByRole("radio").every((r) => r.getAttribute("aria-checked") === "false")).toBe(true);
    expect((screen.getByRole("button", { name: "Smazat klienta…" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(within(pick).getByRole("radio", { name: "Kavárny Lípa" }));
    fireEvent.click(screen.getByRole("button", { name: "Smazat klienta Kavárny Lípa…" }));
    return waitFor(() => {
      const d = document.querySelector("[data-client-delete-dialog]") as HTMLElement | null;
      if (!d) throw new Error("no dialog");
      return d;
    });
  };

  it("draws the deletion as prototype v99: a danger button, Smaže se / Zůstane in the open, help behind ⓘ (F12)", async () => {
    fake({ "GET /api/v1/settings/kept-records": () => [] });
    render(<DataPanel mayAdminister clients={CLIENTS} reload={() => {}} />);
    const pick = await screen.findByRole("radiogroup", { name: "Klient" });
    // Nothing chosen: no inline lists yet.
    expect(document.querySelector("[data-delete-inline]")).toBeNull();
    fireEvent.click(within(pick).getByRole("radio", { name: "Kavárny Lípa" }));
    const inline = document.querySelector("[data-delete-inline]") as HTMLElement;
    expect(within(inline).getByRole("heading", { name: /Smaže se/ })).toBeTruthy();
    expect(within(inline).getByRole("heading", { name: /Zůstane/ })).toBeTruthy();
    expect(inline.textContent).toContain("Studie");
    expect(inline.textContent).toContain("Záznamy útraty AI");
    // What stays until SDL2 is listed in the open too, not only in the confirmation.
    expect(within(inline).getByRole("heading", { name: "Zůstává do SDL2" })).toBeTruthy();
    expect(inline.querySelector("[data-inline-until-sdl2]")?.querySelectorAll("li").length).toBe(2);
    // No emoji anywhere (design brief §5): the danger button and Smaže se draw the set's trash icon.
    expect(document.body.textContent).not.toMatch(/\p{Extended_Pictographic}/u);
    // The one destructive action is fault-toned, apart from every other button; so is "Nelze vrátit".
    const del = screen.getByRole("button", { name: "Smazat klienta Kavárny Lípa…" });
    expect(del.hasAttribute("data-danger")).toBe(true);
    expect(del.className).toContain("text-status-fault");
    expect(document.querySelector("[data-irreversible]")?.className).toContain("status-fault");
    // Each card's help behind its ⓘ; the cards are h2s.
    for (const [label, id] of [["Jak se klient maže", "data-del-about"], ["Co jsou uchovávané záznamy", "data-kept-about"]] as const) {
      const info = screen.getByRole("button", { name: label });
      expect((document.getElementById(id) as HTMLElement).hidden).toBe(true);
      fireEvent.click(info);
      expect((document.getElementById(id) as HTMLElement).hidden).toBe(false);
    }
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual(["Smazat klienta", "Uchovávané záznamy"]);
  });

  it("offers a few clients as a segmented bar and more as a select, never a bar of every client (review of #870)", async () => {
    fake({ "GET /api/v1/settings/kept-records": () => [] });
    const client = (i: number) => ({ client_id: `CLI-${i}`, slug: `c${i}`, name: `Klient ${i}`, status: "ACTIVE", reference: "", study_count: 0, created_at: null });
    const five = { ok: true as const, data: [1, 2, 3, 4, 5].map(client) };
    const { unmount } = render(<DataPanel mayAdminister clients={five} reload={() => {}} />);
    const bar = await screen.findByRole("radiogroup", { name: "Klient" });
    expect(within(bar).getAllByRole("radio")).toHaveLength(5);
    expect(screen.queryByRole("combobox")).toBeNull();
    unmount();
    const thirty = { ok: true as const, data: Array.from({ length: 30 }, (_, i) => client(i + 1)) };
    render(<DataPanel mayAdminister clients={thirty} reload={() => {}} />);
    const pick = await screen.findByRole("combobox", { name: "Klient" });
    expect(screen.queryByRole("radiogroup", { name: "Klient" })).toBeNull();
    expect(within(pick).getAllByRole("option")).toHaveLength(31);
    expect((screen.getByRole("button", { name: "Smazat klienta…" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(pick, { target: { value: "CLI-17" } });
    expect(screen.getByRole("button", { name: "Smazat klienta Klient 17…" })).toBeTruthy();
  });

  it("shows what is deleted and what stays, unknown as nezjištěno, and deletes only once acknowledged, with the server's token", async () => {
    fake({
      "POST /api/v1/clients/CLI-a/deletion": () => PREVIEW,
      "DELETE /api/v1/clients/CLI-a": () => ({ client_id: "CLI-a", already_deleted: false, deleted: {}, objects_deleted: 9, objects_failed: 0 }),
      "GET /api/v1/settings/kept-records": () => [],
    });
    const reload = vi.fn();
    render(<DataPanel mayAdminister clients={CLIENTS} reload={reload} />);
    const dialog = await openDialog();
    expect(within(dialog.querySelector("[data-will-delete]") as HTMLElement).getByText("12")).toBeTruthy();
    expect(within(dialog.querySelector("[data-will-stay]") as HTMLElement).getByText("400")).toBeTruthy();
    expect(within(dialog.querySelector("[data-until-sdl2]") as HTMLElement).getByText("nezjištěno")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "Smazat klienta" }));
    expect(within(dialog).getByRole("alert").textContent).toMatch(/nelze vrátit/);
    expect(calls.filter((c) => c.method === "DELETE")).toEqual([]);
    fireEvent.click(within(dialog).getByRole("switch", { name: "Rozumím, že smazání nelze vrátit." }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Smazat klienta" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "DELETE")).toHaveLength(1));
    expect(calls.find((c) => c.method === "DELETE")?.body).toEqual({ confirm_token: "tok-1" });
    expect(await screen.findByText(/Klient Kavárny Lípa je smazán/)).toBeTruthy();
    expect(reload).toHaveBeenCalled();
  });

  it("names the runs that still run, and says files still waiting are retried by a repeat", async () => {
    let tries = 0;
    fake({
      "POST /api/v1/clients/CLI-a/deletion": () => PREVIEW,
      "DELETE /api/v1/clients/CLI-a": () => (++tries === 1
        ? refuse(409, "client_has_active_work", "Klient má běhy, které neskončily: nejdřív je zrušte.", { run_ids: ["RUN-1", "RUN-2"] })
        : tries === 2 ? { client_id: "CLI-a", already_deleted: false, deleted: {}, objects_deleted: 7, objects_failed: 2 }
        : { client_id: "CLI-a", already_deleted: true, deleted: {}, objects_deleted: 2, objects_failed: 0 }),
      "GET /api/v1/settings/kept-records": () => [],
    });
    render(<DataPanel mayAdminister clients={CLIENTS} reload={() => {}} />);
    const dialog = await openDialog();
    fireEvent.click(within(dialog).getByRole("switch", { name: "Rozumím, že smazání nelze vrátit." }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Smazat klienta" }));
    expect(await within(dialog).findByText(/RUN-1, RUN-2/)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "Smazat klienta" }));
    expect(await screen.findByText(/2 souborů ještě čeká na smazání/)).toBeTruthy();
    // The client has left the list: the retry is offered here, with the same token.
    fireEvent.click(screen.getByRole("button", { name: "Zkusit smazat soubory znovu" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "DELETE")).toHaveLength(3));
    expect(calls.filter((c) => c.method === "DELETE")[2].body).toEqual({ confirm_token: "tok-1" });
    expect(await screen.findByText(/Klient Kavárny Lípa je smazán/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Zkusit smazat soubory znovu" })).toBeNull();
  });

  it("says a client already deleted no longer exists and reloads the list, never that deletion is not in AIA", async () => {
    fake({
      "POST /api/v1/clients/CLI-a/deletion": () => refuse(404, "not_found", "No such client."),
      "GET /api/v1/settings/kept-records": () => [],
    });
    const reload = vi.fn();
    render(<DataPanel mayAdminister clients={CLIENTS} reload={reload} />);
    fireEvent.click(within(await screen.findByRole("radiogroup", { name: "Klient" })).getByRole("radio", { name: "Kavárny Lípa" }));
    fireEvent.click(screen.getByRole("button", { name: "Smazat klienta Kavárny Lípa…" }));
    expect(await screen.findByText("Klient už neexistuje; seznam je obnovený.")).toBeTruthy();
    expect(reload).toHaveBeenCalled();
    expect(document.querySelector("[data-client-delete] [data-not-yet]")).toBeNull();
  });

  it("reads the kept records again after a client is deleted", async () => {
    let deletedClients = 0;
    fake({
      "POST /api/v1/clients/CLI-a/deletion": () => PREVIEW,
      "DELETE /api/v1/clients/CLI-a": () => { deletedClients += 1; return { client_id: "CLI-a", already_deleted: false, deleted: {}, objects_deleted: 9, objects_failed: 0 }; },
      "GET /api/v1/settings/kept-records": () => [{ record: "deleted_clients", count: deletedClients, kept_for: "indefinite", why: "x" }],
    });
    render(<DataPanel mayAdminister clients={CLIENTS} reload={() => {}} />);
    const count = () => (document.querySelector('[data-kept="deleted_clients"] td:nth-child(2)') as HTMLElement | null)?.textContent;
    await waitFor(() => expect(count()).toBe("0"));
    const dialog = await openDialog();
    fireEvent.click(within(dialog).getByRole("switch", { name: "Rozumím, že smazání nelze vrátit." }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Smazat klienta" }));
    await waitFor(() => expect(count()).toBe("1"));
  });

  it("lists the kept records in words, and says not in AIA yet without the routes", async () => {
    fake({ "GET /api/v1/settings/kept-records": () => [{ record: "usage_rows", count: 4812, kept_for: "indefinite", why: "each model call's tokens and cost" }] });
    render(<DataPanel mayAdminister clients={CLIENTS} reload={() => {}} />);
    const row = await waitFor(() => {
      const r = document.querySelector('[data-kept="usage_rows"]') as HTMLElement | null;
      if (!r) throw new Error("no row");
      return r;
    });
    expect(within(row).getByText("Útrata AI")).toBeTruthy();
    expect(within(row).getByText("4 812")).toBeTruthy();
    expect(within(row).getByText("bez lhůty")).toBeTruthy();
    cleanup();
    fake({});
    render(<DataPanel mayAdminister clients={CLIENTS} reload={() => {}} />);
    expect(await screen.findByText("V AIA zatím není")).toBeTruthy();
  });
});
