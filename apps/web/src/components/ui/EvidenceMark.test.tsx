import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { EvidenceMark } from "./EvidenceMark";
import { KNOWN_EVIDENCE_ROLES, evidenceGrade } from "@/design/evidence";

describe("EvidenceMark", () => {
  it.each([
    ["MEASURED_JOINT", "measured", "Měřeno"],
    ["CALIBRATED_CORE", "calibrated", "Kalibrované jádro"],
    ["MODELED_BEHAVIOR_PRIOR", "modelled", "Modelováno"],
    ["EXTERNAL_HOLDOUT_PENDING", "holdout-pending", "Validace čeká"],
  ])("draws %s as %s", (role, grade, name) => {
    render(<EvidenceMark role={role} />);
    expect(screen.getByRole("img", { name })).toHaveAttribute("data-grade", grade);
  });

  it("never falls back to the strongest grade", () => {
    for (const role of [undefined, null, "", "measured", "MEASURED", "CROSS_BLOCK", {}, 1]) {
      expect(evidenceGrade(role)).toBe("unknown");
    }
  });

  it("is vector-only: no text characters stand in for the mark", () => {
    for (const role of [...KNOWN_EVIDENCE_ROLES, "UNKNOWN_X"]) {
      const { container, unmount } = render(<EvidenceMark role={role} />);
      expect(container.querySelector("svg")).not.toBeNull();
      expect(container.querySelector("text")).toBeNull();
      expect(container.textContent).toBe("");
      unmount();
    }
  });

  it("gives every grade a distinct shape", () => {
    const shapes = [...KNOWN_EVIDENCE_ROLES, "?"].map((role) => {
      const { container, unmount } = render(<EvidenceMark role={role} />);
      const html = container.querySelector("svg")!.innerHTML;
      unmount();
      return html;
    });
    expect(new Set(shapes).size).toBe(shapes.length);
  });
});
