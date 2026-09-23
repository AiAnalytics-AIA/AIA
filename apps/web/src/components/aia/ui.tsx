import Link from "next/link";

export function Card({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-border bg-surface-raised p-4 ">
      {title ? <div className="mb-3 text-sm font-semibold text-ink">{title}</div> : null}
      <div className="text-sm text-ink-muted">{children}</div>
    </div>
  );
}

export function Pill({ children, tone = "zinc" }: { children: React.ReactNode; tone?: "zinc" | "amber" | "green" | "red" | "blue" }) {
  const map: Record<string, string> = {
    // Interim mapping onto tokens until chunk 3 replaces Pill with StatusChip.
    // "amber" is waiting-on-a-person only; there is no green in the status family.
    zinc: "bg-surface-sunken text-ink-muted border-border",
    amber: "bg-status-you-wash text-status-you-ink border-status-you",
    green: "bg-surface-sunken text-ink border-border",
    red: "bg-status-fault-wash text-status-fault border-status-fault",
    blue: "bg-signal-wash text-signal border-signal",
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${map[tone]}`}>{children}</span>
  );
}

export function AiaLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="text-sm font-medium text-signal hover:underline">
      {children}
    </Link>
  );
}
