// @vitest-environment jsdom
// The Metodika tab's versions and editor against a stateful fake of the four version routes,
// serving the API's own catalogue and presets (src/lib/fixtures/methodology.json): what is in
// force, an edit checked and stored as a version that says what it changes, a version put in
// force with a reason and back to the code, the domain's problems at the field they name, a
// word where a number was caught before anything is sent, and a member who sees but cannot edit.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

function fakeApi({ mayAdminister = true, mayEdit = mayAdminister, check, compare }: { mayAdminister?: boolean; mayEdit?: boolean; check?: (body: Record<string, unknown>) => unknown; compare?: unknown } = {}) {
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
            ? { origin: "stored", preset: null, version_number: inForce, name: current.name, register_status: id === "sociomap" ? "INTERNAL_ONLY" : null }
            : { origin: "code", preset: "aia-sociomap-5", version_number: null, name: "aia-sociomap-5", register_status: id === "sociomap" ? "CLIENT_FACING" : null },
          may_administer: mayAdminister,
          may_edit: mayEdit,
          presets: doc.presets[id],
          versions: [...versions].reverse(),
          history: [...history].reverse(),
        });
      }
      if (what === "compare") return json(compare ?? { valid: true, problems: {}, in_force: "aia-sociomap-5", panels: [] });
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
    if (group?.hidden) fireEvent.click(document.querySelector(`[data-edit-step-link="${group.getAttribute("data-edit-step")}"]`)!);
    const disclosure = element.closest("details");
    if (disclosure && !disclosure.open) fireEvent.click(disclosure.querySelector("summary")!);
    return element as HTMLElement;
  });
const editor = () => found("[data-methodology-editor]");
/** An administrator opens on the editor; after a save or a cancel it is one click away. */
async function openEditor() {
  await versionsSection();
  if (!document.querySelector("[data-methodology-editor]")) await openEditor();
}
const field = (form: HTMLElement, reference: string) =>
  waitFor(() => {
    const input = form.querySelector(`[data-field="${reference}"]`);
    if (!input) throw new Error(`no field ${reference} among ${[...form.querySelectorAll("[data-field]")].map((n) => n.getAttribute("data-field")).join(",")} in ${form.isConnected}`);
    const group = input.closest("fieldset")!;
    if (group.hidden) fireEvent.click(form.querySelector(`[data-edit-step-link="${group.getAttribute("data-edit-step")}"]`)!);
    return input as HTMLInputElement;
  });

/** A module's part (settings-redesign 10b): Výpočet, Verze a aktivace, Porovnání or Upravit. */
async function openPart(name: string) {
  fireEvent.click(await screen.findByRole("tab", { name }));
}

/** The tab opens on the module catalogue (fidelity F4): back to it if a module is open, then a card. */
async function openModule(name: string) {
  const back = document.querySelector<HTMLElement>("[data-methodology-back]");
  if (back) fireEvent.click(back);
  fireEvent.click(await within(await screen.findByRole("navigation", { name: "Oblasti metodiky" })).findByRole("button", { name }));
}
/** Opens the object map from the catalogue, as a person's first click on the tab does. */
const openMap = () => openModule("Sociomapa: objektová mapa");

beforeEach(() => {
  // jsdom has no <dialog> modality: the activation is a native dialog (I7b).
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) { this.removeAttribute("open"); };
  resetConfigCache();
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "owner@example.test", subject: "s" }));
});
afterEach(() => {
  cleanup();
  resetConfigCache();
  vi.unstubAllGlobals();
});

describe("the support rules' versions (plan G1d)", () => {
  it("edit a line both ways, a line not checked included, and store the whole specification", async () => {
    const { sent } = fakeApi();
    render(<MethodologyPanel />); await openMap();
    await openModule("Podpora a potlačení: kdy se číslo smí ukázat");
    await openPart("Výpočet");
    await screen.findByRole("heading", { name: "Pravidlo jednotky 18.6.6 (Výsledky)" });
    await versionsSection();
    await openPart("Upravit");
    await openEditor();
    const form = await editor();
    const unchecked = await field(form, "results.n_guard");
    expect(unchecked.value).toBe("null"); // the unit's rule does not check it, and says so
    fireEvent.change(unchecked, { target: { value: "25" } });
    fireEvent.change(await field(form, "results.min_layer_donors"), { target: { value: "10" } });
    fireEvent.change(await field(form, "analysis.min_cell"), { target: { value: "null" } });
    fireEvent.click(within(form).getByRole("button", { name: "Zkontrolovat a uložit" }));

    await waitFor(() => expect(sent.some((s) => s.method === "POST" && s.url.endsWith("/support/versions"))).toBe(true));
    const stored = sent.find((s) => s.method === "POST" && s.url.endsWith("/support/versions"));
    type Rule = Record<string, number | null>;
    const spec = stored?.body?.spec as { results: Rule; analysis: Rule };
    expect(stored?.body?.base_preset).toBe("aia-support-1");
    expect(spec.results).toEqual({ min_cell: null, n_guard: 25, indicative: null, min_layer_donors: 10, indicative_layer_donors: 50 });
    expect(spec.analysis.min_cell).toBeNull();
    expect(spec.analysis.n_guard).toBe(25);
  });
});

