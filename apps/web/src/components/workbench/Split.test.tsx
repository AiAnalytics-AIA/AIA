// @vitest-environment jsdom
// The open drawer or sheet keeps the focus inside when the control that held it unmounts
// (research-lead-workbench, D21): a card's button replaced by its result left the focus on the body,
// outside the modal and behind an inert page.
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { Split, recoveryTarget } from "./Split";

afterEach(cleanup);

function Conversation({ composer = true }: { composer?: boolean }) {
  const [done, setDone] = useState(false);
  return (
    <div>
      <div role="log" tabIndex={0} aria-label="Konverzace">
        {done ? <p>Rozhodnuto</p> : <button type="button" onClick={() => setDone(true)}>Spustit úlohu</button>}
      </div>
      {composer ? <textarea aria-label="Napište Vedoucímu výzkumu" /> : <textarea aria-label="Napište Vedoucímu výzkumu" disabled />}
    </div>
  );
}

const bench = (shown: boolean, composer = true) =>
  render(<Split split={40} mode="split" layout="sheet" shown={shown} leftLabel="Vedoucí výzkumu" onSplit={() => {}} onCommit={() => {}}
    left={<Conversation composer={composer} />} right={<div>artefakt</div>} rail={<button type="button">Vedoucí</button>} />);

describe("focus recovery in the open drawer or sheet", () => {
  it("brings the focus to the composer when the focused card control unmounts", async () => {
    bench(true);
    const button = screen.getByRole("button", { name: "Spustit úlohu" });
    button.focus();
    act(() => button.click());
    await waitFor(() => expect(document.activeElement).toBe(screen.getByLabelText("Napište Vedoucímu výzkumu")));
  });

  it("brings it to the log when the composer takes no text", async () => {
    bench(true, false);
    const button = screen.getByRole("button", { name: "Spustit úlohu" });
    button.focus();
    act(() => button.click());
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("log")));
  });

  it("leaves the focus alone when the conversation is closed, and when the person moved it themselves", async () => {
    bench(false);
    const button = screen.getByText("Spustit úlohu");
    button.focus();
    act(() => button.click());
    await new Promise((r) => setTimeout(r, 20));
    expect(document.activeElement).toBe(document.body);
    cleanup();
    bench(true);
    const held = screen.getByRole("button", { name: "Spustit úlohu" });
    held.focus();
    act(() => held.blur());
    await new Promise((r) => setTimeout(r, 20));
    expect(document.activeElement).toBe(document.body);
    // The button the person left unmounts later (a poll re-renders its card): nothing is taken
    // back, so a phone's keyboard never pops up on its own (review of #683).
    act(() => held.click());
    await waitFor(() => expect(screen.queryByRole("button", { name: "Spustit úlohu" })).toBeNull());
    await new Promise((r) => setTimeout(r, 20));
    expect(document.activeElement).toBe(document.body);
  });

  it("picks the composer, else the log, else the dialog itself", () => {
    const box = document.createElement("div");
    expect(recoveryTarget(box)).toBe(box);
    box.innerHTML = '<div role="log"></div>';
    expect(recoveryTarget(box)).toBe(box.firstElementChild);
    box.innerHTML = '<div role="log"></div><textarea></textarea>';
    expect(recoveryTarget(box)).toBe(box.querySelector("textarea"));
    box.innerHTML = '<div role="log"></div><div hidden><textarea></textarea></div>';
    expect(recoveryTarget(box)).toBe(box.querySelector('[role="log"]'));
  });
});
