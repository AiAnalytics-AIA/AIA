"use client";

// The rebuilt interface's shell (ADR 0014, area A1): the rail the classic
// interface has (ui_app.html `.sideTools`), item for item, and the page header.
// A rebuilt area is a route here; every other item hands off to the classic
// interface (src/lib/interface-handoff.ts) and says so. Client-side only for
// the active item.

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { classicHref, type ClassicTarget } from "@/lib/interface-handoff";
import { t } from "@/i18n/t";
import { unit } from "@/unit/client";
import { type RailStatus, parseBootstrap, parseClaudeCode } from "@/unit/shell";
import { Icon, type IconName } from "./icons";

type Item = { key: string; icon?: IconName } & ({ href: string } | { classic: ClassicTarget });
type Entry = Item | { group: string; icon: IconName; items: Item[] };

// The classic rail's order and targets: goHome(), switchProduct1776(...),
// openAssistant1791(), the Nastavení and Pokročilé groups, go('projects').
const ENTRIES: Entry[] = [
  { key: "navHome", icon: "home", classic: { go: "home" } },
  { key: "navSimulation", icon: "simulation", classic: { switch: "simulation" } },
  { key: "navResearch", icon: "research", classic: { switch: "research" } },
  { key: "navAssistant", icon: "assistant", classic: { assistant: "open" } },
  { key: "navLibrary", icon: "library", classic: { switch: "library" } },
  {
    group: "navSettings",
    icon: "settings",
    items: [
      { key: "navSettingsGeneral", classic: { go: "settings" } },
      { key: "navSettingsClaude", classic: { go: "settings" } },
      { key: "navDiagnostics", classic: { support: "bundle" } },
    ],
  },
  { group: "navAdvanced", icon: "command", items: [{ key: "navCommand", classic: { go: "command" } }] },
  { key: "navProjects", icon: "projects", href: "/app/projects" },
];

const ITEM = "flex min-h-9 items-center gap-2.5 rounded-sm px-2.5 text-sm no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";

function RailLink({ item, path }: { item: Item; path: string }) {
  const label = t(`rehome.${item.key}`);
  if ("href" in item) {
    const active = path === item.href || path.startsWith(`${item.href}/`);
    return (
      <Link
        href={item.href}
        aria-current={active ? "page" : undefined}
        className={`${ITEM} ${active ? "bg-signal-wash font-semibold text-signal" : "text-ink hover:bg-surface-raised"}`}
      >
        {item.icon ? <Icon name={item.icon} /> : null}
        <span className="flex-1">{label}</span>
        <span className="rounded-sm border border-signal-edge px-1 font-mono text-[10px] uppercase text-signal">{t("rehome.rebuiltBadge")}</span>
      </Link>
    );
  }
  return (
    <a href={classicHref(item.classic)} className={`${ITEM} text-ink-muted hover:bg-surface-raised hover:text-ink`}>
      {item.icon ? <Icon name={item.icon} /> : null}
      <span className="flex-1">{label}</span>
      <Icon name="external" size={12} className="opacity-50" />
      <span className="sr-only"> ({t("rehome.inClassic")})</span>
    </a>
  );
}

// One read per page load, shared by the brand line and the status lines.
let railStatus: Promise<RailStatus> | null = null;
function loadRailStatus(): Promise<RailStatus> {
  railStatus ??= Promise.all([
    unit("bootstrap").then(parseBootstrap, () => ({ release: null, jointCore: null })),
    unit("claudeCodeStatus").then(parseClaudeCode, () => null),
  ]).then(([b, claudeCode]) => ({ ...b, claudeCode }));
  return railStatus;
}
function useRailStatus(): RailStatus | null {
  const [s, setS] = useState<RailStatus | null>(null);
  useEffect(() => {
    let live = true;
    loadRailStatus().then((x) => live && setS(x));
    return () => {
      live = false;
    };
  }, []);
  return s;
}

function ReleaseTag() {
  const s = useRailStatus();
  return s?.release ? <span className="font-mono text-[11px] text-ink-faint">{s.release}</span> : null;
}

