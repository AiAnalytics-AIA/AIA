import type { ReactNode } from "react";

export function Section({ id, title, intro, children }: { id: string; title: string; intro?: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm">
      <h2 className="text-base font-semibold text-zinc-900">{title}</h2>
      {intro ? <p className="mt-1 max-w-3xl text-xs text-zinc-600">{intro}</p> : null}
      <div className="mt-3 space-y-4">{children}</div>
    </section>
  );
}

export function Subhead({ children }: { children: ReactNode }) {
  return <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{children}</h3>;
}

export function Unavailable({ what, reason }: { what: string; reason: string }) {
  return (
    <div className="rounded-md border border-dashed border-red-300 bg-red-50/40 p-3 text-xs text-red-800">
      <span className="font-semibold">{what}: nedostupné.</span> {reason}
    </div>
  );
}
