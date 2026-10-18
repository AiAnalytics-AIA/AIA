/**
 * Which of today's acceptance rules a Deep Research review was merged under, from the sealed
 * bundle's own record (``versions.merge``), read as the report with literature reads it
 * (application/contextual_report.py over domain/deep_research topicality.judged_topic and
 * document_types.document_rules_of). A review merged before them is listed on Výsledky as it
 * accepted its findings, while its report, composed today, labels those today's rules would not
 * accept; the screen says so (review web#5). Pure.
 */
import { t, tv } from "@/i18n/t";

/** topicality.py ``TOPICALITY_PREFIX``: any version of the topic rules. */
export const TOPICALITY_PREFIX = "aia-dr-topicality-";
/** document_types.py ``DOCUMENT_RULES_PREFIX``: any version of the document rules. */
export const DOCUMENT_RULES_PREFIX = "aia-document-types-";

/** ``judged_topic``: whether the merge judged each finding's topic (the prefix anywhere in it). */
export const judgedTopic = (merge: string): boolean => merge.includes(TOPICALITY_PREFIX);

/** ``document_rules_of``: whether the merge typed each source's document (a part of its version). */
export const typedDocuments = (merge: string): boolean => merge.split("/").some((part) => part.startsWith(DOCUMENT_RULES_PREFIX));

/** The rules a review predates. A bundle without a merge version predates both, as the report reads it. */
export function rulesPredated(versions: Readonly<Record<string, string>>): { topic: boolean; documents: boolean } {
  const merge = versions.merge ?? "";
  return { topic: !judgedTopic(merge), documents: !typedDocuments(merge) };
}

const P = "research.deep.olderRules";

/**
 * What the literature screen says of a review merged before today's rules, or null when it was
 * merged under both: which rules it predates, that its findings are listed as it accepted them,
 * and what the report composed under the current contract does with them. Today's topic check
 * reads the client's names from the review's stored plan (``todays_topic_rules`` over
 * ``frozen_request``), so it is said to apply only where that plan verifies; the document rules
 * read no plan. Null too without the bundle's versions, which the API always sends (they are
 * sealed with it): a bundle read without them says nothing of its rules, and nothing is said for it.
 */
export function olderRulesWords(versions: Readonly<Record<string, string>> | null | undefined): { title: string; text: string } | null {
  if (!versions) return null;
  const { topic, documents } = rulesPredated(versions);
  if (!topic && !documents) return null;
  const rules = topic && documents ? t(`${P}.both`) : topic ? t(`${P}.topic`) : t(`${P}.documents`);
  return {
    title: t(`${P}.title`),
    text: tv(`${P}.text`, { rules, documents: documents ? t(`${P}.documentsHow`) : "", topicPlan: topic ? t(`${P}.topicPlan`) : "" }),
  };
}
