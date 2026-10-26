"use client";

// The AIA shell (ADR 0015), drawn as Studio v3. One global navigation -- Klienti,
// Společenská inteligence, Projektová paměť, Nastavení -- on a graphite sidebar
// that also names the client you are in, and a page header that always says
// where you are: breadcrumbs from the client down, one title, one primary action.
// A client's areas are tabs under that header; a study's stages are the
// `aside` rail, and only inside the study. Nothing anywhere hands off to the
// 18.6.6 interface (ADR 0018).

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useState } from "react";

import { t } from "@/i18n/t";
import { type ClientArea, appRoutes } from "@/lib/app-routes";
import { useSession } from "@/lib/auth";
import { signOut } from "@/lib/session";
import { Icon, type IconName } from "../rehome/icons";

/** A breadcrumb; `prefix` is a muted word before its label ("Organizace" before the name). */
export type Crumb = { label: string; href?: string; prefix?: string };
/**
 * A tab, optionally with a count: `countLabel` says it in words for a screen reader
 * ("3 čekají na schválení"), `attention` marks a count that waits on a person.
 */
export type Tab = { key: string; label: string; href: string; active: boolean; count?: number | null; countLabel?: string; attention?: boolean };
/** The client a page belongs to: named on the sidebar, its accent across the header. */
export type ShellClient = { id: string; name: string };

// Wayfinding tints (tokens hue-*, shell-hue-*): an active item's tile is filled
// with its hue, an inactive one shows the hue on the graphite. Never a status.
const NAV: { key: string; icon: IconName; href: string; tile: string; idle: string; match: (path: string) => boolean }[] = [
  { key: "navClients", icon: "client", href: appRoutes.clients(), tile: "bg-hue-blue", idle: "text-shell-hue-blue", match: (p) => p === "/app" || p.startsWith("/app/clients") },
  { key: "navIntelligence", icon: "intelligence", href: appRoutes.intelligence(), tile: "bg-hue-green", idle: "text-shell-hue-green", match: (p) => p.startsWith("/app/intelligence") },
  { key: "navMemory", icon: "memory", href: appRoutes.memory(), tile: "bg-hue-violet", idle: "text-shell-hue-violet", match: (p) => p.startsWith("/app/memory") },
  { key: "navSettings", icon: "settings", href: appRoutes.settings(), tile: "bg-hue-slate", idle: "text-shell-hue-slate", match: (p) => p.startsWith("/app/settings") },
];

// A client area's tab: its icon, its hue filled when active, and a light wash of it otherwise.
const AREA_LOOK: Record<ClientArea, { icon: IconName; on: string; off: string; edge: string }> = {
  overview: { icon: "home", on: "bg-hue-blue", off: "bg-signal-wash text-hue-blue", edge: "border-hue-blue" },
  research: { icon: "research", on: "bg-hue-teal", off: "bg-hue-teal/12 text-hue-teal", edge: "border-hue-teal" },
  simulations: { icon: "simulation", on: "bg-hue-orange", off: "bg-hue-orange/12 text-hue-orange", edge: "border-hue-orange" },
  knowledge: { icon: "knowledge", on: "bg-hue-violet", off: "bg-hue-violet/12 text-hue-violet", edge: "border-hue-violet" },
  data: { icon: "data", on: "bg-hue-green", off: "bg-hue-green/12 text-hue-green", edge: "border-hue-green" },
  profile: { icon: "client", on: "bg-hue-slate", off: "bg-hue-slate/12 text-hue-slate", edge: "border-hue-slate" },
};

// The six client accents of the design system; a client keeps the same one wherever it is drawn.
const CLIENT_ACCENT = ["bg-client-1", "bg-client-2", "bg-client-3", "bg-client-4", "bg-client-5", "bg-client-6"] as const;

export function clientAccent(clientId: string): (typeof CLIENT_ACCENT)[number] {
  let h = 0;
  for (const ch of clientId) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return CLIENT_ACCENT[h % CLIENT_ACCENT.length];
}

