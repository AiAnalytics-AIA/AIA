// @vitest-environment jsdom
// Profil → Pravidla (D-17, #853): a client's data posture and the ceiling on its studies' wallets,
// read by any member and set by an organization OWNER or ADMIN. An unset posture reads CLASSIFIED,
// never open; no ceiling reads "bez stropu", never 0; opening the client to public research asks first.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { resetConfigCache } from "@/lib/auth";
import { ClientRulesEditor } from "./ClientRules";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/app/clients/CLI-a/profile" }));

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) { this.removeAttribute("open"); };
});

type Rules = { data_posture: "OPEN" | "CLASSIFIED" | null; effective_posture: "OPEN" | "CLASSIFIED"; wallet_ceiling_usd: number | null; set_by: string | null; set_at: string | null };
let calls: { method: string; url: string; body: Record<string, unknown> | null }[] = [];
function fake(get: () => Response | Rules, put?: (body: Record<string, unknown>) => Response | Rules | Promise<Response>) {
  calls = [];
  let rules: Rules | null = null;
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url).split("?")[0];
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : null;
    calls.push({ method, url: u, body });
    if (u === "/config") return new Response(JSON.stringify({ apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", build: { sha: null } }));
    if (u !== "/api/v1/clients/CLI-a/rules") return new Response('{"code":"http_404","message":"Not Found"}', { status: 404 });
    if (method === "GET") { const r = get(); if (!(r instanceof Response)) rules = r; return r instanceof Response ? r : new Response(JSON.stringify(r)); }
    if (put) { const r = await put(body); return r instanceof Response ? r : new Response(JSON.stringify(r)); }
    // The route's own rule: only what is sent changes, null clears.
    const next: Rules = { ...(rules as Rules), ...body, set_by: "USR-1", set_at: new Date().toISOString() };
    next.effective_posture = next.data_posture ?? "CLASSIFIED";
    rules = next;
    return new Response(JSON.stringify(next));
  }));
}
const UNSET: Rules = { data_posture: null, effective_posture: "CLASSIFIED", wallet_ceiling_usd: null, set_by: null, set_at: null };

beforeEach(() => {
  resetConfigCache();
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "owner@example.test", subject: "s" }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); });

