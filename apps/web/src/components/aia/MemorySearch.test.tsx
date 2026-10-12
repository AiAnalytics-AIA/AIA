// @vitest-environment jsdom
// Project memory's search on the pages (plans/project-memory-reuse.md M1d): Projektová paměť
// asks for a client first and searches that client alone; each hit says what matched and
// whether it came from a design or a working draft; a short query is not sent.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t, tv } from "@/i18n/t";
import type { MemoryHit } from "@/lib/api";
import { MemoryPage } from "./GlobalPages";
import { MemorySearch } from "./MemorySearch";

vi.mock("next/navigation", () => ({ usePathname: () => "/app/memory", useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const M = "aia.memory";
const CLIENTS = [
  { client_id: "CLI-a", name: "Klient A", slug: "a", status: "ACTIVE", your_role: "RESEARCHER", permissions: [], studies: 2, recent: [] },
  { client_id: "CLI-b", name: "Klient B", slug: "b", status: "ACTIVE", your_role: "RESEARCHER", permissions: [], studies: 1, recent: [] },
];
const HITS: MemoryHit[] = [
  {
    study_id: "STU-1", name: "Ranní káva", kind: "RESEARCH", status: "ACTIVE", modified_at: null, source: "design", design_revision: 2,
    matches: [{ field: "name", texts: ["Ranní káva"] }, { field: "research_questions", texts: ["Kdo pije kávu ráno?"] }],
  },
  {
    study_id: "STU-2", name: "Kávové ceny", kind: "RESEARCH", status: "DRAFT", modified_at: null, source: "draft", design_revision: null,
    matches: [{ field: "title", texts: ["Kávové ceny"] }],
  },
  {
    study_id: "STU-3", name: "Cenový scénář kávy", kind: "SIMULATION", status: "DRAFT", modified_at: null, source: "name", design_revision: null,
    matches: [{ field: "name", texts: ["Cenový scénář kávy"] }],
  },
];

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
      if (u === "/api/v1/workspace/clients") return new Response(JSON.stringify(CLIENTS));
      if (u.startsWith("/api/v1/clients/CLI-a/memory/search")) return new Response(JSON.stringify(HITS));
      return new Response("[]");
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const searches = () => urls.filter((u) => u.includes("/memory/search"));

describe("Projektová paměť", () => {
  it("asks for a client first and searches that client alone", async () => {
    render(<MemoryPage />);
    expect(await screen.findByText(t(`${M}.pickClient`))).toBeTruthy();
    expect(screen.queryByLabelText(t(`${M}.search`))).toBeNull();
    fireEvent.change(screen.getByLabelText(t(`${M}.client`)), { target: { value: "CLI-a" } });
    fireEvent.change(screen.getByLabelText(t(`${M}.search`)), { target: { value: "káva" } });
    expect(await screen.findByText(tv(`${M}.hits`, { n: 3 }))).toBeTruthy();
    expect(searches()).toEqual([`/api/v1/clients/CLI-a/memory/search?q=${encodeURIComponent("káva")}`]);
    expect(screen.getByText(tv(`${M}.source.design`, { revision: 2 }))).toBeTruthy();
    expect(screen.getByText(t(`${M}.source.draft`))).toBeTruthy();
    expect(screen.getByText("Kdo pije kávu ráno?")).toBeTruthy();
    expect(searches().some((u) => u.includes("CLI-b"))).toBe(false);
  });
});

describe("the search box", () => {
  it("sends nothing shorter than two characters", async () => {
    render(<MemorySearch clientId="CLI-a"><p>the list</p></MemorySearch>);
    expect(screen.getByText("the list")).toBeTruthy();
    fireEvent.change(screen.getByLabelText(t(`${M}.search`)), { target: { value: "k" } });
    expect(await screen.findByText(t(`${M}.typeMore`))).toBeTruthy();
    await new Promise((r) => setTimeout(r, 400));
    expect(searches()).toEqual([]);
  });

  it("on Výzkumy shows research hits only", async () => {
    render(<MemorySearch clientId="CLI-a" kind="RESEARCH" />);
    fireEvent.change(screen.getByLabelText(t(`${M}.search`)), { target: { value: "káva" } });
    expect(await screen.findByText(tv(`${M}.hits`, { n: 2 }))).toBeTruthy();
    expect(screen.queryByText("Cenový scénář kávy")).toBeNull();
  });
});
