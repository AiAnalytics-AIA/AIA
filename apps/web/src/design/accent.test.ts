import { describe, expect, it } from "vitest";
import { ACCENT_SLOTS, accentSlot, hashAccentSlot, monogram } from "./accent";

describe("accent slot", () => {
  it("is deterministic and always one of the six slots", () => {
    for (const id of ["CLI-4183b1f7a32140", "CLI-54ce087fb73347", "x", ""]) {
      expect(hashAccentSlot(id)).toBe(hashAccentSlot(id));
      expect(ACCENT_SLOTS).toContain(hashAccentSlot(id));
    }
  });
  it("collides — which is why the persisted slot (OI-12) replaces it", () => {
    expect(hashAccentSlot("cl_salvia")).toBe(hashAccentSlot("cl_tecka"));
  });
  it("prefers a valid server slot and ignores an out-of-range one", () => {
    expect(accentSlot("cl_salvia", 2)).toBe(2);
    expect(accentSlot("cl_salvia", 9)).toBe(hashAccentSlot("cl_salvia"));
    expect(accentSlot("cl_salvia", null)).toBe(hashAccentSlot("cl_salvia"));
  });
});

describe("monogram", () => {
  it.each([
    ["Banka Horizont", "BH"],
    ["Energie Morava a.s.", "EM"],
    ["Čedok", "ČE"],
    ["  ", "?"],
  ])("%s → %s", (name, mono) => expect(monogram(name)).toBe(mono));
});
