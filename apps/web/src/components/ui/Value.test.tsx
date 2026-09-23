import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Value, valueState } from "./Value";
import { Money } from "./Money";
import { formatPercent } from "@/design/format";

describe("Value — zero, null, suppressed and loading are four different things", () => {
  it("renders zero as a figure, not as missing", () => {
    const { container } = render(<Value value={0} />);
    expect(container.firstElementChild).toHaveAttribute("data-state", "zero");
    expect(container).toHaveTextContent("0");
    expect(container).not.toHaveTextContent("chybí");
  });

  it("renders null and undefined as 'chybí', never as 0", () => {
    for (const v of [null, undefined, Number.NaN]) {
      const { container, unmount } = render(<Value value={v} />);
      expect(container.firstElementChild).toHaveAttribute("data-state", "na");
      expect(container).toHaveTextContent("chybí");
      expect(container.textContent).not.toMatch(/\d/);
      unmount();
    }
  });

  it("keeps suppressed distinct from missing, and always states the reason", () => {
    const { container } = render(<Value value={12.3} state="suppressed" reason="vzorek < 30" />);
    expect(container.firstElementChild).toHaveAttribute("data-state", "suppressed");
    expect(container).toHaveTextContent("potlačeno");
    expect(container).toHaveTextContent("vzorek < 30");
    expect(container).not.toHaveTextContent("chybí");
    expect(container).not.toHaveTextContent("12,3");
  });

  it("names a missing suppression reason instead of hiding it", () => {
    render(<Value value={1} state="suppressed" />);
    expect(screen.getByText(/důvod neuveden/)).toBeInTheDocument();
  });

  it("renders loading as a status with no invented number", () => {
    render(<Value value={5} state="loading" />);
    const el = screen.getByRole("status", { name: "Načítá se" });
    expect(el).toHaveAttribute("data-state", "loading");
    expect(el.textContent).toBe("");
  });

  it("classifies states without rendering", () => {
    expect([valueState(0), valueState(null), valueState(3), valueState(3, "suppressed"), valueState(null, "loading")])
      .toEqual(["zero", "na", "value", "suppressed", "loading"]);
  });

  it("formats Czech numbers with a unit", () => {
    render(<Value value={41.7} format={(v) => formatPercent(v)} />);
    expect(screen.getByText("41,7 %")).toBeInTheDocument();
  });
});

describe("Value — evidence grades", () => {
  it("marks an unknown role as unknown, never as measured", () => {
    for (const role of ["SOMETHING_NEW", null, "", 42]) {
      const { container, unmount } = render(<Value value={41.7} role={role} />);
      expect(container.firstElementChild).toHaveAttribute("data-grade", "unknown");
      expect(screen.getByRole("img", { name: "Role neznámá" })).toBeInTheDocument();
      expect(screen.queryByRole("img", { name: "Měřeno" })).toBeNull();
      unmount();
    }
  });

  it("omits the mark when the column already declares the same grade, keeps it when it differs", () => {
    const same = render(<Value value={1} role="CALIBRATED_CORE" inheritRole="CALIBRATED_CORE" />);
    expect(same.queryByRole("img")).toBeNull();
    same.unmount();
    render(<Value value={1} role="MODELED_BEHAVIOR_PRIOR" inheritRole="CALIBRATED_CORE" />);
    expect(screen.getByRole("img", { name: "Modelováno" })).toBeInTheDocument();
  });

  it("flags holdout-pending on the figure itself", () => {
    render(<Value value={3} role="EXTERNAL_HOLDOUT_PENDING" />);
    expect(screen.getByText("neval.")).toBeInTheDocument();
  });
});

describe("Money", () => {
  it("never renders a bare number: the currency is always there", () => {
    render(<Money value={12480.5} />);
    expect(screen.getByText("12 480,50 USD")).toBeInTheDocument();
  });
  it("renders zero money as 0,00 and missing money as chybí", () => {
    const zero = render(<Money value={0} currency="CZK" />);
    expect(zero.container).toHaveTextContent("0,00 CZK");
    zero.unmount();
    const missing = render(<Money value={null} />);
    expect(missing.container).toHaveTextContent("chybí");
    expect(missing.container).not.toHaveTextContent("0,00");
  });
});
