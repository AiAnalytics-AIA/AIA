import type { ReactNode } from "react";

/** A keyboard shortcut hint. Show only shortcuts actually bound for this viewer. */
export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-block min-w-[18px] rounded-sm border border-b-2 border-border-strong bg-surface-sunken px-1 text-center font-mono text-xs leading-4 text-ink-muted">
      {children}
    </kbd>
  );
}
