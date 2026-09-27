import { describe, expect, it } from "vitest";

import { legacyContext, statement } from "../testing/legacy";
import { CLASSIC_ROUTE, RAIL_STEPS, STEP_KEYS, stepEyebrow } from "./steps";

const legacy = legacyContext({
  prelude: [
    "var RESEARCH_STEPS=[];",
    statement("RESEARCH_STEPS.splice(0,RESEARCH_STEPS.length,", ");", { last: true }),
    "var __eye={textContent:''},__prog={innerHTML:''};var $=s=>s==='#stepEyebrow1782'?__eye:s==='#stepProgress1782'?__prog:null;var SIM_STEPS_1773=[];",
  ],
  functions: ["updateTopbarProgress1782"],
});

describe("the research steps are the classic ones", () => {
  it("the rail is RESEARCH_STEPS after its final splice", () => {
    expect(RAIL_STEPS.map((s) => [s.key, s.num, s.label, s.sub])).toEqual(legacy.run("RESEARCH_STEPS"));
  });

  it.each(STEP_KEYS.map((k) => [k] as const))("the eyebrow on %s is updateTopbarProgress1782's", (k) => {
    const text = legacy.run<string>("updateTopbarProgress1782();__eye.textContent", { PRODUCT_PATH: "research", CURRENT: CLASSIC_ROUTE[k] });
    const marks = legacy.run<string>("__prog.innerHTML", {});
    const e = stepEyebrow(k);
    expect(e.text).toBe(text);
    expect((marks.match(/class="done"/g) ?? []).length).toBe(e.done);
    expect((marks.match(/<i /g) ?? []).length).toBe(e.total);
  });
});
