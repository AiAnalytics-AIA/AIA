// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { SpendDialog } from "./SpendDialog";

// jsdom has <dialog> without showModal/close: the modal's open state, as a browser sets it.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.removeAttribute("open");
  };
});
afterEach(cleanup);

const confirm = () =>
  render(
    <SpendDialog
      open
      question="q"
      kind="spend_confirm"
      summary="Horní mez běhu dosahuje vašeho prahu potvrzení."
      ceilingUsd={28.4}
      ceilingNote="600 dotazů × rezervace + 8 modulů"
      lines={[
        { name: "study_budget", usd: 80, remainingUsd: 57.8 },
        { name: "threshold", usd: 25 },
      ]}
      pays="study_budget"
      confirmLabel="Spustit běh · do 28,40 USD"
      onConfirm={vi.fn()}
      onCancel={vi.fn()}
    />,
  );

describe("SpendDialog (I7a): the one modal for money", () => {
  it("is titled by its kind, states the ceiling as an upper bound and the sums by their names", () => {
    confirm();
    const dialog = screen.getByRole("dialog", { name: "Potvrzení útraty" });
    expect(dialog.textContent).toContain("Horní mez");
    expect(screen.getByTestId("spend-ceiling").textContent).toBe("28,40 USD · horní mez, ne odhad600 dotazů × rezervace + 8 modulů");
    expect(dialog.textContent).toContain("Rozpočet studie");
    expect(dialog.textContent).toContain("80,00 USD · zbývá 57,80 USD");
    expect(dialog.textContent).toContain("Práh potvrzení");
    expect(screen.getByTestId("spend-after").textContent).toContain("I při nejvyšší ceně zbude 29,40 USD.");
  });

  it("focuses the safe choice; the primary button names the act and the price, never OK", () => {
    confirm();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Zrušit" }));
    expect(screen.getByRole("button", { name: "Spustit běh · do 28,40 USD" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "OK" })).toBeNull();
  });

  it("says an unknown ceiling and an unknown remainder in words, never as zero", () => {
    render(
      <SpendDialog
        open
        question="q"
        kind="spend_confirm"
        summary="Spustit běh."
        ceilingUsd={null}
        lines={[{ name: "study_budget", usd: null, remainingUsd: null }]}
        pays="study_budget"
        confirmLabel="Spustit běh"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    const text = screen.getByRole("dialog").textContent ?? "";
    expect(text).toContain("nelze předem určit");
    expect(text).toContain("neznámá cena se nikdy nepočítá jako nula");
    expect(text).toContain("neznámé · zbývá neznámé");
    expect(text).toContain("Kolik zbude, nelze spočítat");
    expect(text).not.toMatch(/0,00/);
  });

  it("Esc and the safe button cancel; the primary confirms", () => {
    const yes = vi.fn();
    const no = vi.fn();
    render(
      <SpendDialog open question="q" kind="spend_confirm" summary="x" ceilingUsd={1} lines={[]} confirmLabel="Spustit · do 1,00 USD" onConfirm={yes} onCancel={no} />,
    );
    fireEvent(screen.getByRole("dialog"), new Event("cancel", { cancelable: true }));
    expect(no).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Zrušit" }));
    expect(no).toHaveBeenCalledTimes(2);
    fireEvent.click(screen.getByRole("button", { name: "Spustit · do 1,00 USD" }));
    expect(yes).toHaveBeenCalledWith(undefined);
  });

  it("a lift sets the new amount with a money stepper; what is left follows it, and the yes carries it", () => {
    const yes = vi.fn();
    render(
      <SpendDialog
        open
        question="q"
        kind="study_budget_lift"
        summary="8 kroků analýzy čeká."
        ceilingUsd={1.76}
        lines={[{ name: "study_budget", usd: 80, remainingUsd: 0.9 }]}
        pays="study_budget"
        amount={{ value: 85, min: 80.86, max: 500, step: 5 }}
        confirmLabel={(usd) => `Zvýšit na ${usd} USD a pokračovat`}
        cancelLabel="Nechat čekat"
        onConfirm={yes}
        onCancel={() => {}}
      />,
    );
    expect(screen.getByRole("dialog", { name: "Zvýšení rozpočtu studie" })).toBeTruthy();
    expect(screen.getByTestId("spend-after").textContent).toContain("zbude 4,14 USD");
    const amount = screen.getByRole("spinbutton", { name: "Nová částka" });
    fireEvent.keyDown(amount, { key: "ArrowUp" });
    expect(screen.getByTestId("spend-after").textContent).toContain("zbude 9,14 USD");
    fireEvent.click(screen.getByRole("button", { name: "Zvýšit na 90 USD a pokračovat" }));
    expect(yes).toHaveBeenCalledWith(90);
  });

  it("a lift refuses an amount out of range at the field and waits until it is valid", () => {
    const yes = vi.fn();
    render(
      <SpendDialog
        open
        question="q"
        kind="client_budget_lift"
        summary="Návrhy znalostí ze souboru čekají."
        ceilingUsd={0.31}
        lines={[{ name: "client_budget", usd: 5, remainingUsd: -0.06 }]}
        pays="client_budget"
        amount={{ value: 10, min: 5.37, max: 100 }}
        confirmLabel={(usd) => `Zvýšit na ${usd} USD a pokračovat`}
        onConfirm={yes}
        onCancel={() => {}}
      />,
    );
    const amount = screen.getByRole("spinbutton", { name: "Nová částka" });
    fireEvent.change(amount, { target: { value: "2" } });
    fireEvent.blur(amount);
    expect(screen.getByRole("alert").textContent).toBe("Musí být 5,37–100 USD; neuloženo.");
    const go = screen.getByRole("button", { name: /Zvýšit na/ }) as HTMLButtonElement;
    expect(go.disabled).toBe(true);
    fireEvent.change(amount, { target: { value: "20" } });
    fireEvent.blur(amount);
    fireEvent.click(screen.getByRole("button", { name: "Zvýšit na 20 USD a pokračovat" }));
    expect(yes).toHaveBeenCalledWith(20);
  });

  it("a question queued behind another starts from its own amount, never the one typed before (Codex #532)", () => {
    const yes = vi.fn();
    const ask = (question: string, value: number, min: number) => (
      <SpendDialog
        open
        question={question}
        kind="study_budget_lift"
        summary={`Krok ${question} čeká.`}
        ceilingUsd={1}
        lines={[{ name: "study_budget", usd: 80, remainingUsd: 0 }]}
        pays="study_budget"
        amount={{ value, min, max: 500 }}
        confirmLabel={(usd) => `Zvýšit na ${usd} USD`}
        onConfirm={yes}
        onCancel={() => {}}
      />
    );
    const { rerender } = render(ask("A", 85, 81));
    // A: a refused amount typed in, then a valid one.
    const a = screen.getByRole("spinbutton", { name: "Nová částka" });
    fireEvent.change(a, { target: { value: "2" } });
    fireEvent.blur(a);
    expect(screen.getByRole("alert")).toBeTruthy();
    fireEvent.change(a, { target: { value: "120" } });
    fireEvent.blur(a);
    // B replaces A while the dialog stays open.
    rerender(ask("B", 95, 90));
    expect(screen.getByText("Krok B čeká.")).toBeTruthy();
    expect((screen.getByRole("spinbutton", { name: "Nová částka" }) as HTMLInputElement).value).toBe("95,00");
    expect(screen.queryByRole("alert")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Zvýšit na 95 USD" }));
    expect(yes).toHaveBeenCalledWith(95);

    // And an amount refused in C does not hold the next question's confirmation back.
    rerender(ask("C", 85, 81));
    const c = screen.getByRole("spinbutton", { name: "Nová částka" });
    fireEvent.change(c, { target: { value: "2" } });
    fireEvent.blur(c);
    expect((screen.getByRole("button", { name: /Zvýšit na/ }) as HTMLButtonElement).disabled).toBe(true);
    rerender(ask("D", 100, 90));
    expect((screen.getByRole("button", { name: "Zvýšit na 100 USD" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("says a refusal from the server inside the dialog", () => {
    render(
      <SpendDialog open question="q" kind="wallet_lift" summary="x" ceilingUsd={18.4} lines={[{ name: "wallet", usd: 40, remainingUsd: 12 }]} confirmLabel="Navýšit" error="Nad stropem klienta schvaluje vlastník." onConfirm={() => {}} onCancel={() => {}} />,
    );
    expect(screen.getByRole("dialog", { name: "Navýšení peněženky" })).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toBe("Nad stropem klienta schvaluje vlastník.");
  });
});
