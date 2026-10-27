// @vitest-environment jsdom
// Ctrl+K from anywhere opens the palette; typing narrows it, Enter goes, Esc gives the focus back.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: vi.fn() }) }));
const clients = vi.fn();
vi.mock("@/lib/api", async (original) => ({ ...(await original<typeof import("@/lib/api")>()), workspace: { clients: () => clients() } }));

import { CommandPalette } from "./CommandPalette";

beforeEach(() => {
  push.mockReset();
  clients.mockReset();
  clients.mockResolvedValue([{ client_id: "c1", name: "Pivovar Zlatá Hora", slug: "c1", your_role: null, active_count: 0, study_count: 0, modified_at: null, recent: [] }]);
});
afterEach(cleanup);

const ctrlK = () => act(() => { fireEvent.keyDown(window, { key: "k", ctrlKey: true }); });

describe("CommandPalette", () => {
  it("opens on Ctrl+K, finds a client accent-folded and goes there on Enter", async () => {
    render(<CommandPalette />);
    ctrlK();
    const box = await screen.findByRole("combobox", { name: t("aia.palette.title") });
    await waitFor(() => expect(clients).toHaveBeenCalledTimes(1));
    fireEvent.change(box, { target: { value: "zlata" } });
    await screen.findByRole("option", { name: /Pivovar Zlatá Hora/ });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(push).toHaveBeenCalledWith("/app/clients/c1");
  });

  it("moves with the arrows and opens a settings section", async () => {
    render(<CommandPalette />);
    ctrlK();
    const box = await screen.findByRole("combobox");
    fireEvent.change(box, { target: { value: "audit" } });
    const option = await screen.findByRole("option", { name: /Audit/ });
    expect(option.getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(box, { key: "ArrowDown" });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(push).toHaveBeenCalledWith("/app/settings#audit");
  });

  it("leaves the key to a handler that took it first, as Settings' section menu does", () => {
    const first = (e: KeyboardEvent) => e.preventDefault();
    window.addEventListener("keydown", first);
    render(<CommandPalette />);
    ctrlK();
    expect(screen.queryByRole("combobox")).toBeNull();
    window.removeEventListener("keydown", first);
  });

  it("says when nothing matches and when clients could not be read, never a blank list", async () => {
    clients.mockRejectedValue(new Error("down"));
    render(<CommandPalette />);
    fireEvent.click(screen.getByRole("button", { name: /Hledat nebo přejít/ }));
    const box = await screen.findByRole("combobox");
    await screen.findByText(t("aia.palette.clientsUnread"));
    fireEvent.change(box, { target: { value: "qqqq" } });
    expect(screen.getByText("Nic nenalezeno pro „qqqq“.")).toBeTruthy();
  });
});