describe("a client's rules on its profile", () => {
  it("reads an unset posture as CLASSIFIED and no ceiling as bez stropu, never open or 0", async () => {
    fake(() => UNSET);
    render(<ClientRulesEditor clientId="CLI-a" mayAdminister />);
    const posture = await screen.findByRole("radiogroup", { name: "Postoj dat" });
    expect(within(posture).getByRole("radio", { name: "CLASSIFIED" }).getAttribute("aria-checked")).toBe("true");
    expect(screen.getByText("Nenastaveno: platí CLASSIFIED, dokud ho nezměníte.")).toBeTruthy();
    expect(screen.getByText("Bez stropu: peněženka studie smí nejvýš do rozpočtu studie.")).toBeTruthy();
    expect((screen.getByLabelText("Strop peněženky") as HTMLInputElement).value).toBe("");
    expect(document.body.textContent).not.toMatch(/0,00 USD/);
  });

  it("asks before opening the client to public research, and sends only the posture", async () => {
    fake(() => UNSET);
    render(<ClientRulesEditor clientId="CLI-a" mayAdminister />);
    const posture = await screen.findByRole("radiogroup", { name: "Postoj dat" });
    fireEvent.click(within(posture).getByRole("radio", { name: "OPEN" }));
    const dialog = await waitFor(() => { const d = document.querySelector("[data-posture-open-dialog]"); if (!d) throw new Error("no dialog"); return d as HTMLElement; });
    expect(calls.filter((c) => c.method === "PUT")).toEqual([]);
    fireEvent.click(within(dialog).getByRole("button", { name: "Povolit veřejnou rešerši" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT")).toHaveLength(1));
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ data_posture: "OPEN" });
    await waitFor(() => expect(within(posture).getByRole("radio", { name: "OPEN" }).getAttribute("aria-checked")).toBe("true"));
    // Back to CLASSIFIED is the safe direction: at once, no dialog.
    fireEvent.click(within(posture).getByRole("radio", { name: "CLASSIFIED" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT")).toHaveLength(2));
    expect(calls.filter((c) => c.method === "PUT")[1].body).toEqual({ data_posture: "CLASSIFIED" });
  });

  it("sets the wallet ceiling at the field, clears it to bez stropu, and says a refusal there", async () => {
    let refuse = true;
    fake(() => ({ ...UNSET, wallet_ceiling_usd: 40 }), (body) => {
      if (refuse) { refuse = false; return new Response(JSON.stringify({ code: "forbidden", message: "Jen vlastník nebo správce." }), { status: 403 }); }
      return { ...UNSET, ...body, effective_posture: "CLASSIFIED", set_by: "USR-1", set_at: new Date().toISOString() } as Rules;
    });
    render(<ClientRulesEditor clientId="CLI-a" mayAdminister />);
    const field = await screen.findByLabelText("Strop peněženky") as HTMLInputElement;
    expect(field.value).toBe("40,00");
    fireEvent.change(field, { target: { value: "60" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(await screen.findByText(/Jen vlastník nebo správce/)).toBeTruthy();
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT").at(-1)?.body).toEqual({ wallet_ceiling_usd: 60 }));
    fireEvent.click(await screen.findByRole("button", { name: "Bez stropu" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT").at(-1)?.body).toEqual({ wallet_ceiling_usd: null }));
    expect(await screen.findByText("Bez stropu: peněženka studie smí nejvýš do rozpočtu studie.")).toBeTruthy();
  });

  it("reads a 0 ceiling as a real cap, never as none, for an administrator and a member", async () => {
    fake(() => ({ ...UNSET, wallet_ceiling_usd: 0 }));
    render(<ClientRulesEditor clientId="CLI-a" mayAdminister />);
    expect(((await screen.findByLabelText("Strop peněženky")) as HTMLInputElement).value).toBe("0,00");
    expect(screen.queryByText(/^Bez stropu:/)).toBeNull();
    expect(screen.getByRole("button", { name: "Bez stropu" })).toBeTruthy();
    cleanup();
    fake(() => ({ ...UNSET, wallet_ceiling_usd: 0 }));
    render(<ClientRulesEditor clientId="CLI-a" mayAdminister={false} />);
    expect(await screen.findByText(/^0,00\s*USD$/)).toBeTruthy();
    expect(screen.queryByText(/^Bez stropu:/)).toBeNull();
  });

  it("sends a typed 0 as a cap of 0, never as none", async () => {
    fake(() => UNSET);
    render(<ClientRulesEditor clientId="CLI-a" mayAdminister />);
    const field = await screen.findByLabelText("Strop peněženky") as HTMLInputElement;
    fireEvent.change(field, { target: { value: "0" } });
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT")).toHaveLength(1));
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ wallet_ceiling_usd: 0 });
    await waitFor(() => expect(screen.queryByText(/^Bez stropu:/)).toBeNull());
  });

  it("says a 422 at the field: the API's words, and the stepper unsaved", async () => {
    fake(() => UNSET, () => new Response(JSON.stringify({ code: "validation_error", message: "wallet_ceiling_usd: must be less than 1e9" }), { status: 422 }));
    render(<ClientRulesEditor clientId="CLI-a" mayAdminister />);
    const field = await screen.findByLabelText("Strop peněženky") as HTMLInputElement;
    fireEvent.change(field, { target: { value: "50" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(await screen.findByText(/must be less than 1e9/)).toBeTruthy();
    expect(await screen.findByText(/Neuloženo/)).toBeTruthy();
  });

  it("shows nothing of client A once the page moves to client B, until B's rules are read", async () => {
    const answers: Record<string, Rules> = { "CLI-a": { ...UNSET, data_posture: "OPEN", effective_posture: "OPEN", wallet_ceiling_usd: 40 } };
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => {
      const u = String(url).split("?")[0];
      if (u === "/config") return new Response(JSON.stringify({ apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", build: { sha: null } }));
      const id = u.match(/^\/api\/v1\/clients\/([^/]+)\/rules$/)?.[1];
      // B's read is held: nothing of A may be shown, or sent, in the meantime.
      return id && answers[id] ? new Response(JSON.stringify(answers[id])) : new Promise<Response>(() => {});
    }));
    const { rerender } = render(<ClientRulesEditor clientId="CLI-a" mayAdminister />);
    expect(await screen.findByLabelText("Strop peněženky")).toBeTruthy();
    rerender(<ClientRulesEditor clientId="CLI-b" mayAdminister />);
    expect(screen.queryByRole("radiogroup", { name: "Postoj dat" })).toBeNull();
    expect(screen.queryByLabelText("Strop peněženky")).toBeNull();
    expect(screen.queryByRole("button", { name: "Bez stropu" })).toBeNull();
  });

  it("saves the ceiling one at a time: the field waits for an answer, and the newest value is the one kept", async () => {
    let release: (() => void) | null = null;
    let first = true;
    fake(() => UNSET, (body) => {
      const answer = { ...UNSET, ...body, set_by: "USR-1", set_at: new Date().toISOString() } as Rules;
      if (!first) return answer;
      first = false;
      return new Promise<Response>((resolve) => { release = () => resolve(new Response(JSON.stringify(answer))); });
    });
    render(<ClientRulesEditor clientId="CLI-a" mayAdminister />);
    const field = await screen.findByLabelText("Strop peněženky") as HTMLInputElement;
    fireEvent.change(field, { target: { value: "60" } });
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT")).toHaveLength(1));
    // While the first save is unanswered, the field takes no second one.
    await waitFor(() => expect((screen.getByLabelText("Strop peněženky") as HTMLInputElement).disabled).toBe(true));
    fireEvent.change(screen.getByLabelText("Strop peněženky"), { target: { value: "70" } });
    fireEvent.keyDown(screen.getByLabelText("Strop peněženky"), { key: "Enter" });
    expect(calls.filter((c) => c.method === "PUT")).toHaveLength(1);
    release!();
    await waitFor(() => expect((screen.getByLabelText("Strop peněženky") as HTMLInputElement).disabled).toBe(false));
    const again = screen.getByLabelText("Strop peněženky") as HTMLInputElement;
    fireEvent.change(again, { target: { value: "70" } });
    fireEvent.keyDown(again, { key: "Enter" });
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT")).toHaveLength(2));
    expect(calls.filter((c) => c.method === "PUT").at(-1)?.body).toEqual({ wallet_ceiling_usd: 70 });
    await waitFor(() => expect((screen.getByLabelText("Strop peněženky") as HTMLInputElement).value).toBe("70,00"));
  });

  it("shows a member the rules read-only, and says not in AIA yet without the route", async () => {
    fake(() => ({ data_posture: "OPEN", effective_posture: "OPEN", wallet_ceiling_usd: 25, set_by: "USR-1", set_at: null }));
    render(<ClientRulesEditor clientId="CLI-a" mayAdminister={false} />);
    const posture = await screen.findByRole("radiogroup", { name: "Postoj dat" });
    expect(within(posture).getAllByRole("radio").every((r) => (r as HTMLButtonElement).disabled)).toBe(true);
    expect(screen.queryByLabelText("Strop peněženky")).toBeNull();
    expect(screen.getByText(/25,00\s*USD/)).toBeTruthy();
    expect(screen.getByText("Mění vlastník nebo správce organizace.")).toBeTruthy();
    cleanup();
    fake(() => new Response('{"code":"http_404","message":"Not Found"}', { status: 404 }));
    render(<ClientRulesEditor clientId="CLI-a" mayAdminister />);
    expect(await screen.findByText("V AIA zatím není")).toBeTruthy();
    expect(screen.queryByRole("radiogroup")).toBeNull();
  });

  it("says a refused read once and claims no posture", async () => {
    fake(() => new Response('{"code":"internal","message":"Boom"}', { status: 500 }));
    render(<ClientRulesEditor clientId="CLI-a" mayAdminister />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByRole("radiogroup")).toBeNull();
    expect(document.body.textContent).not.toMatch(/OPEN|CLASSIFIED|bez stropu/i);
  });
});
