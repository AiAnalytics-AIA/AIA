// One Phosphor Regular icon (prototype-build PBA5, UI-2), inline in currentColor. Beside its words
// it is hidden from assistive technology; alone it takes `label` as its accessible name. Icons
// never stand for a status: that is the status glyph's job (workbench/Glyph).

import { PHOSPHOR, type PhosphorName } from "./phosphor";

/** `mirror`: drawn left to right reversed, for an icon whose side matters (a panel on the right). */
export function PhosphorIcon({ name, size = 16, label, className, mirror = false }: { name: PhosphorName; size?: number; label?: string; className?: string; mirror?: boolean }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 256 256"
      fill="currentColor"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
      className={className}
      data-icon={name}
    >
      <path d={PHOSPHOR[name]} transform={mirror ? "matrix(-1 0 0 1 256 0)" : undefined} />
    </svg>
  );
}
