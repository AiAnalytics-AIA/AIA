// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { AuditEntry } from "@/lib/api";
import { AuditPanel } from "./AuditPanel";
import type { StudyRow } from "./StudiesPanel";

afterEach(cleanup);

const ago = (days: number) => new Date(Date.now() - days * 86_400_000).toISOString();
const entry = (event_id: number, action: string, created_at: string | null, extra: Partial<AuditEntry> = {}): AuditEntry => ({
  event_id, action, client_id: null, study_id: null, subject_user_id: null, actor_id: "USR-1", role: null, reason: "", payload: {}, created_at, ...extra,
});
const members = { ok: true as const, data: [{ user_id: "USR-1", email: "owner@example.test", display_name: "Petr Kolář", is_active: true, organization_role: "OWNER", methodologist: false }] };
const clients = { ok: true as const, data: [{ client_id: "CLI-a", slug: "a", name: "Moravská pojišťovna", status: "ACTIVE", reference: "", study_count: 1, created_at: null }] };
const studies = { ok: true as const, data: [{ study: { study_id: "STU-1", client_id: "CLI-a", name: "Vnímání značky" }, detail: { ok: false, message: "" } } as unknown as StudyRow] };

const draw = (data: AuditEntry[]) => render(<AuditPanel audit={{ ok: true, data }} members={members} clients={clients} studies={studies} />);

