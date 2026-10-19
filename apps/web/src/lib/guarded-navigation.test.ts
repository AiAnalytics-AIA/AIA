// @vitest-environment jsdom
// The workbench's navigation goes through a link's click, so a stage's leave guard can stop it.
import { afterEach, describe, expect, it, vi } from "vitest";

import { guardedNavigate } from "./guarded-navigation";

const listeners: ((e: MouseEvent) => void)[] = [];
afterEach(() => {
  for (const l of listeners.splice(0)) document.removeEventListener("click", l, true);
});

describe("guardedNavigate", () => {
  it("navigates with the router when no guard objects, leaving no link behind", () => {
    const push = vi.fn();
    guardedNavigate("/app/clients/C/research/S/plan", push);
    expect(push).toHaveBeenCalledWith("/app/clients/C/research/S/plan");
    expect(document.querySelectorAll("a").length).toBe(0);
  });

  it("lets a stage's capture-phase leave guard stop it, as it stops a link", () => {
    const push = vi.fn();
    const guard = (e: MouseEvent) => {
      if ((e.target as Element).closest("a[href]")) e.preventDefault();
    };
    listeners.push(guard);
    document.addEventListener("click", guard, true);
    guardedNavigate("/app/clients/C/research/S/questionnaire", push);
    expect(push).not.toHaveBeenCalled();
  });
});
