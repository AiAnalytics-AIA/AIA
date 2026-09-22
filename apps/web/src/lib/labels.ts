import { cs } from "@/i18n/cs";
import { SCOPE_ROLE, parseEnum } from "@/design/enums";
import { PROJECT_TYPES } from "@/design/lifecycle";
import { appearance } from "@/design/status";

/** Raw API strings → Czech labels. Unknown values are shown as themselves, marked — never mapped to a known label. */
export const stageStatusLabel = (raw: string) => appearance("StageStatus", raw).label;
export const projectStatusLabel = (raw: string) => appearance("ProjectStatus", raw).label;
export const studyStatusLabel = (raw: string) => appearance("StudyStatus", raw).label;

export function roleLabel(raw: string | null): string {
  if (raw == null) return "—";
  const r = parseEnum(SCOPE_ROLE, raw);
  return r ? cs.role[r] : `? ${raw}`;
}
export function lifecycleLabel(raw: string): string {
  const p = parseEnum(PROJECT_TYPES, raw);
  return p ? cs.lifecycle[p] : `? ${raw}`;
}
