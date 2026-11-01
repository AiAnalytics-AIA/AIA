// @vitest-environment jsdom
// With 18.6.6 out of the product (ADR 0018 decision 4), nothing hands off to it: what
// AIA does not have yet says so where the person meets it, and an old /classic link
// is told the interface is gone. Each test also proves the page asked nothing of the
// unit and offered no way into it.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ClassicRetired from "@/app/classic/page";
import { t, tv } from "@/i18n/t";
import { ClientValue } from "./clients/ClientContext";
import { IntelligencePage, SettingsPage } from "./GlobalPages";
import { SimulationFrame } from "./SimulationFrame";

vi.mock("next/navigation", () => ({ usePathname: () => "/app", useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const CLIENT = {
  client_id: "CLI-a", name: "Klient A", slug: "klient-a", status: "ACTIVE", your_role: "LEAD",
  permissions: ["CREATE_STUDY", "VIEW_CLIENT"],
} as const;

let urls: string[] = [];
beforeEach(() => {
  urls = [];
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "a@example.test" }));
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL) => {
      const u = String(url);
      urls.push(u);
      if (u === "/config") return new Response(JSON.stringify({ apiBase: "", aiRuntime: null }));
      if (u === "/api/v1/workspace/me") return new Response(JSON.stringify({ user_id: "USR-1", email: "a@example.test", organization_role: "MEMBER", may_administer: false }));
      if (u === "/api/v1/population") {
        return new Response(JSON.stringify({ dataset_id: "cz_synthetic_population", contract_id: "c", versions: [], populations: [], history: [] }));
      }
      if (u === "/api/v1/studies/STU-2/workspace") {
        return new Response(JSON.stringify({
          study: { study_id: "STU-2", client_id: "CLI-a", name: "Cenové scénáře", kind: "SIMULATION", status: "ACTIVE" },
          client_name: "Klient A", your_role: "LEAD", can_edit: true, content_state: "EMPTY",
        }));
      }
      return new Response("{}");
    }),
  );
});
afterEach(() => {
  cleanup();
  // Nothing of the unit was asked for, and nothing on the page leads to it.
  expect(urls.filter((u) => !u.startsWith("/api/v1/") && u !== "/config")).toEqual([]);
  expect([...document.querySelectorAll("a")].map((a) => a.getAttribute("href")).filter((h) => h?.startsWith("/classic"))).toEqual([]);
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("what AIA does not have yet", () => {
  it("a simulation says its workflow is not in AIA, and offers no hand-off", async () => {
    render(
      <ClientValue client={CLIENT as never}>
        <SimulationFrame studyId="STU-2" />
      </ClientValue>,
    );
    expect(await screen.findByText(t("aia.simulation.notInAia"))).toBeTruthy();
    expect(screen.getByText(tv("aia.simulation.frameText", { client: "Klient A" }))).toBeTruthy();
    expect(screen.queryByRole("link", { name: /klasick/i })).toBeNull();
  });

  it("a simulation keeps its lifecycle on its frame: the status menu, and a closed one reopened in place (F7)", async () => {
    let status = "DELIVERED";
    const sent: unknown[] = [];
    const base = vi.mocked(fetch);
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      urls.push(u);
      if (u === "/api/v1/studies/STU-2/status" && init?.method === "PUT") {
        sent.push(JSON.parse(String(init.body)));
        status = (sent.at(-1) as { status: string }).status;
        return new Response(JSON.stringify({ study_id: "STU-2", status }));
      }
      if (u === "/api/v1/studies/STU-2/workspace") {
        return new Response(JSON.stringify({
          study: { study_id: "STU-2", client_id: "CLI-a", name: "Cenové scénáře", kind: "SIMULATION", status, accepts_work: !["DELIVERED", "ARCHIVED", "CANCELLED"].includes(status) },
          client_name: "Klient A", your_role: "LEAD", can_edit: true, content_state: "EMPTY",
        }));
      }
      return base(url, init);
    }));
    render(
      <ClientValue client={CLIENT as never}>
        <SimulationFrame studyId="STU-2" />
      </ClientValue>,
    );
    const notice = await waitFor(() => {
      const el = document.querySelector('[data-study-closed="DELIVERED"]') as HTMLElement | null;
      if (!el) throw new Error("no closed notice yet");
      return el;
    });
    expect(screen.getByRole("button", { name: "Stav: Předáno" })).toBeTruthy();
    fireEvent.click(within(notice).getByRole("button", { name: t("aia.study.closed.reopen") }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Aktivní" }));
    await waitFor(() => expect(sent).toEqual([{ status: "ACTIVE" }]));
    expect(await screen.findByRole("button", { name: "Stav: Aktivní" })).toBeTruthy();
    expect(document.querySelector("[data-study-closed]")).toBeNull();
  });

  it("the shared layer says the 18.6.6 Data Library is not in AIA", async () => {
    render(<IntelligencePage />);
    expect(screen.getByText(t("aia.intelligence.notInAia")).getAttribute("role")).toBe("status");
    expect(screen.queryByRole("link", { name: /klasick|Data Library/i })).toBeNull();
    // The population registry beneath it, empty: research answers with fictional respondents.
    expect(await screen.findByText(t("aia.intelligence.population.empty"))).toBeTruthy();
  });

  it("settings offer no way into the classic interface or its project store", async () => {
    render(<SettingsPage />);
    expect(await screen.findByText(t("aia.settings.account"))).toBeTruthy();
    expect(screen.queryByText(/klasick/i)).toBeNull();
    expect(screen.queryByRole("link", { name: /Projekty klasického úložiště|Diagnostika/ })).toBeNull();
  });
});

describe("/classic", () => {
  it("tells an old link the interface is gone, and leads into AIA", () => {
    render(<ClassicRetired />);
    expect(screen.getByRole("heading", { name: t("classic.title") })).toBeTruthy();
    expect(screen.getByText(t("classic.missing"))).toBeTruthy();
    expect(screen.getByRole("link", { name: t("classic.openAia") }).getAttribute("href")).toBe("/app/clients");
  });
});
