"use client";

// A Settings page's hero figures handed up by its panel (settings-redesign F18, part 2): a panel
// that reads its own route (Stav systému, Správa dat) knows its figures, and the page's hero, drawn by
// ControlPanel above it, does not. The panel hands them up through this context; outside a page that
// listens (a panel rendered alone, in a test) nothing is handed and nothing breaks.

import { type ReactNode, createContext, useContext, useEffect } from "react";

import type { Figure } from "@/lib/settings-hero";
import type { SectionId } from "./sections";

type Hand = (section: SectionId, figures: readonly Figure[] | undefined) => void;

const HeroFiguresContext = createContext<Hand | null>(null);

export function HeroFiguresProvider({ hand, children }: { hand: Hand; children: ReactNode }) {
  return <HeroFiguresContext.Provider value={hand}>{children}</HeroFiguresContext.Provider>;
}

/** Hand this section's figures to the page's hero; again whenever they change, and none on unmount. */
export function useHeroFigures(section: SectionId, figures: readonly Figure[] | undefined): void {
  const hand = useContext(HeroFiguresContext);
  // The figures are compared by value: a panel builds a new array on every render.
  const key = figures === undefined ? "" : JSON.stringify(figures);
  useEffect(() => {
    if (!hand) return;
    hand(section, key ? (JSON.parse(key) as Figure[]) : undefined);
    return () => hand(section, undefined);
  }, [hand, section, key]);
}
