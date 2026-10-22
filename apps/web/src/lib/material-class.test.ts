import { describe, expect, it } from "vitest";
import { type BriefMaterials, classLabel, classOf } from "./material-class";

const UNKNOWN_CLASS = "třída neznámá";

const B = { data_class: "CLASS_B_DERIVED_CLIENT", class_source: "rule:design" };
const answer: BriefMaterials = {
  revision: 3,
  materials: [
    { index: 0, kind: "file", ref: "ART-01", ...B },
    { index: 1, kind: "url", ref: "https://example.org/a", ...B },
    { index: 2, kind: "file", ref: null, ...B },
    { index: 3, kind: null, ref: null, data_class: null, class_source: null },
  ],
};

describe("classLabel", () => {
  it("prints each class as V2 does", () => {
    expect(classLabel("CLASS_A_CLIENT_CONFIDENTIAL")).toBe("A · důvěrné klienta");
    expect(classLabel("CLASS_B_DERIVED_CLIENT")).toBe("B · odvozené od klienta");
    expect(classLabel("CLASS_C_INTERNAL")).toBe("C · interní");
  });
  it("prints an unknown class as unknown, never C", () => {
    expect(classLabel(null)).toBe(UNKNOWN_CLASS);
    expect(classLabel("CLASS_Z")).toBe(UNKNOWN_CLASS);
    expect(classLabel("constructor")).toBe(UNKNOWN_CLASS);
  });
});

describe("classOf", () => {
  it("finds a file by its artifact and a link by its address, wherever they now stand", () => {
    expect(classOf(answer, 4, { kind: "file", attachment_id: "ART-01" }, 5)?.index).toBe(0);
    expect(classOf(answer, 4, { kind: "url", url: "https://example.org/a" }, 0)?.index).toBe(1);
  });
  it("does not match a link to a file of the same ref", () => {
    expect(classOf(answer, 3, { kind: "url", url: "ART-01" }, 0)).toBeUndefined();
  });
  it("matches an entry with no ref by position, only at the answer's revision", () => {
    expect(classOf(answer, 3, { filename: "stary.pdf" }, 2)?.data_class).toBe("CLASS_B_DERIVED_CLIENT");
    expect(classOf(answer, 4, { filename: "stary.pdf" }, 2)).toBeUndefined();
    expect(classOf(answer, 3, { filename: "x" }, 3)?.data_class).toBeNull();
  });
  it("has nothing to say before an answer or for a material added since", () => {
    expect(classOf(null, 3, { kind: "file", attachment_id: "ART-01" }, 0)).toBeUndefined();
    expect(classOf(answer, 3, { kind: "file", attachment_id: "ART-99" }, 0)).toBeUndefined();
  });
});
