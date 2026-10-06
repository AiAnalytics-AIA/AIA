// @vitest-environment jsdom
// The system prompts tab against a fake of the prompt API: what an administrator can read,
// edit, save, compare, put live, return to the code's wording and test -- and that every
// refusal is shown as the API gave it. The fake keeps real state, so a save followed by an
// activation behaves as the server does: a saved version does not run until it is put live.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PromptActive, PromptSlotDetail, PromptSlotSummary, PromptVersion, SettingsDocument } from "@/lib/api";
import { resetConfigCache } from "@/lib/auth";
import type { Part, StudyRow } from "./ControlPanel";
import { SystemPromptsPanel, actionOf } from "./SystemPromptsPanel";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace }), usePathname: () => "/app/settings" }));

const ANALYZE = "aia.research.analyze_brief";
const BUILD = "aia.research.build_questionnaire";
const RESPONDENT = "aia.respondent.block";
const FRAME = "Jsi výzkumný pracovník AIA.\n";

type Slot = { id: string; family: string; wired: boolean; reason: string | null; baseline: string; version: string; literals: string[] };
const SLOTS: Slot[] = [
  { id: ANALYZE, family: "research_agents", wired: true, reason: null, baseline: "Analyzuj problém.\nNesestavuj dotazník.", version: "1", literals: [] },
  { id: BUILD, family: "research_agents", wired: true, reason: null, baseline: "Převeď analýzu na dotazník s {object}.", version: "1", literals: ["{object}"] },
  { id: RESPONDENT, family: "respondent", wired: false, reason: "feeds_a_reuse_fingerprint", baseline: "Jsi respondent.", version: "1", literals: [] },
];

/** The JSON bodies this fake reads; whatever a test sends is checked against the real API's tests. */
type Body = {
  declares_no_client_data?: boolean;
  text: string; note: string; based_on?: string | null; version_number: number | null; reason: string;
  prompt_version?: number; design_revision_id: string; action: string;
};

type Backend = {
  versions: Record<string, PromptVersion[]>;
  active: Record<string, number | null>;
  history: Record<string, { activation_id: number; version_number: number | null; label: string | null; activated_by: string; reason: string; activated_at: string }[]>;
  refuseActivation: boolean;
  jobs: Record<string, { status: string }>;
  /** The deployment's fictional-client list, as the API reports it on a prompt's detail. */
  draftClients: string[];
};
let backend: Backend;
let calls: { method: string; url: string; body: unknown }[] = [];

const sha = (text: string) => `sha-${text.length}-${text.slice(0, 4)}`;
const activeOf = (s: Slot): PromptActive => {
  const n = backend.active[s.id];
  const v = n === null ? undefined : backend.versions[s.id].find((x) => x.version_number === n);
  return v
    ? { version_number: n, label: v.label, origin: "stored", text_sha256: v.text_sha256, activated_by: "USR-1", activated_at: new Date().toISOString(), reason: "" }
    : { version_number: null, label: s.version, origin: "baseline", text_sha256: sha(s.baseline), activated_by: null, activated_at: null, reason: "" };
};
const summary = (s: Slot): PromptSlotSummary => ({
  prompt_id: s.id, family: s.family, wired: s.wired, unwired_reason: s.reason, baseline_version: s.version, baseline_chars: s.baseline.length,
  active: activeOf(s), version_count: backend.versions[s.id].length, latest_number: backend.versions[s.id].at(-1)?.version_number ?? null,
});
const detail = (s: Slot): PromptSlotDetail => ({
  ...summary(s), fixed_prefix: s.wired ? FRAME : "", baseline_text: s.baseline, required_literals: s.literals, max_chars: 200, draft_test_client_ids: backend.draftClients,
  versions: [...backend.versions[s.id]].reverse(), history: [...backend.history[s.id]].reverse(),
});

