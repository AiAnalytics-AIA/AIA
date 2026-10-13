// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ResearchAssistance } from "./ResearchAssistance";
import type { useResearchAgents } from "./useResearchAgents";

const actions = [
  { action: "critique_design" as const, label: "research.aiCritique", title: "Kontrola návrhu" },
  { action: "design_copilot" as const, label: "research.aiCopilot", title: "Pomoc s návrhem" },
  { action: "answer_memory" as const, label: "research.aiMemory", title: "Klientské znalosti" },
];
let agents: ReturnType<typeof useResearchAgents>;
let memory: Map<string, unknown>;
function Harness({ canEdit = true }: { canEdit?: boolean }) {
  return <ResearchAssistance step="plan" studyName="Fictional study" studyId="STU-1" canEdit={canEdit} actions={actions} memory={memory} agents={agents} job={null} onCancel={vi.fn()}>
    {({ card, panel }) => <><header>{card}</header><main>{panel}</main></>}
  </ResearchAssistance>;
}
beforeEach(() => {
  memory = new Map();
  agents = { run: vi.fn().mockResolvedValue({}), busy: false, activeAction: null, adviceReview: null, recent: [], notice: null, dialog: null,
    refresh: vi.fn().mockResolvedValue([]), open: vi.fn().mockResolvedValue(undefined), continueAdvice: vi.fn().mockResolvedValue(undefined) };
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("prefills without running, preserves edits across closing and stage remount, and returns keyboard focus", () => {
  const view = render(<Harness />);
  const trigger = screen.getByRole("button", { name: "AI pomoc" }); trigger.focus(); fireEvent.click(trigger);
  fireEvent.click(screen.getByRole("button", { name: /Začít otázkou: Které výzkumné otázky/ }));
  const field = screen.getByRole("textbox", { name: "Co chcete zjistit?" }) as HTMLTextAreaElement;
  expect(field.value).toContain("Které výzkumné otázky"); expect(document.activeElement).toBe(field);
  fireEvent.change(field, { target: { value: "Unfinished question" } });
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("complementary", { name: "Pomoc s návrhem" })).toBeNull();
  expect(document.activeElement).toBe(trigger); expect(agents.run).not.toHaveBeenCalled();
  view.unmount(); render(<Harness />);
  fireEvent.click(screen.getByRole("button", { name: "AI pomoc" }));
  expect((screen.getByRole("textbox", { name: "Co chcete zjistit?" }) as HTMLTextAreaElement).value).toBe("Unfinished question");
});

it("requires explicit submission and keeps the question after refusal; refresh does not send again", async () => {
  vi.mocked(agents.run).mockRejectedValue(new Error("Runtime unavailable"));
  render(<Harness />); fireEvent.click(screen.getByRole("button", { name: "AI pomoc" }));
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "  Explain the design  " } });
  expect(agents.run).not.toHaveBeenCalled(); fireEvent.click(screen.getByRole("button", { name: "Odeslat otázku" }));
  await screen.findByRole("alert");
  expect(agents.run).toHaveBeenCalledExactlyOnceWith("design_copilot", { instruction: "Explain the design" }, "Pomoc s návrhem");
  expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("  Explain the design  ");
  fireEvent.click(screen.getByRole("button", { name: "Obnovit stav" }));
  await waitFor(() => expect(agents.refresh).toHaveBeenCalledOnce()); expect(agents.run).toHaveBeenCalledOnce();
});

it("uses a native narrow-screen dialog and preserves the question on Escape cancellation", () => {
  vi.stubGlobal("matchMedia", () => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  render(<Harness />); fireEvent.click(screen.getByRole("button", { name: "AI pomoc" }));
  const dialog = screen.getByRole("dialog", { name: "Pomoc s návrhem" }); expect(dialog.hasAttribute("open")).toBe(true);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Mobile draft" } }); fireEvent(dialog, new Event("cancel", { cancelable: true }));
  expect(screen.queryByRole("dialog")).toBeNull(); expect(memory.get("contextual-ai-questions")).toEqual({ design_copilot: "Mobile draft" }); expect(agents.run).not.toHaveBeenCalled();
});

it("offers read-only readers stored answers without any new AI start controls", () => {
  agents.recent = [{run_id:"RUN-old",design_revision_id:"REV-old",action:"answer_memory",status:"COMPLETED",is_terminal:true,needs_attention:false,context_sha256:"hash",harness_version:"v1",created_at:null,steps:[],actual_cost_usd:null}];
  render(<Harness canEdit={false} />);
  expect(document.querySelectorAll("[data-ai-action]").length).toBe(0);
  fireEvent.click(screen.getByRole("button", { name: "AI pomoc" }));
  const panel = screen.getByRole("complementary"); fireEvent.click(within(panel).getByRole("button", { name: "Otevřít odpověď" }));
  expect(agents.open).toHaveBeenCalledExactlyOnceWith(agents.recent[0]); expect(agents.run).not.toHaveBeenCalled();
  expect(within(panel).getByText("Náklady nejsou vykázané")).toBeTruthy();
});
