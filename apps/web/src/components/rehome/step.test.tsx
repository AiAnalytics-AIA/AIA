// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ActionDock, ChipInput, InlineConfirm, RadioCard, Segmented, StepSection, Switch } from "./step";

afterEach(cleanup);

describe("Studio v3 step pieces", () => {
  it("StepSection is a labelled section that says when it is optional", () => {
    render(<StepSection id="s" n={3} optional title="Podklady" hint="Dokumenty">tělo</StepSection>);
    const section = screen.getByRole("region", { name: /^Podklady\s*· volitelné$/ });
    expect(section.id).toBe("s");
    expect(section.textContent).toContain("3");
    expect(section.textContent).toContain("tělo");
  });

  it("ActionDock says why a step is not ready, beside its way back and its action", () => {
    render(<ActionDock back={{ href: "/zpet", label: "Zpět" }} ready={false} note="Chybí cíl"><button>Další</button></ActionDock>);
    expect(screen.getByRole("link", { name: "Zpět" }).getAttribute("href")).toBe("/zpet");
    expect(screen.getByText("Chybí cíl").className).toContain("text-status-you-ink");
    expect(screen.getByRole("button", { name: "Další" })).toBeTruthy();
  });

  it("RadioCard, Switch and Segmented report their choice and expose their state", () => {
    const pick = vi.fn();
    const flip = vi.fn();
    const seg = vi.fn();
    render(
      <>
        <div role="radiogroup" aria-label="Zdroj"><RadioCard checked={false} onSelect={pick} title="Vlastní" /></div>
        <Switch checked onChange={flip} label="Zeptat se" />
        <Segmented label="Pohled" value="edit" options={[{ key: "edit", label: "Upravit" }, { key: "preview", label: "Náhled" }]} onChange={seg} />
      </>,
    );
    const card = screen.getByRole("radio", { name: "Vlastní" });
    expect(card.getAttribute("aria-checked")).toBe("false");
    fireEvent.click(card);
    expect(pick).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("switch", { name: "Zeptat se" }));
    expect(flip).toHaveBeenCalledWith(false);
    expect(screen.getByRole("radio", { name: "Upravit" }).getAttribute("aria-checked")).toBe("true");
    fireEvent.click(screen.getByRole("radio", { name: "Náhled" }));
    expect(seg).toHaveBeenCalledWith("preview");
  });

  it("ChipInput adds a trimmed value on Enter, removes one by ×, and the last by Backspace when asked", () => {
    const add = vi.fn();
    const remove = vi.fn();
    render(<ChipInput label="Položky" values={["A", "B"]} onAdd={add} onRemove={remove} backspaceRemoves />);
    const input = screen.getByLabelText("Položky");
    fireEvent.change(input, { target: { value: "  C  " } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(add).toHaveBeenCalledWith("C");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(add).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Odebrat A" }));
    expect(remove).toHaveBeenCalledWith(0);
    fireEvent.keyDown(input, { key: "Backspace" });
    expect(remove).toHaveBeenLastCalledWith(1);
  });

  it("InlineConfirm confirms or keeps", () => {
    const yes = vi.fn();
    const no = vi.fn();
    render(<InlineConfirm message="Smazat blok i otázky?" action="Smazat" onConfirm={yes} onCancel={no} />);
    fireEvent.click(screen.getByRole("button", { name: "Smazat" }));
    fireEvent.click(screen.getByRole("button", { name: "Ponechat" }));
    expect(yes).toHaveBeenCalledTimes(1);
    expect(no).toHaveBeenCalledTimes(1);
  });
});
