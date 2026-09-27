"use client";

// Interim, removed in the same pull request (legacy-phase-out.md chunk 5): the
// Audience and Dimenze steps still read their panel-derived catalogues from the
// 18.6.6 unit's bootstrap. The research session itself no longer does.

import { useEffect, useState } from "react";

import { loadBoot } from "@/unit/boot";

export function useUnitCatalogues(): Record<string, unknown> {
  const [raw, setRaw] = useState<Record<string, unknown>>({});
  useEffect(() => {
    let live = true;
    loadBoot().then(
      (b) => live && setRaw(b.raw),
      () => {},
    );
    return () => {
      live = false;
    };
  }, []);
  return raw;
}