function fakeApi(overrides: Record<string, (body: Body, m: RegExpMatchArray) => unknown> = {}) {
  backend = {
    versions: Object.fromEntries(SLOTS.map((s) => [s.id, [] as PromptVersion[]])),
    active: Object.fromEntries(SLOTS.map((s) => [s.id, null])),
    history: Object.fromEntries(SLOTS.map((s) => [s.id, []])),
    refuseActivation: false,
    jobs: {},
    draftClients: ["CLI-a"],
  };
  calls = [];
  const refuse = (status: number, code: string, message: string) => new Response(JSON.stringify({ code, message }), { status });
  const routes: [string, RegExp, (body: Body, m: RegExpMatchArray) => unknown][] = [
    ["GET", /^\/config$/, () => ({ apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", build: { sha: null } })],
    ["GET", /^\/api\/v1\/system-prompts$/, () => SLOTS.map(summary)],
    ["GET", /^\/api\/v1\/system-prompts\/([^/]+)$/, (_b, m) => detail(SLOTS.find((s) => s.id === m[1]) as Slot)],
    ["POST", /^\/api\/v1\/system-prompts\/([^/]+)\/versions$/, (b, m) => {
      const slot = SLOTS.find((s) => s.id === m[1]) as Slot;
      const list = backend.versions[slot.id];
      const n = list.length + 1;
      const v: PromptVersion = { version_number: n, label: `e${n}`, text: b.text, text_sha256: sha(b.text), material_sha256: `material-${b.text}`, declared_class: b.declares_no_client_data ? "CLASS_C_INTERNAL" : null, declared_by: b.declares_no_client_data ? "USR-1" : null, declared_at: b.declares_no_client_data ? new Date().toISOString() : null, based_on: b.based_on ?? "baseline", note: b.note, created_by: "USR-1", created_at: new Date().toISOString() };
      list.push(v);
      return v;
    }],
    ["PUT", /^\/api\/v1\/system-prompts\/([^/]+)\/active$/, (b, m) => {
      const slot = SLOTS.find((s) => s.id === m[1]) as Slot;
      if (backend.refuseActivation) return refuse(403, "self_activation_not_allowed", "a prompt version is put live by someone other than its author (organization self-approval is off)");
      backend.active[slot.id] = b.version_number;
      backend.history[slot.id].push({ activation_id: backend.history[slot.id].length + 1, version_number: b.version_number, label: b.version_number === null ? null : `e${b.version_number}`, activated_by: "USR-1", reason: b.reason, activated_at: new Date().toISOString() });
      return activeOf(slot);
    }],
    ["GET", /^\/api\/v1\/studies\/STU-1\/design\/revisions$/, () => ({ items: [
      { revision_id: "REV-1", study_id: "STU-1", revision: 1, content_sha256: "x", parent_revision: null, source_stage: "brief", created_by: "USR-1", created_at: "" },
      { revision_id: "REV-2", study_id: "STU-1", revision: 2, content_sha256: "y", parent_revision: 1, source_stage: "plan", created_by: "USR-1", created_at: "" },
    ] })],
    ["POST", /^\/api\/v1\/studies\/STU-1\/research\/agent-jobs$/, (b) => ({
      run_id: "RUN-1", design_revision_id: b.design_revision_id, action: b.action, status: "COMPLETED", is_terminal: true, needs_attention: false,
      context_sha256: "c", harness_version: "h", prompt_version: b.prompt_version ? `e${b.prompt_version}` : "1", prompt_origin: "stored", created_at: null, steps: [], actual_cost_usd: 0.0123,
    })],
    ["GET", /^\/api\/v1\/studies\/STU-1\/research\/agent-jobs\/RUN-1\/result$/, () => ({ result: { project: {}, proposal: { title: "Návrh z e1" } }, provenance: { agent_id: "a", design_revision_id: "REV-2", context_sha256: "c", status: "PROPOSED" } })],
  ];
  for (const [k, fn] of Object.entries(overrides)) {
    const [method, path] = k.split(" ");
    routes.unshift([method, new RegExp(`^${path.replace(/[/]/g, "\\/")}$`), fn]);
  }
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url).split("?")[0];
    const method = init?.method ?? "GET";
    const body = (init?.body ? JSON.parse(String(init.body)) : null) as Body;
    calls.push({ method, url: u, body });
    for (const [m, re, fn] of routes) {
      const match = u.match(re);
      if (m === method && match) {
        const answer = fn(body, match);
        return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: method === "POST" && u.endsWith("/versions") ? 201 : 200 });
      }
    }
    return new Response("{}", { status: 404 });
  }));
}
/** A version's row, once the list has re-read after a change. */
const versionRow = (key: string) =>
  waitFor(() => {
    const el = document.querySelector(`[data-version="${key}"]`) as HTMLElement | null;
    if (!el) throw new Error(`no row ${key}`);
    return el;
  });
