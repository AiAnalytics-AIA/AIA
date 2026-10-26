"use client";

// The settings pages' ⓘ (prototype v52-v58): a short explanation behind a real button, never only a
// hover. A keyboard and a touch open it (aria-expanded, aria-controls); the text it controls is the
// caller's, hidden until then. Dense beside its heading on a desktop (24 px), a 44 px target on a
// phone (I11), as on Studie a rozpočty (#892) and Deep Research (F8).

import { FOCUS } from "../../ui/parts";

export function InfoButton({ label, controls, expanded, onToggle, title }: {
  /** What the button explains, as a screen reader names it ("Co která role smí"). */
  label: string;
  /** The id of the element it opens. */
  controls: string;
  expanded: boolean;
  onToggle: () => void;
  /** The same text on hover, for a pointer. */
  title?: string;
}) {
  return (
    <button type="button" data-dense data-info={controls} aria-expanded={expanded} aria-controls={controls} aria-label={label} title={title}
      onClick={onToggle}
      className={`inline-flex size-11 shrink-0 items-center justify-center rounded-full align-middle text-sm font-normal text-ink-faint hover:text-ink sm:size-6 ${FOCUS}`}>ⓘ</button>
  );
}
