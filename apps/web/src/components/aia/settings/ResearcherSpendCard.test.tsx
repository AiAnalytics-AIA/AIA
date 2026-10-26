// @vitest-environment jsdom
// "Útrata podle výzkumníka" against a fake API: one row per person with the period's total and
// its parts, the unattributed row named, a researcher's own view said so, the period asked of
// the API, a row opened to its studies, and a malformed answer refused rather than read as zero.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetConfigCache } from "@/lib/auth";
import { ResearcherSpendCard } from "./ResearcherSpendCard";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/app/settings" }));

const fig = (total: number, uncertain = 0, reserved = 0) => ({
  model_usd: total, outside_ledger_usd: 0, total_usd: total, reserved_usd: reserved, uncertain_calls: uncertain,
});
const acts = (lead: number, deep: number) => [
  { activity: "lead", ...fig(lead) },
  { activity: "fieldwork", ...fig(0) },
  { activity: "analysis_report", ...fig(0) },
  { activity: "deep_research", ...fig(deep) },
  { activity: "other", ...fig(0) },
];
const REPORT = (everyone: boolean) => ({
  period: "this_month", start: "2026-10-01T00:00:00Z", end: "2026-10-21T00:00:00Z", everyone, currency: "USD",
  people: [
    {
      user_id: "USR-1", email: "jana@example.test", display_name: "Jana", is_member: true, study_count: 1,
      ...fig(0.5, 0, 2), by_activity: acts(0.1, 0.4),
      studies: [{ study_id: "STU-1", study_name: "Vnímání značky", client_id: "CLI-a", client_name: "Klient A", ...fig(0.5, 0, 2), by_activity: acts(0.1, 0.4) }],
    },
    ...(everyone ? [{
      user_id: null, email: null, display_name: null, is_member: null, study_count: 0,
      ...fig(0, 1), by_activity: acts(0, 0), studies: [],
    }] : []),
  ],
});

let asked: string[] = [];
function api(answer: (url: string) => unknown) {
  asked = [];
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => {
    const u = String(url);
    if (u.endsWith("/config")) return new Response(JSON.stringify(CONFIG), { status: 200 });
    asked.push(u);
    return new Response(JSON.stringify(answer(u)), { status: 200 });
  }));
}

const CONFIG = { cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", apiBase: "", build: { sha: null } };

beforeEach(() => {
  resetConfigCache();
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "owner@example.test", subject: "s" }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); resetConfigCache(); sessionStorage.clear(); });

