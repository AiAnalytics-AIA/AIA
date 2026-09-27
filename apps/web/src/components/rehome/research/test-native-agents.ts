// HTTP fixtures for rebuilt screen tests. Native-job lifecycle assertions live
// in useResearchAgents.test.tsx; reference pure-function parity is unchanged.
import type { ResearchAgentAction } from "@/lib/api";
import { fireEvent, screen } from "@testing-library/react";

export const AGENTS_PATH = "/api/v1/studies/STU-1/research/agent-jobs";
export const DESIGN_PATH = "/api/v1/studies/STU-1/design/revisions";
export const PARK_MESSAGE = "AI návrhy výzkumu nejsou zapnuté. Zadání zůstává uložené.";

export function nativeAgentFixture(
  output: (action: ResearchAgentAction, baseline: Record<string, unknown>, instruction: string) => Record<string, unknown>,
  overrides: Record<string, (body: unknown) => unknown> = {},
) {
  let baseline: Record<string, unknown> = {};
  let action: ResearchAgentAction = "analyze_brief";
  let instruction = "";
  let created = false;
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000 }));
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
  const job = () => ({
    run_id: "RUN-A", design_revision_id: "REV-A", action, status: "COMPLETED", is_terminal: true,
    needs_attention: false, steps: [], created_at: null, context_sha256: "sha", harness_version: "v1", actual_cost_usd: null,
  });
  return (path: string, method: string, body: Record<string, unknown> | null): unknown => {
    if (path === "/config") return { apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost" };
    if (path === DESIGN_PATH && method === "POST") {
      baseline = structuredClone(body?.content as Record<string, unknown>); return { revision_id: "REV-A", revision: 1 };
    }
    if (path === DESIGN_PATH) return { items: [] };
    if (path.endsWith("/research/readiness")) return { ready: false, checks: [], questions: 0, batteries: 0, objects: 0, n: 0 };
    if (path.endsWith("/research/runs")) return { items: [] };
    if (path === AGENTS_PATH && method === "POST") {
      action = body?.action as ResearchAgentAction; instruction = String(body?.instruction || ""); created = true; return job();
    }
    if (path === AGENTS_PATH) return [];
    if (path === `${AGENTS_PATH}/RUN-A`) return overrides["native/job"]?.(body) ?? job();
    if (path === `${AGENTS_PATH}/RUN-A/result`) {
      const proposal = output(action, baseline, instruction);
      return { result: proposal, provenance: { agent_id: "research", design_revision_id: "REV-A", context_sha256: "sha", status: "PROPOSED" } };
    }
    if (path === `${AGENTS_PATH}/RUN-A/accept`) {
      if (!created) throw new Error("No job created"); return { revision_id: "REV-B", revision: 2 };
    }
    return undefined;
  };
}
// A native job reaches its review dialog through a chain of mocked requests and
// renders: about 0.3 s on an idle machine, several seconds on a loaded CI runner,
// where 1 s and 4 s waits failed (PlanStep, AudienceStep; AGENTS.md § Next.js / TypeScript). A
// wait resolves as soon as the element appears, so the room costs a passing test
// nothing. Files that drive native jobs raise their test timeout to match.
export const NATIVE_JOB_WAIT = { timeout: 15_000 } as const;
export const NATIVE_TEST_TIMEOUT_MS = 30_000;
export function findProposalDialog() {
  return screen.findByRole("dialog", {}, NATIVE_JOB_WAIT);
}
export async function approveProposal() {
  fireEvent.click(await screen.findByRole("button", { name: "Použít návrh" }, NATIVE_JOB_WAIT));
}
