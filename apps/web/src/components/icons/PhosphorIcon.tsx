// One Phosphor Regular icon (prototype-build PBA5, UI-2), inline in currentColor. Beside its words
// it is hidden from assistive technology; alone it takes `label` as its accessible name. Icons
// never stand for a status: that is the status glyph's job (workbench/Glyph).

import { PHOSPHOR, type PhosphorName } from "./phosphor";

export function PhosphorIcon({ name, size = 16, label, className }: { name: PhosphorName; size?: number; label?: string; className?: string }) {
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
      <path d={PHOSPHOR[name]} />
    </svg>
  );
}
