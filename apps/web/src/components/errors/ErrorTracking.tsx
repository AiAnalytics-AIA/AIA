"use client";

import { useEffect } from "react";

import { loadConfig } from "@/lib/auth";
import { startErrorTracking } from "@/lib/error-tracking";

// Starts the browser's error reporter once per page load, from /config (a DSN or nothing).
// Renders nothing; a failed /config read leaves it off, never in the way of the page.
export function ErrorTracking() {
  useEffect(() => {
    loadConfig()
      .then((config) => startErrorTracking(config.errorTracking))
      .catch(() => undefined);
  }, []);
  return null;
}
