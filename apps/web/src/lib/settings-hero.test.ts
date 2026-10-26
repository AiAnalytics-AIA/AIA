import { describe, expect, it } from "vitest";

import type { AdminClient, AuditEntry, Member } from "./api";
import { accessFigures, auditFigures } from "./settings-hero";

const AW = { active: "Aktivní členové", deactivated: "Deaktivovaní", methodologist: "Metodik", clients: "Klienti", selfApproval: "Samoschválení v organizaci", allowed: "povoleno", forbidden: "zakázáno", byDefault: "výchozí" };
const member = (over: Partial<Member>): Member => ({ user_id: "u", email: "a@example.test", display_name: "A", is_active: true, organization_role: "RESEARCHER", methodologist: false, ...over });
const client = (id: string): AdminClient => ({ client_id: id, slug: id, name: id, status: "ACTIVE", reference: "", study_count: 0, created_at: null });
const value = (figures: { label: string; value: string | null }[], label: string) => figures.find((f) => f.label === label)?.value;

describe("Přístup's hero figures (F18)", () => {
  it("counts active, deactivated and Metodik members, clients and the organization's rule", () => {
    const members = [member({ user_id: "a", methodologist: true }), member({ user_id: "b" }), member({ user_id: "c", deactivated_at: "2026-10-20T10:00:00Z", methodologist: true })];
    const f = accessFigures({ ok: true, data: members }, { ok: true, data: [client("x"), client("y")] }, { ok: true, data: { organization: false, clients: [], studies: [] } }, AW);
    expect(f.map((x) => [x.label, x.value])).toEqual([
      ["Aktivní členové", "2"], ["Deaktivovaní", "1"], ["Metodik", "1"], ["Klienti", "2"], ["Samoschválení v organizaci", "zakázáno"],
    ]);
  });

  it("leaves out Deaktivovaní when nobody is, and says unknown for a read that failed or was not made", () => {
    const f = accessFigures({ ok: false }, { ok: false }, null, AW);
    expect(f.map((x) => x.label)).toEqual(["Aktivní členové", "Metodik", "Klienti", "Samoschválení v organizaci"]);
    expect(f.every((x) => x.value === null)).toBe(true);
    // A rule never set reads as the default, not as allowed.
    const unset = accessFigures({ ok: true, data: [member({})] }, { ok: true, data: [] }, { ok: true, data: { organization: null, clients: [], studies: [] } }, AW);
    expect(value(unset, "Samoschválení v organizaci")).toBe("výchozí");
    expect(value(unset, "Klienti")).toBe("0");
  });
});

const NOW = Date.parse("2026-10-26T12:00:00Z");
const AUW = { inPeriod: "Události · 7 dní", today: "Dnes", people: "Kdo měnil", last: "Poslední změna" };
const at = (iso: string, actor: string | null = "u1", id = 1): AuditEntry => ({ event_id: id, action: "MEMBER_ADDED", client_id: null, study_id: null, subject_user_id: null, actor_id: actor, role: null, reason: "", payload: {}, created_at: iso });
const when = (iso: string) => `kdy:${iso}`;

describe("Audit's hero figures (F18)", () => {
  it("counts the week's events, today's, the people who changed something and the newest change", () => {
    const list = [at("2026-10-26T09:00:00Z", "u1", 3), at("2026-10-24T09:00:00Z", "u2", 2), at("2026-10-10T09:00:00Z", "u3", 1)];
    const f = auditFigures({ ok: true, data: list }, 50, NOW, AUW, when);
    expect(f.map((x) => x.value)).toEqual(["2", "1", "2", "kdy:2026-10-26T09:00:00Z"]);
  });

  it("says unknown, never the part read, when a full page does not reach back over the window", () => {
    // Two rows, a page of two, both inside the week: the week may hold more than was read.
    const list = [at("2026-10-26T09:00:00Z"), at("2026-10-25T09:00:00Z")];
    const f = auditFigures({ ok: true, data: list }, 2, NOW, AUW, when);
    // Today is read whole (the oldest row is from yesterday); the week is not.
    expect(f.map((x) => x.value)).toEqual([null, "1", null, "kdy:2026-10-26T09:00:00Z"]);
  });

  it("says unknown without the read, for a row with no date, and for no event at all", () => {
    expect(auditFigures(null, 50, NOW, AUW, when).every((x) => x.value === null)).toBe(true);
    const undated = auditFigures({ ok: true, data: [{ ...at("2026-10-26T09:00:00Z"), created_at: null }] }, 50, NOW, AUW, when);
    expect(undated.slice(0, 3).every((x) => x.value === null)).toBe(true);
    const none = auditFigures({ ok: true, data: [] }, 50, NOW, AUW, when);
    expect(none.map((x) => x.value)).toEqual(["0", "0", "0", null]);
  });
});
