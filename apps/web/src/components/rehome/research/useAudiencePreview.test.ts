// @vitest-environment jsdom
// Proveditelnost is asked once the audience stops changing, and shows only the answer to what is stored.
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AudiencePreview } from "@/lib/api";
import { PREVIEW_DEBOUNCE_MS, useAudiencePreview } from "./useAudiencePreview";

const answer = (selected_rows: number): AudiencePreview => ({
  version_id: "DSV-1", version_label: "v17_4_0", population_rows: 1000, selected_rows, selected_donors: null,
  filters_applied: {}, per_filter: null, audience: { ok: true }, n: 300, sample: { ok: true, status: "PASS" }, seed: 1,
});

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

const flush = async (ms = 0) => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
};

describe("useAudiencePreview", () => {
  it("asks once, after the last change has settled, and is busy until the answer comes", async () => {
    const read = vi.fn(async () => answer(500));
    const { result, rerender } = renderHook(({ filters }) => useAudiencePreview(filters, 300, read), { initialProps: { filters: {} as Record<string, unknown> } });
    expect(result.current).toEqual({ answer: null, error: null, busy: true });
    await flush(PREVIEW_DEBOUNCE_MS - 1);
    rerender({ filters: { kraj: ["A"] } });
    await flush(PREVIEW_DEBOUNCE_MS - 1);
    expect(read).not.toHaveBeenCalled();
    await flush(1);
    expect(read).toHaveBeenCalledTimes(1);
    expect(read).toHaveBeenCalledWith({ kraj: ["A"] }, 300);
    expect(result.current).toMatchObject({ busy: false, error: null });
    expect(result.current.answer?.selected_rows).toBe(500);
  });

  it("drops an answer to an older question, and keeps the last answer while a newer one is asked", async () => {
    const pending: ((a: AudiencePreview) => void)[] = [];
    const read = vi.fn(() => new Promise<AudiencePreview>((resolve) => pending.push(resolve)));
    const { result, rerender } = renderHook(({ n }) => useAudiencePreview({}, n, read), { initialProps: { n: 300 } });
    await flush(PREVIEW_DEBOUNCE_MS);
    rerender({ n: 400 });
    await flush(PREVIEW_DEBOUNCE_MS);
    expect(read).toHaveBeenCalledTimes(2);
    // The second question is answered first; the first's late answer must not replace it.
    await act(async () => pending[1]!(answer(400)));
    await act(async () => pending[0]!(answer(300)));
    expect(result.current.answer?.selected_rows).toBe(400);
    expect(result.current.busy).toBe(false);
    // A newer question keeps the shown answer, busy, until it is answered.
    rerender({ n: 500 });
    expect(result.current).toMatchObject({ busy: true });
    expect(result.current.answer?.selected_rows).toBe(400);
  });

  it("keeps a failure as the error, without the answer it no longer counts", async () => {
    let fail = false;
    const read = vi.fn(async () => {
      if (fail) throw new Error("no population");
      return answer(500);
    });
    const { result, rerender } = renderHook(({ n }) => useAudiencePreview({}, n, read), { initialProps: { n: 300 } });
    await flush(PREVIEW_DEBOUNCE_MS);
    fail = true;
    rerender({ n: 400 });
    await flush(PREVIEW_DEBOUNCE_MS);
    expect(result.current.answer).toBeNull();
    expect((result.current.error as Error).message).toBe("no population");
    expect(result.current.busy).toBe(false);
  });
});
