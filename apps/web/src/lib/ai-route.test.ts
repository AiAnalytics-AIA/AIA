import { describe, expect, it } from "vitest";

import { type AiRoute, classLines } from "./ai-route";

const recorded: AiRoute = {
  recorded: true,
  worker: "worker-1",
  build_sha: "abc1234",
  composed_at: "2026-10-28T20:00:00Z",
  runtime: true,
  route_id: "bedrock-eu-primary",
  study_lead: "configured",
  classes: [
    { data_class: "A", refusal: "egress_route_not_approved_for_class", advisory: false },
    { data_class: "B", refusal: null, advisory: true },
    { data_class: "C", refusal: null, advisory: false },
  ],
  lead_refusal: null,
};

describe("the AI route as the worker composed it", () => {
  it("names each class carried, carried only under advisory gates, or refused with its code", () => {
    expect(classLines(recorded)).toEqual([
      { letter: "A", kind: "refused", code: "egress_route_not_approved_for_class" },
      { letter: "B", kind: "advisory", code: null },
      { letter: "C", kind: "carried", code: null },
    ]);
  });

  it("presumes nothing carried when no worker recorded a route", () => {
    expect(classLines({ ...recorded, recorded: false })).toEqual([]);
  });
});
