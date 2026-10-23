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
const members = { ok: true as const, data: [{ user_id: "USR-1", email: "owner@example.test", display_name: "Petr Kolář", is_active: true, organization_role: "OWNER" }] };
const clients = { ok: true as const, data: [{ client_id: "CLI-a", slug: "a", name: "Moravská pojišťovna", status: "ACTIVE", reference: "", study_count: 1, created_at: null }] };
const studies = { ok: true as const, data: [{ study: { study_id: "STU-1", client_id: "CLI-a", name: "Vnímání značky" }, detail: { ok: false, message: "" } } as unknown as StudyRow] };

const draw = (data: AuditEntry[]) => render(<AuditPanel audit={{ ok: true, data }} members={members} clients={clients} studies={studies} />);

describe("the audit", () => {
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
    expect(within(row).getByText("Vnímání značky")).toBeTruthy();
    expect(within(row).getByText("100 → 120 USD")).toBeTruthy();
    fireEvent.click(document.querySelector('[data-audit-category="all"]') as HTMLElement);
    fireEvent.click(within(screen.getByRole("radiogroup", { name: "Období" })).getByRole("radio", { name: "Vše" }));
    expect(document.querySelectorAll("[data-audit-entry]")).toHaveLength(3);
    expect(count("method")).toBe("Metodika1");
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

  it("names a deactivated member's sealed Lead and the system as its actor", () => {
    draw([entry(1, "LEAD_SEALED", ago(0), { actor_id: null, subject_user_id: "USR-1" })]);
    const row = document.querySelector("[data-audit-entry]") as HTMLElement;
    expect(within(row).getByText("Vedoucí zapečetěn")).toBeTruthy();
    expect(within(row).getByText("Systém")).toBeTruthy();
    expect(row.getAttribute("data-category")).toBe("lead");
  });
});
