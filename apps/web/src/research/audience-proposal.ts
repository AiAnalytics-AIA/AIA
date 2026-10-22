// An audience proposal against the audience there is now (artifact-audience AUD5), pure. The
// propose_audience job changes the audience's description and keeps its criteria beside it
// (domain/research_agents.py proposal_result: audience.description and audience.ai_proposal);
// filters and strategy stay the person's, so nothing here touches them. ProposalReview draws it
// beside the plan's diff, which reads plan fields and finds nothing in an audience proposal.

import type { ResearchProject } from "./model";
import { diffLists, strings } from "./proposal-diff";

type ListDiff = ReturnType<typeof diffLists>;

export type AudienceProposalDiff = {
  /** The description, when the proposal changes it: what there is now (null: none) and what it proposes. */
  description: { before: string | null; after: string } | null;
  inclusion: ListDiff;
  exclusion: ListDiff;
  /** What the model says the proposal does not cover, and what it asks: read, never applied. */
  notes: string[];
  /** Change rows the review counts: the description and each criterion added or removed. */
  changes: number;
};

const record = (v: unknown): Record<string, unknown> => (v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {});
const text = (v: unknown): string => (typeof v === "string" ? v.trim() : "");

/**
 * A propose_audience job's `proposal` against `project`. Criteria are compared with those of the
 * AI proposal the audience already keeps (an earlier accept), so a first proposal adds every
 * criterion and a second names what moved.
 */
export function audienceProposalDiff(project: Pick<ResearchProject, "audience">, proposal: Record<string, unknown>): AudienceProposalDiff {
  const audience = record(project.audience);
  const kept = record(audience.ai_proposal);
  const now = text(audience.description);
  const proposed = text(proposal.description);
  const description = proposed && proposed !== now ? { before: now || null, after: proposed } : null;
  const inclusion = diffLists(strings(kept.inclusion_criteria), strings(proposal.inclusion_criteria));
  const exclusion = diffLists(strings(kept.exclusion_criteria), strings(proposal.exclusion_criteria));
  const changes = (description ? 1 : 0) + inclusion.added.length + inclusion.removed.length + exclusion.added.length + exclusion.removed.length;
  return { description, inclusion, exclusion, notes: [...strings(proposal.limitations), ...strings(proposal.questions_for_user)], changes };
}