const called = (method: string, url: string) => calls.filter((c) => c.method === method && c.url === url);

const STUDY = (id: string, name: string, kind = "RESEARCH", clientId = "CLI-a") => ({
  study: { study_id: id, client_id: clientId, slug: id, name, kind, status: "ACTIVE", accepts_work: true, your_role: "LEAD", budget_usd: null, spent_usd: null, remaining_usd: null },
  detail: { ok: false, message: "" },
}) as unknown as StudyRow;
const DOC = (may = true) => ({ may_administer: may }) as unknown as SettingsDocument;
const members: Part<{ user_id: string; email: string; display_name: string; is_active: boolean; organization_role: string }[]> = {
  ok: true, data: [{ user_id: "USR-1", email: "owner@example.test", display_name: "", is_active: true, organization_role: "OWNER" }],
};
const clients: Part<{ client_id: string; slug: string; name: string; status: string; reference: string; study_count: number; created_at: null }[]> = {
  ok: true, data: [
    { client_id: "CLI-a", slug: "a", name: "Fiktivní klient", status: "ACTIVE", reference: "", study_count: 1, created_at: null },
    { client_id: "CLI-b", slug: "b", name: "Skutečný klient", status: "ACTIVE", reference: "", study_count: 1, created_at: null },
  ],
};
// STU-2 belongs to a client the deployment does not list as fictional: never offered for a draft.
const studies: Part<StudyRow[]> = {
  ok: true,
  data: [STUDY("STU-1", "Fiktivní studie"), STUDY("STU-9", "Simulace", "SIMULATION"), STUDY("STU-2", "Skutečná studie", "RESEARCH", "CLI-b")],
};

function mount(may = true) {
  render(<SystemPromptsPanel doc={DOC(may)} members={members} clients={clients} studies={studies} />);
}
const editor = async () => (await screen.findByLabelText("Instrukce")) as HTMLTextAreaElement;
const saveButton = () => screen.getByRole("button", { name: "Uložit jako novou verzi" }) as HTMLButtonElement;
async function saveAs(text: string, note = "") {
  const box = await editor();
  fireEvent.change(box, { target: { value: text } });
  if (note) fireEvent.change(screen.getByLabelText("Poznámka k verzi (nepovinná)"), { target: { value: note } });
  fireEvent.click(saveButton());
}

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

describe("the prompt list", () => {
  it("groups prompts by family, marks what runs, and locks what no step reads", async () => {
    fakeApi();
    mount();
    const list = await screen.findByRole("navigation", { name: "Seznam promptů" });
    expect(within(list).getByText("Návrhoví agenti výzkumu")).toBeTruthy();
    expect(within(list).getByText("AI respondent")).toBeTruthy();
    const analyze = list.querySelector(`[data-prompt="${ANALYZE}"]`) as HTMLElement;
    expect(within(analyze).getByText("Základ z kódu")).toBeTruthy();
    const respondent = list.querySelector(`[data-prompt="${RESPONDENT}"]`) as HTMLElement;
    expect(within(respondent).getByText("Zatím nelze upravit")).toBeTruthy();
    // The first prompt an edit can reach is open.
    expect(analyze.getAttribute("aria-current")).toBe("true");
  });

  it("does not ask for or show prompts to a member", async () => {
    fakeApi();
    mount(false);
    expect(screen.getByText(/Systémové prompty vidí a upravuje jen vlastník nebo správce/)).toBeTruthy();
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toEqual([]);
  });

  it("says so when the API does not return a list", async () => {
    fakeApi({ "GET /api/v1/system-prompts": () => ({}) });
    mount();
    expect(await screen.findByText("API nevrátilo seznam promptů.")).toBeTruthy();
  });

  it("sends the signed-in token and nothing else", async () => {
    fakeApi();
    mount();
    await editor();
    expect(calls.map((c) => c.url).sort()).toEqual(["/api/v1/system-prompts", `/api/v1/system-prompts/${ANALYZE}`, "/config"]);
  });
});