describe("ResearcherSpendCard", () => {
  it("shows each person's total and parts, and the unattributed row as unknown, never 0", async () => {
    api(() => REPORT(true));
    render(<ResearcherSpendCard />);
    const jana = await screen.findByText("Jana");
    const row = jana.closest("[data-person]") as HTMLElement;
    expect(within(row).getByText("0,50 USD")).toBeTruthy();
    expect(row.querySelector('[data-part="lead"]')?.textContent).toContain("0,10 USD");
    expect(row.querySelector('[data-part="deep_research"]')?.textContent).toContain("0,40 USD");
    expect(row.querySelector('[data-part="fieldwork"]')).toBeNull();
    expect(within(row).getByText("2,00 USD")).toBeTruthy();
    const nobody = document.querySelector('[data-person="__unattributed"]') as HTMLElement;
    expect(within(nobody).getByText("Neznámý")).toBeTruthy();
    expect(within(nobody).getByText("neznámá")).toBeTruthy();
    expect(nobody.textContent).not.toContain("0,00 USD");
    expect(screen.getByText(/Vlastník a správce vidí všechny členy/)).toBeTruthy();
    // The organization's total is the first figure above the table (prototype v51), not a footer.
    expect(screen.queryByText("Organizace celkem")).toBeNull();
    const spent = document.querySelector("[data-org-spend] [data-spend-tile]") as HTMLElement;
    expect(spent.textContent).toMatch(/^ΣUtraceno · tento měsíc/);
  });

  it("draws what each person's spend went on as a stacked bar in the chart palette, never the AI's colour", async () => {
    api(() => REPORT(true));
    render(<ResearcherSpendCard roleOf={(id) => (id === "USR-1" ? "Výzkumník" : null)} />);
    const row = (await screen.findByText("Jana")).closest("[data-person]") as HTMLElement;
    const bar = row.querySelector("[data-activity-bar]") as HTMLElement;
    expect([...bar.children].map((i) => i.className.match(/bg-[\w-]+/)?.[0])).toEqual(["bg-viz-cat-1", "bg-viz-cat-6"]);
    expect(bar.innerHTML).not.toContain("bg-ai");
    expect(within(row).getByText("Výzkumník")).toBeTruthy();
    // The organization's total has a call with no known bill: the share is not known, so not shown.
    expect(row.querySelector("[data-share]")).toBeNull();
  });

  it("names the grey of spend on anything else in the legend whenever a row shows it", async () => {
    api(() => REPORT(false));
    render(<ResearcherSpendCard />);
    await screen.findByText("Jana");
    expect(document.querySelector('[data-legend="other"]')).toBeNull();
    cleanup();
    const report = REPORT(false);
    report.people[0]!.by_activity = report.people[0]!.by_activity.map((a) => (a.activity === "other" ? { ...a, ...fig(0.2) } : a));
    api(() => report);
    render(<ResearcherSpendCard />);
    await screen.findByText("Jana");
    const legend = document.querySelector('[data-legend="other"]') as HTMLElement;
    expect(legend.textContent).toBe("ostatní");
    expect(legend.querySelector(".bg-border-strong")).toBeTruthy();
  });

  it("draws a person's initials from the letters of their name alone, a decomposed name included", async () => {
    const cases: [string, string][] = [
      ["Kurátor (seed)", "KS"],
      ["Šárka Čermáková", "ŠČ"],
      ["Šárka Čermáková".normalize("NFD"), "ŠČ"],
      ["jana.mala@firma.cz", "JM"],
      ["workbench", "W"],
      ["(seed)", "S"],
    ];
    for (const [name, expected] of cases) {
      const report = REPORT(false);
      report.people[0]!.display_name = name;
      api(() => report);
      render(<ResearcherSpendCard />);
      const row = (await screen.findByText(name)).closest("[data-person]") as HTMLElement;
      expect(row.querySelector("[aria-hidden='true']")?.textContent).toBe(expected);
      cleanup();
    }
  });

  it("names each amount under a bar by its activity, visibly, whichever activities a person has", async () => {
    api(() => REPORT(false));
    render(<ResearcherSpendCard />);
    const row = (await screen.findByText("Jana")).closest("[data-person]") as HTMLElement;
    // Jana spent on the Lead and Deep Research only: each amount says which it is in words.
    const shown = [...row.querySelectorAll<HTMLElement>("[data-part]")].map((p) =>
      [...p.childNodes].filter((n) => !(n instanceof HTMLElement && (n.classList.contains("sr-only") || n.getAttribute("aria-hidden") === "true"))).map((n) => n.textContent).join(""));
    expect(shown).toEqual(["Vedoucí 0,10 USD", "Deep Research 0,40 USD"]);
  });

  it("shows a person's share of the organization when its total is known", async () => {
    const report = REPORT(true);
    report.people[1] = { ...report.people[1]!, ...fig(0) };
    api(() => report);
    render(<ResearcherSpendCard />);
    const row = (await screen.findByText("Jana")).closest("[data-person]") as HTMLElement;
    expect(row.querySelector("[data-share]")?.textContent).toBe("100 % organizace");
  });

  it("opens what the ⓘ explains by keyboard or touch, not on hover alone", async () => {
    api(() => REPORT(true));
    render(<ResearcherSpendCard />);
    await screen.findByText("Jana");
    const info = screen.getByRole("button", { name: "Jak se útrata počítá" });
    const about = document.getElementById("researcher-spend-about") as HTMLElement;
    expect(info.getAttribute("aria-expanded")).toBe("false");
    expect(about.hidden).toBe(true);
    fireEvent.click(info);
    expect(info.getAttribute("aria-expanded")).toBe("true");
    expect(about.hidden).toBe(false);
    expect(about.textContent).toContain("Měsíce podle UTC");
  });

  it("asks the API for the period chosen and opens a row to its studies", async () => {
    api(() => REPORT(true));
    render(<ResearcherSpendCard />);
    await screen.findByText("Jana");
    expect(asked.at(-1)).toContain("period=this_month");
    fireEvent.click(screen.getByRole("radio", { name: "Od začátku roku" }));
    await waitFor(() => expect(asked.at(-1)).toContain("period=year_to_date"));
    await screen.findByText("Jana");
    const expander = screen.getByRole("button", { name: "Podle studií: Jana" });
    expect(expander.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(expander);
    expect(expander.getAttribute("aria-expanded")).toBe("true");
    const studies = document.querySelector('[data-person-studies="USR-1"]') as HTMLElement;
    expect(within(studies).getByText("Vnímání značky")).toBeTruthy();
    expect(studies.textContent).toContain("Klient A");
  });

  it("says a researcher sees only their own spend", async () => {
    api(() => REPORT(false));
    render(<ResearcherSpendCard />);
    await screen.findByText("Jana");
    expect(screen.getByText(/Vidíte jen svou vlastní útratu/)).toBeTruthy();
    expect(document.querySelector('[data-person="__unattributed"]')).toBeNull();
    expect(screen.queryByText("Organizace celkem")).toBeNull();
  });

  it("refuses a malformed answer rather than show an empty table", async () => {
    api(() => ({}));
    render(<ResearcherSpendCard />);
    expect(await screen.findByText("Útratu nelze načíst.")).toBeTruthy();
    expect(screen.queryByText("Za toto období nikdo nic neutratil.")).toBeNull();
  });
});
