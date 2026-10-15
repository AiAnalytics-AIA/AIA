// @vitest-environment jsdom
// A questionnaire proposal's research-question links, reviewed before they are accepted
// (run-recovery-and-truth 3e).
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { t, tv } from "@/i18n/t";
import type { ResearchAgentResult } from "@/lib/api";
import type { ResearchState } from "@/research/store";

import { ProposalReview } from "./ProposalReview";

afterEach(cleanup);

const RQ1 = "Jak často lidé pijí kávu?";
const RQ2 = "Jak lidé vnímají ranní nápoje?";

const project = {
  research_plan: { research_questions: [RQ1, RQ2], research_question_comparisons: { [RQ1]: "describe" } },
  sections: [
    { id: "ai_section_1", type: "questions", title: "Zvyky", questions: [{ id: "ai_q_1_1", text: "Jak často pijete kávu?", typ: "skala", research_questions: [RQ1] }] },
    { id: "ai_section_2", type: "object_battery", title: "Nápoje", objects: ["Káva", "Čaj", "Kakao"] },
  ],
};

const result = (extra: Record<string, unknown> = {}): ResearchAgentResult => ({
  result: { project, proposal: { message: "Návrh", sections: project.sections, warnings: [], comparisons: [] }, ...extra },
  provenance: { agent_id: "aia.research.build_questionnaire", design_revision_id: "REV-1", context_sha256: "x", status: "COMPLETED" },
});

const state = { project: { research_plan: { research_questions: [RQ1, RQ2] }, sections: [] }, analysis: null } as unknown as Pick<ResearchState, "project" | "analysis">;

describe("ProposalReview", () => {
  it("lists each research question with what the proposal measures it by and how it is answered", () => {
    render(<ProposalReview result={result({ dropped_links: [{ item: "ai_q_1_1", research_question: "Vymyšlená?" }] })} state={state} onDecision={vi.fn()} />);
    const block = screen.getByRole("heading", { name: t("research.questionnaire.proposed.title") }).parentElement as HTMLElement;
    const [first, second] = within(block).getAllByRole("listitem");
    expect(within(first).getByText(tv("research.questionnaire.proposed.measures", { list: "Jak často pijete kávu?" }))).toBeTruthy();
    expect(within(first).getByText(tv("research.questionnaire.proposed.answer", { kind: t("research.questionnaire.comparisons.kind.describe") }))).toBeTruthy();
    expect(within(second).getByText(RQ2)).toBeTruthy();
    expect(within(second).getByText(t("research.questionnaire.proposed.unmeasured"))).toBeTruthy();
    expect(within(block).getByText(tv("research.questionnaire.proposed.dropped", { count: 1 }))).toBeTruthy();
  });

  it("shows no research-question block for a proposal that is not a questionnaire", () => {
    const analysis: ResearchAgentResult = { ...result(), result: { project, proposal: { research_questions: [RQ1] } } };
    render(<ProposalReview result={analysis} state={state} onDecision={vi.fn()} />);
    expect(screen.queryByRole("heading", { name: t("research.questionnaire.proposed.title") })).toBeNull();
  });
});
