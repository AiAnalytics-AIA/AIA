"use client";

// The Dock rail (the look contract's frame; prototype-build PBA1, PBA2): one graphite rail on every
// page, a study's included. 64 px of icons at rest, 240 px with their words on hover or keyboard
// focus, opening over the page; the motion is the Settings prototype's and stops under reduced
// motion (dock-rail.css). Its items: the brand, the client you are in, the four global places, then
// Můj Vedoucí as an item of its own, the account and sign-out. Below 1024 px it is the top bar
// with its menu. The navigation icons are the rail's own drawings (UI-2 keeps them).

import Link from "next/link";
import { useEffect, useState } from "react";

import { t } from "@/i18n/t";
import { researcherLead } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { useSession } from "@/lib/auth";
import { hatchedRemembered, LEAD_HATCHED_EVENT, type LeadPresence, leadPresence, railLeadItem, rememberPresence } from "@/lib/rail-lead";
import { signOut } from "@/lib/session";

import { RailIcon, type RailIconName } from "../rehome/icons";
import { PhosphorIcon } from "../icons/PhosphorIcon";
import { Mark } from "../workbench/Icons";
import "./dock-rail.css";

export type RailClient = { id: string; name: string };

// Wayfinding tints (tokens hue-*, shell-hue-*): an active item's tile is filled with its hue, an
// inactive one shows the hue on the graphite. Never a status.
const NAV: { key: string; icon: RailIconName; href: string; tile: string; idle: string; match: (path: string) => boolean }[] = [
  { key: "navClients", icon: "client", href: appRoutes.clients(), tile: "bg-hue-blue text-shell-strong", idle: "text-shell-hue-blue", match: (p) => p === "/app" || p.startsWith("/app/clients") },
  { key: "navIntelligence", icon: "intelligence", href: appRoutes.intelligence(), tile: "bg-hue-green text-shell-strong", idle: "text-shell-hue-green", match: (p) => p.startsWith("/app/intelligence") },
  { key: "navMemory", icon: "memory", href: appRoutes.memory(), tile: "bg-hue-violet text-shell-strong", idle: "text-shell-hue-violet", match: (p) => p.startsWith("/app/memory") },
  { key: "navSettings", icon: "settings", href: appRoutes.settings(), tile: "bg-hue-slate text-shell-strong", idle: "text-shell-hue-slate", match: (p) => p.startsWith("/app/settings") },
];

/** Up to two letters: the first of the first two words ("Banka Horizont" → "BH"). */
export function initials(name: string): string {
  const words = name.trim().split(/[\s@._-]+/).filter(Boolean);
  return words.slice(0, 2).map((w) => w[0]!.toUpperCase()).join("") || "?";
}

/** GET /lead's hatched state for the rail: unknown until read, unknown when the read fails. */
function useLeadPresence(): LeadPresence {
  const [presence, setPresence] = useState<LeadPresence>(hatchedRemembered() ? "hatched" : "unknown");
  useEffect(() => {
    let live = true;
    if (hatchedRemembered()) return;
    researcherLead.get().then(
      (answer) => {
        const p = leadPresence(answer);
        rememberPresence(p);
        if (live) setPresence(p);
      },
      () => {
        if (live) setPresence("unknown");
      },
    );
    const hatched = () => {
      if (live) setPresence("hatched");
    };
    window.addEventListener(LEAD_HATCHED_EVENT, hatched);
    return () => {
      live = false;
      window.removeEventListener(LEAD_HATCHED_EVENT, hatched);
    };
  }, []);
  return presence;
}

