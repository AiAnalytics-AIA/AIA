import { describe, expect, it } from "vitest";

import { changeOf } from "./audit-change";

const rec = (action: string, reason = "", payload: Record<string, unknown> = {}) => ({ action, reason, payload });

describe("an audit record's change, in words (F10)", () => {
  it("reads a money change the scope repository writes into the reason, never repeating it as a reason", () => {
    expect(changeOf(rec("STUDY_BUDGET_CHANGED", "100.0 -> 120.0"))).toEqual({ change: "100 → 120 USD", why: null });
    expect(changeOf(rec("CLIENT_BUDGET_CHANGED", "60 -> 80.5"))).toEqual({ change: "60 → 80,5 USD", why: null });
    // A threshold cleared or set from none says so in words, never a 0.
    expect(changeOf(rec("STUDY_SPEND_CONFIRM_CHANGED", "None -> 25.0")).change).toBe("bez prahu → 25 USD");
    expect(changeOf(rec("STUDY_SPEND_CONFIRM_CHANGED", "25.0 -> None")).change).toBe("25 USD → bez prahu");
  });

  it("keeps a reason it cannot read as a money change as it was written", () => {
    expect(changeOf(rec("STUDY_BUDGET_CHANGED", "100 → 120 USD")).change).toBe("100 → 120 USD");
    expect(changeOf(rec("STUDY_BUDGET_CHANGED", "abc -> 12")).change).toBe("abc -> 12");
  });

  it("names a status, a role, the self-approval rule and a client's rules in Czech", () => {
    expect(changeOf(rec("CLIENT_STATUS_CHANGED", "DORMANT")).change).toBe("→ Neaktivní");
    expect(changeOf(rec("STUDY_STATUS_CHANGED", "DELIVERED")).change).toBe("→ Předáno");
    expect(changeOf(rec("MEMBER_ADDED", "", { from: "MEMBER", to: "ADMIN" })).change).toBe("výzkumník → správce");
    expect(changeOf(rec("MEMBER_ADDED", "", { from: null, to: "MEMBER" })).change).toBe("nový člen: výzkumník");
    // A name changed under the same role: no role change to show.
    expect(changeOf(rec("MEMBER_ADDED", "", { from: "ADMIN", to: "ADMIN" }))).toEqual({ change: null, why: null });
    expect(changeOf(rec("SELF_APPROVAL_CONFIGURED", "", { level: "client", allow_self_approval: false })).change).toBe("Klient: zakázáno");
    expect(changeOf(rec("SELF_APPROVAL_CONFIGURED", "", { level: "study", allow_self_approval: null })).change).toBe("Studie: dědí");
    expect(changeOf(rec("CLIENT_RULES_CHANGED", "", {
      data_posture: { from: null, to: "OPEN" }, wallet_ceiling_usd: { from: 60, to: null },
    })).change).toBe("Postoj dat: nenastaveno → OPEN; Strop peněženky: 60 USD → bez stropu");
  });

  it("reads versions moved by methodology, prompts and Deep Research rules, with the person's why apart", () => {
    expect(changeOf(rec("METHODOLOGY_ACTIVATED", "x", { module: "sociomap", from: null, to: 3, why: "Práh páru 12" }))).toEqual({ change: "z kódu → v3", why: "Práh páru 12" });
    expect(changeOf(rec("PROMPT_ACTIVATED", "lead v1 -> v2", { prompt_id: "lead", from: "v1", to: "v2", why: "kratší" }))).toEqual({ change: "v1 → v2", why: "kratší" });
    expect(changeOf(rec("DR_SETTING_APPROVED", "k v1 -> v2", { key: "k", from: null, to: 2, why: "" }))).toEqual({ change: "výchozí → v2", why: null });
    expect(changeOf(rec("DR_SETTING_PROPOSED", "k v4", { key: "k", version: 4, value: 365 })).change).toBe("v4: 365");
  });

  it("keeps the reason of a record it knows no shape for, and invents no change", () => {
    expect(changeOf(rec("MEMBER_DEACTIVATED", "Odchod z agentury"))).toEqual({ change: null, why: "Odchod z agentury" });
    expect(changeOf(rec("SOMETHING_NEW", ""))).toEqual({ change: null, why: null });
    expect(changeOf({ action: "CLIENT_RULES_CHANGED", reason: "", payload: null })).toEqual({ change: null, why: null });
  });
});
