// "Ověřeno, přidat zdroj" in words (plan inline-decisions chunk 1): what the button says before and
// after a person adds a source they checked to the client's knowledge, and where it links. Pure: the
// server decides what was written (VerifiedSourceAdded); this only reads its answer.

import type { DeepResearchBundle, VerifiedSourceAdded } from "./api";
import { appRoutes } from "./app-routes";

export const VERIFY_LABEL = "Ověřeno, přidat zdroj";

/** What the button reads after the server answered, and the link beside it (null: none). */
export function verifiedSourceWords(clientId: string, r: VerifiedSourceAdded): { label: string; href: string | null } {
  const item = r.item_id ? appRoutes.knowledgeItem(clientId, r.item_id) : null;
  if (r.status === "added") return { label: "Přidáno do znalostí", href: item };
  if (r.status === "proposed") return { label: "Čeká na schválení ve znalostech", href: `${appRoutes.area(clientId, "knowledge")}?view=review` };
  return { label: "Už je ve znalostech", href: item ?? `${appRoutes.area(clientId, "knowledge")}?view=review` };
}

/**
 * The captured source an accepted finding cites, when it is a web page the run holds: the snapshot
 * the button names. A finding from the client's own knowledge (no snapshot) has none: it is
 * knowledge already.
 */
export function citedSnapshot(bundle: DeepResearchBundle, evidenceId: string): { snapshotId: string; url: string } | null {
  const finding = bundle.accepted.find((a) => a.evidence.evidence_id === evidenceId);
  if (!finding) return null;
  const snapshot = bundle.snapshots.find((s) => s.snapshot_id === finding.evidence.source_ref);
  return snapshot && snapshot.url ? { snapshotId: snapshot.snapshot_id, url: snapshot.url } : null;
}