describe("a prompt that can be edited", () => {
  it("shows the code's frame as read-only and starts from the text that runs", async () => {
    fakeApi();
    mount();
    expect((await editor()).value).toBe("Analyzuj problém.\nNesestavuj dotazník.");
    const frame = document.querySelector("[data-frame]") as HTMLElement;
    expect(within(frame).getByText(/Kód kolem vaší instrukce \(nelze upravit\)/)).toBeTruthy();
    expect(frame.textContent).toContain("Jsi výzkumný pracovník AIA.");
    expect(frame.querySelector("textarea, input")).toBeNull();
  });

  it("does not offer to save a text that is already a version, or that cannot be saved", async () => {
    fakeApi();
    mount();
    const box = await editor();
    expect(saveButton().disabled).toBe(true);
    expect(screen.getByText(/Tento text už existuje jako Základ z kódu/)).toBeTruthy();
    fireEvent.change(box, { target: { value: "  \n " } });
    expect(screen.getByText("Instrukce je prázdná.")).toBeTruthy();
    expect(saveButton().disabled).toBe(true);
    fireEvent.change(box, { target: { value: "x".repeat(201) } });
    expect(screen.getByText("Instrukce je delší než 200 znaků.")).toBeTruthy();
    expect(saveButton().disabled).toBe(true);
    fireEvent.change(box, { target: { value: "Nový text." } });
    expect(saveButton().disabled).toBe(false);
  });

  it("will not save a build prompt that drops the placeholder its contract names", async () => {
    fakeApi();
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /Sestavení dotazníku/ }));
    const box = await waitFor(async () => {
      const found = (await screen.findByLabelText("Instrukce")) as HTMLTextAreaElement;
      expect(found.value).toContain("{object}");
      return found;
    });
    fireEvent.change(box, { target: { value: "Sestav dotazník bez zástupného znaku." } });
    expect(screen.getByText("Chybí povinný text: {object}")).toBeTruthy();
    expect(saveButton().disabled).toBe(true);
    fireEvent.change(box, { target: { value: "Sestav dotazník; baterie má otázku s {object}." } });
    expect(saveButton().disabled).toBe(false);
  });

  it("saves a trimmed edit as a new version that does not run yet", async () => {
    fakeApi();
    mount();
    await saveAs("  Analyzuj stručně.  ", "kratší");
    expect(await screen.findByText("Uloženo jako e1. Zatím neběží.")).toBeTruthy();
    expect(called("POST", `/api/v1/system-prompts/${ANALYZE}/versions`)[0].body).toEqual({ text: "Analyzuj stručně.", note: "kratší", based_on: "baseline", declares_no_client_data: true });
    const row = await versionRow("v1");
    expect(row.getAttribute("data-running")).toBe("no");
    expect(within(row).getByText("owner@example.test")).toBeTruthy();
    expect(within(row).getByText("kratší")).toBeTruthy();
    // The code's wording still runs.
    expect((document.querySelector('[data-version="baseline"]') as HTMLElement).getAttribute("data-running")).toBe("yes");
    const list = screen.getByRole("navigation", { name: "Seznam promptů" });
    expect(within(list.querySelector(`[data-prompt="${ANALYZE}"]`) as HTMLElement).getByText("Základ z kódu")).toBeTruthy();
  });

  it("shows the API's refusal of a save as given", async () => {
    fakeApi({
      [`POST /api/v1/system-prompts/${ANALYZE}/versions`]: () =>
        new Response('{"code":"concurrent_edit","message":"another version was saved at the same time; reload and save again"}', { status: 409 }),
    });
    mount();
    await saveAs("Jiný text.");
    expect(await screen.findByText(/HTTP 409 · concurrent_edit: another version was saved at the same time/)).toBeTruthy();
  });
});

