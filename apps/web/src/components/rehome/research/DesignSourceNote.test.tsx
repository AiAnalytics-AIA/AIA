// @vitest-environment jsdom
// Where a reused study's design came from (project memory M3e): the source study by name and
// revision, a link to it in project memory, and the labels the server recorded; nothing for a
// study whose design was not reused.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t, tv } from "@/i18n/t";
import { DesignSourceNote } from "./DesignSourceNote";

const D = "aia.designSource";
const SOURCE = {
  study_id: "STU-2", revision_id: "REV-9", source_study_id: "STU-1", source_revision_id: "REV-1", source_revision: 3,
  source_content_sha256: "a".repeat(64), created_by: "USR-1", created_at: "2026-10-12T08:00:00Z",
  labels: { synthetic: true, draft: true, never_run: false, unlabelled_data: false, run_ids: ["RUN-1"], report_artifact_ids: ["ART-r"] },
};

function api(routes: Record<string, () => unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL) => {
      const u = String(url);
      if (u === "/config") return new Response(JSON.stringify({ apiBase: "", aiRuntime: null }));
      const answer = routes[u];
      return answer ? new Response(JSON.stringify(answer())) : new Response(JSON.stringify({ code: "not_found" }), { status: 404 });
    }),
  );
}

beforeEach(() => {
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "a@example.test" }));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("a reused design's source", () => {
  it("names the source and its revision, links to it, and says its labels", async () => {
    api({
      "/api/v1/studies/STU-2/design/source": () => SOURCE,
      "/api/v1/studies/STU-1/workspace": () => ({ study: { study_id: "STU-1", name: "Ranní káva" } }),
    });
    render(<DesignSourceNote clientId="CLI-a" studyId="STU-2" />);
    const note = await screen.findByRole("note", { name: t(`${D}.title`) });
    expect(await screen.findByText(new RegExp(tv(`${D}.from`, { name: "Ranní káva", revision: 3 }).replace(".", "\\.")))).toBeTruthy();
    expect(note.textContent).toContain(`${t(`${D}.synthetic`)} · ${t(`${D}.draft`)}`);
    expect(screen.getByRole("link", { name: t(`${D}.open`) }).getAttribute("href")).toBe("/app/clients/CLI-a/memory/STU-1");
  });

  it("says nothing for a study whose design was not reused", async () => {
    api({});
    const { container } = render(<DesignSourceNote clientId="CLI-a" studyId="STU-2" />);
    await new Promise((r) => setTimeout(r, 50));
    expect(container.textContent).toBe("");
  });
});
