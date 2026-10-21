import { describe, expect, it } from "vitest";

import { editKeyAction, opensEdit, readDraft } from "./inline-edit";

describe("editing a value where it is shown (I1)", () => {
  it("saves a single line on Enter, a multi-line text on Ctrl/Cmd+Enter, and restores on Esc", () => {
    expect(editKeyAction({ key: "Enter" }, false)).toBe("commit");
    expect(editKeyAction({ key: "Enter", shiftKey: true }, false)).toBeNull();
    expect(editKeyAction({ key: "Enter" }, true)).toBeNull();
    expect(editKeyAction({ key: "Enter", ctrlKey: true }, true)).toBe("commit");
    expect(editKeyAction({ key: "Enter", metaKey: true }, true)).toBe("commit");
    expect(editKeyAction({ key: "Escape" }, false)).toBe("cancel");
    expect(editKeyAction({ key: "Escape" }, true)).toBe("cancel");
    expect(editKeyAction({ key: "a" }, false)).toBeNull();
  });

  it("opens on Enter or F2", () => {
    expect(opensEdit("Enter")).toBe(true);
    expect(opensEdit("F2")).toBe(true);
    expect(opensEdit(" ")).toBe(false);
  });

  it("trims a draft; a single line also collapses its spaces, a multi-line text keeps its lines", () => {
    expect(readDraft("  Ranní   pečivo ", false)).toEqual({ value: "Ranní pečivo", problem: null });
    expect(readDraft(" první\n\n druhá ", true)).toEqual({ value: "první\n\n druhá", problem: null });
  });

  it("refuses an empty value unless it is optional, and one too long, in words (I9)", () => {
    expect(readDraft("   ", false)).toEqual({ value: "", problem: "Vyplňte text; neuloženo." });
    expect(readDraft("   ", false, { required: false })).toEqual({ value: "", problem: null });
    expect(readDraft("abcdef", false, { maxLength: 5 }).problem).toBe("Nejvýš 5 znaků; neuloženo.");
    // Counted in code points, as the server counts (Codex #532 sweep): five emoji are five.
    expect(readDraft("\u{1F4C1}".repeat(5), false, { maxLength: 5 }).problem).toBeNull();
    expect(readDraft("\u{1F4C1}".repeat(6), false, { maxLength: 5 }).problem).toBe("Nejvýš 5 znaků; neuloženo.");
    expect(readDraft("abc", false, { validate: (v) => (v === "abc" ? "Ne." : null) }).problem).toBe("Ne.");
  });
});
