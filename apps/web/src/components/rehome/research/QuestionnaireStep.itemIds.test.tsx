// @vitest-environment jsdom
// Dotazník's import undo with stable item ids on (AIA_WEB_STABLE_ITEM_IDS). A file of its own: the
// screen reads the switch once per module (ResearchScreen.tsx switchesKnown), so it cannot be turned
// on beside the other Dotazník tests.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NATIVE_TEST_TIMEOUT_MS, nativeAgentFixture } from "./test-native-agents";
import { ResearchScreen } from "./ResearchScreen";
import { workspaceFixture } from "./test-workspace";
import { TEST_FRAME } from "./test-frame";

vi.setConfig({ testTimeout: NATIVE_TEST_TIMEOUT_MS });
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/questionnaire", useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const IMPORT_PATH = "/api/v1/studies/STU-1/workspace/questionnaire-import";
// A choice question and a tracked set: the store gives both item ids once they are on the copy.
const IMPORTED = [
  { id: "sec_a", type: "questions", title: "Hlavní otázky", purpose: "", questions: [{ id: "Q1", text: "Jak často?", typ: "vyber", kategorie: ["Denně", "Týdně"] }] },
  { id: "sec_b", type: "object_battery", title: "Sledovaná sada — média", object_type: "média", objects: ["TV", "Rádio", "Web", "Tisk"], object_question: "Jak často používáte {object}?" },
];
const MINE = [{ id: "sec_m", type: "questions", title: "Moje", purpose: "", questions: [{ id: "Q9", text: "Moje otázka?", typ: "otevrena" }] }];

// jsdom's Blob has no arrayBuffer; the upload reads the file through it.
if (!Blob.prototype.arrayBuffer) {
  Blob.prototype.arrayBuffer = function (this: Blob) {
    return new Promise<ArrayBuffer>((resolve) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result as ArrayBuffer);
      r.readAsArrayBuffer(this);
    });
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Dotazník's import undo with stable item ids", () => {
  it("takes an import back with Vrátit, though the store gave its items ids", async () => {
    const ws = workspaceFixture({ goal: "Cíl", sections: MINE, ui_state: { questionnaire_path: "upload" } });
    const over: Record<string, () => unknown> = {
      "/config": () => ({ stableItemIds: true }),
      [IMPORT_PATH]: () => ({ sections: IMPORTED, summary: {}, filename: "dotaznik.xlsx" }),
    };
    const native = nativeAgentFixture(() => ({ project: {}, proposal: {} }), over, ws.write);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        const path = String(url).split("?")[0];
        const body = init?.body ? JSON.parse(String(init.body)) : null;
        const answer = native(path, init?.method ?? "GET", body) ?? ws.answer(path, init?.method ?? "GET", body) ?? over[path]?.();
        if (answer === undefined) return new Response(JSON.stringify({ code: "not_found", message: "No such resource." }), { status: 404 });
        return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
      }),
    );
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.change(await screen.findByLabelText("Vyplněný XLSX / CSV"), { target: { files: [new File(["x"], "dotaznik.xlsx")] } });
    const toast = (await screen.findByText(/^Načteno:/)).closest("[role=status]") as HTMLElement;
    fireEvent.click(within(toast).getByRole("button", { name: "Vrátit" }));
    expect(screen.queryByText("Dotazník se od načtení změnil, import už se nevrátí.")).toBeNull();
    await waitFor(() => expect(ws.saves.at(-1)?.reason).toBe("questionnaire_import_undone"));
    const sections = (ws.saves.at(-1)!.content as { sections: { id: string }[] }).sections;
    expect(sections.map((s) => s.id)).toEqual(["sec_m"]);
  });
});
