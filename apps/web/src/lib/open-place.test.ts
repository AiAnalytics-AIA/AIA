// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { openPlace, scrollBehavior, scrollToPlace } from "./open-place";

let scrolled: { id: string; options: ScrollIntoViewOptions | boolean | undefined }[] = [];
const original = Element.prototype.scrollIntoView;

beforeEach(() => {
  scrolled = [];
  Element.prototype.scrollIntoView = function (this: Element, options?: ScrollIntoViewOptions | boolean) {
    scrolled.push({ id: this.id, options });
  };
  document.body.innerHTML = `
    <main>
      <a id="start" href="#x">Začátek</a>
      <div id="card"><input id="field" /></div>
      <h2 id="heading">Editor</h2>
      <button id="action" type="button">Akce</button>
      <section id="kept" tabindex="0">Sekce</section>
    </main>`;
  (document.getElementById("start") as HTMLElement).focus();
});
afterEach(() => {
  Element.prototype.scrollIntoView = original;
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
});

const reduceMotion = (reduce: boolean) =>
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: reduce && query === "(prefers-reduced-motion: reduce)", media: query }));

describe("openPlace", () => {
  it("scrolls to a card and moves keyboard focus to it, without putting it in the Tab order", () => {
    // Review web#7: the page scrolled to the gap's place and focus stayed at the start of the page.
    expect(openPlace("card", "center")).toBe(true);
    expect(scrolled).toEqual([{ id: "card", options: { behavior: "smooth", block: "center" } }]);
    expect(document.activeElement?.id).toBe("card");
    expect(document.getElementById("card")?.getAttribute("tabindex")).toBe("-1");
    openPlace("heading", "start");
    expect(document.activeElement?.id).toBe("heading");
  });

  it("leaves an element that takes focus with its own Tab order", () => {
    openPlace("action", "start");
    expect(document.activeElement?.id).toBe("action");
    expect(document.getElementById("action")?.hasAttribute("tabindex")).toBe(false);
    openPlace("kept", "start");
    expect(document.activeElement?.id).toBe("kept");
    expect(document.getElementById("kept")?.getAttribute("tabindex")).toBe("0");
  });

  it("jumps without the smooth scroll when the person asked for reduced motion", () => {
    reduceMotion(true);
    expect(scrollBehavior()).toBe("auto");
    openPlace("card", "center");
    scrollToPlace("heading", "start");
    expect(scrolled.map((s) => s.options)).toEqual([{ behavior: "auto", block: "center" }, { behavior: "auto", block: "start" }]);
    reduceMotion(false);
    expect(scrollBehavior()).toBe("smooth");
  });

  it("does nothing for a place the page does not have", () => {
    expect(openPlace("gone", "center")).toBe(false);
    expect(scrollToPlace("gone", "center")).toBe(false);
    expect(scrolled).toEqual([]);
    expect(document.activeElement?.id).toBe("start");
  });

  it("scrolls without moving focus where only a scroll is asked (an outline row)", () => {
    expect(scrollToPlace("card", "center")).toBe(true);
    expect(scrolled).toEqual([{ id: "card", options: { behavior: "smooth", block: "center" } }]);
    expect(document.activeElement?.id).toBe("start");
  });
});