/** Up to two letters: the first of the first two words ("Banka Horizont" → "BH"). */
function initials(name: string): string {
  const words = name.trim().split(/[\s@._-]+/).filter(Boolean);
  return words.slice(0, 2).map((w) => w[0]!.toUpperCase()).join("") || "?";
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

/** Inside a study the global navigation is icons only: the study gets the width (research-lane-redesign). */
function CompactSidebar({ path, client }: { path: string; client?: ShellClient }) {
  const [expanded, setExpanded] = useState(false);
  const session = useSession();
  const email = session?.email ?? null;
  return (
    <div className="flex w-full shrink-0 flex-col bg-shell text-shell-ink lg:sticky lg:top-0 lg:h-screen lg:w-16">
      <button type="button" aria-expanded={expanded} aria-controls="aia-main-navigation" onClick={() => setExpanded(!expanded)} className={`flex min-h-12 items-center justify-between px-4 text-sm font-semibold lg:hidden ${FOCUS}`}>
        <span>AI Analytics · {client?.name ?? t("aia.workspaceLabel")}</span><span>{expanded ? "Zavřít menu" : "Menu"}</span>
      </button>
      <nav id="aia-main-navigation" aria-label={t("aia.mainNav")} className={`${expanded ? "flex" : "hidden lg:flex"} min-h-0 flex-1 flex-col gap-1 px-2.5 py-3.5 lg:items-center lg:px-0`}>
        <Link href={appRoutes.home()} aria-label={t("aia.product")} title={t("aia.product")} className={`mb-2.5 inline-flex rounded-control no-underline ${FOCUS}`}>
          {/* eslint-disable-next-line @next/next/no-img-element -- the identity's own SVG, served by this app */}
          <img src="/skin/brand/aia-mark-on-graphite.svg" alt="" width={30} height={30} />
        </Link>
        {NAV.map((item) => {
          const active = item.match(path);
          const label = t(`aia.${item.key}`);
          return (
            <Link
              key={item.key}
              href={item.href}
              aria-label={label}
              title={label}
              aria-current={active ? "page" : undefined}
              className={`flex min-h-11 items-center gap-3 rounded-control px-2.5 text-sm no-underline lg:size-11 lg:justify-center lg:px-0 ${FOCUS} ${active ? "bg-shell-strong/12 text-shell-strong" : `${item.idle} hover:bg-shell-strong/8 hover:text-shell-strong`}`}
            >
              <Icon name={item.icon} size={18} />
              <span className="lg:sr-only">{label}</span>
            </Link>
          );
        })}
      </nav>
      <div className={`${expanded ? "flex" : "hidden lg:flex"} flex-col items-center gap-2 px-2 pb-3.5`}>
        <Link
          href={appRoutes.settings()}
          aria-label={`${t("aia.account")}${email ? ` · ${email}` : ""}`}
          title={email ?? t("aia.account")}
          className={`inline-flex size-8 items-center justify-center rounded-full bg-shell-avatar text-[11px] font-semibold text-shell-avatar-ink no-underline ${FOCUS}`}
        >
          {email ? initials(email.split("@")[0]!) : "?"}
        </Link>
        <button type="button" onClick={() => void signOut()} aria-label={t("aia.signOut")} title={t("aia.signOut")} className={`rounded-sm px-1 text-shell-muted hover:text-shell-strong ${FOCUS}`}>
          <span aria-hidden="true">⎋</span>
        </button>
      </div>
    </div>
  );
}

function Sidebar({ path, client }: { path: string; client?: ShellClient }) {
  const [expanded, setExpanded] = useState(false);
  const session = useSession();
  const email = session?.email ?? null;
  return (
    <div className="flex w-full shrink-0 flex-col bg-shell text-shell-ink lg:sticky lg:top-0 lg:h-screen lg:w-52 xl:w-60">
      <button type="button" aria-expanded={expanded} aria-controls="aia-main-navigation" onClick={() => setExpanded(!expanded)} className={`flex min-h-12 items-center justify-between px-4 text-sm font-semibold lg:hidden ${FOCUS}`}>
        <span>AI Analytics · {client?.name ?? t("aia.workspaceLabel")}</span><span>{expanded ? "Zavřít menu" : "Menu"}</span>
      </button>
      <nav id="aia-main-navigation" aria-label={t("aia.mainNav")} className={`${expanded ? "flex" : "hidden lg:flex"} min-h-0 flex-1 flex-col overflow-y-auto`}>
        <Link href={appRoutes.home()} className={`flex items-center gap-2.5 px-[18px] pb-4 pt-5 no-underline ${FOCUS}`}>
          {/* eslint-disable-next-line @next/next/no-img-element -- the identity's own SVG, served by this app */}
          <img src="/skin/brand/aia-mark-on-graphite.svg" alt="" width={30} height={30} />
          <span className="flex flex-col">
            <span className="text-[15px] font-semibold leading-5 tracking-[0.01em] text-shell-strong">{t("aia.product")}</span>
            <span aria-hidden="true" className="text-[11px] leading-[14px] text-shell-muted">{t("aia.productSub")}</span>
          </span>
        </Link>
        {client ? (
          <div className="mx-3 mt-1 flex items-center gap-2.5 rounded-control border border-shell-strong/8 bg-shell-strong/4 p-2.5">
            <span aria-hidden="true" className={`inline-flex size-8 shrink-0 items-center justify-center rounded-control text-xs font-semibold text-shell-strong ${clientAccent(client.id)}`}>
              {initials(client.name)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-semibold leading-[18px] text-shell-strong">{client.name}</span>
              <Link href={appRoutes.clients()} className={`block rounded-sm text-xs leading-4 text-shell-muted no-underline hover:text-shell-strong ${FOCUS}`}>
                {t("aia.changeClient")}
              </Link>
            </span>
          </div>
        ) : null}
        <div aria-hidden="true" className="px-5 pb-1.5 pt-5 text-[11px] font-semibold leading-4 tracking-[0.04em] text-shell-faint">{t("aia.workspaceLabel")}</div>
        <ul className="flex flex-col gap-0.5 px-2.5 pb-2">
          {NAV.map((item) => {
            const active = item.match(path);
            return (
              <li key={item.key}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`flex min-h-10 items-center gap-3 rounded-control px-2.5 text-sm no-underline ${FOCUS} ${active ? "bg-shell-strong/8 font-semibold text-shell-strong" : "text-shell-item hover:bg-shell-strong/6 hover:text-shell-strong"}`}
                >
                  <span aria-hidden="true" className={`inline-flex size-[26px] shrink-0 items-center justify-center rounded-control ${active ? `${item.tile} text-shell-strong` : `bg-shell-strong/6 ${item.idle}`}`}>
                    <Icon name={item.icon} size={15} />
                  </span>
                  {t(`aia.${item.key}`)}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className={`${expanded ? "flex" : "hidden lg:flex"} items-center gap-2.5 border-t border-shell-strong/8 px-4 py-3.5 text-xs leading-4 text-shell-muted`}>
        <span aria-hidden="true" className="inline-flex size-[30px] shrink-0 items-center justify-center rounded-full bg-shell-avatar text-[11px] font-semibold text-shell-avatar-ink">
          {email ? initials(email.split("@")[0]!) : "?"}
        </span>
        <span className="min-w-0 flex-1">
          {email ? <span className="block truncate font-medium text-shell-ink" title={email}>{email}</span> : null}
          <Link href={appRoutes.settings()} className={`rounded-sm text-shell-muted no-underline hover:text-shell-strong ${FOCUS}`}>
            {t("aia.account")}
          </Link>
        </span>
        <button
          type="button"
          onClick={() => void signOut()}
          aria-label={t("aia.signOut")}
          title={t("aia.signOut")}
          className={`rounded-sm px-1 text-shell-muted hover:text-shell-strong ${FOCUS}`}
        >
          <span aria-hidden="true">⎋</span>
        </button>
      </div>
    </div>
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
  /** The client this page belongs to: on the sidebar, and its accent across the header. */
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
  children: ReactNode;
}) {
  const path = usePathname() ?? "";
  // The header's top edge: the client's accent inside a client, quiet on settings, the signal elsewhere.
  const accent = client ? clientAccent(client.id) : path.startsWith("/app/settings") ? "bg-ink-muted" : "bg-signal";
  if (track) {
    return (
      <div className="flex min-h-screen flex-col bg-surface text-ink lg:flex-row">
        <a href="#aia-main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-control focus:bg-surface-raised focus:p-3 focus:text-ink">Přejít k obsahu</a>
        <CompactSidebar path={path} client={client} />
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="z-20 border-b border-border bg-surface-raised lg:sticky lg:top-0">
            <div aria-hidden="true" className={`h-[3px] ${accent}`} />
            <div className="flex min-h-[52px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-1.5 lg:px-6">
              {back ? (
                <Link href={back.href} aria-label={back.label} title={back.label} className={`inline-flex size-8 shrink-0 items-center justify-center rounded-control text-ink-muted no-underline hover:bg-surface-sunken hover:text-ink ${FOCUS}`}>
                  <Icon name="back" size={16} />
                </Link>
              ) : null}
              {client ? (
                <span aria-hidden="true" className={`inline-flex size-7 shrink-0 items-center justify-center rounded-control text-[11px] font-semibold text-shell-strong ${clientAccent(client.id)}`}>
                  {initials(client.name)}
                </span>
              ) : null}
              <div className="min-w-0 flex-1">
                <Breadcrumbs crumbs={crumbs} />
              </div>
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
      <Sidebar path={path} client={client} />

      <div className="flex min-w-0 flex-1 flex-col">
        {topbar ? (
          <header className="z-20 border-b border-border bg-surface-raised lg:sticky lg:top-0">
            <div aria-hidden="true" className={`h-[3px] ${accent}`} />
            {/* relative: a control in the trail anchors its panel to this row (the section menu). */}
            <div className="relative flex min-h-11 flex-wrap items-center gap-3 px-4 py-2.5 md:px-6">
              <div className="flex min-w-0 flex-wrap items-center gap-1 text-[13px] leading-5">
                <Breadcrumbs crumbs={crumbs.length || crumbEnd ? crumbs : [{ label: title }]} strong end={crumbEnd} />
              </div>
              {status || action ? <div className="ml-auto flex flex-wrap items-center gap-3">{status}{action}</div> : null}
            </div>
          </header>
        ) : (
        <header className="z-20 border-b border-border bg-surface-raised px-4 lg:sticky lg:top-0 lg:px-6 xl:px-8">
          <div aria-hidden="true" className={`-mx-4 mb-3 h-[3px] lg:-mx-6 xl:-mx-8 ${accent}`} />
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
            <Breadcrumbs crumbs={crumbs} />
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
                {status}
                {action}
              </div>
            </div>
            {tabs?.length ? (
              <nav aria-label={t("aia.client.tabsLabel")} className="-mb-px flex flex-wrap gap-0.5">
                {tabs.map((tab) => {
                  const look = AREA_LOOK[tab.key as ClientArea];
                  return (
                    <Link
                      key={tab.key}
                      href={tab.href}
                      aria-current={tab.active ? "page" : undefined}
                      className={`inline-flex items-center gap-1.5 whitespace-nowrap border-b-2 px-2.5 pb-2.5 pt-1 text-sm no-underline ${FOCUS} ${tab.active ? `${look?.edge ?? "border-signal"} font-semibold text-ink` : "border-transparent font-medium text-ink-muted hover:text-ink"}`}
                    >
                      {look ? (
                        <span aria-hidden="true" className={`inline-flex size-[22px] items-center justify-center rounded-[5px] ${tab.active ? `${look.on} text-shell-strong` : look.off}`}>
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
