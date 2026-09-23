import { cs } from "@/i18n/cs";
import { evidenceGrade, type EvidenceGrade } from "@/design/evidence";

/**
 * The epistemic grade, as vector shapes — never font glyphs (the shipped faces
 * have none of ■ ▣ □ ⬚). Achromatic, so it survives greyscale print.
 *   measured ■ · calibrated ▣ · modelled □ · holdout pending ⬚ · unknown "?"
 */
export function EvidenceMark({ role, size = 8 }: { role: unknown; size?: number }) {
  const grade = evidenceGrade(role);
  const stroke = { fill: "none", stroke: "var(--evidence-mark)", strokeWidth: 1.2 } as const;
  let body: React.ReactNode;
  switch (grade) {
    case "measured":
      body = <rect x={0} y={0} width={8} height={8} fill="var(--evidence-mark)" />;
      break;
    case "calibrated":
      body = <><rect x={0.6} y={0.6} width={6.8} height={6.8} {...stroke} /><rect x={2.4} y={2.4} width={3.2} height={3.2} fill="var(--evidence-mark)" /></>;
      break;
    case "modelled":
      body = <rect x={0.6} y={0.6} width={6.8} height={6.8} {...stroke} />;
      break;
    case "holdout-pending":
      body = <rect x={0.6} y={0.6} width={6.8} height={6.8} {...stroke} strokeDasharray="1.4 1.2" />;
      break;
    case "unknown":
      // Drawn, not typed: a question mark as two paths, so no font is involved.
      body = <path d="M2.4 2.9a1.6 1.6 0 1 1 2.4 1.4c-.6.3-.8.6-.8 1.2v.4 M4 7.2v.4" fill="none" stroke="var(--evidence-mark)" strokeWidth={1.3} />;
      break;
  }
  return (
    <svg className="relative -top-px inline-block shrink-0" width={size} height={size} viewBox="0 0 8 8" role="img" aria-label={cs.evidence[grade].name} data-grade={grade}>
      {body}
    </svg>
  );
}

export function evidenceLabel(grade: EvidenceGrade): string {
  return cs.evidence[grade].long;
}
