// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ActionDock, ChipInput, FrameNavigation, InlineConfirm, RadioCard, Segmented, StageHeader, StageHeaderSlot, StepSection, Switch } from "./step";
import { WellItem } from "./ui";

afterEach(cleanup);

describe("Studio v3 step pieces", () => {
  it("StepSection is a labelled section that says when it is optional", () => {
    render(<StepSection id="s" optional title="Podklady" hint="Dokumenty">tělo</StepSection>);
    const section = screen.getByRole("region", { name: /^Podklady\s*· volitelné$/ });
    expect(section.id).toBe("s");
    expect(section.textContent).toContain("tělo");
  });

  it("StepSection prints its number and cap, and the need state names what is missing (v73 X1)", () => {
    render(
      <>
        <StepSection n={3} title="Rozhodnutí" cap="povinné" need>tělo</StepSection>
        <StepSection n={4} num="S1" title="Sada" cap="7 objektů" />
      </>,
    );
    const decision = screen.getByRole("region", { name: "Rozhodnutí" });
    // The board's number, two digits and mono, beside the title; the cap at the right.
    expect(decision.querySelector("[data-step-num]")?.textContent).toBe("03");
    expect(decision.textContent).toContain("povinné");
    // Needs you: the coral edge, and "chybí" said in words, not by colour alone.
    expect(decision.getAttribute("data-need")).toBe("true");
    expect(decision.textContent).toContain("chybí");
    const set = screen.getByRole("region", { name: "Sada" });
    expect(set.querySelector("[data-step-num]")?.textContent).toBe("S1");
    expect(set.getAttribute("data-need")).toBeNull();
    expect(set.textContent).not.toContain("chybí");
  });

  it("WellItem is one row: its mono id at the left, its text, its actions at the right", () => {
    render(<ul><WellItem id="C2" actions={<button type="button">Upravit</button>}>Zjistit cenovou citlivost</WellItem></ul>);
    const row = screen.getByRole("listitem");
    expect(row.querySelector("[data-well-id]")?.textContent).toBe("C2");
    expect(row.textContent).toContain("Zjistit cenovou citlivost");
    expect(screen.getByRole("button", { name: "Upravit" })).toBeTruthy();
  });

  it("a stage's header parts stay where they stand outside the workbench, and go to its slots inside it", () => {
    const view = render(<StageHeaderSlot slot="actions"><button type="button">Akce</button></StageHeaderSlot>);
    expect(screen.getByRole("button", { name: "Akce" })).toBeTruthy();
    view.unmount();
    const actions = document.createElement("div");
    document.body.appendChild(actions);
    try {
      render(
        <StageHeader.Provider value={{ actions, status: null, primary: null, claimPrimary: () => () => {} }}>
          <StageHeaderSlot slot="actions"><button type="button">Akce</button></StageHeaderSlot>
          <StageHeaderSlot slot="status"><span>Stav</span></StageHeaderSlot>
        </StageHeader.Provider>,
      );
      expect(actions.querySelector("button")?.textContent).toBe("Akce");
      // A slot the header does not offer yet shows nothing, never a stray copy in the body.
      expect(screen.queryByText("Stav")).toBeNull();
    } finally {
      actions.remove();
    }
  });

  it("ActionDock in the workbench puts its action in the header's primary slot, and claims it while mounted", () => {
    const primary = document.createElement("div");
    document.body.appendChild(primary);
    const released = vi.fn();
    const claimPrimary = vi.fn(() => released);
    try {
      const view = render(
        <StageHeader.Provider value={{ actions: null, status: null, primary, claimPrimary }}>
          <ActionDock note="Připraveno"><button type="button">Další</button></ActionDock>
        </StageHeader.Provider>,
      );
      expect(primary.querySelector("button")?.textContent).toBe("Další");
      expect(screen.getByText("Připraveno")).toBeTruthy();
      expect(claimPrimary).toHaveBeenCalled();
      view.unmount();
      expect(released).toHaveBeenCalled();
    } finally {
      primary.remove();
    }
  });

  it("ActionDock says why a step is not ready, beside its way back and its action", () => {
    render(<ActionDock back={{ href: "/zpet", label: "Zpět" }} ready={false} note="Chybí cíl"><button>Další</button></ActionDock>);
    expect(screen.getByRole("link", { name: "Zpět" }).getAttribute("href")).toBe("/zpet");
    expect(screen.getByText("Chybí cíl").className).toContain("text-status-you-ink");
    expect(screen.getByRole("button", { name: "Další" })).toBeTruthy();
  });

  it("ActionDock leaves its back link to a frame that names the neighbouring stages itself", () => {
    // The workbench's navigator calls the stages otherwise and orders them otherwise (DIM-F4).
    render(<FrameNavigation.Provider value={{ next: null }}><ActionDock back={{ href: "/audience", label: "4. Audience" }} note="Připraveno"><button>Další</button></ActionDock></FrameNavigation.Provider>);
    expect(screen.queryByRole("link", { name: "4. Audience" })).toBeNull();
    expect(screen.getByText("Připraveno")).toBeTruthy();
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

  it("Segmented is one Tab stop whose arrows move and choose (input-interactions I11)", () => {
    const seg = vi.fn();
    render(
      <Segmented
        label="Řadit"
        value="new"
        options={[{ key: "new", label: "Nejnovější" }, { key: "name", label: "Podle názvu" }, { key: "state", label: "Podle stavu" }]}
        onChange={seg}
      />,
    );
    const radios = screen.getAllByRole("radio");
    expect(radios.map((r) => r.tabIndex)).toEqual([0, -1, -1]);
    fireEvent.keyDown(radios[0], { key: "ArrowLeft" });
    expect(seg).toHaveBeenLastCalledWith("state");
    expect(document.activeElement).toBe(radios[2]);
    fireEvent.keyDown(radios[0], { key: "End" });
    expect(seg).toHaveBeenLastCalledWith("state");
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

  it("ChipInput with rename rewords a value in its place, refusing what refuse refuses for that place", () => {
    const rename = vi.fn();
    const refuse = vi.fn((v: string, i?: number) => (v === "A" && i !== 0 ? "Už je." : null));
    render(<ChipInput label="Položky" values={["A", "B"]} onAdd={vi.fn()} onRemove={vi.fn()} refuse={refuse} rename={{ label: "Položka", onRename: rename }} />);
    fireEvent.click(screen.getByRole("button", { name: "Upravit: Položka · 2 B" }));
    const field = screen.getByRole("textbox", { name: "Položka · 2" });
    fireEvent.change(field, { target: { value: "A" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(screen.getByText("Už je.")).toBeTruthy();
    expect(rename).not.toHaveBeenCalled();
    fireEvent.change(field, { target: { value: "Bé" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(rename).toHaveBeenCalledWith(1, "Bé");
    expect(refuse).toHaveBeenLastCalledWith("Bé", 1);
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
