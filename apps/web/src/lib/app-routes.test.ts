import { describe, expect, it } from "vitest";

import { STEP_KEYS, stepFromSlug, stepSlug } from "@/research/steps";
import { appRoutes } from "./app-routes";

describe("the client-first URLs (ADR 0015)", () => {
  it("put every study under its client, and every stage under its study", () => {
    expect(appRoutes.stage("CLI-a", "STU-1", "questionnaire")).toBe("/app/clients/CLI-a/research/STU-1/questionnaire");
    expect(appRoutes.study("CLI-a", "STU-2", "SIMULATION")).toBe("/app/clients/CLI-a/simulations/STU-2");
    expect(appRoutes.area("CLI-a", "overview")).toBe("/app/clients/CLI-a");
    expect(appRoutes.area("CLI-a", "knowledge")).toBe("/app/clients/CLI-a/knowledge");
    expect(appRoutes.home()).toBe("/app/clients");
  });
  it("name the dimension step by what the researcher sees, and give the classic name no URL", () => {
    expect(appRoutes.stage("CLI-a", "STU-1", "persona")).toBe("/app/clients/CLI-a/research/STU-1/dimensions");
    expect(stepFromSlug("dimensions")).toBe("persona");
    expect(stepFromSlug("persona")).toBeNull();
    expect(stepFromSlug("../x")).toBeNull();
    for (const k of STEP_KEYS) expect(stepFromSlug(stepSlug(k))).toBe(k);
  });
  it("encode what they are given", () => {
    expect(appRoutes.client("CLI-a/../b")).toBe("/app/clients/CLI-a%2F..%2Fb");
  });
});
