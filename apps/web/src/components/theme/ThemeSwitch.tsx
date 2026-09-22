"use client";
// Client component: it reads and writes a per-viewer preference in localStorage
// and changes <html data-theme>, neither of which a server component can do.

import { useEffect, useState } from "react";
import { t } from "@/i18n/t";
import { THEMES, THEME_STORAGE_KEY, applyTheme, isThemePreference, type ThemePreference } from "./theme";

export function ThemeSwitch() {
  const [pref, setPref] = useState<ThemePreference>("system");

  useEffect(() => {
    try {
      const stored = localStorage.getItem(THEME_STORAGE_KEY);
      if (isThemePreference(stored)) setPref(stored);
    } catch {
      /* storage unavailable: stay on system */
    }
  }, []);

  function choose(next: ThemePreference) {
    setPref(next);
    applyTheme(next);
    try {
      if (next === "system") localStorage.removeItem(THEME_STORAGE_KEY);
      else localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      /* preference applies for this page only */
    }
  }

  return (
    <fieldset className="flex gap-1 text-xs">
      <legend className="sr-only">{t("theme.label")}</legend>
      {THEMES.map((th) => (
        <label key={th} className="cursor-pointer rounded-sm border border-border-strong px-2 py-1 has-[:checked]:bg-signal-wash has-[:checked]:font-semibold has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus-ring">
          <input type="radio" name="aia-theme" value={th} checked={pref === th} onChange={() => choose(th)} className="sr-only" />
          {t(`theme.${th}`)}
        </label>
      ))}
    </fieldset>
  );
}
