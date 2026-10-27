"use client";

// The AIA shell (ADR 0015). One global navigation -- Klienti, Společenská
// inteligence, Projektová paměť, Nastavení, then Můj Vedoucí -- on the graphite Dock
// rail (DockRail: 64 px of icons, 240 px on hover or focus) that also names the
// client you are in, on every page, a study's too, and a page header that always says
// where you are: breadcrumbs from the client down, one title, one primary action.
// A client's areas are tabs under that header; a study's stages are the
// `aside` rail, and only inside the study. Nothing anywhere hands off to the
// 18.6.6 interface (ADR 0018).

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { t } from "@/i18n/t";
import type { ClientArea } from "@/lib/app-routes";
import { Icon, type IconName } from "../rehome/icons";
import { CommandPalette } from "./CommandPalette";
import { DockRail, initials } from "./DockRail";
import { Hero, type HeroEdit, type HeroFigure } from "./Hero";

/** A breadcrumb; `prefix` is a muted word before its label ("Organizace" before the name). */
export type Crumb = { label: string; href?: string; prefix?: string };
/**
 * A tab, optionally with a count: `countLabel` says it in words for a screen reader
 * ("3 čekají na schválení"), `attention` marks a count that waits on a person.
 */
export type Tab = { key: string; label: string; href: string; active: boolean; count?: number | null; countLabel?: string; attention?: boolean };
/** The client a page belongs to: named on the sidebar, its accent on its monogram. */
export type ShellClient = { id: string; name: string };

// A client area's tab: its icon, the signal mark on its wash when active, quiet grey otherwise
// (design system v3: no wayfinding hue in the chrome, where colour would read as a status).
const AREA_LOOK: Record<ClientArea, { icon: IconName }> = {
  overview: { icon: "home" },
  research: { icon: "research" },
  simulations: { icon: "simulation" },
  knowledge: { icon: "knowledge" },
  data: { icon: "data" },
  profile: { icon: "client" },
};

// The six client accents of the design system; a client keeps the same one wherever it is drawn.
const CLIENT_ACCENT = ["bg-client-1", "bg-client-2", "bg-client-3", "bg-client-4", "bg-client-5", "bg-client-6"] as const;

export function clientAccent(clientId: string): (typeof CLIENT_ACCENT)[number] {
  let h = 0;
  for (const ch of clientId) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return CLIENT_ACCENT[h % CLIENT_ACCENT.length];
}

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";

/** The trail. `end`, a control that names the current page (Settings: the section menu), is its
 *  last step inside the list; no crumb is then the current page, the control is. */