describe("the readiness limits (plan V1a2)", () => {
  const preview = [
    { step_id: "sample_size", status: "PASS", message_cs: "n = 12." },
    { step_id: "sample_size", status: "PASS", message_cs: "n = 450." },
    { step_id: "tracked_set", status: "WARN", message_cs: "Značky: 18 položek; doporučeno 4–15." },
    { step_id: "tracked_set", status: "FAIL", message_cs: "Značky: sada potřebuje 3–40 srovnatelných položek, má 41." },
  ];
  it("says what each limit does, reads the rule with the draft's values and previews the check's own lines", async () => {
    const compare = {
      valid: true, problems: {}, in_force: "aia-readiness-1", panels: [],
      readiness: {
        draft: "aia-readiness-1+e1", unchanged: 1, not_assessed: 2,
        studies: [{
          study_id: "S-1", client_id: "C-1", client_name: "Horizont Mobility (fiktivní)", name: "Pilotní vlna", source: "draft", n: 15,
          ready: [false, true], moves: [{ check_id: "sample_size", in_force: "FAIL", draft: "PASS", message: "n = 15." }],
        }],
      },
    };
    fakeApi({ check: () => ({ valid: true, problems: {}, not_computed: [], formulas_latex: {}, preview }), compare });
    render(<MethodologyPanel />); await openMap();
    await openModule("Připravenost studie: kdy lze běh spustit");
    await versionsSection();
    await openEditor();
    const form = await editor();
    const min = await field(form, "sample_size.min");
    const step = min.closest("fieldset") as HTMLElement;
    expect(within(step).getAllByText("zablokuje běh")).toHaveLength(2);
    const reading = step.querySelector("[data-step-reading]") as HTMLElement;
    expect(reading.textContent).toMatch(/20 ≤ n ≤ 10\s000/);
    fireEvent.change(min, { target: { value: "10" } });
    expect(reading.textContent).toMatch(/10 ≤ n ≤ 10\s000/);
    // Before a check the preview says what it will show; after, the lines the code wrote.
    expect(within(step.querySelector("[data-step-preview]") as HTMLElement).getByText(/Po kontrole/)).toBeTruthy();
    fireEvent.click(within(form).getByRole("button", { name: /^Zkontrolovat$/ }));
    await waitFor(() => expect(step.querySelectorAll("[data-preview-status]")).toHaveLength(2));
    expect(within(step).getByText("n = 12.")).toBeTruthy();
    expect(within(step.querySelector("[data-step-keeps]") as HTMLElement).getByText("chybějící n blokuje vždy")).toBeTruthy();

    const set = await field(form, "tracked_set.recommended_max");
    const setStep = set.closest("fieldset") as HTMLElement;
    expect(within(setStep).getAllByText("zablokuje návrh")).toHaveLength(2);
    expect(within(setStep).getAllByText("jen upozorní")).toHaveLength(2);

    fireEvent.click(within(form).getByRole("button", { name: "Porovnat s metodikou v platnosti" }));
    const impact = await found("[data-compare-readiness]");
    const row = impact.querySelector('[data-readiness-study="S-1"]') as HTMLElement;
    expect(within(row).getByRole("link", { name: "Pilotní vlna" }).getAttribute("href")).toBe("/app/clients/C-1/research/S-1");
    expect(within(row).getByText("zablokováno")).toBeTruthy();
    expect(within(row).getByText("lze spustit")).toBeTruthy();
    expect(within(impact).getByText(/změní výsledek kontroly: 1\. Žádná studie se sama nespustí/)).toBeTruthy();
    expect(within(impact).getByText("Další studie beze změny: 1")).toBeTruthy();
  });
});

