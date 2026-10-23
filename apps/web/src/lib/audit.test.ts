import { describe, expect, it } from "vitest";

import { ACTION_NAMES, CATEGORY_NAMES, actionName, categoryOf, inPeriod } from "./audit";
import auditActions from "./fixtures/audit-actions.json";

// Every action code the backend writes to the access audit: content_free.py's AUDIT_ACTIONS, copied
// to fixtures/audit-actions.json (the backend's own test holds that list to the repositories' writes).
// Beside it, the grant era's codes, which an upgraded database still holds.
const KEPT_ELSEWHERE = ["CLIENT_GRANT", "STUDY_GRANT", "CLIENT_SELF_GRANT", "CLIENT_REVOKE"];
const SERVER_ACTIONS = [...auditActions.actions, ...KEPT_ELSEWHERE];

describe("the audit's words", () => {
  it("names every action the server writes in Czech, none under Ostatní", () => {
    for (const a of SERVER_ACTIONS) {
      expect(ACTION_NAMES[a], a).toBeTruthy();
      expect(categoryOf(a), a).not.toBe("other");
    }
  });

  it("files each action where a person looks for it", () => {
    expect(categoryOf("STUDY_BUDGET_CHANGED")).toBe("money");
    expect(categoryOf("STUDY_SPEND_CONFIRM_CHANGED")).toBe("money");
    expect(categoryOf("MEMBER_DEACTIVATED")).toBe("access");
    expect(categoryOf("LEAD_SEALED")).toBe("lead");
    expect(categoryOf("CLIENT_KNOWLEDGE_FOLDER_DELETED")).toBe("clients");
    expect(categoryOf("CLIENT_DELETED")).toBe("data");
    expect(CATEGORY_NAMES[categoryOf("DR_SETTING_PROPOSAL_DECLINED")]).toBe("Deep Research");
    expect(categoryOf("CLIENT_RULES_CHANGED")).toBe("clients");
    expect(actionName("CLIENT_RULES_CHANGED")).toBe("Změna pravidel klienta");
    expect(categoryOf("CLIENT_DELETION_OBJECTS")).toBe("data");
    expect(categoryOf("WORKSPACE_MIGRATED")).toBe("data");
  });

  it("names the grant-era records an upgraded database keeps, in Czech, under access", () => {
    // Written before the grants were dropped (migration d8e2f4a6b1c3); access_audit keeps them.
    for (const a of ["CLIENT_GRANT", "STUDY_GRANT", "CLIENT_SELF_GRANT", "CLIENT_REVOKE"]) {
      expect(ACTION_NAMES[a], a).toBeTruthy();
      expect(actionName(a), a).not.toMatch(/[A-Z_]{4,}|grant|revoke/);
      expect(categoryOf(a), a).toBe("access");
    }
  });

  it("spells out a code it does not know, under Ostatní, never dropping it", () => {
    expect(actionName("SOMETHING_NEW_HAPPENED")).toBe("something new happened");
    expect(categoryOf("SOMETHING_NEW_HAPPENED")).toBe("other");
  });

  it("puts a record without a time in every period", () => {
    const now = new Date("2026-10-23T12:00:00Z");
    expect(inPeriod(null, "today", now)).toBe(true);
    expect(inPeriod("2026-10-23T08:00:00Z", "today", now)).toBe(true);
    expect(inPeriod("2026-10-20T08:00:00Z", "today", now)).toBe(false);
    expect(inPeriod("2026-10-20T08:00:00Z", "week", now)).toBe(true);
    expect(inPeriod("2026-09-01T08:00:00Z", "month", now)).toBe(false);
    expect(inPeriod("2026-09-01T08:00:00Z", "all", now)).toBe(true);
  });
});