describe("putting a version live", () => {
  async function savedAndAskedToActivate() {
    await saveAs("Analyzuj stručně.");
    fireEvent.click(await screen.findByRole("button", { name: "Zapnout e1" }));
    return document.querySelector("[data-activation]") as HTMLElement;
  }

  it("says what changes and for whom, then makes it run for new jobs", async () => {
    fakeApi();
    mount();
    const panel = await savedAndAskedToActivate();
    expect(within(panel).getByText(/Od teď poběží místo Základ z kódu verze e1 pro všechny nově zadané úlohy/)).toBeTruthy();
    expect(within(panel).getByText(/Úlohy zadané před touto změnou doběhnou s promptem, se kterým byly zadány/)).toBeTruthy();
    fireEvent.change(within(panel).getByLabelText(/Důvod/), { target: { value: "kratší je lepší" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Potvrdit" }));
    await waitFor(() => expect(called("PUT", `/api/v1/system-prompts/${ANALYZE}/active`)).toHaveLength(1));
    expect(called("PUT", `/api/v1/system-prompts/${ANALYZE}/active`)[0].body).toEqual({ version_number: 1, reason: "kratší je lepší" });
    expect(await screen.findByText("Teď běží: e1.")).toBeTruthy();
    await waitFor(() => expect((document.querySelector('[data-version="v1"]') as HTMLElement).getAttribute("data-running")).toBe("yes"));
    const list = screen.getByRole("navigation", { name: "Seznam promptů" });
    expect(within(list.querySelector(`[data-prompt="${ANALYZE}"]`) as HTMLElement).getByText("Upraveno e1")).toBeTruthy();
    expect(document.querySelector("[data-activation]")).toBeNull();
    fireEvent.click(screen.getByText("Historie zapnutí"));
    const history = document.querySelector("[data-history]") as HTMLElement;
    expect(within(history).getByText("kratší je lepší", { exact: false })).toBeTruthy();
  });

  it("shows the refusal when the author may not put their own version live, and changes nothing", async () => {
    fakeApi();
    mount();
    const panel = await savedAndAskedToActivate();
    backend.refuseActivation = true;
    fireEvent.click(within(panel).getByRole("button", { name: "Potvrdit" }));
    const refusal = await within(panel).findByText(/HTTP 403 · self_activation_not_allowed/);
    expect(refusal.textContent).toContain("someone other than its author");
    expect(backend.active[ANALYZE]).toBeNull();
    const list = screen.getByRole("navigation", { name: "Seznam promptů" });
    expect(within(list.querySelector(`[data-prompt="${ANALYZE}"]`) as HTMLElement).getByText("Základ z kódu")).toBeTruthy();
  });

  it("returns to the code's wording in one confirmed step", async () => {
    fakeApi();
    mount();
    const panel = await savedAndAskedToActivate();
    fireEvent.click(within(panel).getByRole("button", { name: "Potvrdit" }));
    await screen.findByText("Teď běží: e1.");
    fireEvent.click(await screen.findByRole("button", { name: "Vrátit základ z kódu" }));
    const reset = document.querySelector("[data-activation]") as HTMLElement;
    expect(within(reset).getByRole("heading", { name: "Vrátit základ z kódu" })).toBeTruthy();
    fireEvent.click(within(reset).getByRole("button", { name: "Potvrdit" }));
    await waitFor(() => expect(called("PUT", `/api/v1/system-prompts/${ANALYZE}/active`)).toHaveLength(2));
    expect(called("PUT", `/api/v1/system-prompts/${ANALYZE}/active`)[1].body).toEqual({ version_number: null, reason: "" });
    await waitFor(() => expect((document.querySelector('[data-version="baseline"]') as HTMLElement).getAttribute("data-running")).toBe("yes"));
  });
});

describe("the author's declaration", () => {
  it("says, next to the save button, that saving declares the text holds no client data", async () => {
    fakeApi();
    mount();
    await editor();
    expect(document.querySelector("[data-declaration]")?.textContent).toMatch(/Uložením prohlašujete, že text neobsahuje žádné údaje klienta/);
    expect(document.querySelector("[data-declaration]")?.textContent).toMatch(/nikdo další ji schvalovat nemusí/);
  });

  it("sends the declaration with the save, and shows who made it", async () => {
    fakeApi();
    mount();
    await saveAs("Analyzuj stručně.");
    await screen.findByText("Uloženo jako e1. Zatím neběží.");
    expect(called("POST", `/api/v1/system-prompts/${ANALYZE}/versions`)[0].body).toMatchObject({ declares_no_client_data: true });
    await versionRow("v1");
    const approval = document.querySelector("[data-approval]") as HTMLElement;
    fireEvent.click(within(approval).getByText("Třída dat a schválení operátora"));
    const line = approval.querySelector('[data-material="e1"]') as HTMLElement;
    expect(line.textContent).toMatch(/prohlásil\(a\) owner@example\.test/);
    expect(line.querySelector("[data-undeclared]")).toBeNull();
    expect(line.querySelector("code")?.textContent).toBe("material-Analyzuj stručně.");
    expect(approval.textContent).toMatch(/AIA_AI_MATERIAL_CLASSIFICATIONS/);
    expect(approval.textContent).toMatch(/třída C na základě prohlášení autora/);
  });

  it("puts a declared version live without any warning about an operator", async () => {
    fakeApi();
    mount();
    await saveAs("Analyzuj stručně.");
    fireEvent.click(await screen.findByRole("button", { name: "Zapnout e1" }));
    const panel = document.querySelector("[data-activation]") as HTMLElement;
    expect(panel.querySelector("[data-needs-approval]")).toBeNull();
  });

  it("knows the version it just saved before the prompt has been read again", async () => {
    fakeApi();
    // Hold every read of the prompt after the save: the "Zapnout e1" button shows at once, from
    // the save's answer, while the detail it once read the version from is still the old one.
    const served = globalThis.fetch;
    let release!: () => void;
    const held = new Promise<void>((r) => { release = r; });
    let saved = false;
    vi.stubGlobal("fetch", async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url).split("?")[0];
      if (saved && (init?.method ?? "GET") === "GET" && u.startsWith("/api/v1/system-prompts")) await held;
      if (init?.method === "POST" && u.endsWith("/versions")) saved = true;
      return served(url, init);
    });
    mount();
    await saveAs("Analyzuj stručně.");
    fireEvent.click(await screen.findByRole("button", { name: "Zapnout e1" }));
    expect(document.querySelector('[data-version="v1"]')).toBeNull(); // the detail has not been read again
    const panel = document.querySelector("[data-activation]") as HTMLElement;
    expect(panel.querySelector("[data-needs-approval]")).toBeNull();
    fireEvent.click(within(panel).getByRole("button", { name: "Potvrdit" }));
    await screen.findByText("Teď běží: e1.");
    // The editor keeps the text that now runs, not an empty one.
    expect((await editor()).value).toBe("Analyzuj stručně.");
    release();
    await versionRow("v1");
    expect((await editor()).value).toBe("Analyzuj stručně.");
  });

  it("warns only for a version saved before declarations existed", async () => {
    fakeApi();
    mount();
    await saveAs("Stará verze.");
    await screen.findByText("Uloženo jako e1. Zatím neběží.");
    // The server's rows from before declarations carry none.
    for (const v of backend.versions[ANALYZE]) Object.assign(v, { declared_class: null, declared_by: null, declared_at: null });
    cleanup();
    mount();
    await versionRow("v1");
    fireEvent.click(within(await versionRow("v1")).getByRole("button", { name: "Zapnout e1" }));
    const panel = document.querySelector("[data-activation]") as HTMLElement;
    expect(panel.querySelector("[data-needs-approval]")?.textContent).toMatch(/byla uložena bez prohlášení autora/);
    expect(panel.querySelector("[data-needs-approval]")?.textContent).toMatch(/nově zadané úlohy čekají/);
    const approval = document.querySelector("[data-approval]") as HTMLElement;
    fireEvent.click(within(approval).getByText("Třída dat a schválení operátora"));
    expect(approval.querySelector('[data-material="e1"] [data-undeclared]')?.textContent).toBe("bez prohlášení");
  });
});

describe("comparing", () => {
  it("shows added and removed lines, with a word for each as well as a sign", async () => {
    fakeApi();
    mount();
    await saveAs("Analyzuj problém.\nPiš stručně.");
    await screen.findByText("Uloženo jako e1. Zatím neběží.");
    const compare = document.querySelector("[data-compare]") as HTMLElement;
    fireEvent.click(within(compare).getByText("Porovnání verzí"));
    fireEvent.click(within(await versionRow("v1")).getByRole("button", { name: "Porovnat" }));
    const [from, to] = within(compare).getAllByRole("combobox") as HTMLSelectElement[];
    fireEvent.change(from, { target: { value: "baseline" } });
    fireEvent.change(to, { target: { value: "v1" } });
    expect(within(compare).getByText("+1 / −1 řádků")).toBeTruthy();
    const removed = compare.querySelector('[data-diff="del"]') as HTMLElement;
    const added = compare.querySelector('[data-diff="add"]') as HTMLElement;
    expect(removed.textContent).toContain("Nesestavuj dotazník.");
    expect(removed.textContent).toContain("odebráno");
    expect(added.textContent).toContain("Piš stručně.");
    expect(added.textContent).toContain("přidáno");
    fireEvent.change(to, { target: { value: "baseline" } });
    expect(within(compare).getByText("Vybrané texty jsou stejné.")).toBeTruthy();
  });
});

describe("leaving with unsaved changes", () => {
  it("asks before another prompt replaces the editor, and keeps the text if you stay", async () => {
    fakeApi();
    mount();
    const box = await editor();
    fireEvent.change(box, { target: { value: "Rozepsaný text." } });
    expect(screen.getByText("Neuložené změny")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Sestavení dotazníku/ }));
    const guard = await screen.findByRole("alert");
    expect(guard.textContent).toContain("Přepnutím na „Sestavení dotazníku“ se zahodí.");
    fireEvent.click(within(guard).getByRole("button", { name: "Zůstat u úprav" }));
    expect((await editor()).value).toBe("Rozepsaný text.");
    fireEvent.click(screen.getByRole("button", { name: /Sestavení dotazníku/ }));
    fireEvent.click(within(await screen.findByRole("alert")).getByRole("button", { name: "Zahodit změny a přepnout" }));
    await waitFor(async () => expect(((await screen.findByLabelText("Instrukce")) as HTMLTextAreaElement).value).toContain("{object}"));
    expect(screen.queryByText("Neuložené změny")).toBeNull();
  });

  it("does not ask when nothing was changed", async () => {
    fakeApi();
    mount();
    await editor();
    fireEvent.click(screen.getByRole("button", { name: /Sestavení dotazníku/ }));
    expect(screen.queryByRole("alert")).toBeNull();
    await waitFor(async () => expect(((await screen.findByLabelText("Instrukce")) as HTMLTextAreaElement).value).toContain("{object}"));
  });

  it("asks the browser to confirm leaving the page while an edit is unsaved", async () => {
    fakeApi();
    mount();
    fireEvent.change(await editor(), { target: { value: "Rozepsaný text." } });
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
  });
});

