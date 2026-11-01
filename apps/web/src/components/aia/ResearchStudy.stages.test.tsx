// @vitest-environment jsdom
// Moving between a study's stages swaps the stage's body and nothing else (research-lead-workbench
// 34): the Lead's conversation, the split, the header and the stage navigator are the study's, drawn
// once in its layout, so a stage change neither remounts the Lead (its draft, scroll and cards) nor
// reads the study, its working copy or the Lead again. Before, each stage was a page of its own and
// every click read the whole study back (24 requests, the Lead's pane drawn anew).
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetConfigCache } from "@/lib/auth";
import { ResearchSession, resetWorkbenchSwitch } from "../rehome/research/ResearchScreen";
import { StudyFrameProvider } from "../rehome/research/frame";
import { TEST_FRAME } from "../rehome/research/test-frame";
import { CONTENT_PATH, EMPTY_PROJECT, signedIn } from "../rehome/research/test-workspace";
import { ResearchStage, ResearchStages } from "./ResearchStudy";

const nav = vi.hoisted(() => ({ segment: "brief" as string | null, push: vi.fn() }));
vi.mock("next/navigation", () => ({
  usePathname: () => `/app/clients/CLI-1/research/STU-1/${nav.segment ?? ""}`,
  useRouter: () => ({ replace: vi.fn(), push: nav.push }),
  useSelectedLayoutSegment: () => nav.segment,
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
}));

const urls: string[] = [];
function api() {
  urls.length = 0;
  vi.stubGlobal("matchMedia", (q: string) => ({ matches: q.includes("min-width: 1100px"), media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url).split("?")[0];
    const method = init?.method ?? "GET";
    urls.push(`${method} ${u}`);
    const answer =
      u === "/config" ? { apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", workbench: true }
      : u === CONTENT_PATH && method === "GET" ? { study_id: "STU-1", state: "NATIVE", revision: 2, revision_id: "REV-2", content: { title: "Alfa" }, analysis: null, template: EMPTY_PROJECT, saved_at: null, saved_by: null, can_edit: true, lineage: {} }
      : u.endsWith("/research/readiness") ? { design_revision_id: "REV-2", revision: 2, ready: false, checks: [], questions: 0, batteries: 0, objects: 0, n: 0, rules: "test", fieldwork_source: "ai_runtime" }
      : u.endsWith("/research/runs") ? { items: [] }
      : u.endsWith("/research/agent-jobs") ? []
      : u === "/api/v1/lead" ? { hatched: true, lead: { lead_id: "L", name: "Bára", hatched_at: "", updated_at: "", files: { soul: "", user: "" }, memories: [] } }
      : u.endsWith("/lead") ? { available: true, unavailable_reason: null, busy: false, turns: [] }
      : null;
    return answer === null
      ? new Response(JSON.stringify({ code: "not_found", message: "not here" }), { status: 404 })
      : new Response(JSON.stringify(answer), { status: 200 });
  }));
}

beforeEach(() => {
  resetWorkbenchSwitch();
  resetConfigCache();
  signedIn();
  nav.segment = "brief";
  api();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const count = (entry: string) => urls.filter((u) => u === entry).length;
const study = () => (
  <StudyFrameProvider frame={TEST_FRAME}>
    <ResearchSession studyId="STU-1">
      <ResearchStages />
    </ResearchSession>
  </StudyFrameProvider>
);
const title = () => document.querySelector(".arthead__title")?.textContent;

describe("a study's stages in one workbench", () => {
  it("keeps the Lead's pane, its draft and the study's reads when the stage changes", async () => {
    const { rerender } = render(study());
    await screen.findByText("Bára");
    const composer = await waitFor(() => {
      const c = document.getElementById("composer") as HTMLTextAreaElement | null;
      expect(c).not.toBeNull();
      return c as HTMLTextAreaElement;
    });
    fireEvent.change(composer, { target: { value: "Rozepsaná zpráva" } });
    const workbench = document.querySelector("[data-workbench]");
    const reads = {
      lead: count("GET /api/v1/studies/STU-1/lead"),
      me: count("GET /api/v1/lead"),
      content: count(`GET ${CONTENT_PATH}`),
      study: count("GET /api/v1/studies/STU-1"),
    };
    expect(reads.content).toBe(1);

    for (const [segment, label] of [["questionnaire", "Dotazník"], ["audience", "Cílová skupina"], ["brief", "Zadání"]] as const) {
      nav.segment = segment;
      await act(async () => rerender(study()));
      await waitFor(() => expect(title()).toBe(label));
      expect(document.querySelector("[data-workbench]")).toBe(workbench);
      expect(document.getElementById("composer")).toBe(composer);
      expect(composer.value).toBe("Rozepsaná zpráva");
    }
    expect(count("GET /api/v1/studies/STU-1/lead")).toBe(reads.lead);
    expect(count("GET /api/v1/lead")).toBe(reads.me);
    expect(count(`GET ${CONTENT_PATH}`)).toBe(1);
    // The runs are the stage's lane, read on each; the study (the budget meter) only when they move.
    expect(count("GET /api/v1/studies/STU-1/research/runs")).toBeGreaterThan(1);
    expect(count("GET /api/v1/studies/STU-1")).toBe(reads.study);
  });

  it("opens another stage's artifact at its top", async () => {
    const { rerender } = render(study());
    await screen.findByText("Bára");
    const body = document.getElementById("artbody")!;
    let top = 480;
    Object.defineProperty(body, "scrollTop", { configurable: true, get: () => top, set: (v: number) => { top = v; } });
    nav.segment = "questionnaire";
    await act(async () => rerender(study()));
    await waitFor(() => expect(title()).toBe("Dotazník"));
    expect(document.getElementById("artbody")).toBe(body);
    expect(top).toBe(0);
  });

  it("draws nothing on the study's own address, which goes on to a stage", async () => {
    nav.segment = null;
    render(study());
    await waitFor(() => expect(count(`GET ${CONTENT_PATH}`)).toBe(1));
    expect(document.querySelector("[data-workbench]")).toBeNull();
  });

  it("still answers an address that names no stage as not found", () => {
    expect(() => render(<ResearchStage slug="neni" />)).toThrow("NEXT_NOT_FOUND");
  });
});