describe("the aggregation's versions (plan G3b)", () => {
  it("edit a value, the interval's quantiles and an estimator, and store them together", async () => {
    const { sent } = fakeApi();
    render(<MethodologyPanel />); await openMap();
    await openModule("Agregace: z odpovědí odhad s intervalem");
    await versionsSection();
    await openEditor();
    const form = await editor();
    fireEvent.change(await field(form, "top_box"), { target: { value: "3" } });
    const quantiles = await field(form, "bootstrap.quantiles");
    expect(quantiles.value).toBe("[0.025,0.975]");
    fireEvent.change(quantiles, { target: { value: "[0.05, 0.95]" } });
    const slot = await found('[data-edit-slot="agg.top_box"] textarea', form);
    expect((slot as HTMLTextAreaElement).value).toBe("x >= top - (b - 1)"); // the built-in, as computed
    // The box is one estimator; what the aggregate keeps around it is said beside it.
    const kept = form.querySelector('[data-edit-slot="agg.top_box"] [data-kept]') as HTMLElement;
    expect(within(kept).getByText(/Podíl top boxu a jeho interval počítá vážený průměr/)).toBeTruthy();
    fireEvent.change(slot, { target: { value: "x >= top - b + 1" } });
    fireEvent.click(within(form).getByRole("button", { name: "Zkontrolovat a uložit" }));

    await waitFor(() => expect(sent.some((s) => s.method === "POST" && s.url.endsWith("/aggregation/versions"))).toBe(true));
    const stored = sent.find((s) => s.method === "POST" && s.url.endsWith("/aggregation/versions"));
    const spec = stored?.body?.spec as { top_box: number; bootstrap: { quantiles: number[]; reps: number } };
    expect(stored?.body?.base_preset).toBe("aia-aggregate-1");
    expect(spec.top_box).toBe(3);
    expect(spec.bootstrap.quantiles).toEqual([0.05, 0.95]);
    expect(spec.bootstrap.reps).toBe(400); // what was not edited is sent as it was
    expect(stored?.body?.formulas).toEqual({ "agg.top_box": "x >= top - b + 1" }); // only the replaced slot
  });
});

