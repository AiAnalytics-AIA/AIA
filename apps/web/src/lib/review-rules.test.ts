import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { t } from "@/i18n/t";
import { DOCUMENT_RULES_PREFIX, TOPICALITY_PREFIX, judgedTopic, olderRulesWords, rulesPredated, typedDocuments } from "./review-rules";

// The prefixes, today's merge version and cases as the rules read them;
// test_review_rules_web_fixture.py checks the server's side.
const RULES = JSON.parse(readFileSync(join(process.cwd(), "src/lib/fixtures/review-rules.json"), "utf8")) as {
  topicality_prefix: string;
  document_rules_prefix: string;
  current: string;
  cases: { merge: string; topic: boolean; documents: boolean }[];
};

/** What the screen says of the topic check's condition: the stored plan it reads must verify. */
const PLAN = "Kontrolu tématu přitom lze použít, jen když se podaří ověřit uložený plán rešerše, z něhož kontrola čte jména klienta.";

describe("which acceptance rules a review was merged under (review web#5)", () => {
  it("reads each case as the report reads it", () => {
    expect(TOPICALITY_PREFIX).toBe(RULES.topicality_prefix);
    expect(DOCUMENT_RULES_PREFIX).toBe(RULES.document_rules_prefix);
    for (const c of RULES.cases) {
      expect([c.merge, judgedTopic(c.merge), typedDocuments(c.merge)]).toEqual([c.merge, c.topic, c.documents]);
      expect(rulesPredated({ merge: c.merge })).toEqual({ topic: !c.topic, documents: !c.documents });
    }
    // A bundle without a merge version predates both, as the report reads it.
    expect(rulesPredated({})).toEqual({ topic: true, documents: true });
  });

  it("says nothing of a review merged under today's rules", () => {
    expect(olderRulesWords({ merge: RULES.current, harness: "x" })).toBeNull();
  });

  it("says which rules an older review predates, and what its report does with its findings", () => {
    const both = olderRulesWords({ merge: "aia-merge-1" });
    expect(both?.title).toBe(t("research.deep.olderRules.title"));
    expect(both?.text).toBe(
      "Tato rešerše vznikla před zavedením kontroly tématu a pravidel typů dokumentů. Níže jsou její zjištění tak, jak je tehdy přijala. " +
        "Zpráva s touto rešerší sestavená podle současné skladby je posoudí dnešními pravidly (typ dokumentu jen podle adresy a názvu zdroje) " +
        "a ta, která by neprošla, v ní označí s důvodem; žádné neodstraní a počty nemění. " +
        "Kontrolu tématu přitom lze použít, jen když se podaří ověřit uložený plán rešerše, z něhož kontrola čte jména klienta.",
    );
    const topic = olderRulesWords({ merge: "aia-merge-9/aia-document-types-2" });
    expect(topic?.text).toContain("před zavedením kontroly tématu. ");
    expect(topic?.text).not.toContain("typ dokumentu");
    expect(topic?.text).toContain(PLAN);
    const documents = olderRulesWords({ merge: "aia-merge-9/aia-dr-topicality-4/x" });
    expect(documents?.text).toContain("před zavedením pravidel typů dokumentů. ");
    expect(documents?.text).toContain("(typ dokumentu jen podle adresy a názvu zdroje)");
    // The document rules read no plan: nothing to say of one.
    expect(documents?.text).not.toContain("plán rešerše");
  });

  it("says the topic check applies only where the review's stored plan verifies (review web#5, cross-review)", () => {
    // Today's topic check reads the client's names from the review's stored plan
    // (contextual_report: frozen_request); where that plan does not verify, the report does not
    // label by topic, so the screen must not promise it unconditionally.
    for (const merge of ["aia-merge-1", "aia-merge-9/aia-document-types-2", ""]) {
      expect(olderRulesWords({ merge })?.text.endsWith(PLAN)).toBe(true);
    }
  });

  it("says nothing for a bundle read without its versions: nothing says which rules it ran under", () => {
    expect(olderRulesWords(undefined)).toBeNull();
    expect(olderRulesWords(null)).toBeNull();
  });
});
