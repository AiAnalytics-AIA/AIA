import { describe, expect, it } from "vitest";

import { NAME_MAX, cleanName, nameKey, nameProblem, nameProblemWords } from "./name-input";

describe("a name typed in the list follows the server's organizer rules (domain/knowledge.py)", () => {
  it("is trimmed and its inner spaces collapsed, as organizer_name stores it", () => {
    expect(cleanName("  Trh   a\tkonkurence ")).toBe("Trh a konkurence");
  });

  it("is the same name whatever its case and spacing; accents count (organizer_key)", () => {
    expect(nameKey(" trh  A KONKURENCE")).toBe(nameKey("Trh a konkurence"));
    expect(nameKey("Řízení")).toBe("řízení");
    expect(nameKey("ríz")).not.toBe(nameKey("říz"));
  });

  it("is refused empty, too long, or equal to one already in the list", () => {
    const existing = ["Trh a konkurence", "Smlouvy"];
    expect(nameProblem("   ", existing)).toEqual({ kind: "empty" });
    expect(nameProblem("x".repeat(NAME_MAX + 1), existing)).toEqual({ kind: "tooLong", max: 80 });
    expect(nameProblem("x".repeat(NAME_MAX), existing)).toBeNull();
    expect(nameProblem("SMLOUVY ", existing)).toEqual({ kind: "taken", name: "Smlouvy" });
    expect(nameProblem("Smlouvy 2026", existing)).toBeNull();
  });

  it("may keep its own name when renamed", () => {
    expect(nameProblem("smlouvy", ["Smlouvy", "Trh"], NAME_MAX, "Smlouvy")).toBeNull();
    expect(nameProblem("trh", ["Smlouvy", "Trh"], NAME_MAX, "Smlouvy")).toEqual({ kind: "taken", name: "Trh" });
  });

  it("says each refusal in Czech", () => {
    expect(nameProblemWords({ kind: "empty" })).toBe("Napište název.");
    expect(nameProblemWords({ kind: "tooLong", max: 80 })).toBe("Nejvýš 80 znaků.");
    expect(nameProblemWords({ kind: "taken", name: "Smlouvy" })).toBe("„Smlouvy“ už existuje.");
  });
});