describe("the methodology's versions", () => {
  it("say the code's preset is in force when nothing is stored", async () => {
    fakeApi();
    render(<MethodologyPanel />); await openMap();
    const section = await versionsSection();
    const inForce = section.querySelector("[data-in-force]") as HTMLElement;
    expect(within(inForce).getByText("aia-sociomap-5")).toBeTruthy();
    expect(within(inForce).getByText("z kódu")).toBeTruthy();
    expect(within(section).getByText("Žádná uložená verze: platí metodika z kódu.")).toBeTruthy();
  });

  it("store an edit as a version that says what it changes, put it in force with a reason and back", async () => {
    const { sent } = fakeApi();
    render(<MethodologyPanel />); await openMap();
    const section = await versionsSection();
    await openEditor();
    const form = await editor();
    fireEvent.change(await field(form, "terrain.sigma"), { target: { value: "0,3" } });
    fireEvent.change(await field(form, "relation.n_min"), { target: { value: "12" } });
    fireEvent.change(within(form).getByLabelText("Poznámka k verzi"), { target: { value: "širší kopec" } });
    fireEvent.click(within(form).getByRole("button", { name: "Zkontrolovat a uložit" }));

    await waitFor(() => expect(within(section).getByText("Uloženo jako aia-sociomap-5+e1. V platnosti bude, až ji uvedete.")).toBeTruthy());
    const stored = sent.find((s) => s.method === "POST" && s.url.endsWith("/versions"));
    expect(stored?.body?.base_preset).toBe("aia-sociomap-5"); // the preset in force
    expect((stored?.body?.spec as { terrain: { sigma: number } }).terrain.sigma).toBe(0.3);
    expect((stored?.body?.spec as { relation: { n_min: number } }).relation.n_min).toBe(12);
    expect(stored?.body?.formulas).toEqual({}); // nothing replaced: no built-in sent as an edit
    expect(sent.filter((s) => s.url.endsWith("/check"))).toHaveLength(1); // checked before stored
    const version = await found('[data-methodology-version="1"]', section);
    expect(within(version).getByText(/relation\.n_min.*terrain\.sigma/)).toBeTruthy();

    // The just-saved version is put in force from its confirmation, the one button offering it.
    fireEvent.click(within(section).getByRole("button", { name: "Uvést aia-sociomap-5+e1 v platnost" }));
    const confirm = await found("[data-methodology-activate]", section);
    // Putting an edited Sociomap in force says its maps will be internal, before it is confirmed (PC17).
    expect(confirm.querySelector("[data-sociomap-internal]")).toBeTruthy();
    fireEvent.click(within(confirm).getByRole("radio", { name: "Oprava chyby v metodě" }));
    fireEvent.change(within(confirm).getByLabelText("Poznámka k důvodu"), { target: { value: "ověřeno" } });
    fireEvent.click(within(confirm).getByRole("button", { name: "Aktivovat jako interní" }));
    await waitFor(() => expect(within(section.querySelector("[data-in-force]") as HTMLElement).getByText("uložená verze")).toBeTruthy());
    expect(sent.find((s) => s.method === "PUT")?.body).toEqual({ version_number: 1, reason: "Oprava chyby v metodě: ověřeno" });
    // The module's head moves with it: the edit in force, internal by the register (review of #873).
    const chips = document.querySelector("[data-module-chips]") as HTMLElement;
    await waitFor(() => expect(chips.querySelector("[data-register]")?.getAttribute("data-register")).toBe("INTERNAL_ONLY"));
    expect(within(chips).getByText("V platnosti: aia-sociomap-5+e1")).toBeTruthy();
    expect(within(chips).queryByText("Schváleno pro klienty")).toBeNull();
    expect(within(section).getByText("Oprava chyby v metodě: ověřeno")).toBeTruthy();

    fireEvent.click(within(section).getByRole("button", { name: "Vrátit na aia-sociomap-5 z kódu" }));
    const back = await found("[data-methodology-activate]", section);
    // Back to the code's preset: nothing to warn about.
    expect(back.querySelector("[data-sociomap-internal]")).toBeNull();
    fireEvent.click(within(back).getByRole("radio", { name: "Návrat k výchozí metodě" }));
    fireEvent.click(within(back).getByRole("button", { name: "Vrátit na výchozí" }));
    await waitFor(() => expect(within(section.querySelector("[data-in-force]") as HTMLElement).getByText("z kódu")).toBeTruthy());
    expect(sent.filter((s) => s.method === "PUT").at(-1)?.body).toEqual({ version_number: null, reason: "Návrat k výchozí metodě" });
    // And back: the preset in force, approved for clients, in the head too.
    await waitFor(() => expect(chips.querySelector("[data-register]")?.getAttribute("data-register")).toBe("CLIENT_FACING"));
    expect(within(chips).getByText("V platnosti: aia-sociomap-5")).toBeTruthy();
    // One read of the versions serves the head and the versions' tabs.
    const reads = sent.filter((s) => s.method === "GET" && s.url.endsWith("/sociomap/versions")).length;
    // The catalogue card's, the open module's one (not one each for its head and its tabs), then a
    // re-read after the save, the activation and the return.
    expect(reads).toBe(5);
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
    render(<MethodologyPanel />); await openMap();
    await openEditor();
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
    render(<MethodologyPanel />); await openMap();
    await openEditor();
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
    render(<MethodologyPanel />); await openMap();
    await openEditor();
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
    render(<MethodologyPanel />); await openMap();
    const section = await versionsSection();
    expect(within(section).getByText(/může jen člen se značkou Metodik/)).toBeTruthy();
    expect(within(section).queryByRole("button", { name: "Upravit metodiku" })).toBeNull();
  });

  it("are not offered for a read-only module, which is shown and never edited", async () => {
    fakeApi();
    render(<MethodologyPanel />); await openMap();
    await versionsSection();
    await openModule("Vážení: která váha patří respondentovi a co s neplatnou");
    await screen.findByRole("heading", { name: "Kishovo efektivní n na čtyřech místech" });
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
    render(<MethodologyPanel />); await openMap();
    await openEditor();
    const form = await editor();
    fireEvent.change(await field(form, "relation.n_min"), { target: { value: "34" } });
    fireEvent.click(within(form).getByRole("button", { name: "Porovnat s metodikou v platnosti" }));

    // The comparison is the module's Porovnání (10b): the page moves there.
    await waitFor(() => expect(screen.getByRole("tab", { name: "Porovnání" }).getAttribute("aria-selected")).toBe("true"));
    const panel = await found('[data-compare-panel="small"]');
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

  it("counts a long comparison's seconds and, past 10 s, says it is computing, never a silent wait", async () => {
    fakeApi();
    render(<MethodologyPanel />); await openMap();
    await openEditor();
    const form = await editor();
    // The server takes its time: the comparison answers only when the test lets it.
    const real = globalThis.fetch;
    let answer: (r: Response) => void = () => {};
    vi.stubGlobal("fetch", vi.fn((url: RequestInfo | URL, init?: RequestInit) => String(url).endsWith("/compare") ? new Promise<Response>((r) => { answer = r; }) : real(url, init)));
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      fireEvent.click(within(form).getByRole("button", { name: "Porovnat s metodikou v platnosti" }));
      const status = await within(form).findByText("Porovnávám metodiky…");
      const box = status.closest("[data-operation]") as HTMLElement;
      expect(box.querySelector("[data-elapsed]")).toBeNull();
      await act(async () => { vi.advanceTimersByTime(4000); });
      expect(box.querySelector("[data-elapsed]")?.textContent).toMatch(/^ \d+ s$/);
      expect(box.querySelector("[data-elapsed]")?.getAttribute("aria-hidden")).toBe("true");
      expect(box.querySelector("[data-compare-slow]")).toBeNull();
      await act(async () => { vi.advanceTimersByTime(7000); });
      expect(within(box).getByText(/trvá obvykle kolem 10 s, první po nasazení až minutu/)).toBeTruthy();
      answer(new Response(JSON.stringify({ valid: false, problems: { "spec.relation.n_min": "must be at least 4" }, in_force: "", panels: [] }), { status: 200 }));
      await waitFor(() => expect(within(form).queryByText("Porovnávám metodiky…")).toBeNull());
    } finally {
      vi.useRealTimers();
    }
  });

  it("shows a refused edit's problems at its fields instead of a comparison", async () => {
    fakeApi({ compare: { valid: false, problems: { "spec.relation.n_min": "must be at least 4" }, in_force: "", panels: [] } });
    render(<MethodologyPanel />); await openMap();
    await openEditor();
    const form = await editor();
    fireEvent.click(within(form).getByRole("button", { name: "Porovnat s metodikou v platnosti" }));
    await waitFor(() => expect(within(form).getByText("must be at least 4")).toBeTruthy());
    expect(document.querySelector("[data-methodology-compare]")).toBeNull();
    expect(screen.getByRole("tab", { name: "Upravit" }).getAttribute("aria-selected")).toBe("true");
  });
});

describe("guided methodology editing", () => {
  it("preserves changes across sections, guards preset replacement and cancellation, and warns before leaving", async () => {
    fakeApi(); render(<MethodologyPanel />); await openMap();
    await openEditor();
    const form = await editor();
    fireEvent.change(await field(form, "terrain.sigma"), { target: { value: "0,35" } });
    fireEvent.change(await field(form, "relation.n_min"), { target: { value: "34" } });
    expect((await field(form, "terrain.sigma")).value).toBe("0,35");
    const unload = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(unload); expect(unload.defaultPrevented).toBe(true);
    fireEvent.change(within(form).getByLabelText("Začít od metodiky z kódu"), { target: { value: "aia-sociomap-2" } });
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Ponechat" }));
    expect((await field(form, "terrain.sigma")).value).toBe("0,35");
    fireEvent.click(within(form).getByRole("button", { name: "Zrušit" }));
    fireEvent.click(screen.getByRole("button", { name: "Ponechat" }));
    expect(document.querySelector("[data-methodology-editor]")).toBeTruthy();
    fireEvent.click(within(form).getByRole("button", { name: "Zrušit" }));
    fireEvent.click(screen.getByRole("button", { name: "Zahodit neuložené úpravy" }));
    expect(document.querySelector("[data-methodology-editor]")).toBeNull();
    // A cancelled edit returns to the calculation it was made against (settings-redesign 10b).
    expect(screen.getByRole("tab", { name: "Výpočet" }).getAttribute("aria-selected")).toBe("true");
    // Upravit starts the next edit from what is in force.
    fireEvent.click(screen.getByRole("tab", { name: "Upravit" }));
    expect(await editor()).toBeTruthy();
  });

  it("goes back to the catalogue at once from an untouched editor, and asks first when it holds changes", async () => {
    fakeApi(); render(<MethodologyPanel />); await openMap();
    await openEditor();
    const form = await editor();
    fireEvent.change(await field(form, "terrain.sigma"), { target: { value: "0,35" } });
    expect(screen.queryByRole("navigation", { name: "Oblasti metodiky" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Metodika" }));
    fireEvent.click(screen.getByRole("button", { name: "Ponechat" }));
    expect(document.querySelector("[data-methodology-editor]")).toBeTruthy();
    expect(screen.queryByRole("navigation", { name: "Oblasti metodiky" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Metodika" }));
    fireEvent.click(screen.getByRole("button", { name: "Zahodit úpravy a přepnout" }));
    expect(await screen.findByRole("navigation", { name: "Oblasti metodiky" })).toBeTruthy();
    expect(document.querySelector("[data-methodology-editor]")).toBeNull();
    await openModule("Vážení: která váha patří respondentovi a co s neplatnou");
    expect(await screen.findByRole("heading", { name: "Vážení: která váha patří respondentovi a co s neplatnou" })).toBeTruthy();
  });

  it("shows each step's stage, audit point and place in the computation, and moves along it", async () => {
    fakeApi(); render(<MethodologyPanel />); await openMap();
    await openEditor();
    const form = await editor();
    const outline = form.querySelector("[data-methodology-outline]") as HTMLElement;
    expect(within(outline).getByText("Vztahy mezi objekty")).toBeTruthy();
    expect(within(outline.querySelector("[data-not-yet]") as HTMLElement).getByText("testy při porovnání oblastí (F14)")).toBeTruthy();
    fireEvent.click(form.querySelector('[data-edit-step-link="f6_distance"]')!);
    const step = form.querySelector('[data-edit-step="f6_distance"]') as HTMLElement;
    // The step's number (its stage's and its place there) leads, as in the outline; the audit point is named.
    const number = form.querySelector('[data-edit-step-link="f6_distance"] [data-step-number]')!.textContent!;
    expect(number).toMatch(/^M\d+\.\d+$/);
    expect(step.querySelector("[data-step-stage]")!.textContent).toBe(`${number} · Rozložení na mapě · Původ: audit F6`);
    fireEvent.click(step.querySelector('[data-context="to"] [data-context-link="f6_smacof"]')!);
    expect((form.querySelector('[data-edit-step="f6_smacof"]') as HTMLElement).hidden).toBe(false);
    expect(step.hidden).toBe(true);
    // A step with nothing to edit is named, never a link that would empty the pane.
    fireEvent.click(form.querySelector('[data-edit-step-link="f1_declared_scale"]')!);
    const first = form.querySelector('[data-edit-step="f1_declared_scale"] [data-context="to"]') as HTMLElement;
    expect(first.querySelector('[data-context-name="f11_not_placed"]')).not.toBeNull();
    expect(first.querySelector('[data-context-link="f11_not_placed"]')).toBeNull();
    expect(first.querySelector('[data-context-link="f2_person_minmax"]')).not.toBeNull();
  });

  it("says which part of a step's formula the expression replaces, and what stays code", async () => {
    fakeApi(); render(<MethodologyPanel />); await openMap();
    await openEditor();
    const form = await editor();
    fireEvent.click(form.querySelector('[data-edit-step-link="f3_effective_n"]')!);
    const slot = form.querySelector('[data-edit-slot="f3.effective_n"]') as HTMLElement;
    expect(within(slot).getByRole("textbox", { name: "Upravitelný výraz · Kishovo efektivní n" })).toBeTruthy();
    const kept = slot.querySelector("[data-kept]") as HTMLElement;
    expect(within(kept).getByText(/Výraz nahrazuje jen Kishovu větev/)).toBeTruthy();
  });

  it("numbers each stage by its place in the computation, also when a stage has nothing to edit", async () => {
    fakeApi(); render(<MethodologyPanel />); await openMap();
    await openModule("Odpověď respondenta: od pravděpodobností modelu k odpovědi");
    await versionsSection();
    await openEditor();
    const form = await editor();
    const heads = [...form.querySelectorAll("[data-outline-stage] > p")].map((p) => p.textContent);
    // Pravděpodobnosti od modelu (1) and Losování (3) have nothing to edit; counting only what is
    // shown would read 1 and 2.
    expect(heads).toEqual(expect.arrayContaining(["2Mechanismy odpovědi", "4Styly respondenta"]));
    expect(heads.some((h) => h?.endsWith("Pravděpodobnosti od modelu"))).toBe(false);
  });

  it("invalidates a previous successful check when the parameter changes", async () => {
    const { sent } = fakeApi(); render(<MethodologyPanel />); await openMap();
    await openEditor();
    const form = await editor();
    fireEvent.click(within(form).getByRole("button", { name: "Zkontrolovat" }));
    expect(await screen.findByText("Kontrola prošla.")).toBeTruthy();
    fireEvent.change(await field(form, "terrain.sigma"), { target: { value: "0,3" } });
    expect(screen.queryByText("Kontrola prošla.")).toBeNull();
    expect(sent.filter((c) => c.url.endsWith("/versions") && c.method === "POST")).toEqual([]);
  });
});

describe("the editor a methodologist opens on (product owner, 2026-10-13)", () => {
  it("opens on the editor, with no extra click", async () => {
    fakeApi(); render(<MethodologyPanel />); await openMap();
    const form = await editor();
    // It edits what is in force, aia-sociomap-5, and says so; it saves over that preset itself, not
    // over the first one listed, so no note says it saves over another.
    expect(within(form).getByRole("heading", { name: "Úprava metodiky v platnosti (aia-sociomap-5)" })).toBeTruthy();
    expect(form.querySelector("[data-start-note]")).toBeNull();
    expect((within(form).getByLabelText("Začít od metodiky z kódu") as HTMLSelectElement).selectedOptions[0].textContent).toBe("Metodika v platnosti");
    expect(screen.queryByRole("button", { name: "Upravit metodiku" })).toBeNull();
    // The outline is the calculation in order, every editable step one click away.
    const outline = within(form).getByRole("navigation", { name: "Kroky výpočtu" });
    expect(within(outline).getAllByRole("button").length).toBeGreaterThan(3);
  });

  it("opens the next edit on the stored version in force, with its values", async () => {
    fakeApi(); render(<MethodologyPanel />); await openMap();
    let form = await editor();
    fireEvent.change(await field(form, "terrain.sigma"), { target: { value: "0,3" } });
    fireEvent.click(within(form).getByRole("button", { name: "Zkontrolovat a uložit" }));
    const section = await versionsSection();
    fireEvent.click(await within(section).findByRole("button", { name: "Uvést aia-sociomap-5+e1 v platnost" }));
    const dialog = await found("[data-methodology-activate]", section);
    fireEvent.click(within(dialog).getByRole("radio", { name: "Ověření na pilotní studii" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Aktivovat jako interní" }));
    await waitFor(() => expect(within(section.querySelector("[data-in-force]") as HTMLElement).getByText("uložená verze")).toBeTruthy());
    cleanup();
    render(<MethodologyPanel />); await openMap();
    form = await editor();
    expect(within(form).getByRole("heading", { name: "Úprava metodiky v platnosti (aia-sociomap-5+e1)" })).toBeTruthy();
    expect((await field(form, "terrain.sigma")).value).toBe("0.3"); // stored values are shown as stored
    // A stored version is edited as it is: no note about another preset.
    expect(form.querySelector("[data-start-note]")).toBeNull();
  });

  it("shows the change's place in the safe sequence, and what the draft changes in words", async () => {
    fakeApi(); render(<MethodologyPanel />); await openMap();
    const form = await editor();
    const flow = within(form).getByRole("list", { name: "Postup změny" });
    const state = (key: string) => flow.querySelector(`[data-flow-step="${key}"]`)?.getAttribute("data-state");
    expect(state("edit")).toBe("now");
    expect(state("check")).toBe("todo");
    const decision = within(form).getByRole("complementary", { name: "Dopad a rozhodnutí" });
    expect(within(decision).getByText("Zatím beze změny.")).toBeTruthy();

    fireEvent.change(await field(form, "terrain.sigma"), { target: { value: "0,35" } });
    expect(within(flow).getByText("· 1 změn")).toBeTruthy();
    expect(within(decision).getByText("0,35")).toBeTruthy();
    // The step that holds the change is marked in the outline.
    const link = form.querySelector('[data-edit-step-link] [aria-label="1 změn"]');
    expect(link).not.toBeNull();

    fireEvent.click(within(form).getByRole("button", { name: "Zkontrolovat" }));
    await waitFor(() => expect(state("check")).toBe("done"));
    expect(within(flow).getByText("· prošla")).toBeTruthy();
    expect(state("compare")).toBe("now");
  });

  it("offers to put a just-saved version in force, with a reason, without hunting for it", async () => {
    const { sent } = fakeApi(); render(<MethodologyPanel />); await openMap();
    const form = await editor();
    fireEvent.change(await field(form, "terrain.sigma"), { target: { value: "0,35" } });
    fireEvent.click(within(form).getByRole("button", { name: "Zkontrolovat a uložit" }));
    const section = await versionsSection();
    const offer = await within(section).findByRole("button", { name: "Uvést aia-sociomap-5+e1 v platnost" });
    // Once the list holds the saved version, it still offers one button for it: the confirmation's.
    await found('[data-methodology-version="1"]', section);
    expect(within(section).getAllByRole("button", { name: "Uvést aia-sociomap-5+e1 v platnost" })).toEqual([offer]);
    fireEvent.click(offer);
    const confirm = await found("[data-methodology-activate]", section);
    fireEvent.click(within(confirm).getByRole("radio", { name: "Rozhodnutí vlastníka metody" }));
    fireEvent.change(within(confirm).getByLabelText("Poznámka k důvodu"), { target: { value: "širší kopec" } });
    fireEvent.click(within(confirm).getByRole("button", { name: "Aktivovat jako interní" }));
    await waitFor(() => expect(sent.some((s) => s.url.endsWith("/activation") && (s.body?.version_number as number) === 1)).toBe(true));
  });
});

describe("a module's view (settings-redesign 10b)", () => {
  const tab = (name: RegExp | string) => screen.getByRole("tab", { name });

  it("opens an administrator on Upravit; Výpočet, Verze a aktivace and Porovnání are a tab away, the draft kept", async () => {
    fakeApi();
    render(<MethodologyPanel />); await openMap();
    const form = await editor();
    expect(await screen.findByRole("tablist", { name: "Části modulu" })).toBeTruthy();
    expect(tab("Upravit").getAttribute("aria-selected")).toBe("true");
    fireEvent.change(await field(form, "relation.n_min"), { target: { value: "12" } });
    fireEvent.click(tab("Výpočet"));
    expect(tab("Výpočet").getAttribute("aria-selected")).toBe("true");
    expect(form.closest("[role=tabpanel]")?.hasAttribute("hidden")).toBe(true);
    fireEvent.click(tab("Verze a aktivace"));
    expect(screen.getByRole("heading", { name: "Historie platnosti" })).toBeTruthy();
    fireEvent.click(tab("Upravit"));
    expect((await field(form, "relation.n_min")).value).toBe("12");
  });

  it("shows a member the module read-only: Upravit is the Metodik's, and the member opens on Výpočet", async () => {
    fakeApi({ mayAdminister: false });
    render(<MethodologyPanel />); await openMap();
    await screen.findByRole("tablist", { name: "Části modulu" });
    const edit = tab(/^Upravit · jen Metodik$/);
    expect((edit as HTMLButtonElement).disabled).toBe(true);
    expect(tab("Výpočet").getAttribute("aria-selected")).toBe("true");
    expect(document.querySelector("[data-methodology-editor]")).toBeNull();
    // The editor is the Metodik's: the note says where the mark is granted (Q82, the product owner 2026-10-23).
    expect(screen.getByText(/Značku uděluje vlastník organizace v Nastavení → Přístup a schvalování/)).toBeTruthy();
  });

  it("follows the Metodik mark, not the organization role: an admin without it reads, a marked researcher edits", async () => {
    fakeApi({ mayAdminister: true, mayEdit: false });
    render(<MethodologyPanel />); await openMap();
    await screen.findByRole("tablist", { name: "Části modulu" });
    expect((tab(/^Upravit · jen Metodik$/) as HTMLButtonElement).disabled).toBe(true);
    expect(document.querySelector("[data-methodology-editor]")).toBeNull();
    fireEvent.click(tab("Verze a aktivace"));
    expect(screen.queryByRole("button", { name: /Vrátit na .* z kódu|Upravit z této verze/ })).toBeNull();
    fireEvent.click(tab("Porovnání"));
    expect(screen.queryByText(/Bez úpravy jsou obě strany stejné/)).toBeNull();
    cleanup();
    fakeApi({ mayAdminister: false, mayEdit: true });
    render(<MethodologyPanel />); await openMap();
    expect(await editor()).toBeTruthy();
    expect(tab("Upravit").getAttribute("aria-selected")).toBe("true");
  });

  it("never says both sides are the same while the edit starts from a version not in force", async () => {
    fakeApi();
    render(<MethodologyPanel />); await openMap();
    const form = await editor();
    fireEvent.change(await field(form, "relation.n_min"), { target: { value: "12" } });
    fireEvent.click(within(form).getByRole("button", { name: "Zkontrolovat a uložit" }));
    // e1 is stored, not in force: an edit from it differs from what is in force before a key is pressed.
    fireEvent.click(tab("Verze a aktivace"));
    const version = await found('[data-methodology-version="1"]');
    fireEvent.click(within(version).getByRole("button", { name: "Upravit z této verze" }));
    await editor();
    fireEvent.click(tab("Porovnání"));
    expect(screen.queryByText(/Bez úpravy jsou obě strany stejné/)).toBeNull();
    expect(screen.getByText(/Úpravu jste zatím neporovnali/)).toBeTruthy();
  });

  it("shows Porovnat s platnou's result on Porovnání, and before any comparison says both sides are the same", async () => {
    fakeApi({ compare: { valid: true, problems: {}, in_force: "aia-sociomap-5", panels: [] } });
    render(<MethodologyPanel />); await openMap();
    const form = await editor();
    fireEvent.click(await screen.findByRole("tab", { name: "Porovnání" }));
    expect(screen.getByText(/Bez úpravy jsou obě strany stejné/)).toBeTruthy();
    fireEvent.click(tab("Upravit"));
    fireEvent.change(await field(form, "relation.n_min"), { target: { value: "12" } });
    fireEvent.click(within(form).getByRole("button", { name: "Porovnat s metodikou v platnosti" }));
    await waitFor(() => expect(tab("Porovnání").getAttribute("aria-selected")).toBe("true"));
    expect(screen.getByText("Porovnává se vaše neuložená úprava.")).toBeTruthy();
  });

  it("activates a version in one dialog with a reason chosen as a chip and a note, and sends nothing without a reason", async () => {
    const { sent } = fakeApi();
    render(<MethodologyPanel />); await openMap();
    const form = await editor();
    fireEvent.change(await field(form, "relation.n_min"), { target: { value: "12" } });
    fireEvent.click(within(form).getByRole("button", { name: "Zkontrolovat a uložit" }));
    fireEvent.click(await screen.findByRole("button", { name: "Uvést aia-sociomap-5+e1 v platnost" }));
    const dialog = await found("[data-methodology-activate]");
    // An edited Sociomap is internal until the register approves it: the act says so.
    expect(dialog.querySelector("[data-sociomap-internal]")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "Aktivovat jako interní" }));
    expect(within(dialog).getByRole("alert").textContent).toMatch(/Vyberte důvod/);
    expect(sent.filter((s) => s.method === "PUT")).toEqual([]);
    fireEvent.click(within(dialog).getByRole("radio", { name: "Ověření na pilotní studii" }));
    fireEvent.change(within(dialog).getByLabelText("Poznámka k důvodu"), { target: { value: "studie Lípa" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Aktivovat jako interní" }));
    await waitFor(() => expect(sent.filter((s) => s.method === "PUT")).toHaveLength(1));
    expect(sent.find((s) => s.method === "PUT")?.body).toEqual({ version_number: 1, reason: "Ověření na pilotní studii: studie Lípa" });
    fireEvent.click(tab("Verze a aktivace"));
    const history = await waitFor(() => screen.getByRole("table", { name: "Historie platnosti" }));
    expect(within(history).getByText("Ověření na pilotní studii: studie Lípa")).toBeTruthy();
  });
});
