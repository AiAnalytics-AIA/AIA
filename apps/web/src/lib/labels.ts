import { cs } from "@/i18n/cs";
import { SCOPE_ROLE, parseEnum } from "@/design/enums";
import { PROJECT_TYPES } from "@/design/lifecycle";

/** Raw API strings → Czech labels for non-status vocabulary (statuses go through StatusChip). */

export function roleLabel(raw: string | null): string {
  if (raw == null) return "—";
  const r = parseEnum(SCOPE_ROLE, raw);
  return r ? cs.role[r] : `? ${raw}`;
}
export function lifecycleLabel(raw: string): string {
  const p = parseEnum(PROJECT_TYPES, raw);
  return p ? cs.lifecycle[p] : `? ${raw}`;
}
