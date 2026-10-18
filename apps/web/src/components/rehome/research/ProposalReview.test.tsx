// @vitest-environment jsdom
// A questionnaire proposal's research-question links, reviewed before they are accepted
// (run-recovery-and-truth 3e).
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
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

  it("on a study that takes no new work, is read and closed but never applied", () => {
    const decide = vi.fn();
    render(<ProposalReview result={result()} state={state} onDecision={decide} canApply={false} />);
    expect(screen.getByText(t("research.proposalClosed"))).toBeTruthy();
    expect((screen.getByRole("button", { name: "Použít návrh" }) as HTMLButtonElement).disabled).toBe(true);
    // Keeping the current design writes nothing, so it stays: the review can always be closed.
    fireEvent.click(screen.getByRole("button", { name: "Ponechat současný návrh" }));
    expect(decide).toHaveBeenCalledWith(false);
  });

  it("shows no research-question block for a proposal that is not a questionnaire", () => {
    const analysis: ResearchAgentResult = { ...result(), result: { project, proposal: { research_questions: [RQ1] } } };
    render(<ProposalReview result={analysis} state={state} onDecision={vi.fn()} />);
    expect(screen.queryByRole("heading", { name: t("research.questionnaire.proposed.title") })).toBeNull();
  });

  it("says what accepting a questionnaire proposal replaces, before it is accepted (PC6)", () => {
    const now = { ...state, project: { ...state.project, sections: [
      { id: "s1", type: "questions", title: "Moje", questions: [{ id: "q1", text: "Kde kávu kupujete?" }] },
      { id: "lib", type: "questions", metadata: { instrument_id: "nps" }, questions: [{ id: "n1", text: "Doporučil byste nás?" }] },
    ] } } as unknown as Pick<ResearchState, "project" | "analysis">;
    render(<ProposalReview result={result()} state={now} onDecision={vi.fn()} />);
    const block = screen.getByRole("heading", { name: t("research.questionnaire.replacement.title") }).parentElement as HTMLElement;
    expect(within(block).getByText(tv("research.questionnaire.replacement.summary", { replaced: 1, preserved: 1, kept: 0 }))).toBeTruthy();
    expect(within(block).getByText("Kde kávu kupujete?")).toBeTruthy();
    expect(screen.getByText(t("research.questionnaire.replacement.footer"))).toBeTruthy();
    // The old promise is not made for a proposal that replaces the questionnaire.
    expect(screen.queryByText(/Již vytvořený dotazník se nemění/)).toBeNull();
  });

  it("keeps the old promise for a proposal that does not touch the questionnaire", () => {
    const analysis: ResearchAgentResult = { ...result(), result: { project, proposal: { research_questions: [RQ1] } } };
    render(<ProposalReview result={analysis} state={state} onDecision={vi.fn()} />);
    expect(screen.queryByRole("heading", { name: t("research.questionnaire.replacement.title") })).toBeNull();
    expect(screen.getByText(/Již vytvořený dotazník se nemění/)).toBeTruthy();
  });
});
