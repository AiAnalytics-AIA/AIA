// The data class of each of the Brief's materials, as Podklady prints it (artifact-brief BRF3).
// The class is the server's (GET …/workspace/materials, aia_core.domain.brief_material_classes):
// the web prints what it is told and never decides one. An entry the server named no class for
// prints "třída neznámá" -- never C, never guessed.

import { t } from "@/i18n/t";
import type { Attachment } from "@/research/model";

export type DataClass = "CLASS_A_CLIENT_CONFIDENTIAL" | "CLASS_B_DERIVED_CLIENT" | "CLASS_C_INTERNAL";

/** One entry of `briefing.attachments` as the server classed it. */
export type MaterialClass = {
  index: number;
  kind: "file" | "url" | null;
  ref: string | null;
  data_class: string | null;
  class_source: string | null;
};

export type BriefMaterials = { revision: number | null; materials: MaterialClass[] };

const CLASSES: readonly DataClass[] = ["CLASS_A_CLIENT_CONFIDENTIAL", "CLASS_B_DERIVED_CLIENT", "CLASS_C_INTERNAL"];

/** A class the server answered, in words as V2 prints them ("A · důvěrné klienta"); anything else is unknown. */
export function classLabel(dataClass: string | null): string {
  return CLASSES.includes(dataClass as DataClass) ? t(`research.brief.dataClass.${dataClass}`) : t("research.brief.dataClassUnknown");
}

const refOf = (x: Attachment): string | null => {
  const ref = x.kind === "url" ? x.url : x.attachment_id;
  return typeof ref === "string" && ref ? ref : null;
};

/**
 * The server's answer for the attachment at `index`, or undefined while there is none to read.
 * A file or link is matched by its artifact id or address, so a copy changed since the answer
 * still finds it; an entry that names neither is matched by position, and only when the answer
 * is for the revision this copy is at.
 */
export function classOf(
  answer: BriefMaterials | null,
  revision: number | null,
  x: Attachment,
  index: number,
): MaterialClass | undefined {
  if (!answer) return undefined;
  const ref = refOf(x);
  if (ref !== null) return answer.materials.find((m) => m.ref === ref && m.kind === (x.kind === "url" ? "url" : "file"));
  if (answer.revision === null || answer.revision !== revision) return undefined;
  return answer.materials.find((m) => m.index === index && m.ref === null);
}
