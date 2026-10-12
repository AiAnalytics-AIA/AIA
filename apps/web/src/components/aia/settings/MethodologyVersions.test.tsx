// @vitest-environment jsdom
// The Metodika tab's versions and editor against a stateful fake of the four version routes,
// serving the API's own catalogue and presets (src/lib/fixtures/methodology.json): what is in
// force, an edit checked and stored as a version that says what it changes, a version put in
// force with a reason and back to the code, the domain's problems at the field they name, a
// word where a number was caught before anything is sent, and a member who sees but cannot edit.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetConfigCache } from "@/lib/auth";
import fixture from "@/lib/fixtures/methodology.json";
import { MethodologyPanel } from "./MethodologyPanel";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/app/settings" }));

type Doc = {
  modules: { id: string }[];
  details: Record<string, Record<string, unknown>>;
  presets: Record<string, Record<string, Record<string, unknown>>>;
};
const doc = fixture as unknown as Doc;
type Sent = { method: string; url: string; body: Record<string, unknown> | null };

function fakeApi({ mayAdminister = true, check, compare }: { mayAdminister?: boolean; check?: (body: Record<string, unknown>) => unknown; compare?: unknown } = {}) {
  const sent: Sent[] = [];
  const versions: Record<string, unknown>[] = [];
  const history: Record<string, unknown>[] = [];
  let inForce: number | null = null;
  const now = "2026-10-11T12:00:00Z";
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const full = String(url);
    const method = init?.method ?? "GET";
    const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null;
    sent.push({ method, url: full, body });
    const [u, query] = full.split("?");
    const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
    if (u === "/config") return json({ apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", build: { sha: null } });
    if (u === "/api/v1/methodology") return json(doc.modules);
    const versionsMatch = u.match(/^\/api\/v1\/methodology\/([^/]+)\/(versions|check|activation|compare)$/);
    if (versionsMatch) {
      const [, id, what] = versionsMatch;
      if (what === "versions" && method === "GET") {
        const current = versions.find((v) => v.version_number === inForce);
        return json({
          in_force: current
            ? { origin: "stored", preset: null, version_number: inForce, name: current.name }
            : { origin: "code", preset: "aia-sociomap-3", version_number: null, name: "aia-sociomap-3" },
          may_administer: mayAdminister,
          presets: doc.presets[id],
          versions: [...versions].reverse(),
          history: [...history].reverse(),
        });
      }
      if (what === "compare") return json(compare ?? { valid: true, problems: {}, in_force: "aia-sociomap-3", panels: [] });
      if (what === "check") {
        return json(check?.(body as Record<string, unknown>) ?? { valid: true, problems: {}, not_computed: [], formulas_latex: {} });
      }
      if (what === "versions" && method === "POST") {
        const n = versions.length + 1;
        const name = `${String(body?.base_preset)}+e${n}`;
        const stored = { version_number: n, name, base_preset: body?.base_preset, spec: { ...(body?.spec as object), methodology_version: name }, formulas: body?.formulas, payload_sha256: "a".repeat(64), note: body?.note ?? "", created_by: "U-1", created_at: now };
        versions.push(stored);
        return json(stored, 201);
      }
      if (what === "activation") {
        inForce = (body?.version_number as number | null) ?? null;
        history.push({ activation_id: history.length + 1, version_number: inForce, activated_by: "U-1", reason: body?.reason ?? "", activated_at: now });
        return json({ origin: inForce === null ? "code" : "stored", preset: null, version_number: inForce, name: "" });
      }
    }
    const m = u.match(/^\/api\/v1\/methodology\/([^/]+)$/);
    const byPreset = m ? doc.details[decodeURIComponent(m[1])] : undefined;
    if (!byPreset) return json({ code: "unknown_module", message: "no such module" }, 404);
    const preset = new URLSearchParams(query ?? "").get("preset") ?? Object.keys(byPreset)[0];
    return byPreset[preset] ? json(byPreset[preset]) : json({ code: "unknown_preset", message: "no such preset" }, 404);
  }));
  return { sent };
}

const versionsSection = () =>
  waitFor(() => screen.getByRole("heading", { name: "Verze metodiky" }).closest("section") as HTMLElement);
const found = (selector: string, root: ParentNode = document) =>
  waitFor(() => {
    const element = root.querySelector(selector);
    if (!element) throw new Error(`nothing at ${selector}`);
    const group = element.closest("fieldset");
    if (group?.hidden) fireEvent.change(screen.getByLabelText("Část metodiky k úpravě"), { target: { value: group.getAttribute("data-edit-step") } });
    const disclosure = element.closest("details");
    if (disclosure && !disclosure.open) fireEvent.click(disclosure.querySelector("summary")!);
    return element as HTMLElement;
  });
