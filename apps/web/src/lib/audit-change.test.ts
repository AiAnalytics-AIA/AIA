import { describe, expect, it } from "vitest";

import { changeOf, concernsOf } from "./audit-change";

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
    expect(changeOf(rec("CLIENT_RULES_CHANGED", "", {
      data_posture: { from: null, to: "OPEN" }, wallet_ceiling_usd: { from: 60, to: null },
    })).change).toBe("Postoj dat: nenastaveno → OPEN; Strop peněženky: 60 USD → bez stropu");
  });

  it("never shows the self-approval writer's own code as a person's reason (review of #955)", () => {
    // scope_repository.set_self_approval writes reason f"{level}={allowed}".
    expect(changeOf(rec("SELF_APPROVAL_CONFIGURED", "client=false", { level: "client", allow_self_approval: false }))).toEqual({ change: "Klient: zakázáno", why: null });
    expect(changeOf(rec("SELF_APPROVAL_CONFIGURED", "study=inherit", { level: "study", allow_self_approval: null }))).toEqual({ change: "Studie: dědí", why: null });
  });

  it("names methodology versions as Metodika does, and shows only the person's reason (review of #955)", () => {
    // methodology_repository.activate writes reason f"{module} {preset|eN} -> {preset|eN}" and payload.why.
    expect(changeOf(rec("METHODOLOGY_ACTIVATED", "sociomap preset -> e3", { module: "sociomap", from: null, to: 3, why: "Práh páru 12" }))).toEqual({ change: "z kódu → e3", why: "Práh páru 12" });
    // No reason given: the writer's code is not shown in its place.
    expect(changeOf(rec("METHODOLOGY_ACTIVATED", "sociomap preset -> e3", { module: "sociomap", from: null, to: 3, why: "" }))).toEqual({ change: "z kódu → e3", why: null });
    expect(changeOf(rec("METHODOLOGY_RESET", "sociomap e3 -> preset", { module: "sociomap", from: 3, to: null, why: "zpět" })).change).toBe("e3 → z kódu");
    // propose writes reason f"{module} {named(base, n)}": the version by its name, no reason.
    expect(changeOf(rec("METHODOLOGY_PROPOSED", "sociomap aia-sociomap-5+e2", { module: "sociomap", version: 2, base_preset: "aia-sociomap-5" }))).toEqual({ change: "aia-sociomap-5+e2", why: null });
  });

  it("names prompt versions as Systémové prompty does: the code's base, or verze N (review of #955)", () => {
    // prompt_repository writes from / to as labels: the baseline's own ("1", "analysis-module-v1") or "eN".
    expect(changeOf(rec("PROMPT_ACTIVATED", "lead 1 -> e2", { prompt_id: "lead", from: "1", to: "e2", why: "kratší" }))).toEqual({ change: "Základ z kódu → verze 2", why: "kratší" });
    expect(changeOf(rec("PROMPT_RESET_TO_BASELINE", "lead e2 -> 1", { prompt_id: "lead", from: "e2", to: "1", why: "" }))).toEqual({ change: "verze 2 → Základ z kódu", why: null });
    expect(changeOf(rec("PROMPT_VERSION_CREATED", "lead e3", { prompt_id: "lead", version: "e3" }))).toEqual({ change: "verze 3", why: null });
  });

  it("reads Deep Research rule versions and a proposed value", () => {
    expect(changeOf(rec("DR_SETTING_APPROVED", "k v1 -> v2", { key: "k", from: null, to: 2, why: "" }))).toEqual({ change: "výchozí → v2", why: null });
    expect(changeOf(rec("DR_SETTING_PROPOSED", "k v4", { key: "k", version: 4, value: 365 })).change).toBe("v4: 365");
  });

  it("says a writer's reason code in Czech, never raw (review of #955)", () => {
    expect(changeOf(rec("MEMBER_ROLE_DENIED", "owner_only")).why).toBe("Roli vlastníka mění jen vlastník.");
    expect(changeOf(rec("MEMBER_ROLE_DENIED", "last_owner")).why).toBe("Jediný aktivní vlastník organizace o roli přijít nemůže.");
    expect(changeOf(rec("AIA_SESSION_DENIED", "identity_mismatch")).why).toBe("přihlášení neodpovídá účtu, ke kterému e-mail patří");
    expect(changeOf(rec("CLIENT_KNOWLEDGE_DECIDED", "APPROVED", { decision: "REVIEWED" }))).toEqual({ change: "schváleno", why: null });
    expect(changeOf(rec("CLIENT_KNOWLEDGE_DECIDED", "REJECTED")).change).toBe("zamítnuto");
  });

  it("keeps the reason of a record it knows no shape for, and invents no change", () => {
    expect(changeOf(rec("MEMBER_DEACTIVATED", "Odchod z agentury"))).toEqual({ change: null, why: "Odchod z agentury" });
    expect(changeOf(rec("SOMETHING_NEW", ""))).toEqual({ change: null, why: null });
    expect(changeOf({ action: "CLIENT_RULES_CHANGED", reason: "", payload: null })).toEqual({ change: null, why: null });
  });

  it("names what an organization's record concerns: the module, the prompt, the rule (review of #955)", () => {
    expect(concernsOf(rec("METHODOLOGY_ACTIVATED", "", { module: "sociomap" }))).toBeTruthy();
    expect(concernsOf(rec("PROMPT_ACTIVATED", "", { prompt_id: "aia.research.lead" }))).toBeTruthy();
    expect(concernsOf(rec("DR_SETTING_APPROVED", "", { key: "retention.snapshots" }))).toBeTruthy();
    expect(concernsOf(rec("DR_SETTING_APPROVED", "", { key: "retention.snapshots" }))).not.toBe("retention.snapshots");
    expect(concernsOf(rec("STUDY_BUDGET_CHANGED", "", {}))).toBeNull();
  });
});
