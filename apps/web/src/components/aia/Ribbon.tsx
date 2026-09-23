"use client";

export function RibbonGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-border bg-surface-sunken p-2">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">{title}</div>
      <div className="mt-2">{children}</div>
    </div>
  );
}

export function RibbonButton({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`min-h-9 rounded-sm border px-2 text-xs font-semibold [overflow-wrap:anywhere] transition-colors ${
        disabled
          ? "cursor-not-allowed border-border bg-surface-raised text-ink-faint"
          : "border-border bg-surface-raised text-ink hover:bg-surface-sunken"
      }`}
    >
      {children}
    </button>
  );
}
