import { describe, expect, it } from "vitest";

import { ACTION_NAMES, CATEGORY_NAMES, actionName, categoryOf, inPeriod } from "./audit";

// Every action code the API writes to the access audit, read from the server's code (apps/api,
// packages/aia_core: each AccessAuditRow(action=…) and _audit("…")), and #841's two.
const SERVER_ACTIONS = [
  "AIA_SESSION", "AIA_SESSION_DENIED", "CLIENT_BUDGET_CHANGED", "CLIENT_CONTACT_ADDED", "CLIENT_CONTACT_CHANGED",
  "CLIENT_CONTACT_REMOVED", "CLIENT_CREATED", "CLIENT_KNOWLEDGE_AUTHORED", "CLIENT_KNOWLEDGE_DECIDED",
  "CLIENT_KNOWLEDGE_FOLDER_CREATED", "CLIENT_KNOWLEDGE_FOLDER_DELETED", "CLIENT_KNOWLEDGE_FOLDER_RENAMED",
  "CLIENT_KNOWLEDGE_LABEL_CHANGED", "CLIENT_KNOWLEDGE_LABEL_CREATED", "CLIENT_KNOWLEDGE_LABEL_DELETED",
  "CLIENT_KNOWLEDGE_ORGANIZED", "CLIENT_KNOWLEDGE_SELECTED", "CLIENT_KNOWLEDGE_UNSELECTED", "CLIENT_PROFILE_CHANGED",
  "CLIENT_SOURCE_ADDED", "CLIENT_SOURCE_MARKED_INTERNAL", "CLIENT_SOURCE_REREAD", "CLIENT_SOURCE_UNMARKED_INTERNAL",
  "CLIENT_STATUS_CHANGED", "DR_SETTING_APPROVED", "DR_SETTING_PROPOSED", "DR_SETTING_WITHDRAWN",
  "DR_SETTING_PROPOSAL_WITHDRAWN", "DR_SETTING_PROPOSAL_DECLINED", "DR_TEST_POLICY_APPROVED",
  "DR_TEST_POLICY_PROPOSED", "DR_TEST_POLICY_WITHDRAWN", "IDENTITY_SUBJECT_CLEARED", "LEAD_ERASED", "LEAD_SEALED",
  "LEAD_UNSEALED", "MEMBER_ADDED", "MEMBER_DEACTIVATED", "MEMBER_REACTIVATED", "MEMBER_ROLE_DENIED",
  "METHODOLOGY_ACTIVATED", "METHODOLOGY_PROPOSED", "METHODOLOGY_RESET", "ORGANIZATION_CREATED", "PERMISSION_DENIED",
  "PROMPT_ACTIVATED", "PROMPT_RESET_TO_BASELINE", "PROMPT_VERSION_CREATED", "RESEARCH_LEAD_PREFERENCES_SET",
  "SELF_APPROVAL_CONFIGURED", "STUDY_BUDGET_CHANGED", "STUDY_CREATED", "STUDY_SPEND_CONFIRM_CHANGED",
  "STUDY_STATUS_CHANGED", "USER_DEACTIVATED",
];

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