const editor = () => found("[data-methodology-editor]");
const field = (form: HTMLElement, reference: string) =>
  waitFor(() => {
    const input = form.querySelector(`[data-field="${reference}"]`);
    if (!input) throw new Error(`no field ${reference}`);
    const group = input.closest("fieldset")!;
    if (group.hidden) fireEvent.change(within(form).getByLabelText("Část metodiky k úpravě"), { target: { value: group.getAttribute("data-edit-step") } });
    return input as HTMLInputElement;
  });

beforeEach(() => {
  resetConfigCache();
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "owner@example.test", subject: "s" }));
});
afterEach(() => {
  cleanup();
  resetConfigCache();
  vi.unstubAllGlobals();
});

describe("the methodology's versions", () => {
  it("say the code's preset is in force when nothing is stored", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    const section = await versionsSection();
    expect(within(section).getByText("aia-sociomap-3").closest("[data-in-force]")).not.toBeNull();
    expect(within(section).getByText("z kódu")).toBeTruthy();
    expect(within(section).getByText("Žádná uložená verze: platí metodika z kódu.")).toBeTruthy();
  });

  it("store an edit as a version that says what it changes, put it in force with a reason and back", async () => {
    const { sent } = fakeApi();
    render(<MethodologyPanel />);
    const section = await versionsSection();
    fireEvent.click(within(section).getByRole("button", { name: "Upravit metodiku" }));
    const form = await editor();
    fireEvent.change(await field(form, "terrain.sigma"), { target: { value: "0,3" } });
    fireEvent.change(await field(form, "layout.stress_bands"), { target: { value: "[0.05, 0.1, 0.25]" } });
    fireEvent.change(within(form).getByLabelText("Poznámka k verzi"), { target: { value: "širší kopec" } });
    fireEvent.click(within(form).getByRole("button", { name: "Zkontrolovat a uložit" }));

    await waitFor(() => expect(within(section).getByText("Uloženo jako aia-sociomap-4+e1. V platnosti bude, až ji uvedete.")).toBeTruthy());
    const stored = sent.find((s) => s.method === "POST" && s.url.endsWith("/versions"));
    expect(stored?.body?.base_preset).toBe("aia-sociomap-4"); // the newest preset: its own constants are editable
    expect((stored?.body?.spec as { terrain: { sigma: number } }).terrain.sigma).toBe(0.3);
    expect((stored?.body?.spec as { layout: { stress_bands: number[] } }).layout.stress_bands).toEqual([0.05, 0.1, 0.25]);
    expect(stored?.body?.formulas).toEqual({}); // nothing replaced: no built-in sent as an edit
    expect(sent.filter((s) => s.url.endsWith("/check"))).toHaveLength(1); // checked before stored
    const version = await found('[data-methodology-version="1"]', section);
    expect(within(version).getByText(/layout\.stress_bands.*terrain\.sigma/)).toBeTruthy();

    fireEvent.click(within(version).getByRole("button", { name: "Uvést aia-sociomap-4+e1 v platnost" }));
    const confirm = await found("[data-methodology-activate]", section);
    fireEvent.change(within(confirm).getByLabelText("Důvod (zapíše se do historie)"), { target: { value: "ověřeno" } });
    fireEvent.click(within(confirm).getByRole("button", { name: "Potvrdit" }));
    await waitFor(() => expect(within(section).getByText("uložená verze")).toBeTruthy());
    expect(sent.find((s) => s.method === "PUT")?.body).toEqual({ version_number: 1, reason: "ověřeno" });
    expect(within(section).getByText("— ověřeno", { exact: false })).toBeTruthy();

    fireEvent.click(within(section).getByRole("button", { name: "Vrátit na aia-sociomap-3 z kódu" }));
    const back = await found("[data-methodology-activate]", section);
    fireEvent.click(within(back).getByRole("button", { name: "Potvrdit" }));
    await waitFor(() => expect(within(section).getByText("z kódu")).toBeTruthy());
    expect(sent.filter((s) => s.method === "PUT").at(-1)?.body).toEqual({ version_number: null, reason: "" });
  });

  it("send a replaced formula, show the domain's problems at the field and store nothing", async () => {
    const { sent } = fakeApi({
      check: () => ({
        valid: false,
        problems: { "spec.relation.n_min": "must be at least 5", "formula.f12.kernel.non_increasing_in:d2": "rises with distance", "module": "odd" },
        not_computed: [],
        formulas_latex: {},
      }),
    });
    render(<MethodologyPanel />);
    fireEvent.click(within(await versionsSection()).getByRole("button", { name: "Upravit metodiku" }));
    const form = await editor();
    fireEvent.change(await field(form, "relation.n_min"), { target: { value: "2" } });
    const slot = await found('[data-edit-slot="f12.kernel"]', form);
    fireEvent.change(within(slot).getByRole("textbox"), { target: { value: "h * exp(d2)" } });
    fireEvent.click(within(form).getByRole("button", { name: "Zkontrolovat a uložit" }));

    await waitFor(() => expect(within(form).getByText("must be at least 5")).toBeTruthy());
    expect(within(slot).getByText("non_increasing_in:d2: rises with distance")).toBeTruthy();
    expect(within(form).getByText("module", { exact: false })).toBeTruthy(); // a problem no field shows is said
    expect(within(form).getByText("Kontrola neprošla (3). Nic se neuložilo.")).toBeTruthy();
    const checked = sent.find((s) => s.url.endsWith("/check"))?.body;
    expect(checked?.formulas).toEqual({ "f12.kernel": "h * exp(d2)" });
    expect((checked?.spec as { relation: { n_min: number } }).relation.n_min).toBe(2);
    expect(sent.some((s) => s.method === "POST" && s.url.endsWith("/versions"))).toBe(false);
  });

  it("catch a word where a number was before anything is sent", async () => {
    const { sent } = fakeApi();
    render(<MethodologyPanel />);
    fireEvent.click(within(await versionsSection()).getByRole("button", { name: "Upravit metodiku" }));
    const form = await editor();
    const sigma = await field(form, "terrain.sigma");
    fireEvent.change(sigma, { target: { value: "široký" } });
    fireEvent.click(within(form).getByRole("button", { name: "Zkontrolovat" }));
    await waitFor(() => expect(within(form).getByText("Zadejte číslo (desetinná čárka i tečka).")).toBeTruthy());
    expect(sigma.getAttribute("aria-invalid")).toBe("true");
    expect(sent.some((s) => s.url.endsWith("/check") || s.method === "POST")).toBe(false);
  });

  it("say a replaced formula can be stored but not yet put in force, and draw it", async () => {
    fakeApi({ check: () => ({ valid: true, problems: {}, not_computed: ["f12.kernel"], formulas_latex: { "f12.kernel": "h \\exp\\left(-\\frac{d_2}{2\\sigma^{2}}\\right)" } }) });
    render(<MethodologyPanel />);
    fireEvent.click(within(await versionsSection()).getByRole("button", { name: "Upravit metodiku" }));
    const form = await editor();
    const slot = await found('[data-edit-slot="f12.kernel"]', form);
    fireEvent.change(within(slot).getByRole("textbox"), { target: { value: "h * exp(-d2 / (2 * sigma ** 2))" } });
    fireEvent.click(within(form).getByRole("button", { name: "Zkontrolovat" }));
    await waitFor(() => expect(within(slot).getByText(/zatím ne uvést v platnost/)).toBeTruthy());
    expect(slot.querySelector("math")).not.toBeNull();
    expect(within(form).getByText("Kontrola prošla.")).toBeTruthy();
  });

  it("are shown to a member, who is offered no edit", async () => {
    fakeApi({ mayAdminister: false });
    render(<MethodologyPanel />);
    const section = await versionsSection();
    expect(within(section).getByText(/může vlastník nebo správce organizace/)).toBeTruthy();
    expect(within(section).queryByRole("button", { name: "Upravit metodiku" })).toBeNull();
  });

  it("are not offered for the reference map, which is shown and never edited", async () => {
    fakeApi();
    render(<MethodologyPanel />);
    await versionsSection();
    fireEvent.click(screen.getByRole("button", { name: "Sociomapa: referenční mapa (18.6.6)" }));
    await screen.findByRole("heading", { name: "Váhy respondentů" });
    expect(screen.queryByRole("heading", { name: "Verze metodiky" })).toBeNull();
  });
});

