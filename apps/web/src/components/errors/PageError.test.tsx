// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const loadConfig = vi.fn();
const startErrorTracking = vi.fn();
const reportError = vi.fn();
vi.mock("@/lib/auth", () => ({ loadConfig: () => loadConfig() }));
vi.mock("@/lib/error-tracking", () => ({
  reportError: (...a: unknown[]) => reportError(...a),
  startErrorTracking: (...a: unknown[]) => startErrorTracking(...a),
}));

import { PageError } from "./PageError";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("a page that crashed while rendering", () => {
  it("reports the crash and starts the reporter itself, since the root layout may be gone", async () => {
    const settings = { dsn: "https://k@errors.aia.example.test/3", environment: "develop", release: null };
    loadConfig.mockResolvedValue({ errorTracking: settings });
    const error = Object.assign(new Error("boom"), { digest: "d-1" });
    render(<PageError error={error} reset={() => undefined} boundary="global" />);

    expect(reportError).toHaveBeenCalledWith(error, { boundary: "global", digest: "d-1" });
    await vi.waitFor(() => expect(startErrorTracking).toHaveBeenCalledWith(settings));
    expect(screen.getByText("d-1")).toBeTruthy();
  });

  it("still says what happened when /config cannot be read", async () => {
    loadConfig.mockRejectedValue(new Error("offline"));
    render(<PageError error={new Error("boom")} reset={() => undefined} boundary="app" />);
    expect(screen.getByRole("heading").textContent).toBe("Tuto stránku se nepodařilo zobrazit");
    await vi.waitFor(() => expect(loadConfig).toHaveBeenCalled());
    expect(startErrorTracking).not.toHaveBeenCalled();
  });
});
