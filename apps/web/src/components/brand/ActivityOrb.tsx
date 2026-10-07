"use client";

/**
 * An activity orb (thinking-orbs, MIT): shown only while the API reports a step
 * RUNNING -- lib/activity-orb.ts decides when and which. The dots are the
 * identity's lattice in motion, tinted with a theme colour read where the orb is
 * mounted, so light, dark and an ancestor data-theme all apply without a second
 * copy of the token: --ai-ink (the "AI úloha" badge) while a model thinks,
 * --status-running (the running chip) while code works. Decoration beside text
 * that already says the state, so hidden from assistive technology; the package
 * draws a still frame under prefers-reduced-motion.
 */

import { useEffect, useRef, useState } from "react";
import { ThinkingOrb, type OrbSize } from "thinking-orbs";

import type { Orb, OrbInk } from "@/lib/activity-orb";

const INK_PROPERTY: Record<OrbInk, string> = { ai: "--ai-ink", running: "--status-running" };

export function ActivityOrb({ orb, size = 20, className = "" }: { orb: Orb; size?: OrbSize; className?: string }) {
  const host = useRef<HTMLSpanElement>(null);
  const [ink, setInk] = useState<string | null>(null);
  const property = INK_PROPERTY[orb.ink];

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const read = () => setInk(getComputedStyle(el).getPropertyValue(property).trim() || null);
    read();
    const media = typeof window.matchMedia === "function" ? window.matchMedia("(prefers-color-scheme: dark)") : null;
    media?.addEventListener("change", read);
    const themes = new MutationObserver(read);
    themes.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"], subtree: true });
    return () => {
      media?.removeEventListener("change", read);
      themes.disconnect();
    };
  }, [property]);

  return (
    <span ref={host} aria-hidden="true" data-orb={orb.state} data-orb-ink={orb.ink} className={`inline-flex shrink-0 ${className}`} style={{ width: size, height: size }}>
      {/* Painted once the theme's ink is known, so it never flashes grey first. */}
      {ink ? <ThinkingOrb state={orb.state} size={size} color={ink} aria-hidden="true" /> : null}
    </span>
  );
}
