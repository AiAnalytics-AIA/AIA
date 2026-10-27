// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Figure } from "@/lib/settings-hero";
import { HeroFiguresProvider, useHeroFigures } from "./hero-figures";

afterEach(cleanup);

function Panel({ figures }: { figures: readonly Figure[] | undefined }) {
  useHeroFigures("system", figures);
  return <p>panel</p>;
}

const READY: Figure[] = [{ label: "Připraveno", value: "7 / 9" }];

describe("a panel's hero figures handed up (F18)", () => {
  it("hands its figures once per value, again when they change, and clears them on unmount", () => {
    const hand = vi.fn();
    const { rerender, unmount } = render(<HeroFiguresProvider hand={hand}><Panel figures={READY} /></HeroFiguresProvider>);
    expect(hand).toHaveBeenLastCalledWith("system", READY);
    const calls = hand.mock.calls.length;
    // A new array with the same figures is the same value: nothing handed again.
    rerender(<HeroFiguresProvider hand={hand}><Panel figures={[{ label: "Připraveno", value: "7 / 9" }]} /></HeroFiguresProvider>);
    expect(hand.mock.calls.length).toBe(calls);
    rerender(<HeroFiguresProvider hand={hand}><Panel figures={[{ label: "Připraveno", value: "8 / 9" }]} /></HeroFiguresProvider>);
    expect(hand).toHaveBeenLastCalledWith("system", [{ label: "Připraveno", value: "8 / 9" }]);
    unmount();
    expect(hand).toHaveBeenLastCalledWith("system", undefined);
  });

  it("hands nothing while the panel has no figures to give", () => {
    const hand = vi.fn();
    render(<HeroFiguresProvider hand={hand}><Panel figures={undefined} /></HeroFiguresProvider>);
    expect(hand).toHaveBeenCalledTimes(1);
    expect(hand).toHaveBeenLastCalledWith("system", undefined);
  });

  it("does nothing outside a page that listens: no provider, no error", () => {
    const { getByText, unmount } = render(<Panel figures={READY} />);
    expect(getByText("panel")).toBeTruthy();
    expect(() => unmount()).not.toThrow();
  });
});
