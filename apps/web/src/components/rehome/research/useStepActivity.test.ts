// @vitest-environment jsdom
// The feed is read after its cursor while something runs, once more when it stops, then never.
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { RunEvent } from "@/lib/api";
import { ACTIVITY_POLL_MS, useStepActivity } from "./useStepActivity";

const ev = (event_id: number, message: string): RunEvent => ({
  event_id, step_id: "STEP-a", attempt_id: "ATT-1", event_type: "STEP_PROGRESS", level: "INFO",
  message, payload: {}, created_at: null,
});

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

const flush = async (ms = 0) => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
};

describe("useStepActivity", () => {
  it("reads after its cursor on every tick while live, once more when it stops, then not again", async () => {
    const feed = [ev(1, "první"), ev(2, "druhý")];
    const read = vi.fn(async (since: number) => feed.filter((e) => e.event_id > since));
    const { result, rerender } = renderHook(({ live }) => useStepActivity("RUN-1", read, live), { initialProps: { live: true } });
    await flush();
    expect(read).toHaveBeenLastCalledWith(0);
    expect(result.current.steps["STEP-a"].lines.map((l) => l.text)).toEqual(["první", "druhý"]);

    feed.push(ev(3, "třetí"));
    await flush(ACTIVITY_POLL_MS);
    expect(read).toHaveBeenLastCalledWith(2);
    expect(result.current.steps["STEP-a"].lines.at(-1)?.text).toBe("třetí");

    feed.push(ev(4, "hotovo"));
    rerender({ live: false });
    await flush();
    expect(read).toHaveBeenLastCalledWith(3);
    expect(result.current.steps["STEP-a"].lines.at(-1)?.text).toBe("hotovo");

    const calls = read.mock.calls.length;
    await flush(ACTIVITY_POLL_MS * 5);
    expect(read.mock.calls.length).toBe(calls);
  });

  it("keeps what it read when a read fails, and tries again on the next tick", async () => {
    let fail = false;
    const read = vi.fn(async (since: number) => {
      if (fail) throw new Error("network");
      return [ev(1, "první"), ev(2, "druhý")].filter((e) => e.event_id > since);
    });
    const { result } = renderHook(() => useStepActivity("RUN-1", read, true));
    await flush();
    fail = true;
    await flush(ACTIVITY_POLL_MS);
    expect(result.current.steps["STEP-a"].lines).toHaveLength(2);
    fail = false;
    await flush(ACTIVITY_POLL_MS);
    expect(read).toHaveBeenLastCalledWith(2);
  });

  it("a new run starts from nothing; no run reads nothing", async () => {
    const read = vi.fn(async (since: number) => (since === 0 ? [ev(7, "jiný běh")] : []));
    const { result, rerender } = renderHook(({ key }) => useStepActivity(key, read, false), {
      initialProps: { key: "RUN-1" as string | null },
    });
    await flush();
    expect(result.current.cursor).toBe(7);
    rerender({ key: "RUN-2" });
    await flush();
    expect(read).toHaveBeenLastCalledWith(0);
    read.mockClear();
    rerender({ key: null });
    await flush(ACTIVITY_POLL_MS * 2);
    expect(read).not.toHaveBeenCalled();
    expect(result.current.cursor).toBe(0);
  });
});
