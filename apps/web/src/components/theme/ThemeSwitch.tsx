"use client";
// Client component: it reads and writes a per-viewer preference in localStorage
// and changes <html data-theme>, neither of which a server component can do.

import { useSyncExternalStore } from "react";
import { t } from "@/i18n/t";
import { THEMES, THEME_STORAGE_KEY, applyTheme, isThemePreference, type ThemePreference } from "./theme";

// The stored preference is external state, so it is read through
// useSyncExternalStore rather than copied into React state from an effect.
// The server snapshot is "system", which matches the first client render,
// so hydration never mismatches.
const CHANGE_EVENT = "aia-theme-change";
// When storage is unavailable (private window), the choice lives here for the page's lifetime.
let memoryPreference: ThemePreference = "system";

function readPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    return isThemePreference(stored) ? stored : "system";
  } catch {
    return memoryPreference;
  }
}

function persist(next: ThemePreference) {
  memoryPreference = next;
  applyTheme(next);
  try {
    if (next === "system") localStorage.removeItem(THEME_STORAGE_KEY);
    else localStorage.setItem(THEME_STORAGE_KEY, next);
  } catch {
    /* preference applies for this page only */
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

function subscribe(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener(CHANGE_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(CHANGE_EVENT, onChange);
  };
}

export function ThemeSwitch() {
  const pref = useSyncExternalStore(subscribe, readPreference, () => "system" as const);

  return (
    <fieldset className="flex gap-1 text-xs">
      <legend className="sr-only">{t("theme.label")}</legend>
      {THEMES.map((th) => (
        <label key={th} className="cursor-pointer rounded-sm border border-border-strong px-2 py-1 has-[:checked]:bg-signal-wash has-[:checked]:font-semibold has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus-ring">
          <input type="radio" name="aia-theme" value={th} checked={pref === th} onChange={() => persist(th)} className="sr-only" />
          {t(`theme.${th}`)}
        </label>
      ))}
    </fieldset>
  );
}
