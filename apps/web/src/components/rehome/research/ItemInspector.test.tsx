// @vitest-environment jsdom
// The item inspector (research-lead-workbench chunk 2): the opened item's detail, Back through
// the stack, Close and Escape, and the focus given back to what opened it.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { t } from "@/i18n/t";
import { backEntry, closeStack, emptyStack, openEntry, type InspectorStack } from "@/lib/inspector-stack";
import { ItemInspector } from "./ItemInspector";

afterEach(cleanup);

function Harness() {
  const [stack, setStack] = useState<InspectorStack>(emptyStack("questionnaire"));
  return (
    <>
      <button type="button" onClick={() => setStack((s) => openEntry(s, { id: "question:q1", title: "Otázka 1" }))}>open q1</button>
      <ItemInspector stack={stack} onBack={() => setStack(backEntry)} onClose={() => setStack(closeStack)}>
        {(entry) => (
          <>
            <p>detail {entry.id}</p>
            <button type="button" onClick={() => setStack((s) => openEntry(s, { id: "measure:m1", title: "Měření 1", sub: "Výsledky" }))}>open m1</button>
          </>
        )}
      </ItemInspector>
    </>
  );
}

describe("ItemInspector", () => {
  it("draws nothing while the stack is empty", () => {
    render(<Harness />);
    expect(screen.queryByRole("complementary")).toBeNull();
  });

  it("shows the opened item, goes Back through the stack, and offers Back only with somewhere to go", () => {
    render(<Harness />);
    fireEvent.click(screen.getByText("open q1"));
    expect(screen.getByRole("complementary", { name: `${t("aia.study.workbench.inspector")}: Otázka 1` })).toBeTruthy();
    expect(screen.queryByRole("button", { name: t("aia.study.workbench.back") })).toBeNull();
    fireEvent.click(screen.getByText("open m1"));
    expect(screen.getByText("detail measure:m1")).toBeTruthy();
    expect(screen.getByText("Výsledky")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: t("aia.study.workbench.back") }));
    expect(screen.getByText("detail question:q1")).toBeTruthy();
  });

  it("closes on Escape and gives the focus back to what opened it", () => {
    render(<Harness />);
    const opener = screen.getByText("open q1");
    opener.focus();
    fireEvent.click(opener);
    const panel = screen.getByRole("complementary");
    expect(document.activeElement).toBe(panel);
    fireEvent.click(screen.getByText("open m1"));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("complementary")).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it("leaves an Escape another control already handled", () => {
    render(<Harness />);
    fireEvent.click(screen.getByText("open q1"));
    const handled = new KeyboardEvent("keydown", { key: "Escape", cancelable: true });
    handled.preventDefault();
    window.dispatchEvent(handled);
    expect(screen.getByRole("complementary")).toBeTruthy();
  });

  it("closes from its button", () => {
    render(<Harness />);
    fireEvent.click(screen.getByText("open q1"));
    fireEvent.click(screen.getByRole("button", { name: t("aia.study.workbench.close") }));
    expect(screen.queryByRole("complementary")).toBeNull();
  });
});