describe("the audit", () => {
  it("colours no category with a status: no coral, fault red or green on a chip or a row", () => {
    draw([entry(1, "STUDY_BUDGET_CHANGED", ago(0)), entry(2, "CLIENT_DELETED", ago(0)), entry(3, "MEMBER_ADDED", ago(0))]);
    const html = (document.querySelector("[data-audit-categories]")?.outerHTML ?? "") + [...document.querySelectorAll("[data-audit-entry]")].map((r) => r.outerHTML).join("");
    // The selected chip's signal wash is selection, not a status.
    expect(html).not.toMatch(/status-you|status-fault|in-force|client-\d|bg-signal(?!-wash)/);
  });

  it("says a full page holds only the newest records, and counts a period reaching past them as at least", () => {
    // 500 records, the oldest 3 days ago: 30 days reach past it.
    draw(Array.from({ length: 500 }, (_, i) => entry(i + 1, "MEMBER_ADDED", ago((i * 3) / 500))));
    expect(document.querySelector("[data-audit-truncated]")?.textContent).toMatch(/nejnovějších 500 záznamů; starší nejsou načteny/);
    expect(document.querySelector('[data-audit-category="all"]')?.textContent).toBe("Vše≥ 500");
    cleanup();
    draw([entry(1, "MEMBER_ADDED", ago(0))]);
    expect(document.querySelector("[data-audit-truncated]")).toBeNull();
    expect(document.querySelector('[data-audit-category="all"]')?.textContent).toBe("Vše1");
  });

  it("counts each category in the period, and filters by one", () => {
    draw([
      entry(1, "STUDY_BUDGET_CHANGED", ago(1), { study_id: "STU-1", reason: "100 → 120 USD" }),
      entry(2, "MEMBER_ADDED", ago(2)),
      entry(3, "METHODOLOGY_ACTIVATED", ago(40)),
    ]);
    const count = (c: string) => document.querySelector(`[data-audit-category="${c}"]`)?.textContent;
    // 30 days by default: the methodology record is older.
    expect(count("all")).toBe("Vše2");
    expect(count("money")).toBe("Peníze1");
    expect(count("method")).toBe("Metodika0");
    fireEvent.click(document.querySelector('[data-audit-category="money"]') as HTMLElement);
    const rows = document.querySelectorAll("[data-audit-entry]");
    expect(rows).toHaveLength(1);
    const row = rows[0] as HTMLElement;
    expect(within(row).getByText("Změna rozpočtu studie")).toBeTruthy();
    expect(within(row).getByText("Petr Kolář")).toBeTruthy();
    expect(row.querySelector("[data-audit-concerns]")?.textContent).toBe(" · Vnímání značky");
    expect(within(row).getByText("100 → 120 USD")).toBeTruthy();
    fireEvent.click(document.querySelector('[data-audit-category="all"]') as HTMLElement);
    fireEvent.click(within(screen.getByRole("radiogroup", { name: "Období" })).getByRole("radio", { name: "Vše" }));
    expect(document.querySelectorAll("[data-audit-entry]")).toHaveLength(3);
    expect(count("method")).toBe("Metodika1");
  });

  it("draws prototype v99's four columns, the change in words with the person's reason under it (F10)", () => {
    draw([
      entry(1, "STUDY_BUDGET_CHANGED", ago(0), { study_id: "STU-1", reason: "100.0 -> 120.0" }),
      entry(2, "METHODOLOGY_ACTIVATED", ago(0), { reason: "sociomap v1 -> v2", payload: { module: "sociomap", from: 1, to: 2, why: "Práh páru 12 místo 10." } }),
      entry(3, "MEMBER_DEACTIVATED", ago(0), { reason: "Odchod z agentury" }),
      entry(4, "CLIENT_CREATED", ago(0)),
    ]);
    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Kdy", "Kdo", "Událost", "Důvod / změna"]);
    const row = (id: number) => document.querySelector(`[data-audit-entry="${id}"]`) as HTMLElement;
    // The money change in words; the stored "a -> b" never shown again as a reason.
    expect(row(1).querySelector("[data-audit-change]")?.textContent).toBe("100 → 120 USD");
    expect(row(1).querySelector("[data-audit-why]")).toBeNull();
    expect(row(2).querySelector("[data-audit-change]")?.textContent).toBe("e1 → e2");
    // An organization's record names what changed (the module), never a trailing " · —".
    expect(row(2).querySelector("[data-audit-concerns]")?.textContent).not.toMatch(/—/);
    expect(row(2).querySelector("[data-audit-concerns]")?.textContent?.length).toBeGreaterThan(3);
    expect(row(4).querySelector("[data-audit-concerns]")).toBeNull();
    expect(row(2).querySelector("[data-audit-why]")?.textContent).toBe("Práh páru 12 místo 10.");
    // A reason alone stays the reason; nothing at all is a dash, never invented.
    expect(row(3).querySelector("[data-audit-change]")).toBeNull();
    expect(row(3).querySelector("[data-audit-why]")?.textContent).toBe("Odchod z agentury");
    expect(row(4).lastElementChild?.textContent).toBe("—");
    // The category is named for a reader in the event's cell, its dot decoration.
    expect(row(1).textContent).toContain("Peníze: ");
    // The search reads the change as it is shown.
    fireEvent.change(screen.getByRole("searchbox", { name: "Hledat v historii" }), { target: { value: "120 USD" } });
    expect([...document.querySelectorAll("[data-audit-entry]")].map((r) => r.getAttribute("data-audit-entry"))).toEqual(["1"]);
  });

  it("finds a person's records by their e-mail as well as their name", () => {
    draw([entry(1, "MEMBER_ADDED", ago(0), { subject_user_id: "USR-1" }), entry(2, "STUDY_CREATED", ago(0), { actor_id: "USR-9" })]);
    fireEvent.change(screen.getByRole("searchbox", { name: "Hledat v historii" }), { target: { value: "owner@example.test" } });
    expect([...document.querySelectorAll("[data-audit-entry]")].map((r) => r.getAttribute("data-audit-entry"))).toEqual(["1"]);
  });

  it("shows a code it does not know, in words, under Ostatní, and a record without a time in every period", () => {
    draw([entry(1, "SOMETHING_NEW", null)]);
    expect(document.querySelector('[data-audit-category="other"]')?.textContent).toBe("Ostatní1");
    fireEvent.click(within(screen.getByRole("radiogroup", { name: "Období" })).getByRole("radio", { name: "Dnes" }));
    const row = document.querySelector("[data-audit-entry]") as HTMLElement;
    expect(within(row).getByText("something new")).toBeTruthy();
    expect(row.getAttribute("data-category")).toBe("other");
  });

  it("names an archived client from the archived-inclusive list, and keeps the id of a study the API does not list", () => {
    // admin.clients() asks include_archived=true; a study of an archived client is not listed (ADR 0019): its id stays.
    const archived = { ok: true as const, data: [...clients.data, { client_id: "CLI-z", slug: "z", name: "Archivní klient", status: "ARCHIVED", reference: "", study_count: 1, created_at: null }] };
    render(<AuditPanel audit={{ ok: true, data: [entry(1, "STUDY_STATUS_CHANGED", ago(1), { client_id: "CLI-z", study_id: "STU-z" })] }} members={members} clients={archived} studies={studies} />);
    const row = document.querySelector("[data-audit-entry]") as HTMLElement;
    expect(row.textContent).toContain("Archivní klient");
    expect(row.textContent).toContain("STU-z");
  });

  it("names a deactivated member's sealed Lead and the system as its actor", () => {
    draw([entry(1, "LEAD_SEALED", ago(0), { actor_id: null, subject_user_id: "USR-1" })]);
    const row = document.querySelector("[data-audit-entry]") as HTMLElement;
    expect(within(row).getByText("Vedoucí zapečetěn")).toBeTruthy();
    expect(within(row).getByText("Systém")).toBeTruthy();
    expect(row.getAttribute("data-category")).toBe("lead");
  });
});
