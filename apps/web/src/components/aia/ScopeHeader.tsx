import Link from "next/link";
import { ACCENT_BG, accentSlot, monogram } from "@/design/accent";
import { t } from "@/i18n/t";

type Crumb = { label: string; href?: string };

/**
 * The scope bar: which client (and study) this screen belongs to. The accent
 * band and monogram tile are a cue; the client's name is always written out
 * beside them, so colour is never the only signal (DS-2). A cross-client
 * screen gets the hatched "above the boundary" band instead of an accent.
 */
export function ScopeHeader({
  client,
  crumbs = [],
}: {
  client: { client_id: string; name: string; accent_slot?: number | null; href?: string } | null;
  crumbs?: Crumb[];
}) {
  if (!client) {
    return (
      <div data-scope="above" className="flex items-center gap-3 rounded-md border border-border bg-surface-raised">
        <span aria-hidden="true" className="h-10 w-1.5 self-stretch rounded-l-md [background:repeating-linear-gradient(135deg,var(--scope-above)_0_2px,transparent_2px_5px)]" />
        <span className="py-2 text-xs font-semibold uppercase tracking-[0.06em] text-ink-muted">{t("scope.aboveClients")}</span>
      </div>
    );
  }
  const slot = accentSlot(client.client_id, client.accent_slot);
  const fallback = client.accent_slot == null;
  return (
    <nav aria-label={t("scope.client")} data-scope="client" data-accent-slot={slot} className="flex min-w-0 items-center gap-3 rounded-md border border-border bg-surface-raised pr-3">
      <span aria-hidden="true" className={`w-1.5 self-stretch rounded-l-md ${ACCENT_BG[slot]}`} />
      <span aria-hidden="true" className={`my-2 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-sm text-sm font-semibold text-on-client ${ACCENT_BG[slot]}`}>
        {monogram(client.name)}
      </span>
      <ol className="flex min-w-0 flex-wrap items-center gap-x-2 py-2 text-sm">
        <li className="min-w-0">
          <span className="sr-only">{t("scope.client")}: </span>
          {client.href ? <Link className="font-semibold text-ink hover:underline" href={client.href}>{client.name}</Link> : <span className="font-semibold">{client.name}</span>}
        </li>
        {crumbs.map((c) => (
          <li key={c.label} className="flex min-w-0 items-center gap-2 text-ink-muted">
            <span aria-hidden="true">/</span>
            {c.href ? <Link className="hover:underline" href={c.href}>{c.label}</Link> : <span className="text-ink">{c.label}</span>}
          </li>
        ))}
      </ol>
      {fallback ? <span data-unavailable="client-accent" className="ml-auto hidden text-[11px] text-ink-faint lg:inline" title={t("scope.accentFallback")}>OI-12</span> : null}
    </nav>
  );
}