describe("a prompt no running step reads", () => {
  it("shows the text and the reason, and offers no editor", async () => {
    fakeApi();
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /AI respondent \(blok otázek\)/ }));
    const locked = await waitFor(() => {
      const el = document.querySelector("[data-locked]") as HTMLElement | null;
      if (!el) throw new Error("not loaded");
      return el;
    });
    expect(within(locked).getByRole("note").textContent).toMatch(/Tento prompt zatím nelze upravit.*otisku/);
    expect(screen.queryByLabelText("Instrukce")).toBeNull();
    expect(screen.queryByRole("button", { name: "Uložit jako novou verzi" })).toBeNull();
    fireEvent.click(within(locked).getByText("Zobrazit text z kódu"));
    expect(locked.textContent).toContain("Jsi respondent.");
  });
});

describe("trying a version", () => {
  async function openTest() {
    await saveAs("Analyzuj stručně.");
    await screen.findByText("Uloženo jako e1. Zatím neběží.");
    fireEvent.click(within(await versionRow("v1")).getByRole("button", { name: "Vyzkoušet" }));
    return (await waitFor(() => {
      const el = document.querySelector("[data-test-run]") as HTMLElement | null;
      if (!el) throw new Error("no panel");
      return el;
    }));
  }

  it("queues an ordinary job pinned to that version and shows what it proposes", async () => {
    fakeApi();
    mount();
    const panel = await openTest();
    expect(within(panel).getByText(/Zkoušet lze jen na klientech, které nasazení označilo za fiktivní/)).toBeTruthy();
    // Only an open research study of a client the deployment lists as fictional is offered:
    // not a simulation, and not another client's study.
    const study = within(panel).getByLabelText("Studie") as HTMLSelectElement;
    expect([...study.options].map((o) => o.textContent)).toEqual(["Fiktivní studie · Fiktivní klient"]);
    expect(panel.textContent).not.toContain("Skutečná studie");
    await waitFor(() => expect((within(panel).getByLabelText("Revize návrhu") as HTMLSelectElement).value).toBe("REV-2")); // the newest
    fireEvent.click(within(panel).getByRole("button", { name: "Zadat zkušební úlohu" }));
    await waitFor(() => expect(called("POST", "/api/v1/studies/STU-1/research/agent-jobs")).toHaveLength(1));
    expect(called("POST", "/api/v1/studies/STU-1/research/agent-jobs")[0].body).toEqual({
      design_revision_id: "REV-2", action: "analyze_brief", instruction: "", prompt_version: 1,
    });
    const job = await waitFor(() => {
      const el = panel.querySelector("[data-job]") as HTMLElement | null;
      if (!el) throw new Error("no job");
      return el;
    });
    expect(job.textContent).toContain("Prompt e1");
    expect(job.textContent).toContain("$0.0123");
    expect(await within(panel).findByText(/Návrh z e1/)).toBeTruthy();
  });

  it("shows the API's refusal when a non-administrator's job is not allowed", async () => {
    fakeApi({
      "POST /api/v1/studies/STU-1/research/agent-jobs": () =>
        new Response('{"code":"prompt_test_requires_administrator","message":"only an organization administrator may test a prompt version"}', { status: 409 }),
    });
    mount();
    const panel = await openTest();
    await waitFor(() => expect((within(panel).getByLabelText("Revize návrhu") as HTMLSelectElement).value).toBe("REV-2"));
    fireEvent.click(within(panel).getByRole("button", { name: "Zadat zkušební úlohu" }));
    expect(await within(panel).findByText(/HTTP 409 · prompt_test_requires_administrator/)).toBeTruthy();
  });

  it("offers no test at all when the deployment lists no fictional client, and says why", async () => {
    fakeApi();
    backend.draftClients = [];
    mount();
    await saveAs("Analyzuj stručně.");
    await screen.findByText("Uloženo jako e1. Zatím neběží.");
    const row = await versionRow("v1");
    expect(within(row).queryByRole("button", { name: "Vyzkoušet" })).toBeNull();
    expect(document.querySelector("[data-test-off]")?.textContent).toMatch(/AIA_AI_FICTIONAL_CLIENT_IDS/);
  });

  it("only offers a test where a job exists to run it", () => {
    expect(actionOf(ANALYZE)).toBe("analyze_brief");
    expect(actionOf("aia.research.nope")).toBeNull();
    expect(actionOf(RESPONDENT)).toBeNull();
  });
});

describe("sending a signed-out person to sign in", () => {
  it("redirects instead of showing a refusal", async () => {
    sessionStorage.clear();
    fakeApi();
    mount();
    await waitFor(() => expect(replace).toHaveBeenCalledWith(expect.stringMatching(/^\/login\?next=/)));
  });
});
