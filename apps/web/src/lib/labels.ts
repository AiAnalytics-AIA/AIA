import { cs } from "@/i18n/cs";
import { PROJECT_STATUS, SCOPE_ROLE, STAGE_STATUS, STUDY_STATUS } from "@/design/enums";
import { PROJECT_TYPES } from "@/design/lifecycle";

/**
 * Raw API strings → Czech labels. An unknown value is shown as itself, marked,
 * never silently mapped to a known label. (Chunk 2 replaces this with the
 * enum-bound status maps.)
 */
function label<T extends string>(values: readonly T[], table: Record<T, string>, raw: string): string {
  return (values as readonly string[]).includes(raw) ? table[raw as T] : `? ${raw}`;
}

export const stageStatusLabel = (raw: string) => label(STAGE_STATUS, cs.status.stage, raw);
export const projectStatusLabel = (raw: string) => label(PROJECT_STATUS, cs.status.project, raw);
export const studyStatusLabel = (raw: string) => label(STUDY_STATUS, cs.status.study, raw);
export const roleLabel = (raw: string | null) => (raw == null ? "—" : label(SCOPE_ROLE, cs.role, raw));
export const lifecycleLabel = (raw: string) => label(PROJECT_TYPES, cs.lifecycle, raw);
