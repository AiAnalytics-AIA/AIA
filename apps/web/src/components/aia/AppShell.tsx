"use client";

// The AIA shell (ADR 0015). One global navigation -- Klienti, Společenská
// inteligence, Projektová paměť, Nastavení -- and a page header that always says
// where you are: breadcrumbs from the client down, one title, one primary action.
// A client's areas are tabs under that header; a study's stages are the
// `aside` rail, and only inside the study. Nothing anywhere hands off to the
// 18.6.6 interface (ADR 0018).

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { t } from "@/i18n/t";
import { appRoutes } from "@/lib/app-routes";
import { useSession } from "@/lib/auth";
import { signOut } from "@/lib/session";
import { Icon, type IconName } from "../rehome/icons";

export type Crumb = { label: string; href?: string };
export type Tab = { key: string; label: string; href: string; active: boolean };

const NAV: { key: string; icon: IconName; href: string; match: (path: string) => boolean }[] = [
  { key: "navClients", icon: "client", href: appRoutes.clients(), match: (p) => p === "/app" || p.startsWith("/app/clients") },
  { key: "navIntelligence", icon: "intelligence", href: appRoutes.intelligence(), match: (p) => p.startsWith("/app/intelligence") },
  { key: "navMemory", icon: "memory", href: appRoutes.memory(), match: (p) => p.startsWith("/app/memory") },
  { key: "navSettings", icon: "settings", href: appRoutes.settings(), match: (p) => p.startsWith("/app/settings") },
];

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";

export function Breadcrumbs({ crumbs }: { crumbs: Crumb[] }) {
  if (!crumbs.length) return null;
  return (
    <nav aria-label={t("aia.breadcrumbs")}>
      <ol className="flex flex-wrap items-center gap-1 text-sm text-ink-muted">
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1;
          return (
            <li key={`${c.label}-${i}`} className="flex items-center gap-1">
              {i > 0 ? <span aria-hidden="true" className="text-ink-faint">/</span> : null}
              {c.href && !last ? (
                <Link href={c.href} className={`rounded-sm no-underline hover:text-ink hover:underline ${FOCUS}`}>
                  {c.label}
                </Link>
              ) : (
                <span aria-current={last ? "page" : undefined} className={last ? "font-medium text-ink" : undefined}>
                  {c.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function AppShell({
  crumbs = [],
  title,
  sub,
  eyebrow,
  action,
  status,
  tabs,
  aside,
  children,
}: {
  crumbs?: Crumb[];
  title: string;
  sub?: string;
  /** A short line above the title, e.g. the step of a research. */
  eyebrow?: ReactNode;
  /** The page's one dominant action. */
  action?: ReactNode;
  /** A state the page is in (the save state of a study), right of the title. */
  status?: ReactNode;
  /** The areas of a client, under the header. */
  tabs?: Tab[];
  /** The rail of the open study: its stages. Never global navigation. */
  aside?: ReactNode;
  children: ReactNode;
}) {
  const path = usePathname() ?? "";
  const session = useSession();
  return (
    <div className="flex min-h-screen bg-surface text-ink">
      <nav aria-label={t("aia.mainNav")} className="sticky top-0 flex h-screen w-56 shrink-0 flex-col border-r border-border bg-surface-sunken">
        <Link href={appRoutes.home()} className={`flex items-center gap-2.5 border-b border-border px-4 py-4 no-underline ${FOCUS}`}>
          {/* eslint-disable-next-line @next/next/no-img-element -- the identity's own SVG, served by this app */}
          <img src="/icon.svg" alt="" width={28} height={28} />
          <span className="text-sm font-semibold tracking-wide text-ink">{t("aia.product")}</span>
        </Link>
        <ul className="flex flex-col gap-0.5 p-2">
          {NAV.map((item) => {
            const active = item.match(path);
            return (
              <li key={item.key}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`flex min-h-9 items-center gap-2.5 rounded-sm px-2.5 text-sm no-underline ${FOCUS} ${active ? "bg-signal-wash font-semibold text-signal" : "text-ink hover:bg-surface-raised"}`}
                >
                  <Icon name={item.icon} />
                  {t(`aia.${item.key}`)}
                </Link>
              </li>
            );
          })}
        </ul>
        <div className="mt-auto border-t border-border p-3 text-xs text-ink-muted">
          {session?.email ? <div className="truncate" title={session.email}>{session.email}</div> : null}
          <button type="button" onClick={() => void signOut()} className={`mt-1 rounded-sm underline hover:text-ink ${FOCUS}`}>
            {t("aia.signOut")}
          </button>
        </div>
      </nav>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-border bg-surface px-8 pt-5">
          <div className="mx-auto max-w-[88rem]">
            <Breadcrumbs crumbs={crumbs} />
            <div className="flex flex-wrap items-end justify-between gap-4 pb-5 pt-2">
              <div className="min-w-0 max-w-3xl">
                {eyebrow ? <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-signal">{eyebrow}</div> : null}
                <h1 className="mt-0.5 text-2xl font-semibold tracking-tight">{title}</h1>
                {sub ? <p className="mt-1 text-sm leading-6 text-ink-muted">{sub}</p> : null}
              </div>
              <div className="flex flex-wrap items-center gap-3">
                {status}
                {action}
              </div>
            </div>
            {tabs?.length ? (
              <nav aria-label={t("aia.client.tabsLabel")} className="-mb-px flex gap-1 overflow-x-auto">
                {tabs.map((tab) => (
                  <Link
                    key={tab.key}
                    href={tab.href}
                    aria-current={tab.active ? "page" : undefined}
                    className={`whitespace-nowrap border-b-2 px-3 pb-2.5 pt-1 text-sm no-underline ${FOCUS} ${tab.active ? "border-signal font-semibold text-ink" : "border-transparent text-ink-muted hover:text-ink"}`}
                  >
                    {tab.label}
                  </Link>
                ))}
              </nav>
            ) : null}
          </div>
        </header>
        <div className="flex min-w-0 flex-1">
          {aside ? (
            <aside className="sticky top-0 h-screen w-60 shrink-0 overflow-y-auto border-r border-border bg-surface-sunken">{aside}</aside>
          ) : null}
          <main className="min-w-0 flex-1 px-8 py-6">
            <div className="mx-auto max-w-[88rem]">{children}</div>
          </main>
        </div>
      </div>
    </div>
  );
}
