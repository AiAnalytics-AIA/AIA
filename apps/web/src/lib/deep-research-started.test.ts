// @vitest-environment jsdom
// A run a Lead card started reaches the Deep Research panel already on screen (review of #1006).
import { describe, expect, it, vi } from "vitest";

import { announceDeepResearchStarted, onDeepResearchStarted } from "./deep-research-started";

describe("deep research started", () => {
  it("tells every follower the run and its purpose, and stops once unsubscribed", () => {
    const heard = vi.fn();
    const stop = onDeepResearchStarted(heard);
    announceDeepResearchStarted({ runId: "RUN-dr1", purpose: "DESIGN_RESEARCH" });
    expect(heard).toHaveBeenCalledWith({ runId: "RUN-dr1", purpose: "DESIGN_RESEARCH" });
    stop();
    announceDeepResearchStarted({ runId: "RUN-dr2", purpose: null });
    expect(heard).toHaveBeenCalledTimes(1);
  });
});
