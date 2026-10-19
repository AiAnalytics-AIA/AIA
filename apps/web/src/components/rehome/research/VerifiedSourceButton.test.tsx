// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DeepResearchBundle, VerifiedSourceAdded } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { citedSnapshot, VERIFY_LABEL, verifiedSourceWords } from "@/lib/verified-source";

import { signedIn } from "./test-workspace";
import { VerifiedSourceButton } from "./VerifiedSourceButton";

const PATH = "/api/v1/studies/STU-1/deep-research/runs/RUN-1/sources/SNP-1/knowledge";
let posts: { url: string; body: unknown }[] = [];
let answer: { status: number; body: VerifiedSourceAdded | { code: string; message: string } };

const added = (status: VerifiedSourceAdded["status"], item_id: string | null = "KNI-1"): VerifiedSourceAdded => ({
  status, item_id, proposal_id: status === "proposed" ? "KNP-1" : null, client_id: "CLI-1", url: "https://stat.example/a", title: "Fiktivní statistika",
});

beforeEach(() => {
  signedIn();
  posts = [];
  answer = { status: 201, body: added("added") };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url).split("?")[0];
      if (u === "/config") return new Response(JSON.stringify({ apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost" }));
      if (init?.method === "POST") {
        posts.push({ url: u, body: init.body ? JSON.parse(String(init.body)) : null });
        return new Response(JSON.stringify(answer.body), { status: answer.status });
      }
      return new Response("{}", { status: 404 });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const button = () => render(<VerifiedSourceButton studyId="STU-1" clientId="CLI-1" runId="RUN-1" snapshotId="SNP-1" evidenceId="EV-1" />);

describe("Ověřeno, přidat zdroj", () => {
  it("adds the checked source once, naming only the run's own source and finding, then links to the item", async () => {
    button();
    fireEvent.click(screen.getByRole("button", { name: VERIFY_LABEL }));
    await waitFor(() => expect(screen.getByText("Přidáno do znalostí")).toBeTruthy());
    // The browser names the finding; the URL, title and quote are the bundle's, on the server.
    expect(posts).toEqual([{ url: PATH, body: { evidence_id: "EV-1" } }]);
    expect(screen.getByRole("link", { name: "Otevřít ve znalostech" }).getAttribute("href")).toBe(appRoutes.knowledgeItem("CLI-1", "KNI-1"));
    expect(screen.queryByRole("button", { name: VERIFY_LABEL })).toBeNull();
  });

  it("says a source already in the knowledge is there, and links to it", async () => {
    answer = { status: 200, body: added("exists") };
    button();
    fireEvent.click(screen.getByRole("button", { name: VERIFY_LABEL }));
    await waitFor(() => expect(screen.getByText("Už je ve znalostech")).toBeTruthy());
    expect(screen.getByRole("link", { name: "Otevřít ve znalostech" }).getAttribute("href")).toBe(appRoutes.knowledgeItem("CLI-1", "KNI-1"));
  });

  it("keeps the button and says why when the server refuses", async () => {
    answer = { status: 404, body: { code: "source_not_in_run", message: "The run's evidence holds no such source." } };
    button();
    fireEvent.click(screen.getByRole("button", { name: VERIFY_LABEL }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("no such source"));
    expect(screen.getByRole("button", { name: VERIFY_LABEL })).toBeTruthy();
  });
});

describe("verified-source words", () => {
  it("links a proposal to the review queue and an item to itself", () => {
    expect(verifiedSourceWords("CLI-1", added("added"))).toEqual({ label: "Přidáno do znalostí", href: appRoutes.knowledgeItem("CLI-1", "KNI-1") });
    expect(verifiedSourceWords("CLI-1", added("proposed", null)).href).toBe(`${appRoutes.area("CLI-1", "knowledge")}?view=review`);
    expect(verifiedSourceWords("CLI-1", added("exists", null)).label).toBe("Už je ve znalostech");
  });

  it("offers the button only for a finding whose source is a captured web page", () => {
    const bundle = {
      accepted: [
        { evidence: { evidence_id: "EV-W", claim: "c", quote: "q", source_ref: "SNP-1" }, score: { score: 1, source_class: "A" } },
        { evidence: { evidence_id: "EV-K", claim: "c", quote: "q", source_ref: "KNW-1@1" }, score: { score: 1, source_class: "A" } },
      ],
      snapshots: [{ snapshot_id: "SNP-1", url: "https://stat.example/a", title: "A", retrieval_mode: "LIVE" }],
    } as unknown as DeepResearchBundle;
    expect(citedSnapshot(bundle, "EV-W")).toEqual({ snapshotId: "SNP-1", url: "https://stat.example/a" });
    expect(citedSnapshot(bundle, "EV-K")).toBeNull();
    expect(citedSnapshot(bundle, "EV-missing")).toBeNull();
  });
});