function Breadcrumbs({ crumbs, strong = false, end }: { crumbs: Crumb[]; strong?: boolean; end?: ReactNode }) {
  if (!crumbs.length && !end) return null;
  return (
    <nav aria-label={t("aia.breadcrumbs")}>
      <ol className={`flex flex-wrap items-center gap-1 text-ink-muted ${strong ? "text-[13px] leading-5" : "text-sm"}`}>
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1 && !end;
          return (
            <li key={`${c.label}-${i}`} className="flex items-center gap-1">
              {i > 0 ? <span aria-hidden="true" className={strong ? "" : "text-ink-faint"}>/</span> : null}
              {c.prefix ? <span>{c.prefix}</span> : null}
              {c.href && !last ? (
                <Link href={c.href} className={`whitespace-nowrap rounded-sm no-underline hover:text-ink hover:underline ${FOCUS}`}>
                  {c.label}
                </Link>
              ) : (
                <span aria-current={last ? "page" : undefined} className={`break-words ${last || strong ? "font-medium text-ink" : ""}`}>
                  {c.label}
                </span>
              )}
            </li>
          );
        })}
        {end ? (
          <li className="flex items-center gap-1">
            {crumbs.length ? <span aria-hidden="true" className={strong ? "" : "text-ink-faint"}>/</span> : null}
            {end}
          </li>
        ) : null}
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
  alignActionStart = false,
  status,
  tabs,
  client,
  back,
  aside,
  track,
  topbar = false,
  crumbEnd,
  bleed = false,
  hero = false,
  figures,
  edit,
  children,
}: {
  crumbs?: Crumb[];
  title: string;
  sub?: string;
  /** A short line above the title, e.g. the step of a research. */
  eyebrow?: ReactNode;
  /** The page's one dominant action. */
  action?: ReactNode;
  /** Context cards align with the title rather than pushing it to their bottom. */
  alignActionStart?: boolean;
  /** A state the page is in (the save state of a study), right of the title. */
  status?: ReactNode;
  /** The areas of a client, under the header. */
  tabs?: Tab[];
  /** The client this page belongs to: on the sidebar, and its accent on its monogram. */
  client?: ShellClient;
  /** A way back above the breadcrumbs (a study's stage goes back to its client). */
  back?: { href: string; label: string };
  /** The rail of the open study: its stages. Never global navigation. */
  aside?: ReactNode;
  /**
   * The open study's stage track. Its presence puts the shell in study mode: icons-only
   * global navigation, a one-row header, the title at the top of the page.
   */
  track?: ReactNode;
  /** The header is the breadcrumb alone; the page draws its own heading (Settings: each tab's h1). */
  topbar?: boolean;
  /** With `topbar`: a control after the breadcrumb, as its last step (Settings: the section menu). */
  crumbEnd?: ReactNode;
  /** The page lays out its own columns and gutters, edge to edge under the header (Settings). */
  bleed?: boolean;
  /**
   * A top-level page's header is the hero (UI-1): the serif title at 40/46, the eyebrow, the lede
   * (`sub`), an edit chip and the figures. Never inside a study: a stage keeps its compact header.
   */
  hero?: boolean;
  /** With `hero`: the figures row; a value the page could not read is null and says "neznámé". */
  figures?: readonly HeroFigure[];
  /** With `hero`: whether the person may change what the page shows. */
  edit?: HeroEdit;
  children: ReactNode;
}) {
  const path = usePathname() ?? "";
  if (track) {
    return (
      <div className="flex min-h-screen flex-col bg-surface text-ink lg:flex-row">
        <a href="#aia-main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-control focus:bg-surface-raised focus:p-3 focus:text-ink">Přejít k obsahu</a>
        <DockRail path={path} client={client} accent={client ? clientAccent(client.id) : undefined} />
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="z-20 border-b border-border bg-surface-raised lg:sticky lg:top-0">
            <div className="flex min-h-[52px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-1.5 lg:px-6">
              {back ? (
                <Link href={back.href} aria-label={back.label} title={back.label} className={`inline-flex size-8 shrink-0 items-center justify-center rounded-control text-ink-muted no-underline hover:bg-surface-sunken hover:text-ink ${FOCUS}`}>
                  <Icon name="back" size={16} />
                </Link>
              ) : null}
              {client ? (
                <span aria-hidden="true" className={`inline-flex size-7 shrink-0 items-center justify-center rounded-control text-[11px] font-semibold text-on-client ${clientAccent(client.id)}`}>
                  {initials(client.name)}
                </span>
              ) : null}
              <div className="min-w-0 flex-1">
                <Breadcrumbs crumbs={crumbs} />
              </div>
              <CommandPalette />
              {status}
              {action}
            </div>
            {track}
          </header>
          <main id="aia-main-content" tabIndex={-1} className="min-w-0 flex-1 px-4 pb-10 pt-5 lg:px-6">
            <div className="mb-4 min-w-0">
              {eyebrow ? <div className="mb-1 font-mono text-[11px] uppercase leading-4 tracking-[0.08em] text-ink-faint">{eyebrow}</div> : null}
              <h1 className="text-[22px] font-semibold leading-7 tracking-[-0.01em]">{title}</h1>
              {sub ? <p className="mt-0.5 max-w-4xl text-sm leading-6 text-ink-muted">{sub}</p> : null}
            </div>
            {children}
          </main>
        </div>
      </div>
    );
  }
  return (
    <div className="flex min-h-screen flex-col bg-surface text-ink lg:flex-row">
      <a href="#aia-main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-control focus:bg-surface-raised focus:p-3 focus:text-ink">Přejít k obsahu</a>
      <DockRail path={path} client={client} accent={client ? clientAccent(client.id) : undefined} />

      <div className="flex min-w-0 flex-1 flex-col">
        {topbar ? (
          <header className="z-20 border-b border-border bg-surface-raised lg:sticky lg:top-0">
            {/* relative: a control in the trail anchors its panel to this row (the section menu). */}
            <div className="relative flex min-h-11 flex-wrap items-center gap-3 px-4 py-2.5 md:px-6">
              <div className="flex min-w-0 flex-wrap items-center gap-1 text-[13px] leading-5">
                <Breadcrumbs crumbs={crumbs.length || crumbEnd ? crumbs : [{ label: title }]} strong end={crumbEnd} />
              </div>
              <div className="ml-auto flex flex-wrap items-center gap-3"><CommandPalette chord={!path.startsWith("/app/settings")} />{status}{action}</div>
            </div>
          </header>
        ) : (
        // A hero scrolls with its page, as the prototype draws it; the plain header stays pinned.
        <header data-shell-header="" className={`z-20 border-b border-border bg-surface-raised px-4 pt-[15px] lg:px-6 xl:px-8 ${hero ? "" : "lg:sticky lg:top-0"}`}>
          <div className="mx-auto max-w-[88rem]">
            {back ? (
              <Link
                href={back.href}
                className={`mb-2.5 inline-flex min-h-7 items-center gap-1.5 whitespace-nowrap rounded-control border border-border bg-surface pl-1.5 pr-2.5 text-[13px] font-medium leading-[18px] text-ink no-underline hover:border-border-strong hover:bg-surface-sunken ${FOCUS}`}
              >
                <Icon name="back" size={14} />
                {back.label}
              </Link>
            ) : null}
            {/* The palette sits on the trail's row; a page with no trail keeps it beside its action. */}
            {crumbs.length ? (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <Breadcrumbs crumbs={crumbs} />
                <div className="ml-auto"><CommandPalette /></div>
              </div>
            ) : null}
            {hero ? (
              <div className="pb-[22px] pt-3">
                <Hero eyebrow={eyebrow} title={title} lede={sub} edit={edit} figures={figures} aside={status}
                  action={crumbs.length ? action : <span className="flex flex-wrap items-center gap-3"><CommandPalette />{action}</span>} />
              </div>
            ) : (
            <div className={`flex flex-wrap ${alignActionStart ? "items-start" : "items-end"} justify-between gap-4 pb-5 pt-2`}>
              <div className="min-w-0 max-w-3xl">
                {eyebrow ? (
                  <div className="mb-2 inline-flex items-center gap-2.5 whitespace-nowrap rounded-pill bg-signal-wash px-2.5 py-[3px] font-mono text-[11px] uppercase leading-4 tracking-[0.08em] text-signal">
                    {eyebrow}
                  </div>
                ) : null}
                <h1 className="text-[28px] font-semibold leading-9 tracking-[-0.02em]">{title}</h1>
                {sub ? <p className="mt-1 text-sm leading-6 text-ink-muted">{sub}</p> : null}
              </div>
              <div className="flex flex-wrap items-center gap-3">
                {crumbs.length ? null : <CommandPalette />}
                {status}
                {action}
              </div>
            </div>
            )}
            {tabs?.length ? (
              <nav aria-label={t("aia.client.tabsLabel")} className="-mb-px flex flex-wrap gap-0.5">
                {tabs.map((tab) => {
                  const look = AREA_LOOK[tab.key as ClientArea];
                  return (
                    <Link
                      key={tab.key}
                      href={tab.href}
                      aria-current={tab.active ? "page" : undefined}
                      className={`inline-flex items-center gap-1.5 whitespace-nowrap border-b-2 px-2.5 pb-2.5 pt-1 text-sm no-underline ${FOCUS} ${tab.active ? "border-signal font-semibold text-ink" : "border-transparent font-medium text-ink-muted hover:text-ink"}`}
                    >
                      {look ? (
                        <span aria-hidden="true" className={`inline-flex size-[22px] items-center justify-center rounded-[5px] ${tab.active ? "bg-signal-wash text-signal" : "text-ink-faint"}`}>
                          <Icon name={look.icon} size={13} />
                        </span>
                      ) : null}
                      {tab.label}
                      {tab.count != null && tab.count > 0 ? (
                        <span
                          aria-hidden="true"
                          className={`ml-0.5 inline-flex min-h-[18px] min-w-[18px] items-center justify-center rounded-pill px-1.5 font-mono text-[11px] font-semibold leading-4 ${tab.attention ? "bg-status-you text-ink" : "bg-surface-sunken text-ink-muted"}`}
                        >
                          {tab.count}
                        </span>
                      ) : null}
                      {tab.count != null && tab.count > 0 && tab.countLabel ? <span className="sr-only">, {tab.countLabel}</span> : null}
                    </Link>
                  );
                })}
              </nav>
            ) : null}
          </div>
        </header>
        )}
        <div className="flex min-w-0 flex-1 flex-col xl:flex-row">
          {aside ? (
            <aside className="shrink-0 border-b border-border bg-surface-raised xl:w-56 xl:border-b-0 xl:border-r">{aside}</aside>
          ) : null}
          {bleed ? (
            <main id="aia-main-content" tabIndex={-1} className="flex min-w-0 flex-1 flex-col">{children}</main>
          ) : (
          <main id="aia-main-content" tabIndex={-1} className="min-w-0 flex-1 px-4 py-5 lg:px-6 xl:px-8">
            <div className="mx-auto max-w-[88rem]">{children}</div>
          </main>
          )}
        </div>
      </div>
    </div>
  );
}