const summary = (stress: number, reliable: number, unknown: number) => ({
  outcome: "MAPPED", not_mappable: null, stress_1: stress, quality: "good",
  status_counts: { reliable, weak: 15 - reliable - unknown, unknown }, effective_n: 36,
});

describe("the comparison with what is in force", () => {
  it("shows per panel what the edit moves and says plainly what it does not", async () => {
    const { sent } = fakeApi({
      compare: {
        valid: true,
        problems: {},
        in_force: "aia-sociomap-3",
        panels: [
          {
            panel: "small", label_cs: "Malý panel", respondents: 36, objects: ["objekt 1", "objekt 2"],
            in_force: summary(0.04, 3, 0), draft: summary(0.04, 1, 4),
            status_changes: [{ a: "objekt 1", b: "objekt 2", in_force: "reliable", draft: "unknown" }],
            shifts: { "objekt 1": 0, "objekt 2": 0 }, alignment_rmsd: 0,
            heights: { "objekt 1": [0.5, 0.5], "objekt 2": [0.4, 0.4] },
            k100: { "objekt 1": [20, 10], "objekt 2": [30, 15] },
            terrain_max_change: 0, terrain_note: null, notes: ["Kontrola porovnává K100 jako bod; interval spočítá až běh."],
          },
        ],
      },
    });
    render(<MethodologyPanel />);
    fireEvent.click(within(await versionsSection()).getByRole("button", { name: "Upravit metodiku" }));
    const form = await editor();
    fireEvent.change(await field(form, "relation.n_min"), { target: { value: "34" } });
    fireEvent.click(within(form).getByRole("button", { name: "Porovnat s metodikou v platnosti" }));

    const panel = await found('[data-compare-panel="small"]', form);
    expect(within(panel).getByText(/objekt 1 – objekt 2: spolehlivý →/)).toBeTruthy();
    expect(within(panel).getByText("neznámý")).toBeTruthy();
    expect(within(panel).getByText("Žádný objekt se neposunul.")).toBeTruthy();
    expect(within(panel).getAllByText("Beze změny.").length).toBe(2); // heights, terrain
    expect(within(panel).getByText(/objekt 1: 20 → 10/)).toBeTruthy();
    expect(within(panel).getByText(/interval spočítá až běh/)).toBeTruthy();
    const body = sent.find((x) => x.url.endsWith("/compare"))?.body;
    expect((body?.spec as { relation: { n_min: number } }).relation.n_min).toBe(34);
    expect(sent.some((x) => x.method === "POST" && x.url.endsWith("/versions"))).toBe(false);
  });

  it("shows a refused edit's problems at its fields instead of a comparison", async () => {
    fakeApi({ compare: { valid: false, problems: { "spec.relation.n_min": "must be at least 4" }, in_force: "", panels: [] } });
    render(<MethodologyPanel />);
    fireEvent.click(within(await versionsSection()).getByRole("button", { name: "Upravit metodiku" }));
    const form = await editor();
    fireEvent.click(within(form).getByRole("button", { name: "Porovnat s metodikou v platnosti" }));
    await waitFor(() => expect(within(form).getByText("must be at least 4")).toBeTruthy());
    expect(form.querySelector("[data-methodology-compare]")).toBeNull();
  });
});