export function DockRail({ path, client, accent }: { path: string; client?: RailClient; accent?: string }) {
  const [open, setOpen] = useState(false);
  // The pointer opens the rail when it moves onto it, not where it happens to rest when a page
  // loads: after a click on a rail item the next page's rail stays closed until the pointer moves.
  const [pointer, setPointer] = useState(false);
  // Escape puts the opened rail away while the pointer or focus is still on it (WCAG 1.4.13): it
  // stays put until the pointer comes back onto the rail or focus leaves it.
  const [dismissed, setDismissed] = useState(false);
  const session = useSession();
  const email = session?.email ?? null;
  const lead = railLeadItem(useLeadPresence());
  const leadActive = path.startsWith(appRoutes.lead());
  let i = 2;
  return (
    <div className="dock-slot">
      <div
        className="dock"
        data-rail=""
        data-open={open ? "true" : "false"}
        data-pointer={pointer ? "" : undefined}
        data-dismissed={dismissed ? "" : undefined}
        onKeyDown={(e) => {
          if (e.key === "Escape") setDismissed(true);
        }}
        onPointerEnter={(e) => {
          if (e.pointerType !== "touch") setDismissed(false);
        }}
        onPointerMove={(e) => {
          if (e.pointerType !== "touch" && !pointer) setPointer(true);
        }}
        onPointerLeave={() => setPointer(false)}
        onBlur={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDismissed(false);
        }}
      >
        <button type="button" aria-expanded={open} aria-controls="aia-main-navigation" onClick={() => setOpen(!open)} className="dock__bar">
          <span className="min-w-0 truncate">{t("aia.product")} · {client?.name ?? t("aia.workspaceLabel")}</span>
          <span>{open ? t("aia.menuClose") : t("aia.menuOpen")}</span>
        </button>
        <nav id="aia-main-navigation" aria-label={t("aia.mainNav")} className="dock__nav">
          <Link href={appRoutes.home()} className="dock__brand" style={{ ["--i" as string]: 0 }}>
            {/* eslint-disable-next-line @next/next/no-img-element -- the identity's own SVG, served by this app */}
            <img src="/skin/brand/aia-mark-on-graphite.svg" alt="" width={30} height={30} />
            <span className="dock__product">
              <b>{t("aia.product")}</b>
              <small aria-hidden="true">{t("aia.productSub")}</small>
            </span>
          </Link>
          {client ? (
            <div className="dock__client" data-rail-client="">
              <span aria-hidden="true" className={`dock__tile ${accent ?? ""}`}>{initials(client.name)}</span>
              <span className="dock__label" style={{ ["--i" as string]: 1 }}>
                <b>{client.name}</b>
                <Link href={appRoutes.clients()}>{t("aia.changeClient")}</Link>
              </span>
            </div>
          ) : null}
          <div aria-hidden="true" className="dock__sec" style={{ ["--i" as string]: 1 }}>{t("aia.workspaceLabel")}</div>
          <ul className="dock__list">
            {NAV.map((item) => {
              const active = item.match(path);
              const label = t(`aia.${item.key}`);
              return (
                <li key={item.key}>
                  <Link href={item.href} aria-current={active ? "page" : undefined} title={label} className="dock__item">
                    <span aria-hidden="true" className={`dock__tile ${active ? item.tile : item.idle}`}>
                      <RailIcon name={item.icon} />
                    </span>
                    <span className="dock__label" style={{ ["--i" as string]: i++ }}>{label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
          <Link href={lead.href} aria-current={leadActive ? "page" : undefined} title={lead.label} className="dock__item" data-rail-lead={lead.grow ? "grow" : "mine"}>
            <span aria-hidden="true" className="dock__tile">
              <Mark size={18} onDark />
            </span>
            <span className="dock__label" style={{ ["--i" as string]: 6 }}>{lead.label}</span>
          </Link>
        </nav>
        <div className="dock__foot">
          <Link href={appRoutes.settings()} aria-label={`${t("aia.account")}${email ? ` · ${email}` : ""}`} title={email ?? t("aia.account")} className="dock__account">
            <span aria-hidden="true" className="dock__avatar">{email ? initials(email.split("@")[0]!) : "?"}</span>
            <span aria-hidden="true" className="dock__who" style={{ ["--i" as string]: 7 }}>
              {email ? <b>{email}</b> : null}
              <span>{t("aia.account")}</span>
            </span>
          </Link>
          <button type="button" onClick={() => void signOut()} aria-label={t("aia.signOut")} title={t("aia.signOut")} className="dock__out" style={{ ["--i" as string]: 7 }}>
            <PhosphorIcon name="sign-out" />
          </button>
        </div>
      </div>
    </div>
  );
}
