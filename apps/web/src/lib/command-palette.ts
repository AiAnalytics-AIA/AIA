// The command palette's pure part (Ctrl/⌘ K, design system v3 CommandPalette): the places a
// person can go, grouped, and how typed text matches them. No React, no request.

import { t } from "@/i18n/t";
import type { ClientCard } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { SECTIONS } from "@/components/aia/settings/sections";

export type PaletteGroup = "go" | "clients" | "studies" | "settings";
export type PaletteEntry = { id: string; group: PaletteGroup; label: string; sub?: string; href: string };

/** Lower case with the accents gone, so "rozpocet" finds "Rozpočet". */
export function fold(s: string): string {
  return s.toLocaleLowerCase("cs").normalize("NFD").replace(/\p{M}/gu, "");
}

/** The four global places, Můj Vedoucí and every settings section. */
export function staticEntries(): PaletteEntry[] {
  const go: PaletteEntry[] = [
    { id: "go:clients", group: "go", label: t("aia.navClients"), href: appRoutes.clients() },
    { id: "go:intelligence", group: "go", label: t("aia.navIntelligence"), href: appRoutes.intelligence() },
    { id: "go:memory", group: "go", label: t("aia.navMemory"), href: appRoutes.memory() },
    { id: "go:settings", group: "go", label: t("aia.navSettings"), href: appRoutes.settings() },
    { id: "go:lead", group: "go", label: t("aia.palette.lead"), href: appRoutes.lead() },
  ];
  const settings = SECTIONS.map((s): PaletteEntry => ({
    id: `settings:${s}`, group: "settings", label: t(`aia.settings.panel.tabs.${s}`), sub: t("aia.navSettings"), href: `${appRoutes.settings()}#${s}`,
  }));
  return [...go, ...settings];
}

/** Each client, and each of its recent studies, as the directory read them. */
export function clientEntries(clients: readonly ClientCard[]): PaletteEntry[] {
  return clients.flatMap((c) => [
    { id: `client:${c.client_id}`, group: "clients" as const, label: c.name, href: appRoutes.client(c.client_id) },
    ...c.recent.map((s): PaletteEntry => ({
      id: `study:${s.study_id}`, group: "studies", label: s.name, sub: c.name, href: appRoutes.study(c.client_id, s.study_id, s.kind),
    })),
  ]);
}

const ORDER: readonly PaletteGroup[] = ["go", "clients", "studies", "settings"];

/**
 * The entries the query matches, by every word typed, accents ignored, against the label and the
 * line under it; a label that starts with the query comes first within its group. An empty query
 * keeps everything in its order.
 */
export function matchEntries(entries: readonly PaletteEntry[], query: string, limit = 50): PaletteEntry[] {
  const words = fold(query).split(/\s+/).filter(Boolean);
  const hits = entries.filter((e) => {
    const hay = fold(`${e.label} ${e.sub ?? ""}`);
    return words.every((w) => hay.includes(w));
  });
  const starts = (e: PaletteEntry) => (words.length && fold(e.label).startsWith(words[0]!) ? 0 : 1);
  return hits
    .map((e, i) => ({ e, i }))
    .sort((a, b) => ORDER.indexOf(a.e.group) - ORDER.indexOf(b.e.group) || starts(a.e) - starts(b.e) || a.i - b.i)
    .slice(0, limit)
    .map((x) => x.e);
}

/** The next selected index when moving by `step`, wrapping at both ends; -1 when there is nothing. */
export function moveSelection(current: number, step: number, count: number): number {
  if (count <= 0) return -1;
  return (((current + step) % count) + count) % count;
}