describe("guided methodology editing", () => {
  it("preserves changes across sections, guards preset replacement and cancellation, and warns before leaving", async () => {
    fakeApi(); render(<MethodologyPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Upravit metodiku" }));
    const form = await editor();
    fireEvent.change(await field(form, "terrain.sigma"), { target: { value: "0,35" } });
    fireEvent.change(await field(form, "relation.n_min"), { target: { value: "34" } });
    expect((await field(form, "terrain.sigma")).value).toBe("0,35");
    const unload = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(unload); expect(unload.defaultPrevented).toBe(true);
    fireEvent.change(within(form).getByLabelText("Vycházet z metodiky z kódu"), { target: { value: "aia-sociomap-2" } });
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Ponechat" }));
    expect((await field(form, "terrain.sigma")).value).toBe("0,35");
    fireEvent.click(within(form).getByRole("button", { name: "Zrušit" }));
    fireEvent.click(screen.getByRole("button", { name: "Ponechat" }));
    expect(document.querySelector("[data-methodology-editor]")).toBeTruthy();
    fireEvent.click(within(form).getByRole("button", { name: "Zrušit" }));
    fireEvent.click(screen.getByRole("button", { name: "Zahodit neuložené úpravy" }));
    expect(document.querySelector("[data-methodology-editor]")).toBeNull();
  });

  it("requires confirmation before changing modules while the editor is open", async () => {
    fakeApi(); render(<MethodologyPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Upravit metodiku" }));
    await editor();
    fireEvent.click(screen.getByRole("button", { name: "Sociomapa: referenční mapa (18.6.6)" }));
    fireEvent.click(screen.getByRole("button", { name: "Ponechat" }));
    expect(document.querySelector("[data-methodology-editor]")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Sociomapa: referenční mapa (18.6.6)" }));
    fireEvent.click(screen.getByRole("button", { name: "Zahodit úpravy a přepnout" }));
    expect(await screen.findByRole("heading", { name: "Sociomapa: referenční mapa (18.6.6)" })).toBeTruthy();
    expect(document.querySelector("[data-methodology-editor]")).toBeNull();
  });

  it("invalidates a previous successful check when the parameter changes", async () => {
    const { sent } = fakeApi(); render(<MethodologyPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Upravit metodiku" }));
    const form = await editor();
    fireEvent.click(within(form).getByRole("button", { name: "Zkontrolovat" }));
    expect(await screen.findByText("Kontrola prošla.")).toBeTruthy();
    fireEvent.change(await field(form, "terrain.sigma"), { target: { value: "0,3" } });
    expect(screen.queryByText("Kontrola prošla.")).toBeNull();
    expect(sent.filter((c) => c.url.endsWith("/versions") && c.method === "POST")).toEqual([]);
  });
});
