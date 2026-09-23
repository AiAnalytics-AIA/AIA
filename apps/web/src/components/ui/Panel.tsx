import type { ReactNode } from "react";

/** A bordered surface with an optional heading row. Replaces the demo's Card. */
export function Panel({ title, actions, flush = false, children, headingLevel = 2 }: {
  title?: string;
  actions?: ReactNode;
  /** No body padding — for tables that run edge to edge. */
  flush?: boolean;
  headingLevel?: 2 | 3;
  children: ReactNode;
}) {
  const H = headingLevel === 3 ? "h3" : "h2";
  return (
    <section aria-label={title} className="min-w-0 rounded-md border border-border bg-surface-raised">
      {title || actions ? (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
          {title ? <H className="text-[15px] font-semibold leading-5">{title}</H> : <span />}
          {actions}
        </div>
      ) : null}
      <div className={flush ? "overflow-x-auto" : "px-4 py-3"}>{children}</div>
    </section>
  );
}
