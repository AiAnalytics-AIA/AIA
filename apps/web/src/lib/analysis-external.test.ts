import { describe, expect, it } from "vitest";
import { sourceChip } from "./analysis-external";

describe("sourceChip", () => {
  it("links an http(s) address, named by its host", () => {
    expect(sourceChip("https://www.stat.example/rostlinne-napoje-2025")).toEqual({ href: "https://www.stat.example/rostlinne-napoje-2025", label: "stat.example" });
    expect(sourceChip("http://example.invalid/a")).toEqual({ href: "http://example.invalid/a", label: "example.invalid" });
  });

  it("never links another scheme or a reference that is no address", () => {
    expect(sourceChip("javascript:alert(1)")).toEqual({ href: null, label: "javascript:alert(1)" });
    expect(sourceChip("KNW-1a2b@3")).toEqual({ href: null, label: "KNW-1a2b@3" });
  });
});