/** The classic rail's foot, from what the unit reports (src/unit/shell.ts). */
function RailStatusLines() {
  const s = useRailStatus();
  const lines: { label: string; code: string; tone: "done" | "you" | "neutral" }[] = [];
  if (s?.claudeCode) lines.push({ label: t("rehome.statusClaude"), code: s.claudeCode, tone: s.claudeCode === "READY" ? "done" : "you" });
  if (s?.jointCore) lines.push({ label: t("rehome.statusCore"), code: s.jointCore, tone: s.jointCore === "VALID" ? "done" : "neutral" });
  return (
    <dl className="mt-auto flex flex-col gap-1 border-t border-border px-4 py-3 text-xs">
      {lines.map((l) => (
        <div key={l.label} className="flex items-center gap-2">
          <Icon name={l.tone === "done" ? "done" : l.tone === "you" ? "you" : "dot"} size={12} className={l.tone === "you" ? "text-status-you-ink" : "text-ink-muted"} />
          <dt className="flex-1 text-ink-muted">{l.label}</dt>
          <dd className="font-mono text-[11px] text-ink">{l.code}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Shell({ title, sub, actions, children }: { title: string; sub?: string; actions?: ReactNode; children: ReactNode }) {
  const path = usePathname();
  return (
    <div className="flex min-h-screen bg-surface text-ink">
      <nav aria-label={t("rehome.mainMenu")} className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-border bg-surface-sunken">
        <div className="flex items-center gap-2.5 border-b border-border px-4 py-4">
          {/* eslint-disable-next-line @next/next/no-img-element -- the identity's own SVG, served by this app */}
          <img src="/icon.svg" alt="" width={28} height={28} />
          <div className="leading-tight">
            <div className="text-sm font-semibold tracking-wide">AI Analytics</div>
            <div className="text-xs text-ink-muted">
              {t("rehome.brandProduct")} <ReleaseTag />
            </div>
          </div>
        </div>
        <div className="px-4 pb-1.5 pt-4 font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint">{t("rehome.mainMenu")}</div>
        <ul className="flex flex-col gap-0.5 px-2">
          {ENTRIES.map((e) =>
            "group" in e ? (
              <li key={e.group}>
                <details className="group">
                  <summary className={`${ITEM} cursor-pointer list-none text-ink-muted hover:bg-surface-raised hover:text-ink`}>
                    <Icon name={e.icon} />
                    <span className="flex-1">{t(`rehome.${e.group}`)}</span>
                    <Icon name="back" size={12} className="-rotate-90 opacity-50 transition-transform group-open:rotate-90" />
                  </summary>
                  <ul className="ml-6 flex flex-col gap-0.5 border-l border-border pl-2">
                    {e.items.map((item) => (
                      <li key={item.key}>
                        <RailLink item={item} path={path} />
                      </li>
                    ))}
                  </ul>
                </details>
              </li>
            ) : (
              <li key={e.key}>
                <RailLink item={e} path={path} />
              </li>
            ),
          )}
        </ul>
        <RailStatusLines />
        <div className="border-t border-border p-2">
          <a href={classicHref()} className={`${ITEM} text-ink-muted hover:bg-surface-raised hover:text-ink`}>
            <Icon name="back" />
            <span className="flex-1">{t("rehome.classicInterface")}</span>
            <Icon name="external" size={12} className="opacity-50" />
          </a>
        </div>
      </nav>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-border bg-surface px-8 pb-5 pt-6">
          <div className="mx-auto flex max-w-[88rem] flex-wrap items-end justify-between gap-4">
            <div className="min-w-0 max-w-3xl">
              <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-signal">{t("rehome.eyebrow")}</div>
              <h1 className="mt-1 text-2xl font-semibold tracking-tight">{title}</h1>
              {sub ? <p className="mt-1 text-sm leading-6 text-ink-muted">{sub}</p> : null}
            </div>
            {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
          </div>
        </header>
        <main className="flex-1 px-8 py-6">
          <div className="mx-auto max-w-[88rem]">{children}</div>
        </main>
      </div>
    </div>
  );
}
